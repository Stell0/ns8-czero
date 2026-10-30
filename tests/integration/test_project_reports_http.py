# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fake agent over actual signed OAuth/SDK/Core/PG; no external runner claim."""
from copy import deepcopy
from uuid import uuid4
import pytest
from c0_projects.model import Item,sha
from c0_projects.publish import save_snapshot,parts,sync_part
from c0_projects.reports import save_report,render
from c0_ingest.errors import C0Error
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http
from test_auth_http import application
from test_project_ingestion_http import setup
from test_project_evidence import finding,result_data
from test_project_workflows import candidate


def test_fake_agent_evidence_report_and_lost_response_resume_through_sdk(sample_connection,knowledge_http,tmp_path,monkeypatch):
    config,_=sample_connection;client,definition=setup(config)
    def call(name,**values):return client.call(name,data={**values,'idempotency_key':uuid4().hex})
    try:
        call('project_topic_set',topic={'topic_id':'anchor','label':'Synthetic anchor','classification':'user','authorization_ref':'synthetic:user'})
        part=next(parts(Item('documents','capacity.md','Synthetic original','La capacità sintetica è100 unità.'.encode(),'text/markdown')))
        stored=sync_part(client,part,tmp_path/'source.json',definition_hash=sha(definition),attempts=4,seconds=0)
        save_snapshot(client,part.item,[stored])
        document=client.call('documents_get',version_id=stored['version_id'])
        chunk=client.call('document_chunks_list',document_id=document['id'])['chunks'][0]
        entity=call('entities_create',kind='concept',label='Synthetic capacity')
        claim=call('claims_create',entity_id=entity['id'],predicate='capacity',value={'units':100},evidence_chunk_ids=[chunk['id']])
        run=call('project_run_claim',workflow_type='daily',lease_owner='fake-agent',config_version=2)['records'][0]['data']
        lease={key:run[key] for key in ('run_id','lease_owner','fencing_generation')}
        call('project_queue_admit',candidate=candidate('capacity'))
        reserved=call('project_attempt_reserve',lease=lease)
        attempt=next(row['data'] for row in reserved['records'] if row['type_name'].endswith('attempt_v1'))
        call('project_invocation_set',lease=lease,attempt_id=attempt['attempt_id'],state='started')
        saved=call('project_result_save',lease=lease,attempt_id=attempt['attempt_id'],
            data=result_data(finding(chunk,claim_id=claim['id'],claim_revision=claim['revision'])))
        result=next(row for row in saved['records'] if row['type_name'].endswith('result_v1'))
        call('project_invocation_set',lease=lease,attempt_id=attempt['attempt_id'],state='returned',result_reference=result['id'])
        wiki=call('wiki_pages_create',slug='learning/capacity',title='Synthetic learning',
            body='# Learning\n\nFabricated capacity constrains the approved goal.',
            metadata={'c0_project':{'project_id':client.space_id,'result_references':[result['id']]}})
        proof=call('project_result_publish',lease=lease,result_reference=result['id'],wiki_revision_ids=[wiki['content']['id']])
        publication=next(row for row in proof['records'] if row['type_name'].endswith('result_publication_v1'))
        call('project_research_complete',lease=lease,attempt_id=attempt['attempt_id'],commit_references=[publication['id']])
        publisher=call('project_run_claim',workflow_type='report_publication',lease_owner='fake-publisher',config_version=2,cycle_key='daily-report')['records'][0]['data']
        report_lease={key:publisher[key] for key in ('run_id','lease_owner','fencing_generation')}
        plan={'lease':report_lease,'report_type':'daily','local_date':run['local_cycle_date'],
            'sections':['Synthetic bounded fixture findings.' for _ in range(9)],'entries':[{'result_reference':result['id'],
                'disposition':'included','text':'We learned that fabricated capacity limits the approved synthetic goal.',
                'reason':'','assessment_ref':'synthetic:actual-agent-assessment'}]}
        original=client.call;lost=[]
        def lost_reply(name,**values):
            response=original(name,**values)
            if name=='project_report_finalize' and not lost:
                lost.append(response);raise C0Error('synthetic:lost-finalization-response')
            return response
        monkeypatch.setattr(client,'call',lost_reply)
        with pytest.raises(C0Error,match='lost-finalization'):save_report(client,plan)
        view=save_report(client,plan)
        assert view['report']['data']['saved_status']=='saved' and len(view['members'])==1
        assert view['deliveries']==[] and len(client.call('project_records_list',kind='report_history_v1')['objects'])==1
        budget=client.call('project_record_get',kind='budget_v1',identity=run['local_cycle_date'])
        assert budget['data']['used']==1
        readback=client.call('wiki_pages_get',page_id=view['report']['data']['wiki_page_id'],revision=view['report']['data']['wiki_revision'])
        assert readback['content']['body'].startswith('# Research report')
    finally:client.close()


def test_italian_renderer_uses_byte_ranges_and_rejects_oversized_or_missing_translation():
    plan={'lease':{'run_id':'synthetic','lease_owner':'test','fencing_generation':1},'report_type':'daily','local_date':'2026-10-25',
        'sections':['Novità e capacità sintetiche.' for _ in range(9)],'entries':[{'result_reference':str(uuid4()),
            'disposition':'included','text':'La capacità è cambiata: ciò influenza l’obiettivo.','reason':'','assessment_ref':'synthetic:assessment'}]}
    title,body,ranges=render(plan,'it');entry,start,end=ranges[0]
    assert 'Nuove conoscenze' in body and body.encode()[start:end].decode()==entry['text'] and 'Rapporto' in title
    with pytest.raises(C0Error,match='localized'):render(plan,'fr')
    huge=deepcopy(plan);huge['entries']*=500
    with pytest.raises(C0Error):render(huge,'it')


def test_report_cli_conflicting_dry_run_apply_stops_before_auth_or_network(tmp_path):
    import json
    from types import SimpleNamespace
    from c0_projects.cli import run
    config=tmp_path/'project.json';config.write_text(json.dumps({'schema_version':1,'server_url':'https://c0.example.org/mcp',
        'project_space_id':str(uuid4()),'sources':[]}))
    args=SimpleNamespace(group='project',operation='report',config=config,dry_run=True,apply=True,input=tmp_path/'input.json')
    with pytest.raises(C0Error,match='explicit_report_plan_and_apply'):run(args,client_factory=lambda *_:pytest.fail('Network must not run'))
