# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""FAQ snapshots use real protected C0 publication, independently of website state."""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from c0_freshdesk import markdown
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


def test_saved_faq_publication_readback_unchanged_replacement_and_isolated_state(sample_connection,knowledge_http,tmp_path,monkeypatch):
    config,_=sample_connection;client,_=setup(config)
    definition=source_config({'id':'faq','adapter':'local_files','root':'data/faq/export'})
    cli.bootstrap(client,{'sources':[definition]},'synthetic published public FAQ approval')
    job=tmp_path/'job';job.mkdir(mode=0o700);(job/'config').mkdir(mode=0o700)
    (job/'.env').write_text('C0_FIXTURE=synthetic\n');(job/'.env').chmod(0o600)
    path=job/'config/faq.json';path.write_text(json.dumps({'schema_version':1,'server_url':config['url'],
        'project_space_id':config['space_id'],'sources':[definition]}))
    sentinel=job/'data/c0-projects/latest.json';atomic(sentinel,{'website':'preserve'})
    prior=sentinel.read_bytes();state=job/'data/faq'
    monkeypatch.setattr(cli,'connection_settings',lambda _:config)
    args=SimpleNamespace(group='sources',operation='resume',config=path,job=job,state_directory='data/faq',
        dry_run=True,apply=False,authorization_ref=None,private_github_authorization=None,batch_extraction=True)
    url='https://help.example.org/support/solutions/articles/17'
    def saved(body):
        item=Item('faq','17.md','Router FAQ',markdown({'title':'Router FAQ','description':body},url),
            'text/markdown',url,url,provenance={'source_type':'freshdesk_faq','article_id':17})
        directory=state/'scans'/uuid4().hex
        manifest=cli.save_scan(directory,[(definition,Batch(items=[item],cursor={'complete':True}))])
        atomic(state/'latest.json',{'directory':str(directory),'manifest_hash':sha(manifest)})
        return item
    try:
        item=saved('<p>Use the <strong>secure</strong> listener.</p><pre><code>configure --safe</code></pre>')
        result,code=cli.run(args);assert code==0 and result['status']=='dry_run'
        assert client.call('sources_list')['sources']==[]
        args.dry_run=False;args.apply=True
        first,code=cli.run(args);assert code==0 and first['verified']==1
        ref=first['resource_refs'][0]
        assert client.call('documents_get',version_id=ref['version_id'])['body']==item.content.decode()
        source=client.call('sources_get',source_id=ref['source_id'])
        assert source['metadata']['canonical_url']==url
        again,code=cli.run(args);assert code==0 and again['resource_refs'][0]['version_id']==ref['version_id']
        args.operation='verify';args.apply=False
        assert cli.run(args)[1]==0 and sentinel.read_bytes()==prior
        saved('<p>Changed current procedure: use port 7443.</p>')
        args.operation='resume';args.apply=True
        changed,code=cli.run(args);assert code==0
        current=changed['resource_refs'][0]
        assert current['source_id']==ref['source_id'] and current['version_id']!=ref['version_id']
        with pytest.raises(C0Error,match='content_superseded'):client.call('documents_get',version_id=ref['version_id'])
        assert sentinel.read_bytes()==prior and len(client.call('sources_list')['sources'])==1
    finally:client.close()
