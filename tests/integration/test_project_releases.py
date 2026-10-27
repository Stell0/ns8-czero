# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from datetime import timedelta
from uuid import uuid4
import pytest
from test_access import access
from test_projects import project
from test_sources import sources
from test_project_evidence import evidence
from test_project_maintenance import weekly
from test_project_workflows import row


def test_saved_release_metadata_retry_partial_and_changed_identity(evidence):
    service,owner,_,_,source,_=evidence;lease=weekly(service,owner);repo='Stell0/ns8-czero'
    def metadata(commit='a'*40,complete=True):
        body={'repository':repo,'complete':complete,'fresh':True,'releases':[
            {'version':'core-v0.34.0','release_id':'synthetic-release','source_commit':commit}]}
        version,_=source(json.dumps(body),{'source_type':'workflow_release_metadata','repository':repo})
        return str(version['id'])
    first=service.observe_release(owner,lease,repo,'0.33.0',metadata_version_id=metadata(),idempotency_key='first')
    assert row(first,'release_check_v1')['data']['status']=='available'
    changed=service.observe_release(owner,lease,repo,'0.33.0',metadata_version_id=metadata('b'*40),idempotency_key='changed')
    assert changed['status']=='BLOCKED' and row(changed,'release_check_v1')['data']['status']=='security_alert'
    partial=service.observe_release(owner,lease,repo,'0.34.0',metadata_version_id=metadata('b'*40,False),idempotency_key='partial')
    assert partial['status']=='BLOCKED' and row(partial,'release_check_v1')['data']['status']=='security_alert'
    assert len(service.list_records(owner,'release_identity_v1'))==1
    assert service.observe_release(owner,lease,repo,'0.34.0',error_code='rate_limited',idempotency_key='fourth')['outcome']=='release_retry_not_due'
    assert len(service.list_records(owner,'release_check_history_v1'))==3
    assert service.list_records(owner,'budget_v1')==[]


def test_release_failure_is_unknown_and_no_release_is_a_distinct_observation(evidence):
    service,owner,_,_,source,_=evidence;lease=weekly(service,owner);repo='Kabutojira/WikiPlant'
    failed=service.observe_release(owner,lease,repo,'1.0.0',error_code='timeout',idempotency_key='failure')
    assert failed['status']=='BLOCKED' and row(failed,'release_check_v1')['data']['last_success_at']==''
    old=service.clock();service.clock=lambda:old+timedelta(hours=2)
    lease=weekly(service,owner)
    body={'repository':repo,'complete':True,'fresh':True,'releases':[]}
    version,_=source(json.dumps(body),{'source_type':'workflow_release_metadata','repository':repo})
    saved=service.observe_release(owner,lease,repo,'1.0.0',metadata_version_id=str(version['id']),idempotency_key='empty')
    assert row(saved,'release_check_v1')['data']['status']=='no_release'
    with pytest.raises(ValueError):service.observe_release(owner,lease,'invalid repository','1.0.0',error_code='test',idempotency_key='untrusted')


def test_incomplete_release_observation_is_not_up_to_date(evidence):
    service,owner,_,_,source,_=evidence;lease=weekly(service,owner);repo='Kabutojira/WikiPlant'
    body={'repository':repo,'complete':False,'fresh':True,'releases':[
        {'version':'1.0.0','release_id':'synthetic','source_commit':'a'*40}]}
    version,_=source(json.dumps(body),{'source_type':'workflow_release_metadata','repository':repo})
    result=service.observe_release(owner,lease,repo,'1.0.0',metadata_version_id=str(version['id']),idempotency_key='partial')
    assert result['status']=='PARTIAL' and row(result,'release_check_v1')['data']['last_success_at']==''
    assert service.list_records(owner,'release_identity_v1')==[]
