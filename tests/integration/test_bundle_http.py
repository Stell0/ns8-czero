# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed REST and actual SDK clients publish one revision-safe consolidation."""
import asyncio
import json
import os
from uuid import uuid4

import httpx2
from httpx import ASGITransport, AsyncClient, ReadError
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text
from czero_core.identity import Role
from czero_core.worker import Worker

from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_spaces_http import space_http, create_space
from test_mcp_http import transport, RESOURCE
from test_wiki_memory_http import error, owner_and_member

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
ENDPOINT = '/api/v1/knowledge/bundles/apply'


@pytest.fixture
def bundle_http(knowledge_http, space_http, transport):
    yield knowledge_http, space_http, transport
    app = knowledge_http[0]
    # Claims may point at bundle-created pages; dispose child references before
    # the common SDK fixture disposes its actor-owned pages and client.
    with app.state.auth.access.database.engine.begin() as connection:
        actors = {'issuer':app.state.auth.access.issuer}
        connection.execute(text('DELETE FROM c0_annotation_targets WHERE created_by IN (SELECT id FROM c0_accounts WHERE issuer=:issuer)'),actors)
        connection.execute(text('DELETE FROM c0_evidence_links WHERE claim_id IN (SELECT id FROM c0_claims WHERE actor_id IN (SELECT id FROM c0_accounts WHERE issuer=:issuer))'),actors)
        for table in ('c0_claims','c0_entity_links','c0_relations'):
            connection.execute(text('DELETE FROM '+table+' WHERE actor_id IN (SELECT id FROM c0_accounts WHERE issuer=:issuer)'),actors)


def step(operation, **arguments):
    return {'operation':operation,'arguments':arguments}


def reference(index, path='id'):
    return {'$result':index,'path':path}


def request(space_id=None):
    return {'space_id':space_id,'idempotency_key':uuid4().hex,'operations':[
        step('wiki.upsert',slug='consolidation/'+uuid4().hex,title='Procedure',body='Exact retained procedure'),
        step('entity.create',kind='procedure',label='Procedure '+uuid4().hex),
        step('annotation.update',target={'kind':'wiki_revision','id':reference(0,'content.id'),'revision':reference(0,'content.number')},
            namespace='applicability',value={'knowledge_type':'procedure','status':'applicable','confidence':None,
                'version_tags':['0.44'],'supersedes':[]},expected_revision=0)]}


def test_signed_rest_bundle_typed_references_whole_replay_and_rollback(bundle_http):
    async def check():
        fixture, spaces, _ = bundle_http
        app, owner, *_ = fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner}) as http:
            private = await create_space(http,spaces)
            data = request(private['id'])
            response = await http.post(ENDPOINT,json=data)
            assert response.status_code == 200
            original = response.json()
            assert original['space_id'] == private['id'] and len(original['results']) == 3
            assert original['results'][2]['target']['id'] == original['results'][0]['content']['id']
            assert original['results'][2]['value']['confidence'] is None
            assert original['results'][2]['value']['knowledge_type'] == 'procedure'
            assert (await http.post(ENDPOINT,json=data)).json() == original
            page = original['results'][0]
            updated = await http.post('/api/v1/wiki/pages/upsert',params={'space_id':private['id']},json={
                'slug':page['slug'],'title':'Later','body':'Later content','expected_revision':1,'idempotency_key':uuid4().hex})
            assert updated.status_code == 200
            assert (await http.post(ENDPOINT,json=data)).json() == original
            failed = request(private['id'])
            failed['operations'].append(step('wiki.upsert',slug=page['slug'],title='Stale',body='Stale',expected_revision=1))
            result = await http.post(ENDPOINT,json=failed)
            assert result.status_code == 409 and result.json() == {'detail':'knowledge_conflict'}
            missing = await http.get('/api/v1/wiki/pages/resolve',params={'space_id':private['id'],'slug':failed['operations'][0]['arguments']['slug']})
            assert missing.status_code == 404
            # Only the typed body can choose a space; query selectors cannot
            # silently select Shared or override the protected selector.
            assert (await http.post(ENDPOINT,params={'space_id':private['id']},json=data)).status_code == 422
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_actual_sdk_bundle_matches_rest_and_returns_safe_stale_conflict(bundle_http, mode):
    async def check():
        fixture, spaces, delegated = bundle_http
        app, child, _, _, pair, *_ = delegated
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+fixture[1]}) as rest:
            private = await create_space(rest,spaces)
            data = request(private['id'])
            wire = []
            async def observe(response):
                await response.aread()
                if response.content:
                    wire.append(json.loads(response.content))
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token},event_hooks={'response':[observe]}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        tools = (await client.list_tools()).tools
                        assert len(tools) == 77
                        tool = next(value for value in tools if value.name=='knowledge_bundle_apply')
                        assert not tool.annotations.read_only_hint
                        assert tool.meta['securitySchemes'][0]['scopes'] == ['c0:write']
                        response = await client.call_tool('knowledge_bundle_apply',{'data':data})
                        assert not response.is_error
                        original = json.loads(response.content[0].text)
                        assert original['space_id'] == private['id'] and len(original['results']) == 3
                        assert (await rest.post(ENDPOINT,json=data)).json() == original
                        assert json.loads((await client.call_tool('knowledge_bundle_apply',{'data':data})).content[0].text) == original
                        stale = {**data,'idempotency_key':uuid4().hex}
                        failure = await client.call_tool('knowledge_bundle_apply',{'data':stale})
                        error(failure,'knowledge_conflict',409)
                        raw_tool = next(tool for message in wire for tool in message.get('result',{}).get('tools',[])
                            if tool['name']=='knowledge_bundle_apply')
                        assert raw_tool['securitySchemes'] == raw_tool['_meta']['securitySchemes'] == [{'type':'oauth2','scopes':['c0:write']}]
                        assert any(message.get('result',{}).get('structuredContent') == original for message in wire)
                        raw_error = next(message['result'] for message in wire if message.get('result',{}).get('isError'))
                        assert raw_error['_meta']['c0/error'] == {'code':'knowledge_conflict','status':409}
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('role',list(Role))
def test_bundle_role_grant_scope_matrix_and_revoked_receipt_cannot_revive(bundle_http, mode, role):
    async def check():
        fixture, spaces, delegated = bundle_http
        app, child, _, _, _, _, owner_token, _ = delegated
        owner, identity, issue = owner_and_member(delegated,role)
        member = app.state.auth.access.resolve(identity)
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner_token}) as rest:
            private = await create_space(rest,spaces)
            data = request(private['id'])
            pair = issue(identity,{'c0:read'})
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        denied = await client.call_tool('knowledge_bundle_apply',{'data':data})
                        if role is not Role.ADMIN:
                            error(denied,'permission_denied',403)
                            assert 'mcp/www_authenticate' not in denied.meta
                        else:
                            error(denied,'insufficient_scope',403)
                        grant = app.state.spaces.set_grant(owner,private['id'],member.user_id,
                            Role.READER if role is Role.READER else Role.EDITOR,expected_revision=0,idempotency_key=uuid4().hex)
                        # Policy changes invalidate the earlier real token.
                        fresh = issue(identity,{'c0:read'})
                        http.headers['Authorization']='Bearer '+fresh.access_token
                        denied = await client.call_tool('knowledge_bundle_apply',{'data':data})
                        if role is Role.READER:
                            error(denied,'permission_denied',403)
                            assert 'mcp/www_authenticate' not in denied.meta
                        else:
                            error(denied,'insufficient_scope',403)
                            assert 'scope="c0:write"' in denied.meta['mcp/www_authenticate'][0]
                            narrow = issue(identity,{'c0:write'})
                            http.headers['Authorization']='Bearer '+narrow.access_token
                            saved = await client.call_tool('knowledge_bundle_apply',{'data':data})
                            assert not saved.is_error
                            assert json.loads(saved.content[0].text)['space_id'] == private['id']
                        if role is not Role.ADMIN:
                            app.state.spaces.set_grant(owner,private['id'],member.user_id,None,
                                expected_revision=grant['revision'],idempotency_key=uuid4().hex)
                            raw = {'jsonrpc':'2.0','id':42,'method':'tools/call','params':{'name':'knowledge_bundle_apply','arguments':{'data':data}}}
                            assert (await http.post('/mcp',json=raw)).status_code == 401
                            app.state.spaces.set_grant(owner,private['id'],member.user_id,
                                Role.READER if role is Role.READER else Role.EDITOR,expected_revision=2,idempotency_key=uuid4().hex)
                            assert (await http.post('/mcp',json=raw)).status_code == 401
                            restored = issue(identity,{'c0:read'} if role is Role.READER else {'c0:write'})
                            http.headers['Authorization']='Bearer '+restored.access_token
                            result = await client.call_tool('knowledge_bundle_apply',{'data':data})
                            if role is Role.READER:
                                error(result,'permission_denied',403)
                            else:
                                assert not result.is_error and json.loads(result.content[0].text) == json.loads(saved.content[0].text)
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('failure',['value','database','private_http'])
def test_bundle_private_errors_use_only_the_fixed_mapping(bundle_http,monkeypatch,caplog,mode,failure):
    from fastapi import HTTPException
    from sqlalchemy.exc import SQLAlchemyError
    async def check():
        _, _, delegated = bundle_http
        app, child, _, _, pair, *_ = delegated
        def fail(*args,**kwargs):
            if failure=='value':raise ValueError('PRIVATE-BUNDLE')
            if failure=='database':raise SQLAlchemyError('PRIVATE-BUNDLE')
            raise HTTPException(404,'PRIVATE-BUNDLE')
        monkeypatch.setattr(app.state.bundles,'apply',fail)
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                    result = await client.call_tool('knowledge_bundle_apply',{'data':request()})
                    expected = ('invalid_knowledge_request',422) if failure=='value' else ('service_unavailable',503)
                    error(result,*expected)
                    assert 'PRIVATE-BUNDLE' not in result.model_dump_json()
        assert 'PRIVATE-BUNDLE' not in caplog.text
    asyncio.run(check())


@pytest.mark.parametrize('change',[
    {'operations':[]},{'operations':[step('jobs.enqueue',kind='PRIVATE-BUNDLE')]},
    {'operations':[step('wiki.upsert',slug='private',title='Private',body='Private',space_id=str(uuid4()))]},
    {'operations':[step('wiki.upsert',slug='private',title='Private',body='Private',expected_revision=True)]},
    {'operations':[step('entity.create',kind='procedure',label='PRIVATE-BUNDLE',idempotency_key='subkey')]},
    {'operations':[step('entity.create',kind='procedure',label=reference(0))]},
    {'operations':[step('wiki.upsert',slug='private',title='Private',body='x'*262144)]},
    {'operations':[step('entity.create',kind='procedure',label='x')]*26},
    {'space_id':'PRIVATE-BUNDLE'}, {'unexpected':'PRIVATE-BUNDLE'},
])
def test_bundle_invalid_input_budget_and_selector_are_bounded_and_private(bundle_http,change,caplog):
    async def check():
        fixture, _, _ = bundle_http
        app, owner, *_ = fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner}) as http:
            with caplog.at_level('DEBUG'):
                response = await http.post(ENDPOINT,json={**request(),**change})
            assert response.status_code == 422 and response.json() == {'detail':'invalid_knowledge_request'}
            assert response.headers['cache-control'] == 'no-store'
            assert (await http.get('/api/v1/wiki/pages')).json()['pages'] == []
        assert 'PRIVATE-BUNDLE' not in caplog.text
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_sourced_consolidation_supersession_and_unknown_new_content_through_sdk(bundle_http,mode):
    async def check():
        fixture, spaces, delegated = bundle_http
        app, child, _, _, pair, *_ = delegated
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+fixture[1]}) as rest:
            private = await create_space(rest,spaces); params={'space_id':private['id']}
            marker='bundlefixture'+uuid4().hex
            title='HTTP Wiki evidence '+uuid4().hex
            submitted = await rest.post('/api/v1/sources/ingest-text',params=params,json={
                'title':title,'body':'Retained evidence '+marker,'media_type':'text/markdown','idempotency_key':uuid4().hex})
            assert submitted.status_code == 202
            version = submitted.json()
            assert Worker(fixture[4],app.state.jobs.registry).tick(max_jobs=20,budget_seconds=10) >= 1
            document = (await rest.get('/api/v1/source-versions/'+version['id']+'/document',params=params)).json()
            chunk = (await rest.get('/api/v1/documents/'+document['id']+'/chunks',params=params)).json()['chunks'][0]
            source_reference={'kind':'chunk','id':chunk['id']}
            old = (await rest.post('/api/v1/wiki/pages/upsert',params=params,json={
                'slug':'prior/'+uuid4().hex,'title':'Prior','body':'Prior interpretation','idempotency_key':uuid4().hex})).json()
            old_path='/api/v1/knowledge/annotations/wiki_revision/'+old['content']['id']+'/1/verification'
            previous = await rest.put(old_path,params=params,json={
                'value':{'status':'verified','source_references':[source_reference]},'expected_revision':0,'idempotency_key':uuid4().hex})
            assert previous.status_code == 200
            type_name='bundle-'+uuid4().hex; spaces[2].append(type_name)
            created_type=await rest.post('/api/v1/object-types',json={'name':type_name,'label':'Bundle fixture',
                'schema':{'type':'object','properties':{'name':{'type':'string','maxLength':128}},'required':['name']}})
            assert created_type.status_code == 201
            applicability={'knowledge_type':'procedure','status':'applicable','products':['C0'],'version_tags':['0.44'],
                'observed_at':'2026-10-18T11:00:00+02:00','confidence':None,'source_references':[source_reference]}
            data={'space_id':private['id'],'idempotency_key':uuid4().hex,'operations':[
                step('entity.create',kind='procedure',label=marker),
                step('wiki.upsert',slug='sourced/'+uuid4().hex,title=marker,body='Consolidated '+marker),
                step('claim.create',entity_id=reference(0),page_id=reference(1),predicate='observed',value={'state':marker},evidence_chunk_ids=[chunk['id']]),
                step('object.create',type_name=type_name,data={'name':marker}),
                step('entity.link',entity_id=reference(0),target_kind='object',target_id=reference(3)),
                step('annotation.update',target={'kind':'wiki_revision','id':reference(1,'content.id'),'revision':1},
                    namespace='applicability',value={**applicability,'supersedes':[{'kind':'wiki_revision','id':old['content']['id'],'revision':1}]},expected_revision=0),
                step('annotation.update',target={'kind':'wiki_revision','id':reference(1,'content.id'),'revision':1},
                    namespace='verification',value={'status':'unverified','verified_at':None,'source_references':[source_reference]},expected_revision=0),
                step('annotation.update',target={'kind':'object','id':reference(3),'revision':1},namespace='applicability',value=applicability,expected_revision=0),
                step('annotation.update',target={'kind':'claim','id':reference(2),'revision':1},namespace='applicability',value=applicability,expected_revision=0)]}
            with fixture[4].engine.begin() as connection:
                connection.execute(text("UPDATE c0_source_versions SET state='failed' WHERE id=:id"),{'id':version['id']})
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        error(await client.call_tool('knowledge_bundle_apply',{'data':data}),'evidence_not_ready',409)
                        absent = await rest.get('/api/v1/wiki/pages/resolve',params={**params,'slug':data['operations'][1]['arguments']['slug']})
                        assert absent.status_code == 404
                        with fixture[4].engine.begin() as connection:
                            connection.execute(text("UPDATE c0_source_versions SET state='ready' WHERE id=:id"),{'id':version['id']})
                        saved = await client.call_tool('knowledge_bundle_apply',{'data':data})
                        assert not saved.is_error
                        original=json.loads(saved.content[0].text); rows=original['results']
                        assert len(rows)==9
                        assert rows[5]['value']['observed_at']=='2026-10-18T09:00:00+00:00'
                        assert rows[5]['value']['confidence'] is None
                        assert rows[6]['value']['verified_at'] is None
                        assert (await rest.get(old_path,params=params)).json() == previous.json()
                        assert (await rest.get('/api/v1/wiki/pages/'+old['id'],params=params)).json()['content'] == old['content']
                        citation=await client.call_tool('citations_get',{'chunk_id':chunk['id'],'space_id':private['id']})
                        assert not citation.is_error and json.loads(citation.content[0].text)['source_hash']==version['content_hash']
                        assert (await rest.get('/api/v1/chunks/'+chunk['id']+'/citation')).status_code==404
                        search=await client.call_tool('knowledge_search_structured',{'data':{
                            'query':marker,'space_id':private['id'],'mode':'text','rerank':'off',
                            'filters':{'categories':['wiki','object','claim'],'products':['C0'],'version_tags':['0.44']}}})
                        assert not search.is_error and {hit['category'] for hit in json.loads(search.content[0].text)['hits']}=={'wiki','object','claim'}
                        changed=await client.call_tool('wiki_pages_upsert',{'space_id':private['id'],'data':{
                            'slug':rows[1]['slug'],'title':marker,'body':'New observation','expected_revision':1,'idempotency_key':uuid4().hex}})
                        assert not changed.is_error
                        current=json.loads(changed.content[0].text)
                        unknown=await client.call_tool('knowledge_annotations_get',{'space_id':private['id'],'kind':'wiki_revision',
                            'target_id':current['content']['id'],'content_revision':2,'namespace':'verification'})
                        assert not unknown.is_error
                        assert json.loads(unknown.content[0].text)['status']=='unknown'
                        assert json.loads(unknown.content[0].text)['revision']==0
                        assert json.loads((await client.call_tool('knowledge_bundle_apply',{'data':data})).content[0].text)==original
                        assert (await rest.post(ENDPOINT,json=data)).json()==original
    asyncio.run(check())


def test_bundle_cookie_csrf_and_chunked_wire_limit(bundle_http):
    from urllib.parse import parse_qs,urlsplit
    async def check():
        fixture, _, _ = bundle_http
        app, token, *_ = fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as http:
            login=await http.get('/auth/login');state=parse_qs(urlsplit(login.headers['location']).query)['state'][0]
            await http.get('/auth/callback',params={'state':state,'code':'owner-code'})
            csrf=(await http.get('/api/v1/me')).json()['csrf_token']
            data=request()
            for headers in ({},{'Origin':ORIGIN},{'X-C0-CSRF':csrf},{'Origin':'https://untrusted.example.test','X-C0-CSRF':csrf}):
                assert (await http.post(ENDPOINT,json=data,headers=headers)).status_code==403
            assert (await http.post(ENDPOINT,json=data,headers={'Origin':ORIGIN,'X-C0-CSRF':csrf})).status_code==200
            async def oversized():
                for _ in range(1025):yield b' '*1024
            result=await http.post(ENDPOINT,content=oversized(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
            assert result.status_code==413 and result.json()=={'detail':'upload_too_large'}
    asyncio.run(check())


def test_lost_response_after_commit_is_recovered_by_an_independent_delegated_client(bundle_http):
    class LostReply(ASGITransport):
        async def handle_async_request(self,request):
            response=await super().handle_async_request(request)
            if request.url.path==ENDPOINT and response.status_code==200:
                await response.aclose()
                raise ReadError('injected lost reply after server commit',request=request)
            return response
    async def check():
        fixture, spaces, delegated = bundle_http
        app, child, _, _, pair, *_ = delegated
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+fixture[1]}) as rest:
            private=await create_space(rest,spaces)
            data=request(private['id'])
            async with AsyncClient(transport=LostReply(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+fixture[1]}) as first:
                with pytest.raises(ReadError,match='injected lost reply'):
                    await first.post(ENDPOINT,json=data)
            with fixture[4].engine.connect() as connection:
                stored=connection.execute(text('SELECT result FROM c0_knowledge_receipts WHERE space_id=:space AND key=:key'),
                    {'space':private['id'],'key':data['idempotency_key']}).scalar_one()
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http)) as second:
                        recovered=await second.call_tool('knowledge_bundle_apply',{'data':data})
                        assert not recovered.is_error
                        result=json.loads(recovered.content[0].text)
                        assert [row['id'] for row in result['results']]==[row['id'] for row in stored['results']]
                        assert (await rest.post(ENDPOINT,json=data)).json()==result
            with fixture[4].engine.connect() as connection:
                for table,count in (('c0_wiki_pages',1),('c0_entities',1),('c0_knowledge_events',3),('c0_knowledge_receipts',1)):
                    assert connection.execute(text('SELECT count(*) FROM '+table+' WHERE space_id=:space'),
                        {'space':private['id']}).scalar_one()==count
    asyncio.run(check())


def test_all_seventeen_typed_operations_retain_history_and_original_response_views(bundle_http):
    async def check():
        fixture, spaces, _ = bundle_http
        app, owner, *_ = fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner}) as http:
            private=await create_space(http,spaces);params={'space_id':private['id']}
            uploaded=await http.post('/api/v1/sources/ingest-text',params=params,json={
                'title':'HTTP Wiki evidence '+uuid4().hex,'body':'Retained type-complete observation','idempotency_key':uuid4().hex})
            assert uploaded.status_code==202
            version=uploaded.json();Worker(fixture[4],app.state.jobs.registry).tick()
            document=(await http.get('/api/v1/source-versions/'+version['id']+'/document',params=params)).json()
            chunk=(await http.get('/api/v1/documents/'+document['id']+'/chunks',params=params)).json()['chunks'][0]
            name='all-steps-'+uuid4().hex;spaces[2].append(name)
            assert (await http.post('/api/v1/object-types',json={'name':name,'label':'All step types',
                'schema':{'type':'object','properties':{'name':{'type':'string','maxLength':128}},'required':['name']}})).status_code==201
            operations=[
                step('object.create',type_name=name,data={'name':'original'}),
                step('entity.create',kind='procedure',label='First '+uuid4().hex),
                step('entity.create',kind='component',label='Second '+uuid4().hex),
                step('entity.alias',entity_id=reference(1),value='Alias '+uuid4().hex,expected_revision=1),
                step('entity.update',entity_id=reference(1),label='Updated '+uuid4().hex,expected_revision=2),
                step('relation.create',source_id=reference(1),target_id=reference(2),kind='uses'),
                step('relation.update',relation_id=reference(5),expected_revision=1,metadata={'retained':True},deleted=True),
                step('wiki.upsert',slug='all-steps/'+uuid4().hex,title='Retained',body='Retained authored observation'),
                step('claim.create',entity_id=reference(1),page_id=reference(7),predicate='observed',value={'state':'unknown'},
                    evidence_chunk_ids=[chunk['id']],valid_from='2026-10-18T11:00:00+02:00'),
                step('claim.update',claim_id=reference(8),expected_revision=1,metadata={'review':'retained'}),
                step('entity.link',entity_id=reference(1),target_kind='object',target_id=reference(0)),
                step('entity.unlink',entity_id=reference(1),link_id=reference(10)),
                step('object.update',object_id=reference(0),data={'name':'updated'},expected_revision=1),
                step('annotation.update',target={'kind':'object','id':reference(0),'revision':2},namespace='applicability',
                    value={'knowledge_type':'procedure','source_references':[{'kind':'chunk','id':chunk['id']}],
                        'supersedes':[{'kind':'wiki_revision','id':reference(7,'content.id'),'revision':1}]},expected_revision=0),
                step('claim.archive',claim_id=reference(8),expected_revision=2),
                step('wiki.archive',page_id=reference(7),expected_revision=1),
                step('entity.archive',entity_id=reference(2),expected_revision=1),
                step('object.delete',object_id=reference(0),expected_revision=2)]
            data={'space_id':private['id'],'operations':operations,'idempotency_key':uuid4().hex}
            response=await http.post(ENDPOINT,json=data)
            assert response.status_code==200
            original=response.json();rows=original['results']
            assert len(rows)==18 and rows[3]['revision']==2 and rows[4]['revision']==3
            assert rows[6]['deleted'] and rows[11]['deleted'] and rows[14]['deleted']
            assert rows[15]['deleted'] and 'content' not in rows[15]
            assert rows[16]['deleted'] and rows[17]=={'id':rows[0]['id'],'revision':2,'deleted':True}
            assert rows[8]['valid_from']=='2026-10-18T09:00:00Z'
            assert (await http.post(ENDPOINT,json=data)).json()==original
            retained=(await http.get('/api/v1/wiki/pages/'+rows[7]['id'],params={**params,'revision':1})).json()
            assert retained['content']==rows[7]['content']
            assertion=(await http.get('/api/v1/claims/'+rows[8]['id'],params=params)).json()
            assert assertion['deleted'] and assertion['value']=={'state':'unknown'}
            assert assertion['evidence'][0]['source_hash']==version['content_hash']
            annotation=(await http.get('/api/v1/knowledge/annotations/object/'+rows[0]['id']+'/2/applicability',params=params)).json()
            assert annotation['target_archived'] and annotation['value']==rows[13]['value']
    asyncio.run(check())
