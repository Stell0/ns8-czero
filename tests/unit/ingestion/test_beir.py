# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic BEIR fixtures and real shared client over a deterministic fake transport."""
import copy
import json
import math
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'benchmarks/retrieval/src'))
from c0_ingest.auth import credentials
from c0_ingest.client import C0
from c0_ingest.errors import C0Error
from c0_ingest.state import digest, read
from c0_beir.cli import main
from c0_beir.corpus import check, ingest, load_manifest
from c0_beir.dataset import cached, extract, load
from c0_beir.evaluate import ReadOnly, evaluate, report
from c0_beir.metrics import measure

CONFIG = {'url': 'https://c0.example.org/mcp', 'account_id': 'account', 'identity': 'Alice', 'auth_mode': 'api_key'}


@pytest.fixture
def dataset_path(tmp_path):
    path = tmp_path / 'fixture'
    (path / 'qrels').mkdir(parents=True)
    corpus = [{'_id': 'a', 'title': 'Alpha title', 'text': 'First original body'},
              {'_id': 'b', 'title': '', 'text': 'Second original body'},
              {'_id': 'c', 'title': 'Gamma', 'text': 'Third body'}]
    (path / 'corpus.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in corpus))
    (path / 'queries.jsonl').write_text(json.dumps({'_id': 'q1', 'text': 'Original query'}) + '\n' +
                                      json.dumps({'_id': 'unused', 'text': 'Not in test split'}) + '\n')
    (path / 'qrels/test.tsv').write_text('query-id\tcorpus-id\tscore\nq1\ta\t3\nq1\tb\t1\nq1\tc\t0\n')
    return path


class Transport:
    def __init__(self):
        self.sources = {}; self.versions = {}; self.documents = {}; self.chunks = {}; self.receipts = {}
        self.calls = []; self.write_calls = 0; self.fail_after_commit = False; self.fail_before_commit = False
        self.shared = False; self.role = 'editor'; self.account = 'account'; self.denied = False
        self.wiki = []; self.fallback = False; self.configured = True; self.coverage = True
        self.chunk_duplicates = True; self.queued = False; self.search_error = False; self.drift_on_search = False
        self.method = None

    def resource(self, uri):
        names = ('get_profile', 'spaces_get', 'sources_list', 'sources_get', 'wiki_pages_list',
                 'source_versions_list', 'documents_get', 'document_chunks_list', 'knowledge_index_status', 'knowledge_search', 'sources_ingest_text')
        return {'version': 'synthetic', 'operations': [{'name': name, 'read_only': name != 'sources_ingest_text',
            'input_schema': {'properties': {} if name in ('get_profile', 'knowledge_search') else {'space_id': {}}}} for name in names]}

    def close(self):
        pass

    def call(self, name, args):
        self.calls.append((name, copy.deepcopy(args)))
        value = self.dispatch(name, args)
        return {'structuredContent': copy.deepcopy(value)}

    def dispatch(self, name, args):
        if self.denied:
            raise C0Error('permission_denied')
        if name == 'get_profile': return {'id': self.account, 'nickname': 'Alice'}
        if name == 'spaces_get': return {'shared': self.shared, 'role': self.role}
        if name == 'wiki_pages_list': return {'pages': self.wiki}
        if name == 'sources_list': return {'sources': list(self.sources.values())[args['offset']:args['offset'] + args['limit']]}
        if name == 'sources_get': return self.sources[args['source_id']]
        if name == 'source_versions_list': return {'versions': [self.versions[args['source_id']]]}
        if name == 'documents_get': return next(d for d in self.documents.values() if d['version_id'] == args['version_id'])
        if name == 'document_chunks_list': return {'chunks': [self.chunks[args['document_id']]]}
        if name == 'knowledge_index_status':
            return {'configured': self.configured, 'profile_id': 'profile' if self.configured else None,
                    'generation': 1, 'model': 'synthetic', 'indexed': len(self.chunks) if self.coverage else 0}
        if name == 'sources_ingest_text':
            self.write_calls += 1
            if self.fail_before_commit:
                self.fail_before_commit = False
                raise C0Error('MCP call failed; reconcile the operation before retrying')
            request = args['data']; key = request['idempotency_key']
            if key in self.receipts: return self.receipts[key]
            source = 'source-' + request['metadata']['beir_id']; version = 'version-' + source; doc = 'doc-' + source
            self.sources[source] = {'id': source, 'title': request['title'], 'metadata': request['metadata'], 'revision': 1, 'deleted': False}
            self.versions[source] = {'id': version, 'source_id': source, 'content_hash': digest(request['body'].encode()),
                                     'state': 'queued' if self.queued else 'ready'}
            self.documents[doc] = {'id': doc, 'version_id': version, 'body': request['body'], 'text_hash': digest(request['body'].encode())}
            self.chunks[doc] = {'id': 'chunk-' + source, 'document_id': doc, 'body': request['body'],
                                'content_hash': digest(request['body'].encode()), 'start_offset': 0, 'end_offset': len(request['body'])}
            self.receipts[key] = self.versions[source]
            if self.fail_after_commit:
                self.fail_after_commit = False
                raise C0Error('MCP call failed; reconcile the operation before retrying')
            return self.versions[source]
        if name == 'knowledge_search':
            assert args['options']['space_id'] == 'protected'
            assert args['options']['kind'] == 'source' and args['options']['graph_depth'] == 0
            if self.search_error: raise C0Error('permission_denied')
            mode = args['options']['mode']; rerank = args['options']['rerank']
            hits = []
            for key in ('b', 'b', 'a') if self.chunk_duplicates else ('b', 'a'):
                source = 'source-' + key; doc = self.documents['doc-' + source]; chunk = self.chunks[doc['id']]
                hits.append({'id': chunk['id'], 'kind': 'chunk', 'score': .4, 'citation': {
                    **chunk, 'chunk_id': chunk['id'], 'source_id': source, 'version_id': doc['version_id']}})
            if self.drift_on_search: self.sources['source-c']['revision'] += 1
            return {'hits': hits, 'retrieval_method': self.method or ('text' if self.fallback else mode + ('+' + rerank if rerank != 'off' else '')),
                    'fallback_reason': 'embedding_timeout' if self.fallback else None,
                    'fallback_reasons': ['embedding_timeout'] if self.fallback else [], 'lexical_strategy': 'relaxed',
                    'candidate_count': 3, 'scored_count': 0, 'provider_usage': {'embedding': {'tokens': 2}}}
        raise AssertionError(name)


def client(transport=None):
    result = C0(CONFIG, transport=transport or Transport())
    result.select_space('protected')
    return result


@pytest.fixture
def prepared(dataset_path, tmp_path):
    dataset = load(dataset_path)
    api = client()
    path = tmp_path / 'manifest.json'
    manifest = ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    return dataset, api, path, manifest


def test_dataset_format_fingerprint_and_grades(dataset_path):
    dataset = load(dataset_path)
    assert dataset.qrels['q1'] == {'a': 3, 'b': 1, 'c': 0}
    assert dataset.body('a') == 'Alpha title\n\nFirst original body'
    lines = (dataset_path / 'corpus.jsonl').read_text().splitlines()
    (dataset_path / 'corpus.jsonl').write_text('\n'.join(reversed(lines)) + '\n')
    assert load(dataset_path).fingerprint == dataset.fingerprint
    (dataset_path / 'corpus.jsonl').write_text('\n'.join(lines).replace('First', 'Changed') + '\n')
    assert load(dataset_path).fingerprint != dataset.fingerprint


@pytest.mark.parametrize('file,body', [
    ('corpus.jsonl', '{"_id":"a","title":"","text":"ok"}\n{"_id":"a","title":"","text":"again"}\n'),
    ('queries.jsonl', '{"_id":7,"text":"bad"}\n'),
    ('queries.jsonl', '{"_id":"q1","text":null}\n'),
    ('corpus.jsonl', 'not json\n'),
    ('qrels/test.tsv', 'query-id\tcorpus-id\tscore\nq1\tmissing\t1\n'),
    ('qrels/test.tsv', 'query-id\tcorpus-id\tscore\nmissing\ta\t1\n'),
    ('qrels/test.tsv', 'query-id\tcorpus-id\tscore\nq1\ta\t1\nq1\ta\t2\n'),
    ('qrels/test.tsv', 'query-id\tcorpus-id\tscore\nq1\ta\t-1\n')])
def test_reject_bad_datasets(dataset_path, file, body):
    (dataset_path / file).write_text(body)
    with pytest.raises(ValueError): load(dataset_path)


def test_cache_and_safe_extraction(dataset_path, tmp_path, monkeypatch):
    target = tmp_path / 'cache/scifact'
    import shutil
    shutil.copytree(dataset_path, target)
    monkeypatch.setattr('c0_beir.dataset.open_url', lambda *a, **kw: pytest.fail('Redownloaded valid cache'))
    assert cached('scifact', target.parent) == target
    for name in ('../escape', '/scifact/absolute', 'scifact/../escape', 'scifact/evil\\path'):
        archive = tmp_path / 'evil.zip'
        with zipfile.ZipFile(archive, 'w') as zipped: zipped.writestr(name, 'bad')
        with pytest.raises(ValueError): extract(archive, tmp_path / 'out', 'scifact')
    with zipfile.ZipFile(archive, 'w') as zipped:
        link = zipfile.ZipInfo('scifact/link'); link.external_attr = 0o120777 << 16
        zipped.writestr(link, '/tmp')
    with pytest.raises(ValueError): extract(archive, tmp_path / 'out', 'scifact')


def test_idempotent_and_complete_mapping(prepared):
    dataset, api, path, manifest = prepared
    writes = api.transport.write_calls
    again = ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    assert api.transport.write_calls == writes == 3
    assert again['documents'] == manifest['documents']
    assert manifest['complete'] and manifest['index']['coverage_ready']
    assert manifest['documents']['a']['id'] == 'source-a'
    assert load_manifest(path, api, dataset)['binding']['fingerprint'] == dataset.fingerprint


@pytest.mark.parametrize('when', ['fail_before_commit', 'fail_after_commit'])
def test_resume_uncertain_write_without_duplicates(dataset_path, tmp_path, when):
    dataset = load(dataset_path); api = client(); path = tmp_path / 'resume.json'
    setattr(api.transport, when, True)
    with pytest.raises(C0Error): ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    assert read(path)['pending'] == 'a'
    manifest = ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    assert manifest['complete'] and len(api.transport.sources) == 3
    assert api.transport.write_calls == (4 if when == 'fail_before_commit' else 3)


def test_resume_after_extraction_wait(dataset_path, tmp_path):
    api = client(); api.transport.queued = True; dataset = load(dataset_path); path = tmp_path / 'resume.json'
    with pytest.raises(C0Error): ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    api.transport.queued = False
    assert set(read(path)['submitted']) == {'a', 'b', 'c'}
    assert not read(path)['documents'] and read(path)['pending'] is None
    for version in api.transport.versions.values():
        version['state'] = 'ready'
    assert ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)['complete']
    assert api.transport.write_calls == 3


def test_fingerprint_mismatch_and_oversize_are_zero_write(prepared, dataset_path, tmp_path):
    dataset, api, path, manifest = prepared; writes = api.transport.write_calls
    dataset.fingerprint = 'changed'
    with pytest.raises(C0Error): ingest(api, dataset, path)
    dataset.corpus['c']['text'] = 'é' * 131072
    with pytest.raises(ValueError): ingest(api, dataset, tmp_path / 'large.json')
    assert api.transport.write_calls == writes


@pytest.mark.parametrize('drift', ['missing', 'additional', 'changed', 'unready', 'metadata', 'chunk', 'wiki', 'revision'])
def test_corpus_drift_rejected(prepared, drift):
    dataset, api, path, manifest = prepared; transport = api.transport
    if drift == 'missing': del transport.sources['source-a']
    if drift == 'additional': transport.sources['unrelated'] = {'metadata': {}}
    if drift == 'changed': transport.documents['doc-source-a']['body'] = 'changed'
    if drift == 'unready': transport.versions['source-a']['state'] = 'queued'
    if drift == 'metadata': transport.sources['source-a']['metadata']['content_sha256'] = 'changed'
    if drift == 'chunk': transport.chunks['doc-source-a']['id'] = 'changed'
    if drift == 'wiki': transport.wiki = [{'id': 'unrelated'}]
    if drift == 'revision': transport.sources['source-a']['revision'] += 1
    with pytest.raises(C0Error): check(api, dataset, manifest)


def test_incomplete_manifest_rejected(prepared):
    dataset, api, path, manifest = prepared
    manifest['complete'] = False
    with pytest.raises(C0Error): check(api, dataset, manifest)


def test_evaluation_is_readonly_deduplicates_and_writes_reports(prepared, tmp_path):
    dataset, api, path, manifest = prepared; writes = api.transport.write_calls
    result = evaluate(api, dataset, manifest, tmp_path / 'runs', repetitions=2)
    assert api.transport.write_calls == writes
    assert result['comparison_valid']
    for mode in result['modes'].values():
        assert mode['quality_queries'] == 1 and mode['latency_samples'] == 2
        assert mode['metrics']['duplicate_chunk_rate'] == pytest.approx(1/3)
        assert mode['metrics']['recall_at_10'] == 1
    output = next((tmp_path / 'runs/scifact').iterdir())
    assert {p.name for p in output.iterdir()} == {'summary.json', 'queries.jsonl', 'rankings.jsonl', 'report.md'}
    rows = [json.loads(line) for line in (output / 'queries.jsonl').read_text().splitlines()]
    ranking = json.loads((output / 'rankings.jsonl').read_text().splitlines()[0])
    assert rows[0]['documents'] == ['b', 'a']
    assert [row['id'] for row in ranking['chunks']] == ['b', 'b', 'a']
    assert ranking['raw_hits'][0]['score'] == .4
    assert report(result, rows) == (output / 'report.md').read_text()
    evaluate(api, dataset, manifest, tmp_path / 'runs', modes=['text'])
    assert len(list((tmp_path / 'runs/scifact').iterdir())) == 2
    with pytest.raises(C0Error): ReadOnly(api).call('sources_ingest_text')


@pytest.mark.parametrize('state', ['unconfigured', 'incomplete', 'fallback', 'wrong_method'])
def test_provider_unavailability_never_scores_semantic(prepared, tmp_path, state):
    dataset, api, path, manifest = prepared
    if state == 'unconfigured': api.transport.configured = False
    if state == 'incomplete': api.transport.coverage = False
    if state == 'fallback': api.transport.fallback = True
    if state == 'wrong_method': api.transport.method = 'text'
    result = evaluate(api, dataset, manifest, tmp_path / 'runs', modes=['semantic'])
    assert not result['comparison_valid'] and result['corpus_valid']
    mode = result['modes']['semantic+off']
    assert mode['metrics'] is None
    assert mode['status'] == ('unavailable' if state in ('unconfigured', 'incomplete') else 'invalid_fallback')


def test_search_denial_preserves_invalid_report(prepared, tmp_path):
    dataset, api, path, manifest = prepared; api.transport.search_error = True
    with pytest.raises(C0Error): evaluate(api, dataset, manifest, tmp_path / 'runs')
    result = read(next((tmp_path / 'runs/scifact').iterdir()) / 'summary.json')
    assert not result['comparison_valid'] and result['modes']['text+off']['errors'] == 1


def test_drift_during_queries_invalidates_run(prepared, tmp_path):
    dataset, api, path, manifest = prepared; api.transport.drift_on_search = True
    with pytest.raises(C0Error): evaluate(api, dataset, manifest, tmp_path / 'runs')
    result = read(next((tmp_path / 'runs/scifact').iterdir()) / 'summary.json')
    assert not result['comparison_valid'] and not result['corpus_valid']


def test_metrics_exact_linear_graded_and_empty():
    grades = {'a': 3, 'b': 1, 'c': 0}
    result = measure(grades, ['b', 'c', 'a'], 4)
    assert result['ndcg_at_10'] == pytest.approx((1 + 3/2) / (3 + 1/math.log2(3)))
    assert result['map_at_10'] == pytest.approx((1 + 2/3)/2)
    assert result['precision_at_10'] == .2 and result['mrr_at_10'] == 1
    assert result['duplicate_chunk_rate'] == .25
    assert measure(grades, [], 0)['ndcg_at_10'] == 0
    long = {str(i): 1 for i in range(20)}
    assert measure(long, list(long)[:10], 10)['map_at_10'] == .5
    assert measure(grades, ['c', 'b'], 2)['mrr_at_10'] == .5


def test_authentication_and_authorization(monkeypatch):
    monkeypatch.delenv('C0_API_KEY', raising=False)
    with pytest.raises(C0Error): credentials(CONFIG)
    monkeypatch.setenv('C0_API_KEY', 'c0k_' + 'a'*43)
    assert credentials(CONFIG).startswith('c0k_')
    transport = Transport(); transport.account = 'wrong'
    with pytest.raises(C0Error): client(transport)
    for change in ('shared', 'role', 'denied'):
        transport = Transport()
        setattr(transport, change, 'reader' if change == 'role' else True)
        with pytest.raises(C0Error): client(transport)


def test_cli_default_commands_and_private_config(prepared, tmp_path, monkeypatch):
    dataset, api, path, manifest = prepared
    private = tmp_path / '.local/benchmark'; private.mkdir(parents=True)
    config = private / 'config.toml'
    config.write_text('[connection]\nurl="https://c0.example.org/mcp"\naccount_id="account"\nidentity="Alice"\nspace_id="protected"\n'
                      '[benchmark]\ndataset_path="../../fixture"\npoll_seconds=0\nindex_attempts=1\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('C0_API_KEY', 'c0k_' + 'a'*43)
    monkeypatch.setattr('c0_beir.cli.C0', lambda config: api)
    monkeypatch.setattr('c0_beir.cli.instance_version', lambda config: {'app_version': 'synthetic'})
    # A preexisting remote corpus with no local receipt must be refused.
    assert main(['ingest']) == 1
    from c0_ingest.state import atomic
    atomic(private / 'manifests/scifact-test.json', manifest)
    assert main(['ingest']) == 0
    assert main(['evaluate', '--mode', 'text']) == 0
    assert main(['evaluate', '--mode', 'semantic', '--limit', '51']) == 1


def test_recovery_after_acknowledged_prefix(dataset_path, tmp_path):
    dataset = load(dataset_path); api = client(); path = tmp_path / 'resume.json'
    original = api.transport.dispatch
    def interrupt(name, arguments):
        if name == 'sources_ingest_text' and arguments['data']['metadata']['beir_id'] == 'c':
            api.transport.fail_after_commit = True
        return original(name, arguments)
    api.transport.dispatch = interrupt
    with pytest.raises(C0Error): ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    assert set(read(path)['submitted']) == {'a', 'b'} and not read(path)['documents']
    assert read(path)['pending'] == 'c'
    api.transport.dispatch = original
    assert ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)['complete']
    assert api.transport.write_calls == 3


def test_citation_tampering_and_reranking(prepared, tmp_path):
    dataset, api, path, manifest = prepared
    result = evaluate(api, dataset, manifest, tmp_path / 'reranked', modes=['hybrid'], rerank='rerank')
    assert result['modes']['hybrid+rerank']['effective_modes'] == {'hybrid+rerank': 1}
    original = api.transport.dispatch
    def corrupt(name, arguments):
        result = original(name, arguments)
        if name == 'knowledge_search': result['hits'][0]['citation']['version_id'] = 'wrong'
        return result
    api.transport.dispatch = corrupt
    with pytest.raises(C0Error): evaluate(api, dataset, manifest, tmp_path / 'bad-citation', modes=['text'])


def test_atomic_download_cache(dataset_path, tmp_path, monkeypatch):
    import io
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as zipped:
        for path in dataset_path.rglob('*'):
            if path.is_file(): zipped.writestr('scifact/' + str(path.relative_to(dataset_path)), path.read_bytes())
    calls = []
    def download(*args, **kwargs):
        calls.append(args)
        return io.BytesIO(archive.getvalue())
    monkeypatch.setattr('c0_beir.dataset.open_url', download)
    target = cached('scifact', tmp_path / 'download')
    assert load(target).fingerprint == load(dataset_path).fingerprint
    assert cached('scifact', tmp_path / 'download') == target and len(calls) == 1
    monkeypatch.setattr('c0_beir.dataset.MAX_ARCHIVE', 1)
    with pytest.raises(ValueError): cached('scifact', tmp_path / 'failed-download')
    assert not (tmp_path / 'failed-download/scifact').exists()


def test_queries_and_qrels_are_fingerprinted(dataset_path):
    before = load(dataset_path).fingerprint
    path = dataset_path / 'qrels/test.tsv'
    path.write_text(path.read_text().replace('q1\ta\t3', 'q1\ta\t2'))
    assert load(dataset_path).fingerprint != before


def test_long_queries_are_not_silently_truncated(prepared, tmp_path):
    dataset, api, path, manifest = prepared
    dataset.queries['q1'] = 'q' * 513
    searches = sum(name == 'knowledge_search' for name, _ in api.transport.calls)
    with pytest.raises(ValueError): evaluate(api, dataset, manifest, tmp_path / 'runs')
    assert sum(name == 'knowledge_search' for name, _ in api.transport.calls) == searches


def test_all_submissions_precede_extraction_reads(dataset_path, tmp_path):
    dataset = load(dataset_path); api = client(); path = tmp_path / 'queue.json'
    api.transport.queued = True
    original = api.transport.dispatch
    def background(name, arguments):
        if name in ('source_versions_list', 'documents_get'):
            assert api.transport.write_calls == 3, 'Do not wait for extraction before submitting the corpus'
            for version in api.transport.versions.values():
                version['state'] = 'ready'
        return original(name, arguments)
    api.transport.dispatch = background
    manifest = ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    assert manifest['complete'] and len(manifest['documents']) == 3
    assert not manifest['submitted'] and manifest['pending'] is None


@pytest.mark.parametrize('drift', ['missing', 'version', 'hash', 'failed'])
def test_acknowledged_queue_drift_stops_without_more_writes(dataset_path, tmp_path, drift):
    dataset = load(dataset_path); api = client(); path = tmp_path / 'queue.json'
    api.transport.queued = True
    with pytest.raises(C0Error): ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    if drift == 'missing': del api.transport.sources['source-a']
    if drift == 'version': api.transport.versions['source-a']['id'] = 'replacement'
    if drift == 'hash': api.transport.versions['source-a']['content_hash'] = 'replacement'
    if drift == 'failed': api.transport.versions['source-a']['state'] = 'failed'
    with pytest.raises(C0Error): ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    assert api.transport.write_calls == 3
    assert not read(path)['complete'] and len(read(path)['submitted']) == 3


def test_legacy_pending_manifest_resumes_without_duplicate(dataset_path, tmp_path):
    from c0_beir.corpus import binding, metadata, title, verify_source
    from c0_ingest.sources import submit_text
    from c0_ingest.state import atomic
    dataset = load(dataset_path); api = client(); path = tmp_path / 'legacy.json'
    for key in ('a', 'b'):
        submit_text(api, body=dataset.body(key), title=title(dataset, key), metadata=metadata(dataset, key),
                    external_key=['beir-v1', dataset.fingerprint, key])
    record = verify_source(api, dataset, 'a', api.transport.sources['source-a'])
    # Exact prior format: one completed receipt, one uncertain committed item,
    # and one item which has never been submitted.
    atomic(path, {'binding': binding(api, dataset), 'documents': {'a': record}, 'pending': 'b',
                  'complete': False, 'timings': {'ingestion_seconds': 0., 'indexing_seconds': 0.}})
    manifest = ingest(api, dataset, path, attempts=1, seconds=0, index_attempts=1)
    assert manifest['complete'] and manifest['documents']['a'] == record
    assert api.transport.write_calls == 3


def test_evaluation_rejects_unverified_submission_receipts(prepared, tmp_path):
    dataset, api, path, manifest = prepared
    manifest['submitted'] = {'a': {'id': 'source-a'}}
    with pytest.raises(C0Error): evaluate(api, dataset, manifest, tmp_path / 'incomplete')
    assert not any(name == 'knowledge_search' for name, _ in api.transport.calls)


def test_only_exact_pinned_reports_can_be_excluded(prepared, monkeypatch):
    from c0_beir.corpus import inventory, index_status
    dataset, api, _, manifest = prepared
    page = {'page_id': 'report', 'revision': 1, 'content_hash': 'a'*64}
    api.excluded_wiki_pages = [page]
    api.transport.wiki = [{'id': 'report'}]
    original = api.transport.dispatch
    def dispatch(name, args):
        if name == 'wiki_pages_get':
            return {'revision': 1, 'content': {'content_hash': 'a'*64}}
        if name == 'knowledge_index_status':
            return {**original(name,args), 'indexed': len(api.transport.chunks)+4,
                    'source_indexed': len(api.transport.chunks)}
        return original(name,args)
    monkeypatch.setattr(api.transport, 'dispatch', dispatch)
    api.operations['wiki_pages_get'] = {'read_only': True, 'input_schema': {'properties': {'space_id': {}}}}
    assert len(inventory(api,dataset)) == len(dataset.corpus)
    assert index_status(api,manifest)['coverage_ready']
    page['content_hash'] = 'b'*64
    with pytest.raises(C0Error,match='report changed'):
        inventory(api,dataset)
    page['content_hash'] = 'a'*64
    api.transport.wiki.append({'id': 'unrelated'})
    with pytest.raises(C0Error):
        inventory(api,dataset)


def test_report_exclusion_requires_source_specific_coverage(prepared):
    from c0_beir.corpus import index_status
    _, api, _, manifest = prepared
    api.excluded_wiki_pages = [{'page_id': 'report', 'revision': 1, 'content_hash': 'a'*64}]
    assert not index_status(api, manifest)['coverage_ready']



def test_ingestion_helper_rejects_report_exclusions_before_writes(prepared):
    dataset, api, path, _ = prepared
    api.excluded_wiki_pages = [{'page_id': 'report', 'revision': 1, 'content_hash': 'a'*64}]
    before = api.transport.write_calls
    with pytest.raises(C0Error, match='evaluation-only'):
        ingest(api, dataset, path)
    assert api.transport.write_calls == before
