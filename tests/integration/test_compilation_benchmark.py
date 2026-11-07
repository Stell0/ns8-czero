# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Matched originals with reviewed construction through production compiler APIs."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import pytest
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'scripts'),str(ROOT/'tests')]
from agentic_retrieval.compiler import publish
from agentic_retrieval.fixture import paired_fixture
from agentic_retrieval.protocol import digest
from czero_core.worker import Worker
from c0_ingest.errors import C0Error
from test_knowledge_compilation_baseline import bind_response

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def review(corpus, plan):
    return {'corpus_hash':digest(corpus),'plan_hash':digest(plan),'provenance':'independent source-based fixture analyst',
        'records':[{'key':r['key'],'source_supported':True,'uncertainty_preserved':True} for r in plan['records']]}


def test_compiler_publisher_real_sql_originals_review_unchanged_and_replacement(tmp_path):
    async def check():
        sources = json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'fixture',sources) as (raw,enriched,corpus):
            plan = bind_response(corpus); audited = review(corpus,plan); state = tmp_path/'publication.json'
            baseline = enriched.snapshot()
            dry = await publish(enriched,corpus,plan,state,audited)
            assert dry['writes'] == 0 and enriched.snapshot() == baseline and not state.exists()
            bad = deepcopy(audited);bad['records'][0]['source_supported'] = False
            with pytest.raises(ValueError,match='review_incomplete'):
                await publish(enriched,corpus,plan,state,bad,apply=True)
            assert enriched.snapshot() == baseline
            first = await publish(enriched,corpus,plan,state,audited,apply=True)
            assert len(first['records']) == 3 and first['status']['tasks']['succeeded'] == 3
            assert not first['complete_corpus_coverage']
            saved = json.loads(state.read_text()); before = enriched.snapshot()
            repeated = await publish(enriched,corpus,plan,state,audited,apply=True)
            assert {r['outcome'] for r in repeated['records']} == {'unchanged'}
            assert enriched.snapshot() == before and json.loads(state.read_text()) == saved
            assert await raw.corpus() == await enriched.corpus() == corpus
            with enriched.db.engine.connect() as connection:
                counts = {table:connection.execute(text('SELECT count(*) FROM '+table+' WHERE space_id=:space'),
                    {'space':enriched.space}).scalar_one() for table in ('c0_wiki_pages','c0_compilation_dependencies')}
            assert counts['c0_wiki_pages'] == 3 and counts['c0_compilation_dependencies'] >= 3
            doc = next(d for d in corpus if 'listener' in d['url'])
            await enriched.request('POST','/api/v1/sources/ingest-text',{'source_id':doc['id'],'title':doc['title'],
                'body':'The replacement requires revalidation.','expected_revision':1,'metadata':{'canonical_url':doc['url']},
                'idempotency_key':'replace'},enriched.space)
            Worker(enriched.db,enriched.app.state.jobs.registry).tick()
            with pytest.raises(ValueError,match='source_drift'):
                await publish(enriched,corpus,plan,state,audited,apply=True)
            with pytest.raises(C0Error,match='content_superseded'):
                await enriched.api_call('citations_get',{'space_id':enriched.space,'chunk_id':doc['chunks'][0]['chunk_id']})
            assert await raw.corpus() == corpus
    asyncio.run(check())


def test_unknown_compiler_intent_blocks_without_repeating_a_write(tmp_path):
    async def check():
        sources = json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'fixture',sources) as (_,enriched,corpus):
            plan = bind_response(corpus); state = tmp_path/'publication.json'
            state.write_text(json.dumps({'space':enriched.space,'plan_hash':digest(plan),'records':{},
                'pending':{'operation':'compilation_propose','key':'unchanged-opaque-key','fingerprint':'unknown'}}))
            before = enriched.snapshot()
            with pytest.raises(RuntimeError,match='requires_reconciliation'):
                await publish(enriched,corpus,plan,state,review(corpus,plan),apply=True)
            assert enriched.snapshot() == before
    asyncio.run(check())


def test_lost_compiler_response_reconciles_saved_publication_without_reapply(tmp_path,monkeypatch):
    from agentic_retrieval import compiler
    real = compiler.compile_plan
    attempts = []
    async def lost(*args,**kwargs):
        result = await real(*args,**kwargs)
        if kwargs.get('apply'):
            attempts.append(result['task']['id'])
            if len(attempts) == 1:raise ConnectionError('synthetic lost committed response')
        return result
    monkeypatch.setattr(compiler,'compile_plan',lost)
    async def check():
        sources = json.loads((ROOT/'tests/fixtures/knowledge_compilation/sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path/'fixture',sources) as (_,enriched,corpus):
            plan = bind_response(corpus);state = tmp_path/'publication.json'
            interrupted = False
            try:
                await publish(enriched,corpus,plan,state,review(corpus,plan),apply=True)
            except* ConnectionError:
                interrupted = True
            assert interrupted
            assert json.loads(state.read_text())['pending']['operation'] == 'compile_plan'
            result = await publish(enriched,corpus,plan,state,review(corpus,plan),apply=True)
            assert len(attempts) == len(set(attempts)) == 3
            assert len(result['records']) == 3 and result['status']['tasks']['succeeded'] == 3
            assert json.loads(state.read_text())['pending'] is None
    asyncio.run(check())
