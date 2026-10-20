# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""REST and actual SDK clients; identities are trusted disposable test inputs."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
from uuid import UUID, uuid4

from fastapi import HTTPException
import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from czero_core.identity import PermissionDenied, Role, VerifiedIdentity
from czero_core.oauth_clients import OAuthClientService
from czero_core.worker import Worker
from czero_app.knowledge import PageUpsert
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport, RESOURCE

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')

# Presentation help may evolve; retain the accepted validation contracts using
# schema-aware fingerprints frozen from the genuine M17 predecessor.
spec = importlib.util.spec_from_file_location('tool_contract', Path(__file__).parents[1]/'tool_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
M17_CONTRACT = {item['name']:item for item in json.loads(
    (Path(__file__).parents[1]/'fixtures/tool_guidance/m17_contract.json').read_text())['operations']}

UPSERT='/api/v1/wiki/pages/upsert'
RESOLVE='/api/v1/wiki/pages/resolve'


def payload(**changes):
    return {**{'slug':'memory/'+uuid4().hex, 'title':'Procedure', 'body':'Selected café 東京',
               'metadata':{'status':'unverified'}, 'idempotency_key':uuid4().hex}, **changes}


def error(result, code, status):
    assert result.is_error and result.content[0].text == code
    assert result.meta['c0/error'] == {'code':code, 'status':status}
    assert result.structured_content is None


def owner_and_member(fixture, role):
    app, _, _, _, _, issue, owner_token, member_token = fixture
    access=app.state.auth.access
    owner=access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    identity=app.state.auth.oidc.verify_access_token(member_token)
    with pytest.raises(PermissionDenied): access.resolve(identity)
    account=next(a for a in access.list_accounts(owner) if a['username']=='member')
    access.set_role(owner, account['id'], role)
    return owner, identity, issue


def test_accepted_contracts_only_add_optional_space_selectors(application):
    app, owner_token, *_=application
    registry=app.state.operations
    baseline=json.loads((Path(__file__).parents[1]/'fixtures/agent_memory/am1_contract.json').read_text())
    for expected in baseline['operations']:
        actual=registry.definition(expected['name'])
        for key,value in expected.items():
            if key=='description':
                # M18 intentionally revises presentation; the complete card/wire
                # test checks descriptions while these assertions freeze authority.
                assert actual[key] and isinstance(actual[key],str)
                continue
            if key in ('input_schema','output_schema'):
                projected=json.loads(json.dumps(actual[key]))
                if key=='input_schema':
                    for candidate in (projected,projected.get('$defs',{}).get('SearchOptions',{})):
                        properties=candidate.get('properties',{})
                        if 'space_id' in properties:
                            assert 'space_id' not in candidate.get('required',[])
                            assert contract.structural_schema(properties.pop('space_id'))=={
                                'anyOf':[{'format':'uuid','type':'string'},{'type':'null'}],
                                'default':None}
                value_at_key=contract.schema_hash(actual[key])
                value=M17_CONTRACT[expected['name']]['input_sha256' if key=='input_schema' else 'output_sha256']
            else: value_at_key=actual[key]
            assert value_at_key==value, (expected['name'],key)
    owner=app.state.auth.access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    assert len(registry.describe(owner))==77
    schema=app.openapi()
    assert schema['paths'][RESOLVE]['get']['x-c0-operation']=={
        'name':'wiki_pages_resolve','minimum_role':'reader','required_scope':'c0:read','read_only':True,
        'annotations':{'readOnlyHint':True,'destructiveHint':False,'idempotentHint':True,'openWorldHint':False}}
    assert schema['paths'][UPSERT]['post']['x-c0-operation']=={
        'name':'wiki_pages_upsert','minimum_role':'editor','required_scope':'c0:write','read_only':False,
        'annotations':{'readOnlyHint':False,'destructiveHint':True,'idempotentHint':True,'openWorldHint':False}}


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_two_editor_sdk_sessions_race_reload_replay_and_keep_history(transport,knowledge_http,mode):
    async def check():
        app,child,_,_,_,_,_,_=transport
        owner, first_identity, issue=owner_and_member(transport,Role.EDITOR)
        access=app.state.auth.access
        second_identity=VerifiedIdentity(access.issuer,'second-session',str(uuid4()),'second-editor','Synthetic second editor',time.time()+300)
        with pytest.raises(PermissionDenied): access.resolve(second_identity)
        second=next(a for a in access.list_accounts(owner) if a['username']=='second-editor')
        access.set_role(owner,second['id'],Role.EDITOR)
        pairs=[issue(i,{'c0:read','c0:write'}) for i in (first_identity,second_identity)]
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pairs[0].access_token}) as h0, httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+pairs[1].access_token}) as h1:
                async with Client(streamable_http_client(RESOURCE,http_client=h0),mode=mode) as a, Client(
                        streamable_http_client(RESOURCE,http_client=h1),mode=mode) as b:
                    clients=[a,b];slug='investigation/'+uuid4().hex
                    requests=[payload(slug=slug,body='Observation '+str(i)) for i in range(2)]
                    results=await asyncio.gather(*(c.call_tool('wiki_pages_upsert',{'data':d}) for c,d in zip(clients,requests)))
                    assert sum(not r.is_error for r in results)==1
                    winner=next(i for i,r in enumerate(results) if not r.is_error)
                    error(results[1-winner],'knowledge_conflict',409)
                    first=results[winner].structured_content
                    assert (await clients[winner].call_tool('wiki_pages_upsert',{'data':requests[winner]})).structured_content==first
                    assert (await h0.get(RESOLVE,params={'slug':slug})).json()==first
                    updates=[payload(slug=slug,body='Revision '+str(i),expected_revision=1) for i in range(2)]
                    results=await asyncio.gather(*(c.call_tool('wiki_pages_upsert',{'data':d}) for c,d in zip(clients,updates)))
                    assert sum(not r.is_error for r in results)==1
                    winner2=next(i for i,r in enumerate(results) if not r.is_error);loser=1-winner2
                    second=results[winner2].structured_content;error(results[loser],'knowledge_conflict',409)
                    resolved=(await clients[loser].call_tool('wiki_pages_resolve',{'slug':slug})).structured_content
                    retry=payload(slug=slug,body=resolved['content']['body']+'\nAdditional observation',expected_revision=2)
                    final=(await clients[loser].call_tool('wiki_pages_upsert',{'data':retry})).structured_content
                    assert final['revision']==3 and second['content']['body'] in final['content']['body']
                    assert final['content']['content_hash']==hashlib.sha256(retry['body'].encode()).hexdigest()
                    history=(await a.call_tool('wiki_revisions_list',{'page_id':first['id']})).structured_content
                    assert [v['number'] for v in history['revisions']]==[3,2,1]
                    assert (await b.call_tool('wiki_pages_get',{'page_id':first['id'],'revision':1})).structured_content['content']==first['content']
                    assert (await b.call_tool('wiki_pages_get',{'page_id':first['id'],'revision':2})).structured_content['content']==second['content']
                    # Existing tools preserve their behavior and immutable IDs.
                    old=await a.call_tool('wiki_pages_update',{'page_id':first['id'],'data':{
                        'title':'Old client','body':final['content']['body'],'expected_revision':3,'idempotency_key':uuid4().hex}})
                    assert not old.is_error and old.structured_content['revision']==4
                    await a.call_tool('wiki_pages_archive',{'page_id':first['id'],'data':{'expected_revision':4,'idempotency_key':uuid4().hex}})
                    error(await a.call_tool('wiki_pages_resolve',{'slug':slug}),'knowledge_not_found',404)
                    archived=(await b.call_tool('wiki_pages_resolve',{'slug':slug,'include_deleted':True})).structured_content
                    assert archived['deleted'] and archived['revision']==5
                    assert (await clients[winner].call_tool('wiki_pages_upsert',{'data':requests[winner]})).structured_content==first
                    assert (await clients[winner2].call_tool('wiki_pages_upsert',{'data':updates[winner2]})).structured_content==second
                    error(await a.call_tool('wiki_pages_upsert',{'data':payload(slug=slug,expected_revision=5)}),'knowledge_conflict',409)
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('role',list(Role))
def test_new_tools_obey_roles_independent_scopes_and_active_revocation(transport,knowledge_http,mode,role):
    async def check():
        app,child,grants,saved,*_=transport
        owner,identity,issue=owner_and_member(transport,role)
        pair=issue(identity,{'c0:read'})
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    data=payload();denied=await client.call_tool('wiki_pages_upsert',{'data':data})
                    if role is Role.READER:
                        error(denied,'permission_denied',403)
                        assert 'mcp/www_authenticate' not in denied.meta
                    else:
                        error(denied,'insufficient_scope',403)
                        assert 'scope="c0:write"' in denied.meta['mcp/www_authenticate'][0]
                        write=issue(identity,{'c0:write'});http.headers['Authorization']='Bearer '+write.access_token
                        result=await client.call_tool('wiki_pages_upsert',{'data':data});assert not result.is_error
                        error(await client.call_tool('wiki_pages_resolve',{'slug':data['slug']}),'insufficient_scope',403)
                        both=issue(identity,{'c0:read','c0:write'});http.headers['Authorization']='Bearer '+both.access_token
                        assert (await client.call_tool('wiki_pages_resolve',{'slug':data['slug']})).structured_content==result.structured_content
                    actor=app.state.auth.access.resolve(identity)
                    app.state.auth.access.set_role(owner,actor.user_id,None)
                    response=await http.post('/mcp',json={'jsonrpc':'2.0','id':8,'method':'tools/call',
                        'params':{'name':'wiki_pages_resolve','arguments':{'slug':data['slug']}}})
                    assert response.status_code==401
    asyncio.run(check())


@pytest.mark.parametrize('changes',[
    {'slug':'Private/Invalid'}, {'body':'PRIVATE\ud800'}, {'body':'PRIVATE\0'}, {'body':'PRIVATE'+'é'*65537},
    {'metadata':['PRIVATE']}, {'metadata':{'secret':'PRIVATE'+'x'*16384}}, {'expected_revision':True},
    {'idempotency_key':''}, {'unexpected':'PRIVATE'}, {'body':{'secret':'PRIVATE'}},
])
def test_new_rest_validation_is_static_and_legacy_validation_is_preserved(knowledge_http,changes,caplog):
    async def check():
        app,owner,*_=knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner}) as http:
            with caplog.at_level('DEBUG'):
                response=await http.post(UPSERT,content=json.dumps(payload(**changes)).encode(),headers={'Content-Type':'application/json'})
                assert response.status_code==422 and response.json()=={'detail':'invalid_knowledge_request'}
                response=await http.get(RESOLVE,params={'slug':'PRIVATE/INVALID'})
                assert response.status_code==422 and response.json()=={'detail':'invalid_knowledge_request'}
                assert (await http.get(RESOLVE,params={'include_deleted':'PRIVATE'})).json()=={'detail':'invalid_knowledge_request'}
            assert 'PRIVATE' not in repr(PageUpsert(**payload(body='PRIVATE',metadata={'secret':'PRIVATE'})))
            # Retain ordinary FastAPI validation on old Wiki endpoints.
            assert isinstance((await http.post('/api/v1/wiki/pages',json={'body':[]})).json()['detail'],list)
            # Retain the source-specific safe error handler installed earlier.
            assert (await http.post('/api/v1/sources/ingest-text',json={'body':{'private':'PRIVATE'}})).json()=={'detail':'invalid_source_request'}
        assert not any('PRIVATE' in r.message for r in caplog.records if r.name.startswith('czero'))
    asyncio.run(check())


def test_new_rest_raw_limits_bad_json_archive_missing_and_no_auth(knowledge_http):
    async def check():
        app,owner,member,*_=knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as http:
            assert (await http.post(UPSERT,json=payload())).status_code==401
            assert (await http.get(RESOLVE,params={'slug':'missing'})).status_code==401
            http.headers['Authorization']='Bearer '+member
            assert (await http.post(UPSERT,json=payload())).status_code==403
            http.headers['Authorization']='Bearer '+owner
            assert (await http.post(UPSERT,content=b'{"body":"PRIVATE",')).json()=={'detail':'invalid_knowledge_request'}
            async def body():
                for _ in range(17):yield b' '*65536
            huge=await http.post(UPSERT,content=body(),headers={'Content-Type':'application/json'})
            assert huge.status_code==413 and 'PRIVATE' not in huge.text
            missing=await http.post(UPSERT,json=payload(expected_revision=1))
            assert missing.status_code==404 and missing.json()=={'detail':'knowledge_not_found'}
            data=payload();first=(await http.post(UPSERT,json=data)).json()
            assert (await http.get(RESOLVE,params={'slug':data['slug']})).json()==first
            assert (await http.post(UPSERT,json={**data,'idempotency_key':uuid4().hex})).status_code==409
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('failure',[
    (404,'knowledge_not_found','knowledge_not_found',404),
    (409,'knowledge_conflict','knowledge_conflict',409),
    (409,'evidence_not_ready','evidence_not_ready',409),
    (422,'invalid_knowledge_request','invalid_knowledge_request',422),
    (503,'service_unavailable','service_unavailable',503),
    (422,'PRIVATE value is invalid','service_unavailable',503),
    (404,{'private':'PRIVATE'},'service_unavailable',503),
    (500,'PRIVATE','service_unavailable',503),
    ([], 'PRIVATE', 'service_unavailable', 503),
    ('value',None,'invalid_knowledge_request',422),
    ('database',None,'service_unavailable',503),
    ('unexpected',None,'service_unavailable',503),
])
def test_safe_structured_errors_reach_actual_sdk_without_private_values(transport,monkeypatch,mode,failure,caplog):
    async def check():
        app,child,_,_,pair,*_=transport
        status,detail,code,expected=failure
        def fail(*args,**kwargs):
            if status=='value':raise ValueError('PRIVATE')
            if status=='database':raise SQLAlchemyError('PRIVATE')
            if status=='unexpected':raise RuntimeError('PRIVATE')
            raise HTTPException(status,detail)
        monkeypatch.setattr(app.state.knowledge,'resolve_page',fail)
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    result=await client.call_tool('wiki_pages_resolve',{'slug':'safe'})
                    error(result,code,expected)
                    assert 'PRIVATE' not in result.model_dump_json()
                    error(await client.call_tool('wiki_pages_upsert',{'data':{'body':'PRIVATE'}}),'invalid_knowledge_request',422)
        assert 'PRIVATE' not in caplog.text
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_real_unready_chunks_report_structured_error_then_same_key_succeeds(transport,knowledge_http,mode):
    async def check():
        app,child,_,_,pair,*_=transport
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    source=(await client.call_tool('sources_ingest_text',{'data':{
                        'title':'HTTP Wiki evidence '+uuid4().hex,'body':'Selected immutable evidence','idempotency_key':uuid4().hex}})).structured_content
                    Worker(knowledge_http[4],app.state.jobs.registry).tick()
                    document=(await client.call_tool('documents_get',{'version_id':source['id']})).structured_content
                    chunk=(await client.call_tool('document_chunks_list',{'document_id':document['id']})).structured_content['chunks'][0]
                    entity=(await client.call_tool('entities_create',{'data':{'kind':'system','label':'HTTP readiness '+uuid4().hex,'idempotency_key':uuid4().hex}})).structured_content
                    page_data=payload()
                    page=(await client.call_tool('wiki_pages_upsert',{'data':page_data})).structured_content
                    reference=(await client.call_tool('entity_references_create',{'entity_id':entity['id'],'data':{
                        'target_kind':'page','target_id':page['id'],'idempotency_key':uuid4().hex}})).structured_content
                    claim={'entity_id':entity['id'],'page_id':page['id'],'predicate':'observed','value':{'status':'recorded'},
                        'evidence_chunk_ids':[chunk['id']],'idempotency_key':uuid4().hex}
                    with knowledge_http[4].engine.begin() as c:
                        c.execute(text("UPDATE c0_source_versions SET state='queued' WHERE id=:id"),{'id':source['id']})
                    error(await client.call_tool('claims_create',{'data':claim}),'evidence_not_ready',409)
                    response=await http.post('/api/v1/claims',json=claim)
                    assert response.status_code==409 and response.json()=={'detail':'evidence_not_ready'}
                    with knowledge_http[4].engine.begin() as c:
                        c.execute(text("UPDATE c0_source_versions SET state='ready' WHERE id=:id"),{'id':source['id']})
                    result=await client.call_tool('claims_create',{'data':claim});assert not result.is_error
                    saved=(await client.call_tool('claims_get',{'claim_id':result.structured_content['id']})).structured_content
                    assert saved['evidence'][0]['chunk_id']==chunk['id']
                    updated=(await client.call_tool('wiki_pages_upsert',{'data':{
                        **page_data,'body':'Revised reusable procedure','expected_revision':1,'idempotency_key':uuid4().hex}})).structured_content
                    assert updated['id']==page['id'] and updated['revision']==2
                    retained=(await client.call_tool('claims_get',{'claim_id':saved['id']})).structured_content
                    assert retained==saved and retained['page_id']==page['id']
                    references=(await client.call_tool('entity_references_list',{'entity_id':entity['id']})).structured_content['references']
                    assert references==[reference] and not references[0]['missing']
                    assert (await client.call_tool('wiki_pages_get',{'page_id':page['id'],'revision':1})).structured_content['content']==page['content']
    asyncio.run(check())


def test_exact_native_wiki_receipts_helper_survives_app_reconstruction(knowledge_http):
    import importlib.util
    from types import SimpleNamespace
    from czero_app.main import create_app
    path=Path(__file__).parents[1]/'oidc_probe.py'
    spec=importlib.util.spec_from_file_location('native_memory_receipts',path)
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    async def check():
        app,owner_token,*_=knowledge_http
        loop=asyncio.get_running_loop()
        async def use(app,expected=None):
            async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+owner_token}) as http:
                def api(path,data=None,method=None,csrf=None):
                    response=asyncio.run_coroutine_threadsafe(http.request(method or 'GET',path,json=data),loop).result(timeout=15)
                    return response.status_code,response.content,str(response.url)
                browser=SimpleNamespace(api=api);profile={'csrf_token':'disposable'}
                if expected is None:
                    return await asyncio.to_thread(probe.seed_wiki_memory,browser,profile)
                await asyncio.to_thread(probe.verify_wiki_memory_receipts,browser,profile,expected)
        expected=await use(app)
        rebuilt=create_app('czero900',base_path='',database=knowledge_http[4],auth=app.state.auth)
        await use(rebuilt,expected)
    asyncio.run(check())


@pytest.mark.parametrize('role',list(Role))
def test_new_rest_role_matrix_and_cookie_csrf(knowledge_http,role):
    async def check():
        from urllib.parse import parse_qs,urlsplit
        app,owner_token,member_token,*_=knowledge_http
        access=app.state.auth.access
        owner=access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        identity=app.state.auth.oidc.verify_access_token(member_token)
        with pytest.raises(PermissionDenied):access.resolve(identity)
        member=next(a for a in access.list_accounts(owner) if a['username']=='member')
        access.set_role(owner,member['id'],role)
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+member_token}) as http:
            assert (await http.get(RESOLVE,params={'slug':'absent'})).status_code==404
            result=await http.post(UPSERT,json=payload())
            assert result.status_code==(403 if role is Role.READER else 200)
            access.set_role(owner,member['id'],None)
            assert (await http.get(RESOLVE,params={'slug':'absent'})).status_code==403
            http.headers.pop('Authorization')
            login=await http.get('/auth/login');state=parse_qs(urlsplit(login.headers['location']).query)['state'][0]
            assert (await http.get('/auth/callback',params={'state':state,'code':'fixture-only'})).status_code==302
            profile=(await http.get('/api/v1/me')).json();data=payload()
            assert (await http.post(UPSERT,json=data)).status_code==403
            assert (await http.post(UPSERT,json=data,headers={'X-C0-CSRF':profile['csrf_token'],'Origin':'https://wrong.example.test'})).status_code==403
            assert (await http.post(UPSERT,json=data,headers={'X-C0-CSRF':profile['csrf_token'],'Origin':ORIGIN})).status_code==200
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('reason',['disabled','revoked'])
def test_own_client_invalidation_rejects_new_tool_replay(transport,knowledge_http,mode,reason):
    async def check():
        app,child,grants,saved,pair,_,owner_token,_=transport
        owner=app.state.auth.access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                data=payload()
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    assert not (await client.call_tool('wiki_pages_upsert',{'data':data})).is_error
                    if reason=='disabled':
                        OAuthClientService(app.state.auth.access).set_enabled(owner,UUID(saved['client_id']),enabled=False,expected_revision=saved['revision'])
                    else:grants.revoke(pair.access_token,saved['client_id'],resource=RESOURCE)
                    response=await http.post('/mcp',json={'jsonrpc':'2.0','id':9,'method':'tools/call',
                        'params':{'name':'wiki_pages_upsert','arguments':{'data':data}}})
                    assert response.status_code==401
    asyncio.run(check())
