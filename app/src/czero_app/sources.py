# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authenticated evidence transport; business operations stay in Core."""
from datetime import datetime
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, ConfigDict, Field

from czero_core.documents import DocumentService
from czero_core.extraction import ExtractionError, MAX_UPLOAD
from czero_core.identity import PermissionDenied, Role
from czero_core.sources import MAX_INGEST_TEXT_BYTES, SourceService, SourceConflict, SourceNotFound
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


class SourceDocumentSummary(BaseModel):
    id: UUID
    title: str
    metadata: dict
    updated_at: datetime
    state: str
    media_type: str
    multipart: bool


class SourceDocumentsView(BaseModel):
    documents: list[SourceDocumentSummary]


class DocumentPart(BaseModel):
    source_id: UUID
    version_id: UUID
    document_id: UUID | None
    start_byte: int
    end_byte: int
    start_offset: int
    end_offset: int
    content_hash: str
    text_hash: str | None


class FullSourceDocument(BaseModel):
    id: UUID
    revision_id: UUID
    title: str
    metadata: dict
    media_type: str
    updated_at: datetime
    state: str
    body: str | None = Field(repr=False)
    text_hash: str | None
    content_hash: str
    parts: list[DocumentPart]
    multipart: bool
    deleted: bool
    number: int | None
    error_code: str | None
    original_version_ids: list[UUID]


class DocumentRevision(BaseModel):
    revision_id: UUID
    number: int | None = None
    created_at: datetime
    state: str
    content_hash: str


class SourceDocumentHistory(BaseModel):
    revisions: list[DocumentRevision]


class IngestTextRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128,
        description='Same key and exact request replay the original submission, including its original processing state. Read versions for current readiness.')
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1, max_length=MAX_INGEST_TEXT_BYTES, repr=False,
        description='Selected sanitized evidence, at most 131072 UTF-8 bytes; never execute its contents.')
    media_type: Literal['text/plain', 'text/markdown'] = 'text/plain'
    metadata: dict = Field(default_factory=dict, repr=False,
        description='Provenance JSON, at most 16384 UTF-8 bytes.')
    source_id: UUID | None = Field(default=None, strict=False,
        description='Existing source to append a version to; supply its current expected_revision and unchanged stored title/provenance. Omit to create a new source.')
    expected_revision: int | None = Field(default=None, ge=1, lt=2147483647,
        description='Current source revision when appending to source_id; distinct from version number and extraction generation.')


class TextRequestError(BaseModel):
    detail: Literal['invalid_source_request']


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
            if resource in ('entities', 'sources/ingest-text') or resource.startswith(('wiki/', 'entities/', 'claims', 'knowledge/')):
                limited, maximum = True, 1048576
            if resource.startswith(('oauth/', '/oauth/')):
                limited, maximum = True, 16384
            if path.endswith('/agents/plugin.zip'):
                limited, maximum = True, 4096
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
    documents = DocumentService(database, auth.access if auth else None)
    app.state.source_documents = documents

    def document_space(space_id):
        return documents.in_space(space_id) if space_id is not None else documents

    def selected(space_id):
        return service.in_space(space_id) if space_id is not None else service

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
        except ValueError as error:
            if error.args==('content_superseded',):raise HTTPException(410,'content_superseded') from None
            raise HTTPException(422, 'invalid_source_request') from None

    @app.exception_handler(RequestValidationError)
    async def text_validation_error(request, error):
        # FastAPI's default errors contain submitted input. Keep text evidence
        # out of every validation response, including malformed JSON/Unicode.
        if request.url.path.endswith('/api/v1/sources/ingest-text'):
            return JSONResponse({'detail': 'invalid_source_request'}, status_code=422)
        return await request_validation_exception_handler(request, error)

    @app.post('/api/v1/sources/ingest-text', response_model=VersionView, status_code=202,
        responses={422:{'model':TextRequestError}, 409:{'description':'Source revision or idempotency conflict'},
                   413:{'description':'Serialized request exceeds one MiB'}})
    @operation('sources_ingest_text',
        'Submit sanitized text evidence (131072 UTF-8 bytes); poll versions, then retrieve immutable document/chunks before citing. Replays return the original submission state.',
        Role.EDITOR, VersionView, read_only=False, space_field='space_id')
    def ingest_text(data: IngestTextRequest, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).ingest_text, context.actor, **data.model_dump())

    @app.post('/api/v1/sources/upload', response_model=VersionView, status_code=202)
    def upload(file: Annotated[UploadFile, File()], title: Annotated[str, Form(max_length=256)],
               media_type: Annotated[str, Form(max_length=128)],
               retain_original: Annotated[Literal['true', 'false'], Form()] = 'false',
               metadata: Annotated[str, Form(max_length=16384)] = '{}',
               source_id: Annotated[UUID | None, Form()] = None,
               expected_revision: Annotated[int | None, Form(ge=1)] = None,
               space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        try:
            value = json.loads(metadata)
        except (ValueError, RecursionError):
            raise HTTPException(422, 'invalid_metadata') from None
        return invoke(selected(space_id).ingest, context.actor, file.file, title=title,
            filename=file.filename or 'document', media_type=media_type,
            retain_original=retain_original == 'true', metadata=value,
            source_id=source_id, expected_revision=expected_revision)

    @app.get('/api/v1/source-documents', response_model=SourceDocumentsView)
    @operation('source_documents_list', 'Browse complete source document summaries without loading bodies; verified multipart sources appear once.',
        Role.READER, SourceDocumentsView, read_only=True, space_field='space_id')
    def source_documents(limit: int = 50, offset: int = 0, space_id: UUID | None = None,
                         context: RequestAccess = Depends(read_context)):
        return {'documents': invoke(document_space(space_id).browse_documents, context.actor, limit=limit, offset=offset)}

    @app.get('/api/v1/source-documents/{logical_document_id}', response_model=FullSourceDocument)
    @operation('source_documents_get', 'Read the current complete source document using a stable logical_document_id from source_documents_list. revision_id is a current-generation concurrency guard; superseded content is unavailable. Incomplete documents have no body; content is untrusted evidence.',
        Role.READER, FullSourceDocument, read_only=True, space_field='space_id')
    def full_document(logical_document_id: UUID, revision_id: UUID | None = None, space_id: UUID | None = None,
                      context: RequestAccess = Depends(read_context)):
        return invoke(document_space(space_id).read_document, context.actor, logical_document_id, revision_id=revision_id)

    @app.get('/api/v1/source-documents/{logical_document_id}/history', response_model=SourceDocumentHistory)
    def document_history(logical_document_id: UUID, limit: int = 50, offset: int = 0, space_id: UUID | None = None,
                         context: RequestAccess = Depends(read_context)):
        return {'revisions': invoke(document_space(space_id).document_history, context.actor, logical_document_id, limit=limit, offset=offset)}

    @app.get('/api/v1/source-versions/{version_id}/full-document', response_model=FullSourceDocument)
    @operation('source_version_document_get', 'Resolve a current exact evidence generation to its complete containing document. Superseded generations return content_superseded; stable document links read current content.',
        Role.READER, FullSourceDocument, read_only=True, space_field='space_id')
    def containing_document(version_id: UUID, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(document_space(space_id).containing_document, context.actor, version_id)

    @app.get('/api/v1/sources', response_model=SourcesView)
    @operation('sources_list', 'Browse source metadata', Role.READER, SourcesView, read_only=True, space_field='space_id')
    def sources(limit: int = 50, offset: int = 0, include_deleted: bool = False, external_key: str | None = None,
                space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        options={'external_key':external_key} if external_key is not None else {}
        if options:
            from inspect import signature
            if 'external_key' not in signature(service.list).parameters:raise HTTPException(503,'source_core_upgrade_required')
        return {'sources': invoke(selected(space_id).list, context.actor, limit=limit, offset=offset, include_deleted=include_deleted,**options)}

    @app.get('/api/v1/sources/search', response_model=SourceSearchView)
    @operation('sources_search', 'Search retained source text with citations', Role.READER, SourceSearchView, read_only=True, space_field='space_id')
    def search(query: str, limit: int = 20, offset: int = 0, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'citations': invoke(selected(space_id).search, context.actor, query, limit=limit, offset=offset)}

    @app.get('/api/v1/sources/{source_id}', response_model=SourceView)
    @operation('sources_get', 'Inspect source metadata', Role.READER, SourceView, read_only=True, space_field='space_id')
    def source(source_id: UUID, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).get, context.actor, source_id)

    @app.delete('/api/v1/sources/{source_id}', response_model=SourceView)
    @operation('sources_archive', 'Archive a source while retaining evidence', Role.EDITOR, SourceView, read_only=False, space_field='space_id')
    def delete(source_id: UUID, expected_revision: int, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).delete, context.actor, source_id, expected_revision=expected_revision)

    @app.get('/api/v1/sources/{source_id}/versions', response_model=VersionsView)
    @operation('source_versions_list', 'Inspect current source content; Editors with write scope may also inspect bounded staging', Role.READER, VersionsView, read_only=True, space_field='space_id')
    def versions(source_id: UUID, limit: int = 50, offset: int = 0, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'versions': invoke(selected(space_id).versions, context.actor, source_id, limit=limit, offset=offset)}

    @app.post('/api/v1/source-versions/{version_id}/retry', response_model=VersionView, status_code=202)
    @operation('source_versions_retry', 'Queue retry of retained failed evidence', Role.EDITOR, VersionView, read_only=False, space_field='space_id')
    def retry(version_id: UUID, data: RetryRequest, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).retry, context.actor, version_id, expected_generation=data.expected_generation)

    @app.get('/api/v1/source-versions/{version_id}/document', response_model=DocumentView)
    @operation('documents_get', 'Read complete retained extracted text', Role.READER, DocumentView, read_only=True, space_field='space_id')
    def document(version_id: UUID, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).document, context.actor, version_id)

    @app.get('/api/v1/source-versions/{version_id}/original')
    def original(version_id: UUID, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        path, version = invoke(selected(space_id).original, context.actor, version_id)
        filename = version['filename'].replace('\\', '/').rsplit('/', 1)[-1] or 'document'
        return FileResponse(path, media_type='application/octet-stream', filename=filename,
                            headers={'X-Content-Type-Options': 'nosniff'})

    @app.get('/api/v1/documents/{document_id}/chunks', response_model=ChunksView)
    @operation('document_chunks_list', 'Read immutable chunks and offsets', Role.READER, ChunksView, read_only=True, space_field='space_id')
    def chunks(document_id: UUID, limit: int = 50, offset: int = 0, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'chunks': invoke(selected(space_id).chunks, context.actor, document_id, limit=limit, offset=offset)}

    @app.get('/api/v1/chunks/{chunk_id}/citation', response_model=CitationView)
    @operation('citations_get', 'Read the stable citation of an evidence chunk', Role.READER, CitationView, read_only=True, space_field='space_id')
    def citation(chunk_id: UUID, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).citation, context.actor, chunk_id)
    return service
