# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real report membership/readback and delivery recovery; hosts are synthetic."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
import pytest
from czero_core.current_content import ContentSuperseded
from czero_core.projects import ProjectConflict
from test_access import access
from test_projects import project
from test_sources import sources
from test_project_evidence import evidence,start,finding,result_data,save,page
from test_project_workflows import row


def publisher(evidence,worker='publisher',cycle='daily-report'):
    service,owner,*_=evidence
    run=service.claim_run(owner,'report_publication',worker,service.get(owner)['data']['version'],
        cycle_key=cycle,idempotency_key=uuid4().hex)['records'][0]['data']
    return {key:run[key] for key in ('run_id','lease_owner','fencing_generation')}


def completed(evidence,name='report-result'):
    service,owner,lease,_,source,_=evidence;attempt=start(evidence,name);_,chunks=source()
    result=row(save(evidence,attempt,result_data(finding(chunks[0]))),'result_v1')
    service.invocation(owner,lease,attempt['attempt_id'],'returned',result_reference=result['id'],idempotency_key=uuid4().hex)
    wiki=page(evidence,result_reference=result['id'])
    published=service.publish_result(owner,lease,result['id'],[wiki['content']['id']],idempotency_key=uuid4().hex)
    service.complete_research(owner,lease,attempt['attempt_id'],commit_references=[row(published,'result_publication_v1')['id']],idempotency_key=uuid4().hex)
    return service.get_record(owner,'result_v1','attempt:'+attempt['attempt_id'])


def prepare(evidence,lease,report_type='daily',**changes):
    service,owner,*_=evidence
    return row(service.prepare_report(owner,lease,report_type,idempotency_key=uuid4().hex,**changes),'report_v1')


def report_page(evidence,header,body):
    service,owner,_,knowledge,*_=evidence
    return knowledge.create_page(owner,'reports/'+uuid4().hex,'Daily research',body,
        metadata={'c0_project':{'project_id':str(service._space_id),'report_reference':header['id'],'language':header['data']['language']}},
        idempotency_key=uuid4().hex)


def member(evidence,lease,header,result,wiki,entry,**changes):
    service,owner,*_=evidence;body=wiki['content']['body'].encode();encoded=entry.encode();start_byte=body.index(encoded)
    values={'result_reference':result['id'],'disposition':'included','location':'main','wiki_revision_id':wiki['content']['id'],
        'start_byte':start_byte,'end_byte':start_byte+len(encoded),'reason':'','assessment_ref':'synthetic:substantive-entry',**changes}
    revision=values.pop('expected_revision',0)
    return row(service.set_report_member(owner,lease,header['id'],values,expected_revision=revision,idempotency_key=uuid4().hex),'report_member_v1')


def finalize(evidence,lease,header,wiki):
    service,owner,*_=evidence
    return service.finalize_report(owner,lease,header['id'],wiki['content']['id'],idempotency_key=uuid4().hex)


def saved_report(evidence):
    result=completed(evidence);lease=publisher(evidence);header=prepare(evidence,lease)
    entry='We learned that fabricated capacity constrains the synthetic manufacturing goal.'
    wiki=report_page(evidence,header,'# Daily findings\n\n'+entry)
    member(evidence,lease,header,result,wiki,entry)
    return lease,row(finalize(evidence,lease,header,wiki),'report_v1'),wiki


def test_report_cannot_omit_completed_results_or_accept_unrelated_wiki(evidence):
    service,owner,_,knowledge,*_=evidence
    first=completed(evidence,'capacity-review');second=completed(evidence,'software-development')
    lease=publisher(evidence);header=prepare(evidence,lease)
    one='Capacity constraints changed the first approved synthetic investigation.'
    two='Development activity changed the second approved synthetic investigation.'
    wiki=report_page(evidence,header,'# Daily findings\n\n'+one)
    earlier=member(evidence,lease,header,first,wiki,one)
    with pytest.raises(ValueError,match='missing_completed'):finalize(evidence,lease,header,wiki)
    assert service.get_report(owner)['report'] is None # Draft is not the latest saved report.
    updated=knowledge.update_page(owner,wiki['id'],'Daily findings',wiki['content']['body']+'\n\n'+two,
        metadata=wiki['content']['metadata'],expected_revision=1,idempotency_key='complete-body')
    member(evidence,lease,header,first,updated,one,expected_revision=earlier['revision'])
    member(evidence,lease,header,second,updated,two)
    saved=row(finalize(evidence,lease,header,updated),'report_v1')
    view=service.get_report(owner)
    assert saved['data']['included_count']==2 and len(view['members'])==2 and not view['more']
    assert knowledge.get_page(owner,saved['data']['wiki_page_id'],revision=saved['data']['wiki_revision'])['content']['content_hash']==saved['data']['content_hash']
    assert saved['data']['saved_status']=='saved' and view['deliveries']==[]


def test_blocked_daily_run_can_save_a_report_without_false_monitoring_success(evidence):
    service,owner,_,_,_,_=evidence
    config=deepcopy(service.get(owner)['data']['manifest']);config['primary_topic_ids']=['anchor'];config['state']['initialized']=True
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:primary',idempotency_key='primary')
    run=service.claim_run(owner,'daily','worker-one',2,idempotency_key='current-config')['records'][0]['data']
    lease={key:run[key] for key in ('run_id','lease_owner','fencing_generation')}
    cycle=row(service.monitor_begin(owner,lease,'anchor',idempotency_key='begin'),'monitor_cycle_v1')
    service.monitor_finish(owner,lease,cycle['data']['cycle_id'],'blocked',summary='Synthetic provider unavailable',idempotency_key='blocked')
    service.checkpoint_run(owner,lease,'monitoring','PARTIAL',summary='Primary search unavailable',idempotency_key='partial')
    report_lease=publisher(evidence);header=prepare(evidence,report_lease)
    wiki=report_page(evidence,header,'# Daily coverage\n\nPrimary monitoring could not be completed. No successful search or material conclusion is claimed.')
    saved=row(finalize(evidence,report_lease,header,wiki),'report_v1')
    assert saved['data']['monitoring_expected']==1 and saved['data']['monitoring_complete']==0
    assert saved['data']['coverage_complete'] is False and saved['data']['saved_status']=='saved'
    assert service.get_record(owner,'run_v1',run['run_id'])['data']['state']=='partial'
    assert service.list_records(owner,'monitor_watermark_v1')==[] and service.list_records(owner,'budget_v1')==[]


def test_saved_report_publication_retry_does_not_repeat_research_or_imply_notification(evidence):
    service,owner,*_=evidence;lease,header,wiki=saved_report(evidence);calls=[]
    def observe(state,**changes):return service.observe_report_delivery(owner,lease,header['id'],'external_result',state,
        observation_source='sdk_simulation',idempotency_key=uuid4().hex,**changes)
    assert observe('started')['status']=='QUEUED';calls.append('first-fake-host-call')
    assert observe('failed',external_reference='synthetic:host-failure',evidence_reference='synthetic:observed-failure')['status']=='BLOCKED'
    assert observe('started')['outcome']=='report_publication_retry_deferred'
    old=service.clock();service.clock=lambda:old+timedelta(seconds=31)
    assert observe('started')['status']=='QUEUED';calls.append('second-fake-host-call')
    assert observe('succeeded',external_reference='synthetic:published-result',evidence_reference='synthetic:publication-readback')['status']=='SAVED'
    view=service.get_report(owner)
    assert len(calls)==2 and [entry['data']['channel'] for entry in view['deliveries']]==['external_result']
    assert view['report']['data']['wiki_revision_id']==wiki['content']['id']
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1
    assert len(service.list_records(owner,'result_v1'))==1 and len(service.list_records(owner,'report_history_v1'))==1


def test_uncertain_publication_is_reconciled_after_fence_transfer(evidence):
    service,owner,*_=evidence;lease,header,_=saved_report(evidence)
    service.observe_report_delivery(owner,lease,header['id'],'external_result','started',idempotency_key='start')
    old=service.clock();service.clock=lambda:old+timedelta(minutes=6)
    recovered=publisher(evidence,worker='recovery-worker')
    with pytest.raises(ProjectConflict):service.observe_report_delivery(owner,lease,header['id'],'external_result','succeeded',
        external_reference='synthetic:stored-host-result',evidence_reference='synthetic:readback',idempotency_key='stale')
    blocked=service.observe_report_delivery(owner,recovered,header['id'],'external_result','started',idempotency_key='no-second-call')
    assert blocked['outcome']=='report_publication_requires_reconciliation'
    saved=service.observe_report_delivery(owner,recovered,header['id'],'external_result','succeeded',
        external_reference='synthetic:stored-host-result',evidence_reference='synthetic:actual-reconciliation',idempotency_key='reconciled')
    assert row(saved,'report_delivery_v1')['data']['attempt_count']==1
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1


def test_concurrent_report_preparation_has_one_owner(evidence):
    service,owner,*_=evidence
    leases=[publisher(evidence,'publisher-'+str(index),'publication-'+str(index)) for index in range(2)]
    def prepare_one(lease):
        try:return service.prepare_report(owner,lease,'daily',idempotency_key=uuid4().hex)
        except ProjectConflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(prepare_one,leases))
    assert sum(result is not None for result in results)==1
    assert len(service.list_records(owner,'report_v1'))==1


def test_new_completed_result_during_report_requires_visible_coverage(evidence):
    service,owner,*_=evidence
    first=completed(evidence,'first-subject');lease=publisher(evidence);header=prepare(evidence,lease)
    entry='We learned the first fabricated constraint and its project consequence.'
    wiki=report_page(evidence,header,'# Daily findings\n\n'+entry)
    member(evidence,lease,header,first,wiki,entry)
    completed(evidence,'second-subject')
    with pytest.raises(ValueError,match='missing_completed'):finalize(evidence,lease,header,wiki)
    assert service.list_records(owner,'report_history_v1')==[]


def test_deferred_completed_evidence_remains_due_in_next_report(evidence):
    service,owner,*_=evidence;result=completed(evidence);lease=publisher(evidence);header=prepare(evidence,lease)
    abandoned='This completed result appears only in an abandoned report draft.'
    old_wiki=report_page(evidence,header,'# Unsaved draft\n\n'+abandoned)
    member(evidence,lease,header,result,old_wiki,abandoned)
    header=prepare(evidence,lease,amend=True,expected_revision=header['revision'])
    entry='Completed capacity evidence is explicitly deferred until a contrary check is summarized.'
    wiki=report_page(evidence,header,'# Deferred findings\n\n'+entry)
    member(evidence,lease,header,result,wiki,entry,disposition='deferred',reason='Contrary check summary pending')
    first=row(finalize(evidence,lease,header,wiki),'report_v1')
    assert first['data']['deferred_count']==1 and first['data']['included_count']==0
    old=service.clock();service.clock=lambda:old+timedelta(days=1)
    service.claim_run(owner,'daily','next-day',1,idempotency_key='next-day')
    later=publisher(evidence,cycle='next-report');header=prepare(evidence,later)
    wiki=report_page(evidence,header,'# Next report\n\nNo completed evidence may silently disappear.')
    with pytest.raises(ValueError,match='missing_completed'):finalize(evidence,later,header,wiki)


def test_italian_appendix_utf8_proof_and_historical_result_are_preserved(evidence):
    service,owner,_,knowledge,*_=evidence;result=completed(evidence)
    config=deepcopy(service.get(owner)['data']['manifest']);config['language']='it'
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:language',idempotency_key='italian')
    lease=publisher(evidence);header=prepare(evidence,lease)
    text='Abbiamo appreso che la capacità sintetica limita l’obiettivo: è un’ipotesi da verificare.'
    appendix=report_page(evidence,header,'# Appendice\n\n'+text)
    member(evidence,lease,header,result,appendix,text,location='appendix')
    wiki=report_page(evidence,header,'# Ricerca quotidiana\n\nLa nuova conoscenza e le prove sono conservate nell’[appendice](./wiki?page_id='+appendix['id']+'&revision=1).')
    saved=row(finalize(evidence,lease,header,wiki),'report_v1')
    knowledge.update_page(owner,appendix['id'],'Appendice aggiornata','# Revisione successiva\n\nLa vecchia prova rimane consultabile.',
        metadata=appendix['content']['metadata'],expected_revision=1,idempotency_key='later-appendix')
    view=service.get_report(owner)
    assert saved['data']['language']=='it' and view['members'][0]['data']['wiki_revision_id']==appendix['content']['id']
    with pytest.raises(ContentSuperseded):knowledge.get_page(owner,appendix['id'],revision=1)
    assert knowledge.get_page(owner,appendix['id'])['revision']==2


def test_other_project_cannot_read_or_publish_foreign_report(evidence,project):
    from czero_core.objects import ObjectNotFound
    service,owner,*_=evidence;_,header,_=saved_report(evidence)
    other,manifest=project[3]();other.initialize(owner,manifest,authorization_ref='synthetic:other',idempotency_key='other')
    lease=other.claim_run(owner,'report_publication','other-worker',1,cycle_key='other',idempotency_key='other-run')['records'][0]['data']
    lease={key:lease[key] for key in ('run_id','lease_owner','fencing_generation')}
    assert other.get_report(owner)['report'] is None
    with pytest.raises((ValueError,ObjectNotFound)):other.observe_report_delivery(owner,lease,header['id'],'external_result','started',idempotency_key='foreign')
    assert service.get_report(owner)['deliveries']==[] and other.list_records(owner,'report_v1')==[]


def test_daily_report_phase_requires_actual_saved_report_receipt(evidence):
    service,owner,lease,*_=evidence;_,header,_=saved_report(evidence)
    for phase in ('monitoring','research','evidence','synthesis'):
        service.checkpoint_run(owner,lease,phase,'SAVED',idempotency_key='phase-'+phase)
    with pytest.raises(ValueError,match='saved_report_required'):
        service.checkpoint_run(owner,lease,'report','SAVED',idempotency_key='no-report-reference')
    completed=service.checkpoint_run(owner,lease,'report','SAVED',references=[header['id']],idempotency_key='actual-report')
    assert row(completed,'run_v1')['data']['state']=='complete'
    assert service.get_report(owner)['deliveries']==[]


def test_scope_change_does_not_count_old_monitoring_as_current_report_coverage(evidence):
    from test_project_monitoring import begin,call,observe,finish
    service,owner,*_=evidence
    manifest=deepcopy(service.get(owner)['data']['manifest']);manifest['primary_topic_ids']=['anchor'];manifest['state']['initialized']=True
    service.configure(owner,manifest,expected_revision=1,authorization_ref='synthetic:primary',idempotency_key='primary')
    run=service.claim_run(owner,'daily','worker-one',2,idempotency_key='version-two')['records'][0]['data']
    lease={key:run[key] for key in ('run_id','lease_owner','fencing_generation')}
    cycle=begin(service,owner,lease);query=call(service,owner,lease,cycle);observe(service,owner,lease,query);finish(service,owner,lease,cycle)
    manifest['scope']+=' Changed authorized scope.'
    service.configure(owner,manifest,expected_revision=2,authorization_ref='synthetic:scope-change',idempotency_key='scope-change')
    service.claim_run(owner,'daily','worker-one',3,idempotency_key='version-three')
    report_lease=publisher(evidence);header=prepare(evidence,report_lease)
    wiki=report_page(evidence,header,'# Coverage\n\nThe earlier successful check does not cover the changed project scope.')
    saved=row(finalize(evidence,report_lease,header,wiki),'report_v1')['data']
    assert saved['monitoring_expected']==1 and saved['monitoring_complete']==0 and not saved['coverage_complete']
