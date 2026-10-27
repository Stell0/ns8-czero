# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen private fixture replay crosses actual OAuth/SDK/Core/PostgreSQL."""
import io
import json
import urllib.error
from types import SimpleNamespace
from uuid import uuid4
import pytest
from c0_ingest.errors import C0Error
from c0_ingest.state import atomic
from c0_projects import cli
from c0_projects.model import Batch,Item,sha,source_config
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http
from test_auth_http import application
from test_project_ingestion_http import setup


def test_private_frozen_cli_resume_requires_current_consent_and_remote_access(sample_connection,knowledge_http,tmp_path,monkeypatch):
    config,_=sample_connection;client,_=setup(config)
    repository='fixture-c0-lab/synthetic-project'
    definition=source_config({'id':'private-repo','adapter':'github','repository':repository,'include':['issues']})
    cli.bootstrap(client,{'sources':[definition]},'synthetic explicit private destination approval')
    job=tmp_path/'job';job.mkdir(mode=0o700);(job/'config').mkdir(mode=0o700)
    (job/'.env').write_text('C0_FIXTURE=synthetic\n');(job/'.env').chmod(0o600)
    path=job/'config/project.json';path.write_text(json.dumps({'schema_version':1,'server_url':config['url'],
        'project_space_id':config['space_id'],'sources':[definition]}))
    state=job/'data/c0-projects';directory=state/'scans'/uuid4().hex
    item=Item(definition['id'],'issue:27','Fabricated private issue',b'Private synthetic evidence only.',provenance={
        'source_visibility':'private','repository':repository,'repository_id':'17','private_authorization_ref':'synthetic:old-consent'})
    manifest=cli.save_scan(directory,[(definition,Batch(items=[item],cursor={'complete':True}))])
    atomic(state/'latest.json',{'directory':str(directory),'manifest_hash':sha(manifest)})
    monkeypatch.setattr(cli,'connection_settings',lambda _:config)
    args=SimpleNamespace(group='sources',operation='resume',config=path,job=job,dry_run=False,apply=True,
        authorization_ref=None,private_github_authorization=None)
    try:
        with pytest.raises(C0Error):cli.run(args)
        assert client.call('sources_list')['sources']==[]
        assert client.call('project_records_list',kind='run_v1')['objects']==[]
        consent=job/'config/private.json';consent.write_text(json.dumps({'schema_version':1,'project_space_id':config['space_id'],
            'repositories':[repository],'authorization_ref':'synthetic:current-consent'}));consent.chmod(0o600)
        args.private_github_authorization=consent
        monkeypatch.setattr('github_vault.github_client.token',lambda:'synthetic-gh-credential')
        calls=[];allowed=[False]
        class Response(io.BytesIO):
            headers={}
        def remote(request,**_):
            calls.append(request.full_url)
            assert request.get_header('Authorization')=='Bearer synthetic-gh-credential'
            if not allowed[0]:raise urllib.error.HTTPError(request.full_url,403,'Forbidden',{},None)
            return Response(json.dumps({'id':17,'full_name':repository,'private':True}).encode())
        monkeypatch.setattr('github_vault.github_client.open_url',remote)
        with pytest.raises(C0Error,match='private_source_access_not_current'):cli.run(args)
        assert client.call('sources_list')['sources']==[]
        assert client.call('project_records_list',kind='run_v1')['objects']==[]
        allowed[0]=True
        result,code=cli.run(args)
        assert code==0 and result['status']=='SAVED' and result['verified']==1
        assert len(calls)==2 and all(url=='https://api.github.com/repos/'+repository for url in calls)
        version=client.call('source_versions_list',source_id=result['resource_refs'][0]['source_id'])['versions'][0]
        assert version['state']=='ready' and 'synthetic-gh-credential' not in json.dumps(version)
        assert client.call('project_records_list',kind='budget_v1')['objects']==[]
        args.private_github_authorization=None
        with pytest.raises(C0Error):cli.run(args)
        assert len(client.call('sources_list')['sources'])==1
    finally:client.close()
