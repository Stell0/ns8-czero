# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""REST-only client review and request-local OAuth metadata verification."""
from functools import partial
import time
from uuid import UUID

from anyio import to_thread
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from czero_core.cimd import CimdRejected
from czero_core.identity import PermissionDenied
from czero_core.cimd_metadata import ClientMetadata, MetadataRejected, metadata_url
from czero_core.oauth_clients import ClientConflict
from czero_app.auth import RequestAccess
from czero_app.cimd_fetch import FetchRejected, FetchedMetadata, MetadataFetcher
from czero_app.oauth import Scope


class MetadataPreview(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    metadata_url: str = Field(min_length=1, max_length=2048)


class MetadataApproval(MetadataPreview):
    metadata_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    allowed_scopes: list[Scope] = Field(default=['c0:read'], min_length=1, max_length=3)


class MetadataReapproval(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    metadata_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    allowed_scopes: list[Scope] = Field(default=['c0:read'], min_length=1, max_length=3)
    expected_revision: int = Field(ge=1, le=2147483646)


class CimdAdapter:
    def __init__(self, service):
        self.service = service
        self.fetcher = MetadataFetcher()

    async def verification(self, public_id):
        client = await to_thread.run_sync(partial(self.service.clients._lookup, public_id))
        if client is None:
            raise CimdRejected()
        if client.get('registration_kind') != 'cimd':
            return None
        approved = await to_thread.run_sync(partial(self.service.approval, public_id))
        # A valid approved cache survives process restart; no-store has no
        # persisted reuse window. Never load a cache for an unknown binding.
        if public_id not in self.fetcher.cache:
            remaining = approved['fresh_until'].timestamp() - time.time()
            if 0 < remaining <= 300:
                descriptor = approved['approved_descriptor']
                value = ClientMetadata(public_id, descriptor['client_name'],
                    tuple(descriptor['redirect_uris']), tuple(descriptor['grant_types']),
                    None if descriptor['scope_ceiling'] is None else tuple(descriptor['scope_ceiling']))
                self.fetcher.remember(public_id, FetchedMetadata(value, time.monotonic() + remaining))
        fetched = await self.fetcher.fetch(public_id, cache=True)
        return await to_thread.run_sync(partial(self.service.observe, fetched.metadata,
            expected_revision=approved['revision'], cache_seconds=fetched.remaining))

    async def preview(self, actor, url):
        await to_thread.run_sync(partial(self.service.authorize_preview, actor))
        metadata_url(url)
        fetched = await self.fetcher.fetch(url, reuse=False)
        status = await to_thread.run_sync(partial(self.service.status, actor))
        # A valid changed document observed during an Admin preview also makes
        # the review requirement sticky. This never approves or alters grants.
        approved = next((row for row in status['clients'] if row['metadata_url'] == url), None)
        if approved is not None and not approved['review_required']:
            try:
                await to_thread.run_sync(partial(self.service.observe, fetched.metadata,
                    expected_revision=approved['revision'], cache_seconds=fetched.remaining))
            except CimdRejected:
                pass
        await to_thread.run_sync(partial(self.service.authorize_preview, actor))
        return fetched


def install_cimd_routes(app, service, read_context, write_context):
    adapter = CimdAdapter(service)
    app.state.cimd = adapter

    async def approve_checked(*args, **kwargs):
        try:
            return await to_thread.run_sync(partial(service.approve, *args, **kwargs))
        except (PermissionDenied, CimdRejected, ClientConflict):
            raise
        except ValueError:
            raise HTTPException(422, 'invalid_client_metadata') from None

    @app.get('/api/v1/oauth/cimd')
    def status(context: RequestAccess = Depends(read_context)):
        return service.status(context.actor)

    @app.post('/api/v1/oauth/cimd/preview')
    async def preview(data: MetadataPreview, context: RequestAccess = Depends(write_context)):
        fetched = await adapter.preview(context.actor, data.metadata_url)
        return {'descriptor': fetched.metadata.descriptor(), 'metadata_digest': fetched.metadata.digest}

    @app.post('/api/v1/oauth/cimd/clients', status_code=201)
    async def approve(data: MetadataApproval, context: RequestAccess = Depends(write_context)):
        fetched = await adapter.preview(context.actor, data.metadata_url)
        result = await approve_checked(context.actor, fetched.metadata,
            expected_digest=data.metadata_digest, scopes=data.allowed_scopes, cache_seconds=fetched.remaining)
        adapter.fetcher.remember(data.metadata_url, fetched)
        return result

    @app.put('/api/v1/oauth/cimd/clients/{client_id}')
    async def reapprove(client_id: UUID, data: MetadataReapproval,
                        context: RequestAccess = Depends(write_context)):
        state = await to_thread.run_sync(partial(service.status, context.actor))
        client = next((row for row in state['clients'] if row['client_id'] == str(client_id)), None)
        if client is None:
            raise HTTPException(404, 'oauth_client_not_found')
        fetched = await adapter.preview(context.actor, client['metadata_url'])
        result = await approve_checked(context.actor, fetched.metadata,
            expected_digest=data.metadata_digest, scopes=data.allowed_scopes, client_id=client_id,
            expected_revision=data.expected_revision, cache_seconds=fetched.remaining)
        adapter.fetcher.remember(client['metadata_url'], fetched)
        return result

    @app.exception_handler(CimdRejected)
    def rejected(request, error):
        return JSONResponse({'detail': 'cimd_unavailable'}, status_code=409, headers={'Cache-Control': 'no-store'})

    @app.exception_handler(MetadataRejected)
    def invalid(request, error):
        return JSONResponse({'detail': 'invalid_client_metadata'}, status_code=422, headers={'Cache-Control': 'no-store'})

    @app.exception_handler(FetchRejected)
    def unavailable(request, error):
        return JSONResponse({'detail': error.code}, status_code=503, headers={'Cache-Control': 'no-store'})

    @app.exception_handler(ClientConflict)
    def conflict(request, error):
        return JSONResponse({'detail': 'oauth_client_conflict'}, status_code=409, headers={'Cache-Control': 'no-store'})

    return adapter
