# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""First-party workspace access transport; authorization remains in Core."""
from functools import partial
from uuid import UUID

from anyio import to_thread
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from czero_core.access import AccessConflict
from czero_core.identity import PermissionDenied
from czero_core.cimd import CimdRejected
from czero_core.client_onboarding import OnboardingRejected
from czero_core.oauth_clients import ClientConflict
from czero_core.oauth_grants import GrantRejected
from czero_core.workspace_access import WorkspaceAccessService
from czero_app.oauth import Scope


class RequestApproval(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    metadata_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    allowed_scopes: list[Scope] = Field(min_length=1, max_length=3)
    client_id: str | None = Field(default=None, max_length=36)
    expected_revision: int | None = Field(default=None, ge=1, le=2147483646)


def install_workspace_routes(app, grants, read_context, write_context, cimd):
    service = WorkspaceAccessService(grants)
    previous_validation = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def private_validation(request, error):
        path = request.url.path
        prefix = request.scope.get('root_path', '')
        if prefix and path.startswith(prefix+'/'):
            path = path[len(prefix):]
        if (path == '/api/v1/access/workspace' or path.startswith('/api/v1/access/requests/')
                or path.startswith('/api/v1/access/connections/')
                or path.startswith('/api/v1/access/accounts/') and path.endswith('/applications')):
            return JSONResponse({'detail': 'invalid_access_request'}, status_code=422,
                                headers={'Cache-Control': 'no-store'})
        return await previous_validation(request, error)

    def read_browser(request: Request, context=Depends(read_context)):
        if request.headers.get('authorization') is not None or context.csrf_token is None:
            raise PermissionDenied()
        return context

    def write_browser(request: Request, context=Depends(write_context)):
        if request.headers.get('authorization') is not None or context.csrf_token is None:
            raise PermissionDenied()
        return context

    if cimd is None:
        @app.exception_handler(CimdRejected)
        def unavailable_discovery(request, error):
            return JSONResponse({'detail': 'cimd_unavailable'}, status_code=409,
                                headers={'Cache-Control': 'no-store'})

        @app.exception_handler(OnboardingRejected)
        def unavailable_request(request, error):
            return JSONResponse({'detail': 'connection_request_unavailable'}, status_code=410,
                                headers={'Cache-Control': 'no-store'})

    @app.exception_handler(AccessConflict)
    def changed(request, error):
        return JSONResponse({'detail': 'access_changed'}, status_code=409,
                            headers={'Cache-Control': 'no-store'})

    @app.get('/api/v1/access/workspace')
    def overview(limit: int = 25, offset: int = 0, context=Depends(read_browser)):
        try:
            return {**service.overview(context.actor, limit=limit, offset=offset), 'connections_available': cimd is not None,
                    'discovery_enabled': cimd is not None and grants.cimd.enabled()}
        except ValueError as error:
            if isinstance(error, PermissionDenied):raise
            raise HTTPException(422, 'invalid_page') from None

    @app.get('/api/v1/access/accounts/{account_id}/applications')
    def applications(account_id: UUID, limit: int = 10, offset: int = 0, context=Depends(read_browser)):
        try:
            return service.applications(context.actor, account_id, limit=limit, offset=offset)
        except PermissionDenied:raise
        except ValueError:raise HTTPException(404, 'account_or_page_unavailable') from None

    @app.post('/api/v1/access/requests/{identifier}/preview')
    async def preview(identifier: UUID, context=Depends(write_browser)):
        if cimd is None:
            raise HTTPException(409, 'cimd_unavailable')
        before = await to_thread.run_sync(partial(service.request, context.actor, identifier))
        if before['account']['blocked'] or before['account']['role'] is None:
            raise PermissionDenied()
        fetched = await cimd.preview(context.actor, before['metadata_url'])
        # Recheck the exact request, current role, block and approval after I/O.
        after = await to_thread.run_sync(partial(service.request, context.actor, identifier))
        if after['account']['blocked'] or after['account']['role'] is None:
            raise PermissionDenied()
        state = await to_thread.run_sync(partial(grants.cimd.status, context.actor))
        selected = next((c for c in state['clients'] if c['metadata_url']==after['metadata_url']), None)
        return {'request': after, 'descriptor': fetched.metadata.descriptor(),
                'metadata_digest': fetched.metadata.digest, 'client': selected}

    @app.post('/api/v1/access/requests/{identifier}/approve')
    async def approve(identifier: UUID, data: RequestApproval, context=Depends(write_browser)):
        if cimd is None:
            raise HTTPException(409, 'cimd_unavailable')
        before = await to_thread.run_sync(partial(service.request, context.actor, identifier))
        if before['account']['blocked'] or before['account']['role'] is None:
            raise PermissionDenied()
        fetched = await cimd.preview(context.actor, before['metadata_url'])
        try:
            client_id = UUID(data.client_id) if data.client_id is not None else None
        except ValueError:raise HTTPException(422, 'invalid_client') from None
        try:
            return await to_thread.run_sync(partial(service.approve, context.actor, identifier,
                fetched.metadata, scopes=data.allowed_scopes, expected_digest=data.metadata_digest,
                client_id=client_id, expected_revision=data.expected_revision, cache_seconds=fetched.remaining))
        except (PermissionDenied, CimdRejected, OnboardingRejected, ClientConflict):
            raise
        except ValueError:
            raise HTTPException(422, 'invalid_approval') from None


    @app.delete('/api/v1/access/requests/{identifier}', status_code=204)
    def decline(identifier: UUID, context=Depends(write_browser)):
        service.decline(context.actor, identifier)
        return Response(status_code=204)

    @app.delete('/api/v1/access/connections/{identifier}', status_code=204)
    def disconnect(identifier: UUID, context=Depends(write_browser)):
        try:
            service.disconnect(context.actor, identifier)
        except GrantRejected:
            raise HTTPException(404, 'connection_not_found') from None
        return Response(status_code=204)
