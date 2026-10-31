# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real protected-space, worker, SDK and current-generation semantic contracts."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import pytest
from czero_core.worker import Worker

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
from agentic_retrieval.fixture import paired_fixture
from agentic_retrieval.layer import maintain,verify,validate_plan
from agentic_retrieval.runner import ReadBoundary
from c0_ingest.errors import C0Error

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_paired_real_sources_readonly_semantics_idempotency_and_expired_support(tmp_path):
    async def check():
        sources=json.loads((ROOT/'tests/evaluation/agentic_sources.json').read_text())
        async with paired_fixture(os.environ['CZERO_TEST_DATABASE_URL'],tmp_path,sources) as (a,b,corpus):
            d=next(d for d in corpus if d['version']=='2' and d['product']=='Orion');c=d['chunks'][0]
            plan={'namespace':'integration-layer','records':[{'key':'navigation','title':'Orion connections',
                'synthesis':'Read the original connection settings.','classification':'extracted',
                'evidence':[{'document_id':d['id'],'generation':d['generation'],'content_hash':d['content_hash'],
                            'quote':c['body'],'chunk_id':c['chunk_id']}]}]}
            state=tmp_path/'managed.json'
            dry=await maintain(b.api_call,b.space,corpus,plan,state)
            assert not state.exists() and not dry['applied']
            await maintain(b.api_call,b.space,corpus,plan,state,apply=True)
            first=json.loads(state.read_text())
            again=await maintain(b.api_call,b.space,corpus,plan,state,apply=True)
            assert again['records'][0]['action']=='unchanged'
            assert json.loads(state.read_text())==first
            assert await a.corpus()==await b.corpus()==corpus
            await verify(b.api_call,b.space,corpus,plan,state)
            async with b.mcp('reader-denial') as client:
                tools=(await client.list_tools()).tools
                assert all(t.annotations.read_only_hint for t in tools)
                assert 'wiki_pages_create' not in {t.name for t in tools}
                boundary=ReadBoundary(client,tools,b.space)
                result=await boundary.call('knowledge_search',{'options':{'space_id':b.space,'query':'Orion','mode':'text','rerank':'off'}})
                assert not result.is_error
            # A real supported source replacement retires old exact evidence.
            await b.request('POST','/api/v1/sources/ingest-text',{'source_id':d['id'],'title':'Changed manual',
                'body':'Orion 2 now requires a newly documented procedure.',
                'metadata':{'canonical_url':d['url'],'provenance':{'product':d['product'],'product_version':d['version'],'language':d['language']}},
                'expected_revision':1,'idempotency_key':'replacement'},b.space)
            Worker(b.db,b.app.state.jobs.registry).tick()
            with pytest.raises(C0Error,match='content_superseded'):
                await verify(b.api_call,b.space,corpus,plan,state)
            saved=first['records']['navigation']
            page=await b.api_call('wiki_pages_get',{'page_id':saved['id'],'space_id':b.space})
            annotation=await b.api_call('knowledge_annotations_get',{'kind':'wiki_revision','target_id':page['content']['id'],
                 'content_revision':page['revision'],'namespace':'verification','space_id':b.space})
            assert annotation['status']=='stale'
            assert await a.corpus()==corpus and await b.corpus()!=corpus
    asyncio.run(check())


def test_retained_pair_resumes_exact_ids_and_ownership_checked_cleanup(tmp_path):
    from agentic_retrieval.fixture import cleanup_pair,owned_binding
    async def check():
        admin=os.environ['CZERO_TEST_DATABASE_URL'];checkpoint=tmp_path/'binding.json'
        sources=json.loads((ROOT/'tests/evaluation/agentic_sources.json').read_text())[:1]
        async with paired_fixture(admin,tmp_path/'fixture',sources,checkpoint=checkpoint) as (a,b,corpus):
            frozen=deepcopy(corpus);space=a.space
        assert checkpoint.stat().st_mode & 0o077==0
        async with paired_fixture(admin,tmp_path/'fixture',sources,checkpoint=checkpoint) as (a,b,corpus):
            assert corpus==frozen and a.space==b.space==space
            async with a.mcp('reader-denial') as client:
                assert not (await client.call_tool('sources_search',{'space_id':space,'query':'Orion'})).is_error
        binding=json.loads(checkpoint.read_text());wrong={**binding,'nonce':'incorrect'}
        with pytest.raises(ValueError,match='ownership'):owned_binding(admin,wrong)
        cleanup_pair(admin,checkpoint);assert not checkpoint.exists()
    asyncio.run(check())
