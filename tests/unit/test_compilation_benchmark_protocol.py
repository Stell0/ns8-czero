# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""No model: independent review bindings, incomplete denominators and failure retention."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'scripts'),str(ROOT/'tests')]
from agentic_retrieval.audit import answer_audit
from agentic_retrieval.compiler import review_plan
from agentic_retrieval.protocol import digest
from test_agentic_retrieval_protocol import fixture


def study(tmp_path):
    corpus,question,plan = fixture()
    frozen = {'corpus':digest(corpus),'questions':digest([question])}
    final = {'answer':'Orion uses port 7443.','outcome':'completed',
        'parts':[{'statement':'Orion uses port 7443.','chunk_ids':['c']}], 'citations':[]}
    row = {'status':'measured','question_id':question['id'],'answerability':'answerable',
        'grade':{'observed_original_chunks':['c'],'invalid_citations':0,'product_errors':0,'version_errors':0},
        'runner':{'final':final}}
    values = {'corpus':corpus,'questions':[question],'freeze':frozen}
    for name,value in values.items():(tmp_path/(name+'.json')).write_text(json.dumps(value))
    destination = tmp_path/'development-0-enriched-question-a-0';destination.mkdir()
    (destination/'episode.json').write_text(json.dumps(row))
    reviews = {'freeze_hash':digest(frozen),'provenance':'Source-based independent fixture analyst',
        'independent_of_producer':True,'episodes':[{'episode':destination.name,'episode_hash':digest(row),
            'all_assertions_reviewed':True,'correct':True,'rationale':'Exact current original states the port.',
            'assertions':[{'text':'Orion uses port 7443.','verdict':'supported','chunk_ids':['c']}]}]}
    return corpus,plan,row,reviews,destination


def test_independent_answer_audit_is_distinct_from_evidence_and_retains_missing_failures(tmp_path):
    _,_,row,reviews,_ = study(tmp_path)
    other = tmp_path/'development-0-raw-question-a-0';other.mkdir()
    (other/'episode.json').write_text(json.dumps(row))
    failed = tmp_path/'sealed-0-raw-question-b-0';failed.mkdir()
    (failed/'episode.json').write_text(json.dumps({'status':'runner_failure','failure':'budget_exhausted'}))
    result = answer_audit(tmp_path,reviews)
    assert result['summary']['episodes'] == 3 and result['summary']['runner_failures'] == 1
    assert result['summary']['reviewed'] == 1 and result['summary']['unreviewed'] == 1
    assert result['summary']['accuracy'] == 1 and result['summary']['accuracy_n'] == 1
    assert result['arms']['raw']['accuracy'] is None and result['arms']['enriched']['reviewed_assertions'] == 1
    assert result['monetary_cost'] is None and 'not independent human' in result['judgment']
    assert 'Orion uses port' not in json.dumps(result)


@pytest.mark.parametrize('fault',[
    'freeze','question','episode','producer','duplicate','missing','incomplete',
    'unobserved','no-support','invented-text','empty','wrong-verdict','unsupported-correct','uncertain-correct'])
def test_answer_audit_fails_closed_on_unbound_or_unsupported_judgments(tmp_path,fault):
    _,_,row,reviews,path = study(tmp_path);review = reviews['episodes'][0];assertion = review['assertions'][0]
    if fault == 'freeze':reviews['freeze_hash'] = 'changed'
    elif fault == 'question':(tmp_path/'questions.json').write_text('[]')
    elif fault == 'episode':row['runner']['final']['answer'] = 'changed';(path/'episode.json').write_text(json.dumps(row))
    elif fault == 'producer':reviews['independent_of_producer'] = False
    elif fault == 'duplicate':reviews['episodes'].append(deepcopy(review))
    elif fault == 'missing':review['episode'] = 'not-an-episode'
    elif fault == 'incomplete':review['all_assertions_reviewed'] = False
    elif fault == 'unobserved':assertion['chunk_ids'] = ['unknown']
    elif fault == 'no-support':assertion['chunk_ids'] = []
    elif fault == 'invented-text':assertion['text'] = 'An assertion absent from the answer'
    elif fault == 'empty':review['assertions'] = []
    elif fault == 'wrong-verdict':assertion['verdict'] = 'automatically_verified'
    elif fault == 'unsupported-correct':assertion['verdict'] = 'unsupported'
    elif fault == 'uncertain-correct':assertion['verdict'] = 'uncertain'
    with pytest.raises(ValueError):answer_audit(tmp_path,reviews)


@pytest.mark.parametrize('verdict,correct',[('unsupported',False),('uncertain',None)])
def test_wrong_and_unknown_answers_are_reported_without_becoming_correct(tmp_path,verdict,correct):
    _,_,_,reviews,_ = study(tmp_path)
    reviews['episodes'][0]['correct'] = correct
    reviews['episodes'][0]['assertions'][0]['verdict'] = verdict
    result = answer_audit(tmp_path,reviews)['summary']
    assert result['unsupported_assertions'] == (verdict == 'unsupported')
    assert result['uncertain_assertions'] == (verdict == 'uncertain')
    assert result['accuracy'] == (0 if correct is False else None)
    assert result['unknown'] == (correct is None)


def test_source_plan_review_binds_exact_complete_records_without_question_inputs():
    corpus,_,plan = fixture()
    review = {'corpus_hash':digest(corpus),'plan_hash':digest(plan),'provenance':'source-based analyst',
        'records':[{'key':r['key'],'source_supported':True,'uncertainty_preserved':True} for r in plan['records']]}
    review_plan(review,corpus,plan)
    for field in ('corpus_hash','plan_hash'):
        bad = {**review,field:'changed'}
        with pytest.raises(ValueError,match='review_missing_or_changed'):review_plan(bad,corpus,plan)
    bad = {**review,'records':[]}
    with pytest.raises(ValueError,match='review_incomplete'):review_plan(bad,corpus,plan)
    with pytest.raises(ValueError):review_plan({**review,'questions':['forbidden']},corpus,plan)


def test_measured_citation_denominator_and_observed_model_events_stay_separate():
    from agentic_retrieval.protocol import summary
    row = {'status':'measured','answerability':'answerable','grade':{'complete_evidence':False,
        'passage_coverage':0,'invalid_citations':1,'product_errors':0,'version_errors':0,
        'rankings':{k:0 for k in ('hit_at_1','hit_at_5','hit_at_10','recall_at_5','recall_at_10','mrr_at_10','duplicate_document_rate')}},
        'runner':{'calls':2,'context_bytes':100,'elapsed_seconds':1,'usage_events':3,
            'final':{'citations':[{},{}]}}}
    result = summary([row])
    assert result['submitted_citations'] == 2 and result['citation_validity'] == .5
    assert result['model_usage_events'] == 3 and result['calls']['mean'] == 2
    row['runner']['final']['citations'] = [];row['grade']['invalid_citations'] = 0
    assert summary([row])['citation_validity'] is None
