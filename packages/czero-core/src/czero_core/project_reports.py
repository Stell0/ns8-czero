# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded report membership/readback and independent delivery observations."""
from datetime import date,timedelta
from uuid import UUID
from sqlalchemy import text
from .object_schema import bounded_json,validate_record
from .objects import page as paging
from .project_schema import PREFIX,REPORT_MEMBER_INPUT,identifier,timestamp
from .project_monitoring import scope_hash
from .project_workflows import data_of,digest,receipt
from .receipts import snapshot


class ProjectReports:
    def _report_context(self,connection,run,report_type,local_date):
        if report_type not in ('daily','weekly'):raise ValueError('invalid_report_type')
        if run['workflow_type'] not in (report_type,'report_publication'):raise ValueError('invalid_report_workflow')
        if run['workflow_type']==report_type and (run['local_cycle_date']!=local_date or run['current_phase']!='report'):
            raise self.conflict()
        day=date.fromisoformat(local_date)
        if day.isoformat()!=local_date:raise ValueError('invalid_report_date')
        source=self._find(connection,'run_v1',digest([str(self._space_id),report_type,local_date]))['data']
        return source

    def _report_owned(self,connection,run,reference):
        row=self._project_resource(connection,'report_v1',reference);values=row['data']
        source=self._report_context(connection,run,values['report_type'],values['local_date'])
        if (not values['draft_open'] or values['publisher_run_id']!=run['run_id']
                or values['config_version']!=run['config_version'] or values['source_config_version']!=source['config_version']):
            raise self.conflict()
        return row

    def prepare_report(self,actor,lease,report_type,*,local_date='',amend=False,expected_revision=0,idempotency_key):
        if type(amend) is not bool or type(expected_revision) is not int or expected_revision<0:raise ValueError('invalid_report_preparation')
        payload=dict(report_type=report_type,local_date=local_date,amend=amend,expected_revision=expected_revision)
        def execute(connection,current,run_row):
            run=run_row['data'];day=local_date or run['local_cycle_date'];source=self._report_context(connection,run,report_type,day)
            identity=report_type+':'+day;previous=self._find(connection,'report_v1',identity,required=False)
            if previous:
                values=data_of(previous)
                if values['saved_status']=='saved' and not values['draft_open'] and not amend:
                    self._saved_report(connection,previous)
                    return receipt('SAVED','report_already_saved',previous)
                if values['draft_open'] and values['publisher_run_id']!=run['run_id']:
                    other=self._find(connection,'run_v1',values['publisher_run_id'])['data']
                    if (other['state']=='running' and other['lease_expiry'] and timestamp(other['lease_expiry'])>self.clock()
                            and other['config_version']==run['config_version']):raise self.conflict()
                same_context=values['config_version']==run['config_version'] and values['source_config_version']==source['config_version']
                if not amend and values['draft_open'] and same_context:
                    if values['publisher_run_id']==run['run_id']:return receipt('SAVED','report_draft_resumed',previous)
                    values['publisher_run_id']=run['run_id']
                else:
                    if not amend or previous['revision']!=expected_revision:raise self.conflict()
                    values.update(draft_generation=values['draft_generation']+1,draft_open=True,publisher_run_id=run['run_id'],
                        config_version=run['config_version'],source_config_version=source['config_version'],
                        language=self._manifest(connection)['data']['manifest']['language'],cutoff_at=self.clock().isoformat())
            else:
                if amend or expected_revision:raise self.conflict()
                values={'report_id':digest([str(self._space_id),identity]),'project_id':str(self._space_id),'report_type':report_type,
                    'local_date':day,'language':self._manifest(connection)['data']['manifest']['language'],
                    'config_version':run['config_version'],'source_config_version':source['config_version'],'source_run_id':source['run_id'],
                    'publisher_run_id':run['run_id'],'current_version':0,'draft_generation':1,'draft_open':True,
                    'cutoff_at':self.clock().isoformat(),'included_count':0,'deferred_count':0,'inventory_hash':digest([]),
                    'monitoring_expected':0,'monitoring_complete':0,'coverage_complete':False,'wiki_page_id':'','wiki_revision_id':'',
                    'wiki_revision':0,'content_hash':'','saved_status':'draft','saved_at':''}
            saved=self._save(connection,current,'report_v1',identity,values,previous=previous)
            return receipt('SAVED','report_draft_prepared',saved)
        return self._workflow_mutate(actor,'report_prepare',payload,idempotency_key,lease,execute)

    def _report_members(self,connection,reference,generation,*,limit=10001,offset=0):
        return [dict(row) for row in connection.execute(text('''SELECT * FROM c0_objects WHERE space_id=:space
            AND type_name=:type AND data->>'report_reference'=:reference AND (data->>'draft_generation')::int=:generation
            ORDER BY created_at,id LIMIT :limit OFFSET :offset'''),{'space':self._space_id,'type':PREFIX+'report_member_v1',
                'reference':reference,'generation':generation,'limit':limit,'offset':offset}).mappings()]

    def _entry_proof(self,connection,header,data,*,current):
        wiki=self._wiki_receipts(connection,[data['wiki_revision_id']],current=current)[0]
        if self._wiki_project_marker(wiki).get('report_reference')!=str(header['id']):
            raise ValueError('wiki_report_binding_missing')
        body=wiki['body'].encode();start=data['start_byte'];end=data['end_byte']
        if not 0<=start<end<=len(body):raise ValueError('report_entry_range_invalid')
        try:entry=body[start:end].decode('utf-8')
        except UnicodeError:raise ValueError('report_entry_utf8_boundary') from None
        if len(entry.strip())<8:raise ValueError('report_entry_is_not_substantive')
        return wiki,digest(entry)

    def set_report_member(self,actor,lease,report_reference,data,*,expected_revision=0,idempotency_key):
        data=validate_record(REPORT_MEMBER_INPUT,bounded_json(data))
        if type(expected_revision) is not int or expected_revision<0:raise ValueError('invalid_revision')
        payload=dict(report_reference=report_reference,data=data,expected_revision=expected_revision)
        def execute(connection,current,run_row):
            header=self._report_owned(connection,run_row['data'],report_reference);report=header['data']
            result=self._project_resource(connection,'result_v1',data['result_reference'])
            if result['data']['local_date']>report['local_date']:raise ValueError('result_outside_report_cycle')
            if data['disposition']=='included':self._result_ready(connection,result,current=False)
            elif not data['reason'].strip():raise ValueError('report_deferral_reason_required')
            wiki,entry_hash=self._entry_proof(connection,header,data,current=True)
            identity=report['report_id']+':'+str(report['draft_generation'])+':'+data['result_reference']
            previous=self._find(connection,'report_member_v1',identity,required=False)
            if (previous['revision'] if previous else 0)!=expected_revision:raise self.conflict()
            saved=self._save(connection,current,'report_member_v1',identity,{
                'report_reference':report_reference,'report_id':report['report_id'],'report_version':report['current_version']+1,
                'draft_generation':report['draft_generation'],'result_reference':data['result_reference'],
                'result_version':result['data']['content_version'],**{key:value for key,value in data.items() if key!='result_reference'},
                'wiki_hash':wiki['content_hash'],'entry_hash':entry_hash},previous=previous)
            return receipt('SAVED','report_membership_saved',saved)
        return self._workflow_mutate(actor,'report_member',payload,idempotency_key,lease,execute)

    def _unreported_results(self,connection,day):
        maximum=self._manifest(connection)['data']['manifest']['maintenance']['max_inventory']
        rows=[dict(row) for row in connection.execute(text('''SELECT r.* FROM c0_objects r
            WHERE r.space_id=:space AND r.type_name=:result AND r.data->>'state'='published' AND r.data->>'local_date'<=:day
            AND NOT EXISTS(SELECT 1 FROM c0_objects m JOIN c0_objects h ON h.space_id=m.space_id AND h.type_name=:history
                AND h.data->>'report_id'=m.data->>'report_id' AND h.data->>'current_version'=m.data->>'report_version'
                AND h.data->>'draft_generation'=m.data->>'draft_generation'
                AND h.data->>'saved_status'='saved'
                WHERE m.space_id=r.space_id AND m.type_name=:member AND m.data->>'result_reference'=r.id::text
                AND m.data->>'result_version'=r.data->>'content_version' AND m.data->>'disposition'='included')
            ORDER BY r.created_at,r.id LIMIT :limit'''),{'space':self._space_id,'result':PREFIX+'result_v1',
                'history':PREFIX+'report_history_v1','member':PREFIX+'report_member_v1','day':day,'limit':maximum+1}).mappings()]
        if len(rows)>maximum:raise ValueError('report_inventory_incomplete')
        return rows

    def _monitoring_coverage(self,connection,report):
        config=self._find(connection,'config_v1',str(report['source_config_version']))['data']['manifest']
        topics=config['primary_topic_ids'];days=7 if report['report_type']=='weekly' else 1;complete=0
        for offset in range(days):
            day=(date.fromisoformat(report['local_date'])-timedelta(days=offset)).isoformat()
            for topic_id in topics:
                cycle=self._find(connection,'monitor_cycle_v1',digest([str(self._space_id),day,topic_id]),required=False)
                topic=self._find(connection,'topic_v1',topic_id,required=False)
                context=scope_hash(config,topic['data']) if topic else ''
                if (topic and topic['data']['lifecycle']=='active' and topic['data']['classification']=='user'
                        and topic['data']['authorized_by'] and cycle and cycle['data']['scope_hash']==context
                        and cycle['data']['status'] in ('complete','no_material_update') and cycle['data']['successful_watermark']):
                    success=self._find(connection,'monitor_success_v1',cycle['data']['cycle_id']+':'+cycle['data']['scope_hash'],required=False)
                    if success:complete+=1
        expected=len(topics)*days
        return expected,complete,bool(expected and complete==expected and config['monitoring']['enabled'])

    def _saved_report(self,connection,row,version=None):
        values=row['data']
        if version is not None and version!=values['current_version']:
            values=self._find(connection,'report_history_v1',values['report_id']+':'+str(version))['data']
        if values['saved_status']!='saved' or not values['wiki_revision_id']:raise ValueError('report_not_saved')
        wiki=self._wiki_receipts(connection,[values['wiki_revision_id']],current=False)[0]
        if (str(wiki['page_id']),wiki['number'],wiki['content_hash'])!=(values['wiki_page_id'],values['wiki_revision'],values['content_hash']):
            raise ValueError('report_readback_mismatch')
        if self._wiki_project_marker(wiki).get('report_reference')!=str(row['id']):raise ValueError('wiki_report_binding_missing')
        return values

    def finalize_report(self,actor,lease,report_reference,wiki_revision_id,*,idempotency_key):
        def execute(connection,current,run_row):
            previous=self._project_resource(connection,'report_v1',report_reference);report=data_of(previous)
            if not report['draft_open']:
                if report['wiki_revision_id']!=wiki_revision_id:raise self.conflict()
                self._saved_report(connection,previous)
                return receipt('SAVED','report_already_verified',previous)
            self._report_owned(connection,run_row['data'],report_reference)
            wiki=self._wiki_receipts(connection,[wiki_revision_id])[0]
            marker=self._wiki_project_marker(wiki)
            if marker.get('report_reference')!=report_reference or marker.get('language')!=report['language']:
                raise ValueError('report_wiki_binding_or_language_mismatch')
            members=self._report_members(connection,report_reference,report['draft_generation'])
            maximum=self._manifest(connection)['data']['manifest']['maintenance']['max_inventory']
            if len(members)>maximum:raise ValueError('report_membership_inventory_incomplete')
            represented=set();included=0;deferred=0
            for member in members:
                values=member['data'];result=self._project_resource(connection,'result_v1',values['result_reference'])
                if result['data']['content_version']!=values['result_version']:raise self.conflict()
                if values['location']=='main' and values['wiki_revision_id']!=wiki_revision_id:raise ValueError('report_entry_not_in_main_revision')
                entry_wiki,entry_hash=self._entry_proof(connection,previous,values,current=values['location']=='main')
                if values['location']=='appendix':
                    target='page_id='+str(entry_wiki['page_id'])+'&revision='+str(entry_wiki['number'])
                    if target not in wiki['body']:raise ValueError('report_appendix_link_required')
                if entry_hash!=values['entry_hash']:raise self.conflict()
                if values['disposition']=='included':
                    self._result_ready(connection,result,current=False);included+=1
                else:deferred+=1
                represented.add((str(result['id']),result['data']['content_version']))
            pending=self._unreported_results(connection,report['local_date'])
            required={(str(row['id']),row['data']['content_version']) for row in pending}
            if required-represented:raise ValueError('report_missing_completed_results')
            expected,complete,coverage=self._monitoring_coverage(connection,report)
            report.update(current_version=report['current_version']+1,draft_open=False,cutoff_at=self.clock().isoformat(),
                included_count=included,deferred_count=deferred,inventory_hash=digest(sorted(required)),monitoring_expected=expected,
                monitoring_complete=complete,coverage_complete=coverage,wiki_page_id=str(wiki['page_id']),wiki_revision_id=wiki_revision_id,
                wiki_revision=wiki['number'],content_hash=wiki['content_hash'],saved_status='saved',saved_at=self.clock().isoformat())
            saved=self._save(connection,current,'report_v1',report['report_type']+':'+report['local_date'],report,previous=previous)
            history=self._save(connection,current,'report_history_v1',report['report_id']+':'+str(report['current_version']),report)
            self._saved_report(connection,saved)
            return receipt('SAVED','report_saved_and_verified',saved,history)
        return self._workflow_mutate(actor,'report_finalize',{'report_reference':report_reference,'wiki_revision_id':wiki_revision_id},idempotency_key,lease,execute)

    def get_report(self,actor,report_type='daily',*,local_date='',limit=50,offset=0):
        if report_type not in ('daily','weekly'):raise ValueError('invalid_report_type')
        paging(limit,offset)
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor)
            if local_date:
                if date.fromisoformat(local_date).isoformat()!=local_date:raise ValueError('invalid_report_date')
                row=self._find(connection,'report_v1',report_type+':'+local_date,required=False)
            else:
                found=connection.execute(text('''SELECT * FROM c0_objects WHERE space_id=:space AND type_name=:type
                    AND data->>'report_type'=:report AND data->>'saved_status'='saved'
                    ORDER BY data->>'local_date' DESC,id DESC LIMIT 1'''),
                    {'space':self._space_id,'type':PREFIX+'report_v1','report':report_type}).mappings().one_or_none()
                row=dict(found) if found else None
            if row is None:return {'report':None,'members':[],'more':False,'deliveries':[]}
            values=row['data'];generation=values['draft_generation']
            if values['saved_status']=='saved':
                self._saved_report(connection,row)
                generation=self._find(connection,'report_history_v1',values['report_id']+':'+str(values['current_version']))['data']['draft_generation']
            members=self._report_members(connection,str(row['id']),generation,limit=limit+1,offset=offset)
            deliveries=[dict(item) for item in connection.execute(text('''SELECT * FROM c0_objects WHERE space_id=:space
                AND type_name=:type AND data->>'report_reference'=:reference AND (data->>'report_version')::int=:version
                ORDER BY created_at,id LIMIT 3'''),{'space':self._space_id,'type':PREFIX+'report_delivery_v1',
                    'reference':str(row['id']),'version':values['current_version']}).mappings()]
            def public(item):return {key:value for key,value in item.items() if key!='space_id'}
            return snapshot({'report':public(row),'members':[public(member) for member in members[:limit]],
                'more':len(members)>limit,'deliveries':[public(item) for item in deliveries]})

    def observe_report_delivery(self,actor,lease,report_reference,channel,state,*,report_version=None,
            external_reference='',evidence_reference='',observation_source='runner_report',idempotency_key):
        if report_version is not None and (type(report_version) is not int or report_version<1):
            raise ValueError('invalid_report_version')
        if channel not in ('external_result','notification','human_read') or state not in ('started','succeeded','failed','uncertain'):
            raise ValueError('invalid_delivery_observation')
        if observation_source not in ('operator_report','runner_report','sdk_simulation'):raise ValueError('invalid_observation_source')
        if any(type(value) is not str or len(value)>512 for value in (external_reference,evidence_reference)):
            raise ValueError('invalid_delivery_reference')
        payload=dict(report_reference=report_reference,channel=channel,state=state,report_version=report_version,
            external_reference=external_reference,evidence_reference=evidence_reference,observation_source=observation_source)
        def execute(connection,current,run_row):
            run=run_row['data']
            if run['workflow_type']!='report_publication':raise ValueError('delivery_requires_publication_run')
            header=self._project_resource(connection,'report_v1',report_reference);report=self._saved_report(connection,header,report_version)
            identity=report['report_id']+':'+str(report['current_version'])+':'+channel
            previous=self._find(connection,'report_delivery_v1',identity,required=False)
            if state=='started':
                if channel!='external_result':raise ValueError('notifications_and_reading_are_observations_only')
                if previous:
                    old=previous['data']
                    if old['state']=='succeeded':return receipt('SAVED','report_already_published',previous)
                    if old['state'] in ('started','uncertain'):return receipt('BLOCKED','report_publication_requires_reconciliation',previous)
                    if old['attempt_count']>=5:return receipt('BLOCKED','report_publication_retry_exhausted',previous)
                    if old['retry_after'] and timestamp(old['retry_after'])>self.clock():return receipt('BLOCKED','report_publication_retry_deferred',previous)
                attempts=(previous['data']['attempt_count'] if previous else 0)+1
            else:
                if not evidence_reference.strip() or not external_reference.strip():raise ValueError('delivery_observation_requires_evidence')
                if channel=='external_result' and (not previous or previous['data']['state'] not in ('started','uncertain')):
                    if previous and previous['data']['state']=='succeeded' and state=='succeeded' and previous['data']['external_reference']==external_reference:
                        return receipt('SAVED','report_publication_already_observed',previous)
                    raise self.conflict()
                attempts=previous['data']['attempt_count'] if previous else 0
            retry=(self.clock()+timedelta(seconds=min(3600,30*2**max(0,attempts-1)))).isoformat() if state=='failed' else ''
            values={'report_reference':report_reference,'report_version':report['current_version'],'content_hash':report['content_hash'],
                'channel':channel,'state':state,'attempt_count':attempts,'retry_after':retry,'run_id':run['run_id'],
                'fencing_generation':run['fencing_generation'],'external_reference':external_reference,'evidence_reference':evidence_reference,
                'observation_source':observation_source,'recorded_at':self.clock().isoformat(),'actor_id':str(current.user_id)}
            saved=self._save(connection,current,'report_delivery_v1',identity,values,previous=previous)
            history=self._save(connection,current,'report_delivery_history_v1',digest(values),values)
            return receipt('SAVED' if state=='succeeded' else 'BLOCKED' if state in ('failed','uncertain') else 'QUEUED',
                'report_delivery_'+state,saved,history)
        return self._workflow_mutate(actor,'report_delivery',payload,idempotency_key,lease,execute)
