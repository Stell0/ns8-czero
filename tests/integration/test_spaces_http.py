# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Space selectors exercise typed signed HTTP rather than mock Core services."""
import asyncio
import os
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def space_http(application):
    created, types = [], []
    yield application, created, types
    dispose_spaces(application[4],created,types)


def dispose_spaces(db, created, types=()):
    with db.engine.begin() as c:
        for identifier in created:
            for table in ('c0_content_tombstones','c0_original_cleanup','c0_annotation_targets','c0_evidence_links','c0_entity_links','c0_relations','c0_claims','c0_knowledge_receipts',
                          'c0_knowledge_events','c0_entity_aliases','c0_entities','c0_wiki_revisions','c0_wiki_pages',
                          'c0_chunks','c0_documents','c0_source_versions','c0_sources','c0_jobs','c0_object_relations',
                          'c0_object_keys','c0_objects','c0_object_events','c0_space_grants'):
                c.execute(text('DELETE FROM '+table+' WHERE space_id=:space'),{'space':UUID(identifier)})
            c.execute(text('DELETE FROM c0_spaces WHERE id=:id'),{'id':UUID(identifier)})
        for name in types:c.execute(text('DELETE FROM c0_object_types WHERE name=:name'),{'name':name})


async def create_space(client, fixture):
    response = await client.post('/api/v1/spaces',json={'name':'Investigation '+uuid4().hex,'idempotency_key':uuid4().hex})
    assert response.status_code == 201
    result = response.json(); fixture[1].append(result['id'])
    return result


def test_signed_space_discovery_wiki_names_replay_and_fail_closed_selectors(space_http, knowledge_http):
    async def check():
        app, owner, member, *_ = space_http[0]
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
            private = await create_space(client,space_http)
            second = await create_space(client,space_http)
            shared = next(s for s in (await client.get('/api/v1/spaces')).json()['spaces'] if s['shared'])
            assert private['role'] == 'admin' and shared['id'] != private['id']
            values = {'slug':'same-slug','title':'Private','body':'Private text','idempotency_key':'same-key'}
            a = await client.post('/api/v1/wiki/pages/upsert',params={'space_id':private['id']},json=values)
            b = await client.post('/api/v1/wiki/pages/upsert',params={'space_id':second['id']},json={**values,'body':'Other text'})
            assert a.status_code == b.status_code == 200 and a.json()['id'] != b.json()['id']
            assert (await client.get('/api/v1/wiki/pages/resolve',params={'slug':'same-slug'})).status_code == 404
            assert (await client.get('/api/v1/wiki/pages/resolve',params={'slug':'same-slug','space_id':private['id']})).json() == a.json()
            assert (await client.get('/api/v1/wiki/pages/'+a.json()['id'])).status_code == 404
            for selector, status in (('not-a-uuid',422),(str(uuid4()),403)):
                response = await client.get('/api/v1/wiki/pages',params={'space_id':selector})
                assert response.status_code == status
            assert (await client.get('/api/v1/knowledge/search',params={'query':'Private','space_id':private['id']})).json()['hits'][0]['resource_id'] == a.json()['id']
            assert (await client.get('/api/v1/knowledge/search',params={'query':'Private'})).json()['hits'] == []
            assert (await client.get('/api/v1/me',params={'space_id':private['id']})).json()['role'] == 'admin'
            for path in ('wiki/pages','knowledge/search?query=Private','me'):
                separator = '&' if '?' in path else '?'
                duplicate = await client.get('/api/v1/'+path+separator+'space_id='+private['id']+'&space_id='+private['id'])
                assert duplicate.status_code == 422 and duplicate.json() == {'detail':'invalid_space_request'}
                assert duplicate.headers['cache-control'] == 'no-store'
    asyncio.run(check())


def test_grants_revision_replay_current_role_cap_and_cookie_csrf(space_http, knowledge_http):
    from urllib.parse import parse_qs, urlsplit
    async def check():
        app, owner, member, *_ = space_http[0]
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
            private = await create_space(client,space_http)
            path = '/api/v1/spaces/'+private['id']
            page = (await client.post('/api/v1/wiki/pages/upsert',params={'space_id':private['id']},json={'slug':'grant-page','title':'Private','body':'Retained','idempotency_key':'page'})).json()
            client.headers['Authorization'] = 'Bearer '+member
            assert (await client.get('/api/v1/me')).status_code == 403
            client.headers['Authorization'] = 'Bearer '+owner
            account = next(a for a in (await client.get('/api/v1/access/accounts')).json()['accounts'] if a['username']=='member')
            assert (await client.put('/api/v1/access/accounts/'+account['id'],json={'role':'editor'})).status_code == 204
            grant_path = path+'/grants/'+account['id']
            client.headers['Authorization'] = 'Bearer '+member
            assert (await client.get(path)).status_code == 403
            assert all(s['id'] != private['id'] for s in (await client.get('/api/v1/spaces')).json()['spaces'])
            client.headers['Authorization'] = 'Bearer '+owner
            grant = {'role':'reader','expected_revision':0,'idempotency_key':'initial-grant'}
            first = await client.put(grant_path,json=grant)
            assert first.status_code == 200 and first.json()['revision'] == 1
            assert (await client.put(grant_path,json={**grant,'idempotency_key':'stale'})).status_code == 409
            client.headers['Authorization'] = 'Bearer '+member
            me = (await client.get('/api/v1/me',params={'space_id':private['id']})).json()
            assert me['role']=='reader' and me['application_role']=='editor'
            assert (await client.get('/api/v1/wiki/pages/'+page['id'],params={'space_id':private['id']})).status_code == 200
            assert (await client.post('/api/v1/wiki/pages/upsert',params={'space_id':private['id']},json={'slug':'denied','title':'Denied','body':'Denied','idempotency_key':'denied'})).status_code == 403
            assert (await client.get(path+'/grants')).status_code == 403
            client.headers['Authorization'] = 'Bearer '+owner
            assert (await client.put(grant_path,json={'role':None,'expected_revision':1,'idempotency_key':'revoke'})).json()['revision']==2
            assert (await client.put(grant_path,json=grant)).json() == first.json()
            client.headers['Authorization'] = 'Bearer '+member
            assert (await client.get('/api/v1/me',params={'space_id':private['id']})).status_code == 403
            client.headers['Authorization'] = 'Bearer '+owner
            assert (await client.put(grant_path,json={'role':'editor','expected_revision':2,'idempotency_key':'regrant'})).json()['revision']==3
            assert (await client.put('/api/v1/access/accounts/'+account['id'],json={'role':'reader'})).status_code == 204
            client.headers['Authorization'] = 'Bearer '+member
            assert (await client.get('/api/v1/me',params={'space_id':private['id']})).json()['role']=='reader'
            client.headers.pop('Authorization')
            login=await client.get('/auth/login'); state=parse_qs(urlsplit(login.headers['location']).query)['state'][0]
            assert (await client.get('/auth/callback',params={'code':'owner-code','state':state})).status_code==302
            csrf=(await client.get('/api/v1/me')).json()['csrf_token']
            request={'name':'Cookie space '+uuid4().hex,'idempotency_key':'cookie-space'}
            for headers in ({},{'Origin':ORIGIN},{'X-C0-CSRF':csrf},{'Origin':'https://elsewhere.example.test','X-C0-CSRF':csrf}):
                assert (await client.post('/api/v1/spaces',json=request,headers=headers)).status_code == 403
            response=await client.post('/api/v1/spaces',json=request,headers={'Origin':ORIGIN,'X-C0-CSRF':csrf})
            assert response.status_code == 201;space_http[1].append(response.json()['id'])
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_current_and_legacy_sdk_spaces_evidence_resources_and_denial_order(space_http, knowledge_http, transport, mode):
    import json
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared.exceptions import MCPError
    from czero_core.identity import PermissionDenied, Role
    from czero_core.worker import Worker
    from test_mcp_http import RESOURCE
    async def check():
        app, child, _, _, owner_pair, issue, owner_token, member_token = transport
        access = app.state.auth.access
        owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        member_identity = app.state.auth.oidc.verify_access_token(member_token)
        with pytest.raises(PermissionDenied):access.resolve(member_identity)
        account=next(a for a in access.list_accounts(owner) if a['username']=='member')
        access.set_role(owner,account['id'],Role.EDITOR)
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner_token}) as rest:
            private = await create_space(rest,space_http); identifier=private['id']
            await rest.put('/api/v1/spaces/'+identifier+'/grants/'+str(account['id']),json={'role':'reader','expected_revision':0,'idempotency_key':'reader-grant'})
            member_pair=issue(member_identity,{'c0:read'})
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner_pair.access_token}) as owner_http, httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+member_pair.access_token}) as member_http:
                    async with Client(streamable_http_client(RESOURCE,http_client=owner_http),mode=mode) as admin, Client(streamable_http_client(RESOURCE,http_client=member_http),mode=mode) as reader:
                        import importlib.util
                        from pathlib import Path
                        spec=importlib.util.spec_from_file_location('native_protected_sdk',Path(__file__).parents[1]/'mcp_tls_probe.py')
                        probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
                        before_spaces={s['id'] for s in (await owner_http.get('/api/v1/spaces')).json()['spaces']}
                        before_types={t['name'] for t in (await owner_http.get('/api/v1/object-types')).json()['types']}
                        async def wake_worker(request):
                            poll=request.method=='GET' and request.url.path.endswith('/versions')
                            if request.method=='POST' and request.url.path.endswith('/mcp'):
                                message=json.loads(request.content)
                                poll=message.get('method')=='tools/call' and message.get('params',{}).get('name')=='source_versions_list'
                            if poll:
                                Worker(knowledge_http[4],app.state.jobs.registry).tick()
                        owner_http.event_hooks['request'].append(wake_worker)
                        try:
                            state=await probe.protected_spaces(admin,owner_http)
                            assert (await probe.protected_spaces(admin,owner_http,state))==state
                        finally:
                            owner_http.event_hooks['request'].remove(wake_worker)
                            after_spaces={s['id'] for s in (await owner_http.get('/api/v1/spaces')).json()['spaces']}
                            after_types={t['name'] for t in (await owner_http.get('/api/v1/object-types')).json()['types']}
                            space_http[1].extend(after_spaces-before_spaces)
                            space_http[2].extend(after_types-before_types)
                        listed=await admin.call_tool('spaces_list',{})
                        assert not listed.is_error and identifier in {s['id'] for s in listed.structured_content['spaces']}
                        page_values={'data':{'slug':'sdk-private','title':'Private procedure','body':'Private content','idempotency_key':'same-key'},'space_id':identifier}
                        page_result=await admin.call_tool('wiki_pages_upsert',page_values)
                        assert not page_result.is_error;page=page_result.structured_content
                        denied=await reader.call_tool('wiki_pages_upsert',{**page_values,'data':{**page_values['data'],'slug':'denied'}})
                        assert denied.is_error and denied.content[0].text=='permission_denied'
                        assert 'mcp/www_authenticate' not in (denied.meta or {})
                        narrow_owner=issue(app.state.auth.oidc.verify_access_token(owner_token),{'c0:read'})
                        # A role-eligible Admin lacking write scope gets a real
                        # challenge for an accessible space, rather than denial.
                        member_http.headers['Authorization']='Bearer '+narrow_owner.access_token
                    async with Client(streamable_http_client(RESOURCE,http_client=member_http),mode=mode) as narrow:
                        challenged=await narrow.call_tool('wiki_pages_upsert',page_values)
                        assert challenged.is_error and challenged.content[0].text=='insufficient_scope'
                        assert 'scope="c0:write"' in challenged.meta['mcp/www_authenticate'][0]
                    async with Client(streamable_http_client(RESOURCE,http_client=owner_http),mode=mode) as admin:
                        qualified='c0://spaces/'+identifier+'/wiki/pages/'+page['id']
                        assert json.loads((await admin.read_resource(qualified)).contents[0].text)==page
                        with pytest.raises(MCPError,match='invalid_resource_request'):await admin.read_resource('c0://wiki/pages/'+page['id'])
                        templates=[str(t.uri_template) for t in (await admin.list_resource_templates()).resource_templates]
                        assert 'c0://spaces/{space_id}/wiki/pages/{page_id}' in templates
                        request={'space_id':identifier,'data':{'title':'HTTP Wiki evidence '+uuid4().hex,'body':'Immutable private SDK evidence','idempotency_key':'sdk-text'}}
                        submitted=await admin.call_tool('sources_ingest_text',request)
                        assert not submitted.is_error;version=submitted.structured_content
                        Worker(space_http[0][4],app.state.jobs.registry).tick()
                        document=(await admin.call_tool('documents_get',{'version_id':version['id'],'space_id':identifier})).structured_content
                        chunk=(await admin.call_tool('document_chunks_list',{'document_id':document['id'],'space_id':identifier})).structured_content['chunks'][0]
                        citation=(await admin.call_tool('citations_get',{'chunk_id':chunk['id'],'space_id':identifier})).structured_content
                        assert citation['body']=='Immutable private SDK evidence'
                        result=await admin.call_tool('citations_get',{'chunk_id':chunk['id']})
                        assert result.is_error
                        replay=await admin.call_tool('sources_ingest_text',request)
                        assert replay.structured_content==version and replay.structured_content['state']=='queued'
                        assert json.loads((await admin.read_resource('c0://spaces/'+identifier+'/source-versions/'+version['id'])).contents[0].text)==document
                        grant_path='/api/v1/spaces/'+identifier+'/grants/'+str(account['id'])
                        assert (await rest.put(grant_path,json={'role':None,'expected_revision':1,'idempotency_key':'revoke'})).status_code==200
                        assert (await rest.put(grant_path,json={'role':'reader','expected_revision':2,'idempotency_key':'regrant'})).status_code==200
                        stale=await rest.get('/api/v1/wiki/pages/'+page['id'],params={'space_id':identifier},headers={'Authorization':'Bearer '+member_pair.access_token})
                        assert stale.status_code==401
                        conflict=await admin.call_tool('spaces_create',{'data':{'name':private['name'],'idempotency_key':'different'}})
                        assert conflict.is_error and conflict.content[0].text=='space_conflict' and conflict.meta['c0/error']['status']==409
    asyncio.run(check())


def test_typed_content_selectors_cover_originals_history_graph_objects_and_feeds(space_http, knowledge_http):
    from czero_core.worker import Worker
    async def check():
        app, owner, *_ = space_http[0]
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
            private=await create_space(client,space_http); selected={'space_id':private['id']}
            other=await create_space(client,space_http)
            schema={'type':'object','properties':{'name':{'type':'string','maxLength':64},'space_id':{'type':'string','maxLength':64}},'required':['name']}
            type_name='space-http-'+uuid4().hex;space_http[2].append(type_name)
            assert (await client.post('/api/v1/object-types',json={'name':type_name,'label':'Shared schema','schema':schema,'unique_fields':['name']})).status_code==201
            assert (await client.get('/api/v1/object-types/'+type_name)).status_code==200
            record=(await client.post('/api/v1/objects',params=selected,json={'type_name':type_name,'data':{'name':'Private','space_id':'user payload'}})).json()
            assert record['data']['space_id']=='user payload'
            duplicate=await client.post('/api/v1/objects',params={'space_id':other['id']},json={'type_name':type_name,'data':{'name':'Private'}})
            assert duplicate.status_code==201 and duplicate.json()['id']!=record['id']
            page=(await client.post('/api/v1/wiki/pages/upsert',params=selected,json={'slug':'negative-paths','title':'Private article','body':'Retained private article','idempotency_key':'page'})).json()
            entity=(await client.post('/api/v1/entities',params=selected,json={'kind':'investigation','label':'Private root','idempotency_key':'entity'})).json()
            other_entity=(await client.post('/api/v1/entities',params=selected,json={'kind':'investigation','label':'Private leaf','idempotency_key':'other-entity'})).json()
            relation=await client.post('/api/v1/knowledge/relations',params=selected,json={'source_id':entity['id'],'target_id':other_entity['id'],'kind':'related','idempotency_key':'relation'})
            assert relation.status_code==201
            fields={'title':'HTTP Wiki evidence '+uuid4().hex,'media_type':'text/plain','retain_original':'true'}
            upload=await client.post('/api/v1/sources/upload',params=selected,data=fields,files={'file':('proof.txt',b'Private HTTP evidence')})
            assert upload.status_code==202;version=upload.json()
            Worker(space_http[0][4],app.state.jobs.registry).tick()
            document=(await client.get('/api/v1/source-versions/'+version['id']+'/document',params=selected)).json()
            chunk=(await client.get('/api/v1/documents/'+document['id']+'/chunks',params=selected)).json()['chunks'][0]
            claim=await client.post('/api/v1/claims',params=selected,json={'entity_id':entity['id'],'page_id':page['id'],'predicate':'observed','value':{'unknown':True},'evidence_chunk_ids':[chunk['id']],'idempotency_key':'claim'})
            assert claim.status_code==201;claim=claim.json()
            for kind,identifier in (('object',record['id']),('page',page['id']),('source',version['source_id']),('document',document['id']),('chunk',chunk['id'])):
                response=await client.post('/api/v1/entities/'+entity['id']+'/references',params=selected,json={'target_kind':kind,'target_id':identifier,'idempotency_key':'link-'+kind})
                assert response.status_code==201
                assert (await client.get('/api/v1/references/'+kind+'/'+identifier,params={**selected,'type_name':type_name if kind=='object' else kind})).status_code==200
                assert (await client.get('/api/v1/references/'+kind+'/'+identifier,params={'type_name':type_name if kind=='object' else kind})).status_code==404
            paths=[
                '/api/v1/wiki/pages/'+page['id'], '/api/v1/wiki/pages/'+page['id']+'/revisions',
                '/api/v1/wiki/pages/'+page['id']+'/export', '/api/v1/entities/'+entity['id'],
                '/api/v1/entities/'+entity['id']+'/relations','/api/v1/entities/'+entity['id']+'/references',
                '/api/v1/knowledge/graph/'+entity['id'],'/api/v1/claims/'+claim['id'],
                '/api/v1/objects/'+record['id'],'/api/v1/objects/'+record['id']+'/relations',
                '/api/v1/sources/'+version['source_id'],'/api/v1/sources/'+version['source_id']+'/versions',
                '/api/v1/source-versions/'+version['id']+'/document','/api/v1/source-versions/'+version['id']+'/original',
                '/api/v1/chunks/'+chunk['id']+'/citation']
            for path in paths:
                assert (await client.get(path,params=selected)).status_code==200,path
                assert (await client.get(path)).status_code==404,path
                assert (await client.get(path,params={'space_id':other['id']})).status_code==404,path
            assert (await client.get('/api/v1/documents/'+document['id']+'/chunks')).json()['chunks']==[]
            assert (await client.get('/api/v1/entities/resolve',params={'alias':'Private root'})).status_code==404
            assert (await client.get('/api/v1/entities/resolve',params={**selected,'alias':'Private root'})).json()['id']==entity['id']
            assert (await client.get('/api/v1/objects',params={'type_name':type_name})).json()['objects']==[]
            assert (await client.get('/api/v1/sources/search',params={'query':'Private'})).json()['citations']==[]
            assert (await client.get('/api/v1/claims')).json()['claims']==[]
            assert (await client.get('/api/v1/object-events')).json()['events']==[]
            assert (await client.get('/api/v1/knowledge/changes')).json()['changes']==[]
    asyncio.run(check())


def test_exact_native_protected_seed_and_recovery_contract_over_signed_http(space_http, knowledge_http):
    import importlib.util
    from pathlib import Path
    from fastapi.testclient import TestClient
    from czero_core.worker import Worker
    spec=importlib.util.spec_from_file_location('native_spaces_probe',Path(__file__).parents[1]/'oidc_probe.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    app,owner,member,*_=space_http[0]
    with TestClient(app,base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
        class Browser:
            def api(self,path,data=None,method=None,csrf=None):
                if '/versions' in path: Worker(space_http[0][4],app.state.jobs.registry).tick()
                response=client.request(method or 'GET',path,json=data)
                if path=='/api/v1/spaces' and method=='POST' and response.status_code==201:
                    space_http[1].append(response.json()['id'])
                return response.status_code,response.content,str(response.url)
            def upload(self,profile,content,*,filename,title,media_type,retain_original,space_id):
                response=client.post('/api/v1/sources/upload',params={'space_id':space_id},
                    data={'title':title,'media_type':media_type,'retain_original':'true' if retain_original else 'false'},
                    files={'file':(filename,content)})
                return response.status_code,response.content,str(response.url)
        browser=Browser();profile={'csrf_token':None}
        client.get('/api/v1/me',headers={'Authorization':'Bearer '+member})
        account=next(a for a in client.get('/api/v1/access/accounts').json()['accounts'] if a['username']=='member')
        assert client.put('/api/v1/access/accounts/'+account['id'],json={'role':'editor'}).status_code==204
        if client.get('/api/v1/object-types/fixture-inventory').status_code==404:
            probe.object_fixtures(browser,profile);space_http[2].extend(['fixture-inventory','fixture-projects'])
        expected=probe.seed_protected_space(browser,profile,account['id'])
        probe.verify_protected_space(browser,profile,expected,admin=True)
        # Independent signed Reader requests must resolve the same retained
        # identities while their current space grant caps application authority.
        client.headers['Authorization']='Bearer '+member
        probe.verify_protected_space(browser,profile,expected)
