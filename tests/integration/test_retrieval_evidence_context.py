# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
import hashlib
import json
import os

import httpx2
import pytest
from sqlalchemy import text

from czero_core.embeddings import EmbeddingStore,profile_identity
from czero_core.migrate import migrate_database
from czero_core.retrieval import SearchService
from czero_core.structured import StructuredSearchService
from test_embeddings import indexed,search,wiki,sources,access
from test_wiki import create_page
from test_sources import upload,execute
from test_spaces import spaces,create,member
from czero_core.identity import PermissionDenied,Role

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


@pytest.fixture
def contextual(indexed):
    store,_,_=indexed
    store.client.settings=replace(store.client.settings,input_format='context-v1')
    store.profile_id,store.fingerprint=profile_identity(store.client.settings)
    return indexed


def test_normalized_queries_have_identical_core_source_and_structured_results(search):
    service,wiki,source=search
    version=upload(source,data=b'alpha recovery');execute(source,'source.extract',version['id'])
    create_page(wiki,body='alpha recovery')
    for query in ['  alpha\n\trecovery\r\n',' '*600+'alpha recovery']:
        assert service.search(wiki[1],query,mode='text')==service.search(wiki[1],'alpha recovery',mode='text')
        assert source[0].search(source[1],query)==source[0].search(source[1],'alpha recovery')
        structured=StructuredSearchService(service.database,wiki[0].access)
        assert structured.search(wiki[1],query,mode='text')==structured.search(wiki[1],'alpha recovery',mode='text')


@pytest.mark.parametrize('kind',['source','wiki'])
def test_contextual_input_contains_recorded_identity_and_ancestor_sections(contextual,kind):
    store,fixtures,calls=contextual;_,wiki,source=fixtures
    body='# Recovery\n\n## Console\n\n'+'alpha '*1000
    if kind=='source':
        version=upload(source,data=body.encode(),title='ACME manual',media_type='text/markdown',
            metadata={'provenance':{'product':'ACME','product_version':'8'}})
        execute(source,'source.extract',version['id'])
    else:
        create_page(wiki,title='ACME manual',body=body,metadata={'provenance':{'product':'ACME','product_version':'8'}})
    for _ in range(3):
        with store.database.engine.begin() as c:store._index_batch(c)
    inputs=[v for call in calls for v in call['input']]
    assert inputs and all('title: ACME manual' in v and 'product: ACME' in v for v in inputs)
    assert any('section: # Recovery > ## Console' in v for v in inputs)
    assert all(len(v)<=4096 for v in inputs)
    with store.database.engine.connect() as c:
        hashes=set(c.execute(text('SELECT input_hash FROM c0_embeddings WHERE profile_id=:id'),{'id':store.profile_id}).scalars())
    assert hashes=={hashlib.sha256(v.encode()).hexdigest() for v in inputs}
    status=store.status(wiki[1]);assert status['complete'] and status['input_format']=='context-v1'


def test_contextual_search_waits_for_complete_coverage_and_reindex(contextual):
    store,fixtures,_=contextual;_,wiki,source=fixtures
    version=upload(source,data=b'alpha '*3000);execute(source,'source.extract',version['id'])
    service=SearchService(store.database,wiki[0].access,embedding_client=store.client)
    with store.database.engine.begin() as c:store._index_batch(c)
    status=store.status(wiki[1]);assert status['source_indexed']==8 and status['source_expected']>8 and not status['complete']
    assert service.search(wiki[1],'alpha',mode='hybrid')['fallback_reason']=='embedding_index_not_ready'
    for _ in range(3):
        with store.database.engine.begin() as c:store._index_batch(c)
    assert store.status(wiki[1])['complete']
    assert service.search(wiki[1],'alpha',mode='hybrid')['retrieval_method']=='hybrid'
    with store.database.engine.begin() as c:
        store._reindex(c,{'profile_id':str(store.profile_id),'expected_generation':1})
    assert not store.status(wiki[1])['complete']
    assert service.search(wiki[1],'alpha',mode='hybrid')['fallback_reason']=='embedding_index_not_ready'


def test_contextual_readiness_and_counts_are_selected_space_bound(spaces,contextual):
    store,fixtures,_=contextual;_,wiki,source=fixtures
    private=create(spaces);reader=member(spaces,Role.READER)
    protected=(source[0].in_space(private['id']),source[1],source[2],source[3])
    public=upload(source,data=b'alpha public evidence');execute(source,'source.extract',public['id'])
    hidden=upload(protected,data=b'alpha private evidence');execute(protected,'source.extract',hidden['id'])
    with store.database.engine.begin() as c:
        store._index_batch(c)
        c.execute(text('''DELETE FROM c0_embeddings e USING c0_chunks ch,c0_documents d
            WHERE e.source_chunk_id=ch.id AND ch.document_id=d.id AND d.version_id=:version'''),{'version':hidden['id']})
    status=store.status(reader)
    assert status['source_expected']==status['source_indexed']==1 and status['complete']
    assert not store.in_space(private['id']).status(wiki[1])['complete']
    service=SearchService(store.database,wiki[0].access,embedding_client=store.client)
    result=service.search(reader,'alpha',mode='hybrid')
    assert result['retrieval_method']=='hybrid'
    assert {h['resource_id'] for h in result['hits']}=={str(public['source_id'])}
    with pytest.raises(PermissionDenied):store.in_space(private['id']).status(reader)
    with pytest.raises(PermissionDenied):service.in_space(private['id']).search(reader,'alpha',mode='hybrid')


def test_context_label_edit_invalidates_only_context_profile_and_rebuilds_same_evidence(contextual):
    store,fixtures,calls=contextual;_,wiki,source=fixtures
    version=upload(source,data=b'alpha stable original',title='Old title');execute(source,'source.extract',version['id'])
    legacy=EmbeddingStore(store.database,type(store.client)(replace(store.client.settings,input_format='legacy'),transport=store.client._transport),wiki[0].access)
    try:
        with store.database.engine.begin() as c:
            legacy._index_batch(c);store._index_batch(c)
        old=source[0].get(source[1],version['source_id'])
        updated=upload(source,data=b'alpha stable original',title='New title',source_id=version['source_id'],expected_revision=old['revision'])
        assert updated['id']==version['id']
        with store.database.engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM c0_embeddings WHERE profile_id=:id'),{'id':store.profile_id}).scalar_one()==0
            assert c.execute(text('SELECT count(*) FROM c0_embeddings WHERE profile_id=:id'),{'id':legacy.profile_id}).scalar_one()==1
        with store.database.engine.begin() as c:store._index_batch(c)
        assert 'title: New title' in calls[-1]['input'][0]
        assert source[0].document(source[1],version['id'])['body']=='alpha stable original'
        migrate_database(store.database);migrate_database(store.database)
        assert store.status(wiki[1])['complete']
    finally:
        with store.database.engine.begin() as c:c.execute(text('DELETE FROM c0_embedding_profiles WHERE id=:id'),{'id':legacy.profile_id})


def test_wiki_title_only_edit_invalidates_context_without_changing_body_generation(contextual):
    store,fixtures,_=contextual;_,wiki,_=fixtures
    page=create_page(wiki,title='Old title',body='alpha unchanged body')
    with store.database.engine.begin() as c:store._index_batch(c)
    changed=wiki[0].update_page(wiki[1],page['id'],'New title','alpha unchanged body',expected_revision=1,idempotency_key='rename')
    assert changed['content']['id']==page['content']['id']
    assert not store.status(wiki[1])['complete']
    with store.database.engine.begin() as c:store._index_batch(c)
    assert store.status(wiki[1])['complete']


def test_label_change_during_provider_io_cannot_publish_stale_context(contextual):
    store,fixtures,_=contextual;_,wiki,source=fixtures
    version=upload(source,data=b'alpha unchanged body',title='Old title');execute(source,'source.extract',version['id'])
    def reply(request):
        old=source[0].get(source[1],version['source_id'])
        upload(source,data=b'alpha unchanged body',title='New title',source_id=version['source_id'],expected_revision=old['revision'])
        payload=json.loads(request.content)
        return httpx2.Response(200,json={'model':payload['model'],'data':[{'index':i,'embedding':[1,0,0]} for i in range(len(payload['input']))]})
    store.client._transport=httpx2.MockTransport(reply)
    with store.database.engine.begin() as c:
        assert store._index_batch(c)['indexed']==0
    assert not store.status(wiki[1])['complete']


def test_context_index_does_not_invert_content_writer_lock_order(contextual):
    from czero_core.current_content import content_lock
    store,fixtures,_=contextual;_,_,source=fixtures
    version=upload(source,data=b'alpha evidence');execute(source,'source.extract',version['id'])
    with store.database.engine.begin() as writer:
        content_lock(writer)
        with store.database.engine.begin() as c:
            result=store._index_batch(c)
            assert result['status']=='busy' and result['indexed']==0
    with store.database.engine.begin() as c:
        assert store._index_batch(c)['indexed']==1


@pytest.mark.parametrize('kind',['source','wiki'])
def test_hybrid_keeps_exact_semantic_procedure_from_same_document(indexed,monkeypatch,kind):
    store,fixtures,_=indexed;_,wiki,source=fixtures
    body='alpha general introduction. '+'padding '*600+'alpha precise recovery procedure.'
    if kind=='source':
        version=upload(source,data=body.encode());execute(source,'source.extract',version['id'])
    else:
        create_page(wiki,body=body)
    for _ in range(3):
        with store.database.engine.begin() as c:store._index_batch(c)
    service=SearchService(store.database,wiki[0].access,embedding_client=store.client)
    with store.database.engine.connect() as c:
        if kind=='source':
            rows=list(c.execute(text('SELECT id FROM c0_chunks ORDER BY start_offset')).scalars())
            first=service._source_hit(c,rows[0],'alpha');last=service._source_hit(c,rows[-1],'precise')
        else:
            rows=c.execute(text('SELECT id,revision_id FROM c0_wiki_chunks ORDER BY ordinal')).mappings().all()
            first=service._wiki_hit(c,rows[0]['revision_id'],'alpha',chunk_id=rows[0]['id'])
            last=service._wiki_hit(c,rows[-1]['revision_id'],'precise',chunk_id=rows[-1]['id'])
    monkeypatch.setattr(service,'_text',lambda *a,**k:([first],'bm25'))
    monkeypatch.setattr(service,'_semantic',lambda *a,**k:[last])
    result=service.search(wiki[1],'alpha recovery',kind=kind,mode='hybrid')
    hit,=result['hits'];support,=hit['supporting_passages']
    assert 'precise recovery procedure' in support['excerpt']
    assert body[support['start_offset']:support['end_offset']]==support['excerpt']
    assert hit['id']==str(first['id']) and result['retrieval_method']=='hybrid'
