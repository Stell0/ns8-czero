# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application-level approval of external clients; NS8 identity stays native."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from czero_core.identity import PermissionDenied, Role
from czero_core.oauth_clients import OAuthClientService, ClientConflict
from czero_app.auth import RequestAccess

Scope = Literal['c0:read', 'c0:write', 'c0:admin']


class ClientRegistration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    client_name: str = Field(min_length=1, max_length=128)
    redirect_uris: list[str] = Field(min_length=1, max_length=4)
    allowed_scopes: list[Scope] = Field(default=['c0:read'], min_length=1, max_length=3)


class ClientUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    expected_revision: int = Field(ge=1, le=2147483646)


class ClientView(BaseModel):
    client_id: UUID
    client_name: str
    redirect_uris: list[str]
    allowed_scopes: list[Scope]
    token_endpoint_auth_method: Literal['none']
    enabled: bool
    revision: int
    created_at: datetime


class ClientsView(BaseModel):
    clients: list[ClientView]


def install_oauth_routes(app, auth, read_context, write_context):
    service = OAuthClientService(auth.access if auth else None)
    app.state.oauth_clients = service
    operation = app.state.operation_catalog.bind

    def invoke(method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except PermissionDenied:
            raise
        except ClientConflict:
            raise HTTPException(409, 'oauth_client_conflict') from None
        except ValueError:
            raise HTTPException(422, 'invalid_oauth_client_request') from None

    @app.get('/api/v1/oauth/clients', response_model=ClientsView)
    @operation('oauth_clients_list', 'Inspect administrator-approved external clients', Role.ADMIN, ClientsView)
    def clients(context: RequestAccess = Depends(read_context)):
        return {'clients': invoke(service.list, context.actor)}

    @app.post('/api/v1/oauth/clients', response_model=ClientView, status_code=201)
    @operation('oauth_clients_register', 'Approve a public client with exact callbacks and bounded scopes', Role.ADMIN, ClientView, read_only=False)
    def register(data: ClientRegistration, context: RequestAccess = Depends(write_context)):
        return invoke(service.register, context.actor, data.client_name, data.redirect_uris, scopes=data.allowed_scopes)

    @app.put('/api/v1/oauth/clients/{client_id}', response_model=ClientView)
    @operation('oauth_clients_configure', 'Enable or disable a registered client with revision protection', Role.ADMIN, ClientView, read_only=False)
    def configure(client_id: UUID, data: ClientUpdate, context: RequestAccess = Depends(write_context)):
        return invoke(service.set_enabled, context.actor, client_id, **data.model_dump())
