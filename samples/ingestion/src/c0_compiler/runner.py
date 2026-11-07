# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded external host for the existing compiler engine; no direct content writes."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

from c0_ingest.errors import C0Error
from c0_ingest.state import atomic, digest, encoded, read
from .model import READ_TOOLS

REQUIRED = {'spaces_get','compilation_policy_get','compilation_status_get','compilation_tasks_get',
    'compilation_run_claim','compilation_run_checkpoint','compilation_discover',
    'compilation_assessment_complete','compilation_propose','compilation_plan_validate',
    'compilation_apply','compilation_verify','compilation_source_bindings_get',
    'compilation_target_bindings_get','knowledge_annotations_get','compilation_semantic_select',
    'compilation_semantic_review',*READ_TOOLS}


def due(config, kind, now):
    from czero_core.project_schedules import schedule_contract
    manifest = {'timezone':config['timezone'], 'schedule':{k:config[k] for k in
        ('daily_local_time','weekly_local_time','weekly_day')}}
    return schedule_contract(manifest, now)['occurrences'][kind]['latest_due']


class Runner:
    def __init__(self, client, config, model=None):
        self.client, self.config, self.model = client, config, model
        self.path = Path(config['state_dir'])/'journal.json'
        from .config import private_file
        self.state = json.loads(private_file(self.path,maximum=262144)) if self.path.exists() else {}
        if self.state and self.state.get('binding_hash') != config['binding_hash']:
            raise C0Error('configuration_changed_review_saved_journal')
        self.state.setdefault('binding_hash',config['binding_hash'])
        self.calls = 0
        self.started = time.monotonic()
        self.run = None
        self.lease = None

    def save(self):
        atomic(self.path,self.state)

    def call(self, name, arguments=None):
        arguments = arguments or {}
        if name == 'knowledge_search':
            if arguments.get('options',{}).get('space_id',self.client.space_id)!=self.client.space_id:
                raise C0Error('wrong_space_selector')
            arguments = {**arguments,'options':{**arguments.get('options',{}),
                'space_id':self.client.space_id,'mode':'text','rerank':'off','graph_depth':0,'limit':3}}
        else:
            if 'space_id' in arguments and arguments['space_id'] != self.client.space_id:
                raise C0Error('wrong_space_selector')
            arguments = {**arguments,'space_id':self.client.space_id}
        return self.client.call(name,**arguments)

    async def async_call(self,name,arguments):
        result=self.call(name,arguments)
        if 'run' in result: self.run=result['run']
        return result

    def mutate(self, name, data):
        key=uuid4().hex
        self.state['pending']={'operation':name,'key':key,'fingerprint':digest(data),**({'action':data['action']} if 'action' in data else {}),
            **({'request_id':data['request_id']} if 'request_id' in data else {}),
            **({'claim':data} if name=='compilation_run_claim' else {}),
            **({'proposal':data} if name=='compilation_propose' else {})}
        self.save()  # Intent is durable before any network call; no source/model body.
        result=self.call(name,{'data':{'data':data,'idempotency_key':key}})
        self.state.pop('pending',None)
        if 'run' in result:
            self.run=result['run']; self.state['run_id']=self.run['id']
        if 'lease' in result: self.lease=result['lease']; self.state['lease']=self.lease
        if 'task' in result: self.state['task_id']=result['task']['id']
        self.save()
        return result

    def checkpoint(self,action,**extra):
        return self.mutate('compilation_run_checkpoint',{'lease':self.lease,
            'expected_revision':self.run['revision'],'action':action,**extra})

    def inspect(self):
        return {'status':self.call('compilation_status_get',{'run_id':self.state['run_id']} if self.state.get('run_id') else {}),
            'local':{k:v for k,v in self.state.items() if k != 'binding_hash'},'writes_c0':0}

    def recover(self):
        from czero_core.compilation_client import verify_pending
        space,policy=self.setup()
        if not policy['data']['enabled']: return {'outcome':'disabled','compiled':False,'writes_c0':0}
        if space['role'] not in ('editor','admin'): raise C0Error('editor_required')
        pending=self.state.get('pending',{}); model=self.state.get('model',{})
        original=self.state.get('recovery_of') or pending
        if original.get('operation')=='compilation_run_claim' and original.get('claim'):
            saved=self.call('compilation_run_claim',{'data':{'data':original['claim'],'idempotency_key':original['key']}})
            if 'run' in saved:
                self.state['run_id']=saved['run']['id'];self.state['cycle']=original['claim']['cycle_key']
            if 'lease' in saved: self.state['lease']=saved['lease']
            self.state.pop('pending',None);self.state.pop('recovery_of',None);self.save()
            return {'outcome':'claim_reconciled','compiled':False}
        if original.get('operation')=='compilation_propose' and original.get('proposal'):
            saved=self.call('compilation_propose',{'data':{'data':original['proposal'],'idempotency_key':original['key']}})
            if 'task' not in saved: return {'outcome':'reconcile_required','compiled':False}
            actual=self.call('compilation_tasks_get',{'task_id':saved['task']['id']})
            self.state['reconciled_proposal_id']=actual['id']
            self.state.pop('pending',None);self.state.pop('recovery_of',None);self.save()
            return {'outcome':'proposal_reconciled','task_id':actual['id'],'compiled':False}
        report=self.inspect()
        run=next((r for r in report['status']['runs'] if r['id']==self.state.get('run_id')),None)
        if not run: return {'outcome':'reconcile_required','compiled':False}
        task=(self.call('compilation_tasks_get',{'task_id':self.state['task_id']})
            if self.state.get('task_id') else None)
        publication=task and task['state'] in ('applied_pending_verify','succeeded') and original.get('operation') in ('compile_plan','verify_pending')
        receipt=(model.get('state')=='returned' and model.get('request_id') in run['data']['calls']
            and (not original or original.get('operation')=='compilation_run_checkpoint'
                and original.get('action')=='return_model' and original.get('request_id')==model.get('request_id')))
        if not publication and not receipt: return {'outcome':'reconcile_required','compiled':False}
        # Preserve the uncertain original intent while acquiring a current fence.
        self.state['recovery_of']=original;self.save()
        result=self.mutate('compilation_run_claim',{'kind':run['kind'],'cycle_key':run['cycle_key'],
            'lease_owner':run['lease_owner'],'policy_revision':policy['revision'],'task_limit':1,
            **({'project_lease':run['data']['project_lease']} if run['data'].get('project_lease') else {})})
        if result['outcome']!='claimed':
            self.state['pending']=pending;self.save()
            return {'outcome':'reconcile_required','compiled':False}
        if publication:
            key=uuid4().hex;self.state['pending']={'operation':'verify_pending','key':key};self.save()
            saved=asyncio.run(verify_pending(self.async_call,self.client.space_id,task['id'],self.lease,
                self.run['revision'],idempotency_key=key))
            self.state.pop('pending',None);self.state.pop('recovery_of',None);self.save()
            return {'outcome':saved['outcome'],'compiled':saved['outcome']=='succeeded'}
        observed=self.run['data']['calls'][model['request_id']]
        if observed['state']=='started': self.checkpoint('uncertain_model',request_id=model['request_id'])
        observed=self.run['data']['calls'][model['request_id']]
        if observed['state']=='uncertain':
            self.checkpoint('reconcile_returned',request_id=model['request_id'],
                observed_tokens=model['observed_tokens'],external_reference_hash=model['external_reference_hash'])
        elif observed['state']!='returned' or observed.get('external_reference_hash')!=model['external_reference_hash']:
            self.state['pending']=pending;self.save()
            return {'outcome':'reconcile_required','compiled':False}
        self.state.pop('pending',None);self.state.pop('recovery_of',None);self.save()
        return {'outcome':'reconciled_pending_analysis','compiled':False}

    def setup(self):
        missing=REQUIRED-set(self.client.operations)
        if missing: raise C0Error('compiler_capabilities_unavailable')
        space=self.call('spaces_get')
        if space['id'] != self.config['space_id'] or space['name'] != self.config['space_name']:
            raise C0Error('space_binding_mismatch')
        policy=self.call('compilation_policy_get')
        if policy['space_id'] != space['id']: raise C0Error('policy_binding_mismatch')
        self.request_seconds=min(self.config['timeout_seconds'],policy['data']['request_seconds'])
        self.project=None
        if not space['shared'] and 'project_get' in self.client.operations:
            try: self.project=self.call('project_get')
            except C0Error as exc:
                if not str(exc).startswith('project_not_found:'): raise
        return space,policy

    def infer(self, task, context, *, semantic_page_id=None):
        if self.model is None:
            from .model import Codex,Responses
            bounded={**self.config,'timeout_seconds':getattr(self,'request_seconds',self.config['timeout_seconds'])}
            self.model=Codex(bounded) if self.config['adapter']=='codex' else Responses(bounded)
        schemas={name:self.client.operations[name]['input_schema'] for name in READ_TOOLS}
        messages=[{'role':'user','content':json.dumps({'task':task,'context':context,
            'instruction':'Perform source-backed assessment or navigation planning using the trusted protocol.'})}]
        usage_id=None
        for _ in range(self.config['max_model_calls']):
            if self.calls >= self.config['max_model_calls'] or time.monotonic()-self.started > 180:
                raise C0Error('runner_budget_exhausted')
            size=len(encoded([messages,schemas,self.config['protocol']]))+8192
            if size > self.config['max_input_bytes']: raise C0Error('runner_input_budget_exhausted')
            usage_id=str(uuid4())
            reserved=getattr(self.model,'reservation_tokens',size+self.config['max_output_tokens'])
            binding=({'semantic_page_id':semantic_page_id,'source_bindings':task['source_bindings']} if semantic_page_id
                else {'task_id':task['id'],'expected_task_revision':task['revision']})
            result=self.checkpoint('reserve_model',request_id=usage_id,reserved_tokens=reserved,**binding)
            if result['outcome'] == 'deferred_budget': raise C0Error('server_budget_exhausted')
            self.checkpoint('start_model',request_id=usage_id)
            self.state['model']={'request_id':usage_id,'state':'started'};self.save()
            self.calls+=1
            try:
                response=self.model.request(messages,schemas)
            except C0Error as exc:
                code=str(exc)
                if code in ('model_outcome_uncertain','model_outcome_uncertain_spawn','model_outcome_uncertain_events','invalid_codex_response'):
                    self.state['model']['error_code']=code;self.save()
                raise
            count=response.get('usage',{}).get('total_tokens')
            if type(count) is not int or not 0 <= count <= reserved: count=None
            self.state['model']={'request_id':usage_id,'state':'returned',
                'response_id':response['id'],'observed_tokens':count,
                'external_reference_hash':digest(response['id'])};self.save()
            self.checkpoint('return_model',request_id=usage_id,observed_tokens=count,
                external_reference_hash=digest(response['id']))
            messages.extend(response['output'])
            calls=[o for o in response['output'] if o['type']=='function_call']
            if calls:
                if len(calls)!=1 or calls[0]['name']!='c0_read': raise C0Error('invalid_model_tool')
                tool=calls[0]; args=json.loads(tool['arguments'])
                if set(args)!= {'operation','arguments'} or args['operation'] not in READ_TOOLS:
                    raise C0Error('invalid_model_tool')
                value=json.loads(args['arguments'])
                if type(value) is not dict: raise C0Error('invalid_model_tool')
                result=self.call(args['operation'],value)
                if len(encoded(result)) > 65536: raise C0Error('model_tool_result_too_large')
                messages.append({'type':'function_call_output','call_id':tool['call_id'],'output':json.dumps(result)})
                continue
            outputs=[c['text'] for o in response['output'] if o['type']=='message'
                     for c in o.get('content',[]) if c.get('type')=='output_text']
            decision=json.loads(''.join(outputs))
            self.validate_decision(decision)
            return decision,usage_id
        raise C0Error('runner_budget_exhausted')

    @staticmethod
    def validate_decision(value):
        if type(value) is not dict or set(value)!={'title','synthesis','classification','citations','topics','no_change'}:
            raise C0Error('invalid_model_decision')
        def topic(v,extra=()):
            if type(v) is not dict or set(v)!= {'title','synthesis','classification','citations',*extra}:
                raise C0Error('invalid_model_decision')
            if (type(v['title']) is not str or not 1<=len(v['title'])<=160
                    or type(v['synthesis']) is not str or len(v['synthesis'].encode())>8192
                    or v['classification'] not in ('supported_synthesis','uncertain','contradictory','unsupported')
                    or type(v['citations']) is not list or len(v['citations'])>8):
                raise C0Error('invalid_model_decision')
            for citation in v['citations']:
                if (type(citation) is not dict or set(citation)!={'chunk_id','quote'}
                        or type(citation['chunk_id']) is not str or type(citation['quote']) is not str
                        or not citation['quote'] or len(citation['quote'].encode())>8192):
                    raise C0Error('invalid_model_decision')
        topic({k:v for k,v in value.items() if k not in ('topics','no_change')})
        if type(value['topics']) is not list or len(value['topics'])>3 or type(value['no_change']) is not bool:
            raise C0Error('invalid_model_decision')
        for item in value['topics']: topic(item,('topic_key',))

    def evidence(self,task):
        originals=[]
        for binding in task['source_bindings']:
            original=self.call('source_documents_get',{'logical_document_id':binding['logical_document_id'],
                'revision_id':binding['revision_id']})
            if original['state']!='ready' or original.get('body') is None:
                raise C0Error('source_incomplete')
            originals.append(original)
        # No truncation labelled as a full review. Larger originals remain durable pending work.
        if len(encoded(originals)) > self.config['max_input_bytes']//2:
            raise C0Error('original_requires_selective_context')
        return originals

    def search(self,title):
        return self.call('knowledge_search',{'options':{'query':title,'kind':'wiki'}})['hits']

    def assessment(self,task,decision):
        children=[];findings=[]
        for topic in decision['topics']:
            # Candidate matching is conservative. Different title alone never creates a duplicate page.
            if self.search(topic['title']): findings.append('uncertain');continue
            selections=[]
            for binding in task['source_bindings']:
                ids=[c['chunk_id'] for c in binding['chunks'] if any(q['chunk_id']==c['chunk_id'] for q in topic['citations'])]
                if ids: selections.append({'logical_document_id':binding['logical_document_id'],
                    'revision_id':binding['revision_id'],'chunk_ids':ids})
            if not selections: findings.append('unavailable_evidence');continue
            bound=self.call('compilation_source_bindings_get',{'data':{'selections':selections}})
            classification=topic['classification']
            if classification in ('uncertain','unsupported'):
                findings.append('uncertain');continue
            if classification=='contradictory': findings.append('contradiction')
            result=self.mutate('compilation_propose',{'policy_revision':self.run['policy_revision'],
                'origin':self.run['kind'],'reason':'contradiction' if classification=='contradictory' else 'missing_concept',
                'topic_key':topic['topic_key'],'source_bindings':bound['source_bindings']})
            if 'task' not in result: findings.append('budget_exhausted');continue
            children.append(result['task']['id'])
        if decision['classification'] in ('uncertain','unsupported'): findings.append('uncertain')
        if decision['classification']=='contradictory': findings.append('contradiction')
        if not decision['topics'] and not decision['no_change']: findings.append('uncertain')
        return self.mutate('compilation_assessment_complete',{'lease':self.lease,'expected_revision':self.run['revision'],
            'task_id':task['id'],'expected_task_revision':task['revision'],
            'reviewed_source_ids':[s['logical_document_id'] for s in task['source_bindings']],
            'child_task_ids':children,'status':'partial' if findings else 'reviewed','findings':sorted(set(findings))})

    def knowledge(self,task,decision,usage_id,apply):
        from czero_core.compilation_client import navigation_plan,compile_plan
        if decision['no_change'] and decision['classification']=='supported_synthesis':
            self.checkpoint('no_change',task_id=task['id'],expected_task_revision=task['revision'])
            return {'outcome':'no_change','compiled':False}
        current=self.call('wiki_pages_get',{'page_id':task['target']['id']}) if task['target'] else None
        if not current and self.search(decision['title']): raise C0Error('duplicate_candidates_require_review')
        allowed={c['chunk_id'] for s in task['source_bindings'] for c in s['chunks']}
        citations=[]
        for item in decision['citations']:
            if item['chunk_id'] not in allowed: raise C0Error('unbound_model_citation')
            citations.append((self.call('citations_get',{'chunk_id':item['chunk_id']}),item['quote']))
        if not citations: raise C0Error('original_evidence_required')
        managed=False
        if current:
            packet=self.call('compilation_target_bindings_get',{'data':{'targets':[{'kind':'page','id':current['id']}]}})
            managed=packet['target_bindings'][0]['managed']
        plan=navigation_plan(self.client.space_id,task,decision['title'],decision['synthesis'],citations,
            classification=decision['classification'],current=current,managed=managed,usage_reservation_id=usage_id,
            reviewed_source_ids=[s['logical_document_id'] for s in task['source_bindings']])
        data={'lease':self.lease,'expected_revision':self.run['revision'],'plan':plan}
        preview=asyncio.run(compile_plan(self.async_call,self.client.space_id,data))
        self.state['plan_hash']=preview['plan_hash'];self.save()
        if not apply or preview['outcome']!='eligible':
            self.checkpoint('fail',task_id=task['id'],expected_task_revision=task['revision'],error_code='unsupported_evidence')
            return {'outcome':preview['outcome'],'compiled':False}
        key=uuid4().hex
        self.state['pending']={'operation':'compile_plan','key':key,'fingerprint':digest(data)};self.save()
        saved=asyncio.run(compile_plan(self.async_call,self.client.space_id,data,apply=True,idempotency_key=key))
        self.state.pop('pending',None);self.save()
        return {'outcome':saved['outcome'],'compiled':saved['outcome']=='succeeded'}

    def semantic(self,apply):
        selected=self.mutate('compilation_semantic_select',{'lease':self.lease,'expected_revision':self.run['revision']})
        selection=selected.get('selection')
        if not selection or selection['state']=='complete': return
        # One selected page per invocation; pending selection resumes without advancing rotation.
        item=next((i for i in selection['items'] if selection['reviews'].get(i['page_id'],{}).get('status')!='reviewed'),None)
        if not item: return
        page=self.call('wiki_pages_get',{'page_id':item['page_id']})
        dependencies=self.call('compilation_dependencies_list',{'target_id':page['id'],'limit':32})
        rows=dependencies['dependencies']; bindings=[]; children=[]; usage_id=None; status='blocked'
        if rows and not dependencies.get('next_cursor') and all(r['identities_current'] for r in rows):
            selections=[]
            for logical in dict.fromkeys(r['logical_document_id'] for r in rows):
                group=[r for r in rows if r['logical_document_id']==logical and r['chunk_id']]
                if group: selections.append({'logical_document_id':logical,'revision_id':group[0]['source_revision'],
                    'chunk_ids':list(dict.fromkeys(r['chunk_id'] for r in group))})
            if 0<len(selections)<=3:
                bindings=self.call('compilation_source_bindings_get',{'data':{'selections':selections}})['source_bindings']
                previous=self.call('compilation_tasks_get',{'task_id':rows[0]['task_id']})
                schema=self.client.operations['compilation_run_checkpoint']['input_schema']
                node=schema
                for field in ('data','data'):
                    while '$ref' in node:
                        parts=node['$ref'].removeprefix('#/').split('/')
                        node=schema
                        for part in parts: node=node[part]
                    node=node.get('properties',{}).get(field,{})
                if 'semantic_page_id' in node.get('properties',{}):
                    semantic_task={**previous,'purpose':'semantic_review','origin':'weekly','source_bindings':bindings,
                        'target':{'kind':'page','id':page['id'],'revision':page['revision'],
                            'content_id':page['content']['id'],'content_hash':page['content']['content_hash']}}
                    context={'originals':self.evidence(semantic_task),'current_page':page,
                        'existing_wiki':self.search(page['title']),
                        'citations':[self.call('citations_get',{'chunk_id':c['chunk_id']})
                            for c in [c for s in bindings for c in s['chunks']][:8]],
                        'review':'Check original support, applicability, overlapping concepts, contradictions and cross-links.'}
                    decision,usage_id=self.infer(semantic_task,context,
                        semantic_page_id=page['id'])
                    if decision['no_change'] and decision['classification']=='supported_synthesis' and not decision['topics']:
                        status='reviewed'
                    elif decision['classification']=='contradictory':
                        proposal=self.mutate('compilation_propose',{'policy_revision':self.run['policy_revision'],'origin':'weekly',
                            'reason':'contradiction','topic_key':previous['topic_key'],'source_bindings':bindings,
                            'target':semantic_task['target']})
                        # A genuine contradiction is a review hold, never an automatic publish.
                        if proposal.get('task',{}).get('target',{}).get('id')==page['id']:
                            children=[proposal['task']['id']]
        page=self.call('wiki_pages_get',{'page_id':item['page_id']})
        self.mutate('compilation_semantic_review',{'lease':self.lease,'expected_revision':self.run['revision'],
            'page_id':page['id'],'revision':page['revision'],'content_id':page['content']['id'],
            'content_hash':page['content']['content_hash'],'source_bindings':bindings,'usage_reservation_id':usage_id,
            'status':status,'child_task_ids':children})

    def execute(self,kind,*,apply=False,tick=False,now=None,project_lease=None):
        now=now or datetime.now(timezone.utc)
        space,policy=self.setup()
        if not policy['data']['enabled']: return {'outcome':'disabled','compiled':False,'writes_c0':0}
        if space['role'] not in ('editor','admin'): raise C0Error('editor_required')
        if self.state.get('pending') or self.state.get('recovery_of') or self.state.get('model',{}).get('state')=='started':
            return {'outcome':'reconcile_required','compiled':False,'writes_c0':0}
        if self.project and kind in ('daily','weekly') and not project_lease:
            raise C0Error('use_existing_project_workflow_and_lease')
        if tick and self.project: raise C0Error('do_not_duplicate_project_scheduler')
        if policy['data']['timezone']!=self.config['timezone']: raise C0Error('schedule_timezone_changed')
        occurrence=due(self.config,kind,now) if tick else None
        done=self.state.get('completed',{})
        handled=self.state.get('handled',{})
        if occurrence and occurrence in (done.get(kind),handled.get(kind)):
            return {'outcome':'not_due','compiled':False,'writes_c0':0}
        if (self.state.get('finished') and kind in ('manual','bootstrap')
                or kind=='bootstrap' and self.state.get('bootstrap_stage_done')):
            self.state.pop('cycle',None)
        cycle=(now.astimezone(ZoneInfo(policy['data']['timezone'])).date().isoformat()
            if kind in ('daily','weekly') else self.state.get('cycle',uuid4().hex))
        claim={'kind':kind,'cycle_key':cycle,'lease_owner':'external-'+self.config['binding_hash'][:16],
            'policy_revision':policy['revision'],'task_limit':1}
        if project_lease: claim['project_lease']=project_lease
        self.state.update(cycle=cycle,kind=kind,finished=False,bootstrap_stage_done=False);self.save()
        result=self.mutate('compilation_run_claim',claim)
        if result['outcome']!='claimed':
            if occurrence and result['outcome']=='completed_bounded':
                done[kind]=occurrence;self.state['completed']=done;self.save()
            return {'outcome':result['outcome'],'compiled':False}
        if any(c['state'] in ('started','uncertain','reserved') for c in self.run['data']['calls'].values()):
            return {'outcome':'reconcile_required','run_id':self.run['id'],'compiled':False}
        if not result['tasks']:
            result=self.mutate('compilation_discover',{'lease':self.lease,'expected_revision':self.run['revision'],'limit':1})
        outcome={'outcome':'no_work','compiled':False}
        for selected in result.get('tasks',[])[:1]:
            task=self.call('compilation_tasks_get',{'task_id':selected['id']})
            self.state['task_id']=task['id'];self.save()
            if task['state']=='applied_pending_verify':
                from czero_core.compilation_client import verify_pending
                key=uuid4().hex
                self.state['pending']={'operation':'verify_pending','key':key,'fingerprint':digest([task['id'],self.lease,self.run['revision']])};self.save()
                saved=asyncio.run(verify_pending(self.async_call,self.client.space_id,task['id'],self.lease,
                    self.run['revision'],idempotency_key=key))
                self.state.pop('pending',None);self.save()
                outcome={'outcome':saved['outcome'],'compiled':saved['outcome']=='succeeded'}
                continue
            context={'originals':self.evidence(task),'current_page':self.call('wiki_pages_get',{'page_id':task['target']['id']}) if task['target'] else None}
            if task['purpose']=='source_assessment':
                outstanding=[];overflow=False
                for state in ('queued','needs_review'):
                    page=self.call('compilation_tasks_list',{'state':state,'limit':20})
                    overflow=overflow or bool(page.get('next_cursor'))
                    outstanding.extend({'id':t['id'],'topic_key':t['topic_key'],'state':t['state'],
                        'source_ids':[s['logical_document_id'] for s in t['source_bindings']]} for t in page['tasks'] if t['id']!=task['id'])
                if overflow:
                    outcome=self.mutate('compilation_assessment_complete',{'lease':self.lease,'expected_revision':self.run['revision'],
                        'task_id':task['id'],'expected_task_revision':task['revision'],'reviewed_source_ids':[],
                        'child_task_ids':[],'status':'partial','findings':['target_overflow']})
                    continue
                context['outstanding']=outstanding
            context['existing_wiki']=self.search(context['originals'][0]['title'])
            context['citations']=[self.call('citations_get',{'chunk_id':c['chunk_id']})
                for c in [c for s in task['source_bindings'] for c in s['chunks']][:8]]
            decision,usage_id=self.infer(task,context)
            task=self.call('compilation_tasks_get',{'task_id':task['id']})
            outcome=(self.assessment(task,decision) if task['purpose']=='source_assessment'
                else self.knowledge(task,decision,usage_id,apply))
        if kind=='weekly' and not self.project:
            self.semantic(apply)
        tasks=[self.call('compilation_tasks_get',{'task_id':i}) for i in self.run['data']['task_ids']]
        settled=all(t['state'] in ('succeeded','no_change','assessed') for t in tasks)
        settled=settled and self.run['data'].get('semantic',{}).get('state','complete')=='complete'
        # Assessment children may remain queued; the server's finish guard is authoritative.
        children=[child for t in tasks for child in t.get('assessment',{}).get('child_task_ids',[])]
        settled=settled and all(self.call('compilation_tasks_get',{'task_id':child})['state'] in ('succeeded','no_change') for child in children)
        catchup_before_due=False
        if occurrence:
            from czero_core.project_schema import occurrence_on_day
            local_day=now.astimezone(ZoneInfo(self.config['timezone'])).date().isoformat()
            try:
                today_due=occurrence_on_day({'timezone':self.config['timezone'],'schedule':self.config},kind,local_day)
                catchup_before_due=today_due>now
            except ValueError: pass  # No configured weekly occurrence today.
        final=self.checkpoint('finish' if settled and not catchup_before_due else 'partial')
        if occurrence and settled and catchup_before_due:
            handled[kind]=occurrence;self.state['handled']=handled;self.save()
        self.state['finished']=final['run']['state']=='complete'
        self.state['bootstrap_stage_done']=kind=='bootstrap' and bool(result.get('tasks')) and any(
            t['state'] in ('assessed','succeeded','no_change') for t in tasks)
        self.save()
        if occurrence and final['run']['state']=='complete':
            done[kind]=occurrence;self.state['completed']=done;self.save()
        return {'outcome':final['outcome'],'last_step':outcome.get('outcome'),'run_id':self.run['id'],
            'compiled':outcome.get('compiled',False),'complete_corpus_coverage':False,'model_calls':self.calls,
            'state':final['run']['state']}
