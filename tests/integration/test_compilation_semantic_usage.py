# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Current selected-page model reservations without reopening terminal knowledge."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.api_keys import ApiKeyService
from czero_core.compilation import CompilationConflict, CompilationDisabled, CompilationNotFound
from czero_core.current_content import ContentSuperseded
from czero_core.identity import PermissionDenied, Role
from czero_core.operations import ScopeDenied
from test_access import access, account_named, identity, record_unadmitted
from test_compilation import claim, checkpoint, enable, propose, support
from test_compilation_plans import compiler, coordinator_fixture, candidate, apply, verify
from test_sources import sources, upload, execute
from test_wiki import wiki, create_page


def selected(fixture, run=None, **policy):
    service,owner,now,_,pages=fixture
    if not service.policy(owner)['data']['enabled']:enable(fixture,**policy)
    page=create_page(pages,title='Current evidence-backed concept')
    run=run or claim(fixture,kind='weekly',cycle_key=now[0].date().isoformat())
    result=service.semantic_select(owner,{'lease':run['lease'],'expected_revision':run['run']['revision']},idempotency_key=uuid4().hex)
    return {**result,'lease':run['lease']},next(i for i in result['selection']['items'] if i['page_id']==str(page['id']))


def reserve(fixture, run, item, bindings, *, request=None, key=None, **extra):
    service,owner,*_=fixture
    data={'lease':run['lease'],'expected_revision':run['run']['revision'],'action':'reserve_model',
        'semantic_page_id':item['page_id'],'source_bindings':bindings,'request_id':request or str(uuid4()),'reserved_tokens':100,**extra}
    result=service.checkpoint(owner,data,idempotency_key=key or uuid4().hex)
    return {**result,'lease':run['lease']},data


def returned(fixture, run, request_id, **changes):
    run=checkpoint(fixture,run,'start_model',request_id=request_id)
    return checkpoint(fixture,run,'return_model',request_id=request_id,observed_tokens=73,external_reference_hash='a'*64,**changes)


def review(fixture, run, item, bindings, usage, **changes):
    service,owner,*_=fixture
    data={'lease':run['lease'],'expected_revision':run['run']['revision'],'page_id':item['page_id'],
        'revision':item['revision'],'content_id':item['wiki_revision_id'],'content_hash':item['content_hash'],
        'source_bindings':bindings,'usage_reservation_id':usage,'status':'reviewed','child_task_ids':[],**changes}
    result=service.semantic_review(owner,data,idempotency_key=uuid4().hex)
    return {**result,'lease':run['lease']}


def test_weekly_unchanged_terminal_creation_keeps_task_and_wiki_unchanged(compiler):
    service,owner,now,*_=compiler
    data,_=candidate(compiler)
    saved=apply(compiler,data)
    verified=verify(compiler,data,saved)
    checkpoint(compiler,{**verified,'lease':data['lease']},'finish')
    terminal=service.get_task(owner,saved['task']['id'])
    assert terminal['state']=='succeeded' and terminal['target']=={}
    bindings=data['plan']['source_bindings']
    run=claim(compiler,kind='weekly',cycle_key=now[0].date().isoformat())
    result=service.semantic_select(owner,{'lease':run['lease'],'expected_revision':run['run']['revision']},idempotency_key='select')
    run={**result,'lease':run['lease']};item=result['selection']['items'][0]
    run,request=reserve(compiler,run,item,bindings,key='semantic-reserve')
    assert run['run']['data']['calls'][request['request_id']]['task_id'] is None
    semantic=run['run']['data']['calls'][request['request_id']]['semantic']
    assert semantic['target']['id']==item['page_id'] and 'source_selections' in semantic
    assert 'Inventory evidence' not in str(semantic)
    assert service.checkpoint(owner,request,idempotency_key='semantic-reserve')['run']==run['run']
    run=returned(compiler,run,request['request_id'])
    run=review(compiler,run,item,bindings,request['request_id'])
    assert run['selection']['state']=='complete'
    complete=checkpoint(compiler,run,'finish')
    assert complete['outcome']=='completed_bounded' and not service.status(owner)['complete_corpus_coverage']
    assert service.get_task(owner,saved['task']['id'])==terminal
    with service.database.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM c0_wiki_revisions WHERE space_id=:space'),{'space':service._space_id}).scalar_one()==1
        assert connection.execute(text('SELECT count(*) FROM c0_compilation_tasks WHERE space_id=:space'),{'space':service._space_id}).scalar_one()==1
    budgets=service.status(owner)['budgets']
    assert all(b['data']['requests']==1 and b['data']['observed_tokens']==73 for b in budgets)


@pytest.mark.parametrize('change',['unselected','empty_sources','mixed_task','wrong_revision','manual_kind'])
def test_invalid_semantic_reservations_do_not_charge(compiler,change):
    service,owner,*_=compiler
    bindings,_=support(compiler)
    run,item=selected(compiler)
    extra={}
    if change=='unselected':item={**item,'page_id':str(uuid4())}
    elif change=='empty_sources':bindings=[]
    elif change=='mixed_task':extra={'task_id':str(uuid4()),'expected_task_revision':1}
    elif change=='wrong_revision':extra={'expected_revision':run['run']['revision']-1}
    elif change=='manual_kind':
        checkpoint(compiler,run,'partial')
        run=claim(compiler,cycle_key='ordinary-manual')
    before=deepcopy(service.status(owner)['budgets'])
    with pytest.raises((ValueError,CompilationConflict)):
        reserve(compiler,run,item,bindings,**extra)
    assert service.status(owner)['budgets']==before


@pytest.mark.parametrize('which',['daily_documents','weekly_documents'])
def test_semantic_source_reservations_observe_document_caps(compiler,which):
    service,owner,*_=compiler
    bindings,_=support(compiler)
    other,_=support(compiler,data=b'A second current original.')
    run,item=selected(compiler,**{which:1})
    run,request=reserve(compiler,run,item,bindings)
    run=checkpoint(compiler,run,'fail_model',request_id=request['request_id'])
    held,_=reserve(compiler,run,item,other)
    assert held['outcome']=='deferred_budget' and held['retryable']
    assert all(b['data']['requests']==1 for b in service.status(owner)['budgets'])
    assert len(held['run']['data']['calls'])==1
    with service.database.engine.connect() as connection:
        rows=connection.execute(text("SELECT metrics FROM c0_compilation_events WHERE space_id=:space AND kind='semantic_reserve'"),{'space':service._space_id}).scalars().all()
    assert set(i for row in rows for i in row['document_ids'])=={bindings[0]['logical_document_id']}
    assert set(i for row in rows for i in row['target_keys'])=={'page:'+item['page_id']}


def test_concurrent_task_and_semantic_calls_share_request_ceiling(compiler):
    service,owner,*_=compiler
    bindings,_=support(compiler)
    run,item=selected(compiler,concurrency=2,daily_model_requests=1,weekly_model_requests=1)
    propose(compiler,bindings,topic_key='another-concept')
    taskrun=claim(compiler,cycle_key='other-host')
    def task_request():
        return checkpoint(compiler,taskrun,'reserve_model',taskrun['tasks'][0],request_id=str(uuid4()),reserved_tokens=100)
    def semantic_request():
        return reserve(compiler,run,item,bindings)[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(task_request);second=pool.submit(semantic_request)
        results=[first.result(),second.result()]
    assert sorted(r['outcome'] for r in results)==['deferred_budget','reserve_model']
    budgets={b['kind']:b['data'] for b in service.status(owner)['budgets']}
    assert budgets['budget_day']['requests']==1
    assert budgets['budget_week']['requests']==int(results[1]['outcome']=='reserve_model')


def test_unresolved_semantic_call_excludes_second_call_for_same_page(compiler):
    service,owner,*_=compiler
    bindings,_=support(compiler)
    run,item=selected(compiler)
    run,request=reserve(compiler,run,item,bindings)
    with pytest.raises(CompilationConflict):reserve(compiler,run,item,bindings)
    assert len(service.status(owner)['runs'][0]['data']['calls'])==1
    run=returned(compiler,run,request['request_id'])
    _,second=reserve(compiler,run,item,bindings)
    assert second['request_id']!=request['request_id']


@pytest.mark.parametrize('point',['reserve','start','reserve_replay','start_replay'])
def test_source_replacement_rejects_semantic_inference_and_replay(compiler,point):
    service,owner,_,source,*_=compiler
    bindings,row=support(compiler)
    run,item=selected(compiler)
    request=None
    if point!='reserve':run,request=reserve(compiler,run,item,bindings,key='original-reserve')
    start=None
    if point=='start_replay':
        start={'lease':run['lease'],'expected_revision':run['run']['revision'],'action':'start_model','request_id':request['request_id']}
        result=service.checkpoint(owner,start,idempotency_key='original-start');run={**result,'lease':run['lease']}
    replacement=upload(source,data=b'Changed original.',source_id=row['source_id'],expected_revision=1)
    execute(source,'source.extract',replacement['id'])
    with pytest.raises(ContentSuperseded):
        if point=='reserve':reserve(compiler,run,item,bindings)
        elif point=='start':checkpoint(compiler,run,'start_model',request_id=request['request_id'])
        elif point=='reserve_replay':service.checkpoint(owner,request,idempotency_key='original-reserve')
        else:service.checkpoint(owner,start,idempotency_key='original-start')


def test_authored_page_edit_prevents_started_semantic_call(compiler):
    service,owner,_,_,pages=compiler
    bindings,_=support(compiler)
    run,item=selected(compiler)
    run,request=reserve(compiler,run,item,bindings)
    pages[0].update_page(owner,item['page_id'],'Authored edit','Preserved authored knowledge.',
        expected_revision=item['revision'],idempotency_key='authored-change')
    with pytest.raises((CompilationConflict,ContentSuperseded)):
        checkpoint(compiler,run,'start_model',request_id=request['request_id'])


def test_semantic_usage_requires_matching_page_sources_and_returned_call(compiler):
    service,owner,*_=compiler
    bindings,_=support(compiler)
    other,_=support(compiler,data=b'Other unbound evidence.')
    run,item=selected(compiler)
    run,request=reserve(compiler,run,item,bindings)
    with pytest.raises(CompilationConflict):review(compiler,run,item,bindings,request['request_id'])
    run=returned(compiler,run,request['request_id'])
    with pytest.raises(CompilationConflict):review(compiler,run,item,other,request['request_id'])
    assert review(compiler,run,item,bindings,request['request_id'])['selection']['state']=='complete'


def test_expired_fence_recovery_preserves_uncertain_semantic_debit(compiler):
    service,owner,now,*_=compiler
    bindings,_=support(compiler)
    run,item=selected(compiler)
    run,request=reserve(compiler,run,item,bindings,key='old-reserve')
    run=checkpoint(compiler,run,'start_model',request_id=request['request_id'])
    now[0]+=timedelta(minutes=6)
    with pytest.raises(CompilationConflict):service.checkpoint(owner,request,idempotency_key='old-reserve')
    recovered=claim(compiler,kind='weekly',cycle_key=now[0].date().isoformat())
    assert recovered['lease']['fencing_generation']>run['lease']['fencing_generation']
    assert recovered['run']['data']['calls'][request['request_id']]['state']=='uncertain'
    recovered=checkpoint(compiler,recovered,'reconcile_returned',request_id=request['request_id'],
        observed_tokens=73,external_reference_hash='a'*64)
    complete=review(compiler,recovered,item,bindings,request['request_id'])
    assert checkpoint(compiler,complete,'finish')['outcome']=='completed_bounded'
    assert all(b['data']['requests']==1 for b in service.status(owner)['budgets'])


def test_reader_and_read_only_key_cannot_reserve_semantic_model(compiler):
    service,owner,*_=compiler
    bindings,_=support(compiler)
    run,item=selected(compiler)
    account_key=uuid4()
    record_unadmitted(service.access,account_key,'semantic-reader')
    account=account_named(service.access,owner,'semantic-reader')
    service.access.set_role(owner,account['id'],Role.READER)
    reader=service.access.resolve(identity(service.access,account_key,'semantic-reader'))
    data={'lease':run['lease'],'expected_revision':run['run']['revision'],'action':'reserve_model',
        'semantic_page_id':item['page_id'],'source_bindings':bindings,'request_id':str(uuid4()),'reserved_tokens':100}
    with pytest.raises(PermissionDenied):service.checkpoint(reader,data,idempotency_key='reader-denied')
    keys=ApiKeyService(service.access,client_id='fixture',client_secret='synthetic',resource='https://example.test/mcp')
    key=keys.create(owner,name='Read only',scopes={'c0:read'},space_ids=[str(service._space_id)])['key']
    restricted=keys.verify(key,resource=keys.resource).actor
    with pytest.raises(ScopeDenied):service.checkpoint(restricted,data,idempotency_key='key-denied')
    assert all(b['data']['requests']==0 for b in service.status(owner)['budgets'])


def test_semantic_source_binding_from_another_authorized_space_is_rejected(compiler):
    from czero_core.spaces import SpaceService
    service,owner,now,source,pages=compiler
    run,item=selected(compiler)
    with service.database.engine.connect() as connection:other=SpaceService.shared_id(connection)
    foreign_source=(source[0].in_space(other),*source[1:])
    foreign=(service.in_space(other),owner,now,foreign_source,pages)
    bindings,_=support(foreign,data=b'Original in a different authorized space.')
    with pytest.raises(CompilationNotFound):reserve(compiler,run,item,bindings)
    assert all(b['data']['requests']==0 for b in service.status(owner)['budgets'])


@pytest.mark.parametrize('limit',['daily_model_tokens','weekly_model_tokens'])
def test_semantic_model_token_hold_reserves_no_source_or_provider_debit(compiler,limit):
    service,owner,*_=compiler
    bindings,_=support(compiler)
    run,item=selected(compiler,**{limit:1})
    held,_=reserve(compiler,run,item,bindings)
    assert held['outcome']=='deferred_budget' and held['retryable']
    assert 'task' not in held
    assert held['run']['data']['calls']=={}
    assert all(b['data']['requests']==0 and b['data']['charged_tokens']==0 for b in service.status(owner)['budgets'])
    with service.database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM c0_compilation_events WHERE space_id=:space AND kind='model_reserve'"),{'space':service._space_id}).scalar_one()==0
        assert connection.execute(text("SELECT count(*) FROM c0_compilation_events WHERE space_id=:space AND kind='semantic_reserve' AND metrics->'document_ids'<>'[]'::jsonb"),{'space':service._space_id}).scalar_one()==0


def test_disabled_policy_and_disallowed_page_target_stop_semantic_inference(compiler):
    service,owner,*_=compiler
    bindings,_=support(compiler)
    run,item=selected(compiler,profile_id='sourced-knowledge-v1',allowed_target_kinds=['entity'])
    with pytest.raises(CompilationDisabled):reserve(compiler,run,item,bindings)
    enable(compiler,enabled=False)
    with pytest.raises(CompilationDisabled):reserve(compiler,run,item,bindings)
    assert all(b['data']['requests']==0 for b in service.status(owner)['budgets'])


def test_semantic_reservation_id_cannot_be_reused_for_a_task_model(compiler):
    bindings,_=support(compiler)
    run,item=selected(compiler,concurrency=2)
    _,request=reserve(compiler,run,item,bindings)
    propose(compiler,bindings,topic_key='independent-task')
    other=claim(compiler,cycle_key='another-run')
    with pytest.raises(CompilationConflict):
        checkpoint(compiler,other,'reserve_model',other['tasks'][0],request_id=request['request_id'],reserved_tokens=100)
