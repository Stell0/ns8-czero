# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic weekly agent through actual signed OAuth, SDK and PostgreSQL."""
from uuid import uuid4
import pytest
from c0_ingest.errors import C0Error
from c0_projects.maintenance import check_release
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http
from test_auth_http import application
from test_project_ingestion_http import setup


def test_weekly_agent_checkpoints_review_and_release_readback(sample_connection,knowledge_http):
    config,_=sample_connection;client,_=setup(config)
    def call(name,**values):return client.call(name,data={**values,'idempotency_key':uuid4().hex})
    try:
        call('project_topic_set',topic={'topic_id':'anchor','label':'Synthetic anchor','classification':'user','authorization_ref':'synthetic:user'})
        wiki=call('wiki_pages_create',slug='weekly/synthetic',title='Synthetic weekly page',body='# Original\n\nSynthetic fixture only.',metadata={})
        run=call('project_run_claim',workflow_type='weekly',lease_owner='fake-weekly-agent',config_version=2)['records'][0]['data']
        lease={key:run[key] for key in ('run_id','lease_owner','fencing_generation')}
        with pytest.raises(C0Error):call('project_run_checkpoint',lease=lease,phase='configuration',status='SAVED',references=[],summary='Cannot skip inspection')
        for phase,kinds in (('configuration',('configuration',)),('references',('wiki','claims','documents','chunks','sources')),('queue',('queue','topics'))):
            references=[]
            for kind in kinds:
                response=call('project_audit_step',lease=lease,kind=kind,limit=10)
                assert response['status']=='SAVED'
                references.extend(row['id'] for row in response['records'] if row['type_name'].endswith('audit_v1'))
            call('project_run_checkpoint',lease=lease,phase=phase,status='SAVED',references=references,summary='Actual bounded structural inspection')
        call('project_run_checkpoint',lease=lease,phase='archive',status='SAVED',references=[],summary='No peripheral topics eligible')
        selection=call('project_semantic_select',lease=lease)
        header=next(row for row in selection['records'] if row['type_name'].endswith('semantic_round_v1'))
        selected=client.call('project_records_list',kind='semantic_selection_v1')['objects'][0]
        assert selected['data']['wiki_revision_id']==wiki['content']['id']
        call('project_semantic_review',lease=lease,selection_reference=selected['id'],data={'status':'reviewed',
            'assessment':'The actual synthetic revision was inspected.','assessment_ref':'synthetic:assessment',
            'limitations':['Fake agent, no real semantic provider.'],'citation_ids':[],'proposed_question':''})
        call('project_run_checkpoint',lease=lease,phase='semantic',status='SAVED',references=[header['id']],summary='One selected revision inspected')
        plan={'lease':lease,'repository':'Kabutojira/WikiPlant','installed_version':'0.1.0'}
        metadata={'repository':plan['repository'],'complete':True,'fresh':True,'releases':[
            {'version':'v0.2.0','release_id':'17','source_commit':'b'*40}]}
        observed=check_release(client,plan,collector=lambda _:metadata)
        release=next(row for row in observed['records'] if row['type_name'].endswith('release_check_v1'))
        assert release['data']['status']=='available'
        again=check_release(client,plan,collector=lambda _:metadata)
        assert next(row for row in again['records'] if row['type_name'].endswith('release_check_v1'))['id']==release['id']
        document=client.call('documents_get',version_id=release['data']['metadata_version_id'])
        source=next(row for row in client.call('sources_list')['sources'] if row['metadata'].get('source_type')=='workflow_release_metadata')
        versions=client.call('source_versions_list',source_id=source['id'])['versions']
        assert document['version_id']==release['data']['metadata_version_id']
        assert len(versions)==1 and versions[0]['state']=='ready'
        diagnostics=client.call('project_diagnostics_get')
        assert diagnostics['last_successful_runs']['weekly'] is None and not diagnostics['external_execution_verified']
        assert client.call('project_records_list',kind='budget_v1')['objects']==[]
    finally:client.close()
