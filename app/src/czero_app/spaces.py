# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Typed space discovery and Admin policy transport over trusted Core services."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import QueryParams
from starlette.responses import JSONResponse
from czero_core.identity import PermissionDenied, Role
from czero_core.spaces import SpaceService, SpaceConflict
from czero_app.auth import RequestAccess


class ExactSpaceSelector:
    """Reject ambiguous query selectors without wrapping the receive stream."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type']=='http' and '/api/v1/' in scope['path']:
            selectors=QueryParams(scope.get('query_string', b'')).getlist('space_id')
            # Structured search has one selector in its typed JSON body. Reject
            # unsupported query selectors instead of silently using Shared.
            unsupported=scope['path'].endswith('/api/v1/knowledge/search/structured') and selectors
            if len(selectors)>1 or unsupported:
                response=JSONResponse({'detail':'invalid_space_request'},status_code=422,
                                      headers={'Cache-Control':'no-store'})
                return await response(scope,receive,send)
        await self.app(scope,receive,send)


class SpaceView(BaseModel):
    id: UUID
    name: str
    shared: bool
    revision: int
    created_at: datetime
    role: Literal['reader','editor','admin']


class SpacesView(BaseModel):
    spaces: list[SpaceView]


class SpaceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)


class GrantUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    role: Literal['reader','editor'] | None
    expected_revision: int = Field(ge=0, lt=2147483646)
    idempotency_key: str = Field(min_length=1, max_length=128)


class GrantView(BaseModel):
    space_id: UUID
    account_id: UUID
    role: Literal['reader','editor'] | None
    revision: int
    updated_at: datetime


class GrantsView(BaseModel):
    grants: list[GrantView]


def install_space_routes(app, database, auth, read_context, write_context):
    service = SpaceService(database, auth.access if auth else None)
    app.state.spaces = service
    operation = app.state.operation_catalog.bind

    def invoke(handler, *args, **kwargs):
        if auth is None: raise HTTPException(503, 'authentication_not_configured')
        try: return handler(*args, **kwargs)
        except PermissionDenied: raise
        except SpaceConflict: raise HTTPException(409, 'space_conflict') from None
        except ValueError: raise HTTPException(422, 'invalid_space_request') from None

    @app.get('/api/v1/spaces', response_model=SpacesView)
    @operation('spaces_list', 'Discover authorized spaces and effective roles; omitted content selectors use the legacy shared space.', Role.READER, SpacesView)
    def spaces(limit: int = 100, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return invoke(service.list, context.actor, limit=limit, offset=offset)

    @app.post('/api/v1/spaces', response_model=SpaceView, status_code=201)
    @operation('spaces_create', 'Create a protected space. Application Admins have access under actual OAuth scopes.', Role.ADMIN, SpaceView, read_only=False)
    def create(data: SpaceCreate, context: RequestAccess = Depends(write_context)):
        return invoke(service.create, context.actor, **data.model_dump())

    @app.get('/api/v1/spaces/{space_id}', response_model=SpaceView)
    @operation('spaces_get', 'Inspect an authorized space and the current effective role.', Role.READER, SpaceView, space_field='space_id')
    def get(space_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(service.get, context.actor, space_id)

    @app.get('/api/v1/spaces/{space_id}/grants', response_model=GrantsView)
    @operation('space_grants_list', 'Admin: inspect revisioned Reader/Editor grants. Shared policy is fixed; Admin access is implicit.', Role.ADMIN, GrantsView, space_field='space_id')
    def grants(space_id: UUID, limit: int = 100, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return invoke(service.list_grants, context.actor, space_id, limit=limit, offset=offset)

    @app.put('/api/v1/spaces/{space_id}/grants/{account_id}', response_model=GrantView)
    @operation('space_grants_set', 'Admin: set or revoke a space grant at its current revision (zero creates). Changes revoke affected delegated tokens; regrant cannot revive them.', Role.ADMIN, GrantView, read_only=False, space_field='space_id')
    def update(space_id: UUID, account_id: UUID, data: GrantUpdate, context: RequestAccess = Depends(write_context)):
        return invoke(service.set_grant, context.actor, space_id, account_id,
            Role(data.role) if data.role is not None else None,
            expected_revision=data.expected_revision, idempotency_key=data.idempotency_key)
    return service
