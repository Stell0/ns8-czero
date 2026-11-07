# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""M0 uses existing real services, not a simulated future compiler state machine."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import time

import pytest
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from agentic_retrieval.fixture import paired_fixture
from agentic_retrieval.layer import maintain, verify
from c0_ingest.client import C0
from c0_ingest.errors import C0Error
from czero_core.worker import Worker

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
FIXTURES = ROOT / 'tests/fixtures/knowledge_compilation'


def bind_response(corpus):
    """Bind canned source-only proposals to real IDs; no question input is accepted."""
    response = json.loads((FIXTURES / 'model-response.json').read_text())
    originals = {s['key']: s for s in json.loads((FIXTURES / 'sources.json').read_text())}
    records = []
    for record in response['records']:
        evidence = []
        for support in record['support']:
            doc = next(d for d in corpus if d['url'] == originals[support['key']]['url'])
            chunk = next(c for c in doc['chunks'] if support['quote'] in c['body'])
            evidence.append({'document_id': doc['id'], 'generation': doc['generation'],
                'content_hash': doc['content_hash'], 'quote': support['quote'], 'chunk_id': chunk['chunk_id']})
        records.append({k: v for k, v in record.items() if k != 'support'} | {'evidence': evidence})
    return {'namespace': response['namespace'], 'records': records}


@asynccontextmanager
async def bound_call(fixture):
    # One genuine delegated connection avoids exhausting the fixture's 32-grant cap.
    async with fixture.mcp('cited-research') as client:
        async def call(name, arguments):
            result = await client.call_tool(name, arguments)
            return C0.decode(name, result.model_dump(mode='json', by_alias=True, exclude_none=True))
        yield call


def sql_state(fixture):

    with fixture.db.engine.connect() as connection:
        return {table: connection.execute(text('SELECT count(*) FROM ' + table + ' WHERE space_id=CAST(:space AS uuid)'),
                    {'space': fixture.space}).scalar_one()
                for table in ('c0_wiki_pages', 'c0_wiki_revisions', 'c0_entities', 'c0_claims',
                              'c0_relations', 'c0_knowledge_events', 'c0_knowledge_receipts')}


def test_m0_source_baseline_and_multiple_relational_records(tmp_path, record_property):
    async def check():
        sources = json.loads((FIXTURES / 'sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'], tmp_path, sources) as (a, b, corpus), bound_call(b) as call:
            initial = sql_state(a)
            measurements = []
            for case in json.loads((FIXTURES / 'retrieval-baseline.json').read_text()):
                started = time.perf_counter()
                result = await a.api_call('knowledge_search', {'options': {'space_id': a.space,
                    'query': case['query'], 'mode': 'text', 'rerank': 'off', 'limit': 10}})
                expected = {s['url'] for s in sources if s['key'] in case['expected_source_keys']}
                ids = {hit['resource_id'] for hit in result['hits']}
                assert ids == {d['id'] for d in corpus if d['url'] in expected}, case['query']
                measurements.append({'query': case['query'], 'seconds': time.perf_counter() - started,
                                     'hits': len(ids), 'expected_documents': len(expected)})
            assert sql_state(a) == initial  # Search did not create coordination/knowledge work.
            plan = bind_response(corpus)
            state = tmp_path / 'managed.json'
            dry = await maintain(call, b.space, corpus, plan, state)
            assert not dry['applied'] and not state.exists() and sql_state(b) == initial
            await maintain(call, b.space, corpus, plan, state, apply=True)
            saved = json.loads(state.read_text())
            before = sql_state(b)
            repeated = await maintain(call, b.space, corpus, plan, state, apply=True)
            assert {r['action'] for r in repeated['records']} == {'unchanged'}
            assert sql_state(b) == before and json.loads(state.read_text()) == saved
            assert (await verify(call, b.space, corpus, plan, state))['verified_current'] == 3
            assert await a.corpus() == await b.corpus() == corpus
            pages = saved['records']
            chunks = {s['key']: next(d for d in corpus if d['url'] == s['url'])['chunks'][0] for s in sources}
            operations = [
                {'operation': 'entity.create', 'arguments': {'kind': 'concept', 'label': 'Orion listener', 'aliases': ['Orion socket']}},
                {'operation': 'entity.create', 'arguments': {'kind': 'procedure', 'label': 'Orion operator access'}},
                {'operation': 'relation.create', 'arguments': {'source_id': {'$result': 1, 'path': 'id'},
                    'target_id': {'$result': 0, 'path': 'id'}, 'kind': 'requires'}},
                {'operation': 'entity.link', 'arguments': {'entity_id': {'$result': 0, 'path': 'id'},
                    'target_kind': 'page', 'target_id': pages['listener']['id']}},
            ]
            for key, port in [('listener', 7443), ('conflict', 8443)]:
                operations.append({'operation': 'claim.create', 'arguments': {
                    'entity_id': {'$result': 0, 'path': 'id'}, 'predicate': 'listener-port',
                    'value': {'port': port}, 'page_id': pages['disagreement']['id'],
                    'evidence_chunk_ids': [chunks[key]['chunk_id']], 'metadata': {'status': 'unresolved'}}})
            result = await call('knowledge_bundle_apply', {'data': {'space_id': b.space,
                'operations': operations, 'idempotency_key': 'kc-m0-relational'}})
            assert await call('knowledge_bundle_apply', {'data': {'space_id': b.space,
                'operations': operations, 'idempotency_key': 'kc-m0-relational'}}) == result
            claims = (await call('claims_list', {'entity_id': result['results'][0]['id'], 'space_id': b.space}))['claims']
            assert {c['value']['port'] for c in claims} == {7443, 8443}
            for claim in claims:
                actual = await call('claims_get', {'claim_id': claim['id'], 'space_id': b.space})
                citation = await call('citations_get', {'chunk_id': actual['evidence'][0]['chunk_id'], 'space_id': b.space})
                assert str(claim['value']['port']) in citation['body']
            graph = await call('knowledge_graph', {'entity_id': result['results'][1]['id'], 'space_id': b.space})
            assert len(graph['relations']) == 1
            for page in pages.values():
                actual = await call('wiki_pages_get', {'page_id': page['id'], 'space_id': b.space})
                assert 'Copy credentials' not in actual['content']['body']
                annotation = await call('knowledge_annotations_get', {'kind': 'wiki_revision',
                    'target_id': actual['content']['id'], 'content_revision': actual['revision'],
                    'namespace': 'verification', 'space_id': b.space})
                assert annotation['status'] == 'unverified'
            counts = sql_state(b)
            assert (counts['c0_wiki_pages'], counts['c0_entities'], counts['c0_claims'], counts['c0_relations']) == (3, 2, 2, 1)
            assert sql_state(a) == initial and await a.corpus() == await b.corpus() == corpus
            record_property('m0_source_only_observations', json.dumps(measurements))
            record_property('m0_sql_counts', json.dumps(counts))
    asyncio.run(check())


def test_m0_replacement_expires_exact_support_and_preserves_authored_page(tmp_path):
    async def check():
        sources = json.loads((FIXTURES / 'sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'], tmp_path, sources) as (a, b, corpus), bound_call(b) as call:
            plan = bind_response(corpus)
            state = tmp_path / 'managed.json'
            await maintain(call, b.space, corpus, plan, state, apply=True)
            saved = json.loads(state.read_text())
            original = next(d for d in corpus if d['url'] == sources[0]['url'])
            await b.request('POST', '/api/v1/sources/ingest-text', {'source_id': original['id'],
                'title': 'Changed listener', 'body': '# Orion 2 listener\n\nThe listener now uses TCP port 9443.\n',
                'metadata': {'canonical_url': original['url']}, 'expected_revision': 1,
                'idempotency_key': 'kc-m0-replacement'}, b.space)
            Worker(b.db, b.app.state.jobs.registry).tick()
            with pytest.raises(C0Error, match='content_superseded'):
                await verify(call, b.space, corpus, plan, state)
            page = await call('wiki_pages_get', {'page_id': saved['records']['listener']['id'], 'space_id': b.space})
            assert page['revision'] == saved['records']['listener']['revision']
            annotation = await call('knowledge_annotations_get', {'kind': 'wiki_revision',
                'target_id': page['content']['id'], 'content_revision': page['revision'],
                'namespace': 'verification', 'space_id': b.space})
            assert annotation['status'] == 'stale'
            assert await a.corpus() == corpus and await b.corpus() != corpus
    asyncio.run(check())
