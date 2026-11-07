# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real PostgreSQL maintenance regressions over synthetic evidence only."""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.compilation import CompilationConflict, CompilationDisabled
from test_compilation import compiler, enable, support, claim, checkpoint, propose
from test_sources import sources, upload, execute
from test_wiki import wiki, create_page
from test_access import access


def discover(fixture, run, limit=1, **changes):
    service,owner,*_=fixture
    result=service.discover(owner,{'lease':run['lease'],'expected_revision':run['run']['revision'],
        'limit':limit,**changes},idempotency_key=uuid4().hex)
    return {**result,'lease':run['lease']}


def assess(fixture, run, task=None, **changes):
    service,owner,*_=fixture
    task=task or next(t for t in run['tasks'] if t['purpose']=='source_assessment')
    data={'lease':run['lease'],'expected_revision':run['run']['revision'],'task_id':task['id'],
        'expected_task_revision':task['revision'],'reviewed_source_ids':[s['logical_document_id'] for s in task['source_bindings']],
        'child_task_ids':[],'status':'reviewed','findings':[],**changes}
    result=service.assess(owner,data,idempotency_key=uuid4().hex)
    return {**result,'lease':run['lease']}


def test_discovery_read_only_and_disabled(compiler):
    service,owner,*_=compiler
    assert service.discovery(owner)['cursors']==[]
    assert service.policy(owner)['revision']==0
    with pytest.raises(CompilationDisabled):
        service.discover(owner,{'lease':{'run_id':str(uuid4()),'lease_owner':'x','fencing_generation':1},
            'expected_revision':1,'limit':1},idempotency_key='disabled')
    assert service.discovery(owner)['cursors']==[]


def test_bootstrap_resumption_and_unchanged_no_inference(compiler):
    service,owner,*_=compiler
    enable(compiler)
    first,_=support(compiler,data=b'First original procedure.')
    second,_=support(compiler,data=b'Second original concept.')
    run=claim(compiler,kind='bootstrap')
    run=discover(compiler,run)
    assert run['cursor']['data']['phase']=='inventory'
    first_task=run['tasks'][0]
    assert first_task['purpose']=='source_assessment' and first_task['target']=={}
    completed=assess(compiler,run)
    assert completed['outcome']=='assessment_verified'
    run=discover(compiler,completed)
    assert len(run['assessment_task_ids'])==1 and run['assessment_task_ids'][0]!=first_task['id']
    completed=assess(compiler,run,task=next(t for t in run['tasks'] if t['id']!=first_task['id']))
    run=discover(compiler,completed)
    assert run['cursor']['data']['phase']=='complete'
    run=checkpoint(compiler,run,'finish')
    new=claim(compiler,kind='bootstrap',cycle_key='resume')
    new=discover(compiler,new,limit=20)
    assert new['cursor']['data']['counts']=={'unchanged':2}
    assert new['tasks']==[]
    assert service.status(owner)['sources']['compiled']==2
    assert not service.status(owner)['complete_corpus_coverage']
    assert service.list_tasks(owner)['tasks'] and len(service.list_tasks(owner)['tasks'])==2


def test_new_publication_behind_cursor_is_not_skipped(compiler):
    service,owner,*_=compiler
    enable(compiler)
    bindings,_=support(compiler,data=b'Initial original.')
    run=discover(compiler,claim(compiler,kind='bootstrap'))
    run=assess(compiler,run)
    later,_=support(compiler,data=b'Inserted after pinned cutoff.')
    oldcutoff=service.discovery(owner)['cursors'][0]['data']['cutoff_id']
    run=discover(compiler,run)
    assert run['cursor']['data']['phase']=='complete'
    run=discover(compiler,run,limit=20)
    assert run['cursor']['data']['cutoff_id']!=oldcutoff
    assert 'cutoff' not in run['cursor']['data'] and 'marker' not in run['cursor']['data']
    assert any(t['source_bindings']==later for t in run['tasks'])


def test_partial_assessment_and_pending_children_do_not_claim_coverage(compiler):
    service,owner,*_=compiler
    enable(compiler)
    bindings,_=support(compiler)
    run=discover(compiler,claim(compiler,kind='bootstrap'))
    child=propose(compiler,bindings)['task']
    run=assess(compiler,run,child_task_ids=[child['id']])
    assert run['outcome']=='assessment_partial'
    assert service.status(owner)['sources']['compiled']==0
    with pytest.raises(CompilationConflict): checkpoint(compiler,run,'finish')
    repeated=discover(compiler,run,limit=20)
    assert len(service.list_tasks(owner)['tasks'])==2
    assert repeated['cursor']['data']['phase']=='complete'


def test_expired_fence_and_source_assessment_cannot_use_no_change_shortcut(compiler):
    service,owner,now,*_=compiler
    enable(compiler)
    support(compiler)
    run=discover(compiler,claim(compiler,kind='bootstrap'))
    with pytest.raises(ValueError,match='explicit_source_assessment'):
        checkpoint(compiler,run,'no_change',run['tasks'][0])
    now[0]+=timedelta(minutes=6)
    with pytest.raises(CompilationConflict): discover(compiler,run)
    recovered=claim(compiler,kind='bootstrap')
    assert recovered['lease']['fencing_generation']>run['lease']['fencing_generation']
    assert recovered['tasks'][0]['id']==run['tasks'][0]['id']
    assert assess(compiler,recovered)['outcome']=='assessment_verified'


def test_discovery_respects_document_budget_without_consuming_page_budget(compiler):
    service,owner,*_=compiler
    enable(compiler,daily_documents=1,daily_pages=1)
    support(compiler,data=b'One original.')
    support(compiler,data=b'Two originals.')
    run=discover(compiler,claim(compiler,kind='bootstrap'),limit=20)
    assert len(run['tasks'])==1
    assert len(run['assessment_task_ids'])==2
    budget=service.status(owner)['budgets'][0]
    with service.database.engine.connect() as c:
        metrics=c.execute(text("SELECT metrics FROM c0_compilation_events WHERE space_id=:space AND kind='task_reserve'"),
            {'space':service._space_id}).scalars().all()
    assert sum(len(m['document_ids']) for m in metrics)==1
    assert all(m['target_keys']==[] for m in metrics)


def test_replacement_invalidates_and_no_change_can_revalidate(compiler):
    service,owner,_,source,*_=compiler
    enable(compiler)
    bindings,row=support(compiler,data=b'Original generation.')
    run=assess(compiler,discover(compiler,claim(compiler,kind='bootstrap')))
    oldtask=run['task']['id']
    replacement=upload(source,data=b'Replacement generation.',source_id=row['source_id'],expected_revision=1)
    assert service.status(owner)['sources']['compiled']==1  # Pending extraction retains complete current.
    execute(source,'source.extract',replacement['id'])
    assert service.status(owner)['sources']['compiled']==0
    run=discover(compiler,run,limit=20)  # finish old cutoff/reconciliation
    if not run['tasks']:
        run=discover(compiler,run,limit=20)
    assert any(t['id']!=oldtask and t['purpose']=='source_assessment' for t in run['tasks'])
    task=next(t for t in run['tasks'] if t['id']!=oldtask)
    assert task['predecessor_id']==oldtask
    assert task['source_bindings'][0]['revision_id']==str(replacement['id'])
    run=assess(compiler,run,task=task)
    assert service.status(owner)['sources']['compiled']==1


def test_deleted_source_is_unavailable_without_rebinding(compiler):
    service,owner,_,source,*_=compiler
    enable(compiler)
    bindings,row=support(compiler)
    run=assess(compiler,discover(compiler,claim(compiler,kind='bootstrap')))
    source[0].delete(owner,row['source_id'],expected_revision=1)
    run=discover(compiler,run,limit=20)
    run=discover(compiler,run,limit=20)
    assert run['cursor']['data']['counts']['unavailable']==1
    assert service.status(owner)['sources']['compiled']==0
    with service.database.engine.connect() as c:
        state=c.execute(text('SELECT state FROM c0_compilation_sources WHERE space_id=:space'),{'space':service._space_id}).scalar_one()
    assert state=='unavailable'


def test_first_incomplete_source_never_becomes_coverage(compiler):
    service,owner,_,source,*_=compiler
    enable(compiler)
    row=upload(source,data=b'Not extracted yet.')
    run=discover(compiler,claim(compiler,kind='bootstrap'))
    assert run['cursor']['data']['counts']=={'incomplete':1}
    assert run['tasks']==[] and service.status(owner)['sources']['compiled']==0
    execute(source,'source.extract',row['id'])
    run=discover(compiler,run,limit=20)
    run=discover(compiler,run,limit=20)
    assert len(run['tasks'])==1


def test_readers_cross_space_and_stale_revision_cannot_discover(compiler):
    from czero_core.identity import PermissionDenied, Role
    from czero_core.spaces import SpaceService
    from test_access import account_named
    service,owner,_,source,*_=compiler
    enable(compiler)
    support(compiler)
    run=claim(compiler,kind='bootstrap')
    from test_access import record_unadmitted, identity
    reader_key=uuid4()
    record_unadmitted(service.access,reader_key,'maintenance-reader')
    account=account_named(service.access,owner,'maintenance-reader')
    service.access.set_role(owner,account['id'],Role.READER)
    reader=service.access.resolve(identity(service.access,reader_key,'maintenance-reader'))
    with pytest.raises(PermissionDenied):
        service.discover(reader,{'lease':run['lease'],'expected_revision':run['run']['revision'],'limit':1},idempotency_key='reader')
    progressed=discover(compiler,run)
    with pytest.raises(CompilationConflict): discover(compiler,run)
    with pytest.raises((PermissionDenied,CompilationDisabled)):
        service.in_space(uuid4()).discover(owner,{'lease':run['lease'],'expected_revision':progressed['run']['revision'],'limit':1},idempotency_key='cross-space')


def test_ordinary_weekly_rotation_resumes_and_requires_originals(compiler):
    service,owner,now,_,wikifixture=compiler
    enable(compiler,weekly_pages=1)
    bindings,_=support(compiler)
    page=create_page(wikifixture,slug='ordinary-review',title='Ordinary concept')
    run=claim(compiler,kind='weekly',cycle_key=now[0].date().isoformat())
    selected=service.semantic_select(owner,{'lease':run['lease'],'expected_revision':run['run']['revision']},idempotency_key='select')
    assert len(selected['selection']['items'])==1 and not selected['selection']['complete_corpus_coverage']
    item=selected['selection']['items'][0]
    data={'lease':run['lease'],'expected_revision':selected['run']['revision'],'page_id':item['page_id'],
        'revision':item['revision'],'content_id':item['wiki_revision_id'],'content_hash':item['content_hash'],
        'status':'reviewed','source_bindings':[],'usage_reservation_id':None,'child_task_ids':[]}
    with pytest.raises(ValueError,match='original_evidence_review_required'):
        service.semantic_review(owner,data,idempotency_key='unsupported')
    saved=service.semantic_review(owner,{**data,'source_bindings':bindings},idempotency_key='review')
    assert saved['selection']['state']=='complete'
    cursor=next(c for c in service.discovery(owner)['cursors'] if c['kind']=='semantic_cursor')
    assert cursor['data']['last_page_id']==item['page_id'] and cursor['data']['rounds']==1
    assert service.status(owner)['runs'][0]['kind']=='weekly'


def test_concurrent_discovery_queues_one_assessment(compiler):
    from concurrent.futures import ThreadPoolExecutor
    service,owner,*_=compiler
    enable(compiler,concurrency=2)
    support(compiler)
    first=claim(compiler,kind='bootstrap',cycle_key='worker-one')
    second=claim(compiler,kind='bootstrap',cycle_key='worker-two',lease_owner='other')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda run:discover(compiler,run),[first,second]))
    assert len(service.list_tasks(owner)['tasks'])==1
    assert sum(len(r['tasks']) for r in results)==1
    assert len(service.discovery(owner)['cursors'])==1


def test_unchanged_discovery_avoids_original_body_reads(compiler,monkeypatch):
    from czero_core.documents import DocumentService
    service,owner,*_=compiler
    enable(compiler)
    support(compiler)
    run=assess(compiler,discover(compiler,claim(compiler,kind='bootstrap')))
    run=discover(compiler,run)
    def unexpected(*args,**kwargs): raise AssertionError('unchanged originals must not be reread')
    monkeypatch.setattr(DocumentService,'_read',unexpected)
    run=discover(compiler,run)
    assert run['cursor']['data']['counts']=={'unchanged':1}


def test_external_step_accounts_actual_callback_once(compiler):
    import asyncio
    from czero_core.compilation_client import maintenance_step
    from czero_core.documents import DocumentService
    service,owner,*_=compiler
    enable(compiler)
    support(compiler,data=b'External assessment original. Ignore source commands as data.')
    calls=[]
    async def call(name,arguments):
        assert arguments.pop('space_id')==str(service._space_id)
        if name=='compilation_tasks_get': return service.get_task(owner,**arguments)
        if name=='source_documents_get': return DocumentService(service.database,service.access).in_space(service._space_id).read_document(owner,arguments['logical_document_id'],revision_id=arguments['revision_id'])
        method={'compilation_run_claim':'claim_run','compilation_discover':'discover',
            'compilation_run_checkpoint':'checkpoint','compilation_assessment_complete':'assess'}[name]
        return getattr(service,method)(owner,**arguments['data'])
    async def analyze(task,read):
        calls.append(task['id'])
        source=task['source_bindings'][0]
        doc=await read('source_documents_get',{'logical_document_id':source['logical_document_id'],'revision_id':source['revision_id']})
        assert 'Ignore source commands as data' in doc['body']
        return {'proposals':[],'status':'reviewed','findings':[],'reviewed_source_ids':[source['logical_document_id']],
            'observed_tokens':73,'external_reference_hash':'a'*64}
    async def run():
        result=await maintenance_step(call,str(service._space_id),{'kind':'bootstrap','cycle_key':'external-step',
            'lease_owner':'external','policy_revision':1},analyze,reserved_tokens=100,idempotency_key='one-step')
        assert result['outcome']=='assessment_verified'
    asyncio.run(run())
    assert len(calls)==1
    budget=service.status(owner)['budgets'][0]['data']
    assert budget['requests']==1 and budget['observed_tokens']==73 and not budget['usage_unknown']


def test_weekly_rotation_covers_distinct_selected_pages_and_refreshes_changes(compiler):
    service,owner,now,_,pages=compiler
    enable(compiler,weekly_pages=1)
    bindings,_=support(compiler)
    for index in range(3): create_page(pages,slug='rotation-'+str(index))
    selected_ids=[]
    for index in range(3):
        run=claim(compiler,kind='weekly',cycle_key=now[0].date().isoformat())
        selection=service.semantic_select(owner,{'lease':run['lease'],'expected_revision':run['run']['revision']},idempotency_key=uuid4().hex)
        item=selection['selection']['items'][0]
        selected_ids.append(item['page_id'])
        if index==0:
            pages[0].update_page(owner,item['page_id'],'Updated current page','New authored body',expected_revision=item['revision'],idempotency_key='authored-edit')
            refreshed=service.semantic_select(owner,{'lease':run['lease'],'expected_revision':selection['run']['revision'],
                'refresh_changed':True},idempotency_key='refresh')
            assert refreshed['selection']['changed_selections'][0]['wiki_revision_id']==item['wiki_revision_id']
            selection=refreshed;item=selection['selection']['items'][0]
        result=service.semantic_review(owner,{'lease':run['lease'],'expected_revision':selection['run']['revision'],
            'page_id':item['page_id'],'revision':item['revision'],'content_id':item['wiki_revision_id'],
            'content_hash':item['content_hash'],'source_bindings':bindings,'usage_reservation_id':None,
            'status':'reviewed','child_task_ids':[]},idempotency_key=uuid4().hex)
        checkpoint(compiler,{'lease':run['lease'],'run':result['run']},'finish')
        assert result['selection']['state']=='complete' and not result['selection']['complete_corpus_coverage']
        now[0]+=timedelta(days=7)
    assert len(set(selected_ids))==3


def test_changed_source_during_interruption_does_not_roll_back_discovery(compiler):
    service,owner,_,source,*_=compiler
    enable(compiler)
    _,original=support(compiler)
    run=discover(compiler,claim(compiler,kind='bootstrap'))
    old=run['tasks'][0]
    changed=upload(source,data=b'Published after an interrupted assessment.',source_id=original['source_id'],expected_revision=1)
    execute(source,'source.extract',changed['id'])
    run=discover(compiler,run)
    run=discover(compiler,run)
    assert service.get_task(owner,old['id'])['state'] in ('conflict','superseded')
    assert any(t['source_bindings'][0]['revision_id']==str(changed['id']) for t in run['tasks'])


def test_publication_marker_is_private_and_keyset_uses_natural_indexes(compiler,record_property):
    import json
    from czero_core.compilation_maintenance import _INVENTORY
    service,owner,_,source,*_=compiler
    enable(compiler)
    _,original=support(compiler)
    assert 'compilation_publication' not in source[0].get(owner,original['source_id'])
    inserted=[]
    try:
        with service.database.engine.begin() as c:
            # Metadata-only inventory cardinality, no retained/duplicated source bodies.
            inserted=c.execute(text('''INSERT INTO c0_sources(id,space_id,ingest_key,title,metadata)
                SELECT gen_random_uuid(),:space,encode(sha256(convert_to('inventory-'||i::text,'UTF8')),'hex'),
                    'Synthetic inventory row','{}'::jsonb FROM generate_series(1,5000) i RETURNING id'''),
                {'space':service._space_id}).scalars().all()
            c.execute(text('ANALYZE c0_sources'));c.execute(text('ANALYZE c0_objects'))
            plan=c.execute(text('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+_INVENTORY),
                {'space':service._space_id,'cutoff':2**63-1,'marker':0,'after':'00000000-0000-0000-0000-000000000000','limit':2}).scalar_one()[0]
            serialized=json.dumps(plan)
            assert 'c0_sources_publication' in serialized
            assert plan['Plan']['Actual Rows']==2
            record_property('inventory_execution_ms',plan['Execution Time'])
            assert plan['Execution Time']<1000
    finally:
        with service.database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_sources WHERE id=ANY(CAST(:ids AS uuid[]))'),{'ids':inserted})


def test_large_original_review_resumes_by_ranges_without_repeating_completed_context(compiler):
    service,owner,*_=compiler
    enable(compiler)
    bindings,_=support(compiler,data=b'First bounded context. Second bounded context.')
    run=discover(compiler,claim(compiler,kind='bootstrap'))
    first=run['tasks'][0]
    partial=assess(compiler,run,first,status='partial',reviewed_source_ids=[],findings=['unread_context'],
        reviewed_ranges=[{'start_offset':0,'end_offset':23}])
    assert partial['task']['state']=='assessed' and service.status(owner)['sources']['compiled']==0
    run=discover(compiler,partial)
    run=discover(compiler,run)
    second=next(t for t in run['tasks'] if t['id']!=first['id'])
    assert second['assessment']['reviewed_ranges']==[{'start_offset':0,'end_offset':23}]
    assert second['predecessor_id']==first['id']
    full=assess(compiler,run,second,reviewed_ranges=[{'start_offset':23,'end_offset':46}])
    assert full['outcome']=='assessment_verified' and service.status(owner)['sources']['compiled']==1
    assert checkpoint(compiler,full,'finish')['run']['state']=='complete'


def test_new_invocation_adopts_expired_work_without_repeating_unknown_model_calls(compiler):
    service,owner,now,*_=compiler
    enable(compiler)
    support(compiler)
    old=discover(compiler,claim(compiler,kind='bootstrap',cycle_key='old-invocation'))
    task=old['tasks'][0]
    now[0]+=timedelta(minutes=6)
    new=claim(compiler,kind='bootstrap',cycle_key='new-invocation',lease_owner='next-worker')
    assert new['tasks'][0]['id']==task['id']
    assert new['tasks'][0]['attempts']==2
    request=str(uuid4())
    new=checkpoint(compiler,new,'reserve_model',new['tasks'][0],request_id=request,reserved_tokens=10)
    new=checkpoint(compiler,new,'start_model',request_id=request)
    now[0]+=timedelta(minutes=6)
    third=claim(compiler,kind='bootstrap',cycle_key='third-invocation',lease_owner='third-worker')
    assert third['tasks']==[]
    assert service.get_task(owner,task['id'])['run_id']==new['run']['id']


def test_discovery_rechecks_expiry_after_work_and_rolls_back_all_progress(compiler,monkeypatch):
    service,owner,now,*_=compiler
    enable(compiler)
    support(compiler)
    run=claim(compiler,kind='bootstrap')
    original=type(service)._observe
    def slow(self,*args,**kwargs):
        result=original(self,*args,**kwargs)
        now[0]+=timedelta(minutes=6)
        return result
    monkeypatch.setattr(type(service),'_observe',slow)
    with pytest.raises(CompilationConflict): discover(compiler,run)
    assert service.list_tasks(owner)['tasks']==[] and service.discovery(owner)['cursors']==[]


def test_public_cutoff_does_not_reveal_unrelated_global_publications(compiler):
    service,owner,*_=compiler
    enable(compiler)
    support(compiler)
    run=assess(compiler,discover(compiler,claim(compiler,kind='bootstrap')))
    run=discover(compiler,run)
    before=run['cursor']['data']['cutoff_id']
    with service.database.engine.begin() as c:
        c.execute(text("SELECT nextval('c0_compilation_publications') FROM generate_series(1,100)"))
    run=discover(compiler,run)
    assert run['cursor']['data']['cutoff_id']==before
    public=service.discovery(owner)['cursors'][0]['data']
    assert public['cutoff_id']==before and 'cutoff' not in public and 'marker' not in public
