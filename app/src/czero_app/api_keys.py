# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Browser-only lifecycle for personal automation credentials."""
from uuid import UUID
from fastapi import Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from czero_core.identity import PermissionDenied


class KeyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=128, strict=True)
    scopes: list[str] = Field(min_length=1, max_length=2)
    space_ids: list[UUID] = Field(min_length=1, max_length=100)
    lifetime_days: int | None = Field(default=90, ge=1, le=365, strict=True)


def install(app, auth, read_context, write_context):
    if auth is None:
        return
    # The frozen released consumer remains usable while the producer is verified.
    # This feature is installed only when that Core explicitly provides it.
    try:
        from czero_core.api_keys import ApiKeyService
    except ModuleNotFoundError as error:
        if error.name != 'czero_core.api_keys':
            raise
        return
    config = auth.oidc.config
    service = ApiKeyService(auth.access, client_id=config.client_id,
        client_secret=config.client_secret, resource=config.public_origin.rstrip('/')+'/mcp')
    app.state.api_keys = service

    previous_validation = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def private_validation(request, error):
        if request.url.path.rstrip('/').endswith('/api/v1/api-keys'):
            return JSONResponse({'detail':'invalid_api_key_request'}, status_code=422,
                                headers={'Cache-Control':'no-store'})
        return await previous_validation(request, error)

    def browser(request, context):
        if request.headers.get('authorization') is not None or context.csrf_token is None:
            raise PermissionDenied()
        return context.actor

    @app.get('/api/v1/api-keys')
    def listing(request: Request, context=Depends(read_context)):
        return {'api_keys': service.list(browser(request, context)), 'csrf_token':context.csrf_token}

    @app.post('/api/v1/api-keys', status_code=201)
    def create(request: Request, data: KeyRequest, context=Depends(write_context)):
        actor = browser(request, context)
        try:
            return service.create(actor, name=data.name, scopes=set(data.scopes),
                space_ids=data.space_ids, lifetime_days=data.lifetime_days)
        except PermissionDenied:
            raise
        except ValueError:
            raise HTTPException(422, 'invalid_api_key_request') from None

    @app.delete('/api/v1/api-keys/{identifier}', status_code=204)
    def revoke(request: Request, identifier: UUID, context=Depends(write_context)):
        service.revoke(browser(request, context), identifier)
        return Response(status_code=204)
