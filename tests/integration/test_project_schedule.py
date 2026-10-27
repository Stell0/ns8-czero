# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
import pytest
from czero_core.projects import ProjectConflict
from test_access import access
from test_projects import project,initialize,topic
from test_project_workflows import claim,admit,reserve,row,candidate


def test_recent_missed_occurrence_uses_logical_date_but_actual_day_budget(project):
    service,manifest,owner,_=project;initialize(project);topic(service,owner)
    original=service.clock();service.clock=lambda:original+timedelta(days=2)
    result=service.claim_run(owner,'daily','late-worker',1,local_cycle_date='2026-10-26',
        scheduled_for='2026-10-26T06:00:00+00:00',idempotency_key='late')
    run=row(result,'run_v1')['data'];lease={k:run[k] for k in ('run_id','lease_owner','fencing_generation')}
    admit(service,owner,'late-question');attempt=row(reserve(service,owner,lease),'attempt_v1')['data']
    assert (run['local_cycle_date'],attempt['local_date'])==('2026-10-26','2026-10-27')
    with pytest.raises(ValueError):service.claim_run(owner,'weekly','wrong-occurrence',1,
        local_cycle_date='2026-10-26',scheduled_for='2026-10-26T08:00:00Z',idempotency_key='wrong')
    with pytest.raises(ValueError):service.claim_run(owner,'daily','old-occurrence',1,
        local_cycle_date='2026-10-01',scheduled_for='2026-10-01T06:00:00Z',idempotency_key='too-old')


def test_source_scope_change_requires_reassessment_before_reserved_external_call(project):
    service,manifest,owner,_=project;initialize(project);topic(service,owner);lease=claim(service,owner)
    admit(service,owner,'scope-review');attempt=row(reserve(service,owner,lease),'attempt_v1')['data']
    config=deepcopy(service.get(owner)['data']['manifest']);config['scope']='Narrower fabricated scope'
    service.configure(owner,config,expected_revision=1,authorization_ref='synthetic:user-narrows-scope',idempotency_key='narrow')
    current=service.claim_run(owner,'daily','worker-one',2,idempotency_key='acknowledge')['records'][0]['data']
    fresh={k:current[k] for k in ('run_id','lease_owner','fencing_generation')}
    blocked=reserve(service,owner,fresh,resume_attempt_id=attempt['attempt_id'])
    assert blocked['outcome']=='scope_reassessment_required'
    with pytest.raises(ProjectConflict):service.invocation(owner,fresh,attempt['attempt_id'],'started',idempotency_key='stale-scope')
    admitted=service.admit(owner,candidate('scope-review',assessment_ref='synthetic:reassessed-current-scope'),idempotency_key='reassess')
    assert admitted['outcome']=='merge'
    assert row(reserve(service,owner,fresh,resume_attempt_id=attempt['attempt_id']),'attempt_v1')['data']['slot']==1
    service.invocation(owner,fresh,attempt['attempt_id'],'started',idempotency_key='current-scope')
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1


def test_runner_observations_do_not_install_or_enable_external_tasks(project):
    service,manifest,owner,_=project;initialize(project)
    data={'provider':'chatgpt_work','workflow_type':'daily','observation_source':'sdk_simulation',
        'status':'reported_installed','task_reference':'synthetic-task','run_id':'',
        'evidence_reference':'synthetic-host-response','summary':'Synthetic installation report only'}
    result=service.observe_runner(owner,data,idempotency_key='reported')
    assert result['status']=='SAVED' and result==service.observe_runner(owner,data,idempotency_key='reported')
    assert service.get(owner)['data']['manifest']['schedule']['enabled'] is False
    assert service.schedule(owner)['installed_by_c0'] is False
    with pytest.raises(ValueError):service.observe_runner(owner,{**data,'status':'reported_execution'},idempotency_key='no-run')


def test_schedule_contracts_are_independent_and_language_specific(project):
    service,manifest,owner,create=project;initialize(project)
    other,config=create();config['language']='it';config['timezone']='Europe/Rome'
    config['schedule'].update(daily_local_time='07:00',weekly_local_time='07:00')
    other.initialize(owner,config,authorization_ref='synthetic:setup',idempotency_key='other')
    a=service.schedule(owner);b=other.schedule(owner)
    assert a['project_id']!=b['project_id'] and a['timezone']=='UTC' and b['timezone']=='Europe/Rome'
    assert b['desired']['daily_local_time']=='07:00' and b['desired']['enabled'] is False
    assert service.list_records(owner,'runner_observation_v1')==[]
