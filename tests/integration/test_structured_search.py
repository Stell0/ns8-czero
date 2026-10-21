# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Applicability and space eligibility precede bounded retrieval candidates."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import text

from czero_core.annotations import ContentTarget
from czero_core.filtered_retrieval import FilteredEmbeddingStore
from czero_core.identity import PermissionDenied
from czero_core.providers import ScorerSettings, SystemOneClient
from czero_core.structured import StructuredFilters, StructuredSearchService
from test_annotations import annotations, write, wiki_target
from test_retrieval import search, wiki, sources, access
from test_wiki import create_page, create_entity
from test_sources import upload, execute
from test_objects import objects
from test_knowledge import knowledge, evidence, claim
from test_spaces import spaces, create, member
from czero_core.identity import Role
from test_embeddings import indexed

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def structured(search, annotations):
    service, wiki_fixture, source_fixture = search
    return StructuredSearchService(service.database, service.access), search, annotations


def annotate(service, actor, target, **fields):
    value = {'products': ['NS8'], 'components': ['backup'], 'version_tags': ['8.4'], 'status': 'applicable', **fields}
    return write(service, actor, target, 'applicability', value)


def test_default_source_wiki_selection_and_legacy_search_are_preserved(knowledge, objects, structured):
    service, fixture, annotations = structured
    legacy, wiki, sources = fixture
    query = 'structured'+uuid4().hex
    page = create_page(wiki, body=query)
    version = upload(sources, data=query.encode()); execute(sources, 'source.extract', version['id'])
    entity = create_entity(wiki, label=query)
    record = objects[0].create(objects[1], objects[2], {'name': query})
    chunk = sources[0].chunks(wiki[1], sources[0].document(wiki[1], version['id'])['id'])[0]
    assertion = claim(knowledge, entity, query, chunk, metadata={'status': 'verified'})
    before = legacy.search(wiki[1], query)
    ordinary = service.search(wiki[1], query)
    assert {hit['category'] for hit in ordinary['hits']} == {'source', 'wiki'}
    assert [hit['id'] for hit in ordinary['hits']] == [hit['id'] for hit in before['hits']]
    assert legacy.search(wiki[1], query) == before
    explicit = service.search(wiki[1], query, filters=StructuredFilters(categories=['entity', 'object', 'claim']))
    assert {hit['reference']['id'] for hit in explicit['hits']} == {entity['id'], str(record['id']), assertion['id']}
    assert all(hit['retrieval_method'] == 'text' and hit['citation'] is None for hit in explicit['hits'])
    assert all(hit['verification']['status'] == 'unknown' for hit in explicit['hits'])
    claim_hit = next(hit for hit in explicit['hits'] if hit['category'] == 'claim')
    assert claim_hit['reference']['revision'] == 1 and claim_hit['evidence_refs'][0]['chunk_id'] == str(chunk['id'])
    assert next(hit for hit in ordinary['hits'] if hit['category'] == 'source')['citation']['source_hash'] == version['content_hash']


def test_exact_filters_precede_candidate_limits_in_large_troubleshooting_corpus(structured):
    service, (_, wiki, _), annotations = structured
    query = 'troubleshoot'+uuid4().hex
    for index in range(70):
        row = create_page(wiki, title='Other version '+str(index), body=(query+' ')*20)
        annotate(annotations, wiki[1], wiki_target(row), version_tags=['8.40'])
    wanted = create_page(wiki, title='Backup EPIPE procedure', body=query+' systemctl restart backup')
    annotate(annotations, wiki[1], wiki_target(wanted), components=['backup', 'storage'])
    write(annotations, wiki[1], wiki_target(wanted), 'verification', {'status': 'verified'})
    filters = StructuredFilters(categories=['wiki'], products=['missing', 'NS8'], components=['storage'],
        version_tags=['8.4'], statuses=['applicable'], verification_statuses=['verified'])
    result = service.search(wiki[1], query, filters=filters, limit=1)
    assert result['candidate_count'] == 1
    assert [hit['reference']['id'] for hit in result['hits']] == [wanted['content']['id']]
    assert result['hits'][0]['applicability']['revision'] == 1
    assert result['hits'][0]['verification']['status'] == 'verified'
    for tags in (['8'], ['8.4.*'], ['8.4.0'], ['8.4 ']):
        assert service.search(wiki[1], query, filters=StructuredFilters(version_tags=tags))['hits'] == []


def test_missing_and_stale_annotations_remain_unknown(structured):
    service, (_, wiki, _), annotations = structured
    query = 'unknown'+uuid4().hex
    row = create_page(wiki, body=query)
    filters = StructuredFilters(statuses=['unknown'], verification_statuses=['unknown'])
    assert len(service.search(wiki[1], query, filters=filters)['hits']) == 1
    annotate(annotations, wiki[1], wiki_target(row))
    write(annotations, wiki[1], wiki_target(row), 'verification', {'status': 'verified'})
    assert service.search(wiki[1], query, filters=filters)['hits'] == []
    changed = wiki[0].update_page(wiki[1], row['id'], 'New revision', query+' new content',
        expected_revision=1, idempotency_key=uuid4().hex)
    hit = service.search(wiki[1], query, filters=filters)['hits'][0]
    assert hit['reference']['id'] == changed['content']['id'] and hit['reference']['revision'] == 2
    assert hit['verification']['revision'] == 0 and hit['verification']['status'] == 'unknown'
    assert service.search(wiki[1], query, filters=StructuredFilters(version_tags=['8.4']))['hits'] == []


def test_archive_and_utc_filters_are_explicit_and_combined(sources, structured):
    service, (_, wiki, _), annotations = structured
    query = 'archival'+uuid4().hex
    version = upload(sources, data=query.encode()); execute(sources, 'source.extract', version['id'])
    target = ContentTarget('source_version', version['id'], version['number'])
    annotate(annotations, wiki[1], target, observed_at='2026-10-18T00:00:00+02:00')
    write(annotations, wiki[1], target, 'verification', {'status': 'verified', 'verified_at': '2026-10-18T00:30:00Z'})
    filters = dict(categories=['source'], products=['NS8'], observed_from='2026-10-17T21:59:59Z',
        observed_to='2026-10-17T22:00:00Z', verified_from='2026-10-18T00:00:00Z')
    assert len(service.search(wiki[1], query, filters=StructuredFilters(**filters))['hits']) == 1
    sources[0].delete(wiki[1], version['source_id'], expected_revision=1)
    assert service.search(wiki[1], query, filters=StructuredFilters(**filters))['hits'] == []
    result = service.search(wiki[1], query, filters=StructuredFilters(**filters, archive='archived'))
    assert len(result['hits']) == 1 and result['hits'][0]['citation']['deleted']
    assert result['hits'][0]['verification']['status'] == 'verified'
    assert service.search(wiki[1], query, filters=StructuredFilters(**{**filters, 'observed_from': '2026-10-17T22:00:01Z', 'observed_to': None}, archive='all'))['hits'] == []


def test_filtered_hybrid_and_reranker_never_receive_other_space_or_version(spaces, indexed, annotations):
    store, fixture, embedding_calls = indexed
    _, wiki, _ = fixture
    wanted = create_page(wiki, title='Selected procedure', body='alpha selected troubleshooting')
    wrong = create_page(wiki, title='Wrong version sentinel', body='alpha wrong-version-secret')
    annotate(annotations, wiki[1], wiki_target(wanted))
    annotate(annotations, wiki[1], wiki_target(wrong), version_tags=['8.40'])
    private = create(spaces)
    hidden = wiki[0].in_space(private['id']).create_page(wiki[1], 'hidden-'+uuid4().hex,
        'Private sentinel', 'alpha private-space-secret', idempotency_key=uuid4().hex)
    wiki[2].append(hidden['id'])
    annotate(annotations.in_space(private['id']), wiki[1], wiki_target(hidden))
    with store.database.engine.begin() as connection:
        while store._index_batch(connection)['indexed']:
            pass
    embedding_calls.clear(); scored = []
    def reply(request):
        body = json.loads(request.content); scored.append(body)
        return httpx2.Response(200, json={'model': 'kev-mock', 'answers': {
            key: {'type': 'noul', 'noul': .9} for key in body['questions']}})
    scorer = SystemOneClient(ScorerSettings('https://score.example.test/v1/systemone', 'kev-mock'),
        transport=httpx2.MockTransport(reply))
    service = StructuredSearchService(store.database, wiki[0].access, embedding_client=store.client,
        scorer=scorer, scorer_mode='rerank')
    result = service.search(wiki[1], 'alpha', filters=StructuredFilters(version_tags=['8.4']), mode='hybrid')
    assert [hit['reference']['id'] for hit in result['hits']] == [wanted['content']['id']]
    assert result['candidate_count'] == result['scored_count'] == 1
    assert result['retrieval_method'] == 'hybrid+rerank'
    outbound = json.dumps([embedding_calls, scored])
    assert 'private-space-secret' not in outbound and 'wrong-version-secret' not in outbound
    assert 'Selected procedure' in outbound and embedding_calls[0]['input'] == ['alpha']
    private_result = service.in_space(private['id']).search(wiki[1], 'alpha', filters=StructuredFilters(version_tags=['8.4']), mode='semantic')
    assert [hit['reference']['id'] for hit in private_result['hits']] == [hidden['content']['id']]


@pytest.mark.parametrize('incremental_sort', ['on', 'off'])
def test_semantic_candidates_beyond_limit_and_provider_failure_keep_valid_version(indexed, annotations, incremental_sort):
    store, fixture, calls = indexed
    _, wiki, _ = fixture
    for index in range(70):
        wrong = create_page(wiki, title='Wrong '+str(index), body='alpha wrong version')
        annotate(annotations, wiki[1], wiki_target(wrong), version_tags=['8.40'])
    wanted = create_page(wiki, title='Selected beta procedure', body='beta distant but applicable')
    annotate(annotations, wiki[1], wiki_target(wanted))
    with store.database.engine.begin() as connection:
        while store._index_batch(connection)['indexed']:
            pass
    calls.clear()
    service = StructuredSearchService(store.database, wiki[0].access, embedding_client=store.client)
    filters = StructuredFilters(categories=['wiki'], version_tags=['8.4'])
    semantic = service.search(wiki[1], 'alpha', mode='semantic', filters=filters, limit=1)
    assert semantic['candidate_count'] == 1 and semantic['retrieval_method'] == 'semantic'
    assert [hit['reference']['id'] for hit in semantic['hits']] == [wanted['content']['id']]
    assert semantic['hits'][0]['wiki']['content_hash'] == wanted['content']['content_hash']
    # Require a real filtered HNSW plan, then force that scan to underfill.
    # The actual exact-distance query must still find the one eligible revision.
    filtered = FilteredEmbeddingStore(store.database, store.client, store.access, filters)
    with store.database.engine.begin() as connection:
        # Forced planner penalties can enable expensive JIT compilation for
        # this tiny fixture. Isolate the ANN/fallback assertion from compiler
        # startup; ordinary search above keeps the database's normal settings.
        # Exercise both incremental and full-sort plans under the same deadline.
        connection.execute(text('SET LOCAL jit=off'))
        connection.execute(text('SET LOCAL enable_incremental_sort='+incremental_sort))
        connection.execute(text('SET LOCAL enable_seqscan=off'))
        connection.execute(text('SET LOCAL enable_sort=off'))
        plans, fallbacks = [], []
        class UnderfilledScan:
            def execute(self, statement, parameters=None):
                if 'WITH nearest AS MATERIALIZED' in str(statement):
                    plans.extend(row[0] for row in connection.execute(text('EXPLAIN '+str(statement)), parameters))
                    connection.execute(statement, parameters).mappings().all()
                    return connection.execute(text('SELECT id,source_chunk_id,wiki_chunk_id,0.0 AS distance FROM c0_embeddings WHERE false'))
                if 'WITH candidates AS MATERIALIZED' in str(statement):
                    fallbacks.append(True)
                return connection.execute(statement, parameters)
        nearest = filtered.nearest(UnderfilledScan(), [1,0,0], limit=1, kind='wiki')
        assert 'c0_embeddings_cosine' in ' '.join(plans) and fallbacks == [True]
        assert len(nearest) == 1
        selected = connection.execute(text('SELECT revision_id FROM c0_wiki_chunks WHERE id=:id'),
            {'id': nearest[0]['wiki_chunk_id']}).scalar_one()
        assert str(selected) == wanted['content']['id']
    store.client._transport = httpx2.MockTransport(lambda _: httpx2.Response(429))
    fallback = service.search(wiki[1], 'beta', mode='hybrid', filters=filters)
    assert fallback['fallback_reason'] == 'embedding_rate_limited'
    assert fallback['retrieval_method'] == 'text' and fallback['candidate_count'] == 1
    assert [hit['reference']['id'] for hit in fallback['hits']] == [wanted['content']['id']]


def test_structured_categories_remain_text_only_with_configured_provider(indexed, annotations):
    store, fixture, calls = indexed
    _, wiki, _ = fixture
    row = create_entity(wiki, kind='procedure', label='Resolver getent troubleshooting')
    annotate(annotations, wiki[1], ContentTarget('entity', row['id'], row['revision']), components=['resolver'])
    service = StructuredSearchService(store.database, wiki[0].access, embedding_client=store.client)
    result = service.search(wiki[1], 'getent', mode='semantic',
        filters=StructuredFilters(categories=['entity'], components=['resolver']))
    assert calls == [] and result['provider_usage'] == {}
    assert result['retrieval_method'] == result['hits'][0]['retrieval_method'] == 'text'
    assert result['hits'][0]['reference']['id'] == row['id']


def test_space_revocation_during_scoring_returns_no_obsolete_authority(spaces, indexed, annotations):
    store, fixture, _ = indexed
    _, wiki, _ = fixture
    private = create(spaces); reader = member(spaces, Role.EDITOR)
    row = wiki[0].in_space(private['id']).create_page(wiki[1], 'race-'+uuid4().hex,
        'Owned investigation', 'alpha selected private observation', idempotency_key=uuid4().hex)
    wiki[2].append(row['id'])
    annotate(annotations.in_space(private['id']), wiki[1], wiki_target(row))
    spaces[0].set_grant(wiki[1], private['id'], reader.user_id, Role.READER,
        expected_revision=0, idempotency_key=uuid4().hex)
    def reply(request):
        assert store.database.engine.pool.checkedout() == 0
        spaces[0].set_grant(wiki[1], private['id'], reader.user_id, None,
            expected_revision=1, idempotency_key=uuid4().hex)
        body = json.loads(request.content)
        return httpx2.Response(200, json={'model': 'kev-mock', 'answers': {
            key: {'type': 'noul', 'noul': .9} for key in body['questions']}})
    scorer = SystemOneClient(ScorerSettings('https://score.example.test/v1/systemone', 'kev-mock'),
        transport=httpx2.MockTransport(reply))
    service = StructuredSearchService(store.database, wiki[0].access,
        scorer=scorer, scorer_mode='rerank').in_space(private['id'])
    with pytest.raises(PermissionDenied):
        service.search(reader, 'alpha', mode='text', filters=StructuredFilters(version_tags=['8.4']))


def test_labeled_troubleshooting_commands_errors_aliases_and_references(knowledge, objects, structured):
    service, (_, wiki, sources), annotations = structured
    procedure = create_page(wiki, title='DNS resolution', body='Use getent hosts to inspect resolver configuration.')
    topic = create_entity(wiki, kind='investigation', label='TLS trust error', aliases=['certificate verify failed'])
    worker = create_entity(wiki, kind='service', label='Backup worker')
    record = objects[0].create(objects[1], objects[2], {'name': 'permission denied backup'})
    version = upload(sources, data=b'EPIPE from backup worker while closing a pipe.')
    execute(sources, 'source.extract', version['id'])
    document = sources[0].document(wiki[1], version['id'])
    chunk = sources[0].chunks(wiki[1], document['id'])[0]
    assertion = knowledge[0].create_claim(wiki[1], worker['id'], 'observed-error', {'message': 'EPIPE pipe closed'},
        evidence_chunk_ids=[chunk['id']], idempotency_key=uuid4().hex)
    targets = [wiki_target(procedure), ContentTarget('entity', topic['id'], 1),
        ContentTarget('object', record['id'], 1), ContentTarget('claim', assertion['id'], 1),
        ContentTarget('source_version', version['id'], version['number'])]
    for target in targets: annotate(annotations, wiki[1], target, components=['support'])
    write(annotations, wiki[1], targets[0], 'verification', {'status': 'verified'})
    fixtures = [('getent', 'wiki', targets[0]), ('certificate verify failed', 'entity', targets[1]),
        ('permission denied', 'object', targets[2]), ('EPIPE', 'claim', targets[3]), ('EPIPE', 'source', targets[4])]
    measurements = []
    for query, category, target in fixtures:
        started = time.perf_counter()
        result = service.search(wiki[1], query, filters=StructuredFilters(categories=[category],
            products=['NS8'], components=['support'], version_tags=['8.4']), limit=1)
        elapsed = (time.perf_counter()-started)*1000
        assert result['candidate_count'] == 1 and result['provider_usage'] == {}
        assert result['hits'][0]['reference']['id'] == str(target.id)
        assert result['hits'][0]['reference']['revision'] == target.revision
        assert result['hits'][0]['verification']['status'] == ('verified' if category == 'wiki' else 'unknown')
        if category == 'source': assert result['hits'][0]['citation']['content_hash'] == chunk['content_hash']
        if category == 'claim': assert result['hits'][0]['evidence_refs'][0]['chunk_id'] == str(chunk['id'])
        measurements.append({'category': category, 'recall_at_1': 1, 'typed_reference_coverage': 1,
            'candidate_count': 1, 'latency_ms': elapsed, 'provider_requests': 0})
    output = os.getenv('CZERO_STRUCTURED_BENCHMARK_OUTPUT')
    if output:
        Path(output).write_text(json.dumps({'fixture': 'five labeled command/error/alias troubleshooting categories',
            'retrieval': 'deterministic text with exact applicability; no real-provider quality claim',
            'results': measurements}, indent=2)+'\n')


@pytest.mark.parametrize('options', [
    {'categories': []}, {'categories': ['table']}, {'version_tags': []}, {'statuses': 'verified'},
    {'products': ['x']*33}, {'products': [chr(0xd800)]}, {'archive': 'deleted'}, {'observed_from': '2026-10-18'},
    {'created_from': '2026-10-18T00:00:00Z', 'created_to': '2026-10-17T00:00:00Z'},
])
def test_invalid_structured_filter_is_not_a_silent_broader_query(options):
    with pytest.raises(ValueError): StructuredFilters(**options)
