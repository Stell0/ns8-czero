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
