# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measured fixture ranking, deliberately helpful/unhelpful protocol mocks."""
import json
import os
from pathlib import Path
import time
import httpx2
import pytest
from czero_core.providers import EmbeddingClient, SystemOneClient, ScorerSettings
from czero_core.retrieval import SearchService
from test_embeddings import indexed, search, wiki, sources, access
from test_wiki import create_page

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_fixture_quality_cost_and_latency(indexed):
    store, fixtures, _ = indexed
    wiki_fixture = fixtures[1]
    relevant = {query: set() for query in ('automobile', 'currency')}
    for query, meaning in [('automobile', 'engine maintenance'), ('currency', 'cash transfer')]:
        for i in range(2):
            page = create_page(wiki_fixture, title='Evidence ' + str(i), body=meaning + ' grounded factual evidence')
            relevant[query].add(str(page['content']['id']))
            create_page(wiki_fixture, title='Distractor ' + str(i), body=query + ' unrelated keyword listing')

    calls = []
    def vectors(request):
        body = json.loads(request.content); calls.append(body)
        def vector(value):
            if value == 'automobile' or 'engine maintenance' in value: return [1, 0, 0]
            if value == 'currency' or 'cash transfer' in value: return [0, 1, 0]
            return [0, 0, 1]
        return httpx2.Response(200, json={'model': body['model'], 'data': [
            {'index': i, 'embedding': vector(value)} for i, value in enumerate(body['input'])]})
    store.client = EmbeddingClient(store.client.settings, transport=httpx2.MockTransport(vectors))
    for _ in range(5):
        with store.database.engine.begin() as connection: store._index_batch(connection)
    service = SearchService(store.database, wiki_fixture[0].access, embedding_client=store.client)
    rows = []
    for strategy in ('text', 'semantic', 'hybrid', 'hybrid_helpful', 'hybrid_unhelpful'):
        scorer_calls = []
        def scores(request):
            body = json.loads(request.content); scorer_calls.append(body)
            meaning = 'engine maintenance' if body['state']['query'] == 'automobile' else 'cash transfer'
            helpful = strategy == 'hybrid_helpful'
            return httpx2.Response(200, json={'model': body['model'], 'answers': {'r' + str(i): {'type': 'noul',
                'noul': .9 if ((meaning in candidate['text']) == helpful) else .1}
                for i, candidate in enumerate(body['state']['candidates'])}})
        service.scorer_mode = 'rerank' if strategy.startswith('hybrid_') else 'off'
        service.scorer = SystemOneClient(ScorerSettings('https://scorer.example.test/v1/systemone', 'kev-mock'),
                                        transport=httpx2.MockTransport(scores)) if service.scorer_mode != 'off' else None
        recalls, precisions, evidence, timings, candidates, scored, bytes_sent = [], [], [], [], [], [], []
        for query in relevant:
            before = len(calls); started = time.perf_counter()
            result = service.search(wiki_fixture[1], query, mode=strategy.split('_')[0], limit=2)
            timings.append((time.perf_counter() - started) * 1000)
            assert result['fallback_reason'] is None
            ids = {str(hit['id']) for hit in result['hits']}
            recalls.append(len(ids & relevant[query]) / len(relevant[query]))
            precisions.append(len(ids & relevant[query]) / max(1, len(ids)))
            evidence.append(sum(bool(hit['wiki'] or hit['citation']) for hit in result['hits']) / max(1, len(ids)))
            candidates.append(result['candidate_count']); scored.append(result['scored_count'])
            bytes_sent.append(sum(len(json.dumps(call).encode()) for call in calls[before:]))
        rows.append({'strategy': strategy, 'recall_at_2': sum(recalls) / 2, 'precision_at_2': sum(precisions) / 2,
                     'citation_coverage': sum(evidence) / 2, 'latency_ms_mean': sum(timings) / 2,
                     'candidates_mean': sum(candidates) / 2, 'scored_mean': sum(scored) / 2,
                     'query_embedding_bytes': sum(bytes_sent), 'scorer_request_bytes': sum(len(json.dumps(call).encode()) for call in scorer_calls)})
    by_name = {row['strategy']: row for row in rows}
    assert by_name['text']['recall_at_2'] == 0
    assert by_name['semantic']['recall_at_2'] == 1
    assert by_name['hybrid_helpful']['recall_at_2'] == 1
    assert by_name['hybrid_unhelpful']['recall_at_2'] == 0
    assert all(row['citation_coverage'] == 1 for row in rows)
    output = os.getenv('CZERO_BENCHMARK_OUTPUT')
    if output:
        Path(output).write_text(json.dumps({'fixture': 'eight immutable Wiki revisions; two paraphrase queries; k=2',
            'providers': 'deterministic protocol mocks; no real provider quality or calibration claim', 'results': rows}, indent=2) + '\n')
