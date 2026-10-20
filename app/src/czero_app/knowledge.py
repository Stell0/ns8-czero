# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Typed Wiki/claim/graph REST adapters for shared Core operations."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from czero_core.identity import PermissionDenied, Role
from czero_core.knowledge import KnowledgeService, EvidenceNotReady
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound
from czero_app.auth import RequestAccess


class Mutation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128,
        description='Reuse only for an identical uncertain request. A changed request or reconciled conflict needs a new key.')


class PageCreate(Mutation):
    slug: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(max_length=131072)
    metadata: dict = Field(default_factory=dict)


class PageUpsert(PageCreate):
    title: str = Field(min_length=1, max_length=256, repr=False)
    body: str = Field(max_length=131072, repr=False,
        description='Authored Markdown, at most 131072 UTF-8 bytes. C0 does not execute its contents.')
    metadata: dict = Field(default_factory=dict, repr=False,
        description='JSON metadata, at most 16384 UTF-8 bytes.')
    expected_revision: int | None = Field(default=None, ge=1, lt=2147483647,
        description='Omitted/null is create-only. Supply the current revision for update-only; conflicts never overwrite.')


class KnowledgeRequestError(BaseModel):
    detail: Literal['invalid_knowledge_request']


class PageUpdate(Mutation):
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(max_length=131072)
    metadata: dict = Field(default_factory=dict)
    expected_revision: int = Field(ge=1, lt=2147483647,
        description='Current page revision from a fresh read. On conflict reload/reconcile and use a new retry key.')


class ArchiveRequest(Mutation):
    expected_revision: int = Field(ge=1, lt=2147483647)


class PageSummary(BaseModel):
    id: UUID
    slug: str
    title: str
    revision: int
    deleted: bool
    created_at: datetime
    updated_at: datetime


class RevisionSummary(BaseModel):
    id: UUID
    page_id: UUID
    number: int
    title: str
    content_hash: str
    actor_id: UUID
    created_at: datetime


class RevisionView(RevisionSummary):
    body: str
    metadata: dict


class PageView(PageSummary):
    content: RevisionView


class PagesView(BaseModel):
    pages: list[PageSummary]


class HistoryView(BaseModel):
    revisions: list[RevisionSummary]


class EntityCreate(Mutation):
    kind: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    aliases: list[str] = Field(default_factory=list, max_length=15)
    metadata: dict = Field(default_factory=dict)


class EntityUpdate(Mutation):
    label: str = Field(min_length=1, max_length=128)
    metadata: dict = Field(default_factory=dict)
    expected_revision: int = Field(ge=1, lt=2147483647)


class AliasCreate(Mutation):
    alias: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=1, lt=2147483647)


class EntityView(BaseModel):
    id: UUID
    kind: str
    label: str
    metadata: dict
    revision: int
    deleted: bool
    created_at: datetime
    updated_at: datetime
    aliases: list[dict] | None = None


class EntitiesView(BaseModel):
    entities: list[EntityView]


class ClaimCreate(Mutation):
    entity_id: str = Field(min_length=36, max_length=36)
    page_id: str | None = Field(default=None, min_length=36, max_length=36)
    predicate: str = Field(min_length=1, max_length=64)
    value: dict
    evidence_chunk_ids: list[str] = Field(min_length=1, max_length=32)
    metadata: dict = Field(default_factory=dict)
    valid_from: datetime | None = Field(default=None, strict=False)
    valid_to: datetime | None = Field(default=None, strict=False)


class ClaimUpdate(Mutation):
    expected_revision: int = Field(ge=1, lt=2147483647)
    metadata: dict
    evidence_chunk_ids: list[str] | None = Field(default=None, min_length=1, max_length=32)


class ClaimView(BaseModel):
    id: UUID
    entity_id: UUID
    page_id: UUID | None
    predicate: str
    value: dict
    metadata: dict
    revision: int
    deleted: bool
    actor_id: UUID
    valid_from: datetime | None
    valid_to: datetime | None
    created_at: datetime
    evidence: list[dict] | None = None


class ClaimsView(BaseModel):
    claims: list[ClaimView]


class RelationCreate(Mutation):
    source_id: str = Field(min_length=36, max_length=36)
    target_id: str = Field(min_length=36, max_length=36)
    kind: str = Field(min_length=1, max_length=64)
    metadata: dict = Field(default_factory=dict)


class RelationUpdate(Mutation):
    expected_revision: int = Field(ge=1, lt=2147483647)
    metadata: dict
    deleted: bool = False


class RelationView(BaseModel):
    id: UUID
    source_id: UUID
    target_id: UUID
    kind: str
    metadata: dict
    revision: int
    deleted: bool
    actor_id: UUID
    created_at: datetime


class RelationsView(BaseModel):
    relations: list[RelationView]


class ReferenceCreate(Mutation):
    target_kind: Literal['object', 'page', 'source', 'document', 'chunk']
    target_id: str = Field(min_length=36, max_length=36)


class LinkView(BaseModel):
    id: UUID
    entity_id: UUID
    target_kind: str
    target_id: UUID
    label_snapshot: str
    actor_id: UUID
    created_at: datetime
    missing: bool = False


class LinksView(BaseModel):
    references: list[LinkView]


class RemovedView(BaseModel):
    id: UUID
    deleted: Literal[True]


class GraphEntity(EntityView):
    depth: int


class GraphView(BaseModel):
    root: UUID
    depth: int
    direction: str
    nodes: list[GraphEntity]
    relations: list[RelationView]
    references: list[LinkView]
    truncated: bool


class ChangeView(BaseModel):
    id: int
    kind: str
    resource_id: UUID
    operation: str
    revision: int
    actor_id: UUID
    created_at: datetime


class ChangesView(BaseModel):
    changes: list[ChangeView]


def install_knowledge_routes(app, database, auth, read_context, write_context):
    operation = app.state.operation_catalog.bind
    service = KnowledgeService(database, auth.access if auth else None)
    app.state.knowledge = service

    def selected(space_id):
        return service.in_space(space_id) if space_id is not None else service
    def invoke(operation, *args, **kwargs):
        if auth is None: raise HTTPException(503, 'authentication_not_configured')
        try: return operation(*args, **kwargs)
        except PermissionDenied: raise
        except EvidenceNotReady: raise HTTPException(409, 'evidence_not_ready') from None
        except KnowledgeConflict: raise HTTPException(409, 'knowledge_conflict') from None
        except KnowledgeNotFound: raise HTTPException(404, 'knowledge_not_found') from None
        except ValueError: raise HTTPException(422, 'invalid_knowledge_request') from None

    previous_validation_handler = app.exception_handlers[RequestValidationError]
    @app.exception_handler(RequestValidationError)
    async def wiki_validation_error(request, error):
        if request.url.path.endswith(('/api/v1/wiki/pages/resolve', '/api/v1/wiki/pages/upsert')):
            return JSONResponse({'detail':'invalid_knowledge_request'}, status_code=422)
        return await previous_validation_handler(request, error)

    @app.get('/api/v1/wiki/pages', response_model=PagesView)
    @operation('wiki_pages_list', 'Browse authored Wiki page metadata', Role.READER, PagesView, read_only=True, space_field='space_id')
    def pages(limit: int = 50, offset: int = 0, include_deleted: bool = False, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'pages': invoke(selected(space_id).list_pages, context.actor, limit=limit, offset=offset, include_deleted=include_deleted)}

    @app.post('/api/v1/wiki/pages', response_model=PageView, status_code=201)
    @operation('wiki_pages_create', 'Create an authored page with a replay key', Role.EDITOR, PageView, read_only=False, space_field='space_id')
    def create(data: PageCreate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).create_page, context.actor, **data.model_dump())

    @app.get('/api/v1/wiki/pages/resolve', response_model=PageView,
        responses={422:{'model':KnowledgeRequestError}, 404:{'description':'Exact slug not found'}})
    @operation('wiki_pages_resolve', 'Resolve an exact Wiki slug; archived pages require include_deleted',
        Role.READER, PageView, read_only=True, space_field='space_id')
    def resolve_page(slug: str, include_deleted: bool = False, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).resolve_page, context.actor, slug, include_deleted=include_deleted)

    @app.post('/api/v1/wiki/pages/upsert', response_model=PageView,
        responses={422:{'model':KnowledgeRequestError}, 409:{'description':'Revision or retry conflict'},
                   413:{'description':'Serialized request exceeds one MiB'}})
    @operation('wiki_pages_upsert',
        'Create by exact slug only when absent, or update with expected_revision. Never silently overwrites; retry an unchanged request with its original key.',
        Role.EDITOR, PageView, read_only=False, space_field='space_id')
    def upsert_page(data: PageUpsert, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).upsert_page, context.actor, **data.model_dump())

    @app.get('/api/v1/wiki/pages/{page_id}', response_model=PageView)
    @operation('wiki_pages_get', 'Read current or historical immutable Wiki content', Role.READER, PageView, read_only=True, space_field='space_id')
    def page_detail(page_id: UUID, revision: int | None = None, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).get_page, context.actor, page_id, revision=revision)

    @app.put('/api/v1/wiki/pages/{page_id}', response_model=PageView)
    @operation('wiki_pages_update', 'Edit a page with revision and replay protection', Role.EDITOR, PageView, read_only=False, space_field='space_id')
    def edit(page_id: UUID, data: PageUpdate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).update_page, context.actor, page_id, **data.model_dump())

    @app.post('/api/v1/wiki/pages/{page_id}/archive', response_model=PageSummary)
    @operation('wiki_pages_archive', 'Archive a page while retaining revisions', Role.EDITOR, PageSummary, read_only=False, space_field='space_id')
    def archive(page_id: UUID, data: ArchiveRequest, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).delete_page, context.actor, page_id, **data.model_dump())

    @app.get('/api/v1/wiki/pages/{page_id}/revisions', response_model=HistoryView)
    @operation('wiki_revisions_list', 'Inspect immutable authored revision history', Role.READER, HistoryView, read_only=True, space_field='space_id')
    def history(page_id: UUID, limit: int = 50, offset: int = 0, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'revisions': invoke(selected(space_id).page_history, context.actor, page_id, limit=limit, offset=offset)}

    @app.get('/api/v1/wiki/pages/{page_id}/export', response_model=PageView)
    def export(page_id: UUID, format: Literal['json', 'markdown'] = 'json', revision: int | None = None,
               space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        result = invoke(selected(space_id).export_page, context.actor, page_id, revision=revision, format=format)
        if format == 'markdown':
            return PlainTextResponse(result, media_type='text/markdown', headers={
                'Content-Disposition': 'attachment; filename="wiki-' + str(page_id) + '.md"', 'X-Content-Type-Options': 'nosniff'})
        return result

    @app.get('/api/v1/entities', response_model=EntitiesView)
    @operation('entities_list', 'Browse knowledge entities', Role.READER, EntitiesView, read_only=True, space_field='space_id')
    def entities(kind: str | None = None, limit: int = 50, offset: int = 0, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'entities': invoke(selected(space_id).list_entities, context.actor, kind=kind, limit=limit, offset=offset)}

    @app.post('/api/v1/entities', response_model=EntityView, status_code=201)
    @operation('entities_create', 'Create an entity and normalized aliases', Role.EDITOR, EntityView, read_only=False, space_field='space_id')
    def entity_create(data: EntityCreate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).create_entity, context.actor, **data.model_dump())

    @app.get('/api/v1/entities/resolve', response_model=EntityView)
    @operation('entities_resolve', 'Resolve a normalized entity alias', Role.READER, EntityView, read_only=True, space_field='space_id')
    def resolve(alias: str, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).resolve_alias, context.actor, alias)

    @app.get('/api/v1/entities/{entity_id}', response_model=EntityView)
    @operation('entities_get', 'Inspect a knowledge entity', Role.READER, EntityView, read_only=True, space_field='space_id')
    def entity_detail(entity_id: UUID, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).get_entity, context.actor, entity_id)

    @app.put('/api/v1/entities/{entity_id}', response_model=EntityView)
    @operation('entities_update', 'Update entity metadata with revision protection', Role.EDITOR, EntityView, read_only=False, space_field='space_id')
    def entity_update(entity_id: UUID, data: EntityUpdate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).update_entity, context.actor, entity_id, **data.model_dump())

    @app.post('/api/v1/entities/{entity_id}/archive', response_model=EntityView)
    @operation('entities_archive', 'Archive an entity preserving its identity', Role.EDITOR, EntityView, read_only=False, space_field='space_id')
    def entity_archive(entity_id: UUID, data: ArchiveRequest, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).delete_entity, context.actor, entity_id, **data.model_dump())

    @app.post('/api/v1/entities/{entity_id}/aliases', response_model=EntityView)
    @operation('entity_aliases_create', 'Add a reserved normalized entity alias', Role.EDITOR, EntityView, read_only=False, space_field='space_id')
    def alias_add(entity_id: UUID, data: AliasCreate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).add_alias, context.actor, entity_id, data.alias,
            expected_revision=data.expected_revision, idempotency_key=data.idempotency_key)

    @app.get('/api/v1/claims', response_model=ClaimsView)
    @operation('claims_list', 'Browse immutable sourced assertions', Role.READER, ClaimsView, read_only=True, space_field='space_id')
    def claims(entity_id: UUID | None = None, page_id: UUID | None = None, predicate: str | None = None,
               limit: int = 50, offset: int = 0, include_deleted: bool = False, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'claims': invoke(selected(space_id).list_claims, context.actor, entity_id=entity_id, page_id=page_id,
            predicate=predicate, limit=limit, offset=offset, include_deleted=include_deleted)}

    @app.post('/api/v1/claims', response_model=ClaimView, status_code=201)
    @operation('claims_create', 'Record an assertion backed by real evidence', Role.EDITOR, ClaimView, read_only=False, space_field='space_id')
    def claim_create(data: ClaimCreate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).create_claim, context.actor, **data.model_dump())

    @app.get('/api/v1/claims/{claim_id}', response_model=ClaimView)
    @operation('claims_get', 'Inspect an assertion and its provenance', Role.READER, ClaimView, read_only=True, space_field='space_id')
    def claim_detail(claim_id: UUID, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).get_claim, context.actor, claim_id)

    @app.put('/api/v1/claims/{claim_id}', response_model=ClaimView)
    @operation('claims_annotate', 'Annotate a claim without rewriting its assertion', Role.EDITOR, ClaimView, read_only=False, space_field='space_id')
    def claim_update(claim_id: UUID, data: ClaimUpdate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).update_claim, context.actor, claim_id, **data.model_dump())

    @app.post('/api/v1/claims/{claim_id}/retract', response_model=ClaimView)
    @operation('claims_retract', 'Retract a claim while retaining provenance', Role.EDITOR, ClaimView, read_only=False, space_field='space_id')
    def retract(claim_id: UUID, data: ArchiveRequest, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).delete_claim, context.actor, claim_id, **data.model_dump())

    @app.post('/api/v1/knowledge/relations', response_model=RelationView, status_code=201)
    @operation('entity_relations_create', 'Create a bounded entity relationship', Role.EDITOR, RelationView, read_only=False, space_field='space_id')
    def relation_create(data: RelationCreate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).add_relation, context.actor, **data.model_dump())

    @app.put('/api/v1/knowledge/relations/{relation_id}', response_model=RelationView)
    @operation('entity_relations_update', 'Update an entity relationship with revision protection', Role.EDITOR, RelationView, read_only=False, space_field='space_id')
    def relation_update(relation_id: UUID, data: RelationUpdate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).update_relation, context.actor, relation_id, **data.model_dump())

    @app.get('/api/v1/entities/{entity_id}/relations', response_model=RelationsView)
    @operation('entity_relations_list', 'Inspect entity relationships', Role.READER, RelationsView, read_only=True, space_field='space_id')
    def relations(entity_id: UUID, limit: int = 50, offset: int = 0, include_deleted: bool = False,
                  space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'relations': invoke(selected(space_id).list_relations, context.actor, entity_id, limit=limit, offset=offset, include_deleted=include_deleted)}

    @app.post('/api/v1/entities/{entity_id}/references', response_model=LinkView, status_code=201)
    @operation('entity_references_create', 'Attach a typed knowledge reference', Role.EDITOR, LinkView, read_only=False, space_field='space_id')
    def reference(entity_id: UUID, data: ReferenceCreate, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).link_entity, context.actor, entity_id, **data.model_dump())

    @app.get('/api/v1/entities/{entity_id}/references', response_model=LinksView)
    @operation('entity_references_list', 'Inspect typed knowledge references', Role.READER, LinksView, read_only=True, space_field='space_id')
    def references(entity_id: UUID, limit: int = 50, offset: int = 0, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'references': invoke(selected(space_id).entity_links, context.actor, entity_id, limit=limit, offset=offset)}

    @app.post('/api/v1/entities/{entity_id}/references/{link_id}/remove', response_model=RemovedView)
    @operation('entity_references_remove', 'Remove an authored typed reference', Role.EDITOR, RemovedView, read_only=False, space_field='space_id')
    def unlink(entity_id: UUID, link_id: UUID, data: Mutation, space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(space_id).unlink_entity, context.actor, entity_id, link_id, idempotency_key=data.idempotency_key)

    @app.get('/api/v1/knowledge/graph/{entity_id}', response_model=GraphView)
    @operation('knowledge_graph', 'Traverse a bounded supplemental knowledge graph', Role.READER, GraphView, read_only=True, space_field='space_id')
    def graph(entity_id: UUID, depth: int = 1, limit: int = 50, direction: Literal['out','in','both'] = 'both',
              space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(space_id).graph, context.actor, entity_id, depth=depth, limit=limit, direction=direction)

    @app.get('/api/v1/knowledge/changes', response_model=ChangesView)
    @operation('knowledge_changes', 'Read commit-ordered knowledge metadata changes', Role.READER, ChangesView, read_only=True, space_field='space_id')
    def changes(after: int = 0, limit: int = 50, space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return {'changes': invoke(selected(space_id).changes, context.actor, after=after, limit=limit)}
    return service
