# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Research policy and concurrency exercised against actual PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
import pytest
from czero_core.projects import ProjectConflict
from test_projects import project, initialize, topic
from test_access import access


def candidate(stable_id,**changes):
    return {'stable_id':stable_id,'topic_id':'anchor','question':'What changed in '+stable_id+'?',
        'kind':'investigation','origin':'user','origin_reference':'synthetic:user', 'priority':20,
        'priority_reason':'Within approved scope','urgency_reason':'','parent_ids':[],'related_pages':[],
        'not_before':'','due_at':'','question_conditions':'','entity_version':'','time_window':'',
        'assessment_ref':'synthetic:assessment','direct_contribution':'Tests approved anchor',
        'anchor_ids':['anchor'],'novelty_key':stable_id,'novelty_refs':['synthetic:primary-evidence'],
        'root_reason':'user_request','authorization_ref':'synthetic:user-turn','excluded':False,
        'semantic_matches':[],'independent_parents':[],**changes}


def setup(project):
    initialize(project);service,manifest,owner,_=project;topic(service,owner)
    return service,owner


def claim(service,owner,**changes):
    result=service.claim_run(owner,'daily','worker-one',1,idempotency_key=uuid4().hex,**changes)
    run=result['records'][0]['data']
    return {key:run[key] for key in ('run_id','lease_owner','fencing_generation')}


def row(result,kind):
    return next(r for r in result['records'] if r['type_name']=='c0_project_'+kind)


def admit(service,owner,stable_id,**changes):
    return service.admit(owner,candidate(stable_id,**changes),idempotency_key=uuid4().hex)


def reserve(service,owner,lease,**changes):
    return service.reserve(owner,lease,idempotency_key=uuid4().hex,**changes)


def test_ordinary_budget_and_replay_do_not_replenish(project):
    service,owner=setup(project);lease=claim(service,owner)
    for index in range(7):admit(service,owner,'ordinary-'+str(index))
    for index in range(5):
        result=service.reserve(owner,lease,idempotency_key='reserve:'+str(index))
        assert row(result,'attempt_v1')['data']['slot']==index+1
        assert service.reserve(owner,lease,idempotency_key='reserve:'+str(index))==result
    assert reserve(service,owner,lease)['status']=='BLOCKED'
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==5
    assert sum(r['data']['status']=='deferred' for r in service.list_records(owner,'queue_v1'))==2
    assert claim(service,owner)==lease
    assert reserve(service,owner,lease)['status']=='BLOCKED'


def test_mixed_urgent_extra_slots_exclusively_urgent(project):
    service,owner=setup(project);lease=claim(service,owner)
    for index in range(6):admit(service,owner,'routine-'+str(index))
    admit(service,owner,'urgent-first',priority=0,urgency_reason='Time-sensitive primary event')
    assert row(reserve(service,owner,lease),'attempt_v1')['data']['priority']==0
    for _ in range(4):assert row(reserve(service,owner,lease),'attempt_v1')['data']['priority']==20
    assert reserve(service,owner,lease)['status']=='BLOCKED'
    for index in range(6):admit(service,owner,'urgent-extra-'+str(index),priority=0,urgency_reason='Deadline')
    for slot in range(6,11):
        attempt=row(reserve(service,owner,lease),'attempt_v1')['data']
        assert (attempt['slot'],attempt['priority'])==(slot,0)
    assert reserve(service,owner,lease)['outcome']=='daily_budget_exhausted'


def test_lineage_children_urgency_and_depth(project):
    service,owner=setup(project)
    admit(service,owner,'root')
    for index in range(3):
        child=row(admit(service,owner,'child-'+str(index),parent_ids=['root'],origin='research',root_reason='derived'),'queue_v1')
        assert child['data']['expansion_priority']==40
    assert admit(service,owner,'fourth',parent_ids=['root'],origin='research',root_reason='derived')['outcome']=='archive_candidate'
    child=service.retune_queue(owner,'child-0',0,'New deadline','Time-sensitive',expected_revision=1,idempotency_key='urgent-child')
    assert row(child,'queue_v1')['data']['expansion_priority']==40
    previous='child-0'
    for depth in (60,80,100):
        current='depth-'+str(depth)
        child=row(admit(service,owner,current,parent_ids=[previous],origin='research',root_reason='derived'),'queue_v1')
        assert child['data']['expansion_priority']==depth;previous=current
    with pytest.raises(ValueError,match='expansion_priority_exhausted'):
        admit(service,owner,'too-deep',parent_ids=[previous],origin='research',root_reason='derived')


def test_deduplication_and_semantic_match_preserve_original_lineage(project):
    service,owner=setup(project)
    first=row(admit(service,owner,'original'), 'queue_v1')
    same=admit(service,owner,'renamed',question=candidate('original')['question'])
    assert same['outcome']=='merge' and row(same,'queue_v1')['id']==first['id']
    semantic=admit(service,owner,'paraphrase',question='Investigate the same development',semantic_matches=[{
        'target_id':'original','equivalent':True,'new_evidence':True,'assessment_ref':'synthetic:check','reason':'Same question'}])
    assert semantic['outcome']=='merge' and row(semantic,'queue_v1')['data']['root_ids']==['original']
    assert len(service.list_records(owner,'queue_v1'))==1


def test_capacity_preserves_explicit_requests_and_initialization_cap(project):
    service,owner=setup(project);manifest=service.get(owner)
    updated=deepcopy(manifest['data']['manifest']);updated['research']['max_active_items']=1
    service.configure(owner,updated,expected_revision=1,authorization_ref='synthetic:user',idempotency_key='small')
    admit(service,owner,'first');deferred=admit(service,owner,'second')
    assert deferred['outcome']=='defer_capacity' and row(deferred,'queue_v1')['data']['status']=='deferred'
    assert row(deferred,'admission_v1')['data']['candidate']['authorization_ref']=='synthetic:user-turn'
    other,manifest=project[3]();other.initialize(owner,manifest,authorization_ref='synthetic:setup',idempotency_key='setup');topic(other,owner)
    for index in range(6):
        result=admit(other,owner,'seed-'+str(index),origin='initialization',root_reason='approved_initialization')
        assert result['outcome']==('admit' if index<5 else 'defer_capacity')


def test_terminal_scope_and_archived_two_step_reactivation_rejected(project):
    service,owner=setup(project)
    peripheral=topic(service,owner,'outside',classification='peripheral',anchor_ids=['anchor'],
        direct_contribution='One-off question',assessment_ref='synthetic:scope')
    root=admit(service,owner,'one-off',topic_id='outside')
    assert row(root,'queue_v1')['data']['terminal']
    assert admit(service,owner,'descendant',parent_ids=['one-off'],origin='research',root_reason='derived')['outcome']=='archive_candidate'
    assert admit(service,owner,'automatic',topic_id='outside',origin='discovery',root_reason='independent_external_event')['outcome']=='reject_scope'
    values={k:v for k,v in peripheral['data'].items() if k not in ('key','schema_version','authorized_by','created_at','expires_at')}
    values['lifecycle']='archived';saved=service.set_topic(owner,values,expected_revision=1,idempotency_key='archive-outside')
    values['lifecycle']='provisional'
    with pytest.raises(ValueError):service.set_topic(owner,values,expected_revision=saved['revision'],idempotency_key='sneaky')


def test_concurrent_claim_and_reservation_have_one_winner(project):
    service,owner=setup(project)
    def work(worker):
        try:return service.claim_run(owner,'daily',worker,1,idempotency_key=worker)
        except ProjectConflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(work,['worker-a','worker-b']))
    assert sum(r is not None for r in results)==1
    run=next(r for r in results if r)['records'][0]['data'];lease={k:run[k] for k in ('run_id','lease_owner','fencing_generation')}
    admit(service,owner,'only-one')
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:reserve(service,owner,lease),range(2)))
    assert sum(r['outcome']=='attempt_reserved' for r in results)==1
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1


def test_stale_lease_cannot_replay_or_commit_and_uncertain_invocation_not_reissued(project):
    service,owner=setup(project);lease=claim(service,owner);admit(service,owner,'crash')
    attempt=row(service.reserve(owner,lease,idempotency_key='reserved'),'attempt_v1')['data']
    service.invocation(owner,lease,attempt['attempt_id'],'started',idempotency_key='started')
    now=service.clock();service.clock=lambda:now+timedelta(minutes=6)
    new=service.claim_run(owner,'daily','worker-two',1,idempotency_key='reclaim')['records'][0]['data']
    current={k:new[k] for k in ('run_id','lease_owner','fencing_generation')}
    assert current['fencing_generation']==2
    with pytest.raises(ProjectConflict):service.reserve(owner,lease,idempotency_key='reserved')
    resumed=reserve(service,owner,current,resume_attempt_id=attempt['attempt_id'])
    assert resumed['status']=='BLOCKED' and row(resumed,'attempt_v1')['data']['state']=='uncertain'
    with pytest.raises(ProjectConflict):service.invocation(owner,current,attempt['attempt_id'],'started',idempotency_key='duplicate-call')
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1


def test_non_result_reference_is_rejected_and_phase_checkpoint_readback(project):
    service,owner=setup(project);lease=claim(service,owner);admit(service,owner,'saved')
    attempt=row(reserve(service,owner,lease),'attempt_v1')['data']
    service.invocation(owner,lease,attempt['attempt_id'],'started',idempotency_key='start')
    stored=service.get(owner)['id']
    with pytest.raises(ValueError):service.invocation(owner,lease,attempt['attempt_id'],'returned',result_reference=stored,idempotency_key='returned')
    resumed=reserve(service,owner,lease,resume_attempt_id=attempt['attempt_id'])
    assert row(resumed,'attempt_v1')['data']['state']=='invoking'
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1
    first=service.checkpoint_run(owner,lease,'monitoring','SAVED',references=[stored],summary='Stored fixture',idempotency_key='phase')
    assert first==service.checkpoint_run(owner,lease,'monitoring','SAVED',references=[stored],summary='Stored fixture',idempotency_key='phase')
    assert row(first,'run_v1')['data']['current_phase']=='research'
    with pytest.raises(ProjectConflict):service.checkpoint_run(owner,lease,'report','SAVED',idempotency_key='skip')


def test_partial_checkpoint_can_resume_and_finish_same_phase(project):
    service,owner=setup(project);lease=claim(service,owner)
    service.checkpoint_run(owner,lease,'monitoring','PARTIAL',summary='Timeout',idempotency_key='partial')
    fresh=claim(service,owner)
    assert fresh['fencing_generation']==2
    result=service.checkpoint_run(owner,fresh,'monitoring','SAVED',summary='Reconciled',idempotency_key='recovered')
    assert row(result,'run_v1')['data']['current_phase']=='research'
    assert len(service.list_records(owner,'checkpoint_v1'))==2


def test_project_budgets_and_configuration_changes_do_not_reset_allowances(project):
    service,owner=setup(project);lease=claim(service,owner);admit(service,owner,'first');reserve(service,owner,lease)
    current=service.get(owner);config=deepcopy(current['data']['manifest'])
    config['timezone']='Pacific/Honolulu';config['research']['normal_daily_attempts']=9
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:user',idempotency_key='timezone')
    with pytest.raises(ProjectConflict):reserve(service,owner,lease)
    run=service.claim_run(owner,'daily','worker-one',2,local_cycle_date='2026-10-25',idempotency_key='config-aware')['records'][0]['data']
    current_lease={k:run[k] for k in ('run_id','lease_owner','fencing_generation')}
    reserve(service,owner,current_lease)
    budget=service.get_record(owner,'budget_v1','2026-10-25')['data']
    assert (budget['used'],budget['ordinary_limit'])==(1,5)
    other,manifest=project[3]();other.initialize(owner,manifest,authorization_ref='synthetic:setup',idempotency_key='setup');topic(other,owner)
    other_lease=claim(other,owner);admit(other,owner,'first')
    assert row(reserve(other,owner,other_lease),'attempt_v1')['data']['slot']==1


def test_daily_and_weekly_share_last_slot_transactionally(project):
    service,owner=setup(project);config=deepcopy(service.get(owner)['data']['manifest'])
    config['research'].update(normal_daily_attempts=1,urgent_total_daily_attempts=1)
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:user',idempotency_key='one-slot')
    leases=[]
    for kind in ('daily','weekly'):
        run=service.claim_run(owner,kind,'worker-'+kind,2,idempotency_key='claim-'+kind)['records'][0]['data']
        leases.append({k:run[k] for k in ('run_id','lease_owner','fencing_generation')})
    admit(service,owner,'first-question');admit(service,owner,'different-question')
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda lease:reserve(service,owner,lease),leases))
    assert sum(r['outcome']=='attempt_reserved' for r in results)==1
    assert sum(r['outcome']=='daily_budget_exhausted' for r in results)==1
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1


def test_failure_backoff_and_reserved_crash_recovery(project):
    service,owner=setup(project);lease=claim(service,owner);admit(service,owner,'retry-work')
    first=row(reserve(service,owner,lease),'attempt_v1')['data']
    resumed=reserve(service,owner,lease,resume_attempt_id=first['attempt_id'])
    assert row(resumed,'attempt_v1')['data']['slot']==1
    failed=service.invocation(owner,lease,first['attempt_id'],'failed',error_code='synthetic_timeout',idempotency_key='failure')
    assert row(failed,'queue_v1')['data']['status']=='retry_wait'
    assert reserve(service,owner,lease)['status']=='BLOCKED'
    previous=service.clock();service.clock=lambda:previous+timedelta(seconds=31)
    second=row(reserve(service,owner,lease),'attempt_v1')['data']
    assert (second['attempt_number'],second['slot'])==(2,2)


def test_fencing_rechecks_actual_space_access_before_receipt_replay(project):
    from test_access import record_unadmitted,account_named,identity
    from czero_core.identity import Role,PermissionDenied
    from czero_core.spaces import SpaceService
    service,owner=setup(project);accounts=service.access;key=uuid4()
    record_unadmitted(accounts,key,'workflow-editor');account=account_named(accounts,owner,'workflow-editor')
    accounts.set_role(owner,account['id'],Role.EDITOR);actor=accounts.resolve(identity(accounts,key,'workflow-editor'))
    spaces=SpaceService(service.database,accounts)
    spaces.set_grant(owner,str(service._space_id),actor.user_id,Role.EDITOR,expected_revision=0,idempotency_key='grant-work')
    lease=claim(service,actor);admit(service,actor,'private-work')
    service.reserve(actor,lease,idempotency_key='private-reservation')
    spaces.set_grant(owner,str(service._space_id),actor.user_id,None,expected_revision=1,idempotency_key='revoke-work')
    with pytest.raises(PermissionDenied):service.reserve(actor,lease,idempotency_key='private-reservation')
