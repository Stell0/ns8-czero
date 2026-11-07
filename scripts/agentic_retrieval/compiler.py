# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Reviewed benchmark proposals through the production compiler, disposable only."""
import json
from pathlib import Path

from c0_ingest.state import atomic
from czero_core.compilation_client import navigation_plan, compile_plan, verify_pending
from czero_core.compilation_schema import defaults
from evaluation.fixture import database_parameters
from .layer import validate_plan
from .protocol import digest


def review_plan(review, corpus, plan):
    if (set(review) != {'corpus_hash','plan_hash','provenance','records'}
            or review['corpus_hash'] != digest(corpus) or review['plan_hash'] != digest(plan)
            or not isinstance(review['provenance'],str) or not review['provenance'].strip()):
        raise ValueError('compiler_source_review_missing_or_changed')
    records = review['records']
    if (not isinstance(records,list) or len(records) != len(plan['records'])
            or {r.get('key') for r in records} != {r['key'] for r in plan['records']}
            or any(set(r) != {'key','source_supported','uncertainty_preserved'}
                or r['source_supported'] is not True or r['uncertainty_preserved'] is not True for r in records)):
        raise ValueError('compiler_source_review_incomplete')


async def publish(fixture, corpus, plan, state_path, review, *, apply=False, forbidden=()):
    """No alternate publication engine: use Core validation, atomic apply and readback.

    The fixture owns this temporary database. Never accept a production connection.
    Builder reasoning is separately measured, reviewed offline work, with no forged
    server model-usage receipt or claim of unattended construction.
    """
    import re
    if not re.fullmatch(r'czero_eval_[0-9a-f]{32}',database_parameters(fixture.db.engine.url).database):
        raise ValueError('disposable_compiler_fixture_required')
    hashed = validate_plan(plan,corpus,forbidden)
    review_plan(review,corpus,plan)
    if await fixture.corpus() != corpus:
        raise ValueError('compiler_source_drift')
    path = Path(state_path)
    state = json.loads(path.read_text()) if path.exists() else {
        'space':fixture.space,'plan_hash':hashed,'records':{},'pending':None}
    if (state['space'],state['plan_hash']) != (fixture.space,hashed):
        raise ValueError('compiler_publication_binding_changed')
    if not apply:
        return {'applied':False,'plan_hash':hashed,'records':len(plan['records']),
            'source_reviewed':True,'writes':0}
    if state['pending'] and state['pending']['operation'] != 'compile_plan':
        raise RuntimeError('uncertain_compiler_write_requires_reconciliation')
    async with fixture.mcp('cited-research') as client:
        from c0_ingest.client import C0
        async def call(name, args):
            result = await client.call_tool(name,{**args,'space_id':fixture.space})
            return C0.decode(name,result.model_dump(mode='json',by_alias=True,exclude_none=True))
        async def write(name, data, key):
            state['pending'] = {'operation':name,'key':key,'fingerprint':digest(data)}
            atomic(path,state)
            result = await call(name,{'data':{'data':data,'idempotency_key':key}})
            state['pending'] = None
            atomic(path,state)
            return result
        if state['pending']:
            pending = state['pending']
            task = await call('compilation_tasks_get',{'task_id':pending['task_id']})
            if (task['state'] not in ('applied_pending_verify','succeeded')
                    or task.get('publication',{}).get('plan_hash') != pending['plan_hash']):
                raise RuntimeError('uncertain_compiler_write_requires_reconciliation')
            status = await call('compilation_status_get',{'run_id':pending['lease']['run_id']})
            run = next(r for r in status['runs'] if r['id'] == pending['lease']['run_id'])
            actual = await verify_pending(call,fixture.space,task['id'],pending['lease'],
                run['revision'],idempotency_key=pending['verify_key'])
            if actual['outcome'] != 'succeeded':raise RuntimeError('compiler_publication_not_verified')
            state['records'][pending['record_key']] = {'task_id':task['id'],'plan_hash':pending['plan_hash'],
                'lease':pending['lease'],'run_revision':run['revision'],'verify_key':pending['verify_key']}
            state['pending'] = None
            atomic(path,state)
        policy = await call('compilation_policy_get',{})
        if not policy['data']['enabled']:
            # Admin setup is solely the owned evaluation fixture, never a compiler action.
            await fixture.request('PUT','/api/v1/compilation/policy',{
                'data':{**defaults(),'enabled':True},'expected_revision':policy['revision'],
                'authorization_ref':'disposable:source-reviewed-study','idempotency_key':'study-policy'},fixture.space)
            policy = await call('compilation_policy_get',{})
        outcomes = []
        for record in plan['records']:
            key = record['key']; saved = state['records'].get(key)
            if saved:
                task = await call('compilation_tasks_get',{'task_id':saved['task_id']})
                if task.get('publication',{}).get('plan_hash') != saved['plan_hash']:
                    raise RuntimeError('compiler_publication_changed')
                actual = await verify_pending(call,fixture.space,task['id'],saved['lease'],
                    saved['run_revision'],idempotency_key=saved['verify_key'])
                if actual['outcome'] != 'succeeded':
                    raise RuntimeError('compiler_publication_not_verified')
                outcomes.append({'key':key,'outcome':'unchanged','task_id':task['id']})
                continue
            selections = []
            for identifier in dict.fromkeys(e['document_id'] for e in record['evidence']):
                doc = next(d for d in corpus if d['id'] == identifier)
                current = await call('source_documents_get',{'logical_document_id':identifier,'revision_id':doc['generation']})
                if current['body'] != doc['body'] or current['text_hash'] != doc['content_hash']:
                    raise RuntimeError('compiler_source_drift')
                selections.append({'logical_document_id':identifier,'revision_id':doc['generation'],
                    'chunk_ids':list(dict.fromkeys(e['chunk_id'] for e in record['evidence'] if e['document_id'] == identifier))})
            bindings = await call('compilation_source_bindings_get',{'data':{'selections':selections}})
            identity = digest([hashed,key])
            proposed = await write('compilation_propose',{'policy_revision':policy['revision'],
                'origin':'manual','reason':'missing_concept','topic_key':plan['namespace']+'/'+key,
                'source_bindings':bindings['source_bindings']},identity+'-propose')
            claimed = await write('compilation_run_claim',{'kind':'manual','cycle_key':hashed,
                'lease_owner':'disposable-study','policy_revision':policy['revision'],'task_limit':1},identity+'-claim')
            if claimed['outcome'] != 'claimed':
                raise RuntimeError('compiler_claim_not_acquired')
            task = await call('compilation_tasks_get',{'task_id':proposed['task']['id']})
            citations = [(await call('citations_get',{'chunk_id':e['chunk_id']}),e['quote']) for e in record['evidence']]
            compiled = navigation_plan(fixture.space,task,record['title'],record['synthesis'],citations,
                classification={'extracted':'extracted','inferred':'supported_synthesis','uncertain':'uncertain'}[record['classification']],
                reviewed_source_ids=[s['logical_document_id'] for s in selections])
            request = {'lease':claimed['lease'],'expected_revision':claimed['run']['revision'],'plan':compiled}
            preview = await compile_plan(call,fixture.space,request)
            state['pending'] = {'operation':'compile_plan','task_id':task['id'],'key':identity+'-apply',
                'lease':claimed['lease'],'run_revision':claimed['run']['revision'],'record_key':key,
                'plan_hash':preview['plan_hash'],'verify_key':digest([identity+'-apply','verify'])}
            atomic(path,state)
            actual = await compile_plan(call,fixture.space,request,apply=True,
                approval={'plan_hash':preview['plan_hash'],'reference':'disposable:source-reviewed-study'},
                idempotency_key=identity+'-apply')
            if actual['outcome'] != 'succeeded':
                raise RuntimeError('compiler_publication_not_verified')
            state['records'][key] = {'task_id':task['id'],'plan_hash':preview['plan_hash'],
                'lease':claimed['lease'],'run_revision':actual.get('run',claimed['run'])['revision'],
                'verify_key':digest([identity+'-apply','verify'])}
            state['pending'] = None
            atomic(path,state)
            outcomes.append({'key':key,'outcome':'succeeded','task_id':task['id']})
        status = await call('compilation_status_get',{})
        active = next((r for r in status['runs'] if r['cycle_key'] == hashed and r['state'] == 'running'),None)
        if active:
            await write('compilation_run_checkpoint',{'lease':next(reversed(state['records'].values()))['lease'],
                'expected_revision':active['revision'],'action':'finish'},hashed+'-finish')
            status = await call('compilation_status_get',{})
    if await fixture.corpus() != corpus:
        raise RuntimeError('compiler_source_drift')
    return {'applied':True,'plan_hash':hashed,'records':outcomes,'status':status,
        'construction':'externally built and source-reviewed; no server inference receipt',
        'complete_corpus_coverage':False}
