# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual REST and current/legacy SDK evidence ingestion; disposable identities only."""
import asyncio
import json
import logging
import os
from uuid import UUID, uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest

from czero_core.identity import PermissionDenied, Role
from czero_core.oauth_clients import OAuthClientService
from czero_core.worker import Worker
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport, RESOURCE

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
PATH='/api/v1/sources/ingest-text'


def payload(**changes):
    value={'idempotency_key':uuid4().hex,'title':'HTTP Wiki evidence '+uuid4().hex,
        'body':'# Investigation\n\nSelected observation café 東京 🔧','media_type':'text/markdown',
        'metadata':{'origin':'synthetic session','knowledge_type':'investigation'}}
    return {**value,**changes}


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_editor_sdk_ingests_real_chunks_claim_and_revision_with_rest_parity(transport,knowledge_http,mode):
    async def check():
        app,child,_,_,_,issue,owner_token,member_token=transport
        access=app.state.auth.access; owner=access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        identity=app.state.auth.oidc.verify_access_token(member_token)
        with pytest.raises(PermissionDenied): access.resolve(identity)
        member=next(a for a in access.list_accounts(owner) if a['username']=='member')
        access.set_role(owner,member['id'],Role.EDITOR)
        pair=issue(identity,{'c0:read','c0:write'})
        data=payload()
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    tool=next(t for t in (await client.list_tools()).tools if t.name=='sources_ingest_text')
                    assert not tool.annotations.read_only_hint
                    assert tool.meta['securitySchemes']==[{'type':'oauth2','scopes':['c0:write']}]
                    ingested=await client.call_tool('sources_ingest_text',{'data':data})
                    assert not ingested.is_error
                    receipt=ingested.structured_content
                    assert receipt['source_id'] and receipt['id'] and receipt['content_hash']
                    assert receipt['state']=='queued' and receipt['original_present']
                    assert json.loads(ingested.content[0].text)==receipt
                    assert (await client.call_tool('documents_get',{'version_id':receipt['id']})).is_error
                    Worker(knowledge_http[4],app.state.jobs.registry).tick()
                    versions=await client.call_tool('source_versions_list',{'source_id':receipt['source_id']})
                    assert versions.structured_content['versions'][0]['state']=='ready'
                    doc=(await client.call_tool('documents_get',{'version_id':receipt['id']})).structured_content
                    assert doc['body']==data['body']
                    chunks=(await client.call_tool('document_chunks_list',{'document_id':doc['id']})).structured_content['chunks']
                    citation=(await client.call_tool('citations_get',{'chunk_id':chunks[0]['id']})).structured_content
                    assert citation['version_id']==receipt['id'] and citation['source_hash']==receipt['content_hash']
                    entity=(await client.call_tool('entities_create',{'data':{'kind':'system','label':'SDK investigation '+uuid4().hex,
                        'idempotency_key':uuid4().hex}})).structured_content
                    claim=await client.call_tool('claims_create',{'data':{'entity_id':entity['id'],'predicate':'observed-state',
                        'value':{'state':'recorded'},'evidence_chunk_ids':[chunks[0]['id']],'idempotency_key':uuid4().hex}})
                    assert not claim.is_error
                    saved=(await client.call_tool('claims_get',{'claim_id':claim.structured_content['id']})).structured_content
                    assert saved['evidence'][0]['chunk_id']==chunks[0]['id']
                    response=await http.post(PATH,json=data)
                    assert response.status_code==202 and response.json()==receipt
                    assert (await client.call_tool('sources_ingest_text',{'data':data})).structured_content==receipt
                    changed={**data,'body':data['body']+'\nA new observation.','source_id':receipt['source_id'],
                        'expected_revision':1,'idempotency_key':uuid4().hex}
                    revision=(await client.call_tool('sources_ingest_text',{'data':changed})).structured_content
                    assert revision['number']==2 and revision['state']=='queued'
                    stale={**changed,'body':'A stale writer','idempotency_key':uuid4().hex}
                    assert (await http.post(PATH,json=stale)).status_code==409
                    assert (await client.call_tool('sources_ingest_text',{'data':stale})).is_error
                    assert (await client.call_tool('citations_get',{'chunk_id':chunks[0]['id']})).structured_content==citation
                    Worker(knowledge_http[4],app.state.jobs.registry).tick()
                # A new SDK session resolves persisted evidence and the original receipt.
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as later:
                    assert (await later.call_tool('sources_ingest_text',{'data':changed})).structured_content==revision
                    doc2=(await later.call_tool('documents_get',{'version_id':revision['id']})).structured_content
                    assert doc2['body']==changed['body'] and doc2['id']!=doc['id']
                    assert (await http.get('/api/v1/source-versions/'+receipt['id']+'/document')).json()==doc
                    assert (await http.get('/api/v1/chunks/'+chunks[0]['id']+'/citation')).json()==citation
    asyncio.run(check())


@pytest.mark.parametrize('role',list(Role))
def test_rest_text_role_csrf_and_revoked_membership(knowledge_http,role):
    async def check():
        app,owner_token,member_token,*_=knowledge_http
        data=payload()
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as http:
            assert (await http.post(PATH,json=data)).status_code==401
            http.headers['Authorization']='Bearer '+owner_token
            assert (await http.get('/api/v1/me')).status_code==200
            http.headers['Authorization']='Bearer '+member_token
            assert (await http.get('/api/v1/me')).status_code==403
            http.headers['Authorization']='Bearer '+owner_token
            member=next(a for a in (await http.get('/api/v1/access/accounts')).json()['accounts'] if a['username']=='member')
            assert (await http.put('/api/v1/access/accounts/'+member['id'],json={'role':role.value})).status_code==204
            http.headers['Authorization']='Bearer '+member_token
            response=await http.post(PATH,json=data)
            assert response.status_code==(403 if role is Role.READER else 202)
            http.headers['Authorization']='Bearer '+owner_token
            await http.put('/api/v1/access/accounts/'+member['id'],json={'role':None})
            http.headers['Authorization']='Bearer '+member_token
            assert (await http.post(PATH,json=data)).status_code==403
            http.headers.pop('Authorization')
            # First-party cookie writes keep the existing same-origin/CSRF guards.
            from urllib.parse import parse_qs,urlsplit
            login=await http.get('/auth/login');state=parse_qs(urlsplit(login.headers['location']).query)['state'][0]
            assert (await http.get('/auth/callback',params={'state':state,'code':'fixture-only'})).status_code==302
            profile=(await http.get('/api/v1/me')).json()
            assert (await http.post(PATH,json=data)).status_code==403
            assert (await http.post(PATH,json=data,headers={'X-C0-CSRF':profile['csrf_token'],'Origin':'https://wrong.example.test'})).status_code==403
            assert (await http.post(PATH,json=data,headers={'X-C0-CSRF':profile['csrf_token'],'Origin':ORIGIN})).status_code==202
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_sdk_text_scope_reader_denial_and_disabled_client_replay(transport,knowledge_http,mode):
    async def check():
        app,child,_,saved,_,issue,owner_token,member_token=transport
        access=app.state.auth.access;owner=access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        identity=app.state.auth.oidc.verify_access_token(member_token)
        with pytest.raises(PermissionDenied):access.resolve(identity)
        member=next(a for a in access.list_accounts(owner) if a['username']=='member')
        access.set_role(owner,member['id'],Role.READER)
        reader=issue(identity,{'c0:read'})
        data=payload()
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+reader.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    assert 'sources_ingest_text' not in {t.name for t in (await client.list_tools()).tools}
                    denied=await client.call_tool('sources_ingest_text',{'data':data})
                    assert denied.is_error and denied.content[0].text=='permission_denied'
                    assert not denied.meta or 'mcp/www_authenticate' not in denied.meta
                access.set_role(owner,member['id'],Role.EDITOR)
                narrow=issue(identity,{'c0:read'});http.headers['Authorization']='Bearer '+narrow.access_token
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    assert 'sources_ingest_text' in {t.name for t in (await client.list_tools()).tools}
                    denied=await client.call_tool('sources_ingest_text',{'data':data})
                    assert denied.is_error and denied.content[0].text=='insufficient_scope'
                    assert 'scope="c0:write"' in denied.meta['mcp/www_authenticate'][0]
                pair=issue(identity,{'c0:write'});http.headers['Authorization']='Bearer '+pair.access_token
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    receipt=await client.call_tool('sources_ingest_text',{'data':data})
                    assert not receipt.is_error  # write-only consent is sufficient for ingestion
                    replay=await http.post(PATH,json=data)
                    assert replay.status_code==202 and replay.json()==receipt.structured_content
                    OAuthClientService(access).set_enabled(owner,UUID(saved['client_id']),enabled=False,expected_revision=saved['revision'])
                    assert (await http.post(PATH,json=data)).status_code==401
                    response=await http.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/call',
                        'params':{'name':'sources_ingest_text','arguments':{'data':data}}})
                    assert response.status_code==401
    asyncio.run(check())


def test_rest_text_errors_limits_unicode_and_logs_do_not_echo_evidence(knowledge_http,caplog):
    marker='SYNTHETIC_EVIDENCE_DO_NOT_ECHO'
    caplog.set_level(logging.INFO)
    async def check():
        app,owner,*_=knowledge_http
        data=payload(body=marker)
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner}) as http:
            for bad in ({**data,'media_type':'application/pdf'},{**data,'metadata':[]},
                    {**data,'expected_revision':True},{**data,'extra':marker},{'body':marker},
                    {**data,'body':marker+'\ud800'},{**data,'body':marker+'\0'},
                    {**data,'body':marker+'é'*65537},{**data,'metadata':{'value':marker+'x'*16384}}):
                r=await http.post(PATH,content=json.dumps(bad).encode(),headers={'Content-Type':'application/json'})
                assert r.status_code==422 and r.json()=={'detail':'invalid_source_request'}
                assert marker not in r.text
            for raw in (b'{"body":"'+marker.encode()+b'",',b'{"body":"\xff"}'):
                r=await http.post(PATH,content=raw,headers={'Content-Type':'application/json'})
                assert r.status_code in (400,422) and marker not in r.text
            async def oversized():
                yield b'{"body":"'+marker.encode()
                for _ in range(17):yield b'x'*65536
            r=await http.post(PATH,content=oversized(),headers={'Content-Type':'application/json'})
            assert r.status_code==413 and r.json()=={'detail':'upload_too_large'} and marker not in r.text
            assert not app.state.sources.originals.root.exists()
            schema=(await http.get('/openapi.json')).json()
            error=schema['paths'][PATH]['post']['responses']['422']['content']['application/json']['schema']
            assert error['$ref'].endswith('/TextRequestError')
            guide=(await http.get('/agents')).text
            assert 'sources_ingest_text' in guide and '128 KiB' in guide
            # Existing endpoint validation retains its original contract.
            old=await http.post('/api/v1/source-versions/not-a-uuid/retry',json={'expected_generation':'invalid'})
            assert old.status_code==422 and isinstance(old.json()['detail'],list)
    asyncio.run(check())
    assert marker not in caplog.text


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_sdk_invalid_text_and_model_errors_are_static(transport,knowledge_http,mode,caplog):
    marker='SYNTHETIC_MCP_EVIDENCE_DO_NOT_ECHO'
    caplog.set_level(logging.INFO)
    async def check():
        app,child,_,_,pair,*_=transport
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    for data in (payload(body=marker+'\0'),payload(body=marker,metadata=[]),
                            payload(body=marker+'é'*65537),payload(body=marker,media_type='application/pdf')):
                        r=await client.call_tool('sources_ingest_text',{'data':data})
                        assert r.is_error and r.content[0].text=='invalid_operation_request'
                        assert marker not in json.dumps(r.model_dump(mode='json'))
                    rpc={'jsonrpc':'2.0','id':7,'method':'tools/call','params':{
                        'name':'sources_ingest_text','arguments':{'data':payload(body=marker+'\ud800')}}}
                    raw=await http.post('/mcp',content=json.dumps(rpc).encode(),headers={
                        'Content-Type':'application/json','Accept':'application/json, text/event-stream',
                        'MCP-Protocol-Version':'2025-11-25'})
                    assert raw.status_code==400 and raw.json()['error']['code']==-32700
                    assert marker not in raw.text
                    rpc={'body':'RPC8SECRET','jsonrpc':'2.0','id':7,'params':{'name':'sources_ingest_text'}}
                    raw=await http.post('/mcp',content=json.dumps(rpc).encode(),headers={
                        'Content-Type':'application/json','Accept':'application/json, text/event-stream',
                        'MCP-Protocol-Version':'2025-11-25'})
                    assert raw.status_code==400 and 'RPC8SECRET' not in raw.text
                    assert raw.json()['error']['message']=='invalid_mcp_request'
    asyncio.run(check())
    assert marker not in caplog.text and 'RPC8SECRET' not in caplog.text


def test_exact_native_text_seed_and_receipt_recovery_with_signed_rest(knowledge_http):
    import importlib.util
    from pathlib import Path
    from fastapi.testclient import TestClient
    spec=importlib.util.spec_from_file_location('native_text_probe',Path(__file__).parents[1]/'oidc_probe.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    app,owner,*_=knowledge_http
    with TestClient(app,headers={'Authorization':'Bearer '+owner}) as client:
        class Browser:
            def api(self,path,data=None,method=None,csrf=None):
                if '/versions' in path: Worker(knowledge_http[4],app.state.jobs.registry).tick()
                response=client.request(method or 'GET',path,json=data)
                return response.status_code,response.content,str(response.url)
        browser=Browser();profile={'csrf_token':None}
        records=probe.seed_text_sources(browser,profile,title='HTTP Wiki evidence '+uuid4().hex)
        assert len(records)==2 and records[0]['version']['source_id']==records[1]['version']['source_id']
        for record in records:
            probe.source_state(browser,record['version'],'ready',seconds=10)
            version=record['version']
            document=client.get('/api/v1/source-versions/'+version['id']+'/document').json()
            assert document['body']==record['text']
            chunk=client.get('/api/v1/documents/'+document['id']+'/chunks').json()['chunks'][0]
            citation=client.get('/api/v1/chunks/'+chunk['id']+'/citation').json()
            assert citation['source_hash']==version['content_hash']
        probe.verify_text_receipts(browser,profile,records)
