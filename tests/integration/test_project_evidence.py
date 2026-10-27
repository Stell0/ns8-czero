# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual immutable evidence, claim and Wiki bindings; no generative provider."""
from copy import deepcopy
import json
from uuid import uuid4
import pytest
from sqlalchemy import text
from czero_core.knowledge import KnowledgeService
from czero_core.projects import ProjectConflict
from czero_core.project_evidence import clean_markdown
from test_access import access
from test_projects import project
from test_project_workflows import setup,claim,admit,reserve,row
from test_sources import sources,upload,execute


@pytest.fixture
def evidence(project,sources):
    service,owner=setup(project);lease=claim(service,owner)
    original,_,registry,created=sources;scoped=original.in_space(service._space_id)
    fixture=(scoped,owner,registry,created)
    knowledge=KnowledgeService(service.database,service.access).in_space(service._space_id)
    def source(body='Fabricated Atlas capacity is100 synthetic units.',metadata=None):
        version=upload(fixture,body.encode(),metadata=metadata or {})
        execute(fixture,'source.extract',version['id'])
        document=scoped.document(owner,version['id']);chunks=scoped.chunks(owner,document['id'])
        return version,chunks
    yield service,owner,lease,knowledge,source,fixture
    with service.database.engine.begin() as connection:
        for table in ('c0_annotation_targets','c0_evidence_links','c0_entity_links','c0_relations','c0_claims','c0_entity_aliases',
                'c0_entities','c0_wiki_chunks','c0_wiki_revisions','c0_wiki_pages','c0_knowledge_events'):
            connection.execute(text('DELETE FROM '+table+' WHERE space_id=:space'),{'space':service._space_id})


def start(evidence,name='investigation'):
    service,owner,lease,*_=evidence;admit(service,owner,name)
    attempt=row(reserve(service,owner,lease),'attempt_v1')['data']
    service.invocation(owner,lease,attempt['attempt_id'],'started',idempotency_key=uuid4().hex)
    return attempt


def finding(chunk,**changes):
    return {'statement':'Fabricated capacity is100 units.','classification':'observed_fact','confidence':70,
        'rationale':'Synthetic original evidence supports this bounded assertion.','citation_ids':[str(chunk['id'])],
        'claim_id':'','claim_revision':0,'consequential':False,'applicability_limits':['Synthetic fixture only'],
        'challenge':{'state':'not_required','reason':'Nonconsequential synthetic assertion','strongest_alternative':'',
            'falsification_conditions':[],'queries':[],'counter_citation_ids':[],'coverage':'','conclusion_change':''},**changes}


def result_data(*findings):
    return {'summary':'A fabricated capacity constraint was identified.','changes':'The synthetic capacity estimate changed.',
        'importance':'It affects the approved synthetic manufacturing goal.','assumptions':['Earlier capacity was unknown.'],
        'uncertainties':['This fixture makes no real-world assertion.'],'assessment_ref':'synthetic:actual-assessment','findings':list(findings)}


def save(evidence,attempt,data,**changes):
    service,owner,lease,*_=evidence
    return service.save_result(owner,lease,data,attempt_id=attempt['attempt_id'],idempotency_key=uuid4().hex,**changes)


def page(evidence,body='# Learning\n\nFabricated capacity is100 units, affecting the synthetic goal.',*,result_reference=''):
    service,owner,_,knowledge,*_=evidence
    return knowledge.create_page(owner,'findings/'+uuid4().hex,'Synthetic learning',body,
        metadata={'fixture':'project evidence','c0_project':{'project_id':str(service._space_id),
            'result_references':[result_reference] if result_reference else []}},idempotency_key=uuid4().hex)


def test_real_result_readback_and_merge_recovery_use_one_attempt(evidence):
    service,owner,lease,_,source,_=evidence;attempt=start(evidence);_,chunks=source()
    with pytest.raises(ValueError):service.invocation(owner,lease,attempt['attempt_id'],'returned',
        result_reference=service.get(owner)['id'],idempotency_key='manifest-is-not-result')
    data=result_data(finding(chunks[0]));saved=row(save(evidence,attempt,data),'result_v1')
    assert row(save(evidence,attempt,data),'result_v1')==saved
    assert len(service.list_records(owner,'finding_v1'))==1
    service.invocation(owner,lease,attempt['attempt_id'],'returned',result_reference=saved['id'],idempotency_key='returned')
    assert reserve(service,owner,lease,resume_attempt_id=attempt['attempt_id'])['status']=='ACCEPTED_PENDING_MERGE'
    with pytest.raises(ValueError):service.complete_research(owner,lease,attempt['attempt_id'],
        commit_references=[saved['id']],idempotency_key='premature')
    wiki=page(evidence,result_reference=saved['id']);published=service.publish_result(owner,lease,saved['id'],[wiki['content']['id']],idempotency_key='publish')
    proof=row(published,'result_publication_v1')
    completed=service.complete_research(owner,lease,attempt['attempt_id'],commit_references=[proof['id']],idempotency_key='complete')
    assert row(completed,'queue_v1')['data']['status']=='complete'
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1
    assert service.get_record(owner,'result_v1','attempt:'+attempt['attempt_id'])['data']['state']=='published'


def test_queued_extraction_and_wrong_claim_passages_cannot_be_result_evidence(evidence):
    service,owner,_,knowledge,source,_=evidence;attempt=start(evidence);version,chunks=source()
    with service.database.engine.begin() as connection:
        connection.execute(text("UPDATE c0_source_versions SET state='queued' WHERE id=:id"),{'id':version['id']})
    with pytest.raises(ValueError,match='not_ready'):save(evidence,attempt,result_data(finding(chunks[0])))
    assert service.list_records(owner,'result_v1')==[]
    with service.database.engine.begin() as connection:
        connection.execute(text("UPDATE c0_source_versions SET state='ready' WHERE id=:id"),{'id':version['id']})
    entity=knowledge.create_entity(owner,'concept','Atlas',idempotency_key='entity')
    claim_row=knowledge.create_claim(owner,entity['id'],'capacity',{'units':100},evidence_chunk_ids=[str(chunks[0]['id'])],idempotency_key='claim')
    _,other=source('A different immutable original with unrelated evidence.')
    with pytest.raises(ValueError,match='evidence_mismatch'):save(evidence,attempt,result_data(finding(other[0],
        claim_id=claim_row['id'],claim_revision=1)))


def test_json_page_envelope_is_not_markdown_and_repair_does_not_repeat_research(evidence):
    service,owner,lease,knowledge,source,_=evidence;attempt=start(evidence);_,chunks=source()
    saved=row(save(evidence,attempt,result_data(finding(chunks[0]))),'result_v1')
    bad=page(evidence,json.dumps({'id':str(uuid4()),'title':'Wrong envelope','content':{'body':'# Real Markdown'}}),result_reference=saved['id'])
    with pytest.raises(ValueError,match='envelope'):service.publish_result(owner,lease,saved['id'],[bad['content']['id']],idempotency_key='bad-body')
    assert service.get_record(owner,'result_v1','attempt:'+attempt['attempt_id'])['data']['state']=='awaiting_merge'
    corrected=knowledge.update_page(owner,bad['id'],'Corrected learning','# Real Markdown\n\nFabricated capacity is100 units.',
        metadata={**bad['content']['metadata'],'fixture':'separate metadata'},expected_revision=1,idempotency_key='repair')
    assert service.publish_result(owner,lease,saved['id'],[corrected['content']['id']],idempotency_key='repaired')['status']=='SAVED'
    assert knowledge.get_page(owner,bad['id'])['content']['body'].startswith('# Real Markdown')
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1
    assert clean_markdown('```json\n{"title":"Example","body":"data"}\n```').startswith('```')


def test_consequential_countercheck_requires_actual_observation_and_retains_budget(evidence):
    service,owner,lease,_,source,_=evidence;attempt=start(evidence);_,chunks=source()
    value=finding(chunks[0],consequential=True);value['challenge'].update(state='not_searched',reason='Check still pending')
    partial=row(save(evidence,attempt,result_data(value)),'result_v1');assert partial['data']['state']=='partial'
    wiki=page(evidence,result_reference=partial['id'])
    assert service.publish_result(owner,lease,partial['id'],[wiki['content']['id']],idempotency_key='unsearched')['status']=='PARTIAL'
    query='Find contrary synthetic capacity evidence';reference='synthetic:observed-counter-result'
    _,snapshot=source('Observed synthetic search response: no contrary development in bounded results.',
        {'source_type':'query_observation','query':query,'external_reference':reference})
    value['challenge'].update(state='searched',strongest_alternative='Capacity may refer to a different operating condition.',
        falsification_conditions=['A primary source reports a lower capacity.'],coverage='One successful bounded contrary query.',
        queries=[{'request_id':'counter-one','query':query,'state':'succeeded','snapshot_chunk_id':str(snapshot[0]['id']),
            'external_reference':reference,'replaces':''}])
    saved=row(save(evidence,attempt,result_data(value),expected_revision=partial['revision']),'result_v1')
    assert saved['id']==partial['id'] and saved['data']['content_version']==2
    assert len(service.list_records(owner,'result_history_v1'))==2
    assert service.publish_result(owner,lease,saved['id'],[wiki['content']['id']],idempotency_key='checked')['status']=='SAVED'
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1


def test_new_wiki_revision_requires_new_explicit_publication_proof(evidence):
    service,owner,lease,knowledge,source,_=evidence;attempt=start(evidence);_,chunks=source()
    saved=row(save(evidence,attempt,result_data(finding(chunks[0]))),'result_v1')
    service.invocation(owner,lease,attempt['attempt_id'],'returned',result_reference=saved['id'],idempotency_key='returned')
    wiki=page(evidence,result_reference=saved['id'])
    first=service.publish_result(owner,lease,saved['id'],[wiki['content']['id']],idempotency_key='first')
    changed=knowledge.update_page(owner,wiki['id'],'New revision','# Updated learning\n\nFabricated capacity needs a revised applicability caveat.',
        metadata=wiki['content']['metadata'],expected_revision=1,idempotency_key='edit')
    with pytest.raises(ProjectConflict):service.complete_research(owner,lease,attempt['attempt_id'],
        commit_references=[row(first,'result_publication_v1')['id']],idempotency_key='stale')
    second=service.publish_result(owner,lease,saved['id'],[changed['content']['id']],idempotency_key='recheck')
    assert row(second,'result_publication_v1')['id']!=row(first,'result_publication_v1')['id']
    assert len(service.list_records(owner,'result_publication_v1'))==2


def test_actual_claim_and_revision_annotations_preserve_history(evidence):
    from czero_core.annotations import AnnotationService,ContentTarget
    service,owner,lease,knowledge,source,_=evidence;attempt=start(evidence);_,chunks=source()
    entity=knowledge.create_entity(owner,'concept','Synthetic capacity',idempotency_key='entity')
    claim=knowledge.create_claim(owner,entity['id'],'capacity',{'units':100},evidence_chunk_ids=[str(chunks[0]['id'])],idempotency_key='claim')
    result=row(save(evidence,attempt,result_data(finding(chunks[0],claim_id=claim['id'],claim_revision=claim['revision']))),'result_v1')
    wiki=page(evidence,result_reference=result['id']);annotations=AnnotationService(service.database,service.access).in_space(service._space_id)
    target=ContentTarget('wiki_revision',wiki['content']['id'],wiki['revision'])
    annotations.update(owner,target,'verification',{'status':'verified'},expected_revision=0,idempotency_key='verify')
    service.publish_result(owner,lease,result['id'],[wiki['content']['id']],idempotency_key='publish')
    changed=knowledge.update_page(owner,wiki['id'],'Revised interpretation','# Revised learning\n\nThe synthetic capacity assumption needs a contrary check.',
        metadata=wiki['content']['metadata'],expected_revision=1,idempotency_key='new-revision')
    assert annotations.get(owner,ContentTarget('wiki_revision',changed['content']['id'],2),'verification')['status']=='unknown'
    assert annotations.get(owner,target,'verification')['status']=='verified'
    assert knowledge.get_claim(owner,claim['id'])['value']=={'units':100}


@pytest.mark.parametrize('envelope',[{'title':'Title','content':{'body':'# Markdown'}},
    {'slug':'page','body':'# Markdown'},{'metadata':{},'body':'# Markdown'},{'revision':1,'content':{'body':'# Markdown'}}])
def test_serialized_page_variants_are_rejected_but_fenced_examples_are_markdown(envelope):
    body=json.dumps(envelope)
    with pytest.raises(ValueError,match='page_envelope'):clean_markdown(body)
    assert clean_markdown('```json\n'+body+'\n```').startswith('```json')


@pytest.mark.parametrize('retracted',[False,True])
def test_pending_published_result_can_rereview_changed_claim_without_another_attempt(evidence,retracted):
    service,owner,lease,knowledge,source,_=evidence;attempt=start(evidence);_,chunks=source()
    entity=knowledge.create_entity(owner,'concept','Synthetic capacity',idempotency_key='entity')
    claim=knowledge.create_claim(owner,entity['id'],'capacity',{'units':100},evidence_chunk_ids=[str(chunks[0]['id'])],idempotency_key='claim')
    data=result_data(finding(chunks[0],claim_id=claim['id'],claim_revision=1))
    result=row(save(evidence,attempt,data),'result_v1')
    service.invocation(owner,lease,attempt['attempt_id'],'returned',result_reference=result['id'],idempotency_key='returned')
    wiki=page(evidence,result_reference=result['id'])
    service.publish_result(owner,lease,result['id'],[wiki['content']['id']],idempotency_key='first-published')
    if retracted:knowledge.delete_claim(owner,claim['id'],expected_revision=1,idempotency_key='retract')
    else:knowledge.update_claim(owner,claim['id'],expected_revision=1,metadata={'applicability':'Reassessment required'},idempotency_key='claim-edit')
    with pytest.raises(ProjectConflict):service.complete_research(owner,lease,attempt['attempt_id'],
        commit_references=[service.get_record(owner,'result_v1','attempt:'+attempt['attempt_id'])['data']['publication_reference']],idempotency_key='stale-claim')
    current=service.get_record(owner,'result_v1','attempt:'+attempt['attempt_id'])
    data['findings'][0]['claim_revision']=2
    if retracted:
        data['findings'][0].update(classification='outdated_assertion',rationale='The original assertion was explicitly retracted; retained for history.')
    saved=row(save(evidence,attempt,data,expected_revision=current['revision']),'result_v1')
    assert saved['data']['content_version']==2 and saved['data']['publication_reference']==''
    revised=knowledge.update_page(owner,wiki['id'],'Reviewed learning',
        '# Reviewed learning\n\nThe earlier capacity assertion needs the recorded applicability correction or retraction.',
        metadata=wiki['content']['metadata'],expected_revision=1,idempotency_key='reviewed-wiki')
    proof=service.publish_result(owner,lease,saved['id'],[revised['content']['id']],idempotency_key='reviewed-published')
    service.complete_research(owner,lease,attempt['attempt_id'],commit_references=[row(proof,'result_publication_v1')['id']],idempotency_key='complete')
    assert service.get_record(owner,'budget_v1','2026-10-25')['data']['used']==1
    assert len(service.list_records(owner,'result_history_v1'))==2 and len(service.list_records(owner,'result_publication_v1'))==2
    current=service.get_record(owner,'result_v1','attempt:'+attempt['attempt_id']);data['summary']='An unrelated replacement is not allowed.'
    with pytest.raises(ValueError,match='completed_result_is_immutable'):
        save(evidence,attempt,data,expected_revision=current['revision'])
