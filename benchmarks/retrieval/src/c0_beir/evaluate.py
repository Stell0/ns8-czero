# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only search experiments with complete-corpus guards and durable reports."""
from collections import Counter
from datetime import datetime, timezone
import json
import platform
from pathlib import Path
from importlib.metadata import version
import time
from uuid import uuid4

from c0_benchmark import effective, normalize, percentile
from c0_ingest.errors import C0Error
from c0_ingest.state import atomic, digest
from .corpus import check, index_status
from .metrics import measure


class ReadOnly:
    """Enforce read-only capability annotations before delegating any API call."""
    def __init__(self, client):
        self.client = client

    def __getattr__(self, name):
        return getattr(self.client, name)

    def call(self, name, **arguments):
        if not self.client.operations.get(name, {}).get('read_only'):
            raise C0Error('Evaluation blocked a non-read-only operation')
        return self.client.call(name, **arguments)

    def listing(self, name, field, **arguments):
        rows, offset = [], 0
        while True:
            page = self.call(name, limit=100, offset=offset, **arguments)[field]
            rows.extend(page)
            if len(page) < 100:
                return rows
            offset += len(page)


def table(summary):
    keys = ('ndcg_at_10', 'recall_at_10', 'mrr_at_10', 'recall_at_5', 'precision_at_10',
            'hit_at_1', 'hit_at_5', 'hit_at_10', 'map_at_10', 'duplicate_chunk_rate',
            'empty_result_rate', 'returned_candidate_recall', 'oracle_ndcg_at_10', 'distinct_document_count')
    labels = ('nDCG@10', 'Recall@10', 'MRR@10', 'Recall@5', 'P@10', 'Hit@1', 'Hit@5', 'Hit@10', 'MAP@10', 'Duplicates',
              'Empty rate', 'Returned recall', 'Oracle nDCG@10', 'Distinct docs')
    lines = ['| Requested | Status | Effective | ' + ' | '.join(labels) + ' | P50 ms | P95 ms | Errors | Fallbacks |',
             '|---|---|---|' + '---:|' * (len(keys) + 4)]
    for name, mode in summary['modes'].items():
        values = [f'{mode["metrics"][key]:.4f}' if mode.get('metrics') and key in mode['metrics'] else '—' for key in keys]
        times = [f'{mode[key]:.1f}' if mode.get(key) is not None else '—' for key in ('p50_ms', 'p95_ms')]
        lines.append('| ' + ' | '.join([name, mode['status'], ', '.join(mode.get('effective_modes', {})) or '—',
                                       *values, *times, str(mode.get('errors', 0)), str(mode.get('fallbacks', 0))]) + ' |')
    return '\n'.join(lines)


def report(summary, queries):
    lines = ['# C0 BEIR retrieval benchmark', '', f"Run: `{summary['run_id']}`. Valid corpus: **{summary['corpus_valid']}**.",
             '', f"Dataset: {summary['dataset']} / {summary['split']}; {summary['corpus_count']} documents; "
             f"{summary['query_count']} eligible queries ({summary['all_query_count']} query records).",
             f"Dataset fingerprint: `{summary['dataset_fingerprint']}`. Corpus receipt: `{summary.get('corpus_hash', '')}`.",
             '', table(summary), '', '## Configuration and availability', '',
             '```json', json.dumps({key: summary[key] for key in ('instance', 'config', 'index_before', 'index_after', 'modes', 'ingestion_timings', 'lexical_index_bytes', 'lexical_index_size_status')},
                                   indent=2, sort_keys=True), '```', '', '## Worst queries', '']
    first = [q for q in queries if q.get('repetition') == 0 and q.get('metrics')]
    for mode in summary['modes']:
        lines += ['', '### ' + mode]
        worst = sorted((q for q in first if q['selection'] == mode), key=lambda q: (q['metrics']['ndcg_at_10'], q['query_id']))[:10]
        for q in worst:
            lines.append(f"- `{q['query_id']}` nDCG@10={q['metrics']['ndcg_at_10']:.4f}: "
                         + json.dumps(q['query_text'], ensure_ascii=False) +
                         '; expected=' + json.dumps(q['qrels'], sort_keys=True) + '; retrieved=' + json.dumps(q['documents'][:10]))
    lines += ['', '## Validation and interpretation', '', json.dumps(summary['issues']), '',
              'Quality uses the first request for each eligible query. Any error or fallback invalidates the whole requested mode; partial scores are not comparable. Latency includes all attempted search requests, including errors/fallbacks, and repetitions never change the quality denominator. P50/P95 use nearest rank. First/repeat samples and raw usage remain in queries.jsonl.', '',
              'Metrics use BEIR/trec_eval conventions: linear graded nDCG, positive relevance for binary metrics, precision denominator 10, MAP denominator all relevant documents. No query/document ID exclusion is applied because these are independent ID namespaces. Empty rankings score zero.', '',
              'Coverage is inferred from the public space/profile generation count and verified chunks. It does not prove provider connectivity. Corpus and index identities are checked before/after every mode. A transient remote change restored between checks cannot be ruled out by the public APIs.', '',
              'This measures retrieval, not generated answers, extraction quality or overall assistant quality. Backend cold cache is not established. Fewer than 10 distinct returned documents remain fewer than 10; no padding or additional search engine is used.', '']
    return '\n'.join(lines)


def evaluate(client, dataset, manifest, output, *, modes=('text', 'semantic', 'hybrid'), rerank='off', limit=50, repetitions=1):
    client = ReadOnly(client)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '-' + uuid4().hex[:8]
    output = output / dataset.name / run_id
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    summary = {'format': 1, 'run_id': run_id, 'dataset': dataset.name, 'split': dataset.split,
               'dataset_fingerprint': dataset.fingerprint, 'corpus_count': len(dataset.corpus),
               'query_count': len(dataset.qrels), 'all_query_count': len(dataset.queries), 'corpus_valid': False,
               'config': {'modes': list(modes), 'rerank': rerank, 'limit': limit, 'repetitions': repetitions,
                          'kind': 'source', 'graph_depth': 0,
                          'excluded_wiki_pages': getattr(client,'excluded_wiki_pages',[])},
               'instance': {'url': client.config['url'], 'space_id': client.space_id,
                            'account_id': client.config['account_id'], 'capabilities': client.capabilities,
                            'version': getattr(client, 'benchmark_version', {'status': 'unreported'})},
               'index_before': None, 'index_after': None, 'modes': {}, 'issues': [],
               'ingestion_timings': manifest.get('timings'),
               'lexical_index_bytes': None,  # Not exposed by the read-only public API.
               'lexical_index_size_status': 'unreported',
               'environment': {'python': platform.python_version(), 'benchmark': '0.1.0',
                               'ingestion': version('c0-ingestion-samples'),
                               'mcp': version('mcp'), 'httpx2': version('httpx2'),
                               'tool_source_hash': digest({p.name: digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))})}}
    rows = []
    try:
        sources = {doc['id']: {'id': key, 'version_id': doc['version_id']} for key, doc in manifest['documents'].items()}
        chunks_by_id = {chunk['id']: (doc, chunk) for doc in manifest['documents'].values() for chunk in doc['chunks']}
        if (not modes or len(set(modes)) != len(modes) or any(m not in ('text', 'semantic', 'hybrid') for m in modes)
                or rerank not in ('off', 'rerank', 'filter') or not 10 <= limit <= 50 or not 1 <= repetitions <= 5):
            raise ValueError('Invalid evaluation mode/budget')
        # Preflight every query before sending any search; never silently truncate.
        if any(not 1 <= len(dataset.queries[qid]) <= 512 for qid in dataset.qrels):
            raise ValueError('BEIR query exceeds the C0 512-character search bound')
        summary['corpus_hash'] = check(client, dataset, manifest)
        initial = index_status(client, manifest)
        summary['index_before'] = initial
        with (output / 'queries.jsonl').open('x', encoding='utf-8') as query_file, (output / 'rankings.jsonl').open('x', encoding='utf-8') as ranking_file:
            for mode in modes:
                selection = mode + '+' + rerank
                entry = {'requested_mode': mode, 'requested_rerank': rerank, 'status': 'unavailable',
                         'metrics': None, 'errors': 0, 'fallbacks': 0, 'effective_modes': {}, 'provider_usage': {}}
                summary['modes'][selection] = entry
                check(client, dataset, manifest, full=False)
                status = index_status(client, manifest)
                if mode != 'text' and not status['coverage_ready']:
                    entry['reason'] = 'embedding_index_incomplete' if status['configured'] else 'embeddings_not_configured'
                    continue
                if mode != 'text' and status != initial:
                    raise C0Error('Embedding profile/coverage changed during benchmark')
                measured, latencies, methods, usage = [], [], Counter(), Counter()
                for number, qid in enumerate(sorted(dataset.qrels), 1):
                    for repetition in range(repetitions):
                        row = {'query_id': qid, 'query_text': dataset.queries[qid], 'qrels': dataset.qrels[qid],
                               'selection': selection, 'repetition': repetition, 'requested_mode': mode,
                               'requested_rerank': rerank}
                        started = time.perf_counter()
                        try:
                            result = client.call('knowledge_search', options={'query': dataset.queries[qid], 'mode': mode,
                                'rerank': rerank, 'limit': limit, 'kind': 'source', 'graph_depth': 0})
                        except C0Error:
                            entry['errors'] += 1
                            row.update(status='error', error='C0 search rejected or unavailable; inspect credentials/authority/provider', metrics=None)
                            # Denial/uncertain transport is never treated as zero hits; stop further calls.
                            raise
                        finally:
                            row['latency_ms'] = (time.perf_counter() - started) * 1000
                            latencies.append(row['latency_ms'])
                            if row.get('status') == 'error':
                                rows.append(row)
                                query_file.write(json.dumps(row, sort_keys=True) + '\n'); query_file.flush()
                        chunks, documents = normalize(result, sources)
                        for hit in [p for h in result['hits'] for p in [h,*h.get('supporting_passages',[])]]:
                            citation = hit['citation']
                            expected = chunks_by_id.get(citation['chunk_id'])
                            if not expected:
                                raise C0Error('Search citation chunk outside verified corpus')
                            doc, chunk = expected
                            if (hit['id'] != citation['chunk_id'] or doc['document_id'] != citation['document_id']
                                    or doc['id'] != citation['source_id'] or doc['version_id'] != citation['version_id']
                                    or digest(citation['body'].encode()) != chunk['content_hash']
                                    or citation['start_offset'] != chunk['start_offset'] or citation['end_offset'] != chunk['end_offset']):
                                raise C0Error('Search citation differs from verified chunk')
                        ranking = [doc['id'] for doc in documents]
                        valid = effective(result, mode, rerank) and not result.get('fallback_reasons')
                        entry['fallbacks'] += not valid
                        methods[result['retrieval_method']] += 1
                        for provider, counters in result.get('provider_usage', {}).items():
                            for key, value in counters.items():
                                usage[provider + '.' + key] += value
                        row.update(status='measured' if valid else 'fallback', effective_mode=result['retrieval_method'],
                                   lexical_strategy=result.get('lexical_strategy'),
                                   lexical_ranker_version=result.get('lexical_ranker_version'), fallback_reason=result.get('fallback_reason'),
                                   fallback_reasons=result.get('fallback_reasons', []), candidate_count=result.get('candidate_count'),
                                   scored_count=result.get('scored_count'), scorer_truncated_candidates=result.get('scorer_truncated_candidates'),
                                   provider_usage=result.get('provider_usage', {}), documents=ranking,
                                   metrics=measure(dataset.qrels[qid], ranking, sum(not c.get('supporting') for c in chunks)) if valid and repetition == 0 else None)
                        rows.append(row)
                        query_file.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n'); query_file.flush()
                        ranking_file.write(json.dumps({'query_id': qid, 'selection': selection, 'repetition': repetition,
                            'documents': documents, 'chunks': chunks, 'raw_hits': result['hits']}, sort_keys=True, ensure_ascii=False) + '\n'); ranking_file.flush()
                        if repetition == 0:
                            measured.append(row)
                    if number % 25 == 0 or number == len(dataset.qrels):
                        print(f'{selection}: searched {number}/{len(dataset.qrels)} queries', flush=True)
                check(client, dataset, manifest, full=False)
                if mode != 'text' and index_status(client, manifest) != initial:
                    raise C0Error('Embedding profile/coverage changed during evaluation')
                entry.update(status='valid' if not entry['fallbacks'] else 'invalid_fallback',
                             effective_modes=dict(methods), provider_usage=dict(usage), latency_samples=len(latencies),
                             p50_ms=percentile(latencies, .5), p95_ms=percentile(latencies, .95),
                             quality_queries=len(measured))
                if entry['status'] == 'valid':
                    entry['metrics'] = {key: sum(row['metrics'][key] for row in measured) / len(measured) for key in measured[0]['metrics']}
        check(client, dataset, manifest)
        summary['index_after'] = index_status(client, manifest)
        if summary['index_after'] != initial:
            raise C0Error('Index configuration/coverage changed during evaluation; comparison invalid')
        summary['corpus_valid'] = True
    except (C0Error, ValueError, KeyError, TypeError) as exc:
        # C0Error diagnostics are value-free. Never serialize transport exception text.
        summary['issues'].append(str(exc) if isinstance(exc, (C0Error, ValueError)) else 'Malformed manifest or API response')
        for entry in summary['modes'].values():
            entry.update(status='invalid_run', metrics=None)
        raise
    finally:
        for selection, entry in summary['modes'].items():
            selected = [row for row in rows if row['selection'] == selection]
            times = [row['latency_ms'] for row in selected]
            entry.update(latency_samples=len(times), p50_ms=percentile(times, .5), p95_ms=percentile(times, .95),
                         effective_modes=dict(Counter(row['effective_mode'] for row in selected if 'effective_mode' in row)))
        for filename in ('queries.jsonl', 'rankings.jsonl'):
            (output / filename).touch(exist_ok=True)
        summary['comparison_valid'] = summary['corpus_valid'] and all(m['status'] == 'valid' for m in summary['modes'].values())
        summary['report_fingerprint'] = digest({k: v for k, v in summary.items() if k != 'run_id'})
        atomic(output / 'summary.json', summary)
        atomic(output / 'report.md', report(summary, rows).encode())
        print(table(summary), flush=True)
        print('Saved run: ' + str(output), flush=True)
    return summary
