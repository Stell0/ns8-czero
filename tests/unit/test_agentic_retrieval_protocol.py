# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult,TextContent

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
from agentic_retrieval.protocol import (Budget,body_hash,digest,episode_input,grade,partition,
                                       summary,validate_corpus,validate_questions)
from agentic_retrieval.layer import maintain,validate_plan,verify
from agentic_retrieval.runner import ReadBoundary,accepted
from evaluation.codex_driver import RunnerFailure,evaluate
from test_tool_evaluation import fake_codex


def fixture():
    body='Orion 2 uses port 7443.'
    c={'source_id':'s','version_id':'v','document_id':'d','chunk_id':'c',
        'content_hash':body_hash(body),'source_hash':'sh','start_offset':0,'end_offset':len(body),'body':body}
    d={'id':'s','url':'https://docs.example.test/2','generation':'v','content_hash':body_hash(body),
        'body':body,'product':'Orion','version':'2','language':'en','chunks':[c]}
    e={'document_id':'s','url':d['url'],'generation':'v','content_hash':d['content_hash'],'quote':'port 7443'}
    q={'id':'question-a','text':'Which port is used?','language':'en','type':'configuration',
        'answerability':'answerable','products':['Orion'],'versions':['2'],'evidence_sets':[[[e]]],
        'provenance':'provisional analyst fixture','confidence':'high','uncertainty':''}
    r={'key':'connection','title':'Orion connection','synthesis':'See original connection settings.',
       'classification':'extracted','evidence':[{k:v for k,v in e.items() if k!='url'}|{'chunk_id':'c'}]}
    return [d],q,{'namespace':'test-layer','records':[r]}


def test_quotes_hashes_generation_and_alternative_complete_sets():
    corpus,q,_=fixture();validate_corpus(corpus);validate_questions([q],corpus)
    q['evidence_sets'].append(q['evidence_sets'][0]);validate_questions([q],corpus)
    for k,v in [('generation','old'),('content_hash','wrong'),('quote','not in body')]:
        bad=deepcopy(q);bad['evidence_sets'][0][0][0][k]=v
        with pytest.raises(ValueError):validate_questions([bad],corpus)
    bad=deepcopy(corpus);bad[0]['body']='changed'
    with pytest.raises(ValueError):validate_corpus(bad)


def test_sealed_partition_projection_has_no_gold_or_other_questions():
    corpus,q,_=fixture()
    qs=[dict(q,id='question-'+str(i),text='Question '+str(i)) for i in range(12)]
    first=partition(qs,'fixed');assert first==partition(qs,'fixed')
    assert {v['split'] for v in first}=={'development','validation','sealed'}
    prompt=episode_input(first[-1],'space')
    assert first[-1]['text'] in prompt and 'evidence_sets' not in prompt
    assert first[-1]['id'] not in prompt and first[0]['text'] not in prompt


def call(citation):
    return {'name':'sources_search','arguments':{'space_id':'space','query':'Orion'},
            'result':{'structuredContent':{'citations':[citation]}}}


def test_hand_computable_multi_document_metrics_duplicates_and_missing_results():
    corpus,q,_=fixture();c=corpus[0]['chunks'][0]
    other=deepcopy(corpus[0]);other['id']='s2';other['url']+='other'
    other['generation']='v2'
    other['chunks'][0]|={'source_id':'s2','chunk_id':'c2','version_id':'v2','document_id':'d2'};corpus.append(other)
    e=deepcopy(q['evidence_sets'][0][0][0]);e|={'document_id':'s2','url':other['url'],'generation':'v2'}
    q['evidence_sets'][0].append([e])
    final={'outcome':'completed','citations':[{k:v for k,v in c.items() if k!='body'}]}
    result=grade(q,final,[call(c),call(c)],corpus)
    assert result['complete_evidence'] is False and result['passage_coverage']==.5
    assert result['rankings']['hit_at_1']==1 and result['rankings']['recall_at_5']==.5
    assert result['rankings']['mrr_at_10']==1
    assert grade(q,final,[],corpus)['invalid_citations']==1
    c2=other['chunks'][0];final['citations'].append({k:v for k,v in c2.items() if k!='body'})
    assert grade(q,final,[call(c),call(c2)],corpus)['complete_evidence'] is True
    q['evidence_sets'].append([[e]])
    final['citations']=final['citations'][1:]
    assert grade(q,final,[call(c2)],corpus)['complete_evidence'] is True


def test_unanswerable_recall_and_disposition_separate():
    corpus,q,_=fixture();q|={'answerability':'unanswerable','evidence_sets':[]}
    result=grade(q,{'outcome':'completed','citations':[]},[],corpus)
    assert result['complete_evidence'] is None and not result['disposition_correct']
    assert result['rankings']['recall_at_10'] is None


def test_boundary_enforces_actual_readonly_annotation_and_space():
    seen=[]
    class Client:
        async def call_tool(self,n,a):
            seen.append(n);return CallToolResult(content=[TextContent(type='text',text='permission_denied')],is_error=True)
    tool=SimpleNamespace(name='read',annotations=SimpleNamespace(read_only_hint=True))
    boundary=ReadBoundary(Client(),[tool],'space')
    for name,args in [('write',{'space_id':'space'}),('read',{}),('read',{'space_id':'other'})]:
        with pytest.raises(RunnerFailure):asyncio.run(boundary.call(name,args))
    asyncio.run(boundary.call('read',{'space_id':'space'}))
    with pytest.raises(RunnerFailure):asyncio.run(boundary.call('read',{'space_id':'space'}))
    assert seen==['read']


def test_budget_exhaustion_resume_and_uncertain_attempt(tmp_path):
    limits={'sessions':2,'tokens':100,'seconds':5,'episode_tokens':60}
    p=tmp_path/'ledger.json';b=Budget(p,limits);assert b.reserve('a')
    with pytest.raises(RuntimeError,match='uncertain'):Budget(p,limits).reserve('a')
    b.finish('a',{},'runner_failure');assert not Budget(p,limits).reserve('a')
    assert b.reserve('b');b.finish('b',{},'runner_failure')
    with pytest.raises(RuntimeError,match='budget'):b.reserve('c')
    assert b.state['tokens']==120


def test_benchmark_material_and_unknown_profile_fields_rejected():
    corpus,q,plan=fixture();validate_plan(plan,corpus,[q['id'],q['text']])
    for key,value in [('synthesis',q['text']),('question_id','question-a')]:
        bad=deepcopy(plan);bad['records'][0][key]=value
        with pytest.raises(ValueError):validate_plan(bad,corpus,[q['id'],q['text']])
    bad=deepcopy(plan);bad['records'][0]['evidence'][0]['generation']='old'
    with pytest.raises(ValueError,match='stale'):validate_plan(bad,corpus)


class LayerAPI:
    def __init__(self):self.pages={};self.annotations={};self.writes=0;self.lose=False;self.receipts={}
    async def __call__(self,name,args):
        if name=='wiki_pages_upsert':
            self.writes+=1;data=args['data'];key=data['idempotency_key']
            if key in self.receipts:return self.receipts[key]
            page={'id':'page','revision':len(self.pages)+1,'content':{'id':'revision',**data}}
            self.pages['page']=page;self.receipts[key]=deepcopy(page)
            if self.lose:self.lose=False;raise ConnectionError('committed reply lost')
            return page
        if name=='wiki_pages_get':return self.pages[args['page_id']]
        if name=='knowledge_annotations_get':return {'revision':int(bool(self.annotations)),'value':self.annotations or None}
        if name=='knowledge_annotations_update':self.writes+=1;self.annotations=args['data']['value'];return {}
        if name=='citations_get':return fixture()[0][0]['chunks'][0]
        raise AssertionError(name)


def test_managed_identity_idempotency_uncertain_replay_and_authored_conflict(tmp_path):
    corpus,q,plan=fixture();api=LayerAPI();state=tmp_path/'state.json'
    async def check():
        dry=await maintain(api,'space',corpus,plan,state)
        assert not state.exists() and api.writes==0 and dry['records'][0]['action']=='create'
        api.lose=True
        with pytest.raises(ConnectionError):await maintain(api,'space',corpus,plan,state,apply=True)
        assert json.loads(state.read_text())['pending']
        await maintain(api,'space',corpus,plan,state,apply=True)
        writes=api.writes
        await maintain(api,'space',corpus,plan,state,apply=True)
        assert api.writes==writes and len(api.pages)==1
        await verify(api,'space',corpus,plan,state)
        api.pages['page']['content']['body']='authored change'
        with pytest.raises(RuntimeError,match='authored'):await maintain(api,'space',corpus,plan,state,apply=True)
    asyncio.run(check())


@pytest.mark.parametrize('limit,kwargs,match',[
    ('model',{'require_model':True},'model'),('context',{'max_context_bytes':1},'context'),
    ('calls',{'max_calls':0},'call budget')])
def test_driver_missing_model_and_hard_budgets_fail_closed(tmp_path,monkeypatch,limit,kwargs,match):
    monkeypatch.setenv('CODEX_HOME',str(tmp_path/'no-config'))
    tool=SimpleNamespace(name='actual_probe',description='Synthetic',input_schema={'type':'object'})
    async def actual(n,a):return CallToolResult(content=[])
    with pytest.raises(RunnerFailure,match=match):
        asyncio.run(evaluate(tools=[tool],instructions='Test',prompt='Probe',call_tool=actual,
            output=tmp_path/'episode',codex=str(fake_codex(tmp_path,'success')),timeout=10,**kwargs))


def test_builder_schema_constrains_logical_identity_counts_and_label_groups():
    from agentic_retrieval.builders import output_schema
    from jsonschema import validate,ValidationError
    corpus,q,plan=fixture()
    validate(plan,output_schema('layer',corpus,3,'test-layer'))
    invalid=deepcopy(plan);invalid['records'][0]['evidence'][0]['document_id']='physical-id'
    with pytest.raises(ValidationError):validate(invalid,output_schema('layer',corpus,3,'test-layer'))
    schema=output_schema('questions',corpus,12,'test-layer')
    assert schema['properties']['answerable']['maxItems']==6
    assert schema['properties']['ambiguous']['minItems']==3
    with pytest.raises(ValidationError):validate({'answerable':[],'ambiguous':[],'unanswerable':[]},schema)


def test_comparison_targets_reject_missing_controls():
    base={'runner_failures':0,'complete_evidence':{'mean':.5},'calls':{'p50':3,'n':1,'mean':3},
          'invalid_citations':0,'product_version_errors':0,'ambiguous':{'n':1,'mean':1},
          'unanswerable':{'n':0,'mean':None},'elapsed_seconds':{'p95':20}}
    candidate=deepcopy(base);candidate['complete_evidence']['mean']=1
    assert 'unanswerable' in accepted(base,candidate,{'complete':.8,'improvement':.1,'disposition':.8,'p95_seconds':180})


def test_derived_metadata_cannot_impersonate_an_original_evidence_read():
    corpus,q,_=fixture();c=corpus[0]['chunks'][0]
    forged={'name':'wiki_pages_get','arguments':{'space_id':'space','page_id':'page'},
        'result':{'structuredContent':{'content':{'metadata':{'citation':c}}}}}
    final={'outcome':'completed','citations':[{k:v for k,v in c.items() if k!='body'}]}
    assert grade(q,final,[forged],corpus)['invalid_citations']==1


def test_labels_freeze_only_after_hash_bound_audit_and_exposed_questions_stay_development():
    from agentic_retrieval.protocol import freeze_labels
    corpus,q,plan=fixture();proposal={'corpus_hash':digest(corpus),'questions_hash':digest([q]),'plan_hash':digest(plan)}
    with pytest.raises(ValueError,match='audit'):freeze_labels(corpus,[q],[q],{},'protocol',digest(plan))
    audit={'proposal_hash':digest(proposal),'reviewed_questions_hash':digest([q]),'approved_for_pilot':True,
           'audit':[{'id':q['id'],'provenance':'provisional analyst read original'}]}
    questions,frozen=freeze_labels(corpus,[q],[q],audit,'protocol',digest(plan))
    assert frozen['questions']==digest(questions)
    revised=[{**q,'previously_exposed':True}];audit['reviewed_questions_hash']=digest(revised)
    questions,_=freeze_labels(corpus,[q],revised,audit,'protocol',digest(plan))
    assert questions[0]['split']=='development'
    audit['reviewed_questions_hash']='tampered'
    with pytest.raises(ValueError):freeze_labels(corpus,[q],revised,audit,'protocol',digest(plan))


def test_wiki_hits_without_original_citations_do_not_break_or_earn_evidence_credit():
    corpus,q,_=fixture();c=corpus[0]['chunks'][0]
    calls=[{'name':'knowledge_search','arguments':{'options':{'space_id':'space','query':'Orion'}},
        'result':{'structuredContent':{'hits':[{'kind':'wiki','citation':None},{'kind':'chunk','citation':c}]}}}]
    final={'outcome':'completed','citations':[{k:v for k,v in c.items() if k!='body'}]}
    result=grade(q,final,calls,corpus)
    assert result['complete_evidence'] and result['citation_validity']==1
    calls[0]['result']['structuredContent']['hits']=calls[0]['result']['structuredContent']['hits'][:1]
    assert grade(q,final,calls,corpus)['invalid_citations']==1


def test_prepared_import_rebinds_only_exact_sources_and_preserves_sealed_partitions(tmp_path):
    from agentic_retrieval.prepared import load_prepared
    corpus,q,plan=fixture();q['split']='sealed'
    (tmp_path/'initial-layer-builder').mkdir()
    for name,value in [('corpus.json',corpus),('questions.json',[q]),('initial-layer-builder/validated.json',plan),
        ('freeze.json',{'corpus':digest(corpus),'questions':digest([q]),'plan':digest(plan)})]:
        (tmp_path/name).write_text(json.dumps(value))
    changed=deepcopy(corpus);changed[0]|={'id':'new-source','generation':'new-version'}
    changed[0]['chunks'][0]|={'source_id':'new-source','version_id':'new-version','document_id':'new-doc','chunk_id':'new-chunk'}
    questions,layer,proof=load_prepared(tmp_path,changed)
    assert questions[0]['text']==q['text'] and questions[0]['split']=='sealed'
    assert layer['records'][0]['evidence'][0]['chunk_id']=='new-chunk'
    assert proof['only_identity_bindings_changed']
    changed[0]['version']='other'
    with pytest.raises(ValueError,match='metadata'):load_prepared(tmp_path,changed)
    exposed=tmp_path/'sealed-0-raw-question-a-0';exposed.mkdir();(exposed/'runner.json').write_text('{}')
    questions,_,proof=load_prepared(tmp_path,corpus)
    assert questions[0]['split']=='development' and proof['previous_test_exposure']
