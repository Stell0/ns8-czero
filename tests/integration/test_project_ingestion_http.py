# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""New collectors publish through the actual SDK/OAuth/Core/PostgreSQL boundary."""
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from c0_ingest.client import C0
from c0_ingest.errors import C0Error
from c0_projects.cli import bootstrap
from c0_projects.model import Item, source_config, sha
from c0_projects.publish import parts, sync_part, approved
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http
from test_auth_http import application

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


def setup(config):
    client=C0(config,bootstrap=True);client.select_space(config['space_id'])
    manifest={'project_id':config['space_id'],'space_id':config['space_id'],'name':'Synthetic ingestion project',
        'purpose':'Test original evidence','scope':'Fabricated documents only'}
    client.call('project_initialize',data={'manifest':manifest,'authorization_ref':'synthetic setup','idempotency_key':'setup'})
    definition=source_config({'id':'documents','adapter':'local_files','root':'inputs'})
    bootstrap(client,{'sources':[definition]},'synthetic explicit source approval')
    assert approved(client,definition)['data']['definition_hash']==sha(definition)
    return client,definition


def test_source_repeat_changed_and_lost_publication_reply_preserve_versions(sample_connection,knowledge_http,tmp_path,monkeypatch):
    config,_=sample_connection;client,definition=setup(config)
    try:
        item=Item('documents','article.md','Original','Original café evidence.\n'.encode(), 'text/markdown',provenance={'relative_path':'article.md'})
        part=next(parts(item));journal=tmp_path/'publication.json'
        original=client.call;lost=[]
        def fail_after_save(name,**arguments):
            result=original(name,**arguments)
            if name=='sources_ingest_text' and not lost:
                lost.append(result['id']);raise C0Error('Synthetic lost publication response')
            return result
        monkeypatch.setattr(client,'call',fail_after_save)
        with pytest.raises(C0Error):sync_part(client,part,journal,definition_hash=sha(definition),attempts=4,seconds=0)
        first=sync_part(client,part,journal,definition_hash=sha(definition),attempts=4,seconds=0)
        again=sync_part(client,part,journal,definition_hash=sha(definition),attempts=4,seconds=0)
        assert first==again and first['version_id']==lost[0]
        assert len(client.call('source_versions_list',source_id=first['source_id'])['versions'])==1
        changed=next(parts(Item('documents','article.md','Original',b'Changed original evidence.\n','text/markdown')))
        second=sync_part(client,changed,journal,definition_hash=sha(definition),attempts=4,seconds=0)
        assert second['source_id']==first['source_id'] and second['version_id']!=first['version_id']
        versions=client.call('source_versions_list',source_id=first['source_id'])['versions']
        assert len(versions)==2
        assert client.call('documents_get',version_id=first['version_id'])['body']=='Original café evidence.\n'
        history=client.call('project_records_list',kind='source_sync_history_v1')['objects']
        assert len(history)==2 and {r['data']['version_id'] for r in history}=={first['version_id'],second['version_id']}
    finally:client.close()


def test_queued_extraction_cannot_be_claimed_verified_and_cursors_do_not_advance(sample_connection,knowledge_http,tmp_path):
    config,_=sample_connection;client,definition=setup(config)
    try:
        part=next(parts(Item('documents','queued.md','Queued',b'Original queued extraction.')))
        with pytest.raises(C0Error):sync_part(client,part,tmp_path/'pending.json',definition_hash=sha(definition),attempts=1,seconds=0)
        pending=client.call('project_source_status_get',connector_id='documents',external_id=part.external_id)
        assert pending['data']['sync_status']=='partial' and pending['data']['extraction_status']=='queued'
        bad={k:v for k,v in pending['data'].items() if k!='key'};bad['sync_status']='verified'
        with pytest.raises(C0Error):
            client.call('project_source_status_set',data={'data':bad,'expected_revision':pending['revision'],'idempotency_key':'premature'})
        assert not client.call('project_records_list',kind='source_sync_history_v1')['objects']
    finally:client.close()


def test_partial_collection_keeps_success_cursor_and_recovers_with_fenced_revision(sample_connection,knowledge_http,tmp_path):
    from c0_projects.cli import connector_status
    from c0_projects.model import Batch
    config,_=sample_connection;client,definition=setup(config)
    try:
        from c0_projects.publish import save_snapshot
        original=Item('documents','cursor.md','Original cursor evidence',b'Synthetic persisted cursor evidence.')
        receipt=sync_part(client,next(parts(original)),tmp_path/'cursor.json',definition_hash=sha(definition),attempts=4,seconds=0)
        save_snapshot(client,original,[receipt]);proof=[receipt['receipt_id']]
        first=connector_status(client,definition,Batch(cursor={'page':1}),0,0)
        partial=connector_status(client,definition,Batch(cursor={'page':2},status='partial',errors=['github_rate_limit']),1,1,proof)
        assert json.loads(partial['data']['remote_cursor'])=={'page':1}
        assert json.loads(partial['data']['progress_cursor'])=={'page':2}
        assert partial['data']['last_success_at']==first['data']['last_success_at']
        assert partial['data']['attempt_count']==1 and partial['data']['retry_after']
        unverified=connector_status(client,definition,Batch(cursor={'page':3}),0,1)
        assert json.loads(unverified['data']['progress_cursor'])=={'page':2}
        assert json.loads(unverified['data']['remote_cursor'])=={'page':1}
        assert unverified['data']['attempt_count']==2
        stale={k:v for k,v in first['data'].items() if k!='key'}
        with pytest.raises(C0Error):client.call('project_connector_status_set',data={'data':stale,'expected_revision':1,'idempotency_key':'stale-collector'})
        recovered=connector_status(client,definition,Batch(cursor={'page':3}),1,1,proof)
        assert recovered['data']['status']=='complete' and recovered['data']['retry_after']==''
        assert json.loads(recovered['data']['remote_cursor'])=={'page':3}
    finally:client.close()


def test_binary_uses_actual_existing_rest_upload_and_immutable_citations(sample_connection,knowledge_http,tmp_path):
    import asyncio
    import httpx
    from c0_ingest.auth import credentials
    from czero_core.worker import Worker
    from test_auth_http import ORIGIN
    config,_=sample_connection;client,definition=setup(config)
    # Small genuine PDF fixture supplied by the existing extraction tests.
    original=(Path(__file__).parents[1]/'fixtures/evidence/sample.pdf').read_bytes()
    part=next(parts(Item('documents','original.pdf','Synthetic PDF',original,'application/pdf')))
    def binary(client,part,source):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=knowledge_http[0]),base_url=ORIGIN) as rest:
                response=await rest.post('/api/v1/sources/upload',params={'space_id':client.space_id},
                    headers={'Authorization':'Bearer '+credentials(client.config)},
                    data={'title':part.item.title,'media_type':part.item.media_type,'retain_original':'true',
                        'metadata':json.dumps({'external_key':sha([part.item.connector_id,part.external_id])})},
                    files={'file':('original.pdf',part.content,part.item.media_type)})
                assert response.status_code==202,response.text
                return response.json()
        version=asyncio.run(send())
        Worker(knowledge_http[4],knowledge_http[0].state.jobs.registry).tick()
        return version
    try:
        first=sync_part(client,part,tmp_path/'binary.json',definition_hash=sha(definition),binary_publisher=binary,attempts=3,seconds=0)
        second=sync_part(client,part,tmp_path/'binary.json',definition_hash=sha(definition),binary_publisher=binary,attempts=3,seconds=0)
        assert first==second
        assert len(client.call('source_versions_list',source_id=first['source_id'])['versions'])==1
        assert client.call('documents_get',version_id=first['version_id'])['body'].strip()
    finally:client.close()


def test_large_source_shrink_has_exact_current_snapshot_and_retained_old_parts(sample_connection,knowledge_http,tmp_path):
    from c0_projects.publish import save_snapshot
    config,_=sample_connection;client,definition=setup(config)
    try:
        large=Item('documents','large.md','Large original',('A bounded original paragraph.\n\n'*6000).encode(),'text/markdown')
        initial=[sync_part(client,part,tmp_path/'large.json',definition_hash=sha(definition),attempts=4,seconds=0) for part in parts(large,limit=131072)]
        assert len(initial)==2
        first=save_snapshot(client,large,initial)
        assert len(first['data']['part_receipt_ids'])==2
        short=Item('documents','large.md','Shortened original',b'Updated shorter original.\n','text/markdown')
        current=[sync_part(client,part,tmp_path/'large.json',definition_hash=sha(definition),attempts=4,seconds=0) for part in parts(short)]
        second=save_snapshot(client,short,current)
        assert second['id']==first['id'] and len(second['data']['part_receipt_ids'])==1
        assert save_snapshot(client,short,current)==second
        histories=client.call('project_records_list',kind='source_snapshot_history_v1')['objects']
        assert len(histories)==2 and histories[0]['data']['part_receipt_ids']==first['data']['part_receipt_ids']
        prior=client.call('objects_get',object_id=first['data']['part_receipt_ids'][0])
        assert prior['data']['version_id']==initial[0]['version_id']
        bad={'connector_id':'documents','external_id':short.external_id,'content_hash':short.content_hash,
            'part_receipt_ids':[row['receipt_id'] for row in initial],'expected_revision':second['revision'],'idempotency_key':'wrong-old-parts'}
        with pytest.raises(C0Error):client.call('project_source_snapshot_set',data=bad)
    finally:client.close()


def test_private_cli_dry_run_resume_status_and_verify_use_actual_c0(sample_connection,knowledge_http,tmp_path,monkeypatch):
    from types import SimpleNamespace
    from c0_projects import cli
    config,_=sample_connection;client,definition=setup(config)
    job=tmp_path/'job';job.mkdir(mode=0o700);(job/'config').mkdir(mode=0o700)
    (job/'.env').write_text('C0_FIXTURE=synthetic\n');(job/'.env').chmod(0o600)
    (job/'inputs').mkdir();original=job/'inputs/article.md';original.write_text('Synthetic original CLI evidence.')
    path=job/'config/project.json';path.write_text(json.dumps({'schema_version':1,'server_url':config['url'],
        'project_space_id':config['space_id'],'sources':[definition]}))
    monkeypatch.setattr(cli,'connection_settings',lambda _:config)
    def run(operation,**changes):
        args=SimpleNamespace(group='sources',operation=operation,config=path,job=job,dry_run=False,apply=True,authorization_ref=None)
        for field,value in changes.items():setattr(args,field,value)
        return cli.run(args)
    try:
        assert run('validate')[0]['writes_c0']==0
        assert run('scan')[0]['writes_c0']==0
        dry,code=run('sync',dry_run=True,apply=False)
        assert code==0 and dry['status']=='dry_run'
        assert client.call('sources_list')['sources']==[]
        saved,code=run('sync');assert code==0 and saved['status']=='SAVED' and saved['verified']==1
        original.write_text('Changed on disk after the frozen scan.')
        resumed,code=run('resume');assert code==0 and resumed['resource_refs'][0]['version_id']==saved['resource_refs'][0]['version_id']
        assert len(client.call('sources_list')['sources'])==1
        assert run('verify')[0]['verified']==1
        assert run('status')[0]['connectors'][0]['data']['status']=='complete'
        snapshots=client.call('project_records_list',kind='source_snapshot_v1')['objects']
        assert len(snapshots)==1 and snapshots[0]['data']['content_hash']==sha(b'Synthetic original CLI evidence.')
    finally:client.close()


def test_c0_space_source_uses_explicit_authorized_space_and_immutable_revision(sample_connection,knowledge_http,tmp_path):
    from c0_projects.adapters import collect
    config,_=sample_connection;client,definition=setup(config)
    try:
        page=client.call('wiki_pages_create',data={'slug':'synthetic-source','title':'Same topic label',
            'body':'Synthetic separately selected source knowledge.','idempotency_key':'source-page'})
        subscription=source_config({'id':'subscription','adapter':'c0_space','source_space_id':client.space_id,
            'authorization_ref':'synthetic explicit source read','include':['wiki']})
        batch=collect(subscription,root=tmp_path,source_client=client)
        assert batch.status=='complete' and len(batch.items)==1
        assert batch.items[0].provenance['space_id']==client.space_id
        assert batch.items[0].provenance['page_id']==page['id']
        assert batch.items[0].provenance['revision']==1 and batch.items[0].external_id=='wiki:'+page['id']
        with pytest.raises(C0Error):client.select_space(str(uuid4()),writable=False)
        assert client.space_id is None # Denial clears selection; no Shared fallback.
        with pytest.raises(C0Error):collect(subscription,root=tmp_path,source_client=client)
        client.select_space(config['space_id'],writable=False)
        assert collect(subscription,root=tmp_path,source_client=client).items[0].content==batch.items[0].content
    finally:client.close()


def test_same_external_item_in_two_connectors_has_independent_source_identity(sample_connection,knowledge_http,tmp_path):
    config,_=sample_connection;client,first=setup(config)
    second=source_config({'id':'independent','adapter':'local_files','root':'inputs'})
    try:
        bootstrap(client,{'sources':[first,second]},'synthetic independent connector approval')
        receipts=[]
        for definition in (first,second):
            part=next(parts(Item(definition['id'],'same.md','Same label',b'Same synthetic original content.')))
            receipts.append(sync_part(client,part,tmp_path/'connectors.json',definition_hash=sha(definition),attempts=4,seconds=0))
        assert receipts[0]['source_id']!=receipts[1]['source_id']
        assert len(client.call('project_records_list',kind='source_sync_v1')['objects'])==2
    finally:client.close()


def test_core_connector_approval_rejects_credential_urls_without_fetching(sample_connection,knowledge_http):
    config,_=sample_connection;client,_=setup(config)
    base=source_config({'id':'public-pages','adapter':'http','url':'https://example.org/page'})
    try:
        for field in ('apiKey','client_secret','X-Amz-Signature','client_assertion','sessionid','authorization'):
            with pytest.raises(C0Error):
                client.call('project_connector_set',data={'definition':{**base,'url':base['url']+'?'+field+'=synthetic-value'},
                    'authorization_ref':'synthetic setup','idempotency_key':'bad-url-'+field.replace('_','-')})
        assert len(client.call('project_records_list',kind='connector_v1')['objects'])==1
        assert client.call('project_connector_set',data={'definition':base,'authorization_ref':'synthetic public page approval',
            'idempotency_key':'public-page-approved'})['data']['definition']==base
    finally:client.close()


def test_changed_connector_definition_cannot_inherit_old_success_or_progress(sample_connection,knowledge_http,tmp_path):
    from c0_projects.cli import connector_status
    from c0_projects.model import Batch
    config,_=sample_connection;client,definition=setup(config)
    try:
        from c0_projects.publish import save_snapshot
        original=Item('documents','configured.md','Configured original',b'Synthetic configured source evidence.')
        receipt=sync_part(client,next(parts(original)),tmp_path/'configured.json',definition_hash=sha(definition),attempts=4,seconds=0)
        save_snapshot(client,original,[receipt])
        connector_status(client,definition,Batch(cursor={'offset':99,'inventory_hash':'old'}),1,1,[receipt['receipt_id']])
        changed={**definition,'root':'different-explicit-inputs'}
        bootstrap(client,{'sources':[changed]},'synthetic source selection change')
        current=connector_status(client,changed,Batch(cursor={},status='partial',errors=['source_unavailable']),0,1)
        assert current['data']['remote_cursor']=='' and current['data']['progress_cursor']==''
        assert current['data']['last_success_at']=='' and current['data']['attempt_count']==1
    finally:client.close()


def test_connector_cannot_advance_cursor_with_unbacked_verified_counts(sample_connection,knowledge_http):
    from c0_projects.cli import connector_status
    from c0_projects.model import Batch
    config,_=sample_connection;client,definition=setup(config)
    try:
        with pytest.raises(C0Error):connector_status(client,definition,Batch(cursor={'page':99}),1,1)
        with pytest.raises(C0Error):connector_status(client,definition,Batch(cursor={'page':99}),1,1,[str(uuid4())])
        assert client.call('project_records_list',kind='connector_sync_v1')['objects']==[]
    finally:client.close()


def test_source_sync_workflow_fences_status_commits_and_reuses_completed_scan(sample_connection,knowledge_http,tmp_path):
    from c0_projects.workflow import SourceWorkflow
    from c0_projects.publish import save_snapshot
    from c0_projects.cli import connector_status
    from c0_projects.model import Batch
    config,_=sample_connection;client,definition=setup(config)
    try:
        publisher=SourceWorkflow(client,'documents','synthetic-frozen-scan')
        # Long extraction polling renews ownership even between read calls.
        previous_expiry=publisher.run['lease_expiry'];publisher.renewed-=61
        publisher.call('project_get')
        assert publisher.run['lease_expiry']>previous_expiry
        assert publisher.run['fencing_generation']==1
        item=Item('documents','leased.md','Leased original',b'Synthetic fenced publication.')
        result=sync_part(publisher,next(parts(item)),tmp_path/'leased.json',definition_hash=sha(definition),attempts=4,seconds=0)
        snapshot=save_snapshot(publisher,item,[result])
        coverage=connector_status(publisher,definition,Batch(),1,1,[result['receipt_id']])
        finished=publisher.finish(coverage,True)
        assert finished['status']=='SAVED' and publisher.completed
        same=SourceWorkflow(client,'documents','synthetic-frozen-scan')
        assert same.completed
        assert len(client.call('project_records_list',kind='run_v1')['objects'])==1
        assert len(client.call('source_versions_list',source_id=result['source_id'])['versions'])==1
        # Actual persisted lease, not a mocked guard. An old owner cannot replay
        # a status receipt or alter its successful cursor after completion.
        saved=client.call('project_source_status_get',connector_id='documents',external_id=next(parts(item)).external_id)
        data={k:v for k,v in saved['data'].items() if k!='key'}
        with pytest.raises(C0Error):client.call('project_source_status_set',data={'lease':publisher.lease,'data':data,
            'expected_revision':saved['revision'],'idempotency_key':'old-source-owner'})
        with pytest.raises(C0Error):client.call('project_source_status_set',data={'data':data,
            'expected_revision':saved['revision'],'idempotency_key':'stale-owner-omits-fence'})
        assert client.call('project_record_get',kind='source_snapshot_v1',identity='documents:leased.md')['id']==snapshot['id']
    finally:client.close()
