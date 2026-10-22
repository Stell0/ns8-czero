# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real controlled metadata HTTPS with public OAuth handlers and PostgreSQL."""
import asyncio
import json
import os
from pathlib import Path
import runpy
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text

from czero_core.cimd import CimdPolicyService
from czero_core.identity import PermissionDenied, Role
from czero_core.oauth_grants import GrantRejected
from test_auth_http import application, ORIGIN, PrivateFixture
from test_oauth_server_http import authorize, login, CALLBACK, RESOURCE

_fixture = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'cimd_https_fixture.py'))
certificates, Harness = _fixture['certificates'], _fixture['Harness']
URL, document = _fixture['URL'], _fixture['document']
pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def cimd_http(application):
    app, owner, *_ = application
    registry = app.state.delegated_grants.cimd
    registry.sync_policy(True)
    yield PrivateFixture((app, owner, registry))
    registry.sync_policy(False)
    with registry.access.database.engine.begin() as connection:
        connection.execute(text('DELETE FROM c0_client_onboarding WHERE issuer=:issuer'), {'issuer': registry.access.issuer})
        connection.execute(text('DELETE FROM c0_oauth_clients WHERE id IN (SELECT client_id FROM c0_cimd_clients)'))
    asyncio.run(app.state.cimd.fetcher.aclose())


async def approve(http, url=URL, *, scopes=None):
    preview = await http.post('/api/v1/oauth/cimd/preview', json={'metadata_url': url})
    assert preview.status_code == 200, preview.status_code
    result = await http.post('/api/v1/oauth/cimd/clients', json={'metadata_url': url,
        'metadata_digest': preview.json()['metadata_digest'], 'allowed_scopes': scopes or ['c0:read']})
    assert result.status_code == 201, result.status_code
    return result.json()


async def connect(http, public_id=URL):
    verifier, state = await authorize(http, {'client_id': public_id})
    profile = await login(http)
    view = await http.get('/oauth/consent/request')
    assert view.status_code == 200 and view.json()['client_id'] == public_id
    response = await http.post('/oauth/consent', json={'approve': True, 'scopes': ['c0:read']},
        headers={'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']})
    assert response.status_code == 200, response.status_code
    values = parse_qs(urlsplit(response.json()['redirect_uri']).query)
    if values['state'] != [state]:
        raise AssertionError('OAuth state binding changed')
    parameters = {'grant_type': 'authorization_code', 'client_id': public_id,
        'redirect_uri': CALLBACK, 'code': values['code'][0], 'code_verifier': verifier, 'resource': RESOURCE}
    token = await http.post('/oauth/token', data=parameters)
    assert token.status_code == 200, token.status_code
    return PrivateFixture((token.json(), parameters))



async def rejected_authorization(http, public_id, *, callback_error=False):
    response = await http.get('/oauth/authorize', params={'client_id': public_id,
        'redirect_uri': CALLBACK, 'response_type': 'code', 'code_challenge': 'a' * 43,
        'code_challenge_method': 'S256', 'scope': 'c0:read', 'resource': RESOURCE})
    if callback_error:
        assert response.status_code == 302
        target = urlsplit(response.headers['location'])
        assert target._replace(query='').geturl() == CALLBACK
        assert parse_qs(target.query)['error'] == ['invalid_request']
    else:
        assert response.status_code == 400 and response.json()['error'] == 'invalid_request'

def test_actual_https_review_approval_oauth_rotation_replay_and_no_token_fetch(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, registry = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                client = await approve(http)
                assert len(h.requests) == 2  # Approval fetches the document again.
                http.headers.pop('Authorization')
                tokens, code = await connect(http)
                assert registry.clients._lookup(client['client_id']) is None
                assert (await http.post('/oauth/token', data=code)).status_code == 400
                before = len(h.requests)
                # The metadata host can fail without affecting existing authority.
                h.status = 503
                refreshed = await http.post('/oauth/token', data={'grant_type': 'refresh_token',
                    'client_id': URL, 'refresh_token': tokens['refresh_token'], 'resource': RESOURCE})
                assert refreshed.status_code == 200
                current = refreshed.json()
                read = await http.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + current['access_token']})
                assert read.status_code == 200 and read.json()['name']
                wrong = await http.post('/oauth/token', data={'grant_type': 'refresh_token',
                    'client_id': client['client_id'], 'refresh_token': current['refresh_token'], 'resource': RESOURCE})
                assert wrong.status_code in (400, 401)
                replay = await http.post('/oauth/token', data={'grant_type': 'refresh_token',
                    'client_id': URL, 'refresh_token': tokens['refresh_token'], 'resource': RESOURCE})
                assert replay.status_code == 400
                assert (await http.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + current['access_token']})).status_code == 401
                assert len(h.requests) == before
    asyncio.run(check())


def test_unknown_urls_and_global_off_never_fetch_and_uuid_clients_continue(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, registry = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                known = await approve(http)
                actor = registry.access.resolve(app.state.auth.oidc.verify_access_token(owner))
                manual = app.state.oauth_clients.register(actor, 'Legacy UUID preserved', [CALLBACK])
                try:
                    http.headers.pop('Authorization')
                    pending = await http.get('/oauth/authorize', params={'client_id': 'https://unknown.example.test/client.json',
                        'redirect_uri': CALLBACK, 'response_type': 'code', 'code_challenge': 'a' * 43,
                        'code_challenge_method': 'S256', 'scope': 'c0:read', 'resource': RESOURCE})
                    assert pending.status_code == 302 and pending.headers['location'] == '/oauth/connect'
                    assert len(h.requests) == 2
                    assert (await http.get('/.well-known/oauth-authorization-server/oauth')).json()['client_id_metadata_document_supported'] is True
                    registry.sync_policy(False)
                    assert (await http.get('/.well-known/oauth-authorization-server/oauth')).json()['client_id_metadata_document_supported'] is False
                    await rejected_authorization(http, URL)
                    assert len(h.requests) == 2
                    tokens, _ = await connect(http, manual['client_id'])
                    assert tokens['refresh_token']
                    registry.sync_policy(True)
                    assert registry.clients._lookup(known['client_id']) is None
                finally:
                    with registry.access.database.engine.begin() as connection:
                        connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id': UUID(manual['client_id'])})
    asyncio.run(check())


def test_admin_reapproval_pins_digest_and_invalidates_previous_authority(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, registry = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                client = await approve(http)
                http.headers.pop('Authorization')
                tokens, _ = await connect(http)
                http.headers['Authorization'] = 'Bearer ' + owner
                h.body = document(client_name='Changed remote name')
                preview = (await http.post('/api/v1/oauth/cimd/preview', json={'metadata_url': URL})).json()
                state = (await http.get('/api/v1/oauth/cimd')).json()
                assert state['clients'][0]['review_required']
                assert (await http.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + tokens['access_token']})).status_code == 200
                changed_again = document(client_name='Changed after preview')
                h.body = changed_again
                body = {'metadata_digest': preview['metadata_digest'], 'allowed_scopes': ['c0:read'], 'expected_revision': 1}
                path = '/api/v1/oauth/cimd/clients/' + client['client_id']
                assert (await http.put(path, json=body)).status_code == 409
                preview = (await http.post('/api/v1/oauth/cimd/preview', json={'metadata_url': URL})).json()
                body['metadata_digest'] = preview['metadata_digest']
                result = await http.put(path, json=body)
                assert result.status_code == 200 and result.json()['revision'] == 2 and not result.json()['review_required']
                assert (await http.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + tokens['access_token']})).status_code == 401
                assert (await http.put(path, json=body)).status_code == 409
    asyncio.run(check())


def test_no_store_refreshes_after_login_and_denial_does_not_fetch(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, registry = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            h.headers = [(b'Cache-Control', b'no-store')]
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                await approve(http)
                http.headers.pop('Authorization')
                await connect(http)
                assert len(h.requests) == 4  # Two Admin, begin, fresh approval after SSO.
                await authorize(http, {'client_id': URL})
                profile = (await http.get('/api/v1/me')).json()
                before = len(h.requests)
                h.status = 503
                denied = await http.post('/oauth/consent', json={'approve': False},
                    headers={'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']})
                assert denied.status_code == 200 and 'access_denied' in denied.json()['redirect_uri']
                assert len(h.requests) == before
                await rejected_authorization(http, URL, callback_error=True)
    asyncio.run(check())


def test_authcode_only_metadata_omits_refresh_in_public_sdk_response(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, _ = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            h.body = document(grant_types=['authorization_code'])
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                await approve(http)
                http.headers.pop('Authorization')
                tokens, _ = await connect(http)
                if 'refresh_token' in tokens:
                    raise AssertionError('Code-only metadata issued refresh authority')
    asyncio.run(check())



def test_real_url_tokens_support_current_legacy_sdk_tools_and_revocation(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, _ = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                await approve(http)
                http.headers.pop('Authorization')
                tokens, _ = await connect(http)
                before = len(h.requests)
                h.status = 503
                child = app.state.mcp_app
                async with child.router.lifespan_context(child):
                    for mode in ('auto', 'legacy'):
                        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                                headers={'Authorization': 'Bearer ' + tokens['access_token']}) as transport:
                            async with Client(streamable_http_client(RESOURCE, http_client=transport), mode=mode) as sdk:
                                tools = (await sdk.list_tools()).tools
                                assert len(tools) == 77
                                assert not any(tool.name.startswith('cimd') for tool in tools)
                                profile = await sdk.call_tool('get_profile', {})
                                assert not profile.is_error and profile.structured_content['name']
                                denied = await sdk.call_tool('wiki_pages_create', {'data': {'slug': 'not-authorized',
                                    'title': 'No write scope', 'body': 'No write authority', 'idempotency_key': 'cimd-no-scope'}})
                                assert denied.is_error and denied.content[0].text == 'insufficient_scope'
                revoked = await http.post('/oauth/revoke', data={'client_id': URL,
                    'token': tokens['access_token'], 'resource': RESOURCE})
                assert revoked.status_code == 200
                assert (await http.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + tokens['access_token']})).status_code == 401
                assert len(h.requests) == before
    asyncio.run(check())


def test_stale_metadata_outage_blocks_new_consent_then_recovers(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, registry = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                await approve(http)
                http.headers.pop('Authorization')
                tokens, _ = await connect(http)
                h.fetcher.cache.clear()
                with registry.access.database.engine.begin() as c:
                    c.execute(text("UPDATE c0_cimd_clients SET verified_at=now()-interval '120 seconds',fresh_until=now()-interval '60 seconds'"))
                h.status = 503
                await rejected_authorization(http, URL, callback_error=True)
                assert (await http.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + tokens['access_token']})).status_code == 200
                h.status = 200
                await authorize(http, {'client_id': URL})
    asyncio.run(check())


def test_metadata_cache_and_authority_survive_restart_and_missing_sso_revokes(cimd_http, monkeypatch, certificates):
    from czero_app.main import create_app
    from czero_app.cimd_server import CimdAdapter
    async def check():
        app, owner, registry = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                await approve(http)
                http.headers.pop('Authorization')
                tokens, _ = await connect(http)
                before = len(h.requests)
                # Warm a fresh process's empty cache from the approved persisted
                # descriptor, then prove an outage does not force another fetch.
                fresh = CimdAdapter(registry)
                try:
                    h.status = 503
                    assert await fresh.verification(URL)
                    assert not fresh.fetcher.flights and len(h.requests) == before
                finally:
                    await fresh.fetcher.aclose()
                monkeypatch.setenv('CZERO_CIMD_ENABLED', 'true')
                restarted = create_app('czero900', Path(__file__).resolve().parents[2]/'app/static', '',
                    registry.access.database, auth=app.state.auth)
                async with restarted.router.lifespan_context(restarted):
                    assert registry.enabled()
                    assert app.state.delegated_grants.verify(tokens['access_token'], resource=RESOURCE)
                # Authentication is absent even though the native switch remains
                # true. Startup still applies effective-off policy through DB.
                without_sso = create_app('czero900', Path(__file__).resolve().parents[2]/'app/static', '', registry.access.database)
                assert without_sso.state.auth is None
                async with without_sso.router.lifespan_context(without_sso):
                    assert not registry.enabled()
                    with pytest.raises(GrantRejected):
                        app.state.delegated_grants.verify(tokens['access_token'], resource=RESOURCE)
    asyncio.run(check())


def test_delegated_read_scope_cannot_administer_cimd_even_for_owner(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, _ = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                client = await approve(http)
                http.headers.pop('Authorization')
                tokens, _ = await connect(http)
                http.cookies.clear()
                http.headers['Authorization'] = 'Bearer ' + tokens['access_token']
                before = len(h.requests)
                requests = [
                    ('GET', '/api/v1/oauth/cimd', None),
                    ('POST', '/api/v1/oauth/cimd/preview', {'metadata_url': URL}),
                    ('POST', '/api/v1/oauth/cimd/clients', {'metadata_url': URL,
                        'metadata_digest': client['metadata_digest']}),
                    ('PUT', '/api/v1/oauth/cimd/clients/' + client['client_id'],
                        {'metadata_digest': client['metadata_digest'], 'expected_revision': client['revision']}),
                ]
                for method, path, data in requests:
                    response = await http.request(method, path, json=data)
                    assert response.status_code == 403, (method, response.status_code)
                assert len(h.requests) == before
    asyncio.run(check())


def test_browser_cimd_writes_require_origin_and_csrf_before_fetch(cimd_http, monkeypatch, certificates):
    async def check():
        app, _, _ = cimd_http
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                started = await http.get('/auth/login')
                state = parse_qs(urlsplit(started.headers['location']).query)['state'][0]
                response = await http.get('/auth/callback', params={'state': state, 'code': 'unit-only-code'})
                assert response.status_code == 302 and response.headers['location'] == '/'
                profile = (await http.get('/api/v1/me')).json()
                body = {'metadata_url': URL}
                for headers in ({}, {'Origin': ORIGIN}, {'Origin': 'https://wrong.example.test',
                        'X-C0-CSRF': profile['csrf_token']}):
                    response = await http.post('/api/v1/oauth/cimd/preview', json=body, headers=headers)
                    assert response.status_code == 403
                assert not h.requests
                response = await http.post('/api/v1/oauth/cimd/preview', json=body,
                    headers={'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']})
                assert response.status_code == 200 and len(h.requests) == 1
    asyncio.run(check())


def test_admin_role_is_rechecked_after_metadata_io(cimd_http, application, monkeypatch, certificates):
    async def check():
        app, owner, registry = cimd_http
        member = application[2]
        access = registry.access
        owner_actor = access.resolve(app.state.auth.oidc.verify_access_token(owner))
        try:
            access.resolve(app.state.auth.oidc.verify_access_token(member))
        except PermissionDenied:
            pass
        account = next(row for row in access.list_accounts(owner_actor) if row['username'] == 'member')
        account_id = account['id']
        access.set_role(owner_actor, account_id, Role.ADMIN)
        async with Harness(monkeypatch, certificates) as h:
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
                http.headers['Authorization'] = 'Bearer ' + owner
                preview = (await http.post('/api/v1/oauth/cimd/preview', json={'metadata_url': URL})).json()
                h.gate = asyncio.Event()
                http.headers['Authorization'] = 'Bearer ' + member
                pending = asyncio.create_task(http.post('/api/v1/oauth/cimd/clients', json={
                    'metadata_url': URL, 'metadata_digest': preview['metadata_digest']}))
                async with asyncio.timeout(3):
                    while len(h.requests) < 2:
                        await asyncio.sleep(0.01)
                access.set_role(owner_actor, account_id, Role.READER)
                h.gate.set()
                assert (await pending).status_code == 403
                assert registry.status(owner_actor)['clients'] == []
    asyncio.run(check())


def test_sdk_automatically_selects_cimd_from_empty_storage_and_renews_without_fetch(cimd_http, monkeypatch, certificates):
    from mcp.client.auth.oauth2 import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata, AuthorizationCodeResult
    async def check():
        app, owner, _ = cimd_http
        class Storage:
            tokens = client = None
            async def get_tokens(self): return self.tokens
            async def set_tokens(self, value): self.tokens = value
            async def get_client_info(self): return self.client
            async def set_client_info(self, value): self.client = value
        storage = Storage()
        # Keep secrets out of object representations and assertion diagnostics.
        callback_values = []
        async with Harness(monkeypatch, certificates) as h:
            h.headers = [(b'Cache-Control', b'no-store')]
            app.state.cimd.fetcher = h.fetcher
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as browser:
                browser.headers['Authorization'] = 'Bearer ' + owner
                await approve(browser)
                browser.headers.pop('Authorization')
                async def redirect(url):
                    response = await browser.get(url)
                    assert response.status_code == 302
                    profile = await login(browser)
                    response = await browser.post('/oauth/consent', json={'approve': True, 'scopes': ['c0:read']},
                        headers={'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']})
                    assert response.status_code == 200
                    values = parse_qs(urlsplit(response.json()['redirect_uri']).query)
                    callback_values.append(AuthorizationCodeResult(code=values['code'][0], state=values['state'][0]))
                async def callback(): return callback_values[-1]
                def provider():
                    return OAuthClientProvider(server_url=RESOURCE, client_metadata_url=URL,
                        client_metadata=OAuthClientMetadata(redirect_uris=[CALLBACK], scope='c0:read',
                            token_endpoint_auth_method='none', grant_types=['authorization_code', 'refresh_token'],
                            response_types=['code']), storage=storage, redirect_handler=redirect, callback_handler=callback)
                child = app.state.mcp_app
                async with child.router.lifespan_context(child):
                    async def read(auth):
                        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN, auth=auth) as http:
                            async with Client(streamable_http_client(RESOURCE, http_client=http)) as sdk:
                                assert len((await sdk.list_tools()).tools) == 77
                                assert not (await sdk.call_tool('get_profile', {})).is_error
                    auth = provider()
                    await read(auth)
                    assert storage.client.client_id == URL and len(callback_values) == 1
                    assert storage.tokens.scope == 'c0:read' and len(h.requests) == 4
                    old_refresh = storage.tokens.refresh_token
                    # Exercise the SDK's own refresh path using a past local
                    # deadline; real five-minute continuity is a live gate.
                    assert auth.context.token_expiry_time is not None
                    auth.context.token_expiry_time = 1
                    h.status = 503
                    await read(auth)
                    if storage.tokens.refresh_token == old_refresh:
                        raise AssertionError('SDK did not rotate expired access authority')
                    assert len(h.requests) == 4 and len(callback_values) == 1
    asyncio.run(check())
