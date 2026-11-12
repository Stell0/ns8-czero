# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Installed feedback protocols over genuine scoped MCP and disposable PostgreSQL."""
import asyncio
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4
import zipfile

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
from agentic_retrieval.fixture import paired_fixture
from evaluation.fixture import ORIGIN
from evaluation.skill_input import load_plugin
from c0_ingest.client import C0
from czero_app.agent_packages import plugin_payload,skill_payload,zip_bytes
from czero_core.compilation_client import FEEDBACK_TOOLS,feedback_after_answer
from czero_core.compilation_schema import defaults,digest
from czero_core.worker import Worker

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')
TABLES=('c0_compilation_policies','c0_compilation_tasks','c0_compilation_sources',
        'c0_compilation_dependencies','c0_compilation_runs','c0_compilation_events')


def observation(corpus,index='Orion listener configuration',reason='missing_concept'):
    source=next(d for d in corpus if d['title']==index) if isinstance(index,str) else corpus[index]
    return {'reason':reason,'topic_key':'concept/'+digest(source['title'])[:24],'source_label':source['title'],
        'selections':[{'logical_document_id':source['id'],'revision_id':source['generation'],
            'chunk_ids':[source['chunks'][0]['chunk_id']]}]}


def counts(fixture):
    with fixture.db.engine.connect() as c:
        return {table:c.execute(text('SELECT count(*) FROM '+table+' WHERE space_id=:space'),
                    {'space':fixture.space}).scalar_one() for table in (*TABLES,'c0_wiki_pages','c0_knowledge_events')}


async def enable(fixture,mode='queue_only',expected_revision=0):
    result=await fixture.request('PUT','/api/v1/compilation/policy',{'data':{**defaults(),
        'enabled':True,'retrieval_feedback':True,'publication_mode':mode,'retrieval_model_requests':0},
        'expected_revision':expected_revision,'authorization_ref':'synthetic:operator',
        'idempotency_key':'policy-'+str(expected_revision)},fixture.space)
    return result['policy']['revision']


def install(tmp_path,kind):
    directory=tmp_path/'installed';directory.mkdir()
    payload=(plugin_payload(ORIGIN+'/mcp','asdk_app_fixture','feedback-fixture') if kind=='plugin'
        else skill_payload(ORIGIN+'/mcp'))
    with zipfile.ZipFile(BytesIO(zip_bytes(payload))) as archive:archive.extractall(directory)
    if kind=='plugin':
        instructions,package=load_plugin(directory)
        assert package['version']=='1.11.0'
    else:
        instructions=(directory/'SKILL.md').read_text()+(directory/'references/compiler.md').read_text()
    assert 'feedback_after_answer' in instructions and 'after answer delivery' in instructions
    assert 'explicitly read-only' in instructions and 'five-second' in instructions
    return instructions


async def connected(fixture,mode,callback,case='cited-research'):
    fixture.refresh_native();token=fixture.token(case)
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=fixture.app),base_url=ORIGIN,
            headers={'Authorization':'Bearer '+token.access_token}) as http:
        async with Client(streamable_http_client(ORIGIN+'/mcp',http_client=http),mode=mode) as client:
            capability=json.loads((await client.read_resource('c0://capabilities')).contents[0].text)
            names={operation['name'] for operation in capability['operations']}
            calls=[]
            async def call(name,args):
                calls.append((name,args))
                result=await client.call_tool(name,args)
                return C0.decode(name,result.model_dump(mode='json',by_alias=True,exclude_none=True))
            await callback(call,names,capability,calls)


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('archive',['plugin','skill'])
def test_installed_after_answer_feedback_preserves_sources_and_reuses_actual_sql_tasks(tmp_path,mode,archive,record_property):
    install(tmp_path,archive)
    async def check():
        originals=json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'dbs',originals) as (control,fixture,corpus):
            await enable(fixture)
            provider_calls=[]
            class ForbiddenScorer:
                def score(self,*args,**kwargs):
                    provider_calls.append(True)
                    raise AssertionError('Feedback must not invoke a provider')
            fixture.app.state.search.scorer=ForbiddenScorer()
            fixture.app.state.search.scorer_mode='filter'
            async def episode(call,names,capability,calls):
                assert FEEDBACK_TOOLS<=names
                research=next(f for f in capability['guidance']['workflows'] if f['id']=='research')
                assert 'compilation_propose' in str(research['steps'])
                before=counts(fixture)
                # Existing search itself never queues, including with learning enabled.
                result=await call('knowledge_search',{'options':{'space_id':fixture.space,
                    'query':'7443','mode':'text','rerank':'off'}})
                assert result['hits'] and counts(fixture)==before
                calls.clear()
                delivered=['PRIVATE_EPISODE_ANSWER_NOT_A_SOURCE']
                for _ in range(95):
                    result=await feedback_after_answer(call,fixture.space,None,answer_delivered=True,
                        operation_names=names,idempotency_key='no-change')
                    assert result['outcome']=='no_change'
                assert calls==[]
                selected=observation(corpus)
                started=time.perf_counter()
                saved=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='opaque-retrieval-episode')
                elapsed=time.perf_counter()-started
                assert delivered and saved['outcome']=='proposed' and saved['compiled'] is False
                assert len(calls)==7 and sum(n=='compilation_propose' for n,_ in calls)==1
                assert calls[-1][0]=='compilation_tasks_get'
                state=counts(fixture)
                for _ in range(4):
                    reused=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                        operation_names=names,idempotency_key=uuid4().hex)
                    assert reused['outcome']=='existing' and reused['task_id']==saved['task_id']
                    assert counts(fixture)==state
                assert state['c0_compilation_tasks']==1 and state['c0_compilation_runs']==0
                assert state['c0_wiki_pages']==0 and state['c0_knowledge_events']==before['c0_knowledge_events']
                with fixture.db.engine.connect() as c:
                    task=c.execute(text('SELECT * FROM c0_compilation_tasks WHERE id=:id'),{'id':saved['task_id']}).mappings().one()
                    assert task['origin']=='retrieval' and task['state']=='queued' and task['source_label']==selected['source_label']
                    serialized=''.join(str(c.execute(text('SELECT to_jsonb(t)::text FROM '+table+' t WHERE space_id=:space'),
                        {'space':fixture.space}).scalars().all()) for table in TABLES)
                    assert 'PRIVATE_EPISODE_' not in serialized
                    assert 'benchmark_label' not in serialized and 'model_response' not in serialized
                record_property('feedback_seconds',elapsed)
                record_property('feedback_api_calls',7)
                # Automatic policy may safely defer to the same scheduled compiler.
                await enable(fixture,'automatic_supported',1)
                automatic=await feedback_after_answer(call,fixture.space,observation(corpus,'Orion access procedure'),answer_delivered=True,
                    operation_names=names,idempotency_key='automatic-still-queued')
                assert automatic['outcome']=='proposed' and automatic['state']=='queued' and not automatic['compiled']
                # Real contrary source observation becomes reviewable, never verified.
                contrary=await feedback_after_answer(call,fixture.space,{**observation(corpus,'Orion conflicting port note','contradiction'),
                    'selections':observation(corpus,'Orion conflicting port note')['selections']+observation(corpus)['selections']},answer_delivered=True,
                    operation_names=names,idempotency_key='contradictory-evidence')
                assert contrary['state']=='needs_review'
                assert counts(fixture)['c0_wiki_pages']==0
                assert all(n in FEEDBACK_TOOLS for n,_ in calls)
                assert provider_calls==[]
            await connected(fixture,mode,episode)
            assert await control.corpus()==await fixture.corpus()==corpus
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_readers_read_only_scopes_and_disabled_feedback_do_not_write(tmp_path,mode):
    async def check():
        originals=json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'dbs',originals) as (_,fixture,corpus):
            selected=observation(corpus)
            async def denied(call,names,capability,calls):
                before=counts(fixture)
                research=next(f for f in capability['guidance']['workflows'] if f['id']=='research')
                assert 'compilation_propose' not in str(research['steps']) and 'compilation_propose' not in names
                result=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='denied')
                assert result['outcome']=='skipped' and calls==[] and counts(fixture)==before
            await connected(fixture,mode,denied,'reader-denial')
            await connected(fixture,mode,denied,'scope-consent')
            async def disabled(call,names,capability,calls):
                before=counts(fixture)
                result=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='disabled')
                assert result['reason']=='feedback_disabled' and counts(fixture)==before
                await enable(fixture)
                for options in ({'read_only':True},{'answer_delivered':False}):
                    calls.clear();before=counts(fixture)
                    result=await feedback_after_answer(call,fixture.space,selected,
                        **{'answer_delivered':True,'operation_names':names,'idempotency_key':'explicit-no-writes',**options})
                    assert result['outcome']=='skipped' and calls==[] and counts(fixture)==before
            await connected(fixture,mode,disabled)
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_concurrent_equivalent_gaps_and_lost_reply_reconcile_without_second_write(tmp_path,mode):
    async def check():
        originals=json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'dbs',originals) as (_,fixture,corpus):
            await enable(fixture)
            async def episode(call,names,capability,calls):
                selected=observation(corpus)
                results=await asyncio.gather(*(feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='racing-'+str(i)) for i in range(2)))
                assert {r['outcome'] for r in results}<={'proposed','existing'}
                assert len({r['task_id'] for r in results})==1 and counts(fixture)['c0_compilation_tasks']==1
                calls.clear();selected=observation(corpus,'Orion access procedure')
                async def lose(name,args):
                    value=await call(name,args)
                    if name=='compilation_propose':raise RuntimeError('PRIVATE_EPISODE_TRANSPORT_DETAIL')
                    return value
                unknown=await feedback_after_answer(lose,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='stable-lost-reply')
                assert unknown['outcome']=='uncertain' and 'PRIVATE_EPISODE' not in str(unknown)
                assert counts(fixture)['c0_compilation_tasks']==2
                recovered=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='stable-lost-reply')
                assert recovered['outcome']=='existing' and recovered['compiled'] is False
                assert sum(n=='compilation_propose' for n,_ in calls)==1
                # The injected-instruction source is only evidence, never tool authority.
                held=await feedback_after_answer(call,fixture.space,observation(corpus,'Untrusted example text'),answer_delivered=True,
                    operation_names=names,idempotency_key='hostile-original')
                assert held['outcome']=='proposed' and all(n in FEEDBACK_TOOLS for n,_ in calls)
                assert counts(fixture)['c0_wiki_pages']==0 and counts(fixture)['c0_compilation_runs']==0
            await connected(fixture,mode,episode)
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_current_wiki_authored_edits_expired_originals_and_cross_space_defer(tmp_path,mode):
    async def check():
        originals=json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'dbs',originals) as (_,fixture,corpus):
            await enable(fixture)
            source=next(d for d in corpus if d['title']=='Orion listener configuration')
            page=await fixture.request('POST','/api/v1/wiki/pages',{'slug':'authored-listener',
                'title':source['title'],'body':'Authored listener procedure. '+source['title'],
                'idempotency_key':'authored'},fixture.space)
            selected={**observation(corpus),'reason':'incomplete_page','topic_key':'page:'+page['id']}
            async def episode(call,names,capability,calls):
                before=counts(fixture)
                unresolved=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='resolve-current-wiki')
                assert unresolved['reason']=='wiki_resolution_required' and counts(fixture)==before
                selected['target']={'kind':'page','id':page['id'],'revision':page['revision'],
                    'content_id':page['content']['id'],'content_hash':page['content']['content_hash']}
                saved=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='explicit-existing-target')
                assert saved['outcome']=='proposed'
                current=await call('wiki_pages_get',{'space_id':fixture.space,'page_id':page['id']})
                assert current==page
                changed=await fixture.request('PUT','/api/v1/wiki/pages/'+page['id'],{
                    'title':page['title'],'body':page['content']['body']+' Preserved authored addition.',
                    'expected_revision':1,'idempotency_key':'authored-edit'},fixture.space)
                before=counts(fixture)
                drift=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='stale-target')
                assert drift['reason']=='target_changed' and counts(fixture)==before
                assert (await call('wiki_pages_get',{'space_id':fixture.space,'page_id':page['id']}))==changed
                foreign=await fixture.request('POST','/api/v1/spaces',{'name':'Other laboratory','idempotency_key':'other'})
                version=await fixture.request('POST','/api/v1/sources/ingest-text',{'title':'Foreign original',
                    'body':'An unrelated source.','idempotency_key':'foreign'},foreign['id'])
                Worker(fixture.db,fixture.app.state.jobs.registry).tick()
                document=await fixture.request('GET','/api/v1/source-versions/'+version['id']+'/document',space=foreign['id'])
                chunks=await fixture.request('GET','/api/v1/documents/'+document['id']+'/chunks',space=foreign['id'])
                outside={**selected,'selections':[{'logical_document_id':version['source_id'],'revision_id':version['id'],
                    'chunk_ids':[chunks['chunks'][0]['id']]}]}
                calls.clear();before=counts(fixture)
                denied=await feedback_after_answer(call,fixture.space,outside,answer_delivered=True,
                    operation_names=names,idempotency_key='wrong-space-original')
                assert denied['outcome']=='deferred' and counts(fixture)==before
                assert all(args.get('space_id')==fixture.space for _,args in calls)
                # Actual replacement expires the selected identity; no fallback read is attempted.
                await fixture.request('POST','/api/v1/sources/ingest-text',{'source_id':source['id'],
                    'title':source['title'],'body':'The listener now uses TCP port 9443.',
                    'metadata':{'canonical_url':source['url']},'expected_revision':1,
                    'idempotency_key':'changed-original'},fixture.space)
                Worker(fixture.db,fixture.app.state.jobs.registry).tick()
                calls.clear();before=counts(fixture)
                expired=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='expired-exact-original')
                assert expired['outcome']=='deferred' and counts(fixture)==before
                assert [n for n,_ in calls]==['spaces_get','compilation_policy_get','compilation_source_bindings_get']
                assert (await call('wiki_pages_get',{'space_id':fixture.space,'page_id':page['id']}))==changed
            await connected(fixture,mode,episode)
    asyncio.run(check())


def test_queue_cap_restricted_policy_and_midflight_disable_use_actual_core_guards(tmp_path):
    async def check():
        originals=json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'dbs',originals) as (_,fixture,corpus):
            await fixture.request('PUT','/api/v1/compilation/policy',{'data':{**defaults(),
                'enabled':True,'retrieval_feedback':True,'max_outstanding_tasks':1},'expected_revision':0,
                'authorization_ref':'synthetic:operator','idempotency_key':'cap-policy'},fixture.space)
            async def episode(call,names,capability,calls):
                first=await feedback_after_answer(call,fixture.space,observation(corpus),answer_delivered=True,
                    operation_names=names,idempotency_key='first-gap')
                assert first['outcome']=='proposed'
                capped=await feedback_after_answer(call,fixture.space,observation(corpus,'Orion access procedure'),answer_delivered=True,
                    operation_names=names,idempotency_key='queue-at-cap')
                assert capped['reason']=='queue_capacity' and counts(fixture)['c0_compilation_tasks']==1
                await fixture.request('PUT','/api/v1/compilation/policy',{'data':{**defaults(),
                    'enabled':True,'retrieval_feedback':True,'allowed_target_kinds':['annotation']},
                    'expected_revision':1,'authorization_ref':'synthetic:operator','idempotency_key':'restricted'},fixture.space)
                calls.clear();before=counts(fixture)
                restricted=await feedback_after_answer(call,fixture.space,observation(corpus,'Orion access procedure'),answer_delivered=True,
                    operation_names=names,idempotency_key='restricted-gap')
                assert restricted['reason']=='feedback_disabled' and counts(fixture)==before
                assert [n for n,_ in calls]==['spaces_get','compilation_policy_get']
                await enable(fixture,expected_revision=2)
                async def disable(name,args):
                    if name=='compilation_propose':
                        await fixture.request('PUT','/api/v1/compilation/policy',{'data':defaults(),
                            'expected_revision':3,'authorization_ref':'synthetic:operator','idempotency_key':'disable'},fixture.space)
                    return await call(name,args)
                raced=await feedback_after_answer(disable,fixture.space,observation(corpus,'Orion access procedure'),answer_delivered=True,
                    operation_names=names,idempotency_key='disabled-during-episode')
                assert raced['outcome']=='uncertain' and counts(fixture)['c0_compilation_tasks']==1
                assert counts(fixture)['c0_wiki_pages']==0
            await connected(fixture,'auto',episode)
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_daily_common_compiler_consumes_feedback_and_own_publication_does_not_requeue(tmp_path,mode):
    from datetime import datetime,timezone
    from czero_core.compilation_client import navigation_plan,compile_plan
    async def check():
        originals=json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'dbs',originals) as (control,fixture,corpus):
            await enable(fixture,'automatic_supported')
            async def episode(call,names,capability,calls):
                selected=observation(corpus)
                queued=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='after-answer-gap')
                assert queued['outcome']=='proposed' and not queued['compiled']
                run=await call('compilation_run_claim',{'space_id':fixture.space,'data':{'data':{
                    'kind':'daily','cycle_key':datetime.now(timezone.utc).date().isoformat(),
                    'lease_owner':'existing-daily-host','policy_revision':1},'idempotency_key':'daily-existing-engine'}})
                task=await call('compilation_tasks_get',{'space_id':fixture.space,'task_id':queued['task_id']})
                assert task['id'] in run['run']['data']['task_ids'] and task['origin']=='retrieval'
                chunk_id=selected['selections'][0]['chunk_ids'][0]
                citation=await call('citations_get',{'space_id':fixture.space,'chunk_id':chunk_id})
                plan=navigation_plan(fixture.space,task,selected['source_label'],
                    'Read the original configuration evidence.',[(citation,citation['body'])],
                    reviewed_source_ids=[s['logical_document_id'] for s in task['source_bindings']])
                request={'lease':run['lease'],'expected_revision':run['run']['revision'],'plan':plan}
                preview=await compile_plan(call,fixture.space,request)
                result=await compile_plan(call,fixture.space,request,apply=True,
                    approval={'plan_hash':preview['plan_hash'],'reference':'synthetic:exact-maintenance-plan'},
                    idempotency_key='daily-source-backed-publication')
                assert result['outcome']=='succeeded' and result['task']['state']=='succeeded'
                page_record=next(r for r in result['records'] if r['kind']=='page')
                page=await call('wiki_pages_get',{'space_id':fixture.space,'page_id':page_record['id']})
                assert page['revision']==1
                # Compare the complete original after removing Markdown's quote prefix.
                quoted='\n'.join(line[2:] for line in page['content']['body'].splitlines() if line.startswith('> '))
                assert quoted==citation['body']
                annotation=await call('knowledge_annotations_get',{'space_id':fixture.space,'kind':'wiki_revision',
                    'target_id':page['content']['id'],'content_revision':1,'namespace':'verification'})
                assert annotation['status']=='unverified'
                before=counts(fixture);calls.clear()
                unchanged=await feedback_after_answer(call,fixture.space,selected,answer_delivered=True,
                    operation_names=names,idempotency_key='same-gap-after-compilation')
                assert unchanged['outcome']=='existing' and unchanged['state']=='succeeded'
                assert counts(fixture)==before and all(n!='compilation_propose' for n,_ in calls)
                assert any(n=='wiki_pages_get' for n,_ in calls)
                status=await call('compilation_status_get',{'space_id':fixture.space})
                assert status['dependencies']['observed']>0 and status['dependencies']['stale']==0
                assert status['budgets'][0]['data']['requests']==0
            await connected(fixture,mode,episode)
            assert await control.corpus()==await fixture.corpus()==corpus
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_global_editor_with_selected_space_reader_role_makes_no_mutation_call(tmp_path,mode):
    import secrets
    from czero_core.identity import Role
    from czero_core.oauth_grants import pkce_challenge
    from evaluation.fixture import CALLBACK
    async def check():
        originals=json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'dbs',originals) as (_,fixture,corpus):
            await enable(fixture)
            # Application Editor, retained protected-space Reader grant, real Read+Write consent.
            fixture.access.set_role(fixture.owner,fixture.reader_id,Role.EDITOR)
            fixture.refresh_native()
            identity=fixture.app.state.auth.oidc.verify_access_token(fixture.native['reader'])
            cookie=fixture.app.state.auth.sessions.create(identity)
            session=fixture.app.state.auth.sessions.get(cookie)
            verifier=secrets.token_urlsafe(32);grants=fixture.app.state.delegated_grants
            code=grants.issue_code(session,fixture.client['client_id'],callback=CALLBACK,
                scopes={'c0:read','c0:write'},challenge=pkce_challenge(verifier),resource=ORIGIN+'/mcp')
            pair=grants.exchange_code(code,fixture.client['client_id'],callback=CALLBACK,verifier=verifier,resource=ORIGIN+'/mcp')
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=fixture.app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(ORIGIN+'/mcp',http_client=http),mode=mode) as client:
                    capability=json.loads((await client.read_resource('c0://capabilities')).contents[0].text)
                    names={operation['name'] for operation in capability['operations']}
                    assert FEEDBACK_TOOLS<=names
                    calls=[]
                    async def call(name,args):
                        calls.append(name)
                        assert name=='spaces_get' and args['space_id']==fixture.space
                        result=C0.decode(name,(await client.call_tool(name,args)).model_dump(mode='json',by_alias=True,exclude_none=True))
                        assert result['role']=='reader'
                        return result
                    before=counts(fixture)
                    result=await feedback_after_answer(call,fixture.space,observation(corpus),answer_delivered=True,
                        operation_names=names,idempotency_key='effective-reader-skip')
                    assert result['reason']=='space_not_writable' and calls==['spaces_get']
                    assert counts(fixture)==before
    asyncio.run(check())
