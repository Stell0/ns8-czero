# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit local test-extra verification against BEIR's trec_eval dependency."""
import pytest
import pytrec_eval
from c0_beir.metrics import measure


@pytest.mark.parametrize('grades,ranking', [
    ({'a': 3, 'b': 1, 'c': 0}, ['b', 'c', 'a']),
    ({'a': 2, 'b': 4, 'c': 1}, ['c', 'd', 'a']),
    ({'a': 1}, []),
    ({str(i): 1 for i in range(20)}, [str(i) for i in range(10)]),
    ({'a': 1, 'b': 1}, ['z', 'y', 'x', 'b', 'a']),
])
def test_against_beir_reference_evaluator(grades, ranking):
    evaluator = pytrec_eval.RelevanceEvaluator({'q': grades}, {'ndcg_cut.10', 'map_cut.10', 'recall.5,10', 'P.10', 'recip_rank'})
    result = evaluator.evaluate({'q': {doc: float(len(ranking) - rank) for rank, doc in enumerate(ranking)}})['q']
    observed = measure(grades, ranking, len(ranking))
    for ours, reference in [('ndcg_at_10', 'ndcg_cut_10'), ('map_at_10', 'map_cut_10'),
                             ('recall_at_5', 'recall_5'), ('recall_at_10', 'recall_10'),
                             ('precision_at_10', 'P_10'), ('mrr_at_10', 'recip_rank')]:
        assert observed[ours] == pytest.approx(result[reference])
