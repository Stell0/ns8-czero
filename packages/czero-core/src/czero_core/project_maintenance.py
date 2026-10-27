# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Small bounded maintenance transactions over existing protected knowledge."""
from datetime import timedelta
import hashlib
import re
from urllib.parse import urlsplit,parse_qs
from uuid import UUID
from sqlalchemy import text
from .identity import Role
from .object_schema import validate_record,bounded_json
from .project_schema import PREFIX,SEMANTIC_INPUT,normalize_manifest,timestamp
from .project_workflows import data_of,digest,receipt
from .receipts import snapshot
from .annotations import AnnotationService,ContentTarget
from .project_schedules import schedule_contract
from .project_monitoring import scope_hash

AUDIT_KINDS=('configuration','wiki','claims','documents','chunks','queue','topics','sources')


class ProjectMaintenance:
    def _maintenance_run(self,run):
        if run['workflow_type'] not in ('weekly','maintenance'):raise ValueError('maintenance_workflow_required')

    def _weekly_phase_ready(self,connection,run,phase,references):
        kinds={'configuration':('configuration',),'references':('wiki','claims','documents','chunks','sources'),
            'queue':('queue','topics')}.get(phase,())
        for kind in kinds:
            audit=self._find(connection,'audit_v1',run['run_id']+':'+str(run['config_version'])+':'+kind)
            if audit['data']['state']!='complete' or str(audit['id']) not in references:
                raise ValueError('weekly_structural_receipt_required')
        if phase=='semantic':
            review=self._find(connection,'semantic_round_v1',run['run_id']+':'+str(run['config_version']))
            if review['data']['state']!='complete' or str(review['id']) not in references:
                raise ValueError('weekly_semantic_batch_incomplete')
        if phase=='archive':
            pending=connection.execute(text('''SELECT count(*) FROM c0_objects WHERE space_id=:space AND type_name=:type
                AND data->>'classification'='peripheral' AND data->>'lifecycle' NOT IN ('archived','retired')
                AND (data->>'expires_at')::timestamptz<=:started AND (data->>'created_at')::timestamptz<:started'''),
                {'space':self._space_id,'type':PREFIX+'topic_v1','now':self.clock(),'started':timestamp(run['started_at'])}).scalar_one()
            if pending:raise ValueError('weekly_peripheral_archives_pending')

    def _audit_rows(self,connection,kind,after,limit):
        if after:UUID(after)
        tables={'claims':'c0_claims','documents':'c0_documents','chunks':'c0_chunks','sources':'c0_source_versions',
            'queue':'c0_objects','topics':'c0_objects','wiki':'c0_wiki_pages'}
        where='r.space_id=:space';params={'space':self._space_id,'limit':limit,'after':after}
        if after:where+=' AND r.id>CAST(:after AS uuid)'
        if kind in ('queue','topics'):
            where+=' AND r.type_name=:type';params['type']=PREFIX+('queue_v1' if kind=='queue' else 'topic_v1')
        if kind in ('wiki','claims'):where+=' AND NOT r.deleted'
        # Only fixed trusted tables appear in SQL; requests cannot choose SQL.
        columns='r.id,r.version_id,r.text_hash' if kind=='documents' else 'r.*'
        return [dict(row) for row in connection.execute(text('SELECT '+columns+' FROM '+tables[kind]+
            ' r WHERE '+where+' ORDER BY r.id LIMIT :limit'),params).mappings()]

    def _wiki_issues(self,connection,row):
        from .project_evidence import clean_markdown
        revision=connection.execute(text('SELECT * FROM c0_wiki_revisions WHERE space_id=:space AND page_id=:id AND number=:number'),
            {'space':self._space_id,'id':row['id'],'number':row['revision']}).mappings().one()
        issues=[]
        try:clean_markdown(revision['body'])
        except ValueError:issues.append(('wiki_body_envelope','Serialized page metadata appears in Markdown.'))
        if hashlib.sha256(revision['body'].encode()).hexdigest()!=revision['content_hash']:
            issues.append(('wiki_hash_mismatch','Stored Wiki body does not match its immutable hash.'))
        targets=[]
        for match in re.finditer(r'\[([^\]\n]+)\]\(([^\s)]+)\)|\[\[([^\]\n]+)\]\]',revision['body']):
            if match[3]:targets.append(('slug',match[3]));continue
            parsed=urlsplit(match[2])
            if parsed.scheme or parsed.netloc or parsed.path.strip('./')!='wiki':continue
            query=parse_qs(parsed.query)
            if query.get('space_id',[str(self._space_id)])[0]!=str(self._space_id):
                issues.append(('cross_space_link','Cross-space link is not inspected or implicitly authorized.'));continue
            if query.get('page_id'):targets.append(('id',query['page_id'][0]))
            elif query.get('slug'):targets.append(('slug',query['slug'][0]))
        if len(targets)>32:issues.append(('link_coverage_partial','More than32 canonical links; remaining links require review.'))
        for kind,value in targets[:32]:
            if kind=='id':
                try:UUID(value)
                except ValueError:issues.append(('broken_wiki_link','Malformed local page identity.'));continue
            sql='SELECT deleted FROM c0_wiki_pages WHERE space_id=:space AND '+('id=CAST(:value AS uuid)' if kind=='id' else 'slug=:value')
            target=connection.execute(text(sql),{'space':self._space_id,'value':value}).scalar_one_or_none()
            if target is None:issues.append(('broken_wiki_link','Missing canonical local Wiki target: '+value))
        inbound=connection.execute(text('''SELECT EXISTS(SELECT 1 FROM c0_wiki_revisions v JOIN c0_wiki_pages p
            ON p.id=v.page_id AND p.space_id=v.space_id AND p.revision=v.number WHERE p.space_id=:space
            AND NOT p.deleted AND p.id<>:id AND (strpos(v.body,:uuid)>0 OR strpos(v.body,:slug)>0))'''),
            {'space':self._space_id,'id':row['id'],'uuid':'page_id='+str(row['id']),'slug':'[['+row['slug']+']]'}).scalar_one()
        if not inbound:issues.append(('possible_orphan','No inbound canonical Markdown link found; graph/semantic context may still connect this page.'))
        return issues

    def _audit_issues(self,connection,kind,row):
        if kind=='wiki':return self._wiki_issues(connection,row)
        if kind in ('documents','chunks'):
            body=(connection.execute(text('SELECT body FROM c0_documents WHERE space_id=:space AND id=:id'),
                {'space':self._space_id,'id':row['id']}).scalar_one() if kind=='documents' else row['body'])
            expected=row['text_hash'] if kind=='documents' else row['content_hash']
            issues=[] if hashlib.sha256(body.encode()).hexdigest()==expected else [('evidence_hash_mismatch','Immutable evidence hash mismatch.')]
            if kind=='documents':
                count=connection.execute(text('SELECT count(*) FROM c0_chunks WHERE space_id=:space AND document_id=:id'),
                    {'space':self._space_id,'id':row['id']}).scalar_one()
                if not count:issues.append(('evidence_passages_missing','Extracted document has no immutable passages.'))
            else:
                original=connection.execute(text('SELECT body FROM c0_documents WHERE space_id=:space AND id=:id'),
                    {'space':self._space_id,'id':row['document_id']}).scalar_one_or_none()
                if original is None or original[row['start_offset']:row['end_offset']]!=body:
                    issues.append(('evidence_offsets_mismatch','Passage does not match its original document offsets.'))
            return issues
        if kind=='sources':
            return [('source_processing_'+row['state'],'Source extraction is incomplete; it is not ready evidence.')] if row['state']!='ready' else []
        if kind=='claims':
            issues=[]
            links=connection.execute(text('SELECT chunk_id FROM c0_evidence_links WHERE space_id=:space AND claim_id=:id'),
                {'space':self._space_id,'id':row['id']}).scalars().all()
            try:self._citations(connection,[str(value) for value in links])
            except ValueError:issues.append(('claim_evidence_gap','Claim evidence is missing or not ready.'))
            if not links:issues.append(('claim_evidence_gap','Claim has no supporting passage.'))
            if row['valid_to'] and row['valid_to']<self.clock():issues.append(('outdated_claim','Claim validity window has ended; reassessment is external.'))
            if row['metadata'].get('status') in ('disputed','contradicted','outdated'):
                issues.append(('claim_review_required','Recorded claim status requires semantic review.'))
            annotations=AnnotationService(self.database,self.access).in_space(self._space_id)
            for namespace in ('verification','applicability'):
                status=annotations._entry(connection,ContentTarget('claim',row['id'],row['revision']),namespace)['status']
                if status in ('disputed','contradicted','outdated','not_applicable','superseded'):
                    issues.append(('claim_review_required','Current-revision '+namespace+' annotation requires review: '+status))
            return issues
        values=row['data']
        if kind=='topics':
            if values['classification']=='peripheral' and values['lifecycle'] not in ('archived','retired') and timestamp(values['expires_at'])<=self.clock():
                return [('peripheral_archive_due','Peripheral topic awaits a distinct future weekly archive checkpoint.')]
            return []
        issues=[]
        found=self._find(connection,'queue_v1',values['stable_id'],required=False)
        if not found or found['id']!=row['id']:issues.append(('queue_identity_mismatch','Stored stable identity/key mismatch.'))
        for parent in values['parent_ids']:
            original=self._find(connection,'queue_v1',parent,required=False)
            if not original:issues.append(('queue_lineage_gap','Missing causal parent: '+parent))
            elif values['expansion_priority']<original['data']['expansion_priority']:
                issues.append(('queue_depth_mismatch','Causal depth was reduced.'))
        if values['status'] in ('deferred','retry_wait','blocked','awaiting_merge'):
            issues.append(('research_'+values['status'],'Research remains visible and incomplete: '+values['defer_reason']))
        if values['status']=='in_progress' and values['last_attempt_id']:
            attempt=self._find(connection,'attempt_v1',values['last_attempt_id'],required=False)
            run=self._find(connection,'run_v1',attempt['data']['run_id'],required=False) if attempt else None
            if not attempt or not run:issues.append(('research_receipt_gap','Active research has a missing attempt/run receipt.'))
            elif not run['data']['lease_expiry'] or timestamp(run['data']['lease_expiry'])<=self.clock():
                issues.append(('research_recovery_required','Lease expired; reconcile invocation/result before another external call.'))
        return issues

    def audit_step(self,actor,lease,kind,*,limit=10,idempotency_key):
        if kind not in AUDIT_KINDS or type(limit) is not int or not 1<=limit<=10:raise ValueError('invalid_audit_step')
        def execute(connection,current,run_row):
            run=run_row['data'];self._maintenance_run(run);identity=run['run_id']+':'+str(run['config_version'])+':'+kind
            previous=self._find(connection,'audit_v1',identity,required=False);cursor=self._find(connection,'audit_cursor_v1',kind,required=False)
            values=data_of(previous) if previous else {'run_id':run['run_id'],'config_version':run['config_version'],'kind':kind,
                'cursor':cursor['data']['after_id'] if cursor else '','cursor_revision':cursor['revision'] if cursor else 0,'scanned':0,'finding_count':0,'state':'partial',
                'limitations':['Structural checks only; external URLs and semantic truth are not audited.'],'updated_at':self.clock().isoformat()}
            if previous and values['state']=='complete':return receipt('SAVED','audit_slice_already_saved',previous)
            maximum=self._manifest(connection)['data']['manifest']['maintenance']['max_inventory']
            remaining=maximum-values['scanned']
            if remaining<=0:return receipt('PARTIAL','audit_inventory_bound_reached',previous)
            rows=[];issues=[]
            if kind=='configuration':
                manifest=self._manifest(connection);normalize_manifest(manifest['data']['manifest']);rows=[{'id':manifest['id']}]
                for connector_id in manifest['data']['manifest']['connector_ids']:
                    connector=self._find(connection,'connector_v1',connector_id,required=False)
                    if not connector:issues.append((str(manifest['id']),'missing_connector','Missing configured connector: '+connector_id))
                    else:
                        sync=self._find(connection,'connector_sync_v1',connector_id,required=False)
                        if sync and sync['data']['definition_hash']!=connector['data']['definition_hash']:
                            issues.append((str(manifest['id']),'connector_definition_changed','Previous synchronization does not cover connector '+connector_id+'.'))
                config=manifest['data']['manifest'];due=timestamp(schedule_contract(config,self.clock())['occurrences']['daily']['latest_due'])
                for topic_id in config['primary_topic_ids']:
                    topic=self._find(connection,'topic_v1',topic_id,required=False)
                    watermark=self._find(connection,'monitor_watermark_v1',topic_id,required=False)
                    if not topic or (timestamp(topic['data']['created_at'])<=due and (not watermark
                            or watermark['data']['scope_hash']!=scope_hash(config,topic['data'])
                            or timestamp(watermark['data']['coverage_end'])<due)):
                        issues.append((str(manifest['id']),'monitoring_gap','Current approved primary-topic coverage is incomplete: '+topic_id))
                more=False
            else:
                fetched=self._audit_rows(connection,kind,values['cursor'],min(limit,remaining)+1);rows=fetched[:min(limit,remaining)];more=len(fetched)>len(rows)
                for row in rows:
                    for code,detail in self._audit_issues(connection,kind,row):issues.append((str(row['id']),code,detail))
            if cursor and cursor['data']['after_id'] and not previous:
                values['limitations'].append('Resumed structural rotation; this slice is not a complete current snapshot.')
            values.update(cursor=str(rows[-1]['id']) if rows and kind!='configuration' else values['cursor'],
                scanned=values['scanned']+len(rows),state='partial' if more else 'complete',updated_at=self.clock().isoformat())
            # One grouped finding per resource keeps this trusted transaction <=23 writes.
            grouped={}
            for resource,code,detail in issues:grouped.setdefault(resource,[]).append((code,detail))
            if len(grouped)>10:raise ValueError('configuration_audit_requires_bounded_review')
            values['finding_count']+=len(grouped)
            if kind!='configuration':
                if values['cursor_revision']==(cursor['revision'] if cursor else 0):
                    advanced=self._save(connection,current,'audit_cursor_v1',kind,{'kind':kind,
                        'after_id':values['cursor'] if more else '', 'rounds':(cursor['data']['rounds'] if cursor else 0)+(0 if more else 1)},previous=cursor)
                    values['cursor_revision']=advanced['revision']
                elif 'Concurrent cursor progress preserved.' not in values['limitations']:
                    values['limitations'].append('Concurrent cursor progress preserved.')
            saved=self._save(connection,current,'audit_v1',identity,values,previous=previous);proofs=[]
            for row in rows:
                resource=str(row['id']);observation_key=kind+':'+resource
                observed=self._find(connection,'audit_observation_v1',observation_key,required=False)
                self._save(connection,current,'audit_observation_v1',observation_key,{'kind':kind,'resource_id':resource,
                    'audit_reference':str(saved['id']),'issue_count':len(grouped.get(resource,[])),
                    'checked_at':self.clock().isoformat()},previous=observed)
            for resource,findings in grouped.items():
                detail='; '.join(code+': '+description for code,description in findings)
                if len(detail)>2048:detail=detail[:1980]+'; additional findings omitted: review this resource.'
                proofs.append(self._save(connection,current,'audit_finding_v1',identity+':'+resource,{
                    'audit_reference':str(saved['id']),'resource_id':resource,'kind':findings[0][0],'detail':detail,
                    'reference_ids':[],'recorded_at':self.clock().isoformat()}))
            return receipt('PARTIAL' if more else 'SAVED','structural_audit_slice_saved',saved,*proofs)
        return self._workflow_mutate(actor,'audit_step',{'kind':kind,'limit':limit},idempotency_key,lease,execute)

    def semantic_select(self,actor,lease,*,refresh_changed=False,idempotency_key):
        if type(refresh_changed) is not bool:raise ValueError('invalid_semantic_refresh')
        def execute(connection,current,run_row):
            run=run_row['data'];self._maintenance_run(run);identity=run['run_id']+':'+str(run['config_version'])
            previous=self._find(connection,'semantic_round_v1',identity,required=False)
            if previous:
                changed=False
                if refresh_changed:
                    for reference in previous['data']['selected_ids']:
                        selected=self._project_resource(connection,'semantic_selection_v1',reference);values=data_of(selected)
                        current_page=connection.execute(text('''SELECT r.id,r.number,r.content_hash FROM c0_wiki_revisions r
                            JOIN c0_wiki_pages p ON p.id=r.page_id AND p.space_id=r.space_id AND p.revision=r.number
                            WHERE p.space_id=:space AND p.id=CAST(:id AS uuid) AND NOT p.deleted'''),
                            {'space':self._space_id,'id':values['page_id']}).mappings().one_or_none()
                        if current_page and str(current_page['id'])!=values['wiki_revision_id']:
                            history_key=reference+':'+str(selected['revision'])
                            if not self._find(connection,'semantic_selection_history_v1',history_key,required=False):
                                self._save(connection,current,'semantic_selection_history_v1',history_key,values)
                            values.update(wiki_revision_id=str(current_page['id']),wiki_revision=current_page['number'],
                                content_hash=current_page['content_hash'],state='pending')
                            self._save(connection,current,'semantic_selection_v1',identity+':'+values['page_id'],values,previous=selected);changed=True
                    if changed:
                        values=data_of(previous);values.update(state='partial',semantic_coverage_complete=False)
                        previous=self._save(connection,current,'semantic_round_v1',identity,values,previous=previous)
                return receipt('SAVED' if previous['data']['state']=='complete' else 'PARTIAL','semantic_selection_resumed',previous)
            config=self._manifest(connection)['data']['manifest'];limit=config['maintenance']['semantic_pages_per_week']
            cursor=self._find(connection,'semantic_cursor_v1','wiki',required=False);after=cursor['data']['last_page_id'] if cursor else ''
            params={'space':self._space_id,'limit':limit,'after':after}
            count=connection.execute(text('SELECT count(*) FROM c0_wiki_pages WHERE space_id=:space AND NOT deleted'),params).scalar_one()
            base='''SELECT p.id AS page_id,p.revision,r.id AS wiki_revision_id,r.content_hash FROM c0_wiki_pages p
                JOIN c0_wiki_revisions r ON r.page_id=p.id AND r.space_id=p.space_id AND r.number=p.revision
                WHERE p.space_id=:space AND NOT p.deleted'''
            ordered=' ORDER BY p.id LIMIT :limit'
            rows=list(connection.execute(text(base+(' AND p.id>CAST(:after AS uuid)' if after else '')+ordered),{**params,'limit':1}).mappings())
            if not rows and after:rows=list(connection.execute(text(base+ordered),{**params,'limit':1}).mappings())
            rotating=str(rows[0]['page_id']) if rows else after
            if rows and limit>1:
                ranked=base+''' AND p.id<>CAST(:rotate AS uuid) ORDER BY CASE WHEN EXISTS(SELECT 1 FROM c0_claims c
                    WHERE c.space_id=p.space_id AND c.page_id=p.id AND NOT c.deleted AND
                    (c.metadata->>'status' IN ('disputed','contradicted','outdated') OR c.metadata->>'consequential'='true'
                    OR c.valid_to<:now OR EXISTS(SELECT 1 FROM c0_annotation_targets t JOIN c0_annotations a
                        ON a.space_id=t.space_id AND a.anchor_id=t.id JOIN c0_annotation_revisions ar
                        ON ar.space_id=a.space_id AND ar.annotation_id=a.id AND ar.number=a.revision
                        WHERE t.space_id=c.space_id AND t.claim_id=c.id AND t.content_revision=c.revision
                        AND ar.value->>'status' IN ('disputed','contradicted','outdated','not_applicable','superseded'))))
                    THEN 1 ELSE 0 END DESC,p.updated_at DESC,p.id LIMIT :limit'''
                rows+=list(connection.execute(text(ranked),{**params,'rotate':rotating,'limit':limit-1,'now':self.clock()}).mappings())
            selections=[]
            for row in rows:
                selections.append(self._save(connection,current,'semantic_selection_v1',identity+':'+str(row['page_id']),{
                    'round_id':digest(identity),'page_id':str(row['page_id']),'wiki_revision_id':str(row['wiki_revision_id']),
                    'wiki_revision':row['revision'],'content_hash':row['content_hash'],'state':'pending'}))
            saved=self._save(connection,current,'semantic_round_v1',identity,{'run_id':run['run_id'],
                'config_version':run['config_version'],'selected_ids':[str(row['id']) for row in selections],
                'inventory_total':count,'inventory_complete':count<=config['maintenance']['max_inventory'],
                'semantic_coverage_complete':count==0,'limit':limit,'state':'partial' if rows else 'complete',
                'cursor_before':after,'cursor_after':rotating,'cursor_rounds':cursor['data']['rounds'] if cursor else 0})
            return receipt('PARTIAL' if rows else 'SAVED','semantic_selection_saved',saved)
        return self._workflow_mutate(actor,'semantic_select',{'refresh_changed':refresh_changed},idempotency_key,lease,execute)

    def semantic_review(self,actor,lease,selection_reference,data,*,idempotency_key):
        data=validate_record(SEMANTIC_INPUT,bounded_json(data))
        def execute(connection,current,run_row):
            run=run_row['data'];self._maintenance_run(run);identity=run['run_id']+':'+str(run['config_version'])
            round_row=self._find(connection,'semantic_round_v1',identity);round_values=data_of(round_row)
            if selection_reference not in round_values['selected_ids']:raise ValueError('semantic_selection_mismatch')
            selected=self._project_resource(connection,'semantic_selection_v1',selection_reference);values=data_of(selected)
            wiki=self._wiki_receipts(connection,[values['wiki_revision_id']])[0]
            if wiki['content_hash']!=values['content_hash']:raise self.conflict()
            self._citations(connection,data['citation_ids'])
            if values['state']=='reviewed':raise ValueError('semantic_review_already_complete')
            review=self._save(connection,current,'semantic_review_v1',selection_reference+':'+digest(data),{
                'selection_reference':selection_reference,'wiki_revision_id':values['wiki_revision_id'],
                'content_hash':values['content_hash'],**data,'actor_id':str(current.user_id),'recorded_at':self.clock().isoformat()})
            values['state']=data['status'];saved=self._save(connection,current,'semantic_selection_v1',identity+':'+values['page_id'],values,previous=selected)
            all_reviewed=all(self._project_resource(connection,'semantic_selection_v1',ref)['data']['state']=='reviewed' for ref in round_values['selected_ids'])
            if all_reviewed:
                round_values.update(state='complete',semantic_coverage_complete=round_values['inventory_complete']
                    and len(round_values['selected_ids'])==round_values['inventory_total'])
                cursor=self._find(connection,'semantic_cursor_v1','wiki',required=False)
                if round_values['cursor_rounds']==(cursor['data']['rounds'] if cursor else 0):
                    self._save(connection,current,'semantic_cursor_v1','wiki',{'last_page_id':round_values['cursor_after'],
                        'rounds':(cursor['data']['rounds'] if cursor else 0)+1},previous=cursor)
                else:round_values['cursor_after']=cursor['data']['last_page_id']
                round_row=self._save(connection,current,'semantic_round_v1',identity,round_values,previous=round_row)
            return receipt('SAVED' if data['status']=='reviewed' else 'PARTIAL','semantic_review_saved',saved,review,round_row)
        return self._workflow_mutate(actor,'semantic_review',{'selection_reference':selection_reference,'data':data},idempotency_key,lease,execute)

    def archive_peripheral(self,actor,lease,topic_id,summary,assessment_ref,*,reference_ids=None,idempotency_key):
        if type(summary) is not str or not 8<=len(summary.strip())<=4096 or type(assessment_ref) is not str or not 1<=len(assessment_ref)<=512:
            raise ValueError('archive_summary_and_assessment_required')
        reference_ids=[] if reference_ids is None else reference_ids
        def execute(connection,current,run_row):
            run=run_row['data']
            if run['workflow_type']!='weekly':raise ValueError('weekly_archive_checkpoint_required')
            topic=self._find(connection,'topic_v1',topic_id);values=data_of(topic)
            previous=self._find(connection,'archive_v1',topic_id,required=False)
            if previous:return receipt('SAVED','topic_already_archived',previous,topic)
            if (values['classification']!='peripheral' or values['lifecycle'] in ('archived','retired')
                    or timestamp(values['expires_at'])>timestamp(run['started_at'])
                    or timestamp(run['started_at'])<=timestamp(values['created_at'])):
                raise ValueError('distinct_future_weekly_checkpoint_required')
            self._references(connection,reference_ids,ready=True)
            if not self._find(connection,'topic_history_v1',topic_id+':'+str(topic['revision']),required=False):
                self._save(connection,current,'topic_history_v1',topic_id+':'+str(topic['revision']),{
                    'topic_id':topic_id,'version':topic['revision'],'topic':topic['data'],'actor_id':str(current.user_id),
                    'recorded_at':self.clock().isoformat(),'observation':'upgrade_snapshot'})
            capsule=self._save(connection,current,'archive_v1',topic_id,{'run_id':run['run_id'],'topic_id':topic_id,
                'topic_snapshot':topic['data'],'summary':summary,'assessment_ref':assessment_ref,
                'reference_ids':reference_ids,'archived_at':self.clock().isoformat()})
            values['lifecycle']='archived';saved=self._save(connection,current,'topic_v1',topic_id,values,previous=topic)
            self._save(connection,current,'topic_history_v1',topic_id+':'+str(saved['revision']),{
                'topic_id':topic_id,'version':saved['revision'],'topic':saved['data'],'actor_id':str(current.user_id),
                'recorded_at':self.clock().isoformat(),'observation':'changed'})
            return receipt('SAVED','peripheral_topic_archived_with_history',saved,capsule)
        return self._workflow_mutate(actor,'archive_peripheral',{'topic_id':topic_id,'summary':summary,'assessment_ref':assessment_ref,
            'reference_ids':reference_ids},idempotency_key,lease,execute)

    def diagnostics(self,actor):
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor);manifest=self._manifest(connection)['data']
            latest={}
            for kind in ('daily','weekly'):
                row=connection.execute(text('''SELECT id,data FROM c0_objects WHERE space_id=:space AND type_name=:type
                    AND data->>'workflow_type'=:workflow AND data->>'state'='complete'
                    ORDER BY data->>'finished_at' DESC,id DESC LIMIT 1'''),
                    {'space':self._space_id,'type':PREFIX+'run_v1','workflow':kind}).mappings().one_or_none()
                latest[kind]=dict(row) if row else None
            connectors=[]
            for connector_id in manifest['manifest']['connector_ids']:
                connector=self._find(connection,'connector_v1',connector_id,required=False)
                sync=self._find(connection,'connector_sync_v1',connector_id,required=False)
                matches=bool(connector and sync and connector['data']['definition_hash']==sync['data']['definition_hash'])
                connectors.append({'connector_id':connector_id,'current_definition_verified':matches,
                    'status':sync['data']['status'] if matches else 'configuration_changed_or_not_synced'})
            errors=[dict(row) for row in connection.execute(text('''SELECT r.id,r.type_name,r.data FROM c0_objects r WHERE r.space_id=:space
                AND ((r.type_name IN (:run,:queue,:audit) AND (r.data->>'state' IN ('partial','blocked')
                    OR r.data->>'status' IN ('blocked','deferred','retry_wait','awaiting_merge')
                    OR (r.type_name=:run AND r.data->>'state'='running' AND r.data->>'lease_expiry'<>''
                        AND (r.data->>'lease_expiry')::timestamptz<:now)))
                    OR (r.type_name=:release AND r.data->>'status' IN ('failed','partial','security_alert'))
                    OR (r.type_name=:admission AND (r.data->>'reason'='historical_inventory_requires_review'
                        OR r.data->>'disposition'='needs_user_scope_decision')
                        AND NOT EXISTS(SELECT 1 FROM c0_objects a JOIN c0_object_events ae
                            ON ae.space_id=a.space_id AND ae.object_id=a.id JOIN c0_object_events re
                            ON re.space_id=r.space_id AND re.object_id=r.id WHERE a.space_id=r.space_id AND a.type_name=:admission
                            AND a.data->>'candidate_id'=r.data->>'candidate_id' AND ae.feed_cursor>re.feed_cursor
                            AND (a.data->>'target_id'<>'' OR a.data->>'disposition' IN ('reject_scope','archive_candidate'))))) ORDER BY r.updated_at DESC,r.id DESC LIMIT 20'''),
                {'space':self._space_id,'run':PREFIX+'run_v1','queue':PREFIX+'queue_v1',
                    'audit':PREFIX+'audit_v1','admission':PREFIX+'admission_v1','release':PREFIX+'release_check_v1','now':self.clock()}).mappings()]
            findings=connection.execute(text("SELECT COALESCE(sum((data->>'issue_count')::int),0) FROM c0_objects WHERE space_id=:space AND type_name=:type"),
                {'space':self._space_id,'type':PREFIX+'audit_observation_v1'}).scalar_one()
        report=self.get_report(actor)
        return snapshot({'project_id':str(self._space_id),'manifest_version':manifest['version'],'last_successful_runs':latest,
            'connectors':connectors,'latest_daily_report':report['report'],'errors':errors,'errors_may_be_incomplete':len(errors)==20,
            'structural_findings':findings,'external_execution_verified':False})
