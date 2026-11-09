# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import os
from uuid import uuid4

import httpx2
from httpx import ASGITransport,AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text

from czero_core.embeddings import EmbeddingStore
from czero_core.providers import EmbeddingClient,EmbeddingSettings,ScorerSettings,SystemOneClient
from test_auth_http import application,ORIGIN
from test_mcp_http import transport,RESOURCE

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


def test_rest_and_both_sdk_modes_normalize_queries_and_preserve_semantic_passage(transport):
    app,child,_,_,pair,_,owner,_=transport
    body='alpha '*20+'字'*600+'general introduction. '+'padding '*600+'alpha precise recovery procedure.'
    async def setup():
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as http:
            response=await http.post('/api/v1/wiki/pages',json={'slug':'recovery-'+uuid4().hex,
                'title':'Recovery','body':body,'idempotency_key':uuid4().hex})
            assert response.status_code==201
    asyncio.run(setup())
    def reply(request):
        payload=json.loads(request.content)
        return httpx2.Response(200,json={'model':payload['model'],'data':[
            {'index':i,'embedding':[0,1,0] if 'precise' in value or value=='alpha recovery' else [1,0,0]}
            for i,value in enumerate(payload['input'])]})
    embedding=EmbeddingClient(EmbeddingSettings('https://embedding.example.test/'+uuid4().hex,'fixture',dimensions=3),transport=httpx2.MockTransport(reply))
    store=EmbeddingStore(app.state.search.database,embedding,app.state.auth.access)
    app.state.search.embeddings=store
    app.state.structured_search.evidence.embeddings=store
    try:
        with store.database.engine.begin() as c:store._index_batch(c)
        async def check():
            async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as http:
                response=await http.get('/api/v1/knowledge/search',params={'query':'alpha\n\trecovery','mode':'hybrid','kind':'wiki'})
                assert response.status_code==200
                expected=response.json();hit,=expected['hits'];support,=hit['supporting_passages']
                assert 'precise recovery procedure' in support['excerpt']
                assert body[support['start_offset']:support['end_offset']]==support['excerpt']
                assert expected['retrieval_method']=='hybrid'
                expanded=await http.get('/api/v1/knowledge/search',params={'query':' '*600+'alpha recovery','mode':'hybrid','kind':'wiki'})
                assert expanded.status_code==200 and expanded.json()==expected
                for invalid in ['a'*513,'bad\0query','a'*8193]:
                    assert (await http.get('/api/v1/knowledge/search',params={'query':invalid})).status_code==422
                structured=await http.post('/api/v1/knowledge/search/structured',json={'query':'alpha\nrecovery','mode':'hybrid','filters':{'categories':['wiki']}})
                assert structured.status_code==200 and structured.json()['hits'][0]['supporting_passages']
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+pair.access_token}) as http:
                    for mode in ('auto','legacy'):
                        async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                            result=await client.call_tool('knowledge_search',{'options':{'query':' '*600+'alpha\nrecovery','mode':'hybrid','kind':'wiki'}})
                            assert not result.is_error and result.structured_content==expected
                            assert (await client.call_tool('knowledge_search',{'options':{'query':'a'*513}})).is_error
            def score_reply(request):
                payload=json.loads(request.content)
                candidates=json.loads(payload['input'])['candidates']
                assert len(candidates)==1 and len(candidates[0]['text'].encode())<=2048
                assert 'alpha' in candidates[0]['text'] and 'precise recovery procedure' in candidates[0]['text']
                return httpx2.Response(200,json={'model':payload['model'],'answers':[{'name':'r0','type':'predicate','probability':.9}]})
            app.state.search.scorer=SystemOneClient(ScorerSettings('https://score.example.test/v1','gpt-6-luna'),transport=httpx2.MockTransport(score_reply))
            app.state.search.scorer_mode='rerank'
            async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as http:
                result=await http.get('/api/v1/knowledge/search',params={'query':'alpha recovery','mode':'hybrid','kind':'wiki','rerank':'rerank'})
                assert result.status_code==200 and result.json()['scored_count']==1
                assert result.json()['scorer_truncated_candidates']==1
                assert result.json()['hits'][0]['supporting_passages']==expected['hits'][0]['supporting_passages']
        asyncio.run(check())
    finally:
        with store.database.engine.begin() as c:c.execute(text('DELETE FROM c0_embedding_profiles WHERE id=:id'),{'id':store.profile_id})
