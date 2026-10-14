# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authenticated evidence transport; business operations stay in Core."""
from datetime import datetime
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, ConfigDict, Field

from czero_core.extraction import ExtractionError, MAX_UPLOAD
from czero_core.identity import PermissionDenied, Role
from czero_core.sources import SourceService, SourceConflict, SourceNotFound
from czero_app.auth import RequestAccess


class SourceView(BaseModel):
    id: UUID
    title: str
    metadata: dict
    revision: int
    deleted: bool
    created_at: datetime
    updated_at: datetime


class SourcesView(BaseModel):
    sources: list[SourceView]


class VersionView(BaseModel):
    id: UUID
    source_id: UUID
    number: int
    filename: str
    media_type: str
    content_hash: str
    size_bytes: int
    state: Literal['queued', 'ready', 'failed']
    error_code: str | None
    retain_original: bool
    original_present: bool
    generation: int
    job_id: UUID | None
    job_state: str | None = None
    created_at: datetime


class VersionsView(BaseModel):
    versions: list[VersionView]


class DocumentView(BaseModel):
    id: UUID
    version_id: UUID
    body: str
    text_hash: str
    locations: list[dict]
    created_at: datetime


class ChunkView(BaseModel):
    id: UUID
    document_id: UUID
    ordinal: int
    start_offset: int
    end_offset: int
    body: str
    content_hash: str
    locations: list[dict]


class ChunksView(BaseModel):
    chunks: list[ChunkView]


class CitationView(BaseModel):
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    source_id: UUID
    version: int
    filename: str
    media_type: str
    title: str
    deleted: bool
    start_offset: int
    end_offset: int
    body: str
    content_hash: str
    source_hash: str
    text_hash: str
    locations: list[dict]


class SourceSearchView(BaseModel):
    citations: list[CitationView]


class RetryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_generation: int = Field(ge=1, le=2147483646)


class _UploadLimitExceeded(BaseException):
    # Bypass FastAPI's generic body-parse Exception -> HTTP 400 conversion.
    # Starlette closes multipart temporary files on every BaseException.
    pass


class UploadBodyLimit:
    """Bound uploads and authored-knowledge JSON, including chunked bodies."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        limited = scope['type'] == 'http' and scope.get('method') == 'POST' and path.endswith('/api/v1/sources/upload')
        maximum = MAX_UPLOAD + 65536
        if scope['type'] == 'http' and scope.get('method') in ('POST','PUT','PATCH'):
            resource = path.split('/api/v1/', 1)[-1]
            if resource == 'entities' or resource.startswith(('wiki/', 'entities/', 'claims', 'knowledge/')):
                limited, maximum = True, 1048576
        size = 0
        async def bounded_receive():
            nonlocal size
            message = await receive()
            if limited:
                size += len(message.get('body', b''))
                if size > maximum:
                    raise _UploadLimitExceeded()
            return message
        try:
            await self.app(scope, bounded_receive, send)
        except _UploadLimitExceeded:
            await JSONResponse({'detail': 'upload_too_large'}, status_code=413)(scope, receive, send)


def install_source_routes(app, database, auth, read_context, write_context, registry, originals):
    operation = app.state.operation_catalog.bind
    service = SourceService(database, auth.access if auth else None, registry, originals)
    app.state.sources = service

    def invoke(operation, *args, **kwargs):
        if auth is None:
            raise HTTPException(503, 'authentication_not_configured')
        try:
            return operation(*args, **kwargs)
        except PermissionDenied:
            raise
        except SourceConflict:
            raise HTTPException(409, 'source_conflict') from None
        except SourceNotFound:
            raise HTTPException(404, 'source_not_found') from None
        except ExtractionError as error:
            raise HTTPException(413 if error.code == 'too_large' else 422, error.code) from None
        except ValueError:
            raise HTTPException(422, 'invalid_source_request') from None

    @app.post('/api/v1/sources/upload', response_model=VersionView, status_code=202)
    def upload(file: Annotated[UploadFile, File()], title: Annotated[str, Form(max_length=256)],
               media_type: Annotated[str, Form(max_length=128)],
               retain_original: Annotated[Literal['true', 'false'], Form()] = 'false',
               metadata: Annotated[str, Form(max_length=16384)] = '{}',
               source_id: Annotated[UUID | None, Form()] = None,
               expected_revision: Annotated[int | None, Form(ge=1)] = None,
               context: RequestAccess = Depends(write_context)):
        try:
            value = json.loads(metadata)
        except (ValueError, RecursionError):
            raise HTTPException(422, 'invalid_metadata') from None
        return invoke(service.ingest, context.actor, file.file, title=title,
            filename=file.filename or 'document', media_type=media_type,
            retain_original=retain_original == 'true', metadata=value,
            source_id=source_id, expected_revision=expected_revision)

    @app.get('/api/v1/sources', response_model=SourcesView)
    @operation('sources_list', 'Browse source metadata', Role.READER, SourcesView, read_only=True)
    def sources(limit: int = 50, offset: int = 0, include_deleted: bool = False,
                context: RequestAccess = Depends(read_context)):
        return {'sources': invoke(service.list, context.actor, limit=limit, offset=offset, include_deleted=include_deleted)}

    @app.get('/api/v1/sources/search', response_model=SourceSearchView)
    @operation('sources_search', 'Search retained source text with citations', Role.READER, SourceSearchView, read_only=True)
    def search(query: str, limit: int = 20, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return {'citations': invoke(service.search, context.actor, query, limit=limit, offset=offset)}

    @app.get('/api/v1/sources/{source_id}', response_model=SourceView)
    @operation('sources_get', 'Inspect source metadata', Role.READER, SourceView, read_only=True)
    def source(source_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(service.get, context.actor, source_id)

    @app.delete('/api/v1/sources/{source_id}', response_model=SourceView)
    @operation('sources_archive', 'Archive a source while retaining evidence', Role.EDITOR, SourceView, read_only=False)
    def delete(source_id: UUID, expected_revision: int, context: RequestAccess = Depends(write_context)):
        return invoke(service.delete, context.actor, source_id, expected_revision=expected_revision)

    @app.get('/api/v1/sources/{source_id}/versions', response_model=VersionsView)
    @operation('source_versions_list', 'Inspect immutable source version history', Role.READER, VersionsView, read_only=True)
    def versions(source_id: UUID, limit: int = 50, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return {'versions': invoke(service.versions, context.actor, source_id, limit=limit, offset=offset)}

    @app.post('/api/v1/source-versions/{version_id}/retry', response_model=VersionView, status_code=202)
    @operation('source_versions_retry', 'Queue retry of retained failed evidence', Role.EDITOR, VersionView, read_only=False)
    def retry(version_id: UUID, data: RetryRequest, context: RequestAccess = Depends(write_context)):
        return invoke(service.retry, context.actor, version_id, expected_generation=data.expected_generation)

    @app.get('/api/v1/source-versions/{version_id}/document', response_model=DocumentView)
    @operation('documents_get', 'Read complete retained extracted text', Role.READER, DocumentView, read_only=True)
    def document(version_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(service.document, context.actor, version_id)

    @app.get('/api/v1/source-versions/{version_id}/original')
    def original(version_id: UUID, context: RequestAccess = Depends(read_context)):
        path, version = invoke(service.original, context.actor, version_id)
        filename = version['filename'].replace('\\', '/').rsplit('/', 1)[-1] or 'document'
        return FileResponse(path, media_type='application/octet-stream', filename=filename,
                            headers={'X-Content-Type-Options': 'nosniff'})

    @app.get('/api/v1/documents/{document_id}/chunks', response_model=ChunksView)
    @operation('document_chunks_list', 'Read immutable chunks and offsets', Role.READER, ChunksView, read_only=True)
    def chunks(document_id: UUID, limit: int = 50, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return {'chunks': invoke(service.chunks, context.actor, document_id, limit=limit, offset=offset)}

    @app.get('/api/v1/chunks/{chunk_id}/citation', response_model=CitationView)
    @operation('citations_get', 'Read the stable citation of an evidence chunk', Role.READER, CitationView, read_only=True)
    def citation(chunk_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(service.citation, context.actor, chunk_id)
    return service
