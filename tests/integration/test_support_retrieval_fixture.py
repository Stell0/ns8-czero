# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from czero_core.worker import Worker
from test_auth_http import application, ORIGIN
from test_spaces_http import create_space, space_http


@pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
def test_bilingual_support_retrieval(space_http, tmp_path):
    corpus = json.loads((Path(__file__).parents[1] / 'fixtures/support_retrieval.json').read_text(encoding='utf-8'))
    app, owner, _, _, database, _ = space_http[0]
    app.state.sources.originals.root = tmp_path

    async def check():
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                               headers={'Authorization': 'Bearer ' + owner}) as client:
            docs = {'space_id': (await create_space(client, space_http))['id']}
            wiki = {'space_id': (await create_space(client, space_http))['id']}
            worker = Worker(database, app.state.jobs.registry)
            versions = {}
            for seed in corpus['documentation']:
                response = await client.post('/api/v1/sources/ingest-text', params=docs, json=seed)
                assert response.status_code == 202
                versions[seed['idempotency_key']] = response.json()['id']
                worker.tick()
            pages = {}
            for seed in corpus['intelligence']:
                response = await client.post('/api/v1/wiki/pages', params=wiki, json=seed)
                assert response.status_code == 201
                pages[seed['slug']] = response.json()

            actor = app.state.auth.access.resolve(app.state.auth.oidc.verify_access_token(owner))
            readers = {}
            for space, other in ((docs, wiki), (wiki, docs)):
                key = app.state.api_keys.create(actor, name='Support fixture reader', scopes={'c0:read'},
                                                space_ids=[space['space_id']], lifetime_days=1)
                headers = {'Authorization': 'Bearer ' + key['key']}
                readers[space['space_id']] = headers
                denied = await client.get('/api/v1/knowledge/search', headers=headers, params={
                    **other, 'query': corpus['cases'][0]['search'], 'mode': 'text', 'rerank': 'off'})
                assert denied.status_code == 403

            for case in corpus['cases']:
                for space, channel in ((docs, 'documentation'), (wiki, 'intelligence')):
                    headers = readers[space['space_id']]
                    response = await client.get('/api/v1/knowledge/search', headers=headers, params={
                        **space, 'query': case['search'], 'mode': 'text', 'rerank': 'off'})
                    assert response.status_code == 200
                    hits = response.json()['hits']
                    expected = case['expected'].get(channel)
                    if expected is None:
                        assert hits == [], case['ticket']['id']
                        continue
                    assert len(hits) == 1, case['ticket']['id']
                    if channel == 'documentation':
                        hit = hits[0]['citation']
                        assert hit['version_id'] == versions[expected['seed']]
                        read = await client.get('/api/v1/chunks/' + hit['chunk_id'] + '/citation', params=space, headers=headers)
                        assert read.status_code == 200
                        content = read.json()
                        assert content['content_hash'] == hit['content_hash']
                    else:
                        hit = hits[0]['wiki']
                        page = pages[expected['slug']]
                        assert hit['page_id'] == page['id']
                        read = await client.get('/api/v1/wiki/pages/' + page['id'], headers=headers, params={
                            **space, 'revision': hit['revision']})
                        assert read.status_code == 200
                        content = read.json()['content']
                        assert content['number'] == hit['revision'] and content['content_hash'] == hit['content_hash']
                    assert expected['passage'] in content['body']

    asyncio.run(check())
