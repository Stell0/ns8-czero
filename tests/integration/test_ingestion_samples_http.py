# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Sample client over actual SDK/ASGI/OAuth/Core/PostgreSQL, with synthetic GitHub data."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.error
from uuid import UUID, uuid4

import anyio
from anyio.from_thread import start_blocking_portal
import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'samples/ingestion/src'))
from c0_ingest import auth
from c0_ingest.client import C0, CredentialAuth
from c0_ingest.errors import C0Error
from c0_ingest.state import atomic, digest, encoded, read
from c0_ingest.sources import submit_text, verify_document
from github_vault.bootstrap import bootstrap
from github_vault.c0_client import C0 as GitHubC0
from github_vault.models import TYPES
from github_vault.sync import sync
from czero_core.identity import PermissionDenied, Role
from czero_core.worker import Worker
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport
from test_spaces_http import space_http

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def sample_connection(transport, knowledge_http, space_http, monkeypatch, tmp_path, request):
    app, child, _, descriptor, pair, _, owner_token, _ = transport

    async def setup():
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                               headers={'Authorization': 'Bearer ' + owner_token}) as rest:
            profile = (await rest.get('/api/v1/profile')).json()
            existing = (await rest.get('/api/v1/object-types')).json()['types']
            return profile, {t['name'] for t in existing}

    profile, existing = asyncio.run(setup())
    config = {'url': ORIGIN + '/mcp', 'client_id': descriptor['client_id'],
              'credentials_file': str(tmp_path / 'oauth.json'), 'identity': profile['nickname'],
              'account_id': profile['id'], 'scopes': 'c0:read c0:write c0:admin',
              'space_name': 'Ingestion fixture ' + uuid4().hex, 'space_id': '',
              'poll_attempts': 4, 'poll_seconds': 0}
    auth.save_tokens(config, {'access_token': pair.access_token, 'refresh_token': pair.refresh_token,
                             'expires_in': pair.expires_in})
    value = read(config['credentials_file']); value['expires_at'] = 0
    atomic(config['credentials_file'], value)
    requested = []

    # One actual server lifespan/loop, shared by independent client sessions.
    # The SDK manager is deliberately single-use, as in a real server process.
    server_context = start_blocking_portal()
    server_portal = server_context.__enter__()
    lifespan = server_portal.wrap_async_context_manager(child.router.lifespan_context(child))
    lifespan.__enter__()

    def close_server():
        try:
            lifespan.__exit__(None, None, None)
        finally:
            server_context.__exit__(None, None, None)
    request.addfinalizer(close_server)

    async def dispatch(method, url, headers, body):
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN) as http:
            response = await http.request(method, url, headers=headers, content=body)
            return response.status_code, list(response.headers.multi_items()), response.content

    class PortalASGI(httpx2.AsyncBaseTransport):
        async def handle_async_request(self, message):
            body = await message.aread()
            status, headers, raw = await anyio.to_thread.run_sync(lambda: server_portal.call(
                dispatch, message.method, str(message.url), dict(message.headers), body))
            return httpx2.Response(status, headers=headers, content=raw)

    def open_asgi(request, **_):
        # Actual token/metadata/revocation endpoints. Transport-only substitution;
        # no OAuth outcome is mocked, and no installed instance is contacted.
        requested.append(request.full_url.split(ORIGIN, 1)[-1])
        status, _, body = server_portal.call(dispatch, request.get_method(), request.full_url,
                                             dict(request.header_items()), request.data)
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, 'fixture rejection', {}, None)
        result = io.BytesIO(body)
        result.status = status
        return result

    @asynccontextmanager
    async def connect(selected):
        async with httpx2.AsyncClient(transport=PortalASGI(), base_url=ORIGIN,
                                      auth=CredentialAuth(selected)) as http:
            async with Client(streamable_http_client(selected['url'], http_client=http)) as client:
                yield client

    monkeypatch.setattr('c0_ingest.auth.open_url', open_asgi)
    monkeypatch.setattr('c0_ingest.client.connection', connect)
    prepared = bootstrap(config)
    config['space_id'] = prepared['space_id']
    space_http[1].append(prepared['space_id'])
    space_http[2].extend(name for name in TYPES.values() if name not in existing)
    monkeypatch.setattr('c0_ingest.sources.sleep', lambda _: Worker(knowledge_http[4], app.state.jobs.registry).tick())
    yield config, requested


def snapshot(path, body):
    original = body.encode()
    content_hash = hashlib.sha256(original).hexdigest()
    sha = 'a' * 40
    repository = {'external_key': 'repo:7', 'repo_id': 7, 'full_name': 'org/project',
                  'url': 'https://github.com/org/project', 'provenance': ['https://github.com/org/project'],
                  'coverage': 'partial', 'owner': {'id': 8, 'type': 'Organization', 'login': 'org'}, 'parent': None}
    document = {'external_key': 'document:7:' + digest('README.md')[:24], 'repo_id': 7,
                'url': 'https://github.com/org/project/blob/' + sha + '/README.md',
                'provenance': ['https://github.com/org/project'], 'coverage': 'verified',
                'path': 'README.md', 'commit_sha': sha, 'sha256': content_hash,
                'size_bytes': len(original), 'content_path': 'documents/7/readme.txt',
                'license': None, 'retrieved_at': '2026-01-01T00:00:00Z'}
    rows = {'people': [], 'repositories': [repository], 'contributions': [], 'documents': [document]}
    atomic(path / document['content_path'], original)
    files = {}
    for name, records in rows.items():
        raw = b''.join(encoded(r) + b'\n' for r in records)
        atomic(path / (name + '.jsonl'), raw)
        files[name + '.jsonl'] = hashlib.sha256(raw).hexdigest()
    atomic(path / 'manifest.json', {'schema_version': 1, 'snapshot_id': path.name,
        'completeness': 'partial', 'window': {'since': '2025-01-01T00:00:00Z', 'until': '2025-12-31T23:59:59Z'},
        'files': files, 'counts': {name: len(records) for name, records in rows.items()},
        'scope': {'incremental': False}})


def counts(db, space):
    with db.engine.connect() as c:
        return {table: c.execute(text('SELECT count(*) FROM ' + table + ' WHERE space_id=:space'),
                                 {'space': UUID(space)}).scalar_one()
                for table in ('c0_objects', 'c0_object_relations', 'c0_sources', 'c0_source_versions', 'c0_wiki_revisions')}


def test_sample_full_sync_readback_repeat_and_uncertain_reply(sample_connection, knowledge_http, monkeypatch, tmp_path):
    selected, requested = sample_connection
    config = {'c0': selected, 'paths': {'state': str(tmp_path / 'state'), 'reports': str(tmp_path / 'reports')}}
    path = tmp_path / 'snapshot-one'
    snapshot(path, '# Example\n\nDistinctive original documentation phrase.\n')
    args = SimpleNamespace(space_name=selected['space_name'], input=str(path), since=None, until=None,
                           incremental=False, limit_repos=None, limit_people=None, validate_only=False,
                           dry_run=False, apply=True)
    original = GitHubC0.call
    lost = []
    wiki_requests = []

    def uncertain(client, name, **arguments):
        if name.startswith("wiki_"):
            wiki_requests.append(name)
        result = original(client, name, **arguments)
        if name == 'sources_ingest_text' and not lost:
            lost.append(result['id'])
            raise C0Error('Synthetic lost reply after committed ingestion')
        return result

    with monkeypatch.context() as m:
        m.setattr(GitHubC0, 'call', uncertain)
        failed, code = sync(config, args)
        assert code == 1 and failed['status'] == 'failed'
    with monkeypatch.context() as m:
        m.setattr(GitHubC0, 'call', uncertain)
        first, code = sync(config, args)
    assert not wiki_requests
    assert first['stats']['wiki_written'] == 0
    config['sync'] = {'publish_wiki': True}
    published, code = sync(config, args)
    assert code == 2 and published['stats']['wiki_written'] == 2
    assert code == 2 and first['status'] == 'verified_partial'
    assert first['stats']['documents_verified'] == 1 and first['stats']['search_verified'] == 1
    assert counts(knowledge_http[4], selected['space_id'])['c0_source_versions'] == 1
    before = counts(knowledge_http[4], selected['space_id'])
    repeated, code = sync(config, args)
    assert code == 2 and repeated['stats']['sources_unchanged'] == 1
    assert counts(knowledge_http[4], selected['space_id']) == before
    args.dry_run, args.apply = True, False
    assert sync(config, args)[0]['writes'] == 0
    assert counts(knowledge_http[4], selected['space_id']) == before
    assert requested.count('/oauth/token') == 1  # Actual refresh persisted across new SDK clients.
    assert read(selected['credentials_file'])['refresh_token'] != ''
    # A human edit must survive a later generated-summary update attempt.
    client = GitHubC0(selected)
    client.select_space(selected['space_id'])
    try:
        page = next(p for p in client.listing('wiki_pages_list', 'pages')
                    if p['slug'] == 'github-repository-7')
        client.call('wiki_pages_upsert', data={'slug': page['slug'], 'title': 'Human notes',
                    'body': 'Preserve this human edit.', 'expected_revision': page['revision'],
                    'metadata': {}, 'idempotency_key': uuid4().hex})
    finally:
        client.close()
    before = counts(knowledge_http[4], selected['space_id'])
    args.dry_run, args.apply = False, True
    blocked, code = sync(config, args)
    assert code == 1 and 'receipt' in blocked['error']
    assert counts(knowledge_http[4], selected['space_id']) == before
    client = GitHubC0(selected)
    client.select_space(selected['space_id'])
    try:
        assert client.call('wiki_pages_get', page_id=page['id'])['content']['body'] == 'Preserve this human edit.'
    finally:
        client.close()
    auth.disconnect(selected)
    with pytest.raises(C0Error):
        GitHubC0(selected)
    assert counts(knowledge_http[4], selected['space_id']) == before


def test_sample_conflict_and_current_reader_denial(sample_connection, transport, knowledge_http, monkeypatch, tmp_path):
    selected, _ = sample_connection
    client = GitHubC0(selected)
    client.select_space(selected['space_id'])
    try:
        original = submit_text(client, body='Initial original evidence.', title='Fixture',
                               metadata={'origin': 'synthetic'}, external_key='fixture-doc')
        Worker(knowledge_http[4], transport[0].state.jobs.registry).tick()
        verify_document(client, original, 'Initial original evidence.', attempts=2, seconds=0)
        source = client.call('sources_get', source_id=original['source_id'])
        concurrent = submit_text(client, body='Concurrent writer evidence.', title='Ignored on append',
                                 metadata={}, external_key='fixture-doc', source=source)
        with pytest.raises(C0Error):
            client.call('sources_ingest_text', data={'body': 'Stale replacement', 'title': source['title'],
                'metadata': source['metadata'], 'media_type': 'text/plain', 'source_id': source['id'],
                'expected_revision': source['revision'], 'idempotency_key': uuid4().hex})
        assert counts(knowledge_http[4], selected['space_id'])['c0_source_versions'] == 2
        with pytest.raises(C0Error):
            client.call('sources_get', source_id=source['id'], space_id=str(uuid4()))
    finally:
        client.close()
    app, _, _, _, _, issue, owner_token, member_token = transport
    access = app.state.auth.access
    owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    identity = app.state.auth.oidc.verify_access_token(member_token)
    with pytest.raises(PermissionDenied):
        access.resolve(identity)
    member = next(a for a in access.list_accounts(owner) if a['username'] == 'member')
    access.set_role(owner, member['id'], Role.READER)
    app.state.spaces.set_grant(owner, UUID(selected['space_id']), member['id'], Role.READER,
                              expected_revision=0, idempotency_key=uuid4().hex)
    pair = issue(identity, {'c0:read'})
    selected = {**selected, 'credentials_file': str(tmp_path / 'reader-oauth.json'),
                'scopes': 'c0:read', 'account_id': str(member['id']), 'identity': 'member'}
    auth.save_tokens(selected, {'access_token': pair.access_token, 'refresh_token': pair.refresh_token,
                               'expires_in': pair.expires_in})
    reader = GitHubC0(selected)
    try:
        with pytest.raises(C0Error, match='protected'):
            reader.select_space(selected['space_id'])
        reader.space_id = selected['space_id']
        with pytest.raises(C0Error):
            submit_text(reader, body='Denied', title='Denied', metadata={}, external_key='denied')
        assert counts(knowledge_http[4], selected['space_id'])['c0_source_versions'] == 2
    finally:
        reader.close()
