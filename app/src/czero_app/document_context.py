# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only context bindings; current authorization and selection stay in Core."""
from typing import Annotated,Literal
from uuid import UUID
from fastapi import Depends
from pydantic import BaseModel,ConfigDict,Field
from czero_core.identity import Role
from .auth import RequestAccess

SelectionID=Annotated[str,Field(pattern=r'^[sb][0-9]{1,4}$')]
ReferenceID=Annotated[str,Field(pattern=r'^r[0-9]{1,4}$')]


class Limits(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    max_bytes: int = Field(default=32768,ge=4096,le=65536)
    max_tokens: int = Field(default=8192,ge=256,le=16384,
        description='Ceiling on the UTF-8 bytes/3 estimate; not a provider tokenizer count.')


class SectionRequest(Limits):
    revision_id: UUID = Field(strict=False)
    selection_ids: list[SelectionID] = Field(min_length=1,max_length=20,
        description='Exact sN section or bN block IDs from this revision outline; no fallback.')


class ReferenceRequest(Limits):
    revision_id: UUID = Field(strict=False)
    reference_ids: list[ReferenceID] = Field(min_length=1,max_length=20)


class PlanItem(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    logical_document_id: UUID = Field(strict=False)
    revision_id: UUID = Field(strict=False)
    selection_ids: list[SelectionID] = Field(default_factory=list,max_length=20)
    reference_ids: list[ReferenceID] = Field(default_factory=list,max_length=20,
        description='Include only explicitly resolved local target sections; no network fetch.')


class BundleRequest(Limits):
    plan: list[PlanItem] = Field(min_length=1,max_length=5)


class Identity(BaseModel):
    logical_document_id: UUID
    revision_id: UUID
    text_sha256: str
    structure_revision: int
    structure_origin: Literal['persisted','derived_current_body']


class MeasuredReply(BaseModel):
    response_bytes: int
    estimated_tokens: int
    complete_document: Literal[False]


class OutlineView(Identity,MeasuredReply):
    space_id: UUID
    sections: list[dict]
    blocks: list[dict]
    view: Literal['sections','blocks']
    has_ocr: bool
    total_sections: int
    total_blocks: int
    total_references: int
    next_offset: int | None


class CitationHandle(BaseModel):
    source_id: UUID
    version_id: UUID
    document_id: UUID
    chunk_id: UUID
    content_hash: str
    start_offset: int
    end_offset: int
    document_start_offset: int
    document_end_offset: int
    selected_start: int
    selected_end: int


class SelectedEvidence(Identity):
    selection_id: str
    section_id: str
    kind: str
    start_offset: int
    end_offset: int
    body: str = Field(repr=False)
    content_hash: str
    citations: list[CitationHandle]
    extraction: dict
    blocks: list[dict]
    references: list[dict]


class Reference(Identity):
    id: str
    kind: Literal['link']
    start: int
    end: int
    target: str
    section: str | None
    resolved: bool
    citations: list[CitationHandle]


class Omitted(Identity):
    selection_id: str
    reason: Literal['too_large']


class BundleView(MeasuredReply):
    space_id: UUID
    documents: list[Identity]
    sections: list[SelectedEvidence]
    references: list[Reference]
    omitted: list[Omitted]
    no_fallback: Literal[True]


class ReferencesView(Identity,MeasuredReply):
    space_id: UUID
    references: list[Reference]


def install_context_routes(app,documents,read_context,invoke):
    # The released older Core keeps its real working catalog, never a shim or
    # an automatic local-source substitute for this producer capability.
    if not all(callable(getattr(documents,key,None)) for key in ('outline','sections','references','context_bundle')):
        return False
    operation=app.state.operation_catalog.bind
    def selected(space_id):
        return documents.in_space(space_id) if space_id is not None else documents

    @app.get('/api/v1/source-documents/{logical_document_id}/outline',response_model=OutlineView)
    @operation('source_document_outline_get','Inspect exact current section/block spans without loading their bodies.',
        Role.READER,OutlineView,read_only=True,space_field='space_id')
    def outline(logical_document_id: UUID,revision_id: UUID | None=None,limit: int=50,offset: int=0,
                view: Literal['sections','blocks']='sections',max_bytes: int=32768,max_tokens: int=8192,
                space_id: UUID | None=None,context: RequestAccess=Depends(read_context)):
        return invoke(selected(space_id).outline,context.actor,logical_document_id,revision_id=revision_id,
            limit=limit,offset=offset,view=view,max_bytes=max_bytes,max_tokens=max_tokens)

    @app.post('/api/v1/source-documents/{logical_document_id}/sections',response_model=BundleView)
    @operation('source_document_sections_get','Read selected exact current sections or blocks with source citations.',
        Role.READER,BundleView,read_only=True,space_field='space_id')
    def sections(logical_document_id: UUID,data: SectionRequest,space_id: UUID | None=None,
                 context: RequestAccess=Depends(read_context)):
        return invoke(selected(space_id).sections,context.actor,logical_document_id,**data.model_dump())

    @app.post('/api/v1/source-documents/{logical_document_id}/references',response_model=ReferencesView)
    @operation('source_document_references_get','Resolve selected exact local references without fetching URLs.',
        Role.READER,ReferencesView,read_only=True,space_field='space_id')
    def references(logical_document_id: UUID,data: ReferenceRequest,space_id: UUID | None=None,
                   context: RequestAccess=Depends(read_context)):
        return invoke(selected(space_id).references,context.actor,logical_document_id,**data.model_dump())

    @app.post('/api/v1/context-bundles',response_model=BundleView)
    @operation('context_bundle_get','Validate a bounded one-space plan and return only selected exact evidence.',
        Role.READER,BundleView,read_only=True,space_field='space_id')
    def bundle(data: BundleRequest,space_id: UUID | None=None,context: RequestAccess=Depends(read_context)):
        return invoke(selected(space_id).context_bundle,context.actor,[item.model_dump(mode='json') for item in data.plan],
            max_bytes=data.max_bytes,max_tokens=data.max_tokens)
    return True
