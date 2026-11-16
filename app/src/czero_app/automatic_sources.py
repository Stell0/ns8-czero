# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Shared REST/MCP source-definition operations."""
import importlib.util
from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from czero_core.identity import Role, PermissionDenied
from czero_app.auth import RequestAccess


class Save(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    name:str=Field(min_length=1,max_length=256)
    kind:Literal['github','website']
    config:dict=Field(description='GitHub: repositories (owner/name list), include (files/issues/pull_requests/releases), paths/exclude globs, ref. Website: website.seeds, website.allowed_roots, website.sitemaps, website.exclude; optional include URL/path globs. Limits: max_items 1-20, max_requests 4-30, max_bytes up to 2097152, timeout 1-10 seconds. No credentials or commands.')
    enabled:bool=False
    interval_seconds:int|None=Field(default=None,ge=300,le=2678400)
    identifier:UUID|None=Field(default=None,strict=False)
    expected_revision:int|None=Field(default=None,ge=1)
    idempotency_key:str=Field(min_length=1,max_length=128)


class Preview(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    kind:Literal['github','website']
    config:dict=Field(description='GitHub: repositories (owner/name list), include (files/issues/pull_requests/releases), paths/exclude globs, ref. Website: website.seeds, website.allowed_roots, website.sitemaps, website.exclude; optional include URL/path globs. Limits: max_items 1-20, max_requests 4-30, max_bytes up to 2097152, timeout 1-10 seconds. No credentials or commands.')


class PreviewItem(BaseModel):
    title:str
    url:str


class PreviewResult(BaseModel):
    items:list[PreviewItem]
    complete:bool


class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    expected_revision:int=Field(ge=1)
    idempotency_key:str=Field(min_length=1,max_length=128)
    action:Literal['run','pause','remove']


class Ack(BaseModel):
    id:UUID
    revision:int|None=None


class Definition(BaseModel):
    status:str|None=None
    id:UUID
    space_id:UUID
    name:str
    kind:str
    config:dict=Field(description='GitHub: repositories (owner/name list), include (files/issues/pull_requests/releases), paths/exclude globs, ref. Website: website.seeds, website.allowed_roots, website.sitemaps, website.exclude; optional include URL/path globs. Limits: max_items 1-20, max_requests 4-30, max_bytes up to 2097152, timeout 1-10 seconds. No credentials or commands.')
    enabled:bool
    interval_seconds:int|None
    revision:int
    owner_id:UUID
    next_run_at:datetime|None
    last_success_at:datetime|None
    created_at:datetime
    updated_at:datetime


class Definitions(BaseModel):
    definitions:list[Definition]


class Run(BaseModel):
    id:UUID
    definition_id:UUID
    revision:int
    state:str
    error_code:str|None
    processed:int
    created_at:datetime
    finished_at:datetime|None


class Document(BaseModel):
    id:UUID
    title:str
    revision:int
    deleted:bool


class Documents(BaseModel):
    documents:list[Document]


class Runs(BaseModel):
    runs:list[Run]


def install(app,database,auth,read_context,write_context):
    if importlib.util.find_spec('czero_core.automatic_sources') is None:return
    from czero_core.automatic_sources import AutomaticSourceService,UpdateConflict,UpdateNotFound
    service=AutomaticSourceService(database,auth.access if auth else None)
    app.state.automatic_sources=service
    if hasattr(app.state,'website'):app.state.website.automatic_sources=True
    operation=app.state.operation_catalog.bind
    def invoke(space_id,method,actor,**kwargs):
        if auth is None:raise HTTPException(503,'authentication_not_configured')
        try:return getattr(service.in_space(space_id),method)(actor,**kwargs)
        except PermissionDenied:raise
        except UpdateNotFound:raise HTTPException(404,'automatic_source_not_found') from None
        except UpdateConflict:raise HTTPException(409,'automatic_source_conflict') from None
        except (ValueError,RuntimeError):raise HTTPException(422,'invalid_automatic_source') from None

    previous=app.exception_handlers.get(RequestValidationError,request_validation_exception_handler)
    async def validation(request,error):
        if '/api/v1/automatic-sources' in request.url.path:
            return JSONResponse({'detail':'invalid_automatic_source'},status_code=422,headers={'Cache-Control':'no-store'})
        return await previous(request,error)
    app.add_exception_handler(RequestValidationError,validation)

    @app.get('/api/v1/automatic-sources',response_model=Definitions)
    @operation('automatic_sources_list','List automatic source definitions in the selected space.',Role.READER,Definitions,space_field='space_id')
    def listing(space_id:UUID,limit:int=50,offset:int=0,context:RequestAccess=Depends(read_context)):
        return {'definitions':invoke(space_id,'list',context.actor,limit=limit,offset=offset)}

    @app.post('/api/v1/automatic-sources/preview',response_model=PreviewResult)
    @operation('automatic_sources_preview','Fetch a bounded public-source preview without saving definitions or content. Requires selected-space Editor access.',Role.EDITOR,PreviewResult,read_only=False,space_field='space_id')
    def preview(space_id:UUID,data:Preview,context:RequestAccess=Depends(write_context)):
        return invoke(space_id,'preview',context.actor,**data.model_dump())

    @app.post('/api/v1/automatic-sources',response_model=Ack)
    @operation('automatic_sources_save','Create or revise a public GitHub/website definition. Enabling explicitly authorizes recurring native collection for this selection and space under your current Editor membership. Expected revision and replay key required for updates.',Role.EDITOR,Ack,read_only=False,space_field='space_id')
    def save(space_id:UUID,data:Save,context:RequestAccess=Depends(write_context)):
        return invoke(space_id,'save',context.actor,**data.model_dump())

    @app.post('/api/v1/automatic-sources/{identifier}/actions',response_model=Ack)
    @operation('automatic_sources_command','Run now, pause or remove a source definition. Removal retains collected documents. Requires current revision; running requires enabled background authority.',Role.EDITOR,Ack,read_only=False,space_field='space_id')
    def command(space_id:UUID,identifier:UUID,data:Command,context:RequestAccess=Depends(write_context)):
        return invoke(space_id,'command',context.actor,identifier=identifier,**data.model_dump())

    @app.get('/api/v1/automatic-sources/{identifier}/runs',response_model=Runs)
    @operation('automatic_source_runs_list','Inspect collection, extraction and completion status. Partial/queued work is not verified completion.',Role.READER,Runs,space_field='space_id')
    def runs(space_id:UUID,identifier:UUID,limit:int=50,offset:int=0,context:RequestAccess=Depends(read_context)):
        return {'runs':invoke(space_id,'runs',context.actor,identifier=identifier,limit=limit,offset=offset)}

    @app.get('/api/v1/automatic-sources/{identifier}/documents',response_model=Documents)
    @operation('automatic_source_documents_list','List source documents owned by this selected-space definition. Read their current complete originals through the normal source document APIs.',Role.READER,Documents,space_field='space_id')
    def documents(space_id:UUID,identifier:UUID,limit:int=50,offset:int=0,context:RequestAccess=Depends(read_context)):
        return {'documents':invoke(space_id,'documents',context.actor,identifier=identifier,limit=limit,offset=offset)}
