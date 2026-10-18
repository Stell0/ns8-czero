# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json,os
from uuid import UUID,uuid4
import httpx2
import pytest
from sqlalchemy import text
from czero_core.embeddings import EmbeddingStore,profile_identity,vector_literal,register_embedding_handlers,reindex_payload,SCHEDULE_ID
from czero_core.providers import EmbeddingClient,EmbeddingSettings,ProviderUnavailable
from czero_core.jobs import Registry
from czero_core.wiki import KnowledgeConflict
from test_retrieval import search,wiki,sources,access
from test_wiki import create_page
from test_sources import upload,execute

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


@pytest.fixture
def indexed(search):
    service,wiki,sources=search;calls=[]
    def responder(request):
        body=json.loads(request.content);calls.append(body)
        return httpx2.Response(200,json={'model':body['model'],'data':[
            {'index':i,'embedding':[1,0,0] if 'alpha' in value else [0,1,0]} for i,value in enumerate(body['input'])]})
    settings=EmbeddingSettings('https://embedding.example.test/'+uuid4().hex,'fixture-model',dimensions=3)
    client=EmbeddingClient(settings,transport=httpx2.MockTransport(responder))
    store=EmbeddingStore(service.database,client,wiki[0].access)
    with service.database.engine.connect() as c:
        schedule=dict(c.execute(text('SELECT enabled,interval_seconds,next_run_at FROM c0_scheduled_tasks WHERE id=:id'),{'id':SCHEDULE_ID}).mappings().one())
    yield store,search,calls
    with service.database.engine.begin() as c:
        c.execute(text('DELETE FROM c0_embedding_profiles WHERE id=:id'),{'id':store.profile_id})
        c.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled,interval_seconds=:interval_seconds,next_run_at=:next_run_at WHERE id=:id'),{**schedule,'id':SCHEDULE_ID})


def test_indexing_preserves_evidence_ids_complete_wiki_offsets_and_is_replay_safe(indexed):
    store,search,calls=indexed;service,wiki,sources=search
    page=create_page(wiki,body='alpha '*1000)
    original=page['content'];source=upload(sources,data=b'alpha source evidence');execute(sources,'source.extract',source['id'])
    with store.database.engine.begin() as c:
        first=store._index_batch(c)
    assert first['indexed']==3 and len(calls)==1 and len(calls[0]['input'])==3
    with store.database.engine.begin() as c:
        second=store._index_batch(c)
        pieces=c.execute(text('SELECT * FROM c0_wiki_chunks WHERE revision_id=:id ORDER BY ordinal'),{'id':original['id']}).mappings().all()
        assert all(original['body'][p['start_offset']:p['end_offset']]==p['body'] for p in pieces)
        assert pieces[0]['start_offset']==0 and pieces[-1]['end_offset']==len(original['body'])
        assert c.execute(text('SELECT count(*) FROM c0_embeddings WHERE profile_id=:id'),{'id':store.profile_id}).scalar_one()==3
    assert second['indexed']==0 and len(calls)==1
    assert wiki[0].get_page(wiki[1],page['id'])['content']['id']==original['id']
    assert sources[0].document(sources[1],source['id'])['body']=='alpha source evidence'


def test_first_successful_batch_is_not_a_complete_snapshot_with_prior_role_fixtures(indexed,monkeypatch):
    store, fixtures, _ = indexed
    _, wiki, sources = fixtures
    import runpy
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
    native=runpy.run_path(str(Path(__file__).parents[1]/'retrieval_fixture.py'))['index_complete']
    def command(arguments):
        with store.database.engine.connect() as connection:
            return 't' if connection.execute(text(arguments[-1])).scalar_one() else 'f'
    native.__globals__['command']=command
    for ordinal in range(5):
        create_page(wiki, title='Prior role ' + str(ordinal), body='alpha role evidence')
    for ordinal in range(10):
        version=upload(sources,data=('alpha source '+str(ordinal)).encode())
        execute(sources,'source.extract',version['id'])
    # Five vectors can satisfy the old fixture while both source and Wiki
    # indexing are incomplete; repeated valid work then changes the snapshot.
    with store.database.engine.begin() as connection:
        store._activate(connection)
        first=store._index_batch(connection)
        assert first['indexed']==8
        initial=connection.execute(text('SELECT count(*) FROM c0_embeddings WHERE profile_id=:id'),{'id':store.profile_id}).scalar_one()
        assert initial>=5
        assert connection.execute(text('SELECT count(*) FROM c0_wiki_chunks WHERE revision_id IN (SELECT id FROM c0_wiki_revisions WHERE page_id IN (SELECT resource_id FROM c0_knowledge_events WHERE actor_id=:actor))'),{'actor':wiki[1].user_id}).scalar_one()==2
        connection.execute(text('UPDATE c0_scheduled_tasks SET enabled=false WHERE handler=\'embedding.index\''))
    assert native('disposable') is False
    for _ in range(4):
        with store.database.engine.begin() as connection:store._index_batch(connection)
    with store.database.engine.begin() as connection:
        complete=connection.execute(text('SELECT count(*) FROM c0_embeddings WHERE profile_id=:id'),{'id':store.profile_id}).scalar_one()
        assert complete==15 and complete>initial
        store._activate(connection)
        assert connection.execute(text('SELECT enabled FROM c0_scheduled_tasks WHERE handler=\'embedding.index\'')).scalar_one() is False
        assert store._index_batch(connection)['indexed']==0
    assert native('disposable') is True


def test_profile_identity_excludes_keys_and_reembedding_generations_reject_stale_jobs(indexed):
    store,search,_=indexed;_,wiki,_=search
    settings=store.client.settings
    rotated=EmbeddingSettings(settings.endpoint,settings.model,api_key='rotated-unit-key',dimensions=3)
    assert profile_identity(rotated)==profile_identity(settings)
    assert profile_identity(EmbeddingSettings(settings.endpoint,'another-model',dimensions=3))!=profile_identity(settings)
    assert profile_identity(EmbeddingSettings(settings.endpoint,settings.model,dimensions=2))!=profile_identity(settings)
    create_page(wiki,body='alpha')
    with store.database.engine.begin() as c:
        store._index_batch(c)
        result=store._reindex(c,{'profile_id':str(store.profile_id),'expected_generation':1})
        assert result['generation']==2
        assert store.nearest(c,[1,0,0])==[]
    with pytest.raises(KnowledgeConflict):
        with store.database.engine.begin() as c:store._reindex(c,{'profile_id':str(store.profile_id),'expected_generation':1})
    with store.database.engine.begin() as c:
        assert store._index_batch(c)['indexed']==1
        assert len(store.nearest(c,[1,0,0]))==1
    assert store.status(wiki[1])['generation']==2


def test_real_ann_index_cosine_padding_profile_filter_and_current_revision_archives(indexed):
    store,search,_=indexed;_,wiki,sources=search
    page=create_page(wiki,body='alpha')
    version=upload(sources,data=b'not alpha evidence');execute(sources,'source.extract',version['id'])
    with store.database.engine.begin() as c:
        store._index_batch(c)
        nearest=store.nearest(c,[1,0,0]);assert len(nearest)==2
        assert all(abs(row['distance'])<1e-6 for row in nearest)
        c.execute(text('SET LOCAL enable_seqscan=off'))
        # Verify the actual padded-vector cosine index is usable.
        encoded=vector_literal([1,0,0],3)
        plan=' '.join(row[0] for row in c.execute(text('EXPLAIN SELECT id FROM c0_embeddings ORDER BY embedding <=> CAST(:vector AS vector) LIMIT 2'),{'vector':encoded}))
        assert 'c0_embeddings_cosine' in plan
    wiki[0].update_page(wiki[1],page['id'],'Changed','beta',expected_revision=1,idempotency_key='revision')
    with store.database.engine.begin() as c:
        assert len(store.nearest(c,[1,0,0],kind='wiki'))==0
        store._index_batch(c)
        current=store.nearest(c,[0,1,0],kind='wiki')
        assert len(current)==1 and abs(current[0]['distance'])<1e-6
    sources[0].delete(sources[1],version['source_id'],expected_revision=1)
    with store.database.engine.begin() as c:assert store.nearest(c,[1,0,0],kind='source')==[]


def test_provider_failure_rolls_back_derivative_state_without_touching_originals(indexed):
    store,search,_=indexed;_,wiki,_=search
    page=create_page(wiki,body='alpha')
    store.client._transport=httpx2.MockTransport(lambda _:httpx2.Response(429))
    with pytest.raises(ProviderUnavailable):
        with store.database.engine.begin() as c:store._index_batch(c)
    with store.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_embedding_profiles WHERE id=:id'),{'id':store.profile_id}).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM c0_wiki_chunks WHERE revision_id=:id'),{'id':page['content']['id']}).scalar_one()==0
    assert wiki[0].get_page(wiki[1],page['id'])['content']['body']=='alpha'


def test_bounded_index_batch_blank_wiki_and_trusted_registry_payload(indexed):
    store,search,calls=indexed;_,wiki,_=search
    page=create_page(wiki,title='Blank title',body='')
    for i in range(12):create_page(wiki,title='alpha '+str(i),body='alpha')
    registry=Registry();register_embedding_handlers(registry,store)
    assert {h['name'] for h in registry.describe()}=={'embedding.index','embedding.reindex'}
    assert reindex_payload({'profile_id':str(store.profile_id),'expected_generation':1})['expected_generation']==1
    with pytest.raises(ValueError):reindex_payload({'profile_id':str(store.profile_id),'expected_generation':True})
    with store.database.engine.begin() as c:
        assert store._index_batch(c)['indexed']<=8
    assert len(calls[0]['input'])<=8
    # Progressively handle more pages; no blank page stalls the queue.
    for i in range(8):
        with store.database.engine.begin() as c:store._index_batch(c)
    with store.database.engine.connect() as c:
        row=c.execute(text('SELECT start_offset,end_offset,body FROM c0_wiki_chunks WHERE revision_id=:id'),{'id':page['content']['id']}).mappings().one()
        assert row['body']=='' and row['start_offset']==row['end_offset']==0


def test_trusted_jobs_execute_index_and_compare_and_swap_reindex_once(indexed):
    from czero_core.jobs import JobService,default_registry
    from czero_core.worker import Worker
    store,search,_=indexed;_,wiki,_=search
    create_page(wiki,body='alpha')
    registry=default_registry();register_embedding_handlers(registry,store)
    jobs=JobService(store.database,registry,wiki[0].access);created=[]
    try:
        job=jobs.enqueue(wiki[1],'embedding.index',{},'embedding-'+uuid4().hex);created.append(job['id'])
        assert Worker(store.database,registry).tick(max_jobs=1)==1
        assert jobs.get_job(wiki[1],job['id'])['state']=='succeeded'
        key='reindex-'+uuid4().hex;payload={'profile_id':str(store.profile_id),'expected_generation':1}
        job=jobs.enqueue(wiki[1],'embedding.reindex',payload,key);created.append(job['id'])
        assert jobs.enqueue(wiki[1],'embedding.reindex',payload,key)['id']==job['id']
        assert Worker(store.database,registry).tick(max_jobs=1)==1
        assert jobs.get_job(wiki[1],job['id'])['result']['generation']==2
        assert store.status(wiki[1])['indexed']==0
    finally:
        with store.database.engine.begin() as c:
            for key in created:c.execute(text('DELETE FROM c0_jobs WHERE id=:id'),{'id':key})


def test_active_model_profiles_do_not_mix_vectors_for_the_same_raw_revision(indexed):
    store,search,_=indexed;_,wiki,_=search
    page=create_page(wiki,body='alpha')
    settings=EmbeddingSettings(store.client.settings.endpoint,'another-model',dimensions=3)
    other=EmbeddingStore(store.database,EmbeddingClient(settings,transport=store.client._transport),wiki[0].access)
    try:
        with store.database.engine.begin() as c:
            store._index_batch(c);other._index_batch(c)
            nearest=store.nearest(c,[1,0,0],kind='wiki')
            assert len(nearest)==1
            assert c.execute(text('SELECT profile_id FROM c0_embeddings WHERE id=:id'),{'id':nearest[0]['id']}).scalar_one()==store.profile_id
            assert len(other.nearest(c,[1,0,0],kind='wiki'))==1
        assert wiki[0].get_page(wiki[1],page['id'])['content']['body']=='alpha'
    finally:
        with store.database.engine.begin() as c:c.execute(text('DELETE FROM c0_embedding_profiles WHERE id=:id'),{'id':other.profile_id})


def test_actual_filtered_nearest_query_can_use_the_hnsw_index(indexed):
    store,search,_=indexed;_,wiki,_=search
    create_page(wiki,body='alpha')
    with store.database.engine.begin() as c:
        store._index_batch(c)
        c.execute(text('SET LOCAL enable_seqscan=off'));c.execute(text('SET LOCAL enable_sort=off'))
        plans=[]
        class Connection:
            def execute(self,statement,parameters=None):
                if 'WITH nearest AS MATERIALIZED' in str(statement):
                    plans.extend(row[0] for row in c.execute(text('EXPLAIN '+str(statement)),parameters))
                return c.execute(statement,parameters)
        assert store.nearest(Connection(),[1,0,0])
        assert 'c0_embeddings_cosine' in ' '.join(plans)


def test_active_profile_transitions_preserve_an_explicit_scheduler_pause(indexed):
    store,search,_=indexed;_,wiki,_=search
    from czero_core.embeddings import SCHEDULE_ID
    with store.database.engine.begin() as c:
        original=dict(c.execute(text('SELECT enabled,next_run_at FROM c0_scheduled_tasks WHERE id=:id'),{'id':SCHEDULE_ID}).mappings().one())
    try:
        with store.database.engine.begin() as c:
            store._activate(c)
            assert c.execute(text('SELECT active FROM c0_embedding_profiles WHERE id=:id'),{'id':store.profile_id}).scalar_one()
            c.execute(text('UPDATE c0_scheduled_tasks SET enabled=false WHERE id=:id'),{'id':SCHEDULE_ID})
        with store.database.engine.begin() as c:
            store._activate(c)
            assert not c.execute(text('SELECT enabled FROM c0_scheduled_tasks WHERE id=:id'),{'id':SCHEDULE_ID}).scalar_one()
            EmbeddingStore(store.database,None)._activate(c)
            assert not c.execute(text('SELECT active FROM c0_embedding_profiles WHERE id=:id'),{'id':store.profile_id}).scalar_one()
    finally:
        with store.database.engine.begin() as c:c.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled,next_run_at=:next_run_at WHERE id=:id'),{**original,'id':SCHEDULE_ID})


def test_disabled_embedding_schedule_cannot_block_other_worker_jobs(indexed):
    from czero_core.jobs import JobService
    from czero_core.worker import Worker
    from czero_core.embeddings import SCHEDULE_ID
    from czero_app.job_handlers import build_registry
    store,search,_=indexed;_,wiki,_=search
    registry=build_registry(store.database)
    jobs=JobService(store.database,registry,wiki[0].access);created=[]
    with store.database.engine.connect() as c:
        original=dict(c.execute(text('SELECT enabled,interval_seconds,next_run_at FROM c0_scheduled_tasks WHERE id=:id'),{'id':SCHEDULE_ID}).mappings().one())
        previous=set(c.execute(text('SELECT job_id FROM c0_task_runs WHERE schedule_id=:id'),{'id':SCHEDULE_ID}).scalars())
    try:
        health=jobs.enqueue(wiki[1],'health',{},'health-'+uuid4().hex);created.append(health['id'])
        jobs.update_schedule(wiki[1],SCHEDULE_ID,enabled=True,interval_seconds=60)
        with store.database.engine.begin() as c:
            c.execute(text("UPDATE c0_scheduled_tasks SET next_run_at=now()-interval '1 second' WHERE id=:id"),{'id':SCHEDULE_ID})
        assert Worker(store.database,registry).tick(max_jobs=2)==2
        runs=jobs.task_runs(wiki[1],SCHEDULE_ID)
        result=jobs.get_job(wiki[1],runs[0]['job_id'])
        assert result['state']=='succeeded' and result['result']=={'status':'disabled','indexed':0}
        assert jobs.get_job(wiki[1],health['id'])['state']=='succeeded'
    finally:
        with store.database.engine.begin() as c:
            created.extend(key for key in c.execute(text('SELECT job_id FROM c0_task_runs WHERE schedule_id=:id'),{'id':SCHEDULE_ID}).scalars() if key not in previous)
            for key in created:c.execute(text('DELETE FROM c0_jobs WHERE id=:id'),{'id':key})
            c.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled,interval_seconds=:interval_seconds,next_run_at=:next_run_at WHERE id=:id'),{**original,'id':SCHEDULE_ID})


def test_native_completion_drains_a_corpus_larger_than_four_batches(indexed,monkeypatch):
    from pathlib import Path
    import runpy
    from czero_core.jobs import JobService,default_registry
    from czero_core.worker import Worker
    store,fixtures,_=indexed;_,wiki,_=fixtures
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
    native=runpy.run_path(str(Path(__file__).parents[1]/'retrieval_fixture.py'))
    registry=default_registry();register_embedding_handlers(registry,store)
    jobs=JobService(store.database,registry,wiki[0].access);created=[]
    # Every pass prepares at most two Wiki revisions. Four successful jobs
    # cannot finish the larger corpus created by independent native clients.
    for ordinal in range(20):create_page(wiki,title='Consolidated '+str(ordinal),body='alpha retained evidence')
    with store.database.engine.begin() as c:
        store._activate(c)
        c.execute(text("UPDATE c0_scheduled_tasks SET enabled=false WHERE handler='embedding.index'"))
    def command(arguments):
        with store.database.engine.connect() as c:return 't' if c.execute(text(arguments[-1])).scalar_one() else 'f'
    native['index_complete'].__globals__['command']=command
    def enqueue():
        value=jobs.enqueue(wiki[1],'embedding.index',{},'native-complete-'+uuid4().hex);created.append(value['id']);return {**value,'id':str(value['id'])}
    def get(path):
        Worker(store.database,registry).tick(max_jobs=4,budget_seconds=5)
        return jobs.get_job(wiki[1],UUID(path.removeprefix('jobs/')))
    try:
        initial=[enqueue() for _ in range(4)]
        assert all(get('jobs/'+j['id'])['state']=='succeeded' for j in initial)
        assert native['index_complete']('disposable') is False
        submitted=native['complete_indexing']('disposable',get,enqueue)
        assert 4<submitted<=32 and native['index_complete']('disposable') is True
        with store.database.engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM c0_embeddings WHERE profile_id=:id'),{'id':store.profile_id}).scalar_one()==20
            assert c.execute(text("SELECT enabled FROM c0_scheduled_tasks WHERE handler='embedding.index'")).scalar_one() is False
    finally:
        with store.database.engine.begin() as c:
            for key in created:c.execute(text('DELETE FROM c0_jobs WHERE id=:id'),{'id':key})
