# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from io import BytesIO
import json
import os
from uuid import UUID,uuid4
import httpx2
from httpx import ASGITransport,AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool
from czero_core.identity import PermissionDenied,Role
from test_auth_http import application,ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport,RESOURCE
from test_document_context import BODY
from test_sources_http import source_http
from test_pdf_unit_pipeline import FIXTURES

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')
TOOLS={'source_document_outline_get','source_document_sections_get','source_document_references_get','context_bundle_get'}


def seed(app,token,created,*,body=BODY):
    actor=app.state.auth.access.resolve(app.state.auth.oidc.verify_access_token(token))
    source=app.state.sources
    version=source.ingest(actor,BytesIO(body.encode()),title='Context fixture '+uuid4().hex,
        filename='context.md',media_type='text/markdown',retain_original=True)
    created.append(version['source_id'])
    queue=ExtractionQueue(source.database,source.access,source.originals,enabled=True)
    queue.enqueue(actor,version['id'],expected_generation=1); ExtractionPool(queue).tick()
    return actor,version


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_structure_overflow_keeps_complete_reader_and_explicit_context_limit(transport,source_http,mode):
    app,child,_,_,_,issue,token,_=transport
    body=(FIXTURES/'multipart.md').read_text()
    _,version=seed(app,token,source_http[1],body=body)
    pair=issue(app.state.auth.oidc.verify_access_token(token),{'c0:read'})
    async def check():
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                path='/api/v1/source-documents/'+str(version['source_id'])
                complete=await http.get(path)
                assert complete.status_code==200 and complete.json()['body']==body
                limited=await http.get(path+'/outline')
                assert limited.status_code==413 and limited.json()=={'detail':'too_large'}
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as sdk:
                    result=await sdk.call_tool('source_document_outline_get',{'logical_document_id':str(version['source_id'])})
                    assert result.is_error and result.content[0].text=='too_large'
                assert (await http.get(path)).json()['body']==body
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_real_sdk_refresh_reads_exact_context_and_rest_matches(transport,source_http,mode):
    app,child,_,_,_,issue,token,_=transport
    owner,version=seed(app,token,source_http[1])
    pair=issue(app.state.auth.oidc.verify_access_token(token),{'c0:read'})
    async def check():
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as sdk:
                    tools={tool.name:tool for tool in (await sdk.list_tools()).tools}
                    assert TOOLS<=set(tools)
                    for name in TOOLS:
                        assert tools[name].annotations.read_only_hint and not tools[name].annotations.open_world_hint
                        assert tools[name].meta['securitySchemes']==[{'type':'oauth2','scopes':['c0:read']}]
                    args={'logical_document_id':str(version['source_id'])}
                    outline=await sdk.call_tool('source_document_outline_get',args)
                    assert not outline.is_error and outline.structured_content['revision_id']==str(version['id'])
                    data={'revision_id':str(version['id']),'selection_ids':['s3','s1']}
                    result=await sdk.call_tool('source_document_sections_get',{**args,'data':data})
                    assert not result.is_error and len(result.structured_content['sections'])==2
                    assert json.loads(result.content[0].text)==result.structured_content
                    rest=await http.post('/api/v1/source-documents/'+str(version['source_id'])+'/sections',json=data)
                    assert rest.status_code==200 and rest.json()==result.structured_content
                    assert len(rest.content)==rest.json()['response_bytes']<len(BODY.encode())//5
                    ref=await sdk.call_tool('source_document_references_get',{**args,'data':{
                        'revision_id':str(version['id']),'reference_ids':['r0']}})
                    assert not ref.is_error and ref.structured_content['references'][0]['resolved']
                # A fresh catalog/session performs a genuine bundle operation.
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as later:
                    result=await later.call_tool('context_bundle_get',{'data':{'plan':[{
                        **args,'revision_id':str(version['id']),'selection_ids':['s3'],'reference_ids':['r0']}]}})
                    assert not result.is_error and len(result.structured_content['sections'])==2
                    changed=app.state.sources.ingest(owner,BytesIO(b'# New\n\nNew generation.'),title='Changed',filename='new.md',
                        media_type='text/markdown',source_id=version['source_id'],expected_revision=1)
                    with app.state.sources.database.engine.begin() as c:
                        app.state.jobs.registry.get('source.extract').execute(c,{'version_id':str(changed['id'])})
                    assert (await later.call_tool('source_document_sections_get',{**args,'data':data})).is_error
                    assert (await http.post('/api/v1/source-documents/'+str(version['source_id'])+'/sections',json=data)).status_code==410
    asyncio.run(check())


def test_reader_scope_revocation_and_protected_space_do_not_fall_back(transport,source_http):
    app,_,_,_,_,issue,owner_token,member_token=transport
    owner,version=seed(app,owner_token,source_http[1]); access=app.state.auth.access
    member_identity=app.state.auth.oidc.verify_access_token(member_token)
    with pytest.raises(PermissionDenied): access.resolve(member_identity)
    member=next(row for row in access.list_accounts(owner) if row['username']=='member')
    access.set_role(owner,member['id'],Role.READER)
    read=issue(member_identity,{'c0:read'}); write=issue(app.state.auth.oidc.verify_access_token(owner_token),{'c0:write'})
    async def check():
        path='/api/v1/source-documents/'+str(version['source_id'])+'/outline'
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as http:
            assert (await http.get(path)).status_code==401
            http.headers['Authorization']='Bearer '+write.access_token
            assert (await http.get(path)).status_code==403
            http.headers['Authorization']='Bearer '+read.access_token
            assert (await http.get(path)).status_code==200
            assert (await http.get(path,params={'space_id':str(uuid4())})).status_code==403
            access.set_role(owner,member['id'],None)
            assert (await http.get(path)).status_code==401
    asyncio.run(check())


def test_context_request_errors_and_chunked_limits_never_echo_payload(transport,source_http):
    app,_,_,_,_,_,token,_=transport
    _,version=seed(app,token,source_http[1])
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            path='/api/v1/source-documents/'+str(version['source_id'])+'/sections'
            data={'revision_id':str(version['id']),'selection_ids':['s1'],'unexpected':'PRIVATE_CONTEXT_CANARY'}
            response=await http.post(path,json=data)
            assert response.status_code==422 and 'PRIVATE_CONTEXT_CANARY' not in response.text
            async def body():
                for _ in range(20): yield b'X'*1024
            response=await http.post('/api/v1/context-bundles',content=body(),headers={'Content-Type':'application/json'})
            assert response.status_code==413
    asyncio.run(check())
