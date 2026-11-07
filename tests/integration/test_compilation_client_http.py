# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Extracted installed instructions and external steps against actual SQL/REST/MCP."""
import asyncio
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import zipfile

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'scripts'),str(ROOT/'tests')]
from agentic_retrieval.fixture import paired_fixture
from evaluation.fixture import ORIGIN
from evaluation.skill_input import load_plugin
from c0_ingest.client import C0
from czero_app.agent_packages import plugin_payload, zip_bytes
from czero_core.compilation_client import navigation_plan, compile_plan, verify_pending
from czero_core.compilation_plans import plan_hash
from czero_core.compilation_schema import defaults
from test_knowledge_compilation_baseline import bind_response


@pytest.mark.parametrize('mode', ['auto','legacy'])
def test_installed_skill_multiple_source_only_concepts_apply_and_read_back_over_mcp(tmp_path, mode):
    # Install the generated archive, including linked references; no source-only Markdown shortcut.
    directory = tmp_path/'installed-plugin'; directory.mkdir()
    payload = plugin_payload(ORIGIN+'/mcp','asdk_app_fixture','compiler-fixture')
    with zipfile.ZipFile(BytesIO(zip_bytes(payload))) as archive:
        archive.extractall(directory)
    instructions, package = load_plugin(directory)
    assert package['version'] == '1.6.0'
    assert 'skills/c0-knowledge-compiler/SKILL.md' in package['files']
    assert 'references/compiler.md' in package['files'] and 'compilation_verify' in instructions
    async def check():
        originals = json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'], tmp_path/'databases', originals) as (control, fixture, corpus):
            assert await control.corpus() == await fixture.corpus()
            # This explicit test-only Admin setup is not part of the compiler client/skill.
            await fixture.request('PUT','/api/v1/compilation/policy', {'data':{
                **defaults(),'enabled':True,'profile_id':'sourced-knowledge-v1',
                'allowed_target_kinds':['page','annotation','entity','claim','relation']}, 'expected_revision':0,
                'authorization_ref':'synthetic:approved-fixture','idempotency_key':'policy'}, fixture.space)
            fixture.refresh_native(); token = fixture.token('cited-research')
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=fixture.app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+token.access_token}) as http:
                async with Client(streamable_http_client(ORIGIN+'/mcp',http_client=http),mode=mode) as client:
                    calls = []
                    async def call(name, arguments):
                        calls.append(name)
                        result = await client.call_tool(name, arguments)
                        return C0.decode(name,result.model_dump(mode='json',by_alias=True,exclude_none=True))
                    names = {t.name:t for t in (await client.list_tools()).tools}
                    assert all(n in names for n in ('compilation_plan_validate','compilation_apply','compilation_verify'))
                    assert names['compilation_plan_validate'].annotations.read_only_hint
                    assert not names['compilation_apply'].annotations.open_world_hint
                    assert names['compilation_apply'].annotations.idempotent_hint
                    statuses = []
                    for index, record in enumerate(bind_response(corpus)['records']):
                        selections = []
                        for logical in dict.fromkeys(e['document_id'] for e in record['evidence']):
                            evidence = [e for e in record['evidence'] if e['document_id'] == logical]
                            selections.append({'logical_document_id':logical,'revision_id':evidence[0]['generation'],
                                'chunk_ids':list(dict.fromkeys(e['chunk_id'] for e in evidence))})
                        bindings = await call('compilation_source_bindings_get',{'space_id':fixture.space,'data':{'selections':selections}})
                        task = await call('compilation_propose',{'space_id':fixture.space,'data':{'data':{
                            'policy_revision':1,'origin':'manual','reason':'missing_concept','topic_key':'fixture/'+record['key'],
                            'source_bindings':bindings['source_bindings']},'idempotency_key':'proposal-'+record['key']}})
                        run = await call('compilation_run_claim',{'space_id':fixture.space,'data':{'data':{
                            'kind':'manual','cycle_key':'frozen-sources','lease_owner':'external-fixture','policy_revision':1},
                            'idempotency_key':'claim-'+str(index)}})
                        task = await call('compilation_tasks_get',{'space_id':fixture.space,'task_id':task['task']['id']})
                        citations = [(await call('citations_get',{'space_id':fixture.space,'chunk_id':e['chunk_id']}),e['quote']) for e in record['evidence']]
                        plan = navigation_plan(fixture.space,task,record['title'],record['synthesis'],citations,
                            classification='uncertain' if record['classification'] == 'uncertain' else 'supported_synthesis',
                            reviewed_source_ids=[s['logical_document_id'] for s in task['source_bindings']])
                        plan['operations'][0]['arguments']['slug']=task['managed_slug']
                        if index == 2:
                            # Deterministic source-only graph output, including contradictory values.
                            evidence = plan['target_bindings'][0]['evidence']
                            ref = lambda i: {'$result':i,'path':'id'}
                            graph = [
                                ('entity.create',{'kind':'concept','label':'Orion listener observation','aliases':['Orion socket observation']}),
                                ('entity.create',{'kind':'concept','label':'Orion contrary observation'}),
                                ('relation.create',{'source_id':ref(2),'target_id':ref(3),'kind':'contradicts'}),
                            ]
                            for port in (7443,8443):
                                support = next(e for e in evidence if str(port) in e['quote'])
                                graph.append(('claim.create',{'entity_id':ref(2),'predicate':'listener-port','value':{'port':port},
                                    'evidence_chunk_ids':[support['chunk_id']],'valid_from':'2026-01-01T00:00:00+00:00'}))
                            for operation_index,(operation,arguments) in enumerate(graph,2):
                                plan['operations'].append({'operation':operation,'arguments':arguments})
                                chosen = [next(e for e in evidence if str(arguments['value']['port']) in e['quote'])] if operation == 'claim.create' else evidence
                                plan['target_bindings'].append({'operation_index':operation_index,'kind':operation.split('.')[0],
                                    'canonical_key':'fixture/disagreement/'+str(operation_index),'id':None,'revision':0,
                                    'content_id':None,'content_hash':None,'record_hash':None,'managed':False,'evidence':chosen})
                            plan['operations'].append({'operation':'entity.link','arguments':{'entity_id':ref(2),'target_kind':'page','target_id':ref(0)}})
                        request = {'lease':run['lease'],'expected_revision':run['run']['revision'],'plan':plan}
                        preview = await compile_plan(call,fixture.space,request)
                        assert preview['outcome'] == 'needs_review'
                        if index == 0:
                            # Tool-only workflow: genuine content reads plus server hashes, no local digest helper.
                            saved=await call('compilation_apply',{'space_id':fixture.space,'data':{'data':{
                                **request,'plan_hash':preview['plan_hash'],'approval':{'plan_hash':preview['plan_hash'],
                                'reference':'synthetic:exact-plan-review'}},'idempotency_key':'apply-'+record['key']}})
                            page=await call('wiki_pages_get',{'space_id':fixture.space,'page_id':saved['records'][0]['id']})
                            annotation=await call('knowledge_annotations_get',{'space_id':fixture.space,'kind':'wiki_revision',
                                'target_id':page['content']['id'],'content_revision':page['revision'],'namespace':'verification'})
                            packet=await call('compilation_target_bindings_get',{'space_id':fixture.space,'data':{'targets':[
                                {'kind':b['kind'],'id':b['id']} for b in saved['records']]}})
                            observed=[{k:v for k,v in b.items() if k!='managed'} for b in packet['target_bindings']]
                            assert (page['id'],page['revision'],page['content']['content_hash'])==tuple(observed[0][k] for k in ('id','revision','content_hash'))
                            assert (annotation['id'],annotation['revision'])==tuple(observed[1][k] for k in ('id','revision'))
                            for evidence in record['evidence']:
                                assert (await call('citations_get',{'space_id':fixture.space,'chunk_id':evidence['chunk_id']}))['body']
                            bindings=await call('compilation_source_bindings_get',{'space_id':fixture.space,'data':{'selections':selections}})
                            actual=await call('compilation_verify',{'space_id':fixture.space,'data':{'data':{
                                'lease':run['lease'],'expected_revision':saved['run']['revision'],'task_id':task['id'],
                                'expected_task_revision':saved['task']['revision'],'policy_revision':1,'plan_hash':preview['plan_hash'],
                                'observations':observed,'source_bindings':bindings['source_bindings']},'idempotency_key':'verify-tool-only'}})
                        elif index == 1:
                            # Simulate a lost response after the actual server commit; recover from SQL outcome.
                            saved = await call('compilation_apply',{'space_id':fixture.space,'data':{'data':{
                                **request,'plan_hash':preview['plan_hash'], 'approval':{
                                    'plan_hash':preview['plan_hash'],'reference':'synthetic:exact-plan-review'}},'idempotency_key':'apply-'+record['key']}})
                            actual = await verify_pending(call,fixture.space,task['id'],run['lease'],saved['run']['revision'],idempotency_key='verify-'+record['key'])
                        else:
                            actual = await compile_plan(call,fixture.space,request,apply=True,
                                approval={'plan_hash':preview['plan_hash'],'reference':'synthetic:exact-plan-review'},idempotency_key='apply-'+record['key'])
                        assert actual['outcome'] == 'succeeded'
                        statuses.append(actual)
                    status = await call('compilation_status_get',{'space_id':fixture.space})
                    assert status['tasks']['succeeded'] == 3 and not status['complete_corpus_coverage']
                    assert status['budgets'][0]['data']['requests'] == 0
                    assert calls.count('compilation_apply') == 3 and calls.count('compilation_verify') == 3
                    assert calls.count('claims_get') >= 2 and calls.count('entity_relations_list') >= 1
                    assert calls.count('wiki_pages_get') >= 3 and calls.count('knowledge_annotations_get') >= 3
                    # Read-only unchanged reconciliation performs no second publication/verification write.
                    writes = calls.count('compilation_apply')+calls.count('compilation_verify')
                    done = statuses[-1]
                    await verify_pending(call,fixture.space,done['task']['id'],run['lease'],done['run']['revision'],idempotency_key='unchanged-read')
                    assert calls.count('compilation_apply')+calls.count('compilation_verify') == writes
                    invalid = await client.call_tool('compilation_plan_validate',{'space_id':fixture.space,
                        'data':{'data':{'private_query':'PRIVATE-MUST-NOT-ECHO'}}})
                    assert invalid.is_error and 'PRIVATE-MUST-NOT-ECHO' not in str(invalid.content)
            with fixture.db.engine.connect() as c:
                assert c.execute(text('SELECT count(*) FROM c0_wiki_pages WHERE space_id=:space'),{'space':fixture.space}).scalar_one() == 3
                assert c.execute(text("SELECT count(*) FROM c0_annotations WHERE space_id=:space AND namespace='verification'"),{'space':fixture.space}).scalar_one() == 3
            assert await control.corpus() == await fixture.corpus() == corpus
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_installed_maintenance_skill_uses_actual_discovery_and_budgeted_external_step(tmp_path,mode):
    from czero_core.compilation_client import maintenance_step
    directory=tmp_path/'installed-maintenance';directory.mkdir()
    with zipfile.ZipFile(BytesIO(zip_bytes(plugin_payload(ORIGIN+'/mcp','asdk_app_fixture','maintenance-fixture')))) as archive:
        archive.extractall(directory)
    instructions,package=load_plugin(directory)
    assert 'compilation_assessment_complete' in instructions and 'reviewed_ranges' in instructions
    async def check():
        originals=json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'databases',originals) as (_,fixture,corpus):
            await fixture.request('PUT','/api/v1/compilation/policy',{'data':{**defaults(),'enabled':True},
                'expected_revision':0,'authorization_ref':'synthetic:operator','idempotency_key':'policy'},fixture.space)
            fixture.refresh_native();token=fixture.token('cited-research')
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=fixture.app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+token.access_token}) as http:
                async with Client(streamable_http_client(ORIGIN+'/mcp',http_client=http),mode=mode) as client:
                    names={t.name:t for t in (await client.list_tools()).tools}
                    for name in ('compilation_discover','compilation_assessment_complete','compilation_semantic_select','compilation_semantic_review'):
                        assert names[name].annotations.idempotent_hint and not names[name].annotations.open_world_hint
                    calls=[]
                    async def call(name,arguments):
                        calls.append(name)
                        if name=='knowledge_search': assert arguments['options']['space_id']==fixture.space
                        result=await client.call_tool(name,arguments)
                        return C0.decode(name,result.model_dump(mode='json',by_alias=True,exclude_none=True))
                    async def analyze(task,read):
                        binding=task['source_bindings'][0]
                        original=await read('source_documents_get',{'logical_document_id':binding['logical_document_id'],
                            'revision_id':binding['revision_id']})
                        assert original['body'] and original['text_hash']==binding['text_hash']
                        from uuid import uuid4
                        found=await read('knowledge_search',{'options':{'space_id':str(uuid4()),
                            'query':original['title'],'kind':'wiki','mode':'text','rerank':'off'}})
                        assert found['hits']==[]
                        return {'proposals':[],'status':'reviewed','findings':[],
                            'reviewed_source_ids':[binding['logical_document_id']],
                            'observed_tokens':99,'external_reference_hash':'b'*64}
                    result=await maintenance_step(call,fixture.space,{'kind':'bootstrap','cycle_key':'installed-maintenance',
                        'lease_owner':'external-fixture','policy_revision':1},analyze,reserved_tokens=200,idempotency_key='external-step')
                    assert result['outcome']=='assessment_verified'
                    status=await call('compilation_status_get',{'space_id':fixture.space})
                    assert status['sources']['compiled']==1 and not status['complete_corpus_coverage']
                    assert status['budgets'][0]['data']['requests']==1 and status['budgets'][0]['data']['observed_tokens']==99
                    assert 'compilation_apply' not in calls and 'source_documents_get' in calls
    asyncio.run(check())
