# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from czero_core.retrieval import SearchLimits,reciprocal_rank_fusion


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
