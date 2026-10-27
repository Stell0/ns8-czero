# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from uuid import uuid4
from c0_ingest.client import C0
from c0_projects.adapters import collect
from c0_projects.model import source_config,sha
from c0_projects.publish import parts,sync_part
from c0_projects.cli import bootstrap
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http
from test_auth_http import application
from test_project_ingestion_http import setup


def test_separate_github_knowledge_space_is_a_scoped_incremental_source(sample_connection,knowledge_http,tmp_path,space_http):
    config,_=sample_connection;target,_=setup(config);source=C0(config,bootstrap=True)
    try:
        space=target.call('spaces_create',data={'name':'Synthetic repository knowledge','idempotency_key':uuid4().hex})
        space_http[1].append(space['id']);source.select_space(space['id'])
        name='fixture_repo_'+uuid4().hex
        source.call('object_types_create',data={'name':name,'label':'Synthetic repository','schema':{'type':'object','properties':{
            'repository':{'type':'string','maxLength':128},'development':{'type':'string','maxLength':256}},
            'required':['repository','development'],'additionalProperties':False},'unique_fields':['repository']})
        record=source.call('objects_create',data={'type_name':name,'data':{
            'repository':'fixture-c0-lab/synthetic-project','development':'Original synthetic development'}})
        definition=source_config({'id':'repo-subscription','adapter':'c0_space','source_space_id':space['id'],
            'authorization_ref':'synthetic explicit authorized subscription','include':['objects:'+name]})
        bootstrap(target,{'sources':[definition]},'synthetic destination source approval')
        first=collect(definition,source_client=source,root=tmp_path)
        assert first.status=='complete' and len(first.items)==1 and target.space_id==config['space_id']
        stored=sync_part(target,next(parts(first.items[0])),tmp_path/'first.json',definition_hash=sha(definition),attempts=4,seconds=0)
        old=target.call('documents_get',version_id=stored['version_id'])['body']
        assert 'Original synthetic development' in old and first.items[0].provenance['object_id']==record['id']
        source.call('objects_update',object_id=record['id'],data={'data':{
            'repository':'fixture-c0-lab/synthetic-project','development':'Changed synthetic development'},'expected_revision':1})
        second=collect(definition,source_client=source,cursor=first.cursor,root=tmp_path)
        updated=sync_part(target,next(parts(second.items[0])),tmp_path/'changed.json',definition_hash=sha(definition),attempts=4,seconds=0)
        assert updated['source_id']==stored['source_id'] and updated['version_id']!=stored['version_id']
        assert second.items[0].provenance['revision']==2 and second.cursor['object_after']>first.cursor['object_after']
        assert target.call('documents_get',version_id=stored['version_id'])['body']==old
        assert len(target.call('source_versions_list',source_id=stored['source_id'])['versions'])==2
    finally:source.close();target.close()
