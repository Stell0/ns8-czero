# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from types import SimpleNamespace
from uuid import uuid4
import pytest
from c0_ingest.errors import C0Error
from c0_projects.cli import run
from c0_projects.exporting import export_project
from c0_projects.static_export import export_static
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http
from test_auth_http import application
from test_project_ingestion_http import setup


def test_static_pages_and_saved_report_require_explicit_public_selection(sample_connection,knowledge_http,tmp_path):
    config,_=sample_connection;client,_=setup(config)
    def call(name,**values):return client.call(name,data={**values,'idempotency_key':uuid4().hex})
    try:
        page=call('wiki_pages_create',slug='public/learning',title='Fabricated public learning',
            body='# Synthetic learning\n\n<script>untrusted()</script>\n\n![inactive](https://example.org/tracker.png)\n',
            metadata={'static_publish':{'public':True}})
        private=call('wiki_pages_create',slug='private/unselected',title='Private fixture',body='# Private fixture',metadata={})
        call('project_run_claim',workflow_type='daily',lease_owner='synthetic-daily',config_version=2)
        claimed=call('project_run_claim',workflow_type='report_publication',lease_owner='synthetic-publisher',config_version=2,cycle_key='public-report')['records'][0]['data']
        lease={key:claimed[key] for key in ('run_id','lease_owner','fencing_generation')}
        header=call('project_report_prepare',lease=lease,report_type='daily')['records'][0]
        report=call('wiki_pages_create',slug='public/report',title='Public synthetic report',
            body='# Synthetic report\n\n[Learning](./wiki?page_id='+page['id']+'&revision=1&space_id='+client.space_id+
                ')\n\n[Evidence](./sources?source_id='+str(uuid4())+')',metadata={'static_publish':{'public':True},
                    'c0_project':{'project_id':client.space_id,'report_reference':header['id'],'language':'en'}})
        call('project_report_finalize',lease=lease,report_reference=header['id'],wiki_revision_id=report['content']['id'])
        snapshot=tmp_path/'snapshot';assert export_project(client,snapshot)['status']=='VALIDATED'
        selection={'schema_version':1,'project_id':client.space_id,'wiki_revisions':[page['content']['id']],'report_references':[header['id']]}
        before=client.writes;result=export_static(snapshot,selection,tmp_path/'static')
        assert result['status']=='VALIDATED' and result['pages']==2 and not result['publication_performed'] and client.writes==before
        output=(tmp_path/'static/content'/ (page['id']+'.md')).read_text()
        assert '<script>' not in output and '&lt;script&gt;' in output and 'tracker.png' not in output
        report_body=(tmp_path/'static/content'/(report['id']+'.md')).read_text()
        assert page['id']+'.md' in report_body and './sources?' not in report_body and 'evidence retained in C0' in report_body
        assert not (tmp_path/'static/content'/(private['id']+'.md')).exists()
        assert json.loads((tmp_path/'static/static-manifest.json').read_text())['reports']=={header['id']:report['content']['id']}
        with pytest.raises(C0Error):export_static(snapshot,{**selection,'wiki_revisions':[private['content']['id']]},tmp_path/'denied')
        selection_path=tmp_path/'selection.json';selection_path.write_text(json.dumps(selection))
        args=SimpleNamespace(group='export',operation='static',input=snapshot,selection=selection_path,output=tmp_path/'cli-static',apply=False)
        assert run(args,client_factory=lambda *_:pytest.fail('Static export is offline'))[0]['publication_performed'] is False
    finally:client.close()
