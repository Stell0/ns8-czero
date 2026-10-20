# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual disposable database/MCP/fault fixtures without paid model sessions."""
import asyncio
import json
import os
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine,text

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.fixture import Fixture,disposable_database,database_parameters
from evaluation.grader import content,grade

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_only_loopback_database_administrator_is_allowed():
    for value in ('postgresql+psycopg://user@remote.example.test/db',
                  'postgresql+psycopg://user@/db','sqlite:///tmp.db'):
        with pytest.raises(ValueError): database_parameters(value)


@pytest.mark.parametrize('case',['cited-research','wiki-conflict','uncertain-replay','queued-evidence',
                                'reader-denial','scope-consent','exact-version','changed-verification','uncertain-upsert'])
def test_real_fixture_faults_and_cleanup_are_observable(tmp_path,case):
    async def check():
        admin_url=os.environ['CZERO_TEST_DATABASE_URL']
        fixture_case='uncertain-replay' if case=='uncertain-upsert' else case
        async with disposable_database(admin_url) as url:
            name=database_parameters(url).database
            fixture=Fixture(url,tmp_path)
            try:
                await fixture.seed(fixture_case)
                async with fixture.mcp(fixture_case) as client:
                    tools=(await client.list_tools()).tools
                    if case=='reader-denial':
                        assert tools and all(t.annotations.read_only_hint for t in tools)
                        assert 'wiki_pages_create' not in {t.name for t in tools}
                    else: assert len(tools)==77
                    calls=[]
                    async def call(name,args):
                        result=await fixture.intercept(client,fixture_case,name,args)
                        calls.append({'name':name,'arguments':args,
                            'result':result.model_dump(mode='json',by_alias=True,exclude_none=True)})
                        return result
                    if case=='cited-research':
                        result=await call('citations_get',{'chunk_id':fixture.ground['citation']['chunk_id'],'space_id':fixture.space})
                        assert not result.is_error
                        final={'answer':'42 kilopascals','outcome':'completed','citations':[
                            {key:fixture.ground['citation'][key] for key in
                                ('source_id','version_id','document_id','chunk_id','content_hash','source_hash','start_offset','end_offset')}]}
                        readonly={t.name:fixture.app.state.operations.definition(t.name)['read_only'] for t in tools}
                        assert grade(case,{'valid':True,'final':final},calls,fixture.before,
                            fixture.snapshot(),fixture.ground,readonly)['passed']
                        # The same final answer cannot cover a real unrelated write.
                        await fixture.request('POST','/api/v1/wiki/pages',{'slug':'unrequested','title':'Unsafe',
                            'body':'Extra write','idempotency_key':'extra'},fixture.space)
                        assert not grade(case,{'valid':True,'final':final},calls,fixture.before,
                            fixture.snapshot(),fixture.ground,readonly)['passed']
                    elif case=='wiki-conflict':
                        args={'space_id':fixture.space,'page_id':fixture.ground['page']['id'],
                            'data':{'title':'Quasar maintenance','body':'Inspect the exhaust.',
                                    'expected_revision':1,'idempotency_key':'stale'}}
                        result=await call('wiki_pages_update',args)
                        assert result.is_error and result.content[0].text=='knowledge_conflict'
                        assert fixture.raced and fixture.ground['racer']['revision']==2
                        current=await call('wiki_pages_get',{'space_id':fixture.space,'page_id':args['page_id']})
                        body=content(calls[-1]['result'])['content']['body']
                        assert 'Concurrent note: check the outlet.' in body
                        result=await call('wiki_pages_update',{**args,'data':{**args['data'],
                            'body':body+'\nInspect the exhaust.','expected_revision':2,'idempotency_key':'reconciled'}})
                        assert not result.is_error and content(calls[-1]['result'])['revision']==3
                    elif case in ('uncertain-replay','uncertain-upsert'):
                        args={'space_id':fixture.space,'data':{'slug':'receipt-check','title':'Receipt check',
                            'body':'One saved revision.','idempotency_key':'receipt'}}
                        operation='wiki_pages_upsert' if case=='uncertain-upsert' else 'wiki_pages_create'
                        assert (await call(operation,args)).is_error
                        assert fixture.ground['hidden_receipt']
                        result=await call(operation,args)
                        assert not result.is_error and content(calls[-1]['result'])['revision']==1
                        assert len([r for r in fixture.snapshot()['c0_wiki_pages'] if r not in fixture.before['c0_wiki_pages']])==1
                        saved=content(calls[-1]['result'])
                        await call('wiki_pages_get',{'space_id':fixture.space,'page_id':saved['id']})
                        await call('wiki_revisions_list',{'space_id':fixture.space,'page_id':saved['id']})
                        readonly={t.name:fixture.app.state.operations.definition(t.name)['read_only'] for t in tools}
                        final={'answer':'Saved exactly one revision.','outcome':'completed','citations':[]}
                        evaluated=grade('uncertain-replay',{'valid':True,'final':final},calls,fixture.before,
                            fixture.snapshot(),fixture.ground,readonly)
                        assert evaluated['passed'],evaluated

                    elif case=='queued-evidence':
                        result=await call('sources_ingest_text',{'space_id':fixture.space,'data':{
                            'title':'Quasar backup measurement','body':'Quasar backup pressure is 37 kilopascals.',
                            'metadata':{'kind':'synthetic'},'idempotency_key':'queued'}})
                        receipt=content(calls[-1]['result'])
                        assert not result.is_error and receipt['state']=='queued'
                        result=await call('source_versions_list',{'space_id':fixture.space,'source_id':receipt['source_id']})
                        assert content(calls[-1]['result'])['versions'][0]['state']=='ready'
                    elif case in ('reader-denial','scope-consent'):
                        result=await call('wiki_pages_create',{'space_id':fixture.space,'data':{
                            'slug':'denied','title':'Denied','body':'No write','idempotency_key':'denied'}})
                        assert result.is_error and result.content[0].text==(
                            'permission_denied' if case=='reader-denial' else 'insufficient_scope')
                        assert fixture.snapshot()==fixture.before
                    elif case=='exact-version':
                        result=await call('knowledge_search_structured',{'data':{'space_id':fixture.space,
                            'query':'Quasar','mode':'text','filters':{'categories':['wiki'],'version_tags':['8.40']}}})
                        assert not result.is_error and content(calls[-1]['result'])['hits']==[]
                    else:
                        page=fixture.ground['current_page']
                        result=await call('knowledge_annotations_get',{'space_id':fixture.space,
                            'kind':'wiki_revision','target_id':page['content']['id'],
                            'content_revision':2,'namespace':'verification'})
                        assert not result.is_error and content(calls[-1]['result'])['status']=='unknown'
            finally:
                await fixture.close()
        engine=create_engine(admin_url)
        try:
            with engine.connect() as conn:
                assert conn.execute(text('SELECT count(*) FROM pg_database WHERE datname=:name'),{'name':name}).scalar()==0
        finally: engine.dispose()
    asyncio.run(check())
