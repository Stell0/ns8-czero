# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Small research coordination policy over ProjectService's typed transactions.

External calls are never executed here. A reservation survives an uncertain call;
a database receipt cannot establish exactly-once execution at an external host.
"""
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import re
import unicodedata
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .object_schema import bounded_json, validate_record
from .project_schema import PREFIX, SCHEMAS, QUEUE_INPUT, WORKFLOWS, identifier, timestamp, occurrence_on_day
from .receipts import mutate, snapshot

PHASES = {
    'initialize': ('setup','seed','sources','wiki'),
    'daily': ('monitoring','research','evidence','synthesis','report'),
    'weekly': ('configuration','references','queue','archive','semantic','report'),
    'manual_research': ('research','evidence','synthesis'),
    'source_sync': ('collect','publish','verify'),
    'maintenance': ('inventory','review','archive'),
    'report_publication': ('load','publish','observe'),
}
ACTIVE = {'pending','in_progress','retry_wait','awaiting_merge','blocked'}


class QueueInventoryBound(ValueError):
    pass


def active_work(data):
    return data['status'] in ACTIVE or (data['status']=='deferred' and data['defer_reason']=='daily_budget')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def normalized_question(value):
    return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',value).casefold()))


def near_copy(first,second):
    # Linear bounded comparison: do not run quadratic edit matching while
    # holding the shared content transaction lock. Semantic judgment is external.
    a=normalized_question(first);b=normalized_question(second)
    if re.findall(r'\d+',a)!=re.findall(r'\d+',b):return False
    if a==b:return True
    left={a[i:i+4] for i in range(max(0,len(a)-3))}
    right={b[i:i+4] for i in range(max(0,len(b)-3))}
    return bool(left and right) and 2*len(left&right)/(len(left)+len(right))>=.96


def data_of(row):
    return {key:value for key,value in row['data'].items() if key!='key'}


def receipt(status,outcome,*rows):
    return {'status':status,'outcome':outcome,'records':snapshot([
        {key:value for key,value in row.items() if key!='space_id'} for row in rows if row is not None])}


class ProjectWorkflows:
    """Trusted mixin; ProjectService owns storage, authorization and conflicts."""
    def get_record(self,actor,kind,identity):
        if kind not in SCHEMAS or type(identity) is not str or not 1<=len(identity)<=8192:
            raise ValueError('invalid_project_record_identity')
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor)
            return snapshot({k:v for k,v in self._find(connection,kind,identity).items() if k!='space_id'})

    def _lease(self,connection,actor,lease,*,finished=False):
        if type(lease) is not dict or set(lease)!={'run_id','lease_owner','fencing_generation'}:
            raise ValueError('invalid_workflow_lease')
        identifier(lease['run_id']);identifier(lease['lease_owner'])
        if type(lease['fencing_generation']) is not int or lease['fencing_generation']<1:
            raise ValueError('invalid_workflow_fence')
        row=self._find(connection,'run_v1',lease['run_id']);run=row['data']
        if (run['lease_owner']!=lease['lease_owner'] or run['lease_actor_id']!=str(actor.user_id)
                or run['fencing_generation']!=lease['fencing_generation']
                or run['config_version']!=self._manifest(connection)['data']['version']):
            raise self.conflict()
        if finished and run['state']=='complete':return row
        if run['state']!='running' or not run['lease_expiry'] or timestamp(run['lease_expiry'])<=self.clock():
            raise self.conflict()
        return row

    def _workflow_mutate(self,actor,operation,payload,key,lease,execute,*,guard=None):
        bounded_json(payload,maximum=262144)
        def authorize(connection,captured,minimum):
            current=self._authorize(connection,captured,minimum)
            # Recheck before receipt replay as well as after lock acquisition.
            self._lease(connection,current,lease,finished=operation=='run_checkpoint')
            if guard:guard(connection)
            return current
        def checked(connection,current):
            run=self._lease(connection,current,lease)
            return execute(connection,current,run)
        return mutate(self.database,authorize,actor,'project.'+operation,
            {**payload,'lease':lease},key,checked,conflict=self.conflict,lock_objects=True)

    def claim_run(self,actor,workflow_type,lease_owner,config_version,*,cycle_key='',local_cycle_date='',
                  scheduled_for='',lease_seconds=300,connector_id='',idempotency_key):
        if workflow_type not in WORKFLOWS or type(config_version) is not int or config_version<1:
            raise ValueError('invalid_workflow')
        identifier(lease_owner)
        if type(lease_seconds) is not int or not 60<=lease_seconds<=900:raise ValueError('invalid_lease_duration')
        if local_cycle_date:date.fromisoformat(local_cycle_date)
        if scheduled_for:timestamp(scheduled_for)
        if cycle_key:identifier(cycle_key)
        if connector_id:
            identifier(connector_id)
            if workflow_type!='source_sync':raise ValueError('connector_lease_requires_source_sync')
        payload={'workflow_type':workflow_type,'lease_owner':lease_owner,'config_version':config_version,
            'cycle_key':cycle_key,'local_cycle_date':local_cycle_date,'scheduled_for':scheduled_for,'lease_seconds':lease_seconds,'connector_id':connector_id}
        def execute(connection,current):
            manifest=self._manifest(connection);config=manifest['data']['manifest'];now=self.clock()
            if manifest['data']['version']!=config_version:raise self.conflict()
            today=now.astimezone(ZoneInfo(config['timezone'])).date().isoformat()
            day=local_cycle_date or today
            if date.fromisoformat(day).isoformat()!=day:raise ValueError('invalid_project_cycle_date')
            if workflow_type in ('daily','weekly') and scheduled_for:
                scheduled=timestamp(scheduled_for)
                if scheduled>now or scheduled.astimezone(ZoneInfo(config['timezone'])).date().isoformat()!=day:
                    raise ValueError('invalid_project_scheduled_occurrence')
            cycle='once' if workflow_type=='initialize' else day if workflow_type in ('daily','weekly') else cycle_key
            if not cycle:raise ValueError('stable_workflow_cycle_required')
            run_id=digest([str(self._space_id),workflow_type,cycle])
            previous=self._find(connection,'run_v1',run_id,required=False)
            if previous is None:
                if day!=today and (workflow_type not in ('daily','weekly') or not scheduled_for
                        or timestamp(scheduled_for)!=occurrence_on_day(config,workflow_type,day)
                        or now-timestamp(scheduled_for)>timedelta(days=8)):
                    raise ValueError('new_workflow_requires_current_or_recent_scheduled_cycle')
                run={'run_id':run_id,'project_id':str(self._space_id),'config_version':config_version,
                    'workflow_type':workflow_type,'local_cycle_date':day,'cycle_key':cycle,
                    'scheduled_for':scheduled_for or now.isoformat(),'started_at':now.isoformat(),'finished_at':'',
                    'state':'running','current_phase':PHASES[workflow_type][0],'attempt_count':1,
                    'lease_owner':lease_owner,'lease_actor_id':str(current.user_id),
                    'lease_expiry':(now+timedelta(seconds=lease_seconds)).isoformat(),'fencing_generation':1,
                    'error_code':'','result_refs':[]}
            else:
                run=data_of(previous)
                if run['config_version']==config_version and run['state']=='complete':
                    return receipt('SAVED','workflow_already_complete',previous)
                live=run['state']=='running' and run['lease_expiry'] and timestamp(run['lease_expiry'])>now
                same=run['lease_owner']==lease_owner and run['lease_actor_id']==str(current.user_id)
                if live and not same:raise self.conflict()
                if not live or run['config_version']!=config_version:
                    if run['attempt_count']>=config['research']['max_attempts']:
                        run.update(state='blocked',error_code='workflow_retry_exhausted',lease_expiry='')
                        blocked=self._save(connection,current,'run_v1',run_id,run,previous=previous)
                        return receipt('BLOCKED','workflow_retry_exhausted',blocked)
                    run.update(attempt_count=run['attempt_count']+1,fencing_generation=run['fencing_generation']+1)
                if run['config_version']!=config_version:
                    run.update(config_version=config_version,current_phase=PHASES[workflow_type][0],finished_at='',result_refs=[])
                run.update(state='running',lease_owner=lease_owner,lease_actor_id=str(current.user_id),
                    lease_expiry=(now+timedelta(seconds=lease_seconds)).isoformat(),error_code='')
            if connector_id:
                connector=self._find(connection,'connector_v1',connector_id)
                if connector_id not in config['connector_ids'] or not connector['data']['definition']['enabled']:
                    raise ValueError('source_connector_not_enabled')
                binding=self._find(connection,'connector_lease_v1',connector_id,required=False)
                if binding and binding['data']['run_id']!=run_id:
                    other=self._find(connection,'run_v1',binding['data']['run_id'])['data']
                    if (other['state']=='running' and other['config_version']==config_version and other['lease_expiry']
                            and timestamp(other['lease_expiry'])>now):raise self.conflict()
                self._save(connection,current,'connector_lease_v1',connector_id,{'connector_id':connector_id,'run_id':run_id},previous=binding)
            saved=self._save(connection,current,'run_v1',run_id,run,previous=previous)
            return receipt('SAVED','workflow_claimed',saved)
        return self._mutate(actor,'run_claim',payload,idempotency_key,execute)

    def _references(self,connection,values,*,ready=True):
        if type(values) is not list or len(values)>100 or any(type(v) is not str for v in values) or len(set(values))!=len(values):
            raise ValueError('invalid_workflow_references')
        for value in values:
            if type(value) is not str:raise ValueError('invalid_workflow_reference')
            UUID(value)
            rows=connection.execute(text('''
                SELECT 'source' AS kind,state FROM c0_source_versions WHERE space_id=:space AND id=CAST(:id AS uuid)
                UNION ALL SELECT 'wiki','ready' FROM c0_wiki_revisions WHERE space_id=:space AND id=CAST(:id AS uuid)
                UNION ALL SELECT 'object','ready' FROM c0_objects WHERE space_id=:space AND id=CAST(:id AS uuid)
                UNION ALL SELECT 'claim','ready' FROM c0_claims WHERE space_id=:space AND id=CAST(:id AS uuid)
                UNION ALL SELECT 'chunk','ready' FROM c0_chunks WHERE space_id=:space AND id=CAST(:id AS uuid)
                '''),{'space':self._space_id,'id':value}).mappings().all()
            if len(rows)!=1 or (ready and rows[0]['state']!='ready'):
                raise ValueError('workflow_reference_not_stored_or_ready')
        return values

    def checkpoint_run(self,actor,lease,phase,status,*,references=None,summary='',idempotency_key):
        references=[] if references is None else references
        if status not in ('SAVED','PARTIAL','BLOCKED') or type(summary) is not str or len(summary)>4096:
            raise ValueError('invalid_workflow_checkpoint')
        payload={'phase':phase,'status':status,'references':references,'summary':summary}
        def execute(connection,current,run_row):
            run=data_of(run_row);phases=PHASES[run['workflow_type']]
            if phase not in phases:raise ValueError('invalid_workflow_phase')
            self._references(connection,references,ready=status=='SAVED')
            identity=run['run_id']+':'+str(run['config_version'])+':'+phase
            if status!='SAVED':identity+=':'+str(run['fencing_generation'])+':'+status
            previous=self._find(connection,'checkpoint_v1',identity,required=False)
            fingerprint=digest(payload)
            if previous:
                if previous['data']['payload_hash']!=fingerprint:raise self.conflict()
                return receipt(status,'checkpoint_already_saved',run_row,previous)
            if run['current_phase']!=phase:raise self.conflict()
            if run['workflow_type']=='daily' and phase=='monitoring' and status=='SAVED':self._monitoring_ready(connection,run)
            if run['workflow_type']=='weekly' and status=='SAVED':self._weekly_phase_ready(connection,run,phase,references)
            if run['workflow_type'] in ('daily','weekly') and phase=='report' and status=='SAVED':
                report=self._find(connection,'report_v1',run['workflow_type']+':'+run['local_cycle_date'])
                values=self._saved_report(connection,report)
                if (str(report['id']) not in references or values['source_run_id']!=run['run_id']
                        or values['draft_open']):raise ValueError('workflow_saved_report_required')
            saved=self._save(connection,current,'checkpoint_v1',identity,
                {'run_id':run['run_id'],'config_version':run['config_version'],'phase':phase,'status':status,
                 'payload_hash':fingerprint,'references':references,'summary':summary,'recorded_at':self.clock().isoformat()})
            if status=='SAVED':
                position=phases.index(phase)
                run['result_refs']=list(dict.fromkeys(run['result_refs']+references))
                if len(run['result_refs'])>100:raise ValueError('workflow_reference_limit')
                if position+1==len(phases):
                    run.update(state='complete',finished_at=self.clock().isoformat(),lease_expiry='')
                else:run['current_phase']=phases[position+1]
            else:run.update(state='partial' if status=='PARTIAL' else 'blocked',error_code='phase_incomplete',lease_expiry='')
            current_run=self._save(connection,current,'run_v1',run['run_id'],run,previous=run_row)
            return receipt(status,'checkpoint_saved',current_run,saved)
        return self._workflow_mutate(actor,'run_checkpoint',payload,idempotency_key,lease,execute)

    def _budget(self,connection,current,manifest):
        config=manifest['data']['manifest'];now=self.clock()
        pointer=self._find(connection,'budget_pointer_v1','active',required=False)
        if pointer and timestamp(pointer['data']['window_end'])>now:
            return self._find(connection,'budget_v1',pointer['data']['local_date'])
        zone=ZoneInfo(config['timezone']);local=now.astimezone(zone);day=local.date().isoformat()
        end=datetime.combine(local.date()+timedelta(days=1),time(),zone).astimezone(timezone.utc)
        previous=self._find(connection,'budget_v1',day,required=False)
        if previous:
            values=data_of(previous);values['window_end']=max(timestamp(values['window_end']),end).isoformat()
        else:
            values={'project_id':str(self._space_id),'local_date':day,'timezone':config['timezone'],
                'window_end':end.isoformat(),'ordinary_limit':config['research']['normal_daily_attempts'],
                'total_limit':config['research']['urgent_total_daily_attempts'],'used':0,'roots_admitted':0,
                'roots_limit':config['research']['max_new_roots_per_day'],'config_version':manifest['data']['version']}
        budget=self._save(connection,current,'budget_v1',day,values,previous=previous)
        self._save(connection,current,'budget_pointer_v1','active',{'local_date':day,'window_end':values['window_end']},previous=pointer)
        return budget

    def _queue_rows(self,connection,*,active_only=False):
        maximum=self._manifest(connection)['data']['manifest']['maintenance']['max_inventory']
        condition=" AND data->>'status' NOT IN ('complete','archived')" if active_only else ''
        rows=[dict(row) for row in connection.execute(text('''SELECT * FROM c0_objects
            WHERE space_id=:space AND type_name=:type'''+condition+' ORDER BY created_at,id LIMIT :limit'),
            {'space':self._space_id,'type':PREFIX+'queue_v1','limit':maximum+1}).mappings()]
        if len(rows)>maximum:raise QueueInventoryBound('queue_inventory_incomplete_requires_review')
        return rows

    def _topic_scope(self,connection,topic_id,*,one_off=False):
        topic=self._find(connection,'topic_v1',topic_id)['data']
        if topic['lifecycle']!='active':return None
        if topic['expires_at'] and timestamp(topic['expires_at'])<=self.clock():
            # Expiry belongs to a distinct future weekly checkpoint, including recovery.
            expired=connection.execute(text('''SELECT EXISTS(SELECT 1 FROM c0_objects WHERE space_id=:space
                AND type_name=:type AND data->>'workflow_type'='weekly'
                AND (data->>'started_at')::timestamptz>:created
                AND (data->>'started_at')::timestamptz>=:expiry)'''),
                {'space':self._space_id,'type':PREFIX+'run_v1','created':timestamp(topic['created_at']),
                    'expiry':timestamp(topic['expires_at'])}).scalar_one()
            if expired:return None
        if topic['classification']=='peripheral' and not one_off:return None
        for anchor_id in topic['anchor_ids']:
            anchor=self._find(connection,'topic_v1',anchor_id)['data']
            if anchor['classification']!='user' or anchor['lifecycle']!='active' or not anchor['authorized_by']:return None
        pending=list(topic['parent_ids']);seen=set()
        while pending:
            parent_id=pending.pop()
            if parent_id in seen:continue
            seen.add(parent_id)
            if len(seen)>1000:raise ValueError('topic_ancestry_limit')
            parent=self._find(connection,'topic_v1',parent_id)['data']
            if parent['classification']=='peripheral' or parent['lifecycle']!='active':return None
            pending.extend(parent['parent_ids'])
        return topic

    def _lineage_allowed(self,connection,identities,by_id):
        pending=list(identities);seen=set()
        while pending:
            identity=pending.pop()
            if identity in seen:continue
            seen.add(identity)
            if len(seen)>1000:raise ValueError('research_lineage_limit')
            if identity not in by_id:
                parent_row=self._find(connection,'queue_v1',identity,required=False)
                if not parent_row:raise ValueError('unknown_causal_parent')
                by_id[identity]=parent_row
            parent=by_id[identity]['data']
            if parent['terminal'] or parent['status']=='archived' or not self._topic_scope(connection,parent['topic_id']):return False
            pending.extend(parent['parent_ids'])
        return True

    def admit(self,actor,candidate,*,idempotency_key):
        candidate=validate_record(QUEUE_INPUT,bounded_json(candidate))
        for field in ('stable_id','topic_id','novelty_key'):identifier(candidate[field])
        for field in ('not_before','due_at'):
            if candidate[field]:timestamp(candidate[field])
        for field in ('parent_ids','anchor_ids'):
            if len(set(candidate[field]))!=len(candidate[field]):raise ValueError('duplicate_admission_identity')
            for value in candidate[field]:identifier(value)
        if candidate['stable_id'] in candidate['parent_ids']:raise ValueError('cyclic_research_lineage')
        if candidate['priority']==0 and not candidate['urgency_reason'].strip():raise ValueError('urgent_reason_required')
        if not normalized_question(candidate['question']):raise ValueError('question_required')
        def execute(connection,current):
            manifest=self._manifest(connection);config=manifest['data']['manifest'];now=self.clock()
            calendar=self._calendar_context(connection,candidate) if candidate['origin']=='calendar' else None
            self._references(connection,candidate['related_pages'])
            try:rows=self._queue_rows(connection)
            except QueueInventoryBound:
                existing=self._find(connection,'queue_v1',candidate['stable_id'],required=False)
                expected=digest([normalized_question(candidate['question']),digest([candidate[k] for k in ('question_conditions','entity_version','time_window')])])
                if existing and existing['data']['dedup_key']!=expected:raise self.conflict()
                if existing is None:
                    found=connection.execute(text('''SELECT o.* FROM c0_object_keys k JOIN c0_objects o
                        ON o.id=k.object_id AND o.space_id=k.space_id WHERE k.space_id=:space AND k.type_name=:type
                        AND k.field='dedup_key' AND k.value=CAST(:value AS jsonb)'''),
                        {'space':self._space_id,'type':PREFIX+'queue_v1','value':json.dumps(expected)}).mappings().one_or_none()
                    existing=dict(found) if found else None
                if existing and existing['data']['dedup_key']==expected:
                    rows=[existing]
                    pending=list(candidate['parent_ids']);seen=set()
                    while pending:
                        parent=pending.pop()
                        if parent in seen:continue
                        seen.add(parent)
                        if len(seen)>1000:raise ValueError('research_lineage_limit')
                        parent_row=self._find(connection,'queue_v1',parent)
                        rows.append(parent_row);pending.extend(parent_row['data']['parent_ids'])
                else:
                    bounded_topic=self._topic_scope(connection,candidate['topic_id'],one_off=candidate['origin']=='user')
                    disposition='defer_capacity';reason='historical_inventory_requires_review'
                    if not bounded_topic or candidate['excluded']:
                        disposition='reject_scope';reason='inactive_terminal_or_excluded_topic'
                    elif set(candidate['anchor_ids'])!=set(bounded_topic['anchor_ids']):
                        disposition='needs_user_scope_decision';reason='anchor_scope_changed'
                    elif not self._lineage_allowed(connection,candidate['parent_ids'],{}):
                        disposition='archive_candidate';reason='terminal_or_out_of_scope_lineage'
                    held=self._save(connection,current,'admission_v1',uuid4().hex,{'candidate_id':candidate['stable_id'],
                        'disposition':disposition,'reason':reason,'target_id':'',
                        'candidate':candidate,'config_version':manifest['data']['version'],'decided_at':now.isoformat()})
                    return receipt('QUEUED' if disposition=='defer_capacity' else 'BLOCKED',disposition,held)
            by_id={row['data']['stable_id']:row for row in rows}
            context=digest([candidate[k] for k in ('question_conditions','entity_version','time_window')])
            question=normalized_question(candidate['question']);question_key=digest(question)
            dedup=digest([question,context])
            topic=self._topic_scope(connection,candidate['topic_id'],one_off=candidate['origin']=='user')
            disposition='admit';reason='eligible';target=None;expansion=calendar['event']['expansion_priority'] if calendar else candidate['priority'];roots=[]
            if not topic or candidate['excluded']:
                disposition='reject_scope';reason='inactive_terminal_or_excluded_topic'
            elif set(candidate['anchor_ids'])!=set(topic['anchor_ids']):
                disposition='needs_user_scope_decision';reason='direct_user_anchors_required'
            elif not candidate['assessment_ref'].strip() or not candidate['direct_contribution'].strip():
                raise ValueError('admission_assessment_required')
            parents=[]
            for parent_id in candidate['parent_ids']:
                if parent_id not in by_id:raise ValueError('unknown_causal_parent')
                parent=by_id[parent_id]['data'];parents.append(parent)
                if parent['terminal'] or parent['status']=='archived' or not self._topic_scope(connection,parent['topic_id']):
                    disposition='archive_candidate';reason='terminal_or_out_of_scope_lineage'
            if not self._lineage_allowed(connection,candidate['parent_ids'],by_id):
                disposition='archive_candidate';reason='terminal_or_out_of_scope_lineage'
            if parents:
                if candidate['root_reason']!='derived':raise ValueError('derived_work_requires_lineage')
                excluded=set()
                for assessment in candidate['independent_parents']:
                    if (assessment['parent_id'] not in candidate['parent_ids'] or not assessment['reason'].strip()
                            or not assessment['evidence_refs']):raise ValueError('independent_parent_evidence_required')
                    excluded.add(assessment['parent_id'])
                causal=[p for p in parents if p['stable_id'] not in excluded]
                if not causal:raise ValueError('causal_parent_required')
                expansion=max(p['expansion_priority'] for p in causal)+config['research']['child_priority_increment']
                roots=sorted({root for p in parents for root in p['root_ids']})
                if len(roots)>8:raise ValueError('lineage_root_limit')
                if expansion>100:raise ValueError('expansion_priority_exhausted')
                for parent in parents:
                    children=[row for row in rows if parent['stable_id'] in row['data']['parent_ids'] and row['data']['stable_id']!=candidate['stable_id']]
                    if len(children)>=config['research']['max_children_per_investigation']:
                        disposition='archive_candidate';reason='child_limit'
            else:
                if candidate['independent_parents']:raise ValueError('unexpected_independent_parent')
                if candidate['root_reason']=='derived':raise ValueError('causal_parent_required')
                if candidate['origin']=='research':raise ValueError('research_followup_requires_parent')
                if candidate['origin']=='user':
                    if candidate['root_reason']!='user_request' or not candidate['authorization_ref'].strip():
                        raise ValueError('one_off_user_authorization_required')
                elif candidate['origin']=='initialization':
                    if candidate['root_reason']!='approved_initialization' or not candidate['authorization_ref'].strip():
                        raise ValueError('initialization_authorization_required')
                elif candidate['root_reason']!='independent_external_event' or not candidate['novelty_refs']:
                    raise ValueError('independent_novel_event_required')
                roots=[calendar['lineage_root_id'] if calendar else candidate['stable_id']]
            if candidate['stable_id'] in by_id:
                target=by_id[candidate['stable_id']]
                if target['data']['dedup_key']!=dedup:raise self.conflict()
            for row in rows:
                q=row['data']
                similar=(q['context_key']==context and near_copy(q['question'],candidate['question']))
                if q['dedup_key']==dedup or similar:
                    target=row;break
            for assessment in candidate['semantic_matches']:
                if assessment['target_id'] not in by_id or not assessment['assessment_ref'].strip() or not assessment['reason'].strip():
                    raise ValueError('invalid_semantic_match')
                if assessment['equivalent']:target=by_id[assessment['target_id']]
            if target and disposition=='admit':disposition='merge';reason='existing_question_preserves_lineage'
            budget=self._budget(connection,current,manifest)
            root_admitted=bool(parents) or candidate['origin']=='user'
            if disposition=='admit':
                active=sum(active_work(q['data']) for q in rows)
                if active>=config['research']['max_active_items']:
                    disposition='defer_capacity';reason='active_capacity'
                elif not parents and candidate['origin']!='user':
                    initialized=sum(q['data']['origin']=='initialization' and q['data']['root_admitted'] for q in rows)
                    if candidate['origin']=='initialization' and initialized>=min(5,config['research']['normal_daily_attempts']):
                        disposition='defer_capacity';reason='initialization_seed_limit'
                    elif budget['data']['roots_admitted']>=budget['data']['roots_limit']:
                        disposition='defer_capacity';reason='daily_root_capacity'
                    else:
                        values=data_of(budget);values['roots_admitted']+=1
                        budget=self._save(connection,current,'budget_v1',values['local_date'],values,previous=budget)
                        root_admitted=True
            admission_id=uuid4().hex
            admission=self._save(connection,current,'admission_v1',admission_id,{
                'candidate_id':candidate['stable_id'],'disposition':disposition,'reason':reason,
                'target_id':target['data']['stable_id'] if target else candidate['stable_id'] if disposition in ('admit','defer_capacity') else '',
                'candidate':candidate,'config_version':manifest['data']['version'],'decided_at':now.isoformat()})
            if disposition=='merge':
                # A fresh scope assessment may revalidate existing pending work; it
                # never replaces causal roots, depth, attempts, result or urgency.
                values=data_of(target)
                if values['topic_id']==candidate['topic_id'] and values['status'] not in ('archived','complete'):
                    values['admission_ref']=str(admission['id'])
                    target=self._save(connection,current,'queue_v1',values['stable_id'],values,previous=target)
                return receipt('QUEUED',disposition,admission,target,budget)
            if disposition not in ('admit','defer_capacity'):
                return receipt('BLOCKED',disposition,admission)
            values={k:candidate[k] for k in ('stable_id','topic_id','question','kind','origin','origin_reference',
                'priority','priority_reason','urgency_reason','parent_ids','anchor_ids','novelty_key','related_pages','not_before','due_at')}
            values.update(project_id=str(self._space_id),expansion_priority=expansion,
                lineage_root_id=roots[0],root_ids=roots,dedup_key=dedup,question_key=question_key,context_key=context,
                root_admitted=root_admitted,created_at=now.isoformat(),status='pending' if disposition=='admit' else 'deferred',
                terminal=topic['classification']=='peripheral',defer_reason='' if disposition=='admit' else reason,
                attempt_count=0,retry_after='',result_reference='',last_attempt_id='',admission_ref=str(admission['id']))
            saved=self._save(connection,current,'queue_v1',candidate['stable_id'],values)
            return receipt('QUEUED',disposition,admission,saved,budget)
        def admitted(connection,current):
            result=execute(connection,current)
            if candidate['origin']=='calendar':self._calendar_admitted(connection,current,candidate,result)
            return result
        return self._mutate(actor,'queue_admit',candidate,idempotency_key,admitted)

    def retune_queue(self,actor,stable_id,priority,priority_reason,urgency_reason,*,expected_revision,idempotency_key):
        identifier(stable_id)
        if type(priority) is not int or not 0<=priority<=100 or type(priority_reason) is not str or not 1<=len(priority_reason)<=512:
            raise ValueError('invalid_queue_priority')
        if type(urgency_reason) is not str or len(urgency_reason)>512 or (priority==0 and not urgency_reason.strip()):
            raise ValueError('urgent_reason_required')
        payload=dict(stable_id=stable_id,priority=priority,priority_reason=priority_reason,
            urgency_reason=urgency_reason,expected_revision=expected_revision)
        def execute(connection,current):
            previous=self._find(connection,'queue_v1',stable_id)
            if type(expected_revision) is not int or previous['revision']!=expected_revision:raise self.conflict()
            values=data_of(previous);values.update(priority=priority,priority_reason=priority_reason,urgency_reason=urgency_reason)
            saved=self._save(connection,current,'queue_v1',stable_id,values,previous=previous)
            return receipt('QUEUED','priority_changed',saved)
        return self._mutate(actor,'queue_retune',payload,idempotency_key,execute)

    def _attempt(self,connection,run,attempt_id):
        previous=self._find(connection,'attempt_v1',attempt_id)
        if previous['data']['run_id']!=run['run_id']:raise self.conflict()
        return previous

    def _queue_current(self,connection,queue):
        admission=connection.execute(text('''SELECT data FROM c0_objects
            WHERE space_id=:space AND id=CAST(:id AS uuid) AND type_name=:type'''),
            {'space':self._space_id,'id':queue['admission_ref'],'type':PREFIX+'admission_v1'}).scalar_one_or_none()
        if not admission or admission['config_version']!=self._manifest(connection)['data']['version']:
            return False
        return (bool(self._topic_scope(connection,queue['topic_id'],one_off=queue['origin']=='user'))
            and self._lineage_allowed(connection,queue['parent_ids'],{}))

    def reserve(self,actor,lease,*,resume_attempt_id='',idempotency_key):
        if resume_attempt_id:identifier(resume_attempt_id)
        def execute(connection,current,run_row):
            run=run_row['data'];manifest=self._manifest(connection);config=manifest['data']['manifest'];now=self.clock()
            if run['workflow_type'] not in ('daily','weekly','manual_research','initialize','maintenance'):
                raise ValueError('workflow_cannot_reserve_research')
            if resume_attempt_id:
                previous=self._attempt(connection,run,resume_attempt_id);attempt=data_of(previous)
                queue=self._find(connection,'queue_v1',attempt['queue_id'])
                if attempt['state']=='reserved' and not self._queue_current(connection,queue['data']):
                    return receipt('BLOCKED','scope_reassessment_required',previous,queue)
                if attempt['state']=='invoking' and attempt['fencing_generation']!=run['fencing_generation']:
                    attempt['state']='uncertain'
                attempt['fencing_generation']=run['fencing_generation']
                previous=self._save(connection,current,'attempt_v1',resume_attempt_id,attempt,previous=previous)
                status='ACCEPTED_PENDING_MERGE' if attempt['state']=='result_saved' else 'BLOCKED' if attempt['state'] in ('uncertain','failed') else 'SAVED'
                return receipt(status,'reservation_resumed',previous,queue)
            if run['workflow_type']=='daily':self._monitoring_ready(connection,run)
            budget=self._budget(connection,current,manifest);slot=budget['data']['used']+1
            if slot>budget['data']['total_limit']:return receipt('BLOCKED','daily_budget_exhausted',budget)
            try:rows=self._queue_rows(connection,active_only=True)
            except QueueInventoryBound:return receipt('BLOCKED','active_inventory_requires_review',budget)
            eligible=[];blocked=[]
            for row in rows:
                q=row['data']
                if q['status'] not in ('pending','retry_wait','deferred'):continue
                if q['attempt_count']>=config['research']['max_attempts']:continue
                if any(q[k] and timestamp(q[k])>now for k in ('not_before','retry_after')):continue
                admission=connection.execute(text('SELECT data FROM c0_objects WHERE id=CAST(:id AS uuid) AND space_id=:space'),
                    {'id':q['admission_ref'],'space':self._space_id}).scalar_one()
                if (admission['config_version']!=manifest['data']['version'] or not self._topic_scope(connection,q['topic_id'],one_off=q['origin']=='user')):
                    continue
                if not self._lineage_allowed(connection,q['parent_ids'],{r['data']['stable_id']:r for r in rows}):continue
                if q['status']=='deferred' and q['defer_reason'] not in ('daily_budget',''):
                    active=sum(active_work(other['data']) for other in rows)
                    if active>=config['research']['max_active_items']:continue
                    if not q['root_admitted']:
                        if q['origin']=='initialization':
                            initialized=connection.execute(text('''SELECT count(*) FROM c0_objects WHERE space_id=:space AND type_name=:type
                                AND data->>'origin'='initialization' AND data->>'root_admitted'='true' '''),
                                {'space':self._space_id,'type':PREFIX+'queue_v1'}).scalar_one()
                            if initialized>=min(5,config['research']['normal_daily_attempts']):continue
                        if budget['data']['roots_admitted']>=budget['data']['roots_limit']:continue
                if slot>budget['data']['ordinary_limit'] and q['priority']!=0:
                    values=data_of(row);values.update(status='deferred',defer_reason='daily_budget')
                    blocked.append(self._save(connection,current,'queue_v1',q['stable_id'],values,previous=row));continue
                eligible.append(row)
            if not eligible:return receipt('BLOCKED','no_eligible_research',budget,*blocked[:99])
            # Urgency always wins; ageing and per-anchor service break ordinary
            # ties without rewriting stored priority or inherited expansion depth.
            def ranking(row):
                q=row['data'];age=(now-timestamp(q['created_at'])).days
                overdue=q['kind'] in ('validation','contradiction') and q['due_at'] and timestamp(q['due_at'])<=now
                service=sum(other['data']['attempt_count'] for other in rows if set(q['anchor_ids'])&set(other['data']['anchor_ids']))
                return (q['priority']!=0,not (slot==budget['data']['ordinary_limit'] and overdue),
                    max(1,q['priority']-min(20,age//14)),service,q['created_at'],q['stable_id'])
            previous=min(eligible,key=ranking);queue=data_of(previous)
            values=data_of(budget);values['used']=slot
            if not queue['root_admitted']:
                values['roots_admitted']+=1;queue['root_admitted']=True
            budget=self._save(connection,current,'budget_v1',values['local_date'],values,previous=budget)
            attempt_id=uuid4().hex;queue.update(status='in_progress',defer_reason='',attempt_count=queue['attempt_count']+1,last_attempt_id=attempt_id)
            saved_queue=self._save(connection,current,'queue_v1',queue['stable_id'],queue,previous=previous)
            attempt=self._save(connection,current,'attempt_v1',attempt_id,{'attempt_id':attempt_id,'queue_id':queue['stable_id'],
                'run_id':run['run_id'],'project_id':str(self._space_id),'local_date':values['local_date'],'slot':slot,
                'attempt_number':queue['attempt_count'],'priority':queue['priority'],'anchor_ids':queue['anchor_ids'],
                'selection_reason':'urgent' if queue['priority']==0 else 'bounded_priority_age_and_anchor_service',
                'reserved_at':now.isoformat(),'state':'reserved','result_reference':'','invocation_ref':'',
                'fencing_generation':run['fencing_generation']})
            return receipt('SAVED','attempt_reserved',attempt,saved_queue,budget)
        return self._workflow_mutate(actor,'attempt_reserve',{'resume_attempt_id':resume_attempt_id},idempotency_key,lease,execute)

    def invocation(self,actor,lease,attempt_id,state,*,external_reference='',result_reference='',error_code='',idempotency_key):
        identifier(attempt_id)
        if state not in ('started','returned','uncertain','failed'):raise ValueError('invalid_invocation_state')
        if type(external_reference) is not str or len(external_reference)>512:raise ValueError('invalid_external_reference')
        if type(error_code) is not str or not re.fullmatch(r'[a-z0-9_.-]{0,128}',error_code):raise ValueError('invalid_error_code')
        payload=dict(attempt_id=attempt_id,state=state,external_reference=external_reference,result_reference=result_reference,error_code=error_code)
        def execute(connection,current,run_row):
            run=run_row['data'];previous=self._attempt(connection,run,attempt_id);attempt=data_of(previous)
            queue_row=self._find(connection,'queue_v1',attempt['queue_id']);queue=data_of(queue_row)
            if attempt['fencing_generation']!=run['fencing_generation']:raise self.conflict()
            if state=='started' and not self._queue_current(connection,queue):raise self.conflict()
            allowed={'started':('reserved',),'returned':('invoking','uncertain'),
                'uncertain':('invoking','uncertain'),'failed':('reserved','invoking','uncertain')}
            if attempt['state'] not in allowed[state]:raise self.conflict()
            if state=='returned':
                if not result_reference:raise ValueError('stored_result_required')
                self._research_result(connection,attempt_id,result_reference)
                queue.update(status='awaiting_merge',result_reference=result_reference,retry_after='')
                attempt.update(state='result_saved',result_reference=result_reference)
            elif result_reference:raise ValueError('unexpected_result_reference')
            elif state=='started':attempt['state']='invoking'
            elif state=='uncertain':attempt['state']='uncertain';queue['status']='blocked'
            else:
                attempt['state']='failed'
                maximum=self._manifest(connection)['data']['manifest']['research']['max_attempts']
                queue.update(status='blocked' if queue['attempt_count']>=maximum else 'retry_wait',
                    retry_after=(self.clock()+timedelta(seconds=min(3600,30*2**(queue['attempt_count']-1)))).isoformat())
            observation=self._save(connection,current,'invocation_v1',uuid4().hex,{
                'attempt_id':attempt_id,'state':state,'result_reference':result_reference,'external_reference':external_reference,
                'error_code':error_code,'recorded_at':self.clock().isoformat(),'run_id':run['run_id'],
                'fencing_generation':run['fencing_generation']})
            attempt['invocation_ref']=str(observation['id'])
            saved=self._save(connection,current,'attempt_v1',attempt_id,attempt,previous=previous)
            saved_queue=self._save(connection,current,'queue_v1',queue['stable_id'],queue,previous=queue_row)
            return receipt('ACCEPTED_PENDING_MERGE' if state=='returned' else 'BLOCKED' if state in ('failed','uncertain') else 'SAVED',
                'invocation_'+state,observation,saved,saved_queue)
        return self._workflow_mutate(actor,'invocation',payload,idempotency_key,lease,execute)

    def complete_research(self,actor,lease,attempt_id,*,commit_references,idempotency_key):
        identifier(attempt_id)
        def execute(connection,current,run_row):
            previous=self._attempt(connection,run_row['data'],attempt_id);attempt=data_of(previous)
            queue_row=self._find(connection,'queue_v1',attempt['queue_id']);queue=data_of(queue_row)
            if attempt['fencing_generation']!=run_row['data']['fencing_generation'] or attempt['state']!='result_saved':raise self.conflict()
            if not self._queue_current(connection,queue):raise self.conflict()
            if not commit_references:raise ValueError('verified_commit_references_required')
            self._references(connection,commit_references)
            result=self._research_result(connection,attempt_id,attempt['result_reference'],published=True)
            if result['data']['publication_reference'] not in commit_references:
                raise ValueError('result_publication_receipt_required')
            attempt['state']='complete';queue.update(status='complete',retry_after='')
            saved=self._save(connection,current,'attempt_v1',attempt_id,attempt,previous=previous)
            saved_queue=self._save(connection,current,'queue_v1',queue['stable_id'],queue,previous=queue_row)
            completion=self._save(connection,current,'completion_v1',attempt_id,{'attempt_id':attempt_id,
                'result_reference':attempt['result_reference'],'commit_references':commit_references,'recorded_at':self.clock().isoformat()})
            return receipt('SAVED','research_complete',saved,saved_queue,completion)
        return self._workflow_mutate(actor,'research_complete',{'attempt_id':attempt_id,'commit_references':commit_references},
            idempotency_key,lease,execute)
