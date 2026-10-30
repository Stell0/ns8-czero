# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text

from czero_core.worker import Worker
from test_auth_http import application, ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def knowledge_http(application, tmp_path):
    app, *_ = application; db = application[4]
    app.state.sources.originals.root = tmp_path / 'originals'
    with db.engine.begin() as c:
        schedules = [dict(row) for row in c.execute(text('SELECT id,enabled,next_run_at FROM c0_scheduled_tasks')).mappings()]
        c.execute(text('UPDATE c0_scheduled_tasks SET enabled=false'))
    yield application
    with db.engine.begin() as c:
        actors = c.execute(text('SELECT id FROM c0_accounts WHERE issuer=:issuer'), {'issuer': application[5]}).scalars().all()
        for actor in actors:
            c.execute(text('DELETE FROM c0_annotation_targets WHERE created_by=:id'), {'id': actor})
            # This fixture creates knowledge only through signed HTTP.
            c.execute(text('DELETE FROM c0_evidence_links WHERE claim_id IN (SELECT id FROM c0_claims WHERE actor_id=:id)'), {'id': actor})
            c.execute(text('DELETE FROM c0_claims WHERE actor_id=:id'), {'id': actor})
            c.execute(text('DELETE FROM c0_relations WHERE actor_id=:id'), {'id': actor})
            c.execute(text('DELETE FROM c0_entity_links WHERE actor_id=:id'), {'id': actor})
            c.execute(text('DELETE FROM c0_entity_aliases WHERE entity_id IN (SELECT resource_id FROM c0_knowledge_events WHERE actor_id=:id AND kind=\'entity\')'), {'id': actor})
            c.execute(text('DELETE FROM c0_entities WHERE id IN (SELECT resource_id FROM c0_knowledge_events WHERE actor_id=:id AND kind=\'entity\')'), {'id': actor})
            c.execute(text('DELETE FROM c0_wiki_revisions WHERE page_id IN (SELECT resource_id FROM c0_knowledge_events WHERE actor_id=:id AND kind=\'page\')'), {'id': actor})
            c.execute(text('DELETE FROM c0_wiki_pages WHERE id IN (SELECT resource_id FROM c0_knowledge_events WHERE actor_id=:id AND kind=\'page\')'), {'id': actor})
            c.execute(text('DELETE FROM c0_knowledge_events WHERE actor_id=:id'), {'id': actor})
            c.execute(text('DELETE FROM c0_knowledge_receipts WHERE actor_id=:id'), {'id': actor})
        source_ids = c.execute(text("SELECT id FROM c0_sources WHERE title LIKE 'HTTP Wiki evidence %'")).scalars().all()
        for key in source_ids:
            versions = c.execute(text('SELECT id FROM c0_source_versions WHERE source_id=:id'), {'id': key}).scalars().all()
            c.execute(text('DELETE FROM c0_chunks WHERE document_id IN (SELECT id FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id))'), {'id': key})
            c.execute(text('DELETE FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id)'), {'id': key})
            c.execute(text('DELETE FROM c0_source_versions WHERE source_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_sources WHERE id=:id'), {'id': key})
            for version in versions: c.execute(text("DELETE FROM c0_jobs WHERE payload->>'version_id'=:id"), {'id': str(version)})
        for row in schedules: c.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled,next_run_at=:next_run_at WHERE id=:id'), row)


def test_installed_performance_probe_through_real_signed_http(knowledge_http):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('installed_performance', Path(__file__).parents[1] / 'performance_probe.py')
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    async def check():
        app, owner, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                               headers={'Authorization': 'Bearer ' + owner}) as client:
            created = await client.post('/api/v1/wiki/pages', json={'slug': 'performance-' + uuid4().hex,
                'title': 'Independent authored benchmark', 'body': 'Independent authored first revision',
                'idempotency_key': 'performance-create'})
            assert created.status_code == 201
            updated = await client.put('/api/v1/wiki/pages/' + created.json()['id'], json={
                'title': 'Independent authored benchmark', 'body': 'Independent authored current revision',
                'expected_revision': 1, 'idempotency_key': 'performance-update'})
            assert updated.status_code == 200
            loop = asyncio.get_running_loop()
            def api(path):
                response = asyncio.run_coroutine_threadsafe(client.get(path), loop).result(timeout=15)
                return response.status_code, response.content, str(response.url)
            metrics = await asyncio.to_thread(probe.measure, SimpleNamespace(api=api), updated.json())
            assert metrics['health']['requests'] == 50
            assert metrics['wiki_text_search']['requests'] == 20
    asyncio.run(check())


def test_external_agent_rest_workflow_wiki_aliases_sourced_claims_graph_exports_and_changes(knowledge_http):
    async def check():
        app, owner, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get('/api/v1/wiki/pages')).status_code == 401
            client.headers['Authorization'] = 'Bearer ' + owner
            uploaded = await client.post('/api/v1/sources/upload', data={'title': 'HTTP Wiki evidence ' + uuid4().hex,
                'media_type': 'text/plain'}, files={'file': ('evidence.txt', b'Inventory evidence supports the system assertion')})
            assert uploaded.status_code == 202; version = uploaded.json()
            Worker(knowledge_http[4], app.state.jobs.registry).tick()
            document = (await client.get('/api/v1/source-versions/' + version['id'] + '/document')).json()
            chunk = (await client.get('/api/v1/documents/' + document['id'] + '/chunks')).json()['chunks'][0]
            data = {'slug': 'inventory-' + uuid4().hex, 'title': 'Inventory Wiki', 'body': '# Inventory\n\nAuthored claim café 東京 🔧', 'metadata': {'agent': 'external'}, 'idempotency_key': 'page'}
            response = await client.post('/api/v1/wiki/pages', json=data)
            assert response.status_code == 201; page_row = response.json(); path = '/api/v1/wiki/pages/' + page_row['id']
            assert (await client.post('/api/v1/wiki/pages', json=data)).json() == page_row
            assert (await client.post('/api/v1/wiki/pages', json={**data, 'body': 'changed'})).status_code == 409
            updated = await client.put(path, json={'title': 'Revised inventory', 'body': 'Revised authored claim', 'metadata': {}, 'expected_revision': 1, 'idempotency_key': 'update'})
            assert updated.status_code == 200 and updated.json()['revision'] == 2
            assert (await client.put(path, json={'title': 'Stale', 'body': 'Stale', 'expected_revision': 1, 'idempotency_key': 'stale'})).status_code == 409
            assert [r['number'] for r in (await client.get(path + '/revisions')).json()['revisions']]==[2]
            assert (await client.get(path, params={'revision': 1})).status_code==410
            exported = await client.get(path + '/export', params={'format': 'markdown', 'revision': 1})
            assert exported.status_code==410
            assert (await client.get(path + '/export')).json() == updated.json()
            entities = []
            for i in range(4):
                result = await client.post('/api/v1/entities', json={'kind': 'system', 'label': 'HTTP entity ' + str(i), 'aliases': ['HTTP alias ' + str(i)], 'idempotency_key': 'entity-' + str(i)})
                assert result.status_code == 201; entities.append(result.json())
            assert (await client.get('/api/v1/entities/resolve', params={'alias': 'ＨＴＴＰ ＡＬＩＡＳ ０'})).json()['id'] == entities[0]['id']
            for i in range(3):
                edge = await client.post('/api/v1/knowledge/relations', json={'source_id': entities[i]['id'], 'target_id': entities[i+1]['id'], 'kind': 'depends-on', 'idempotency_key': 'relation-' + str(i)})
                assert edge.status_code == 201
            for depth in (1, 2, 3):
                graph = await client.get('/api/v1/knowledge/graph/' + entities[0]['id'], params={'depth': depth, 'direction': 'out'})
                assert graph.status_code == 200 and len(graph.json()['nodes']) == depth + 1
            linked = await client.post('/api/v1/entities/' + entities[0]['id'] + '/references', json={'target_kind': 'page', 'target_id': page_row['id'], 'idempotency_key': 'page-link'})
            assert linked.status_code == 201
            claims = []
            for value in ('Linux', 'BSD'):
                claim = await client.post('/api/v1/claims', json={'entity_id': entities[0]['id'], 'page_id': page_row['id'], 'predicate': 'operating-system',
                    'value': {'name': value}, 'evidence_chunk_ids': [chunk['id']], 'valid_from': '2026-10-14T00:00:00Z', 'idempotency_key': 'claim-' + value})
                assert claim.status_code == 201; claims.append(claim.json())
            result = await client.get('/api/v1/claims', params={'entity_id': entities[0]['id']})
            assert len(result.json()['claims']) == 2
            citation = (await client.get('/api/v1/claims/' + claims[0]['id'])).json()['evidence'][0]
            assert citation['chunk_id'] == chunk['id'] and citation['source_hash'] == version['content_hash']
            for kind, key in [('page', page_row['id']), ('entity', entities[0]['id']), ('claim', claims[0]['id'])]:
                reference = await client.get('/api/v1/references/' + kind + '/' + key, params={'type_name': kind})
                assert reference.status_code == 200 and reference.json()['id'] == key
            assert (await client.put('/api/v1/claims/' + claims[0]['id'], json={'value': {'name': 'silently overwritten'}, 'metadata': {}, 'expected_revision': 1, 'idempotency_key': 'bad'})).status_code == 422
            events = (await client.get('/api/v1/knowledge/changes', params={'limit': 100})).json()['changes']
            assert any(e['kind'] == 'claim' for e in events)
            assert all(e['id'] > events[0]['id'] for e in (await client.get('/api/v1/knowledge/changes', params={'after': events[0]['id']})).json()['changes'])
            assert (await client.post(path + '/archive', json={'expected_revision': 2, 'idempotency_key': 'archive'})).json()['deleted']
            assert (await client.get(path, params={'revision': 1})).status_code == 410
            schema = (await client.get('/openapi.json')).json()
            assert schema['paths']['/api/v1/knowledge/graph/{entity_id}']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/GraphView')
    asyncio.run(check())


def test_wiki_reader_editor_revocation_cookie_csrf_and_unknown_operations(knowledge_http):
    async def check():
        app, owner, member, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/me')).status_code == 403
            client.headers['Authorization'] = 'Bearer ' + owner
            target = next(a['id'] for a in (await client.get('/api/v1/access/accounts')).json()['accounts'] if a['username'] == 'member')
            for role in ('reader','editor','admin'):
                await client.put('/api/v1/access/accounts/' + target, json={'role': role})
                client.headers['Authorization'] = 'Bearer ' + member
                assert (await client.get('/api/v1/wiki/pages')).status_code == 200
                created = await client.post('/api/v1/wiki/pages', json={'slug': role, 'title': role, 'body': role, 'idempotency_key': role})
                assert created.status_code == (403 if role == 'reader' else 201)
                assert (await client.post('/api/v1/entities', json={'kind': 'os.system', 'label': 'bad', 'idempotency_key': 'bad'})).status_code in (403, 422)
                client.headers['Authorization'] = 'Bearer ' + owner
            await client.put('/api/v1/access/accounts/' + target, json={'role': None})
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/wiki/pages')).status_code == 403
            client.headers.pop('Authorization')
            start = await client.get('/auth/login'); state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]
            assert (await client.get('/auth/callback', params={'state': state, 'code': 'fixture-only'})).status_code == 302
            profile = (await client.get('/api/v1/me')).json()
            data = {'slug': 'cookie', 'title': 'Cookie', 'body': 'Cookie', 'idempotency_key': 'cookie'}
            assert (await client.post('/api/v1/wiki/pages', json=data)).status_code == 403
            assert (await client.post('/api/v1/wiki/pages', json=data, headers={'X-C0-CSRF': profile['csrf_token'], 'Origin': 'https://wrong.example.test'})).status_code == 403
            assert (await client.post('/api/v1/wiki/pages', json=data, headers={'X-C0-CSRF': profile['csrf_token'], 'Origin': ORIGIN})).status_code == 201
            assert (await client.get('/api/v1/knowledge/graph/' + str(uuid4()), params={'depth': 4})).status_code == 422
    asyncio.run(check())


def test_knowledge_body_guard_rejects_oversized_chunked_json_before_parsing(knowledge_http):
    async def check():
        app, owner, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN, headers={'Authorization': 'Bearer ' + owner}) as client:
            async def large():
                yield b'{"body":"'
                for _ in range(17): yield b'x' * 65536
                yield b'"}'
            response = await client.post('/api/v1/wiki/pages', content=large(), headers={'Content-Type': 'application/json'})
            assert response.status_code == 413
            assert (await client.get('/api/v1/wiki/pages')).json()['pages'] == []
    asyncio.run(check())


def test_native_wiki_persistence_fixture_uses_actual_signed_rest(knowledge_http):
    """Exercise the exact QEMU seed/verifier locally before slow native runs."""
    import importlib.util
    from pathlib import Path
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location('native_oidc_probe', Path(__file__).parents[1] / 'oidc_probe.py')
    probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)
    app, owner, *_ = knowledge_http
    with TestClient(app, headers={'Authorization': 'Bearer ' + owner}) as client:
        class Browser:
            def api(self, path, data=None, method=None, csrf=None):
                response = client.request(method or 'GET', path, json=data)
                return response.status_code, response.content, str(response.url)
        upload = client.post('/api/v1/sources/upload', data={'title':'HTTP Wiki evidence ' + uuid4().hex, 'media_type':'text/plain'},
                             files={'file':('fixture.txt',b'Persistent source evidence')})
        assert upload.status_code == 202
        version = upload.json(); Worker(knowledge_http[4], app.state.jobs.registry).tick()
        document = client.get('/api/v1/source-versions/' + version['id'] + '/document').json()
        chunks = client.get('/api/v1/documents/' + document['id'] + '/chunks').json()['chunks']
        definition = {'name':'wiki-fixture-' + uuid4().hex,'label':'Wiki persistence','schema':{'type':'object','properties':{'name':{'type':'string'}},'required':['name']}}
        assert client.post('/api/v1/object-types',json=definition).status_code == 201
        record = client.post('/api/v1/objects',json={'type_name':definition['name'],'data':{'name':'Persistent record'}}).json()
        try:
            profile = {**client.get('/api/v1/me').json(), 'csrf_token': None}
            expected = probe.seed_knowledge(Browser(),profile,[{'version':version,'document':document,'chunks':chunks}],[record])
            probe.verify_knowledge(Browser(),profile,expected)
        finally:
            # Remove links before fixture-owned record cleanup.
            with knowledge_http[4].engine.begin() as c:
                c.execute(text('DELETE FROM c0_entity_links WHERE target_id=:id'),{'id':record['id']})
            client.delete('/api/v1/objects/' + record['id'] + '?expected_revision=1')
            with knowledge_http[4].engine.begin() as c:
                c.execute(text('DELETE FROM c0_object_events WHERE type_name=:name'),{'name':definition['name']})
                c.execute(text('DELETE FROM c0_object_types WHERE name=:name'),{'name':definition['name']})


def test_provider_free_knowledge_search_signed_rest_has_revision_citations_and_safe_fallback(knowledge_http):
    async def check():
        app, owner, member, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            path='/api/v1/knowledge/search'
            assert (await client.get(path,params={'query':'knowledge'})).status_code==401
            client.headers['Authorization']='Bearer '+owner
            query='searchtoken'+uuid4().hex
            created=await client.post('/api/v1/wiki/pages',json={'slug':query,'title':'Search fixture','body':'Authored '+query,'idempotency_key':query})
            assert created.status_code==201
            page=created.json()
            upload=await client.post('/api/v1/sources/upload',data={'title':'HTTP Wiki evidence '+uuid4().hex,'media_type':'text/plain'},files={'file':('evidence.txt',('Raw '+query).encode())})
            assert upload.status_code==202
            Worker(knowledge_http[4],app.state.jobs.registry).tick()
            response=await client.get(path,params={'query':query,'mode':'hybrid'})
            assert response.status_code==200
            result=response.json();assert result['retrieval_method']=='text' and result['fallback_reason']=='embeddings_not_configured'
            assert {h['kind'] for h in result['hits']}=={'chunk','wiki_revision'}
            wiki_hit=next(h for h in result['hits'] if h['kind']=='wiki_revision')
            assert wiki_hit['wiki']['revision_id']==page['content']['id'] and query in wiki_hit['excerpt']
            citation=next(h['citation'] for h in result['hits'] if h['kind']=='chunk')
            assert citation['source_hash']==upload.json()['content_hash']
            assert (await client.get(path,params={'query':query,'limit':51})).status_code==422
            assert (await client.get(path,params={'query':query,'provider_url':'https://arbitrary.invalid'})).status_code==422
            client.headers['Authorization']='Bearer '+member
            assert (await client.get(path,params={'query':query})).status_code==403
            client.headers['Authorization']='Bearer '+owner
            account=next(a['id'] for a in (await client.get('/api/v1/access/accounts')).json()['accounts'] if a['username']=='member')
            await client.put('/api/v1/access/accounts/'+account,json={'role':'reader'})
            client.headers['Authorization']='Bearer '+member
            assert (await client.get(path,params={'query':query})).status_code==200
            client.headers['Authorization']='Bearer '+owner
            await client.put('/api/v1/access/accounts/'+account,json={'role':None})
            client.headers['Authorization']='Bearer '+member
            assert (await client.get(path,params={'query':query})).status_code==403
    asyncio.run(check())


def test_signed_hybrid_and_scorer_transport_use_core_caps_and_provenance(knowledge_http):
    import httpx2
    from czero_core.providers import EmbeddingClient,EmbeddingSettings,SystemOneClient,ScorerSettings
    from czero_core.embeddings import EmbeddingStore
    from czero_core.retrieval import SearchLimits
    async def setup():
        app,owner,*_=knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
            pages=[]
            for label in ('Wanted','Other'):
                response=await client.post('/api/v1/wiki/pages',json={'slug':label.lower()+'-'+uuid4().hex,'title':label,
                    'body':'Hybrid transport evidence '+label,'idempotency_key':label})
                assert response.status_code==201;pages.append(response.json())
            return pages
    pages=asyncio.run(setup());app=knowledge_http[0]
    def embedding_reply(request):
        body=json.loads(request.content)
        return httpx2.Response(200,json={'model':body['model'],'data':[{'index':i,'embedding':[1,0,0]} for i in range(len(body['input']))]})
    import json
    client=EmbeddingClient(EmbeddingSettings('https://embedding.example.test/'+uuid4().hex,'fixture',dimensions=3),transport=httpx2.MockTransport(embedding_reply))
    store=EmbeddingStore(knowledge_http[4],client,app.state.auth.access)
    app.state.search.embeddings=store;app.state.search.limits=SearchLimits(max_limit=3,candidates=4,graph_depth=0,scorer_candidates=2)
    def score_reply(request):
        body=json.loads(request.content)
        return httpx2.Response(200,json={'model':'kev-mock','answers':{'r'+str(i):{'type':'noul','noul':.9 if 'Wanted' in c['text'] else .1} for i,c in enumerate(body['state']['candidates'])}})
    app.state.search.scorer=SystemOneClient(ScorerSettings('https://score.example.test/v1/systemone','kev-mock'),transport=httpx2.MockTransport(score_reply))
    app.state.search.scorer_mode='filter'
    try:
        with knowledge_http[4].engine.begin() as c:store._index_batch(c)
        async def check():
            async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+knowledge_http[1]}) as transport:
                status=await transport.get('/api/v1/knowledge/index/status')
                assert status.status_code==200 and status.json()['configured'] is True
                assert status.json()['indexed']==2 and status.json()['dimensions']==3
                assert status.json()['profile_id']==str(store.profile_id)
                assert 'endpoint' not in status.text and 'api_key' not in status.text
                response=await transport.get('/api/v1/knowledge/search',params={'query':'Hybrid transport','mode':'hybrid','rerank':'filter'})
                assert response.status_code==200;result=response.json()
                assert result['retrieval_method']=='hybrid+filter' and result['scored_count']==2
                assert len(result['hits'])==1 and result['hits'][0]['resource_id']==pages[0]['id']
                assert result['hits'][0]['wiki']['revision_id']==pages[0]['content']['id'] and result['hits'][0]['relevance_score']==.9
                assert (await transport.get('/api/v1/knowledge/search',params={'query':'Hybrid','limit':4})).status_code==422
                assert (await transport.get('/api/v1/knowledge/search',params={'query':'Hybrid','graph_depth':1})).status_code==422
                assert (await transport.get('/api/v1/knowledge/search',params={'query':'Hybrid','api_key':'untrusted-request'})).status_code==422
        asyncio.run(check())
    finally:
        with knowledge_http[4].engine.begin() as c:c.execute(text('DELETE FROM c0_embedding_profiles WHERE id=:id'),{'id':store.profile_id})
