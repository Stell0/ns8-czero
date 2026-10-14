# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from uuid import UUID
from urllib.parse import parse_qs, urlsplit

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text

from czero_core.worker import Worker
from test_auth_http import application, ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def source_http(application, tmp_path):
    app = application[0]
    app.state.sources.originals.root = tmp_path / 'sources'
    created = []
    with application[4].engine.begin() as c:
        schedules = [dict(row) for row in c.execute(text('SELECT id,enabled,next_run_at FROM c0_scheduled_tasks')).mappings()]
        c.execute(text('UPDATE c0_scheduled_tasks SET enabled=false'))
    yield application, created
    db = application[4]
    with db.engine.begin() as c:
        for key in created:
            ids = c.execute(text('SELECT id FROM c0_source_versions WHERE source_id=:id'), {'id': key}).scalars().all()
            c.execute(text('DELETE FROM c0_chunks WHERE document_id IN (SELECT id FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id))'), {'id': key})
            c.execute(text('DELETE FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id)'), {'id': key})
            c.execute(text('DELETE FROM c0_source_versions WHERE source_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_sources WHERE id=:id'), {'id': key})
            for version in ids:
                c.execute(text("DELETE FROM c0_jobs WHERE payload->>'version_id'=:id"), {'id': str(version)})
        for row in schedules:
            c.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled,next_run_at=:next_run_at WHERE id=:id'), row)


def test_signed_upload_worker_full_text_citation_search_reference_and_dedup(source_http):
    async def check():
        application, created = source_http
        app, owner, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get('/api/v1/sources')).status_code == 401
            client.headers['Authorization'] = 'Bearer ' + owner
            content = '# Inventory\n\nEvidence café 東京'
            fields = {'title': 'Inventory', 'media_type': 'text/markdown'}
            response = await client.post('/api/v1/sources/upload', data=fields, files={'file': ('../../display.md', content.encode())})
            assert response.status_code == 202
            version = response.json()
            created.append(version['source_id'])
            assert version['state'] == 'queued' and version['original_present']
            assert (await client.get('/api/v1/source-versions/' + version['id'] + '/document')).status_code == 404
            source = (await client.get('/api/v1/sources/' + version['source_id'])).json()
            assert source['revision'] == 1 and source['title'] == 'Inventory'
            Worker(application[4], app.state.jobs.registry).tick()
            versions = (await client.get('/api/v1/sources/' + source['id'] + '/versions')).json()['versions']
            assert versions[0]['state'] == 'ready' and not versions[0]['original_present']
            document = (await client.get('/api/v1/source-versions/' + version['id'] + '/document')).json()
            assert document['body'] == content
            chunk = (await client.get('/api/v1/documents/' + document['id'] + '/chunks')).json()['chunks'][0]
            citation = (await client.get('/api/v1/chunks/' + chunk['id'] + '/citation')).json()
            assert citation['body'] == content and citation['source_hash'] == version['content_hash']
            assert (await client.get('/api/v1/sources/search', params={'query': 'Inventory'})).json()['citations'][0]['chunk_id'] == chunk['id']
            for kind, key in [('source', source['id']), ('document', document['id']), ('chunk', chunk['id'])]:
                ref = await client.get('/api/v1/references/' + kind + '/' + key, params={'type_name': kind})
                assert ref.status_code == 200 and ref.json()['id'] == key
            duplicate = await client.post('/api/v1/sources/upload', data={**fields, 'source_id': source['id'], 'expected_revision': '1'}, files={'file': ('copy.md', content.encode())})
            assert duplicate.status_code == 202 and duplicate.json()['id'] == version['id']
            assert (await client.delete('/api/v1/sources/' + source['id'], params={'expected_revision': 7})).status_code == 409
            deleted = await client.delete('/api/v1/sources/' + source['id'], params={'expected_revision': 1})
            assert deleted.status_code == 200 and deleted.json()['deleted']
            assert (await client.get('/api/v1/chunks/' + chunk['id'] + '/citation')).json()['deleted']
            assert (await client.get('/api/v1/sources/search', params={'query': 'Inventory'})).json()['citations'] == []
            schema = (await client.get('/openapi.json')).json()
            assert schema['paths']['/api/v1/chunks/{chunk_id}/citation']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/CitationView')
    asyncio.run(check())


def test_source_roles_revocation_cookie_csrf_and_failed_original_retry(source_http):
    async def check():
        application, created = source_http
        app, owner, member, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.headers['Authorization'] = 'Bearer ' + owner
            fields = {'title': 'Failed fixture', 'media_type': 'text/plain'}
            uploaded = await client.post('/api/v1/sources/upload', data=fields, files={'file': ('invalid.txt', b'\xff')})
            assert uploaded.status_code == 202
            row = uploaded.json(); created.append(row['source_id'])
            Worker(application[4], app.state.jobs.registry).tick()
            versions = (await client.get('/api/v1/sources/' + row['source_id'] + '/versions')).json()['versions']
            assert versions[0]['state'] == 'failed' and versions[0]['error_code'] == 'invalid_text'
            assert app.state.sources.originals.path(UUID(row['id'])).read_bytes() == b'\xff'
            original = await client.get('/api/v1/source-versions/' + row['id'] + '/original')
            assert original.status_code == 200 and original.content == b'\xff'
            assert original.headers['content-type'] == 'application/octet-stream'
            assert original.headers['content-disposition'].startswith('attachment;')
            assert (await client.post('/api/v1/source-versions/' + row['id'] + '/retry', json={'expected_generation': 1})).status_code == 202
            assert (await client.post('/api/v1/source-versions/' + row['id'] + '/retry', json={'expected_generation': 1})).status_code == 409
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/me')).status_code == 403
            client.headers['Authorization'] = 'Bearer ' + owner
            target = next(a['id'] for a in (await client.get('/api/v1/access/accounts')).json()['accounts'] if a['username'] == 'member')
            await client.put('/api/v1/access/accounts/' + target, json={'role': 'reader'})
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/sources/' + row['source_id'])).status_code == 200
            assert (await client.delete('/api/v1/sources/' + row['source_id'], params={'expected_revision': 1})).status_code == 403
            assert (await client.post('/api/v1/sources/upload', data=fields, files={'file': ('reader.txt', b'evidence')})).status_code == 403
            client.headers['Authorization'] = 'Bearer ' + owner
            await client.put('/api/v1/access/accounts/' + target, json={'role': None})
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/sources/' + row['source_id'])).status_code == 403
            # Real stored cookie session still needs the existing CSRF contract.
            client.headers.pop('Authorization')
            start = await client.get('/auth/login')
            state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]
            assert (await client.get('/auth/callback', params={'state': state, 'code': 'fixture-only'})).status_code == 302
            profile = (await client.get('/api/v1/me')).json()
            assert (await client.post('/api/v1/sources/upload', data=fields, files={'file': ('cookie.txt', b'evidence')})).status_code == 403
            assert (await client.post('/api/v1/sources/upload', data=fields, files={'file': ('cookie.txt', b'evidence')}, headers={'X-C0-CSRF': profile['csrf_token'], 'Origin': 'https://wrong.example.test'})).status_code == 403
            accepted = await client.post('/api/v1/sources/upload', data=fields, files={'file': ('cookie.txt', b'evidence')}, headers={'X-C0-CSRF': profile['csrf_token'], 'Origin': ORIGIN})
            assert accepted.status_code == 202
            created.append(accepted.json()['source_id'])
    asyncio.run(check())


def test_upload_limits_invalid_boolean_and_chunked_body(source_http, monkeypatch):
    import starlette.formparsers
    real_spool = starlette.formparsers.SpooledTemporaryFile
    spools = []
    def spool(*args, **kwargs):
        file = real_spool(*args, **kwargs)
        spools.append(file)
        return file
    monkeypatch.setattr(starlette.formparsers, 'SpooledTemporaryFile', spool)
    async def check():
        application, _ = source_http
        app, owner, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN, headers={'Authorization': 'Bearer ' + owner}) as client:
            fields = {'title': 'Bounded', 'media_type': 'text/plain'}
            assert (await client.post('/api/v1/sources/upload', data={**fields, 'retain_original': 'maybe'}, files={'file': ('file', b'evidence')})).status_code == 422
            assert (await client.post('/api/v1/sources/upload', data=fields, files={'file': ('file', b'x' * (10 * 1024 * 1024 + 1))})).status_code == 413
            async def oversized():
                yield b'--fixture\r\nContent-Disposition: form-data; name="file"; filename="file"\r\n\r\n'
                for _ in range(162):
                    yield b'x' * 65536
                yield b'\r\n--fixture--\r\n'
            response = await client.post('/api/v1/sources/upload', content=oversized(), headers={'Content-Type': 'multipart/form-data; boundary=fixture'})
            assert response.status_code == 413 and response.json()['detail'] == 'upload_too_large'
            assert list(app.state.sources.originals.root.iterdir()) == []
            assert spools and all(file.closed for file in spools)
    asyncio.run(check())
