# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small reviewed, extractive Wiki profile over supported revision-safe APIs."""
import json
from pathlib import Path
import re

from c0_ingest.state import atomic
from .protocol import body_hash, digest, validate_corpus


def validate_plan(plan,corpus,forbidden=()):
    validate_corpus(corpus)
    if set(plan)!={'namespace','records'} or not re.fullmatch(r'[a-z][a-z0-9-]{2,30}',plan['namespace']):
        raise ValueError('invalid_managed_namespace')
    docs={d['id']:d for d in corpus};keys=set()
    if not 1<=len(plan['records'])<=100:raise ValueError('record_budget')
    for r in plan['records']:
        if set(r)!={'key','title','synthesis','evidence','classification'} or r['classification'] not in ('extracted','inferred','uncertain'):
            raise ValueError('unapproved_semantic_profile')
        if not re.fullmatch(r'[a-z0-9-]{1,48}',r['key']) or r['key'] in keys:raise ValueError('managed_key')
        keys.add(r['key'])
        if not r['evidence'] or len(r['evidence'])>32:raise ValueError('missing_source_support')
        for e in r['evidence']:
            if set(e)!={'document_id','generation','content_hash','quote','chunk_id'}:raise ValueError('invalid_support')
            d=docs.get(e['document_id'])
            if d is None:raise ValueError('unknown_logical_document')
            if e['generation']!=d['generation'] or e['content_hash']!=d['content_hash']:raise ValueError('stale_support')
            c=next((c for c in d['chunks'] if c['chunk_id']==e['chunk_id']),None)
            if c is None or not e['quote'] or e['quote'] not in c['body']:raise ValueError('unsupported_passage')
        rendered=json.dumps(r,ensure_ascii=False).casefold()
        if any(str(x).casefold() in rendered for x in forbidden if x):raise ValueError('benchmark_material_in_layer')
        if any(x in rendered for x in ('gold_label','question_id','grading instruction','expected_answer','benchmark question')):
            raise ValueError('benchmark_material_in_layer')
    return digest(plan)


def record_payload(namespace,record):
    body='Derived navigation; unverified '+record['classification']+'.\n\n'+record['synthesis']+'\n\nOriginal evidence:\n'
    for e in record['evidence']:
        body+='\n> '+e['quote'].replace('\n','\n> ')+'\n\nOriginal chunk: '+e['chunk_id']+'\n'
    return {'slug':namespace+'-'+record['key'],'title':record['title'],'body':body,
            'metadata':{'managed_by':namespace,'managed_key':record['key'],
                        'classification':record['classification'],'source_bindings':record['evidence']}}


async def maintain(call,space,corpus,plan,state_path,*,apply=False,max_operations=30,forbidden=()):
    """call(name, args) executes supported MCP operations and raises on errors."""
    plan_hash=validate_plan(plan,corpus,forbidden)
    path=Path(state_path)
    state=json.loads(path.read_text()) if path.exists() else {'space':space,'namespace':plan['namespace'],'records':{},'pending':None}
    if (state['space'],state['namespace'])!=(space,plan['namespace']):raise ValueError('managed_target_changed')
    if len(set(state['records'])|{r['key'] for r in plan['records']})>100:raise ValueError('managed_record_budget')
    operations=0;report=[]
    async def invoke(name,args):
        nonlocal operations
        if operations>=max_operations:raise RuntimeError('layer_operation_budget')
        operations+=1
        return await call(name,{'space_id':space,**args})
    async def write(name,args):
        intent={'name':name,'args':args}
        if state['pending'] and state['pending']!=intent:raise RuntimeError('uncertain_write_requires_exact_reconciliation')
        state['pending']=intent;atomic(path,state)
        result=await invoke(name,args)
        state['pending']=None
        # Caller saves record receipt before the next operation; a lost response
        # retains the exact intent/replay key for reconciliation.
        return result
    if state['pending']:
        if not apply:raise RuntimeError('uncertain_write_requires_apply_reconciliation')
        pending=state['pending'];result=await invoke(pending['name'],pending['args'])
        state['pending']=None
        if pending['name']=='wiki_pages_upsert':
            key=pending['args']['data']['metadata']['managed_key']
            state['records'][key]={'id':result['id'],'revision':result['revision'],
                'body_hash':body_hash(result['content']['body']),'payload_hash':digest(pending['args']['data']|{'idempotency_key':None,'expected_revision':None})}
        atomic(path,state)
    for record in plan['records']:
        key=record['key'];data=record_payload(plan['namespace'],record);saved=state['records'].get(key)
        current=await invoke('wiki_pages_get',{'page_id':saved['id']}) if saved else None
        if current:
            if (current['revision']!=saved['revision'] or body_hash(current['content']['body'])!=saved['body_hash']
                or current['content']['metadata'].get('managed_by')!=plan['namespace']):raise RuntimeError('authored_or_concurrent_edit')
        same=current and all(current['content'].get(k)==data[k] for k in ('title','body','metadata'))
        report.append({'key':key,'action':'unchanged' if same else 'update' if saved else 'create','title':record['title'],'synthesis':record['synthesis'],'classification':record['classification'],'support':record['evidence']})
        if not apply:continue
        if not same:
            args={'data':{**data,'expected_revision':saved['revision'] if saved else None,
                         'idempotency_key':plan['namespace']+'-'+digest([key,data,saved])[:48]}}
            current=await write('wiki_pages_upsert',args)
            state['records'][key]={'id':current['id'],'revision':current['revision'],'body_hash':body_hash(current['content']['body'])}
            atomic(path,state)
        # Verification remains unverified. Its source links become stale on
        # retirement; exact source citation reads still enforce current access.
        target={'kind':'wiki_revision','target_id':current['content']['id'],
                'content_revision':current['revision'],'namespace':'verification'}
        annotation=await invoke('knowledge_annotations_get',target)
        refs=[{'kind':'chunk','id':e['chunk_id']} for e in record['evidence']]
        value={'status':'unverified','source_references':refs,'extensions':{'managed_by':plan['namespace']}}
        if annotation['value']!=value:
            if annotation['revision']!=0:
                raise RuntimeError('authored_or_concurrent_annotation_edit')
            await write('knowledge_annotations_update',{**target,'data':{'value':value,
                'expected_revision':annotation['revision'],'idempotency_key':digest([current['id'],current['revision'],value])}})
            atomic(path,state)
        readback=await invoke('wiki_pages_get',{'page_id':current['id']})
        if readback['content']['body']!=data['body']:raise RuntimeError('layer_readback_mismatch')
    if apply:state['plan_hash']=plan_hash;atomic(path,state)
    return {'applied':apply,'operations':operations,'plan_hash':plan_hash,'records':report}


async def verify(call,space,corpus,plan,state_path):
    validate_plan(plan,corpus)
    state=json.loads(Path(state_path).read_text())
    for r in plan['records']:
        saved=state['records'][r['key']]
        page=await call('wiki_pages_get',{'page_id':saved['id'],'space_id':space})
        if (body_hash(page['content']['body'])!=saved['body_hash'] or page['content']['body']!=record_payload(plan['namespace'],r)['body']
            or page['revision']!=saved['revision']):raise RuntimeError('layer_modified')
        for e in r['evidence']:
            c=await call('citations_get',{'chunk_id':e['chunk_id'],'space_id':space})
            expected=next(c for d in corpus for c in d['chunks'] if c['chunk_id']==e['chunk_id'])
            if e['quote'] not in c['body'] or any(c.get(k)!=expected[k] for k in ('source_id','version_id','document_id','content_hash','source_hash','body')):
                raise RuntimeError('layer_stale_or_unavailable')
    return {'verified_current':len(plan['records']),'state_hash':digest(state)}
