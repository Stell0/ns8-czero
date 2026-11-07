# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Optional external-agent steps. Never invoked by Core server/worker handlers.

The caller supplies an authenticated tool connection and retains its exact apply
request key before I/O. No model, credentials, local corpus mirror or scheduler.
"""
from .compilation_content import passage, record_binding, navigation_body
from .compilation_plans import managed_slug
from .compilation_schema import digest


def navigation_plan(space_id, task, title, synthesis, citations, *, classification='supported_synthesis',
                    current=None, managed=False, usage_reservation_id=None, reviewed_source_ids=()):
    """Promoted extractive profile: original quotes plus source-backed navigation."""
    if task['target'] and current is None:
        raise ValueError('compilation_current_target_read_required')
    citations = list(citations)
    evidence = [passage(citation, quote) for citation, quote in citations]
    references = [{'kind':'chunk', 'id': identifier} for identifier in dict.fromkeys(e['chunk_id'] for e in evidence)]
    body = navigation_body(synthesis, evidence, classification)
    binding = (record_binding('page', current) if current else {'kind':'page','id':None,'revision':0,
        'content_id':None,'content_hash':None,'record_hash':None})
    slug = current['slug'] if current else task.get('managed_slug') or managed_slug(space_id, task['profile_id'], task['topic_key'])
    arguments = {'slug':slug,'title':title,'body':body}
    if current:
        arguments.update(expected_revision=current['revision'], metadata=current['content']['metadata'])
    known_sources = {s['logical_document_id'] for s in task['source_bindings']}
    if not set(reviewed_source_ids) <= known_sources:
        raise ValueError('unbound_compilation_source_review')
    complete = set(reviewed_source_ids)
    for source in task['source_bindings']:
        if any(citation['chunk_id'] in {c['chunk_id'] for c in source['chunks']} and citation['start_offset'] == 0
                and citation['content_hash'] == source['text_hash'] for citation,_ in citations):
            complete.add(source['logical_document_id'])
    unread = sorted(known_sources-complete)
    deferred = [{'reason':'unread_source_context','source_ids':unread}] if unread else []
    return {'schema_version':1, 'space_id':str(space_id), 'task_id':task['id'],
        'expected_task_revision':task['revision'], 'policy_revision':task['policy_revision'],
        'profile_id':task['profile_id'], 'profile_version':task['profile_version'],
        'source_bindings':task['source_bindings'], 'target_bindings':[dict(binding,
            operation_index=0, canonical_key=task['topic_key'], managed=managed, evidence=evidence)],
        'dedup_decisions':[], 'classification':classification, 'operations':[
            {'operation':'wiki.upsert', 'arguments':arguments},
            {'operation':'annotation.update', 'arguments':{'target':{'kind':'wiki_revision',
                'id':{'$result':0,'path':'content.id'}, 'revision':{'$result':0,'path':'revision'}},
                'namespace':'verification', 'value':{'status':'unverified','source_references':references},
                'expected_revision':0}}], 'deferred':deferred, 'usage_reservation_id':usage_reservation_id}


async def verify_pending(call, space_id, task_id, lease, expected_revision, *, idempotency_key):
    """Fresh original/target reads before the separate fenced verify operation.

    call executes supported MCP tools and must raise on transport OR tool errors.
    Graph locators are server-generated identifiers, never source instructions.
    """
    async def read(name, arguments):
        return await call(name, {**arguments, 'space_id':str(space_id)})
    task = await read('compilation_tasks_get', {'task_id':task_id})
    publication = task.get('publication')
    if task['state'] not in ('applied_pending_verify','succeeded') or not publication:
        raise ValueError('compilation_has_no_saved_publication')
    observations = []
    tools = {'page':'wiki_pages_get', 'entity':'entities_get', 'claim':'claims_get',
        'relation':'entity_relations_list', 'link':'entity_references_list', 'annotation':'knowledge_annotations_get'}
    for saved, locator in zip(publication['records'], publication['locators'], strict=True):
        kind = saved['kind']
        if (kind, saved['id']) != (locator['kind'], locator['id']):
            raise ValueError('compilation_readback_locator_mismatch')
        arguments = dict(locator['arguments'])
        if kind in ('relation','link'):
            arguments['limit'] = 50
        result = await read(tools[kind], arguments)
        if kind in ('relation','link'):
            result = next((r for r in result['relations' if kind == 'relation' else 'references'] if r['id'] == saved['id']), None)
            if result is None:
                raise ValueError('compilation_readback_missing')
        observed = record_binding(kind, result)
        if observed != saved:
            raise ValueError('compilation_readback_mismatch')
        observations.append(observed)
    selections = []
    for source in task['source_bindings']:
        for chunk in source['chunks']:
            citation = await read('citations_get', {'chunk_id':chunk['chunk_id']})
            if any(citation[k] != chunk[k] for k in chunk):
                raise ValueError('compilation_original_mismatch')
        selections.append({'logical_document_id':source['logical_document_id'], 'revision_id':source['revision_id'],
            'chunk_ids':[c['chunk_id'] for c in source['chunks']]})
    original = await read('compilation_source_bindings_get', {'data':{'selections':selections}})
    if original['source_bindings'] != task['source_bindings']:
        raise ValueError('compilation_original_mismatch')
    if task['state'] == 'succeeded':
        return {'outcome':'succeeded', 'task':task, 'records':observations, 'plan_hash':publication['plan_hash']}
    data = {'lease':lease, 'expected_revision':expected_revision, 'task_id':task_id,
        'expected_task_revision':task['revision'], 'policy_revision':task['policy_revision'],
        'plan_hash':publication['plan_hash'], 'observations':observations, 'source_bindings':task['source_bindings']}
    return await read('compilation_verify', {'data':{'data':data, 'idempotency_key':idempotency_key}})


async def compile_plan(call, space_id, data, *, apply=False, approval=None, idempotency_key=None):
    """Bounded dry-run/apply/readback; caller owns durable minimal intent and recovery."""
    result = await call('compilation_plan_validate', {'space_id':str(space_id), 'data':{'data':data}})
    if not apply:
        return result
    if not idempotency_key:
        raise ValueError('stable_compilation_request_key_required')
    request = {**data, 'plan_hash':result['plan_hash']}
    if approval:
        request['approval'] = approval
    saved = await call('compilation_apply', {'space_id':str(space_id),
        'data':{'data':request, 'idempotency_key':idempotency_key}})
    return await verify_pending(call, space_id, saved['task']['id'], data['lease'],
        saved['run']['revision'], idempotency_key=digest([idempotency_key,'verify']))


async def maintenance_step(call, space_id, claim, analyze, *, reserved_tokens, idempotency_key):
    """One external-agent assessment, with durable discovery and model accounting.

    analyze(task, read) is an external callback. It reads current whole originals,
    searches existing concepts and returns closed `proposals`, `status`, `findings`,
    `reviewed_source_ids`, `observed_tokens`, `external_reference_hash`. It must not
    publish. Save the request key before starting; after interruption inspect C0
    status rather than replaying a possibly completed model invocation. The helper
    leaves child plans/review/publication to compile_plan and the policy operator.
    """
    from uuid import uuid4

    async def read(name, arguments):
        # Search uses its established nested selectors; never fall back to Shared.
        if name in ('knowledge_search','knowledge_search_structured'):
            field='options' if name=='knowledge_search' else 'data'
            arguments={**arguments,field:{**arguments.get(field,{}),'space_id':str(space_id)}}
            return await call(name,arguments)
        return await call(name, {**arguments, 'space_id':str(space_id)})
    async def mutation(name, data, step):
        return await read(name, {'data':{'data':data,'idempotency_key':digest([idempotency_key,step])}})
    result=await mutation('compilation_run_claim',claim,'claim')
    if result['outcome']!='claimed':
        return result
    lease=result['lease']
    discovered=await mutation('compilation_discover',{'lease':lease,'expected_revision':result['run']['revision'],'limit':1},'discover')
    tasks=discovered['tasks']
    task=next((t for t in tasks if t['purpose']=='source_assessment'),None)
    if not task:
        return discovered  # Existing publication/recovery work takes precedence.
    if discovered['run']['data']['calls']:
        return {**discovered,'outcome':'reconcile_before_inference'}
    request_id=str(uuid4())
    current=discovered
    async def checkpoint(action, extra, step):
        return await mutation('compilation_run_checkpoint',{'lease':lease,
            'expected_revision':current['run']['revision'],'action':action,**extra},step)
    current=await checkpoint('reserve_model',{'task_id':task['id'],'expected_task_revision':task['revision'],
        'request_id':request_id,'reserved_tokens':reserved_tokens},'reserve')
    if current['outcome']=='deferred_budget':
        return current
    current=await checkpoint('start_model',{'request_id':request_id},'start')
    # Exceptions leave the started call uncertain: never manufacture a failed
    # provider receipt or repeat the invocation merely because the client crashed.
    analysis=await analyze(task,read)
    current=await checkpoint('return_model',{'request_id':request_id,
        'observed_tokens':analysis['observed_tokens'],'external_reference_hash':analysis['external_reference_hash']},'returned')
    proposals=analysis['proposals']
    if type(proposals) is not list or len(proposals)>19:
        raise ValueError('bounded_compilation_children_required')
    children=[]
    for index,proposal in enumerate(proposals):
        saved=await mutation('compilation_propose',proposal,'proposal-'+str(index))
        if 'task' not in saved:
            return {**current,'outcome':'assessment_partial','deferred_proposal':index}
        children.append(saved['task']['id'])
    task=await read('compilation_tasks_get',{'task_id':task['id']})
    return await mutation('compilation_assessment_complete',{'lease':lease,'expected_revision':current['run']['revision'],
        'task_id':task['id'],'expected_task_revision':task['revision'],
        'reviewed_source_ids':analysis['reviewed_source_ids'],'child_task_ids':children,
        'status':analysis['status'],'findings':analysis['findings'],
        **({'reviewed_ranges':analysis['reviewed_ranges']} if 'reviewed_ranges' in analysis else {})},'assessed')


FEEDBACK_TOOLS = frozenset({'spaces_get','compilation_policy_get','compilation_source_bindings_get',
    'compilation_propose','compilation_tasks_list','compilation_tasks_get',
    'knowledge_search','wiki_pages_get'})


async def feedback_after_answer(call, space_id, observation=None, *, answer_delivered=False,
                                read_only=False, operation_names=(), idempotency_key=None,
                                timeout_seconds=5):
    """Optional, bounded external handoff after the host has delivered its answer.

    Pass names from actual-scope c0://capabilities, not scope-upgrade tool discovery.
    The host retains its opaque request key before I/O. No query/answer parameter,
    model callback, publication, logging or automatic retry. Tool errors must raise.
    A host without post-answer continuation skips this step.
    """
    import asyncio
    import math
    from uuid import UUID as UUIDValue
    from .compilation_schema import PROPOSAL, SOURCE_SELECTION, TARGET, checked, key, record

    if observation is None:
        return {'outcome':'no_change','compiled':False}
    if answer_delivered is not True or read_only is not False:
        return {'outcome':'skipped','reason':'read_only_or_answer_not_delivered','compiled':False}
    submitted=False; saved_id=None; calls=0
    try:
        if not FEEDBACK_TOOLS <= set(operation_names):
            return {'outcome':'skipped','reason':'capability_unavailable','compiled':False}
        if type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 0<timeout_seconds<=5:
            raise ValueError('invalid_feedback_budget')
        deadline=asyncio.get_running_loop().time()+timeout_seconds
        schema=record({'reason':{'enum':PROPOSAL['properties']['reason']['enum'][:9]},
            'topic_key':PROPOSAL['properties']['topic_key'],
            'source_label':{'type':'string','minLength':1,'maxLength':160},
            'selections':{'type':'array','minItems':1,'maxItems':3,'items':SOURCE_SELECTION},
            'target':{'anyOf':[TARGET,{'type':'null'}]}},
            ['reason','topic_key','source_label','selections'])
        candidate=checked(schema,observation)
        request_key=key(idempotency_key)
        space_id=str(UUIDValue(str(space_id)))
        if sum(len(s['chunk_ids']) for s in candidate['selections'])>32:
            raise ValueError('feedback_evidence_budget')
        target=candidate.get('target')
        async def invoke(name,arguments):
            nonlocal calls
            if calls>=7: raise ValueError('feedback_call_budget')
            calls+=1
            return await call(name,{**arguments,'space_id':str(space_id)})
        async with asyncio.timeout_at(deadline):
            selected=await invoke('spaces_get',{})
            if selected['id']!=space_id or selected['role'] not in ('editor','admin'):
                return {'outcome':'skipped','reason':'space_not_writable','compiled':False}
            policy=await invoke('compilation_policy_get',{})
            config=policy['data']
            if not config['enabled'] or not config['retrieval_feedback'] or 'page' not in config['allowed_target_kinds']:
                return {'outcome':'skipped','reason':'feedback_disabled','compiled':False}
            packet=await invoke('compilation_source_bindings_get',{'data':{'selections':candidate['selections']}})
            bindings=sorted([{**s,'chunks':sorted(s['chunks'],key=lambda c:c['chunk_id'])}
                for s in packet['source_bindings']],key=lambda s:s['logical_document_id'])
            def matches(task):
                return (task.get('purpose','knowledge')=='knowledge' and task['source_bindings']==bindings
                    and task['profile_id']==config['profile_id'] and task['profile_version']==config['profile_version']
                    and task['reason']==candidate['reason'] and task['target']==(target or {}))
            async def inspect_wiki(task=None):
                reference=target
                if not reference and task:
                    reference=next((r for r in (task.get('publication') or {}).get('records',[]) if r['kind']=='page'),None)
                if reference:
                    page=await invoke('wiki_pages_get',{'page_id':reference['id']})
                    observed={'kind':'page','id':page['id'],'revision':page['revision'],
                        'content_id':page['content']['id'],'content_hash':page['content']['content_hash']}
                    if observed!={k:reference[k] for k in observed}:
                        return 'target_changed'
                else:
                    nonlocal calls
                    if calls>=7: raise ValueError('feedback_call_budget')
                    calls+=1
                    result=await call('knowledge_search',{'options':{'space_id':str(space_id),
                        'query':candidate['source_label'],'kind':'wiki','limit':3,'mode':'text','rerank':'off','graph_depth':0}})
                    if result['hits']: return 'wiki_resolution_required'
                return None
            listed=await invoke('compilation_tasks_list',{'topic_key':candidate['topic_key'],'limit':5})
            if len(listed['tasks'])>5: raise ValueError('feedback_task_budget')
            previous=next((t for t in listed['tasks'] if matches(t)),None)
            if previous:
                actual=await invoke('compilation_tasks_get',{'task_id':previous['id']})
                if not matches(actual):
                    return {'outcome':'deferred','reason':'task_changed','compiled':False}
                issue=await inspect_wiki(actual)
                if issue: return {'outcome':'deferred','reason':issue,'compiled':False}
                return {'outcome':'existing','task_id':actual['id'],'task_revision':actual['revision'],
                    'state':actual['state'],'compiled':False}
            if listed.get('next_cursor'):
                return {'outcome':'deferred','reason':'task_comparison_incomplete','compiled':False}
            issue=await inspect_wiki()
            if issue: return {'outcome':'deferred','reason':issue,'compiled':False}
            proposal={'policy_revision':policy['revision'],'origin':'retrieval',
                'reason':candidate['reason'],'topic_key':candidate['topic_key'],
                'source_label':candidate['source_label'],'source_bindings':bindings,'target':target}
            submitted=True
            saved=await invoke('compilation_propose',{'data':{'data':proposal,'idempotency_key':request_key}})
            if saved.get('outcome')=='deferred_capacity' and 'task' not in saved:
                return {'outcome':'deferred','reason':'queue_capacity','compiled':False}
            saved_id=saved['task']['id']
            actual=await invoke('compilation_tasks_get',{'task_id':saved_id})
            if (actual['id']!=saved_id or actual.get('purpose','knowledge')!='knowledge'
                    or actual['source_bindings']!=bindings):
                raise ValueError('feedback_readback_mismatch')
            return {'outcome':'proposed','task_id':actual['id'],'task_revision':actual['revision'],
                'state':actual['state'],'proposal_outcome':saved['outcome'],'compiled':False}
    except Exception:
        # The answer is already delivered; never leak an exception or retry a write.
        return {'outcome':'uncertain' if submitted else 'deferred',
            'reason':'feedback_reconciliation_required' if submitted else 'feedback_unavailable',
            'task_id':saved_id,'compiled':False}
