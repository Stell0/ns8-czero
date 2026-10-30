# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import copy
import pytest
from c0_ingest.errors import C0Error
from c0_benchmark import (check_corpus,comparator_result,effective,experiment,metrics,
                          normalize,percentile,summarize,validate_questions)


def question():
    return {'id':'q1','text':'How to configure?', 'language':'en','answerability':'answerable',
        'products':['Product'],'versions':['8'],'split':'held_out','confidence':'provisional',
        'label_provenance':'Analyst read the original and retained body before retrieval',
        'relevant':[{'url':'a','content_hash':'hash-a','passages':[['alpha','alternative alpha'],['beta']]},
                    {'url':'b','content_hash':'hash-b','passages':[['gamma']]}]}


def test_hand_computable_multiple_documents_duplicates_missing_and_evidence():
    chunks=[{'url':'x','body':'noise'},{'url':'a','body':'alpha'}, {'url':'a','body':'beta'},{'url':'b','body':'gamma'}]
    docs=[{'url':u,'product':'Product','version':'8'} for u in ('x','a','b')]
    m=metrics(question(),chunks,docs)
    assert m['hit_at_1']==0 and m['hit_at_5']==m['hit_at_10']==1
    assert m['recall_at_5']==m['recall_at_10']==1 and m['mrr_at_10']==.5
    assert m['duplicate_document_rate']==.25 and m['evidence_coverage']==1 and m['complete_evidence']==1
    m=metrics(question(),chunks[:2],docs[:2])
    assert m['recall_at_5']==.5 and m['evidence_coverage']==pytest.approx(1/3)
    m=metrics(question(),[],[])
    assert m['recall_at_10']==m['mrr_at_10']==0 and m['duplicate_document_rate']==0


def test_unanswerable_excludes_recall_and_metadata_errors_are_not_abstention():
    q={**question(),'answerability':'unanswerable','relevant':[]}
    m=metrics(q,[{'url':'x','body':'noise'}],[{'url':'x','product':'Other','version':'14'}])
    assert m['recall_at_5'] is None and m['mrr_at_10'] is None
    assert m['wrong_product_hits']==m['wrong_version_hits']==m['returned_documents']==1


def test_normalization_deduplicates_parent_and_rejects_old_or_foreign_evidence():
    source={'s':{'id':'parent','url':'a','version_id':'v'}}
    hit={'kind':'chunk','id':'c1','citation':{'source_id':'s','version_id':'v','body':'alpha'}}
    chunks,docs=normalize({'hits':[hit,{**hit,'id':'c2'}]},source)
    assert len(chunks)==2 and len(docs)==1 and docs[0]['rank']==1
    for changed in ({'source_id':'foreign'},{'version_id':'old'}):
        with pytest.raises(C0Error,match='outside_corpus'):
            normalize({'hits':[{**hit,'citation':{**hit['citation'],**changed}}]},source)
    with pytest.raises(C0Error,match='unexpected_hit_kind'):normalize({'hits':[{'kind':'wiki_revision'}]},source)


def test_labels_require_current_hashes_and_actual_passages():
    manifest={'documents':[{'url':u,'content_hash':'hash-'+u} for u in ('a','b')]}
    bodies={'a':'alpha alternative alpha beta','b':'gamma'}
    validate_questions([question()],manifest,bodies)
    for field,value in [('content_hash','old'),('passages',[['invented']])]:
        q=question();q['relevant'][0][field]=value
        with pytest.raises(ValueError):validate_questions([q],manifest,bodies)
    with pytest.raises(ValueError,match='question_schema'):validate_questions([question(),question()],manifest,bodies)


def test_drift_fallback_and_percentile():
    check_corpus({'hash':'same'},{'hash':'same'})
    with pytest.raises(C0Error,match='corpus_drift'):check_corpus({'hash':'old'},{'hash':'new'})
    assert effective({'retrieval_method':'hybrid+rerank','fallback_reason':None},'hybrid','rerank')
    assert not effective({'retrieval_method':'text','fallback_reason':'provider_unavailable'},'semantic','off')
    assert not effective({'retrieval_method':'text','fallback_reason':None},'semantic','off')
    assert percentile(list(range(1,21)),.95)==19 and percentile([], .5) is None


def test_repeat_timings_do_not_inflate_quality_n_or_count_fallback():
    row={'status':'measured','answerability':'answerable','split':'held_out','repetition':0,'latency_ms':10,
         'metrics':metrics(question(),[],[])}
    result=summarize([row,{**row,'repetition':1,'latency_ms':20},{**row,'status':'fallback'}])
    assert result['all/answerable']['questions']==1 and result['all/answerable']['latency_samples']==2
    assert result['all/answerable']['p95_ms']==20 and result['development/answerable']['questions']==0


def test_comparator_requires_exact_corpus_and_hashes():
    corpus={'hash':'frozen','documents':[{'id':'a','url':'a','content_hash':'hash-a'}]}
    response={'corpus_hash':'frozen','question_id':'q1','hits':[{'url':'a','content_hash':'hash-a','chunk_id':'c','body':'alpha'}]}
    assert comparator_result(response,corpus,'q1')[1][0]['id']=='a'
    bad=copy.deepcopy(response);bad['hits'][0]['content_hash']='different'
    with pytest.raises(C0Error,match='comparator_corpus_mismatch'):comparator_result(bad,corpus,'q1')
    with pytest.raises(C0Error,match='binding_mismatch'):comparator_result(response,corpus,'q2')


def test_authorization_failure_is_not_a_zero_hit_or_text_fallback(tmp_path,monkeypatch):
    import c0_benchmark as benchmark
    manifest={'documents':[],'hash':'empty'}
    monkeypatch.setattr(benchmark,'snapshot',lambda c:(manifest,{},{}))
    monkeypatch.setattr(benchmark,'validate_questions',lambda *args:None)
    class Client:
        def call(self,name,**kwargs):
            if name=='knowledge_index_status':return {'configured':False}
            raise C0Error('permission_denied')
    config={'modes':[{'mode':'text','rerank':'off'}],'repetitions':1,'limit':10,'max_queries':1}
    with pytest.raises(C0Error,match='permission_denied'):experiment(Client(),config,[question()],manifest,tmp_path)
    import json
    assert json.loads((tmp_path/'status.json').read_text())['comparison_valid'] is False


def test_unconfigured_modes_are_unavailable_without_provider_calls(tmp_path,monkeypatch):
    import c0_benchmark as benchmark
    manifest={'documents':[],'hash':'empty'}
    monkeypatch.setattr(benchmark,'snapshot',lambda c:(manifest,{},{}))
    monkeypatch.setattr(benchmark,'validate_questions',lambda *args:None)
    class Client:
        def call(self,name,**kwargs):
            assert name=='knowledge_index_status';return {'configured':False}
    config={'modes':[{'mode':'semantic','rerank':'off'}],'repetitions':1,'limit':10,'max_queries':1}
    result=experiment(Client(),config,[question()],manifest,tmp_path)
    assert result['query_calls']==0 and result['modes']['semantic+off']['status']=='unavailable'
