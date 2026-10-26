# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from datetime import timedelta,date
from uuid import uuid4
import pytest
from czero_core.projects import ProjectConflict
from czero_core.project_events import latest_event_occurrence,event_candidate_identity
from test_access import access
from test_projects import project,topic
from test_sources import sources
from test_project_evidence import evidence,page
from test_project_workflows import setup,candidate,row
from test_project_workflows import admit,reserve,claim


def weekly(service,owner,cycle='weekly',worker='maintainer'):
    values=service.claim_run(owner,cycle,worker,service.get(owner)['data']['version'],
        **({'cycle_key':uuid4().hex} if cycle=='maintenance' else {}),idempotency_key=uuid4().hex)['records'][0]['data']
    return {key:values[key] for key in ('run_id','lease_owner','fencing_generation')}


def test_bounded_audit_cursor_and_json_body_integrity(evidence):
    service,owner,_,knowledge,*_=evidence
    page(evidence,'{"title":"Bad envelope","body":"# Markdown"}')
    page(evidence,'# Real Markdown\n\nA [broken link](./wiki?page_id='+str(uuid4())+').')
    lease=weekly(service,owner)
    first=service.audit_step(owner,lease,'wiki',limit=1,idempotency_key='first')
    assert first['status']=='PARTIAL'
    second=service.audit_step(owner,lease,'wiki',limit=1,idempotency_key='second')
    assert second['status']=='SAVED' and row(second,'audit_v1')['data']['scanned']==2
    findings=service.list_records(owner,'audit_finding_v1')
    assert any('wiki_body_envelope' in finding['data']['detail'] for finding in findings)
    assert any('broken_wiki_link' in finding['data']['detail'] for finding in findings)
    assert service.get_record(owner,'audit_cursor_v1','wiki')['data']['after_id']==''
    assert len(service.list_records(owner,'budget_v1'))==0


def test_semantic_rotation_rejects_stale_revision_and_resumes_without_inheriting_review(evidence):
    service,owner,_,knowledge,*_=evidence
    config=deepcopy(service.get(owner)['data']['manifest']);config['maintenance']['semantic_pages_per_week']=2
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:bounded-review',idempotency_key='bound')
    pages=[page(evidence,'# Synthetic page\n\nA bounded semantic assessment is required.') for _ in range(3)]
    lease=weekly(service,owner)
    result=service.semantic_select(owner,lease,idempotency_key='select');header=row(result,'semantic_round_v1')
    assert len(header['data']['selected_ids'])==2 and not header['data']['semantic_coverage_complete']
    selection=next(record for record in service.list_records(owner,'semantic_selection_v1') if record['id']==header['data']['selected_ids'][0])
    original=next(wiki for wiki in pages if wiki['id']==selection['data']['page_id'])
    knowledge.update_page(owner,original['id'],'Changed','# Changed content\n\nThe old assessment cannot apply to this revision.',
        metadata=original['content']['metadata'],expected_revision=1,idempotency_key='edit')
    data={'status':'reviewed','assessment':'Synthetic semantic review of actual current content.','assessment_ref':'synthetic:assessment',
        'limitations':['No real agent used.'],'citation_ids':[],'proposed_question':''}
    with pytest.raises(ProjectConflict):service.semantic_review(owner,lease,selection['id'],data,idempotency_key='stale')
    service.semantic_select(owner,lease,refresh_changed=True,idempotency_key='refresh')
    assert len(service.list_records(owner,'semantic_selection_history_v1'))==1
    for reference in header['data']['selected_ids']:
        service.semantic_review(owner,lease,reference,data,idempotency_key=uuid4().hex)
    completed=service.semantic_select(owner,lease,idempotency_key='readback')
    assert row(completed,'semantic_round_v1')['data']['state']=='complete'
    assert not row(completed,'semantic_round_v1')['data']['semantic_coverage_complete']
    assert service.get_record(owner,'semantic_cursor_v1','wiki')['data']['rounds']==1
    service_clock=service.clock();service.clock=lambda:service_clock+timedelta(days=7)
    next_lease=weekly(service,owner);next_round=row(service.semantic_select(owner,next_lease,idempotency_key='next'),'semantic_round_v1')
    seen={record['data']['page_id'] for record in service.list_records(owner,'semantic_selection_v1')}
    assert len(next_round['data']['selected_ids'])==2
    for reference in next_round['data']['selected_ids']:
        service.semantic_review(owner,next_lease,reference,data,idempotency_key=uuid4().hex)
    service.clock=lambda:service_clock+timedelta(days=14)
    service.semantic_select(owner,weekly(service,owner),idempotency_key='third')
    assert len({record['data']['page_id'] for record in service.list_records(owner,'semantic_selection_v1')})==3


def test_peripheral_archive_requires_distinct_future_checkpoint_and_preserves_topic_history(project):
    service,owner=setup(project);lease=weekly(service,owner)
    peripheral=topic(service,owner,'peripheral',classification='peripheral',anchor_ids=['anchor'],
        direct_contribution='Potential contribution to approved anchor',assessment_ref='synthetic:scope')
    before=service.clock();service.clock=lambda:before+timedelta(hours=2)
    lease=weekly(service,owner)
    with service.database.engine.connect() as connection:
        assert service._topic_scope(connection,'peripheral',one_off=True)
    with pytest.raises(ValueError,match='distinct_future'):service.archive_peripheral(owner,lease,'peripheral',
        'A compact synthetic summary preserves the original lineage.','synthetic:archive',idempotency_key='same-run')
    service.clock=lambda:before+timedelta(days=7)
    future=weekly(service,owner)
    with service.database.engine.connect() as connection:
        assert service._topic_scope(connection,'peripheral',one_off=True) is None
    archived=service.archive_peripheral(owner,future,'peripheral','A compact synthetic summary preserves the original lineage.',
        'synthetic:archive',idempotency_key='archive')
    capsule=row(archived,'archive_v1');assert capsule['data']['topic_snapshot']==peripheral['data']
    assert row(archived,'topic_v1')['data']['lifecycle']=='archived'
    history=[item for item in service.list_records(owner,'topic_history_v1') if item['data']['topic_id']=='peripheral']
    assert len(history)==2 and history[0]['data']['topic']['anchor_ids']==['anchor']


def test_calendar_recurrence_preserves_expansion_and_actual_occurrence_receipts(project):
    service,owner=setup(project)
    definition={'event_id':'refresh','topic_id':'anchor','kind':'research_refresh','title':'Synthetic recurring observation',
        'start_time':'2026-10-20','timezone':'Europe/Rome','source_reference':'synthetic:calendar-source',
        'refresh_question':'What changed in synthetic production?','priority':0,'expansion_priority':40,
        'recurrence':{'frequency':'daily','interval':1,'until':''}}
    event=service.set_event(owner,definition,idempotency_key='event')
    def admit_day(day):
        identity=event_candidate_identity('refresh',day)
        return service.admit(owner,candidate(identity,origin='calendar',origin_reference='refresh',kind='investigation',
            question=definition['refresh_question'],priority=0,urgency_reason='Actual configured same-day deadline',
            root_reason='independent_external_event',novelty_key=identity,time_window=day,due_at=day+'T22:59:59+00:00'),idempotency_key=uuid4().hex)
    first=row(admit_day('2026-10-25'),'queue_v1')['data'];assert first['expansion_priority']==40
    old=service.clock();service.clock=lambda:old+timedelta(days=1)
    second=row(admit_day('2026-10-26'),'queue_v1')['data']
    assert second['lineage_root_id']==first['lineage_root_id'] and second['expansion_priority']==40
    assert len(service.list_records(owner,'event_occurrence_v1'))==2
    assert service.get_record(owner,'event_v1','refresh')['data']['last_checked_at']==event['data']['last_checked_at']
    with pytest.raises(ValueError):service.set_event(owner,{**definition,'expansion_priority':0},expected_revision=1,idempotency_key='reset-depth')


def test_monthly_calendar_keeps_day_anchor_and_partial_dates_cannot_execute(project):
    service,owner=setup(project)
    value={'event_id':'month','topic_id':'anchor','title':'Synthetic monthly event','start_time':'2026-01-31',
        'timezone':'Europe/Rome','source_reference':'synthetic:date','recurrence':{'frequency':'monthly','interval':1,'until':''}}
    event=service.set_event(owner,value,idempotency_key='month')['data']
    assert latest_event_occurrence(event,date(2026,2,28))==date(2026,2,28)
    assert latest_event_occurrence(event,date(2026,3,31))==date(2026,3,31)
    with pytest.raises(ValueError):service.set_event(owner,{**value,'event_id':'unknown','start_time':'2026-03',
        'date_precision':'month','kind':'research_refresh','refresh_question':'What changed?'},idempotency_key='partial')


def test_concurrent_maintenance_runs_preserve_shared_cursor_progress(evidence):
    service,owner,*_=evidence
    for _ in range(3):page(evidence)
    first=weekly(service,owner);second=weekly(service,owner,'maintenance')
    service.audit_step(owner,first,'wiki',limit=1,idempotency_key='first')
    service.audit_step(owner,second,'wiki',limit=1,idempotency_key='second')
    before=service.get_record(owner,'audit_cursor_v1','wiki')
    result=service.audit_step(owner,first,'wiki',limit=1,idempotency_key='old-progress')
    assert service.get_record(owner,'audit_cursor_v1','wiki')==before
    assert 'Concurrent cursor progress preserved.' in row(result,'audit_v1')['data']['limitations']
    config=deepcopy(service.get(owner)['data']['manifest']);config['maintenance']['semantic_pages_per_week']=1
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:semantic-bound',idempotency_key='semantic-bound')
    first=weekly(service,owner);second=weekly(service,owner,'maintenance')
    one=row(service.semantic_select(owner,first,idempotency_key='one'),'semantic_round_v1')
    two=row(service.semantic_select(owner,second,idempotency_key='two'),'semantic_round_v1')
    data={'status':'reviewed','assessment':'Actual synthetic revision inspected.','assessment_ref':'synthetic:review',
        'limitations':[],'citation_ids':[],'proposed_question':''}
    service.semantic_review(owner,first,one['data']['selected_ids'][0],data,idempotency_key='review-one')
    cursor=service.get_record(owner,'semantic_cursor_v1','wiki')
    service.semantic_review(owner,second,two['data']['selected_ids'][0],data,idempotency_key='review-two')
    assert service.get_record(owner,'semantic_cursor_v1','wiki')==cursor


def test_completed_history_bound_preserves_requests_and_allows_existing_active_work(evidence):
    from test_project_reports import completed
    service,owner,*_=evidence
    completed(evidence,'historical-one');completed(evidence,'historical-two')
    admit(service,owner,'active-three')
    config=deepcopy(service.get(owner)['data']['manifest']);config['maintenance']['max_inventory']=1
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:inventory-bound',idempotency_key='bound')
    reassessed=service.admit(owner,candidate('active-three'),idempotency_key='reassess')
    assert reassessed['outcome']=='merge'
    run=service.claim_run(owner,'daily','worker-one',2,idempotency_key='current-run')['records'][0]['data']
    lease={key:run[key] for key in ('run_id','lease_owner','fencing_generation')}
    assert row(reserve(service,owner,lease),'attempt_v1')['data']['slot']==3
    held=service.admit(owner,candidate('explicit-fourth'),idempotency_key='preserve-request')
    assert held['outcome']=='defer_capacity' and row(held,'admission_v1')['data']['candidate']['question']=='What changed in explicit-fourth?'
    view=service.diagnostics(owner)
    assert any(record['data'].get('candidate_id')=='explicit-fourth' for record in view['errors'])
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==3
    outside=topic(service,owner,'outside',classification='peripheral',anchor_ids=['anchor'],
        direct_contribution='One-off fixture only',assessment_ref='synthetic:scope')
    assert service.admit(owner,candidate('automatic-outside',topic_id='outside',origin='discovery',
        root_reason='independent_external_event'),idempotency_key='outside-bound')['outcome']=='reject_scope'


def test_active_selection_retains_completed_anchor_service_history(evidence):
    from test_project_reports import completed
    service,owner,*_=evidence
    completed(evidence,'served-anchor-one');completed(evidence,'served-anchor-two')
    topic(service,owner,'other-anchor')
    definitions=[('earlier-served-question',{'question':'Which synthetic manufacturing capacity constraint changed?'}),
        ('later-unserved-question',{'topic_id':'other-anchor','anchor_ids':['other-anchor'],
            'question':'How did the unrelated software architecture evolve?'})]
    for identity,values in definitions:admit(service,owner,identity,**values)
    config=deepcopy(service.get(owner)['data']['manifest']);config['maintenance']['max_inventory']=2
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:bounded-active',idempotency_key='active-bound')
    for identity,values in definitions:assert admit(service,owner,identity,**values)['outcome']=='merge'
    run=service.claim_run(owner,'daily','worker-one',2,idempotency_key='fair-run')['records'][0]['data']
    lease={key:run[key] for key in ('run_id','lease_owner','fencing_generation')}
    selected=row(reserve(service,owner,lease),'queue_v1')
    assert selected['data']['stable_id']=='later-unserved-question'
