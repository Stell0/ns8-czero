# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fabricated en/it projects, deterministic fake agents, real SDK and PostgreSQL."""
import json
from pathlib import Path
from uuid import uuid4
import pytest
from c0_ingest.client import C0
from c0_projects.adapters import collect
from c0_projects.cli import bootstrap,connector_status
from c0_projects.exporting import export_project,verify_export
from c0_projects.formats import load_data
from c0_projects.model import source_config,sha
from c0_projects.publish import parts,sync_part,save_snapshot
from c0_projects.reports import save_report
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http
from test_auth_http import application
from test_project_evidence import finding,result_data
from test_project_workflows import candidate,row

EXAMPLES=Path(__file__).parents[2]/'samples/ingestion/examples/projects'


@pytest.mark.parametrize('shape,language,daily,weekly',[('robotelier','en','06:00','08:00'),('myprojects','it','07:00','07:00')])
def test_synthetic_daily_weekly_and_export_are_recoverable_and_project_bound(sample_connection,knowledge_http,tmp_path,shape,language,daily,weekly):
    config,_=sample_connection;client=C0(config,bootstrap=True);client.select_space(config['space_id'])
    root=EXAMPLES/shape;manifest=load_data((root/'manifest.yml').read_text(),'yaml')
    manifest.update(project_id=client.space_id,space_id=client.space_id,primary_topic_ids=[])
    topics=json.loads((root/'topics.json').read_text());primary=[topic['topic_id'] for topic in topics]
    def call(name,**values):return client.call(name,data={**values,'idempotency_key':uuid4().hex})
    def lease(run):return {key:run[key] for key in ('run_id','lease_owner','fencing_generation')}
    def checkpoint(current,phase,references):
        return call('project_run_checkpoint',lease=current,phase=phase,status='SAVED',references=references,summary='Actual bounded synthetic readback')
    def report(current,run,kind,result):
        prose=('La capacità sintetica osservata limita lo sviluppo previsto; non è un dato reale.' if language=='it' else
            'Observed synthetic capacity constrains planned development; this is fabricated evidence.')
        view=save_report(client,{'lease':current,'report_type':kind,'local_date':run['local_cycle_date'],
            'sections':[prose]*9,'entries':[{'result_reference':result['id'],'disposition':'included','text':prose,
                'reason':'','assessment_ref':'synthetic:fake-agent-report'}]})
        checkpoint(current,'report',[view['report']['id']])
        return view
    try:
        call('project_initialize',manifest=manifest,authorization_ref='synthetic:explicit-project-setup')
        for topic in topics:call('project_topic_set',topic=topic)
        definitions=[source_config(value) for value in load_data((root/'sources.yml').read_text(),'yaml')['sources']]
        bootstrap(client,{'sources':definitions},'synthetic:explicit-source-approval')
        stored=client.call('project_get');manifest=stored['data']['manifest'];manifest['primary_topic_ids']=primary;manifest['state']['initialized']=True
        configured=call('project_configure',manifest=manifest,expected_revision=stored['revision'],authorization_ref='synthetic:explicit-primary-topics')
        version=configured['data']['version'];before=configured['data']['manifest']
        schedule=client.call('project_schedule_get')
        assert before['language']==language and before['schedule']['daily_local_time']==daily and before['schedule']['weekly_local_time']==weekly
        assert not before['schedule']['enabled'] and not schedule['installed_by_c0']
        definition=definitions[0]
        if shape=='myprojects':
            fixture=json.loads((root/'github-responses.json').read_text());requests=[]
            class MockGitHub:
                def get(self,path):
                    requests.append(path);response=fixture['responses'][path]
                    return response['body'],response.get('next')
            batch=collect(definition,root=root,github=MockGitHub())
            assert any('page=2' in path for path in requests) and len(batch.items)==9
            assert any('fixture-contributor' in item.content.decode() for item in batch.items)
        else:batch=collect(definition,root=root)
        assert batch.status=='complete' and batch.items
        receipts=[]
        for item in batch.items:
            saved=[sync_part(client,part,tmp_path/'sync.json',definition_hash=sha(definition),attempts=4,seconds=0) for part in parts(item)]
            save_snapshot(client,item,saved);receipts.extend(saved)
        connector_status(client,definition,batch,len(receipts),len(receipts),[entry['receipt_id'] for entry in receipts])
        daily_run=call('project_run_claim',workflow_type='daily',lease_owner='synthetic-daily',config_version=version,lease_seconds=900)['records'][0]['data']
        current=lease(daily_run);monitor_refs=[]
        for topic_id in primary:
            cycle=row(call('project_monitor_begin',lease=current,topic_id=topic_id),'monitor_cycle_v1')['data']
            query=row(call('project_monitor_reserve',lease=current,cycle_id=cycle['cycle_id'],kind='query',request_id='bounded-search',
                request_text='Fabricated primary-topic search; no external provider.'),'monitor_call_v1')['data']
            call('project_monitor_observe',lease=current,call_id=query['call_id'],state='started')
            call('project_monitor_observe',lease=current,call_id=query['call_id'],state='succeeded',external_reference='synthetic:observed-fake-search',
                summary='Observed bounded synthetic provider response.',selected_sources=[])
            monitor_refs.append(row(call('project_monitor_finish',lease=current,cycle_id=cycle['cycle_id'],status='no_material_update',
                summary='Bounded synthetic search found no material update.'),'monitor_success_v1')['id'])
        checkpoint(current,'monitoring',monitor_refs)
        assert client.call('project_records_list',kind='budget_v1')['objects']==[]
        call('project_queue_admit',candidate=candidate('synthetic-capacity',topic_id=primary[0],anchor_ids=[primary[0]]))
        attempt=row(call('project_attempt_reserve',lease=current),'attempt_v1')['data']
        call('project_invocation_set',lease=current,attempt_id=attempt['attempt_id'],state='started')
        document=client.call('documents_get',version_id=receipts[0]['version_id'])
        chunk=client.call('document_chunks_list',document_id=document['id'])['chunks'][0]
        entity=call('entities_create',kind='concept',label='Shared synthetic label')
        claim=call('claims_create',entity_id=entity['id'],predicate='synthetic-capacity',value={'units':100},evidence_chunk_ids=[chunk['id']])
        result=row(call('project_result_save',lease=current,attempt_id=attempt['attempt_id'],
            data=result_data(finding(chunk,claim_id=claim['id'],claim_revision=claim['revision']))),'result_v1')
        call('project_invocation_set',lease=current,attempt_id=attempt['attempt_id'],state='returned',result_reference=result['id'])
        wiki=call('wiki_pages_create',slug='synthetic/learning',title='Apprendimento sintetico' if language=='it' else 'Synthetic learning',
            body='# Synthetic learning\n\nFabricated capacity affects the approved goal.',
            metadata={'c0_project':{'project_id':client.space_id,'result_references':[result['id']]}})
        publication=row(call('project_result_publish',lease=current,result_reference=result['id'],wiki_revision_ids=[wiki['content']['id']]),'result_publication_v1')
        call('project_research_complete',lease=current,attempt_id=attempt['attempt_id'],commit_references=[publication['id']])
        for phase in ('research','evidence','synthesis'):checkpoint(current,phase,[publication['id']])
        daily_report=report(current,daily_run,'daily',result)
        readback=client.call('wiki_pages_get',page_id=daily_report['report']['data']['wiki_page_id'])
        assert ('Nuove conoscenze' if language=='it' else 'New learnings') in readback['content']['body']
        weekly_run=call('project_run_claim',workflow_type='weekly',lease_owner='synthetic-weekly',config_version=version,lease_seconds=900)['records'][0]['data']
        current=lease(weekly_run)
        for phase,kinds in (('configuration',('configuration',)),('references',('wiki','claims','documents','chunks','sources')),('queue',('queue','topics'))):
            references=[]
            for kind in kinds:
                for _ in range(100):
                    response=call('project_audit_step',lease=current,kind=kind,limit=10)
                    if response['status']=='SAVED':break
                else:pytest.fail('Synthetic bounded audit did not finish')
                references.append(row(response,'audit_v1')['id'])
            checkpoint(current,phase,references)
        checkpoint(current,'archive',[])
        header=row(call('project_semantic_select',lease=current),'semantic_round_v1')
        for reference in header['data']['selected_ids']:
            selection=client.call('objects_get',object_id=reference)
            actual=client.call('wiki_pages_get',page_id=selection['data']['page_id'],revision=selection['data']['wiki_revision'])
            assert actual['content']['id']==selection['data']['wiki_revision_id']
            call('project_semantic_review',lease=current,selection_reference=reference,data={'status':'reviewed',
                'assessment':'Actual fabricated revision read and assessed.','assessment_ref':'synthetic:fake-semantic-review',
                'limitations':['No actual external agent or unattended execution.'],'citation_ids':[],'proposed_question':''})
        checkpoint(current,'semantic',[header['id']])
        weekly_report=report(current,weekly_run,'weekly',result)
        diagnostics=client.call('project_diagnostics_get')
        assert all(diagnostics['last_successful_runs'][kind] for kind in ('daily','weekly'))
        assert not diagnostics['external_execution_verified']
        assert client.call('project_record_get',kind='budget_v1',identity=daily_run['local_cycle_date'])['data']['used']==1
        assert client.call('project_get')['data']['manifest']==before
        snapshot=tmp_path/'export';assert export_project(client,snapshot)['status']=='VALIDATED'
        assert verify_export(snapshot)['status']=='VALIDATED'
        assert weekly_report['report']['data']['saved_status']=='saved'
    finally:client.close()
