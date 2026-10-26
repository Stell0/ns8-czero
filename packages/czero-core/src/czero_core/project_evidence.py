# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Research receipts bind existing evidence/knowledge; no reasoning runs here."""
import hashlib
import json
from uuid import UUID
from sqlalchemy import text
from .knowledge import KnowledgeService,KnowledgeNotFound,EvidenceNotReady
from .sources import SourceService,SourceNotFound
from .object_schema import bounded_json,validate_record
from .project_schema import PREFIX,RESULT_INPUT,identifier
from .project_monitoring import scope_hash
from .project_workflows import data_of,digest,receipt
from .wiki import markdown

FACTUAL={'observed_fact','supported_inference','contradiction','outdated_assertion'}


def clean_markdown(body):
    """Reject page DTOs accidentally serialized as prose; fenced JSON is fine."""
    markdown(body)
    candidate=body.lstrip('\ufeff \r\n\t')
    if candidate.startswith('{'):
        try:value=json.loads(candidate)
        except (ValueError,RecursionError):value=None
        if isinstance(value,dict) and (
                ('body' in value and bool({'title','id','page_id','revision','metadata','slug'}&value.keys()))
                or ('content' in value and bool({'title','id','page_id','revision','slug'}&value.keys()))):
            raise ValueError('wiki_body_contains_page_envelope')
    return body


class ProjectEvidence:
    def _project_resource(self,connection,kind,reference):
        UUID(reference)
        row=connection.execute(text('''SELECT * FROM c0_objects WHERE space_id=:space
            AND type_name=:type AND id=CAST(:id AS uuid)'''),
            {'space':self._space_id,'type':PREFIX+kind,'id':reference}).mappings().one_or_none()
        if row is None:raise ValueError('project_resource_not_stored')
        return dict(row)

    def _citations(self,connection,identities):
        if type(identities) is not list or len(identities)>32 or len(set(identities))!=len(identities):
            raise ValueError('invalid_result_citations')
        if not identities:return [],digest([])
        knowledge=KnowledgeService(self.database,self.access).in_space(self._space_id)
        try:
            keys=knowledge._evidence(connection,identities)
            citations=[SourceService._citation(connection,key,space_id=self._space_id) for key in keys]
        except (SourceNotFound,KnowledgeNotFound,EvidenceNotReady):
            raise ValueError('result_evidence_not_ready') from None
        if any(hashlib.sha256(citation['body'].encode()).hexdigest()!=citation['content_hash'] for citation in citations):
            raise ValueError('immutable_passage_hash_mismatch')
        proof=[{key:str(citation[key]) for key in ('chunk_id','document_id','version_id','source_id',
            'source_hash','text_hash','content_hash','start_offset','end_offset')} for citation in citations]
        return citations,digest(proof)

    def _challenge_ready(self,connection,challenge,cycle_id):
        queries=challenge['queries'];ids=[entry['request_id'] for entry in queries]
        if len(set(ids))!=len(ids):raise ValueError('duplicate_countercheck_request')
        by_id={entry['request_id']:entry for entry in queries}
        for entry in queries:
            identifier(entry['request_id'])
            if entry['replaces']:
                replaced=by_id.get(entry['replaces'])
                if not replaced or replaced['state'] not in ('failed','uncertain') or replaced['query']!=entry['query']:
                    raise ValueError('invalid_countercheck_replacement')
            if entry['state']=='succeeded':
                if not entry['snapshot_chunk_id'] or not entry['external_reference'].strip():
                    raise ValueError('countercheck_requires_observed_snapshot')
                self._citations(connection,[entry['snapshot_chunk_id']])
                provenance=connection.execute(text('''SELECT s.metadata FROM c0_chunks c
                    JOIN c0_documents d ON d.id=c.document_id AND d.space_id=c.space_id
                    JOIN c0_source_versions v ON v.id=d.version_id AND v.space_id=d.space_id
                    JOIN c0_sources s ON s.id=v.source_id AND s.space_id=v.space_id
                    WHERE c.space_id=:space AND c.id=CAST(:id AS uuid)'''),
                    {'space':self._space_id,'id':entry['snapshot_chunk_id']}).scalar_one()
                if (provenance.get('source_type')!='query_observation' or provenance.get('query')!=entry['query']
                        or provenance.get('external_reference')!=entry['external_reference']):
                    raise ValueError('countercheck_snapshot_provenance_mismatch')
                if cycle_id:
                    call=self._find(connection,'monitor_call_v1',entry['request_id'])['data']
                    if (call['cycle_id'],call['kind'],call['state'],call['request_text'],call['external_reference'])!=(
                            cycle_id,'query','succeeded',entry['query'],entry['external_reference']):
                        raise ValueError('monitoring_countercheck_not_reserved')
            elif entry['snapshot_chunk_id']:raise ValueError('unverified_countercheck_snapshot')
        self._citations(connection,challenge['counter_citation_ids'])
        recovered={entry['replaces'] for entry in queries if entry['state']=='succeeded' and entry['replaces']}
        searched=(any(entry['state']=='succeeded' for entry in queries)
            and all(entry['state']=='succeeded' or entry['request_id'] in recovered for entry in queries)
            and bool(challenge['coverage'].strip()) and bool(challenge['strongest_alternative'].strip())
            and bool(challenge['falsification_conditions']))
        if challenge['state']=='searched' and not searched:raise ValueError('countercheck_coverage_incomplete')
        if challenge['state'] in ('not_required','not_searched') and queries:
            raise ValueError('countercheck_state_has_executed_queries')
        return challenge['state']=='searched' and searched

    def _finding_values(self,connection,finding,cycle_id):
        citations,evidence_hash=self._citations(connection,finding['citation_ids'])
        if finding['classification'] in FACTUAL and not citations:raise ValueError('factual_finding_requires_evidence')
        claim_hash='';start='';end=''
        if finding['claim_id']:
            knowledge=KnowledgeService(self.database,self.access).in_space(self._space_id)
            try:claim=knowledge._claim(connection,finding['claim_id'])
            except KnowledgeNotFound:raise ValueError('finding_claim_not_stored') from None
            if (claim['deleted'] and finding['classification'] not in ('outdated_assertion','contradiction')) or claim['revision']!=finding['claim_revision']:
                raise self.conflict()
            linked=connection.execute(text('SELECT chunk_id FROM c0_evidence_links WHERE space_id=:space AND claim_id=CAST(:id AS uuid)'),
                {'space':self._space_id,'id':finding['claim_id']}).scalars().all()
            if not linked or not {str(key) for key in linked}<=set(finding['citation_ids']):
                raise ValueError('finding_claim_evidence_mismatch')
            claim_hash=digest(claim['value']);start=claim['valid_from'].isoformat() if claim['valid_from'] else ''
            end=claim['valid_to'].isoformat() if claim['valid_to'] else ''
        elif finding['claim_revision']:raise ValueError('unexpected_claim_revision')
        checked=self._challenge_ready(connection,finding['challenge'],cycle_id)
        return {**finding,'evidence_hash':evidence_hash,'claim_value_hash':claim_hash,'valid_from':start,'valid_to':end},not finding['consequential'] or checked

    def _result_findings(self,connection,result):
        return [self._project_resource(connection,'finding_v1',reference) for reference in result['finding_ids']]

    def _result_context(self,connection,run,attempt_id,cycle_id):
        if bool(attempt_id)==bool(cycle_id):raise ValueError('one_result_origin_required')
        if attempt_id:
            attempt=self._attempt(connection,run,attempt_id)['data']
            if attempt['fencing_generation']!=run['fencing_generation'] or attempt['state'] not in ('invoking','uncertain','result_saved','complete'):
                raise self.conflict()
            queued=self._find(connection,'queue_v1',attempt['queue_id'])['data']
            topic=self._find(connection,'topic_v1',queued['topic_id'])['data']
            context=scope_hash(self._manifest(connection)['data']['manifest'],topic)
            return 'attempt:'+attempt_id,queued['topic_id'],queued['question'],context
        cycle=self._monitor_row(connection,run,cycle_id)['data']
        topic=self._find(connection,'topic_v1',cycle['topic_id'])['data']
        return 'monitor:'+cycle_id+':'+cycle['scope_hash'],cycle['topic_id'],topic['originating_question'] or topic['label'],cycle['scope_hash']

    def save_result(self,actor,lease,data,*,attempt_id='',cycle_id='',expected_revision=0,idempotency_key):
        data=validate_record(RESULT_INPUT,bounded_json(data,maximum=262144))
        if type(expected_revision) is not int or expected_revision<0:raise ValueError('invalid_revision')
        payload=dict(data=data,attempt_id=attempt_id,cycle_id=cycle_id,expected_revision=expected_revision)
        def execute(connection,current,run_row):
            run=run_row['data'];identity,topic_id,question,context=self._result_context(connection,run,attempt_id,cycle_id)
            fingerprint=digest([data,context,run['config_version']]);previous=self._find(connection,'result_v1',identity,required=False)
            if previous and previous['data']['payload_hash']==fingerprint:
                return receipt('SAVED' if previous['data']['state']=='published' else 'PARTIAL' if previous['data']['state']=='partial' else 'ACCEPTED_PENDING_MERGE','result_already_saved',previous)
            if (previous['revision'] if previous else 0)!=expected_revision:raise self.conflict()
            if previous and previous['data']['state']=='published':
                finished=(self._attempt(connection,run,attempt_id)['data']['state']=='complete' if attempt_id
                    else self._monitor_row(connection,run,cycle_id)['data']['status'] in ('complete','no_material_update'))
                if finished:raise ValueError('completed_result_is_immutable')
            old=[row['data'] for row in self._result_findings(connection,previous['data'])] if previous else []
            if len(data['findings'])<len(old):raise ValueError('result_cannot_remove_findings')
            old_queries={entry['request_id']:entry for finding in old for entry in finding['challenge']['queries']}
            all_queries={};counter_sources=set()
            for index,finding in enumerate(data['findings']):
                if index<len(old):
                    earlier=old[index]
                    if (finding['statement']!=earlier['statement'] or (finding['classification']!=earlier['classification']
                            and finding['classification'] not in ('outdated_assertion','contradiction'))):
                        raise ValueError('result_cannot_replace_assertions')
                    if not set(earlier['citation_ids'])<=set(finding['citation_ids']):raise ValueError('result_cannot_remove_evidence')
                    if earlier['claim_id'] and finding['claim_id']!=earlier['claim_id']:raise ValueError('result_cannot_replace_claim')
                for entry in finding['challenge']['queries']:
                    if entry['request_id'] in all_queries and all_queries[entry['request_id']]!=entry:
                        raise ValueError('countercheck_identity_conflict')
                    all_queries[entry['request_id']]=entry
                counter_sources.update(finding['challenge']['counter_citation_ids'])
            if len(all_queries)>3 or len(counter_sources)>10:raise ValueError('result_countercheck_resource_cap')
            for key,entry in old_queries.items():
                current_query=all_queries.get(key)
                if current_query is None or any(current_query[field]!=entry[field] for field in ('query','replaces')):
                    raise ValueError('result_cannot_reset_counterchecks')
                if entry['state']!='uncertain' and current_query!=entry:raise ValueError('recorded_countercheck_is_immutable')
            version=previous['data']['content_version']+1 if previous else 1;result_id=digest([str(self._space_id),identity])
            findings=[];ready=True
            for index,finding in enumerate(data['findings'],1):
                values,valid=self._finding_values(connection,finding,cycle_id);ready=ready and valid
                findings.append(self._save(connection,current,'finding_v1',result_id+':'+str(version)+':'+str(index),
                    {'result_id':result_id,'content_version':version,'ordinal':index,**values}))
            values={'result_id':result_id,'project_id':str(self._space_id),'run_id':run['run_id'],'attempt_id':attempt_id,
                'cycle_id':cycle_id,'topic_id':topic_id,'scope_hash':context,'config_version':run['config_version'],
                'local_date':run['local_cycle_date'],'content_version':version,'question':question,
                **{key:value for key,value in data.items() if key!='findings'},'finding_ids':[str(row['id']) for row in findings],
                'payload_hash':fingerprint,'state':'awaiting_merge' if ready else 'partial','publication_reference':'',
                'saved_at':self.clock().isoformat()}
            saved=self._save(connection,current,'result_v1',identity,values,previous=previous)
            history=self._save(connection,current,'result_history_v1',result_id+':'+str(version),values)
            return receipt('ACCEPTED_PENDING_MERGE' if ready else 'PARTIAL','result_saved',saved,history,*findings)
        return self._workflow_mutate(actor,'result_save',payload,idempotency_key,lease,execute)

    def _wiki_receipts(self,connection,identities,*,current=True):
        if type(identities) is not list or not 1<=len(identities)<=20 or len(set(identities))!=len(identities):
            raise ValueError('invalid_publication_wiki_references')
        rows=[]
        for identity in identities:
            UUID(identity)
            row=connection.execute(text('''SELECT r.*,p.revision AS current_revision,p.deleted FROM c0_wiki_revisions r
                JOIN c0_wiki_pages p ON p.id=r.page_id AND p.space_id=r.space_id
                WHERE r.space_id=:space AND r.id=CAST(:id AS uuid)'''),{'space':self._space_id,'id':identity}).mappings().one_or_none()
            if row is None or (current and (row['deleted'] or row['number']!=row['current_revision'])):raise self.conflict()
            clean_markdown(row['body'])
            if hashlib.sha256(row['body'].encode()).hexdigest()!=row['content_hash']:raise ValueError('wiki_readback_hash_mismatch')
            rows.append(dict(row))
        return rows

    def _wiki_project_marker(self,page):
        marker=page['metadata'].get('c0_project')
        if type(marker) is not dict or marker.get('project_id')!=str(self._space_id):
            raise ValueError('wiki_project_binding_missing')
        references=marker.get('result_references',[])
        if type(references) is not list or len(references)>100 or any(type(value) is not str for value in references):
            raise ValueError('wiki_result_binding_invalid')
        for value in references:UUID(value)
        return marker

    def _research_result(self,connection,attempt_id,reference,*,published=False):
        row=self._project_resource(connection,'result_v1',reference);result=row['data']
        if result['attempt_id']!=attempt_id or result['cycle_id']:raise ValueError('result_attempt_mismatch')
        if published:
            topic=self._find(connection,'topic_v1',result['topic_id'])['data']
            if result['scope_hash']!=scope_hash(self._manifest(connection)['data']['manifest'],topic):raise self.conflict()
            self._result_ready(connection,row)
        return row

    def _result_ready(self,connection,row,*,current=True):
        result=row['data']
        if result['state']!='published' or not result['publication_reference']:raise ValueError('result_knowledge_merge_incomplete')
        publication=self._project_resource(connection,'result_publication_v1',result['publication_reference'])['data']
        if publication['result_reference']!=str(row['id']) or publication['content_version']!=result['content_version']:
            raise ValueError('result_publication_version_mismatch')
        wiki=self._wiki_receipts(connection,publication['wiki_revision_ids'],current=current)
        if [page['content_hash'] for page in wiki]!=publication['wiki_hashes']:raise self.conflict()
        for page in wiki:
            if str(row['id']) not in self._wiki_project_marker(page).get('result_references',[]):
                raise ValueError('wiki_result_binding_missing')
        for finding in self._result_findings(connection,result):
            values=finding['data']
            if not current:
                _,evidence_hash=self._citations(connection,values['citation_ids'])
                if evidence_hash!=values['evidence_hash']:raise ValueError('result_evidence_review_changed')
                if values['claim_id']:
                    claim=KnowledgeService(self.database,self.access).in_space(self._space_id)._claim(connection,values['claim_id'])
                    if digest(claim['value'])!=values['claim_value_hash']:raise ValueError('historical_claim_value_changed')
                continue
            checked,ready=self._finding_values(connection,{key:values[key] for key in RESULT_INPUT['properties']['findings']['items']['properties']},result['cycle_id'])
            if not ready or checked['evidence_hash']!=values['evidence_hash'] or checked['claim_value_hash']!=values['claim_value_hash']:
                raise ValueError('result_evidence_review_changed')
        return publication

    def publish_result(self,actor,lease,result_reference,wiki_revision_ids,*,idempotency_key):
        def execute(connection,current,run_row):
            previous=self._project_resource(connection,'result_v1',result_reference);result=data_of(previous)
            identity,_,_,context=self._result_context(connection,run_row['data'],result['attempt_id'],result['cycle_id'])
            if result['run_id']!=run_row['data']['run_id'] or result['scope_hash']!=context:raise self.conflict()
            if result['attempt_id']:
                attempt=self._attempt(connection,run_row['data'],result['attempt_id'])['data']
                if not self._queue_current(connection,self._find(connection,'queue_v1',attempt['queue_id'])['data']):raise self.conflict()
            if result['state']=='published':
                publication=self._project_resource(connection,'result_publication_v1',result['publication_reference'])['data']
                if publication['wiki_revision_ids']==wiki_revision_ids:
                    self._result_ready(connection,previous)
                    return receipt('SAVED','result_already_published',previous)
            claims=[]
            for finding in self._result_findings(connection,result):
                values=finding['data'];checked,ready=self._finding_values(connection,{key:values[key] for key in RESULT_INPUT['properties']['findings']['items']['properties']},result['cycle_id'])
                if not ready:return receipt('PARTIAL','result_countercheck_incomplete',previous)
                if checked['evidence_hash']!=values['evidence_hash'] or checked['claim_value_hash']!=values['claim_value_hash']:raise self.conflict()
                if values['claim_id']:claims.append(values['claim_id'])
            wiki=self._wiki_receipts(connection,wiki_revision_ids)
            for page in wiki:
                if result_reference not in self._wiki_project_marker(page).get('result_references',[]):
                    raise ValueError('wiki_result_binding_missing')
            publication=self._save(connection,current,'result_publication_v1',result['result_id']+':'+str(result['content_version'])+':'+digest(wiki_revision_ids),{
                'result_reference':result_reference,'content_version':result['content_version'],'config_version':run_row['data']['config_version'],
                'run_id':run_row['data']['run_id'],'wiki_revision_ids':wiki_revision_ids,'wiki_hashes':[page['content_hash'] for page in wiki],
                'claim_ids':list(dict.fromkeys(claims)),'verified_at':self.clock().isoformat()})
            result.update(state='published',publication_reference=str(publication['id']))
            saved=self._save(connection,current,'result_v1',identity,result,previous=previous)
            return receipt('SAVED','result_knowledge_verified',saved,publication)
        return self._workflow_mutate(actor,'result_publish',{'result_reference':result_reference,'wiki_revision_ids':wiki_revision_ids},idempotency_key,lease,execute)

    def _monitor_result_ready(self,connection,cycle,result_reference):
        result=self._project_resource(connection,'result_v1',result_reference)
        values=result['data']
        if values['cycle_id']!=cycle['cycle_id'] or values['scope_hash']!=cycle['scope_hash'] or values['topic_id']!=cycle['topic_id']:
            raise ValueError('monitoring_result_context_mismatch')
        if values['state']!='published':return False
        self._result_ready(connection,result)
        cited={key for row in self._result_findings(connection,values) for key in row['data']['citation_ids']}
        inspected={key for row in self._monitor_calls(connection,cycle['cycle_id'])
            if row['data']['kind']=='source' and row['data']['state']=='succeeded' and row['data']['scope_hash']==cycle['scope_hash']
            for key in row['data']['citation_ids']}
        if not cited&inspected:raise ValueError('monitoring_result_lacks_inspected_evidence')
        return True
