# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded primary monitoring observations, independent of research attempts."""
from datetime import timedelta
from uuid import UUID

from sqlalchemy import text
from .project_schema import PREFIX, identifier, timestamp
from .project_workflows import data_of, digest, receipt


def scope_hash(manifest,topic):
    return digest([manifest[key] for key in ('purpose','scope','exclusions')]+[
        {key:topic[key] for key in ('topic_id','label','classification','originating_question','anchor_ids','authorized_by')}])


def is_new_event(publication_at,event_at,coverage_start,coverage_end):
    """Retrieval/update time alone cannot make an old publication new news."""
    relevant=event_at or publication_at
    return bool(relevant and timestamp(coverage_start)<=timestamp(relevant)<=timestamp(coverage_end))


class ProjectMonitoring:
    def _monitor_context(self,connection,run,topic_id):
        manifest=self._manifest(connection)['data'];config=manifest['manifest']
        if (run['workflow_type']!='daily' or not config['monitoring']['enabled']
                or topic_id not in config['primary_topic_ids']):raise ValueError('not_a_primary_monitoring_cycle')
        topic=self._topic_scope(connection,topic_id)
        if not topic or topic['classification']!='user' or not topic['authorized_by']:
            raise ValueError('primary_monitoring_requires_user_anchor')
        return manifest,topic,scope_hash(config,topic)

    def _monitor_row(self,connection,run,cycle_id):
        row=self._find(connection,'monitor_cycle_v1',cycle_id)
        values=row['data'];_,_,context=self._monitor_context(connection,run,values['topic_id'])
        if values['local_date']!=run['local_cycle_date'] or values['scope_hash']!=context:raise self.conflict()
        return row

    def _monitor_calls(self,connection,cycle_id):
        rows=[dict(row) for row in connection.execute(text('''SELECT * FROM c0_objects
            WHERE space_id=:space AND type_name=:type AND data->>'cycle_id'=:cycle
            ORDER BY created_at,id LIMIT 151'''),{'space':self._space_id,'type':PREFIX+'monitor_call_v1','cycle':cycle_id}).mappings()]
        if len(rows)>150:raise ValueError('monitoring_call_inventory_limit')
        return rows

    def _monitoring_ready(self,connection,run):
        config=self._manifest(connection)['data']['manifest']
        for topic_id in config['primary_topic_ids']:
            _,_,context=self._monitor_context(connection,run,topic_id)
            cycle_id=digest([str(self._space_id),run['local_cycle_date'],topic_id])
            row=self._find(connection,'monitor_cycle_v1',cycle_id,required=False)
            if not row or row['data']['scope_hash']!=context or row['data']['status'] not in ('complete','no_material_update'):
                raise self.conflict()
            if not self._find(connection,'monitor_success_v1',cycle_id+':'+context,required=False):raise self.conflict()

    def monitor_begin(self,actor,lease,topic_id,*,idempotency_key):
        identifier(topic_id)
        def execute(connection,current,run_row):
            run=run_row['data'];manifest,topic,context=self._monitor_context(connection,run,topic_id)
            cycle_id=digest([str(self._space_id),run['local_cycle_date'],topic_id])
            previous=self._find(connection,'monitor_cycle_v1',cycle_id,required=False)
            if previous:
                values=data_of(previous)
                if values['scope_hash']==context:return receipt('SAVED','monitoring_cycle_resumed',previous)
                values.update(scope_hash=context,config_version=manifest['version'],status='partial',
                    successful_watermark='',result_reference='',summary='Scope changed; counters retained and fresh coverage required.')
            else:
                end=timestamp(run['scheduled_for'])
                if end>self.clock():raise ValueError('monitoring_occurrence_not_due')
                previous_success=self._find(connection,'monitor_watermark_v1',topic_id,required=False)
                start=timestamp(previous_success['data']['coverage_end']) if previous_success and previous_success['data']['scope_hash']==context else timestamp(topic['created_at'])
                start-=timedelta(hours=manifest['manifest']['monitoring']['overlap_hours'])
                if start>end:raise ValueError('monitoring_coverage_reversed')
                limits=manifest['manifest']['monitoring']
                values={'cycle_id':cycle_id,'project_id':str(self._space_id),'topic_id':topic_id,'local_date':run['local_cycle_date'],
                    'config_version':manifest['version'],'scope_hash':context,'coverage_start':start.isoformat(),'coverage_end':end.isoformat(),
                    'max_queries':limits['max_queries_per_topic'],'max_sources':limits['max_sources_per_topic'],
                    'queries_used':0,'sources_used':0,'status':'in_progress','result_reference':'','successful_watermark':'','summary':''}
            saved=self._save(connection,current,'monitor_cycle_v1',cycle_id,values,previous=previous)
            return receipt('SAVED','monitoring_cycle_started',saved)
        return self._workflow_mutate(actor,'monitor_begin',{'topic_id':topic_id},idempotency_key,lease,execute)

    def monitor_reserve(self,actor,lease,cycle_id,kind,request_id,request_text,*,replaces_call_id='',idempotency_key):
        identifier(cycle_id);identifier(request_id)
        if kind not in ('query','source') or type(request_text) is not str or not 1<=len(request_text)<=2048:
            raise ValueError('invalid_monitoring_reservation')
        if replaces_call_id:identifier(replaces_call_id)
        payload=dict(cycle_id=cycle_id,kind=kind,request_id=request_id,request_text=request_text,replaces_call_id=replaces_call_id)
        def execute(connection,current,run_row):
            run=run_row['data'];cycle_row=self._monitor_row(connection,run,cycle_id);cycle=data_of(cycle_row)
            call_id=digest([cycle_id,kind,request_id]);previous=self._find(connection,'monitor_call_v1',call_id,required=False)
            if previous:
                call=data_of(previous)
                if (call['request_text'],call['replaces_call_id'],call['scope_hash'])!=(request_text,replaces_call_id,cycle['scope_hash']):raise self.conflict()
                if call['fencing_generation']!=run['fencing_generation']:
                    if call['state']=='started':call['state']='uncertain'
                    call['fencing_generation']=run['fencing_generation']
                    previous=self._save(connection,current,'monitor_call_v1',call_id,call,previous=previous)
                    self._save(connection,current,'monitor_call_history_v1',digest(call),call)
                return receipt('BLOCKED' if call['state']=='uncertain' else 'SAVED','monitoring_reservation_resumed',previous,cycle_row)
            if cycle['status'] in ('complete','no_material_update','awaiting_merge'):raise self.conflict()
            calls=self._monitor_calls(connection,cycle_id)
            if replaces_call_id:
                replaced=self._find(connection,'monitor_call_v1',replaces_call_id)['data']
                if (replaced['cycle_id'],replaced['kind'],replaced['request_text'],replaced['scope_hash'])!=(cycle_id,kind,request_text,cycle['scope_hash']) or replaced['state'] not in ('failed','uncertain'):
                    raise ValueError('monitoring_retry_must_cover_failed_request')
            if kind=='source' and not any(request_text in call['data']['selected_sources'] for call in calls
                    if call['data']['kind']=='query' and call['data']['state']=='succeeded' and call['data']['scope_hash']==cycle['scope_hash']):
                raise ValueError('source_not_selected_by_observed_query')
            used='queries_used' if kind=='query' else 'sources_used';maximum='max_queries' if kind=='query' else 'max_sources'
            if cycle[used]>=cycle[maximum]:return receipt('BLOCKED','monitoring_resource_cap',cycle_row)
            cycle[used]+=1;cycle.update(status='in_progress',summary='')
            saved_cycle=self._save(connection,current,'monitor_cycle_v1',cycle_id,cycle,previous=cycle_row)
            saved=self._save(connection,current,'monitor_call_v1',call_id,{'call_id':call_id,'cycle_id':cycle_id,'kind':kind,
                'ordinal':cycle[used],'scope_hash':cycle['scope_hash'],'request_text':request_text,'run_id':run['run_id'],
                'fencing_generation':run['fencing_generation'],'state':'reserved','external_reference':'','selected_sources':[],
                'version_id':'','citation_ids':[],'replaces_call_id':replaces_call_id,'summary':'',
                'reserved_at':self.clock().isoformat(),'recorded_at':self.clock().isoformat()})
            history=self._save(connection,current,'monitor_call_history_v1',digest(data_of(saved)),data_of(saved))
            return receipt('SAVED','monitoring_call_reserved',saved,saved_cycle,history)
        return self._workflow_mutate(actor,'monitor_reserve',payload,idempotency_key,lease,execute)

    def monitor_observe(self,actor,lease,call_id,state,*,external_reference='',selected_sources=None,
                        version_id='',citation_ids=None,summary='',idempotency_key):
        identifier(call_id);selected_sources=[] if selected_sources is None else selected_sources
        citation_ids=[] if citation_ids is None else citation_ids
        if state not in ('started','succeeded','failed','uncertain'):raise ValueError('invalid_monitoring_outcome')
        if type(summary) is not str or len(summary)>2048 or type(external_reference) is not str or len(external_reference)>512:
            raise ValueError('invalid_monitoring_observation')
        if type(selected_sources) is not list or len(selected_sources)>100 or any(type(s) is not str or not 1<=len(s)<=512 for s in selected_sources) or len(set(selected_sources))!=len(selected_sources):
            raise ValueError('invalid_selected_monitoring_sources')
        payload=dict(call_id=call_id,state=state,external_reference=external_reference,selected_sources=selected_sources,
            version_id=version_id,citation_ids=citation_ids,summary=summary)
        def execute(connection,current,run_row):
            run=run_row['data'];previous=self._find(connection,'monitor_call_v1',call_id);call=data_of(previous)
            cycle=self._monitor_row(connection,run,call['cycle_id'])['data']
            if call['fencing_generation']!=run['fencing_generation'] or call['scope_hash']!=cycle['scope_hash']:raise self.conflict()
            allowed=('reserved',) if state=='started' else ('started','uncertain') if state=='succeeded' else ('reserved','started','uncertain')
            if call['state'] not in allowed:raise self.conflict()
            if state=='succeeded':
                if not external_reference.strip() or not summary.strip():raise ValueError('observed_result_reference_required')
                if call['kind']=='source':
                    if selected_sources or not version_id or not citation_ids:raise ValueError('inspection_requires_immutable_passages')
                    UUID(version_id);self._references(connection,citation_ids)
                    for chunk in citation_ids:
                        found=connection.execute(text('''SELECT 1 FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id AND d.space_id=c.space_id
                            JOIN c0_source_versions v ON v.id=d.version_id AND v.space_id=d.space_id JOIN c0_sources s ON s.id=v.source_id AND s.space_id=v.space_id
                            WHERE c.space_id=:space AND c.id=CAST(:chunk AS uuid) AND v.id=CAST(:version AS uuid) AND v.state='ready' AND NOT s.deleted'''),
                            {'space':self._space_id,'chunk':chunk,'version':version_id}).scalar_one_or_none()
                        if found is None:raise ValueError('monitoring_passage_version_mismatch')
                elif version_id or citation_ids:raise ValueError('query_is_not_source_inspection')
            elif selected_sources or version_id or citation_ids:raise ValueError('unverified_monitoring_evidence')
            call.update(state=state,external_reference=external_reference,selected_sources=selected_sources,
                version_id=version_id,citation_ids=citation_ids,summary=summary,recorded_at=self.clock().isoformat())
            saved=self._save(connection,current,'monitor_call_v1',call_id,call,previous=previous)
            history=self._save(connection,current,'monitor_call_history_v1',digest(call),call)
            return receipt('BLOCKED' if state in ('failed','uncertain') else 'SAVED','monitoring_outcome_'+state,saved,history)
        return self._workflow_mutate(actor,'monitor_observe',payload,idempotency_key,lease,execute)

    def _monitor_material_ready(self,connection,cycle,result_reference):
        # Evidence/result publication adds its stronger domain check in M5.
        return False

    def monitor_finish(self,actor,lease,cycle_id,status,*,summary,result_reference='',idempotency_key):
        identifier(cycle_id)
        if status not in ('complete','no_material_update','partial','blocked') or type(summary) is not str or not 1<=len(summary)<=4096:
            raise ValueError('invalid_monitoring_completion')
        payload=dict(cycle_id=cycle_id,status=status,summary=summary,result_reference=result_reference)
        def execute(connection,current,run_row):
            run=run_row['data'];previous=self._monitor_row(connection,run,cycle_id);cycle=data_of(previous)
            if result_reference:self._references(connection,[result_reference],ready=status in ('complete','no_material_update'))
            if cycle['status'] in ('complete','no_material_update'):return receipt('SAVED','monitoring_already_complete',previous)
            calls=[row['data'] for row in self._monitor_calls(connection,cycle_id) if row['data']['scope_hash']==cycle['scope_hash']]
            queries=[call for call in calls if call['kind']=='query'];sources=[call for call in calls if call['kind']=='source']
            if status in ('complete','no_material_update'):
                recovered={call['replaces_call_id'] for call in calls if call['state']=='succeeded' and call['replaces_call_id']}
                if not any(call['state']=='succeeded' for call in queries) or any(call['state']!='succeeded' and call['call_id'] not in recovered for call in calls):
                    raise ValueError('monitoring_has_unresolved_or_failed_checks')
                selected={locator for call in queries if call['state']=='succeeded' for locator in call['selected_sources']}
                inspected={call['request_text'] for call in sources if call['state']=='succeeded'}
                if selected-inspected:raise ValueError('monitoring_has_uninspected_selected_sources')
                if status=='complete':
                    if not sources or not result_reference:raise ValueError('material_monitoring_requires_stored_result')
                    self._references(connection,[result_reference])
                    if not self._monitor_material_ready(connection,cycle,result_reference):status_value='awaiting_merge'
                    else:status_value='complete'
                else:
                    if result_reference:raise ValueError('no_material_update_has_no_material_result')
                    status_value=status
            else:status_value=status
            cycle.update(status=status_value,summary=summary,result_reference=result_reference)
            success=None;watermark=None
            if status_value in ('complete','no_material_update'):
                cycle['successful_watermark']=cycle['coverage_end']
                identity=cycle_id+':'+cycle['scope_hash'];success=self._find(connection,'monitor_success_v1',identity,required=False)
                if success is None:success=self._save(connection,current,'monitor_success_v1',identity,{
                    'cycle_id':cycle_id,'scope_hash':cycle['scope_hash'],'coverage_start':cycle['coverage_start'],'coverage_end':cycle['coverage_end'],
                    'query_ids':[call['call_id'] for call in queries],'source_ids':[call['call_id'] for call in sources],
                    'result_reference':result_reference,'verified_at':self.clock().isoformat()})
                watermark=self._find(connection,'monitor_watermark_v1',cycle['topic_id'],required=False)
                if not watermark or watermark['data']['scope_hash']!=cycle['scope_hash'] or timestamp(watermark['data']['coverage_end'])<=timestamp(cycle['coverage_end']):
                    watermark=self._save(connection,current,'monitor_watermark_v1',cycle['topic_id'],{
                        'topic_id':cycle['topic_id'],'scope_hash':cycle['scope_hash'],'cycle_id':cycle_id,'coverage_end':cycle['coverage_end']},previous=watermark)
            else:cycle['successful_watermark']=''
            saved=self._save(connection,current,'monitor_cycle_v1',cycle_id,cycle,previous=previous)
            return receipt('ACCEPTED_PENDING_MERGE' if status_value=='awaiting_merge' else 'SAVED' if success else 'PARTIAL' if status_value=='partial' else 'BLOCKED',
                'monitoring_'+status_value,saved,success,watermark)
        return self._workflow_mutate(actor,'monitor_finish',payload,idempotency_key,lease,execute)
