# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""BEIR/trec_eval document metrics, preserving C0's returned order."""
import math

from c0_benchmark import metrics as binary_metrics


def measure(qrels, documents, chunk_count):
    positive = {key for key, grade in qrels.items() if grade > 0}
    # Reuse the existing benchmark's hit, recall, reciprocal rank and duplicate metrics.
    base = binary_metrics({'relevant': [{'url': key, 'passages': []} for key in positive]},
                          [{'url': '', 'body': ''}] * chunk_count, [{'url': key, 'version': '', 'product': ''} for key in documents])
    output = {key: base[key] for key in ('hit_at_1', 'hit_at_5', 'hit_at_10', 'recall_at_5', 'recall_at_10', 'mrr_at_10')}
    output['duplicate_chunk_rate'] = base['duplicate_document_rate']
    gains = [qrels.get(key, 0) for key in documents[:10]]
    # trec_eval ndcg_cut uses linear graded gains, not 2**grade-1.
    dcg = sum(grade / math.log2(rank + 1) for rank, grade in enumerate(gains, 1))
    ideal = sum(grade / math.log2(rank + 1) for rank, grade in enumerate(sorted(qrels.values(), reverse=True)[:10], 1))
    hits = [key in positive for key in documents[:10]]
    returned = set(documents)
    oracle = sorted((qrels.get(key, 0) for key in returned), reverse=True)[:10]
    output.update(empty_result_rate=float(not documents), distinct_document_count=len(returned),
                  returned_candidate_recall=len(positive & returned) / len(positive),
                  oracle_ndcg_at_10=sum(grade / math.log2(rank + 1) for rank, grade in enumerate(oracle, 1)) / ideal,
                  ndcg_at_10=dcg / ideal, precision_at_10=sum(hits) / 10,
                  map_at_10=sum(sum(hits[:rank]) / rank for rank, hit in enumerate(hits, 1) if hit) / len(positive))
    return output
