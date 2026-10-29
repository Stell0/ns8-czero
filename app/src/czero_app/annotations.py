# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Typed transport for exact-content annotations and opt-in structured retrieval."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, model_serializer
from starlette.responses import JSONResponse

from czero_core.annotations import AnnotationService, ContentTarget
from czero_core.identity import PermissionDenied, Role
from czero_core.knowledge import EvidenceNotReady
from czero_core.structured import StructuredFilters, StructuredSearchService
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound
from czero_app.auth import RequestAccess
from czero_app.retrieval import WikiCitation
from czero_app.sources import CitationView

Kind = Literal['source_version','wiki_revision','entity','object','claim']
Namespace = Literal['applicability','verification']
Tag = Annotated[str, Field(strict=True, min_length=1, max_length=128)]
Tags = Annotated[list[Tag], Field(max_length=32)]
FilterTags = Annotated[list[Tag], Field(min_length=1, max_length=32)]


def integer_revision(value):
    if isinstance(value, bool): raise ValueError('invalid_content_revision')
    return value


ObservedRevision = Annotated[int, BeforeValidator(integer_revision), Field(ge=1,lt=2147483647)]


def timestamp(value):
    if isinstance(value,str):
        try: value=datetime.fromisoformat(value)
        except (ValueError,OverflowError): raise ValueError('invalid_annotation_time') from None
    if not isinstance(value,datetime):
        raise ValueError('invalid_annotation_time')
    return value


UTCTime = Annotated[AwareDatetime, BeforeValidator(timestamp)]


class AnnotationSupersessionTarget(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Kind
    id: UUID = Field(strict=False)
    revision: int = Field(strict=True, ge=1, lt=2147483647)


class AnnotationSourceReference(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['chunk']
    id: UUID = Field(strict=False)


class AnnotationValue(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    status: str | None = Field(default=None, min_length=1, max_length=64)
    observed_at: UTCTime | None = Field(default=None, strict=False)
    confidence: float | None = Field(default=None, ge=0, le=1)
    extensions: dict[str, JsonValue] | None = None
    source_references: list[AnnotationSourceReference] | None = Field(default=None, max_length=32)

    @model_serializer(mode='wrap')
    def supplied_fields(self, handler):
        # The REST catalog serializes arguments once before invoking the same
        # typed handler as MCP. Preserve omission independently of explicit null.
        value = handler(self)
        return {key:value[key] for key in self.model_fields_set}


class ApplicabilityValue(AnnotationValue):
    products: Tags | None = None
    components: Tags | None = None
    version_tags: Tags | None = None
    knowledge_type: str | None = Field(default=None, min_length=1, max_length=64)
    supersedes: list[AnnotationSupersessionTarget] | None = Field(default=None, max_length=32)


class VerificationValue(AnnotationValue):
    verified_at: UTCTime | None = Field(default=None, strict=False)


class AnnotationUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    value: ApplicabilityValue | VerificationValue = Field(repr=False,
        description='Use fields for the selected namespace; at most 16384 UTF-8 JSON bytes. Missing values stay unknown.')
    expected_revision: int = Field(strict=True, ge=0, lt=2147483646,
        description='Zero creates only. Supply the current annotation revision to update; stale writes conflict.')
    idempotency_key: str = Field(min_length=1, max_length=128)


class ResourceReference(BaseModel):
    kind: Kind
    id: UUID
    revision: int
    space_id: UUID
    resource_id: UUID


class ContentReference(ResourceReference):
    content_hash: str


class AnnotationView(BaseModel):
    id: UUID | None
    target: ContentReference
    namespace: Namespace
    revision: int
    value: dict[str, JsonValue] | None
    status: str
    actor_id: UUID | None
    created_at: datetime | None
    target_current: bool
    target_archived: bool
    current_content_revision: int | None


class AnnotationRevision(BaseModel):
    id: UUID
    number: int
    value: dict[str, JsonValue]
    actor_id: UUID
    created_at: datetime


class AnnotationHistory(BaseModel):
    target: ContentReference
    namespace: Namespace
    revisions: list[AnnotationRevision]


class FilterOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    categories: list[Literal['source','wiki','entity','object','claim']] = Field(
        default_factory=lambda:['source','wiki'], min_length=1, max_length=5)
    products: FilterTags | None = None
    components: FilterTags | None = None
    version_tags: FilterTags | None = Field(default=None, description='Exact literal version tags, not ranges or prefixes.')
    statuses: FilterTags | None = None
    verification_statuses: FilterTags | None = None
    archive: Literal['active','archived','all'] = 'active'
    created_from: UTCTime | None = None
    created_to: UTCTime | None = None
    observed_from: UTCTime | None = None
    observed_to: UTCTime | None = None
    verified_from: UTCTime | None = None
    verified_to: UTCTime | None = None


class StructuredSearch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(strict=True, min_length=1, max_length=512, repr=False)
    space_id: UUID | None = Field(default=None,
        description='Explicit authorized space inside data for MCP; distinct from ordinary search options.space_id.')
    filters: FilterOptions = Field(default_factory=FilterOptions)
    limit: int | None = Field(default=None, strict=True, ge=1, le=50)
    mode: Literal['auto','text','semantic','hybrid'] = 'auto'
    rerank: Literal['off','rerank','filter'] | None = None


class AnnotationSummary(BaseModel):
    revision: int
    status: str
    value: dict[str, JsonValue] | None


class EvidenceReference(BaseModel):
    chunk_id: UUID
    version_id: UUID
    content_hash: str


class StructuredHit(BaseModel):
    id: UUID
    kind: Literal['chunk','wiki_revision','entity','object','claim']
    category: Literal['source','wiki','entity','object','claim']
    reference: ResourceReference
    title: str
    excerpt: str
    start_offset: int | None
    end_offset: int | None
    score: float
    citation: CitationView | None
    wiki: WikiCitation | None
    applicability: AnnotationSummary
    verification: AnnotationSummary
    evidence_refs: list[EvidenceReference]
    retrieval_method: str
    relevance_score: float | None = Field(default=None, ge=0, le=1)


class StructuredResult(BaseModel):
    hits: list[StructuredHit]
    retrieval_method: str
    fallback_reason: str | None
    fallback_reasons: list[str]
    requested_mode: str
    candidate_count: int
    scored_count: int
    scorer_truncated_candidates: int
    provider_usage: dict[str, dict[str,int]]


_PREFIX = '/api/v1/knowledge/annotations/'
_SEARCH = '/api/v1/knowledge/search/structured'
_TARGET = _PREFIX+'{kind}/{target_id}/{content_revision}/{namespace}'


def install_annotation_routes(app, database, auth, read_context, write_context):
    annotations = AnnotationService(database, auth.access if auth else None)
    ordinary = app.state.search
    search = StructuredSearchService(database, auth.access if auth else None,
        embedding_client=ordinary.embeddings.client, scorer=ordinary.scorer,
        scorer_mode=ordinary.scorer_mode, limits=ordinary.limits)
    search.evidence.configuration_issue = ordinary.configuration_issue
    app.state.annotations, app.state.structured_search = annotations, search
    operation = app.state.operation_catalog.bind

    def selected(service, space_id):
        return service.in_space(space_id) if space_id is not None else service

    def invoke(handler, *args, **kwargs):
        if auth is None: raise HTTPException(503, 'authentication_not_configured')
        try: return handler(*args, **kwargs)
        except PermissionDenied: raise
        except EvidenceNotReady: raise HTTPException(409, 'evidence_not_ready') from None
        except KnowledgeConflict: raise HTTPException(409, 'knowledge_conflict') from None
        except KnowledgeNotFound: raise HTTPException(404, 'knowledge_not_found') from None
        except ValueError as error:
            if error.args==('content_superseded',):raise HTTPException(410,'content_superseded') from None
            raise HTTPException(422,'invalid_knowledge_request') from None

    previous_validation = app.exception_handlers[RequestValidationError]
    @app.exception_handler(RequestValidationError)
    async def annotation_validation(request, error):
        if _PREFIX in request.url.path or request.url.path.endswith(_SEARCH):
            return JSONResponse({'detail':'invalid_knowledge_request'},status_code=422)
        return await previous_validation(request,error)

    @app.get(_TARGET, response_model=AnnotationView)
    @operation('knowledge_annotations_get', 'Read applicability or verification for an exact content revision. Missing metadata is unknown, never verified.',
        Role.READER, AnnotationView, space_field='space_id')
    def get(kind: Kind, target_id: UUID, content_revision: ObservedRevision, namespace: Namespace,
            space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        return invoke(selected(annotations,space_id).get,context.actor,ContentTarget(kind,target_id,content_revision),namespace)

    @app.get(_TARGET+'/history', response_model=AnnotationHistory)
    def history(kind: Kind, target_id: UUID, content_revision: ObservedRevision, namespace: Namespace,
            limit: int = 50, offset: int = 0, space_id: UUID | None = None,
            context: RequestAccess = Depends(read_context)):
        return invoke(selected(annotations,space_id).history,context.actor,ContentTarget(kind,target_id,content_revision),namespace,
            limit=limit,offset=offset)

    @app.put(_TARGET, response_model=AnnotationView)
    @operation('knowledge_annotations_update', 'Set one annotation namespace at the observed content revision and expected annotation revision (zero creates). Retry returns the original snapshot; read again for current state.',
        Role.EDITOR, AnnotationView, read_only=False, space_field='space_id')
    def update(kind: Kind, target_id: UUID, content_revision: ObservedRevision, namespace: Namespace, data: AnnotationUpdate,
            space_id: UUID | None = None, context: RequestAccess = Depends(write_context)):
        return invoke(selected(annotations,space_id).update,context.actor,ContentTarget(kind,target_id,content_revision),namespace,
            data.value.model_dump(exclude_unset=True),expected_revision=data.expected_revision,idempotency_key=data.idempotency_key)

    @app.post(_SEARCH, response_model=StructuredResult)
    @operation('knowledge_search_structured', 'Opt-in exact applicability/status/time filtering and typed references. Fields combine with AND, values with OR. Source/Wiki retain citations; entity/object/claim retrieval is deterministic text.',
        Role.READER, StructuredResult, space_field='data.space_id')
    def structured(data: StructuredSearch, context: RequestAccess = Depends(read_context)):
        def execute():
            filters = StructuredFilters(**data.filters.model_dump(exclude_none=True))
            return selected(search,data.space_id).search(context.actor,data.query,filters=filters,
                limit=data.limit,mode=data.mode,rerank=data.rerank)
        return invoke(execute)
    return annotations
