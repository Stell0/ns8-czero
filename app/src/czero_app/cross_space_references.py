# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Typed transport; endpoint authority, availability and retries remain in Core."""
import importlib.util
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator, model_serializer

from czero_core.identity import PermissionDenied, Role, TokenRejected
from czero_app.auth import RequestAccess


class Endpoint(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['object', 'page', 'source', 'entity', 'claim']
    id: UUID = Field(strict=False)
    type_name: str | None = Field(default=None, min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_-]{0,63}$')

    @model_validator(mode='after')
    def typed(self):
        if (self.kind == 'object' and self.type_name is None) or (self.kind != 'object' and 'type_name' in self.model_fields_set):
            raise ValueError('invalid_reference_endpoint')
        return self

    @model_serializer(mode='wrap')
    def serialize(self, handler):
        result = handler(self)
        if self.kind != 'object': result.pop('type_name', None)
        return result


class Target(Endpoint):
    space_id: UUID = Field(strict=False)


class Create(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source: Endpoint
    target: Target
    relation_kind: Literal['references'] = 'references'
    idempotency_key: str = Field(min_length=1, max_length=128)


class Delete(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source: Endpoint
    reference_id: UUID = Field(strict=False)
    idempotency_key: str = Field(min_length=1, max_length=128)


class Acknowledgement(BaseModel):
    reference_id: UUID


class Summary(BaseModel):
    space_id: UUID
    id: UUID
    revision: int


class LabelSummary(Summary):
    kind: Literal['page', 'source', 'entity']
    label: str


class ObjectSummary(Summary):
    kind: Literal['object']
    type_name: str


class ClaimSummary(Summary):
    kind: Literal['claim']
    predicate: str
    evidence_stale: bool


TargetSummary = Annotated[LabelSummary | ObjectSummary | ClaimSummary, Field(discriminator='kind')]


class Reference(BaseModel):
    id: UUID
    relation_kind: Literal['references']
    target: TargetSummary


class Listing(BaseModel):
    references: list[Reference]
    next_after: UUID | None


def install(app, database, auth, read_context, write_context):
    if importlib.util.find_spec('czero_core.cross_space_references') is None:
        return  # Released consumers cannot advertise uninstalled Core capabilities.
    from czero_core.cross_space_references import (CrossSpaceReferenceService, ReferenceConflict,
                                                   ReferenceNotFound, ReferenceTargetUnavailable)
    service = CrossSpaceReferenceService(database, auth.access if auth else None)
    app.state.cross_space_references = service
    operation = app.state.operation_catalog.bind

    def invoke(method, actor, **arguments):
        if auth is None:
            raise HTTPException(503, 'authentication_not_configured')
        try:
            return getattr(service, method)(actor, **arguments)
        except (ReferenceNotFound, ReferenceTargetUnavailable) as error:
            raise HTTPException(404, str(error)) from None
        except ReferenceConflict:
            raise HTTPException(409, 'reference_conflict') from None
        except (PermissionDenied, TokenRejected):
            raise
        except ValueError:
            raise HTTPException(422, 'invalid_reference_request') from None

    previous = app.exception_handlers.get(RequestValidationError)

    async def validation(request, error):
        if request.url.path.endswith('/api/v1/cross-space-references'):
            return JSONResponse({'detail': 'invalid_reference_request'}, status_code=422,
                                headers={'Cache-Control': 'no-store'})
        return await previous(request, error)
    app.add_exception_handler(RequestValidationError, validation)

    @app.post('/api/v1/cross-space-references', response_model=Acknowledgement)
    @operation('cross_space_ref_create', 'Create an outgoing navigation link with source Editor, target Reader and both c0:write and c0:read. No target content is copied; read back current visibility.',
               Role.EDITOR, Acknowledgement, read_only=False, space_field='space_id', additional_scopes=('c0:read',))
    def create(space_id: UUID, data: Create, context: RequestAccess = Depends(write_context)):
        return invoke('create', context.actor, space_id=space_id, **data.model_dump(mode='json', exclude_none=True))

    @app.get('/api/v1/cross-space-references', response_model=Listing)
    @operation('cross_space_refs_list', 'List outgoing current summaries in 1–10 explicitly selected target spaces. Only currently readable active endpoints appear. Follow with a fresh authorized content read; these links are not evidence.',
               Role.READER, Listing, space_field='space_id')
    def listing(space_id: UUID, source_kind: Literal['object', 'page', 'source', 'entity', 'claim'], source_id: UUID,
                target_space_ids: Annotated[list[UUID], Query(min_length=1, max_length=10)],
                source_type_name: str | None = None, limit: int = 50, after: UUID | None = None,
                context: RequestAccess = Depends(read_context)):
        source = {'kind': source_kind, 'id': source_id}
        if source_type_name is not None:
            source['type_name'] = source_type_name
        return invoke('list', context.actor, space_id=space_id, source=source,
                      target_space_ids=target_space_ids, limit=limit, after=after)

    @app.delete('/api/v1/cross-space-references', status_code=204)
    @operation('cross_space_ref_delete', 'Blindly delete a known source-owned reference UUID with source Editor/c0:write. No target access required. Missing, foreign-source and deleted UUIDs return the same empty result.',
               Role.EDITOR, type(None), read_only=False, space_field='space_id')
    def delete(space_id: UUID, data: Delete, context: RequestAccess = Depends(write_context)):
        invoke('delete', context.actor, space_id=space_id, **data.model_dump(mode='json', exclude_none=True))
        return None
