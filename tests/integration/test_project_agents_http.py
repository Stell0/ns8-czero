# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual OAuth/SDK/PG package generation is read-only; host installation is not exercised."""
import base64
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile
import pytest
from c0_projects.agent_packages import save_package
from c0_ingest.errors import C0Error
from test_auth_http import application
from test_mcp_http import transport
from test_spaces_http import space_http
from test_knowledge_http import knowledge_http
from test_ingestion_samples_http import sample_connection,counts
from test_project_ingestion_http import setup


def test_project_skill_and_plugin_download_readback_preserve_all_knowledge(sample_connection,knowledge_http,tmp_path):
    config,_=sample_connection;client,_=setup(config)
    try:
        before=counts(knowledge_http[4],client.space_id)
        for format in ('skill','plugin'):
            target=tmp_path/('project.'+('skill' if format=='skill' else 'zip'))
            result=save_package(client,target,format=format,connection='asdk_app_fixture')
            assert result['status']=='SAVED' and result['installed'] is False
            assert target.stat().st_mode & 0o777==0o600
            with zipfile.ZipFile(target) as archive:
                root='' if format=='skill' else 'skills/'+next(p.split('/')[1] for p in archive.namelist() if p.endswith('/SKILL.md'))+'/'
                binding=json.loads(archive.read(root+'references/project-binding.md').decode().split('```json\n',1)[1].split('\n```',1)[0])
                assert binding['project_id']==client.space_id and binding['manifest_version']==2
            with pytest.raises(FileExistsError):save_package(client,target,format=format,connection='asdk_app_fixture')
        assert counts(knowledge_http[4],client.space_id)==before
        with pytest.raises(C0Error):save_package(client,tmp_path/'invalid.zip',format='plugin',connection='https://invalid.example.org/private')
        assert not (tmp_path/'invalid.zip').exists()
    finally:client.close()


def test_project_cli_without_sources_generates_and_reads_schedule_without_mutation(sample_connection,knowledge_http,tmp_path,monkeypatch):
    from c0_projects import cli
    config,_=sample_connection;client,_=setup(config)
    job=tmp_path/'job';job.mkdir(mode=0o700);(job/'config').mkdir(mode=0o700)
    (job/'.env').write_text('C0_FIXTURE=synthetic\n');(job/'.env').chmod(0o600)
    path=job/'config/project.json';path.write_text(json.dumps({'schema_version':1,'server_url':config['url'],
        'project_space_id':config['space_id'],'sources':[]}))
    monkeypatch.setattr(cli,'connection_settings',lambda _:config)
    args=SimpleNamespace(group='project',operation='skill',config=path,job=job,dry_run=False,apply=False,
        authorization_ref=None,output=tmp_path/'generated.skill',format='skill',chatgpt_app_id='')
    try:
        before=counts(knowledge_http[4],client.space_id)
        result,code=cli.run(args);assert code==0 and result['status']=='SAVED'
        args.operation='schedule';schedule,code=cli.run(args)
        assert code==0 and schedule['space_id']==client.space_id and schedule['installed_by_c0'] is False
        assert counts(knowledge_http[4],client.space_id)==before
    finally:client.close()


def test_fake_external_agent_observes_monitoring_and_readback_through_actual_sdk(sample_connection,knowledge_http):
    config,_=sample_connection;client,_=setup(config)
    try:
        client.call('project_topic_set',data={'topic':{'topic_id':'anchor','label':'Synthetic approved anchor',
            'classification':'user','authorization_ref':'synthetic:user-track'},'idempotency_key':'anchor'})
        stored=client.call('project_get');manifest=stored['data']['manifest'];manifest['primary_topic_ids']=['anchor']
        manifest['state']['initialized']=True
        updated=client.call('project_configure',data={'manifest':manifest,'expected_revision':stored['revision'],
            'authorization_ref':'synthetic:user-primary','idempotency_key':'primary'})
        claimed=client.call('project_run_claim',data={'workflow_type':'daily','lease_owner':'synthetic-fake-agent',
            'config_version':updated['data']['version'],'idempotency_key':'daily'})
        run=claimed['records'][0]['data'];lease={key:run[key] for key in ('run_id','lease_owner','fencing_generation')}
        with pytest.raises(C0Error):client.call('project_attempt_reserve',data={'lease':lease,'idempotency_key':'before-monitor'})
        cycle=client.call('project_monitor_begin',data={'lease':lease,'topic_id':'anchor','idempotency_key':'begin'})['records'][0]['data']
        reservation={'lease':lease,'cycle_id':cycle['cycle_id'],'kind':'query','request_id':'query-one',
            'request_text':'Synthetic fake-provider bounded search','idempotency_key':'reserve'}
        reserved=client.call('project_monitor_reserve',data=reservation)
        assert client.call('project_monitor_reserve',data=reservation)==reserved
        call=reserved['records'][0]['data']
        client.call('project_monitor_observe',data={'lease':lease,'call_id':call['call_id'],'state':'started','idempotency_key':'start'})
        client.call('project_monitor_observe',data={'lease':lease,'call_id':call['call_id'],'state':'failed',
            'summary':'Synthetic provider timeout','idempotency_key':'failed'})
        with pytest.raises(C0Error):client.call('project_monitor_finish',data={'lease':lease,'cycle_id':cycle['cycle_id'],
            'status':'no_material_update','summary':'Cannot mislabel failure','idempotency_key':'invalid-finish'})
        result=client.call('project_monitor_finish',data={'lease':lease,'cycle_id':cycle['cycle_id'],
            'status':'partial','summary':'Bounded search failed; previous coverage unchanged','idempotency_key':'partial'})
        assert result['status']=='PARTIAL'
        saved=client.call('project_record_get',kind='monitor_cycle_v1',identity=cycle['cycle_id'])
        assert saved['data']['queries_used']==1 and saved['data']['successful_watermark']==''
        assert client.call('project_records_list',kind='monitor_watermark_v1')['objects']==[]
        assert client.call('project_records_list',kind='budget_v1')['objects']==[]
    finally:client.close()
