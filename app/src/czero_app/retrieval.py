# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Knowledge-search transport delegates all ranking/evidence work to Core."""
from typing import Annotated, Literal
from uuid import UUID
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from czero_core.identity import PermissionDenied
from czero_core.retrieval import SearchService
from czero_app.auth import RequestAccess
from czero_app.sources import CitationView
from czero_app.knowledge import GraphView


class WikiCitation(BaseModel):
    page_id: UUID
    revision_id: UUID
    revision: int
    slug: str
    content_hash: str


class SearchHit(BaseModel):
    id: UUID
    kind: Literal['chunk','wiki_revision']
    resource_id: UUID
    revision: int
    title: str
    content_hash: str
    excerpt: str
    start_offset: int
    end_offset: int
    score: float
    citation: CitationView | None
    wiki: WikiCitation | None
    relevance_score: float | None = Field(default=None, ge=0, le=1)


class SearchResult(BaseModel):
    hits: list[SearchHit]
    retrieval_method: str
    fallback_reason: str | None
    requested_mode: str
    candidate_count: int
    fallback_reasons: list[str]
    scored_count: int
    scorer_truncated_candidates: int
    provider_usage: dict[str, dict[str, int]]
    graphs: list[GraphView]


class IndexStatus(BaseModel):
    configured: bool
    profile_id: UUID | None
    generation: int | None
    indexed: int
    model: str | None = None
    dimensions: int | None = None


class SearchOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1, max_length=512)
    limit: int | None = Field(default=None, ge=1, le=50)
    mode: Literal['auto','text','semantic','hybrid'] = 'auto'
    kind: Literal['all','source','wiki'] = 'all'
    graph_depth: int = Field(default=0, ge=0, le=3)
    rerank: Literal['off','rerank','filter'] | None = None


def install_retrieval_routes(app, database, auth, read_context, *, settings=None):
    from czero_core.retrieval_config import load_settings
    settings=settings or load_settings()
    embedding,scorer=settings.clients()
    service = SearchService(database,auth.access if auth else None,embedding_client=embedding,
        scorer=scorer,scorer_mode=settings.scorer_mode,limits=settings.limits)
    service.configuration_issue=settings.issue
    app.state.search = service

    @app.get('/api/v1/knowledge/search', response_model=SearchResult)
    def search(options: Annotated[SearchOptions, Query()], context: RequestAccess = Depends(read_context)):
        if auth is None: raise HTTPException(503,'authentication_not_configured')
        try: return service.search(context.actor,**options.model_dump())
        except PermissionDenied: raise
        except ValueError: raise HTTPException(422,'invalid_retrieval_request') from None

    @app.get('/api/v1/knowledge/index/status', response_model=IndexStatus)
    def index_status(context: RequestAccess = Depends(read_context)):
        return service.embeddings.status(context.actor)
    return service
