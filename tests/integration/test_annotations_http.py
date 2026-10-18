# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed REST and actual current/legacy SDK annotation and retrieval contracts."""
import asyncio
import hashlib
from pathlib import Path
import json
import os
from uuid import UUID, uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text

from czero_core.identity import PermissionDenied, Role
from czero_core.worker import Worker
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_spaces_http import space_http, create_space
from test_mcp_http import transport, RESOURCE
from test_wiki_memory_http import error, owner_and_member

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
SEARCH = '/api/v1/knowledge/search/structured'


@pytest.fixture
def annotation_http(knowledge_http, space_http, transport):
    yield knowledge_http, space_http, transport
    app = knowledge_http[0]
    with app.state.auth.access.database.engine.begin() as connection:
        connection.execute(text('''DELETE FROM c0_annotation_targets WHERE created_by IN
            (SELECT id FROM c0_accounts WHERE issuer=:issuer)'''), {'issuer': app.state.auth.access.issuer})


def target(row, kind='wiki_revision'):
    return {'kind': kind, 'target_id': row['content']['id'] if kind == 'wiki_revision' else row['id'],
            'content_revision': row['number'] if kind == 'source_version' else row['revision']}


def path(reference, namespace='verification'):
    return '/api/v1/knowledge/annotations/{kind}/{target_id}/{content_revision}/'.format(**reference)+namespace


def mutation(value, revision=0, key=None):
    return {'value':value, 'expected_revision':revision, 'idempotency_key':key or uuid4().hex}


async def page(http, space_id=None, body=None):
    response = await http.post('/api/v1/wiki/pages/upsert', params={'space_id':space_id} if space_id else {},
        json={'slug':'annotations/'+uuid4().hex, 'title':'Resolver procedure', 'body':body or 'getent resolver '+uuid4().hex,
              'idempotency_key':uuid4().hex})
    assert response.status_code == 200
    return response.json()


def test_rest_separate_annotations_history_replay_and_exact_search(annotation_http):
    async def check():
        fixture, spaces, _ = annotation_http
        app, token, *_ = fixture
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            private = await create_space(http, spaces); params={'space_id':private['id']}
            row = await page(http, private['id']); ref=target(row)
            missing = await http.get(path(ref), params=params)
            assert missing.status_code == 200
            assert missing.json()['revision'] == 0 and missing.json()['status'] == 'unknown'
            applicable = mutation({'products':['NS8'], 'components':['resolver'], 'version_tags':['8.4'], 'status':'applicable'})
            first = await http.put(path(ref,'applicability'), params=params, json=applicable)
            assert first.status_code == 200
            verified = await http.put(path(ref), params=params,
                json=mutation({'status':'verified','verified_at':'2026-10-18T02:00:00+02:00','confidence':.9}))
            assert verified.status_code == 200 and verified.json()['value']['verified_at'] == '2026-10-18T00:00:00+00:00'
            assert (await http.get(path(ref,'applicability'),params=params)).json() == first.json()
            assert (await http.put(path(ref,'applicability'),params=params,json=applicable)).json() == first.json()
            assert (await http.put(path(ref,'applicability'),params=params,json=mutation({'status':'stale'}))).status_code == 409
            current = await http.put(path(ref), params=params, json=mutation({'status':'contradicted'},1))
            assert current.json()['revision'] == 2
            history = (await http.get(path(ref)+'/history',params=params)).json()
            assert [r['number'] for r in history['revisions']] == [2,1]
            request={'query':'getent','space_id':private['id'],'mode':'text', 'filters':{
                'categories':['wiki'],'products':['NS8'],'components':['resolver'],'version_tags':['8.4']}}
            result = await http.post(SEARCH,json=request)
            assert result.status_code == 200 and result.json()['candidate_count'] == 1
            hit=result.json()['hits'][0]
            assert hit['reference']['id'] == row['content']['id'] and hit['reference']['revision'] == 1
            assert hit['applicability']['revision'] == 1 and hit['verification']['status'] == 'contradicted'
            assert hit['citation'] is None and hit['wiki']['revision_id'] == row['content']['id']
            assert (await http.post(SEARCH,json={**request,'filters':{**request['filters'],'version_tags':['8.40']}})).json()['hits'] == []
            assert (await http.post(SEARCH,json={**request,'space_id':None})).json()['hits'] == []
            assert (await http.get(path(ref))).status_code == 404
            changed=(await http.post('/api/v1/wiki/pages/upsert',params=params,json={
                'slug':row['slug'],'title':row['title'],'body':row['content']['body']+' changed',
                'expected_revision':1,'idempotency_key':uuid4().hex})).json()
            fresh=(await http.get(path(target(changed)),params=params)).json()
            assert fresh['status']=='unknown' and fresh['revision']==0
            assert (await http.get(path(ref),params=params)).json()['target_current'] is False
            assert (await http.put(path(ref,'applicability'),params=params,json=applicable)).json()==first.json()
            assert (await http.get('/api/v1/wiki/pages/'+row['id'],params={**params,'revision':1})).json()['content']==row['content']
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_sdk_annotation_and_structured_search_match_rest(annotation_http, mode):
    async def check():
        fixture, spaces, transport = annotation_http
        app, child, _, _, pair, *_ = transport
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+fixture[1]}) as rest:
            private=await create_space(rest,spaces)
            row=await page(rest,private['id']); ref=target(row)
            args={**ref,'namespace':'verification','space_id':private['id']}
            wire=[]
            async def capture(response):
                if response.status_code==200 and response.request.url.path=='/mcp':
                    wire.append(json.loads(await response.aread()))
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token},event_hooks={'response':[capture]}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        tools={tool.name:tool for tool in (await client.list_tools()).tools}
                        assert len(tools)==75
                        assert tools['knowledge_annotations_update'].meta['securitySchemes']==[{'type':'oauth2','scopes':['c0:write']}]
                        assert tools['knowledge_search_structured'].annotations.read_only_hint
                        missing=await client.call_tool('knowledge_annotations_get',args)
                        assert not missing.is_error and missing.structured_content['status']=='unknown'
                        data=mutation({'status':'verified'})
                        saved=await client.call_tool('knowledge_annotations_update',{**args,'data':data})
                        assert not saved.is_error
                        assert (await rest.put(path(ref),params={'space_id':private['id']},json=data)).json()==saved.structured_content
                        assert (await client.call_tool('knowledge_annotations_get',args)).structured_content==saved.structured_content
                        history=await client.call_tool('knowledge_annotations_history',args)
                        assert [r['number'] for r in history.structured_content['revisions']]==[1]
                        search={'query':'getent','space_id':private['id'],'mode':'text','filters':{
                            'categories':['wiki'],'verification_statuses':['verified']}}
                        result=await client.call_tool('knowledge_search_structured',{'data':search})
                        assert not result.is_error and result.structured_content==(await rest.post(SEARCH,json=search)).json()
                        assert json.loads(result.content[0].text)==result.structured_content
                        error(await client.call_tool('knowledge_annotations_update',{**args,'data':mutation({'status':'stale'})}), 'knowledge_conflict',409)
                        error(await client.call_tool('knowledge_annotations_get',{**args,'target_id':str(uuid4())}), 'knowledge_not_found',404)
                        raw_tools=next(message['result']['tools'] for message in wire if 'tools' in message.get('result',{}))
                        raw_update=next(tool for tool in raw_tools if tool['name']=='knowledge_annotations_update')
                        assert raw_update['securitySchemes']==raw_update['_meta']['securitySchemes']==[{'type':'oauth2','scopes':['c0:write']}]
                        assert any(message.get('result',{}).get('structuredContent')==saved.structured_content for message in wire)
                        raw_error=next(message['result'] for message in wire if message.get('result',{}).get('isError') and
                            message['result']['content'][0]['text']=='knowledge_conflict')
                        assert raw_error['_meta']['c0/error']=={'code':'knowledge_conflict','status':409}
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('role',list(Role))
def test_annotation_tools_enforce_current_role_space_scope_and_regrant(annotation_http, mode, role):
    async def check():
        fixture, spaces, transport = annotation_http
        app, child, _, _, _, _, owner_token, _ = transport
        owner, identity, issue = owner_and_member(transport,role)
        member = app.state.auth.access.resolve(identity)
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner_token}) as rest:
            private=await create_space(rest,spaces); row=await page(rest,private['id']); ref=target(row)
            grant=app.state.spaces.set_grant(owner,private['id'],member.user_id,Role.READER if role is Role.READER else Role.EDITOR,
                expected_revision=0,idempotency_key=uuid4().hex)
            pair=issue(identity,{'c0:read'})
            args={**ref,'namespace':'verification','space_id':private['id']}
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        assert (await client.call_tool('knowledge_annotations_get',args)).structured_content['status']=='unknown'
                        error(await client.call_tool('knowledge_annotations_get',{**args,'space_id':None}), 'knowledge_not_found',404)
                        denied=await client.call_tool('knowledge_annotations_update',{**args,'data':mutation({'status':'verified'})})
                        if role is Role.READER:
                            error(denied,'permission_denied',403)
                            assert 'mcp/www_authenticate' not in denied.meta
                        else:
                            error(denied,'insufficient_scope',403)
                            assert 'scope="c0:write"' in denied.meta['mcp/www_authenticate'][0]
                            narrow=issue(identity,{'c0:write'})
                            http.headers['Authorization']='Bearer '+narrow.access_token
                            assert not (await client.call_tool('knowledge_annotations_update',{
                                **args,'data':mutation({'status':'unverified'})})).is_error
                            for operation,arguments in (
                                    ('knowledge_annotations_get',args),('knowledge_annotations_history',args),
                                    ('knowledge_search_structured',{'data':{'query':'getent','space_id':private['id']}})):
                                denied=await client.call_tool(operation,arguments)
                                error(denied,'insufficient_scope',403)
                                assert 'scope="c0:read"' in denied.meta['mcp/www_authenticate'][0]
                        if role is not Role.ADMIN:
                            app.state.spaces.set_grant(owner,private['id'],member.user_id,None,
                                expected_revision=grant['revision'],idempotency_key=uuid4().hex)
                            response=await http.post('/mcp',json={'jsonrpc':'2.0','id':14,'method':'tools/call',
                                'params':{'name':'knowledge_annotations_get','arguments':args}})
                            assert response.status_code==401
                            app.state.spaces.set_grant(owner,private['id'],member.user_id,Role.READER if role is Role.READER else Role.EDITOR,
                                expected_revision=2,idempotency_key=uuid4().hex)
                            assert (await http.post('/mcp',json={'jsonrpc':'2.0','id':15,'method':'tools/call',
                                'params':{'name':'knowledge_annotations_get','arguments':args}})).status_code==401
                            fresh=issue(identity,{'c0:read'})
                            http.headers['Authorization']='Bearer '+fresh.access_token
                            assert not (await client.call_tool('knowledge_annotations_get',args)).is_error
    asyncio.run(check())


@pytest.mark.parametrize('changes',[
    {'expected_revision':True}, {'expected_revision':-1}, {'value':{'status':None}},
    {'value':{'verified_at':'2026-10-18'}}, {'value':{'verified_at':0}}, {'value':{'verified_at':'0'}}, {'value':{'confidence':True}},
    {'value':{'confidence':2}}, {'value':{'products':['PRIVATE']}},
    {'value':{'extensions':{'private':'x'*16384}}}, {'value':{'status':'PRIVATE\ud800'}},
    {'value':{'unexpected':'PRIVATE'}}, {'unexpected':'PRIVATE'},
])
def test_annotation_and_search_invalid_input_is_bounded_and_private(annotation_http, changes, caplog):
    async def check():
        fixture, _, _=annotation_http
        app,token,*_=fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            row=await page(http); ref=target(row)
            with caplog.at_level('DEBUG'):
                response=await http.put(path(ref),content=json.dumps({**mutation({'status':'verified'}),**changes}).encode(),
                    headers={'Content-Type':'application/json'})
                assert response.status_code==422 and response.json()=={'detail':'invalid_knowledge_request'}
                for filters in ({'version_tags':[]},{'categories':['PRIVATE']},{'verified_from':'2026-10-18'},{'verified_from':0},{'verified_from':'0'},
                                {'products':['PRIVATE'*100]},{'archive':'PRIVATE'}):
                    response=await http.post(SEARCH,json={'query':'PRIVATE','filters':filters})
                    assert response.status_code==422 and response.json()=={'detail':'invalid_knowledge_request'}
                assert (await http.get(path({**ref,'target_id':'not-a-uuid'}))).json()=={'detail':'invalid_knowledge_request'}
            assert (await http.get(path(ref))).json()['revision']==0
    asyncio.run(check())
    assert 'PRIVATE' not in caplog.text


def test_explicit_nulls_and_missing_values_keep_rest_sdk_parity(annotation_http):
    async def check():
        fixture, _, transport=annotation_http
        app,child,_,_,pair,*_=transport
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+fixture[1]}) as rest:
            row=await page(rest); ref=target(row)
            data=mutation({'confidence':None,'verified_at':None,'extensions':{'unknown':None,'__proto__':{'preserved':True}}})
            saved=(await rest.put(path(ref),json=data)).json()
            assert saved['value']==data['value'] and saved['status']=='unknown'
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http)) as client:
                        result=await client.call_tool('knowledge_annotations_update',{**ref,'namespace':'verification','data':data})
                        assert not result.is_error and result.structured_content==saved
    asyncio.run(check())


def test_annotation_cookie_csrf_and_chunked_body_limits(annotation_http):
    from urllib.parse import parse_qs,urlsplit
    async def check():
        fixture, _, _=annotation_http
        app,token,*_=fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as http:
            login=await http.get('/auth/login');state=parse_qs(urlsplit(login.headers['location']).query)['state'][0]
            await http.get('/auth/callback',params={'state':state,'code':'owner-code'})
            csrf=(await http.get('/api/v1/me')).json()['csrf_token']
            http.headers.update({'Origin':ORIGIN,'X-C0-CSRF':csrf})
            row=await page(http); ref=target(row)
            data=mutation({'status':'verified'})
            for headers in ({},{'Origin':ORIGIN},{'X-C0-CSRF':csrf},
                            {'Origin':'https://untrusted.example.test','X-C0-CSRF':csrf}):
                http.headers.clear()
                assert (await http.put(path(ref),json=data,headers=headers)).status_code==403
            assert (await http.put(path(ref),json=data,headers={'Origin':ORIGIN,'X-C0-CSRF':csrf})).status_code==200
            http.headers['Authorization']='Bearer '+token
            async def oversized():
                for _ in range(1025):yield b' '*1024
            for method,url in (('PUT',path(ref)),('POST',SEARCH)):
                response=await http.request(method,url,content=oversized(),headers={'Content-Type':'application/json'})
                assert response.status_code==413 and response.json()=={'detail':'upload_too_large'}
    asyncio.run(check())


def test_ready_evidence_and_all_five_typed_categories_use_separate_annotations(annotation_http):
    async def check():
        fixture,spaces,_=annotation_http
        app,token,*_=fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            private=await create_space(http,spaces); params={'space_id':private['id']}
            marker='category'+uuid4().hex
            row=await page(http,private['id'],marker)
            entity=(await http.post('/api/v1/entities',params=params,json={
                'kind':'procedure','label':marker,'idempotency_key':uuid4().hex})).json()
            name='annotation-'+uuid4().hex
            response=await http.post('/api/v1/object-types',json={'name':name,'label':'Annotated records',
                'schema':{'type':'object','properties':{'name':{'type':'string','maxLength':128}},
                    'required':['name'],'additionalProperties':False},'unique_fields':['name']})
            assert response.status_code==201; spaces[2].append(name)
            record=(await http.post('/api/v1/objects',params=params,json={'type_name':name,'data':{'name':marker}})).json()
            response=await http.post('/api/v1/sources/ingest-text',params=params,json={
                'title':'HTTP Wiki evidence '+uuid4().hex,'body':marker+' original retained evidence',
                'media_type':'text/plain','idempotency_key':uuid4().hex})
            assert response.status_code==202; version=response.json(); version_ref=target(version,'source_version')
            denied=await http.put(path(version_ref),params=params,json=mutation({'status':'verified'}))
            assert denied.status_code==409 and denied.json()=={'detail':'evidence_not_ready'}
            applicable=mutation({'products':['NS8'],'components':['support'],'version_tags':['8.4']})
            assert (await http.put(path(version_ref,'applicability'),params=params,json=applicable)).status_code==200
            Worker(fixture[4],app.state.jobs.registry).tick()
            document=(await http.get('/api/v1/source-versions/'+version['id']+'/document',params=params)).json()
            chunks=(await http.get('/api/v1/documents/'+document['id']+'/chunks',params=params)).json()['chunks']
            citation=(await http.get('/api/v1/chunks/'+chunks[0]['id']+'/citation',params=params)).json()
            assertion=(await http.post('/api/v1/claims',params=params,json={'entity_id':entity['id'],
                'predicate':'observed','value':{'message':marker},'evidence_chunk_ids':[chunks[0]['id']],
                'idempotency_key':uuid4().hex})).json()
            targets=[target(row),version_ref,target(entity,'entity'),target(record,'object'),target(assertion,'claim')]
            for reference in targets:
                if reference != version_ref:
                    assert (await http.put(path(reference,'applicability'),params=params,
                        json=mutation(applicable['value']))).status_code==200
                response=await http.put(path(reference),params=params,json=mutation({'status':'verified'}))
                assert response.status_code==200
            result=await http.post(SEARCH,json={'query':marker,'space_id':private['id'],'mode':'text',
                'filters':{'categories':['source','wiki','entity','object','claim'],'version_tags':['8.4'],
                    'verification_statuses':['verified']}})
            assert result.status_code==200
            hits=result.json()['hits']; assert len(hits)==result.json()['candidate_count']==5
            assert {hit['reference']['id'] for hit in hits}=={reference['target_id'] for reference in targets}
            assert all(hit['reference']['space_id']==private['id'] and hit['retrieval_method']=='text' for hit in hits)
            assert next(hit for hit in hits if hit['category']=='source')['citation']==citation
            assert next(hit for hit in hits if hit['category']=='claim')['evidence_refs'][0]['chunk_id']==chunks[0]['id']
            for category in ('entity','object','claim'):
                hit=next(hit for hit in hits if hit['category']==category)
                assert hit['citation'] is hit['wiki'] is None and hit['start_offset'] is None
            assert (await http.get('/api/v1/source-versions/'+version['id']+'/document',params=params)).json()==document
            changed=(await http.put('/api/v1/entities/'+entity['id'],params=params,json={
                'label':marker+' updated','metadata':{},'expected_revision':1,'idempotency_key':uuid4().hex})).json()
            assert (await http.get(path(target(changed,'entity')),params=params)).json()['status']=='unknown'
            stale=await http.put(path(target(entity,'entity')),params=params,json=mutation({'status':'verified'},1))
            assert stale.status_code==409
    asyncio.run(check())



def test_all_accepted_am3_operation_contracts_remain_unchanged(annotation_http):
    app=annotation_http[0][0]
    baseline=json.loads((Path(__file__).parents[1]/'fixtures/agent_memory/am3_contract.json').read_text())
    assert len(baseline['operations'])==71
    for expected in baseline['operations']:
        actual=app.state.operations.definition(expected['name'])
        for key,value in expected.items():
            observed=actual[key]
            if key in ('input_schema','output_schema'):
                observed=hashlib.sha256(json.dumps(observed,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            assert observed==value,(expected['name'],key)
    schema=app.openapi()
    assert schema['paths'][SEARCH]['post']['x-c0-operation']=={
        'name':'knowledge_search_structured','minimum_role':'reader','required_scope':'c0:read','read_only':True}
    assert schema['paths']['/api/v1/knowledge/annotations/{kind}/{target_id}/{content_revision}/{namespace}']['put']['x-c0-operation']=={
        'name':'knowledge_annotations_update','minimum_role':'editor','required_scope':'c0:write','read_only':False}



@pytest.mark.parametrize('mode',['auto','legacy'])
def test_sdk_unready_verification_rolls_back_and_same_key_succeeds(annotation_http,mode):
    async def check():
        fixture, _, transport=annotation_http
        app,child,_,_,pair,*_=transport
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    version=(await client.call_tool('sources_ingest_text',{'data':{
                        'title':'HTTP Wiki evidence '+uuid4().hex,'body':'Queued observation',
                        'idempotency_key':uuid4().hex}})).structured_content
                    args={**target(version,'source_version'),'namespace':'verification','data':mutation({'status':'verified'})}
                    error(await client.call_tool('knowledge_annotations_update',args),'evidence_not_ready',409)
                    empty=(await client.call_tool('knowledge_annotations_get',{k:v for k,v in args.items() if k!='data'})).structured_content
                    assert empty['revision']==0 and empty['status']=='unknown'
                    Worker(fixture[4],app.state.jobs.registry).tick()
                    saved=await client.call_tool('knowledge_annotations_update',args)
                    assert not saved.is_error and saved.structured_content['revision']==1
                    assert (await client.call_tool('knowledge_annotations_update',args)).structured_content==saved.structured_content
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('operation',['knowledge_annotations_get','knowledge_search_structured'])
@pytest.mark.parametrize('failure',['value','database','private_http'])
def test_new_tool_private_errors_use_the_fixed_mapping(annotation_http,monkeypatch,mode,operation,failure,caplog):
    from fastapi import HTTPException
    from sqlalchemy.exc import SQLAlchemyError
    async def check():
        _,_,transport=annotation_http
        app,child,_,_,pair,*_=transport
        def fail(*args,**kwargs):
            if failure=='value':raise ValueError('PRIVATE')
            if failure=='database':raise SQLAlchemyError('PRIVATE')
            raise HTTPException(404,'PRIVATE')
        if operation=='knowledge_annotations_get':
            monkeypatch.setattr(app.state.annotations,'get',fail)
            args={'kind':'entity','target_id':str(uuid4()),'content_revision':1,'namespace':'verification'}
        else:
            monkeypatch.setattr(app.state.structured_search,'search',fail)
            args={'data':{'query':'PRIVATE'}}
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    result=await client.call_tool(operation,args)
                    expected=('invalid_knowledge_request',422) if failure=='value' else ('service_unavailable',503)
                    error(result,*expected)
                    assert 'PRIVATE' not in result.model_dump_json()
        assert 'PRIVATE' not in caplog.text
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_maximum_unicode_annotation_and_filters_have_rest_mcp_budget_parity(annotation_http,mode):
    async def check():
        fixture,_,transport=annotation_http
        app,child,_,_,pair,*_=transport
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+fixture[1]}) as rest:
            row=await page(rest);ref=target(row)
            data=mutation({'extensions':{'note':'é'*8000}})
            encoded=json.dumps(data).encode()
            assert 32768<len(encoded)<1048576
            response=await rest.put(path(ref),content=encoded,headers={'Content-Type':'application/json'})
            assert response.status_code==200
            values=['😀'*124+str(index) for index in range(32)]
            search={'query':'unicode','mode':'text','filters':{field:values for field in
                ('products','components','version_tags','statuses','verification_statuses')}}
            encoded=json.dumps(search).encode()
            assert 32768<len(encoded)<1048576
            found=await rest.post(SEARCH,content=encoded,headers={'Content-Type':'application/json'})
            assert found.status_code==200 and found.json()['hits']==[]
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        saved=await client.call_tool('knowledge_annotations_update',{**ref,'namespace':'verification','data':data})
                        assert not saved.is_error and saved.structured_content==response.json()
                        assert (await client.call_tool('knowledge_search_structured',{'data':search})).structured_content==found.json()
    asyncio.run(check())


def test_structured_search_rejects_unsupported_query_space_selectors(annotation_http):
    async def check():
        fixture,spaces,_=annotation_http
        app,token,*_=fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            private=await create_space(http,spaces)
            request={'query':'selector'+uuid4().hex,'mode':'text','rerank':'off'}
            for selector in ('not-a-uuid',private['id'],str(uuid4())):
                response=await http.post(SEARCH,params={'space_id':selector},json=request)
                assert response.status_code==422 and response.json()=={'detail':'invalid_space_request'}
                assert response.headers['cache-control']=='no-store'
            assert (await http.post(SEARCH,json={**request,'space_id':'not-a-uuid'})).status_code==422
            assert (await http.post(SEARCH,json={**request,'space_id':str(uuid4())})).status_code==403
            response=await http.post(SEARCH,json={**request,'space_id':private['id']})
            assert response.status_code==200 and response.json()['candidate_count']==0
    asyncio.run(check())
