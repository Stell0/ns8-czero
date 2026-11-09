# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from czero_core.retrieval import SearchLimits,reciprocal_rank_fusion
from czero_core.retrieval import scorer_text


def test_rrf_rewards_shared_candidates_and_ignores_duplicate_rank_rows():
    hit=lambda key:{'kind':'chunk','id':key,'score':1.}
    a,b,c=hit('a'),hit('b'),hit('c')
    result=reciprocal_rank_fusion([a,a,b],[b,c])
    assert [h['id'] for h in result]==['b','a','c']
    assert result[0]['score']==pytest.approx(1/62+1/61)
    assert len(result)==3
    assert reciprocal_rank_fusion([b,a],[a,b])==reciprocal_rank_fusion([a,b],[b,a])


@pytest.mark.parametrize('options',[{'max_limit':True},{'max_limit':51},{'max_limit':20,'candidates':10},
    {'candidates':65},{'graph_depth':4},{'graph_depth':True},{'scorer_candidates':17}])
def test_retrieval_administrator_caps_are_bounded(options):
    with pytest.raises(ValueError):SearchLimits(**options)


def passage(key, start=0, body='evidence', kind='chunk'):
    return {'id':key,'kind':kind,'resource_id':'document','revision':1,'title':'Title',
        'content_hash':'hash','excerpt':body,'start_offset':start,'end_offset':start+len(body),
        'citation':{'document_id':'extracted'} if kind=='chunk' else None,'wiki':None}


@pytest.mark.parametrize('kind',['chunk','wiki_revision'])
def test_document_fusion_preserves_distinct_semantic_passage_and_original_scores(kind):
    first=passage('same' if kind=='wiki_revision' else 'lexical',body='general introduction',kind=kind)
    semantic=passage('same' if kind=='wiki_revision' else 'semantic',start=2000,body='precise procedure',kind=kind)
    result,=reciprocal_rank_fusion([first,first],[semantic,semantic],document_level=True)
    assert result['score']==pytest.approx(2/61)
    assert result['id']==first['id'] and result['excerpt']==first['excerpt']
    assert result['supporting_passages']==[semantic]
    assert 'supporting_passages' not in first


def test_fusion_deduplicates_covered_excerpts_and_caps_support():
    first=passage('a',body='x'*1200)
    overlap=passage('b',start=100,body='x'*1000)
    assert 'supporting_passages' not in reciprocal_rank_fusion([first],[overlap],document_level=True)[0]
    second=passage('c',start=2000,body='precise procedure')
    third=passage('d',start=4000,body='other procedure')
    result,=reciprocal_rank_fusion([first],[second],[third],document_level=True)
    assert result['supporting_passages']==[second]


def test_partial_overlap_cannot_discard_a_unique_procedure_at_the_end():
    first=passage('a',body='x'*1200)
    semantic=passage('b',start=100,body='x'*1100+'recovery command')
    result,=reciprocal_rank_fusion([first],[semantic],document_level=True)
    assert 'recovery command' in result['supporting_passages'][0]['excerpt']


def test_scorer_reserves_bytes_for_semantic_evidence_without_increasing_provider_caps():
    hit=passage('a',body='字'*1200)
    hit['supporting_passages']=[passage('b',start=5000,body='precise procedure')]
    value=scorer_text(hit)
    assert 'precise procedure' in value and len(value.encode())<=2048
