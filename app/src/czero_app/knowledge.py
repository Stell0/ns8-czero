# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Typed Wiki/claim/graph REST adapters for shared Core operations."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from czero_core.identity import PermissionDenied
from czero_core.knowledge import KnowledgeService
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound
from czero_app.auth import RequestAccess


class Mutation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128)


class PageCreate(Mutation):
    slug: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(max_length=131072)
    metadata: dict = Field(default_factory=dict)


class PageUpdate(Mutation):
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(max_length=131072)
    metadata: dict = Field(default_factory=dict)
    expected_revision: int = Field(ge=1, lt=2147483647)


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
    service = KnowledgeService(database, auth.access if auth else None)
    app.state.knowledge = service
    def invoke(operation, *args, **kwargs):
        if auth is None: raise HTTPException(503, 'authentication_not_configured')
        try: return operation(*args, **kwargs)
        except PermissionDenied: raise
        except KnowledgeConflict: raise HTTPException(409, 'knowledge_conflict') from None
        except KnowledgeNotFound: raise HTTPException(404, 'knowledge_not_found') from None
        except ValueError: raise HTTPException(422, 'invalid_knowledge_request') from None

    @app.get('/api/v1/wiki/pages', response_model=PagesView)
    def pages(limit: int = 50, offset: int = 0, include_deleted: bool = False, context: RequestAccess = Depends(read_context)):
        return {'pages': invoke(service.list_pages, context.actor, limit=limit, offset=offset, include_deleted=include_deleted)}

    @app.post('/api/v1/wiki/pages', response_model=PageView, status_code=201)
    def create(data: PageCreate, context: RequestAccess = Depends(write_context)):
        return invoke(service.create_page, context.actor, **data.model_dump())

    @app.get('/api/v1/wiki/pages/{page_id}', response_model=PageView)
    def page_detail(page_id: UUID, revision: int | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(service.get_page, context.actor, page_id, revision=revision)

    @app.put('/api/v1/wiki/pages/{page_id}', response_model=PageView)
    def edit(page_id: UUID, data: PageUpdate, context: RequestAccess = Depends(write_context)):
        return invoke(service.update_page, context.actor, page_id, **data.model_dump())

    @app.post('/api/v1/wiki/pages/{page_id}/archive', response_model=PageSummary)
    def archive(page_id: UUID, data: ArchiveRequest, context: RequestAccess = Depends(write_context)):
        return invoke(service.delete_page, context.actor, page_id, **data.model_dump())

    @app.get('/api/v1/wiki/pages/{page_id}/revisions', response_model=HistoryView)
    def history(page_id: UUID, limit: int = 50, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return {'revisions': invoke(service.page_history, context.actor, page_id, limit=limit, offset=offset)}

    @app.get('/api/v1/wiki/pages/{page_id}/export')
    def export(page_id: UUID, format: Literal['json', 'markdown'] = 'json', revision: int | None = None,
               context: RequestAccess = Depends(read_context)):
        result = invoke(service.export_page, context.actor, page_id, revision=revision, format=format)
        if format == 'markdown':
            return PlainTextResponse(result, media_type='text/markdown', headers={
                'Content-Disposition': 'attachment; filename="wiki-' + str(page_id) + '.md"', 'X-Content-Type-Options': 'nosniff'})
        return result

    @app.get('/api/v1/entities', response_model=EntitiesView)
    def entities(kind: str | None = None, limit: int = 50, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return {'entities': invoke(service.list_entities, context.actor, kind=kind, limit=limit, offset=offset)}

    @app.post('/api/v1/entities', response_model=EntityView, status_code=201)
    def entity_create(data: EntityCreate, context: RequestAccess = Depends(write_context)):
        return invoke(service.create_entity, context.actor, **data.model_dump())

    @app.get('/api/v1/entities/resolve', response_model=EntityView)
    def resolve(alias: str, context: RequestAccess = Depends(read_context)):
        return invoke(service.resolve_alias, context.actor, alias)

    @app.get('/api/v1/entities/{entity_id}', response_model=EntityView)
    def entity_detail(entity_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(service.get_entity, context.actor, entity_id)

    @app.put('/api/v1/entities/{entity_id}', response_model=EntityView)
    def entity_update(entity_id: UUID, data: EntityUpdate, context: RequestAccess = Depends(write_context)):
        return invoke(service.update_entity, context.actor, entity_id, **data.model_dump())

    @app.post('/api/v1/entities/{entity_id}/archive', response_model=EntityView)
    def entity_archive(entity_id: UUID, data: ArchiveRequest, context: RequestAccess = Depends(write_context)):
        return invoke(service.delete_entity, context.actor, entity_id, **data.model_dump())

    @app.post('/api/v1/entities/{entity_id}/aliases', response_model=EntityView)
    def alias_add(entity_id: UUID, data: AliasCreate, context: RequestAccess = Depends(write_context)):
        return invoke(service.add_alias, context.actor, entity_id, data.alias,
            expected_revision=data.expected_revision, idempotency_key=data.idempotency_key)

    @app.get('/api/v1/claims', response_model=ClaimsView)
    def claims(entity_id: UUID | None = None, page_id: UUID | None = None, predicate: str | None = None,
               limit: int = 50, offset: int = 0, include_deleted: bool = False, context: RequestAccess = Depends(read_context)):
        return {'claims': invoke(service.list_claims, context.actor, entity_id=entity_id, page_id=page_id,
            predicate=predicate, limit=limit, offset=offset, include_deleted=include_deleted)}

    @app.post('/api/v1/claims', response_model=ClaimView, status_code=201)
    def claim_create(data: ClaimCreate, context: RequestAccess = Depends(write_context)):
        return invoke(service.create_claim, context.actor, **data.model_dump())

    @app.get('/api/v1/claims/{claim_id}', response_model=ClaimView)
    def claim_detail(claim_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(service.get_claim, context.actor, claim_id)

    @app.put('/api/v1/claims/{claim_id}', response_model=ClaimView)
    def claim_update(claim_id: UUID, data: ClaimUpdate, context: RequestAccess = Depends(write_context)):
        return invoke(service.update_claim, context.actor, claim_id, **data.model_dump())

    @app.post('/api/v1/claims/{claim_id}/retract', response_model=ClaimView)
    def retract(claim_id: UUID, data: ArchiveRequest, context: RequestAccess = Depends(write_context)):
        return invoke(service.delete_claim, context.actor, claim_id, **data.model_dump())

    @app.post('/api/v1/knowledge/relations', response_model=RelationView, status_code=201)
    def relation_create(data: RelationCreate, context: RequestAccess = Depends(write_context)):
        return invoke(service.add_relation, context.actor, **data.model_dump())

    @app.put('/api/v1/knowledge/relations/{relation_id}', response_model=RelationView)
    def relation_update(relation_id: UUID, data: RelationUpdate, context: RequestAccess = Depends(write_context)):
        return invoke(service.update_relation, context.actor, relation_id, **data.model_dump())

    @app.get('/api/v1/entities/{entity_id}/relations', response_model=RelationsView)
    def relations(entity_id: UUID, limit: int = 50, offset: int = 0, include_deleted: bool = False,
                  context: RequestAccess = Depends(read_context)):
        return {'relations': invoke(service.list_relations, context.actor, entity_id, limit=limit, offset=offset, include_deleted=include_deleted)}

    @app.post('/api/v1/entities/{entity_id}/references', response_model=LinkView, status_code=201)
    def reference(entity_id: UUID, data: ReferenceCreate, context: RequestAccess = Depends(write_context)):
        return invoke(service.link_entity, context.actor, entity_id, **data.model_dump())

    @app.get('/api/v1/entities/{entity_id}/references', response_model=LinksView)
    def references(entity_id: UUID, limit: int = 50, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return {'references': invoke(service.entity_links, context.actor, entity_id, limit=limit, offset=offset)}

    @app.post('/api/v1/entities/{entity_id}/references/{link_id}/remove', response_model=RemovedView)
    def unlink(entity_id: UUID, link_id: UUID, data: Mutation, context: RequestAccess = Depends(write_context)):
        return invoke(service.unlink_entity, context.actor, entity_id, link_id, idempotency_key=data.idempotency_key)

    @app.get('/api/v1/knowledge/graph/{entity_id}', response_model=GraphView)
    def graph(entity_id: UUID, depth: int = 1, limit: int = 50, direction: Literal['out','in','both'] = 'both',
              context: RequestAccess = Depends(read_context)):
        return invoke(service.graph, context.actor, entity_id, depth=depth, limit=limit, direction=direction)

    @app.get('/api/v1/knowledge/changes', response_model=ChangesView)
    def changes(after: int = 0, limit: int = 50, context: RequestAccess = Depends(read_context)):
        return {'changes': invoke(service.changes, context.actor, after=after, limit=limit)}
    return service
