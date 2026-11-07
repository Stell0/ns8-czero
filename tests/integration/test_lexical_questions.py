# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real authorized APIs distinguish question matching from explicit syntax."""
import asyncio
import json
import os
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from czero_core.worker import Worker
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_spaces_http import space_http, create_space

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


async def corpus(http, fixture, spaces, *, literal_question=False):
    app = fixture[0]
    space = await create_space(http, spaces)
    rows = []
    for version, body in [
        ('8', '# Backup\n\nEnable scheduled backup in Example Mail 8 from the dashboard.\n'),
        ('7', '# Backup\n\nManual backup in Example Mail 7 uses net.ipv4.ip_forward.\n'),
    ]:
        if version=='7' and literal_question:
            body+='\nHow can I enable scheduled backup in Example Mail 8?\n'
        response = await http.post('/api/v1/sources/upload', params={'space_id':space['id']},
            data={'title':'Synthetic mail manual '+version,'media_type':'text/markdown',
                  'metadata':json.dumps({'canonical_url':'https://example.org/mail/'+version})},
            files={'file':('manual.md',body.encode(),'text/markdown')})
        assert response.status_code == 202
        rows.append(response.json())
    Worker(fixture[4], app.state.jobs.registry).tick()
    for row, version in zip(rows, ('8','7')):
        response = await http.put('/api/v1/knowledge/annotations/source_version/'+row['id']+'/1/applicability',
            params={'space_id':space['id']}, json={'value':{'products':['Example Mail'],'version_tags':[version],
            'status':'applicable'},'expected_revision':0,'idempotency_key':uuid4().hex})
        assert response.status_code == 200
    return space, rows


@pytest.mark.parametrize('caller', ['ordinary','filtered','source'])
def test_question_finds_verified_evidence_through_each_caller(knowledge_http, space_http, caller):
    async def check():
        app, token, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            space, rows = await corpus(http, knowledge_http, space_http)
            params={'space_id':space['id']}
            # Verify the whole body independently of retrieval and its ranking.
            doc = await http.get('/api/v1/source-documents/'+rows[0]['source_id'], params=params)
            assert doc.status_code == 200 and 'Enable scheduled backup' in doc.json()['body']
            query='How can I enable scheduled backup in Example Mail 8?'
            if caller == 'filtered':
                response = await http.post('/api/v1/knowledge/search/structured', json={**params,
                    'query':query,'mode':'text','rerank':'off','filters':{'categories':['source'],
                    'products':['Example Mail'],'version_tags':['8']}})
            else:
                path='/api/v1/'+('sources/search' if caller=='source' else 'knowledge/search')
                response = await http.get(path, params={**params,'query':query,
                    **({'mode':'text','rerank':'off','kind':'source'} if caller=='ordinary' else {})})
            assert response.status_code == 200
            if caller!='source':
                assert response.json()['lexical_strategy']=='bm25'
                assert response.json()['lexical_ranker_version']=='bm25-v1-en-it-k1-1.2-b-0.75'
                assert response.json()['retrieval_method']=='text'
                assert response.json()['provider_usage']=={}
            hits=response.json()['citations' if caller=='source' else 'hits']
            assert hits, 'Natural question lost evidence independently verified above'
            citation=hits[0] if caller=='source' else hits[0]['citation']
            assert citation['source_id'] == rows[0]['source_id']
            if caller=='ordinary':
                for mode in ('semantic','hybrid'):
                    fallback=await http.get('/api/v1/knowledge/search',params={**params,'query':query,
                        'mode':mode,'rerank':'off','kind':'source'})
                    assert fallback.json()['retrieval_method']=='text'
                    assert fallback.json()['lexical_strategy']=='bm25'
                    assert fallback.json()['fallback_reason']=='embeddings_not_configured'
                    assert fallback.json()['hits']==hits
    asyncio.run(check())


def test_relaxation_obeys_the_filtered_selection_and_source_pagination(knowledge_http, space_http):
    async def check():
        app, token, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            space, rows=await corpus(http,knowledge_http,space_http,literal_question=True)
            params={'space_id':space['id'],'query':'How can I enable scheduled backup in Example Mail 8?'}
            # A strict match in another version must not suppress filtered matching.
            ordinary=await http.get('/api/v1/knowledge/search',params={**params,'kind':'source','mode':'text','rerank':'off'})
            assert {h['citation']['source_id'] for h in ordinary.json()['hits']}=={r['source_id'] for r in rows}
            selected=await http.post('/api/v1/knowledge/search/structured',json={**params,'mode':'text',
                'rerank':'off','filters':{'categories':['source'],'version_tags':['8']}})
            assert selected.status_code==200
            assert {h['citation']['source_id'] for h in selected.json()['hits']}=={rows[0]['source_id']}
            # Every page follows the same document ordering.
            first=await http.get('/api/v1/sources/search',params={**params,'limit':1})
            later=await http.get('/api/v1/sources/search',params={**params,'limit':1,'offset':1})
            assert len(first.json()['citations'])==1 and len(later.json()['citations'])==1
            assert first.json()['citations'][0]['source_id']!=later.json()['citations'][0]['source_id']
    asyncio.run(check())


def test_ordinary_prose_keeps_weak_matches_as_candidates(knowledge_http, space_http):
    async def check():
        app, token, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            space, _=await corpus(http,knowledge_http,space_http)
            for query in ('How can I enable quantum teleportation?',
                          'How can I enable scheduled backup blue green purple orange?',
                          'How can I enable scheduled backup in Example Mail 99?',
                          'How do I change net.ipv4.nonexistent in Example Mail?',
                          'How can I enable scheduled backup with UNKNOWN-PROTOCOL?',
                          'How can I enable scheduled backup with XYZZY?'):
                response=await http.get('/api/v1/knowledge/search',params={'space_id':space['id'],
                    'query':query,'kind':'source','mode':'text','rerank':'off'})
                assert response.status_code==200 and response.json()['hits']
    asyncio.run(check())


def test_relaxed_queries_recheck_reader_grants_without_shared_fallback(knowledge_http,space_http):
    async def check():
        app,token,member,*_=knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            space,_=await corpus(http,knowledge_http,space_http)
            assert (await http.get('/api/v1/me',headers={'Authorization':'Bearer '+member})).status_code==403
            account=next(r for r in (await http.get('/api/v1/access/accounts')).json()['accounts'] if r['username']=='member')
            assert (await http.put('/api/v1/access/accounts/'+account['id'],json={'role':'reader'})).status_code==204
            grant='/api/v1/spaces/'+space['id']+'/grants/'+account['id']
            assert (await http.put(grant,json={'role':'reader','expected_revision':0,'idempotency_key':'grant'})).status_code==200
            params={'space_id':space['id'],'query':'How can I enable scheduled backup in Example Mail 8?'}
            for admitted in (True,False):
                if not admitted:
                    assert (await http.put(grant,json={'role':None,'expected_revision':1,'idempotency_key':'revoke'})).status_code==200
                for caller in ('ordinary','filtered','source'):
                    headers={'Authorization':'Bearer '+member}
                    if caller=='filtered':
                        response=await http.post('/api/v1/knowledge/search/structured',headers=headers,
                            json={**params,'mode':'text','rerank':'off','filters':{'categories':['source']}})
                    else:
                        response=await http.get('/api/v1/'+('sources/search' if caller=='source' else 'knowledge/search'),
                            headers=headers,params={**params,**({'mode':'text','rerank':'off','kind':'source'} if caller=='ordinary' else {})})
                    assert response.status_code==(200 if admitted else 403)
                    if admitted:assert response.json()['citations' if caller=='source' else 'hits']
                    else:assert 'dashboard' not in response.text
    asyncio.run(check())


@pytest.mark.parametrize('query,versions', [
    ('scheduled backup', {'8','7'}),
    ('"scheduled backup"', {'8'}),
    ('scheduled OR manual', {'8','7'}),
    ('(scheduled OR manual)', {'8','7'}),
    ('backup -scheduled', {'7'}),
    ('scheduled AND teleportation', set()),
    ('"How can I enable scheduled backup?"', set()),
    ('net.ipv4.ip_forward', {'7'}),
    ('Example Mail 7', {'8','7'}),
    ('quantum teleportation', set()),
])
def test_explicit_syntax_and_identifier_controls(knowledge_http, space_http, query, versions):
    async def check():
        app, token, *_ = knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            space, rows = await corpus(http, knowledge_http, space_http)
            expected={r['source_id'] for r,version in zip(rows, ('8','7')) if version in versions}
            for caller in ('ordinary','filtered','source'):
                params={'space_id':space['id'],'query':query}
                if caller=='filtered':
                    response=await http.post('/api/v1/knowledge/search/structured',json={**params,
                        'mode':'text','rerank':'off','filters':{'categories':['source']}})
                else:
                    response=await http.get('/api/v1/'+('sources/search' if caller=='source' else 'knowledge/search'),
                        params={**params,**({'mode':'text','rerank':'off','kind':'source'} if caller=='ordinary' else {})})
                assert response.status_code==200
                hits=response.json()['citations' if caller=='source' else 'hits']
                assert {h['source_id'] if caller=='source' else h['citation']['source_id'] for h in hits}==expected
    asyncio.run(check())


@pytest.mark.parametrize('inline_diagnostic', [False,True])
def test_parent_product_version_context_and_inline_diagnostic(knowledge_http,space_http,inline_diagnostic):
    async def check():
        app,token,*_=knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            space=await create_space(http,space_http);rows=[]
            for version,edition in [('8','Alpha'),('7','Beta')]:
                body=('# Retention guide\n\nEnable scheduled backup from the dashboard.\nEdition '+edition+'.\n')
                if inline_diagnostic:
                    body='Resolve the Check(flag) authentication error in Example Mail '+version+' by selecting Retry.\n'
                response=await http.post('/api/v1/sources/upload',params={'space_id':space['id']},
                    data={'title':'Retention guide','media_type':'text/markdown','metadata':json.dumps({
                        'canonical_url':'https://example.org/retention/'+version,
                        'provenance':{'product':'Example Mail','product_version':version,'language':'en'}})},
                    files={'file':('guide.md',body.encode(),'text/markdown')})
                assert response.status_code==202;rows.append(response.json())
            Worker(knowledge_http[4],app.state.jobs.registry).tick()
            query=('How can I resolve a Check(flag) authentication error in Example Mail 8?' if inline_diagnostic
                   else 'How can I enable scheduled backup in Example Mail 8?')
            for caller in ('ordinary','filtered','source'):
                params={'space_id':space['id'],'query':query}
                if caller=='filtered':
                    response=await http.post('/api/v1/knowledge/search/structured',json={**params,
                        'mode':'text','rerank':'off','filters':{'categories':['source']}})
                else:
                    response=await http.get('/api/v1/'+('sources/search' if caller=='source' else 'knowledge/search'),
                        params={**params,**({'mode':'text','rerank':'off','kind':'source'} if caller=='ordinary' else {})})
                assert response.status_code==200
                hits=response.json()['citations' if caller=='source' else 'hits']
                assert {h['source_id'] if caller=='source' else h['citation']['source_id'] for h in hits}=={r['source_id'] for r in rows}
    asyncio.run(check())


def test_bm25_keeps_gin_discovery_and_does_not_truncate_long_queries(knowledge_http,space_http):
    from sqlalchemy import text
    from czero_core.bm25 import query_groups
    async def check():
        app,token,*_=knowledge_http
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            space,_=await corpus(http,knowledge_http,space_http)
            query='How can I enable scheduled backup in Example Mail 8?'
            with knowledge_http[4].engine.begin() as connection:
                groups=query_groups(connection,query);assert groups
                connection.execute(text('SET LOCAL enable_seqscan=off'))
                plan=' '.join(r[0] for r in connection.execute(text(
                    'EXPLAIN SELECT document_id FROM c0_lexical_terms WHERE variants && CAST(:variants AS text[])'),
                    {'variants':groups[0]}))
                assert 'c0_lexical_terms_variants' in plan
            words=['opaqueword'+chr(97+i//26)+chr(97+i%26) for i in range(33)]
            response=await http.get('/api/v1/knowledge/search',params={'space_id':space['id'],
                'query':query+' '+' '.join(words),'kind':'source','mode':'text','rerank':'off'})
            assert response.status_code==200 and response.json()['hits']
            assert response.json()['lexical_strategy']=='bm25'
    asyncio.run(check())
