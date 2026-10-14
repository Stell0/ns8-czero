# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json,os
import httpx2
import pytest
from sqlalchemy import text
from czero_core.providers import SystemOneClient,ScorerSettings
from czero_core.retrieval import SearchService,SearchLimits
from czero_core.knowledge import KnowledgeService
from test_embeddings import indexed,search,wiki,sources,access
from test_wiki import create_page,create_entity

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


def configured(indexed,**kwargs):
    store,fixtures,_=indexed
    service=SearchService(store.database,fixtures[1][0].access,embedding_client=store.client,**kwargs)
    return service,fixtures[1]


def test_semantic_paraphrase_hybrid_and_wiki_chunk_aggregation_keep_revision_identity(indexed):
    service,wiki=configured(indexed);store,_,_=indexed
    alpha=create_page(wiki,title='First',body='alpha '*1000)
    beta=create_page(wiki,title='Second',body='beta vehicle maintenance')
    with store.database.engine.begin() as c:store._index_batch(c)
    assert service.search(wiki[1],'automobile',mode='text')['hits']==[]
    result=service.search(wiki[1],'automobile',mode='semantic',limit=1)
    assert result['retrieval_method']=='semantic' and result['hits'][0]['id']==beta['content']['id']
    result=service.search(wiki[1],'alpha',mode='hybrid')
    assert result['retrieval_method']=='hybrid' and result['hits'][0]['id']==alpha['content']['id']
    assert len({h['id'] for h in result['hits']})==len(result['hits'])==2
    hit=result['hits'][0]
    assert alpha['content']['body'][hit['start_offset']:hit['end_offset']]==hit['excerpt']
    assert hit['wiki']['revision_id']==alpha['content']['id']


def test_embedding_missing_rate_limit_and_model_mismatch_preserve_text_results(indexed):
    service,wiki=configured(indexed);store,_,_=indexed
    create_page(wiki,body='alpha evidence')
    before=service.search(wiki[1],'alpha',mode='text')['hits']
    assert service.search(wiki[1],'alpha',mode='hybrid')['fallback_reason']=='embedding_index_not_ready'
    with store.database.engine.begin() as c:store._index_batch(c)
    for response,reason in [(httpx2.Response(429),'embedding_rate_limited'),
                            (httpx2.Response(200,json={'model':'wrong','data':[]}),'embedding_invalid_response')]:
        store.client._transport=httpx2.MockTransport(lambda _:response)
        fallback=service.search(wiki[1],'alpha',mode='hybrid')
        assert fallback['hits']==before and fallback['retrieval_method']=='text' and fallback['fallback_reason']==reason


@pytest.mark.parametrize('model',['jev-1.13','kev-mock'])
def test_scorer_rerank_filter_and_outage_keep_ordinary_ranking(indexed,model):
    service,wiki=configured(indexed)
    create_page(wiki,title='Low',body='alpha')
    wanted=create_page(wiki,title='Wanted',body='alpha useful context')
    settings=ScorerSettings('https://score.example.test/v1/systemone',model,threshold=.7)
    def reply(request):
        body=json.loads(request.content)
        return httpx2.Response(200,json={'model':model,'answers':{
            'r'+str(i):{'type':'noul','noul':.9 if 'Wanted' in c['text'] else .1}
            for i,c in enumerate(body['state']['candidates'])}})
    service.scorer=SystemOneClient(settings,transport=httpx2.MockTransport(reply));service.scorer_mode='filter'
    ordinary=service.search(wiki[1],'alpha',mode='text',rerank='off')['hits']
    reranked=service.search(wiki[1],'alpha',mode='text',rerank='rerank')
    assert reranked['hits'][0]['id']==wanted['content']['id'] and reranked['scored_count']==2
    assert reranked['hits'][0]['relevance_score']==.9
    filtered=service.search(wiki[1],'alpha',mode='text',rerank='filter')
    assert [h['id'] for h in filtered['hits']]==[wanted['content']['id']]
    service.scorer._transport=httpx2.MockTransport(lambda _:httpx2.Response(503,text='untrusted secret body'))
    fallback=service.search(wiki[1],'alpha',mode='text',rerank='filter')
    assert fallback['hits']==ordinary and fallback['fallback_reason']=='systemone_unavailable'


def test_graph_context_uses_existing_bounded_current_role_service(indexed):
    service,wiki=configured(indexed)
    page=create_page(wiki,body='alpha linked evidence')
    root=create_entity(wiki,label='Inventory root');other=create_entity(wiki,label='Inventory leaf')
    knowledge=KnowledgeService(service.database,wiki[0].access)
    try:
        knowledge.link_entity(wiki[1],root['id'],'page',page['id'],idempotency_key='link')
        knowledge.add_relation(wiki[1],root['id'],other['id'],'related-to',idempotency_key='relation')
        result=service.search(wiki[1],'alpha',mode='text',graph_depth=1)
        assert result['retrieval_method']=='text+graph' and result['fallback_reason'] is None and len(result['graphs'])==1
        assert len(result['graphs'][0]['nodes'])==2 and len(result['graphs'][0]['references'])==1
    finally:
        with service.database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_entity_links WHERE entity_id=:id'),{'id':root['id']})
            c.execute(text('DELETE FROM c0_relations WHERE source_id=:id'),{'id':root['id']})


def test_request_overrides_cannot_raise_caps_or_enable_disabled_scoring(indexed):
    service,wiki=configured(indexed,limits=SearchLimits(max_limit=1,candidates=4,graph_depth=0,scorer_candidates=1))
    create_page(wiki,body='alpha');create_page(wiki,body='alpha')
    assert len(service.search(wiki[1],'alpha',mode='text')['hits'])==1
    for options in ({'limit':2},{'graph_depth':1},{'rerank':'rerank'}):
        with pytest.raises(ValueError):service.search(wiki[1],'alpha',**options)


def test_revocation_during_scoring_is_denied_and_network_has_no_held_db_connection(indexed):
    from uuid import uuid4
    from czero_core.identity import Actor,Role,PermissionDenied
    from test_access import record_unadmitted,account_named
    service,wiki=configured(indexed);acl=wiki[0].access
    create_page(wiki,body='alpha')
    record_unadmitted(acl,uuid4(),'scored-reader');member=account_named(acl,wiki[1],'scored-reader')
    acl.set_role(wiki[1],member['id'],Role.READER)
    def reply(request):
        assert service.database.engine.pool.checkedout()==0
        acl.set_role(wiki[1],member['id'],None)
        body=json.loads(request.content)
        return httpx2.Response(200,json={'model':'kev-mock','answers':{key:{'type':'noul','noul':.9} for key in body['questions']}})
    service.scorer=SystemOneClient(ScorerSettings('https://score.example.test/v1/systemone','kev-mock'),transport=httpx2.MockTransport(reply))
    service.scorer_mode='rerank'
    with pytest.raises(PermissionDenied):service.search(Actor(member['id'],Role.READER),'alpha',mode='text')


def test_graph_label_match_with_no_evidence_hits_handles_empty_uuid_filters(indexed):
    service,wiki=configured(indexed)
    root=create_entity(wiki,label='Unique graph entity')
    result=service.search(wiki[1],'Unique graph entity',mode='text',graph_depth=1)
    assert result['hits']==[] and result['fallback_reason'] is None
    assert result['graphs'][0]['root']==root['id']
