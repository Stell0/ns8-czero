# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""First-time real OAuth handlers, signed native identity and controlled TLS."""
import asyncio
import json
import os
import secrets
from urllib.parse import parse_qs, urlencode, urlsplit

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text

from czero_core.oauth_grants import pkce_challenge
from test_auth_http import application, ORIGIN
from test_cimd_http import cimd_http, certificates, Harness, URL, approve
from test_oauth_server_http import CALLBACK, RESOURCE

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def parameters(**updates):
    verifier = secrets.token_urlsafe(32)
    return {'client_id': URL, 'redirect_uri': CALLBACK, 'response_type': 'code',
            'code_challenge_method': 'S256', 'code_challenge': pkce_challenge(verifier),
            'state': secrets.token_urlsafe(32), 'scope': 'c0:read', 'resource': RESOURCE, **updates}, verifier


async def signin(client, *, code='unit-only-code', target='/', return_to=None):
    response = await client.get('/auth/login', params={'return_to': return_to} if return_to else None)
    state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
    response = await client.get('/auth/callback', params={'state': state, 'code': code})
    assert response.status_code == 302 and response.headers['location'] == target
    response = await client.get('/api/v1/me')
    assert response.status_code == 200
    return response.json()


def browser(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN)


def headers(profile):
    return {'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']}


def test_new_reader_gets_signin_visible_approval_then_explicit_consent_and_real_token(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, registry = cimd_http
        registry.access.admit_readers = True
        async with Harness(monkeypatch, certificates) as harness:
            app.state.cimd.fetcher = harness.fetcher
            async with browser(app) as user, browser(app) as admin:
                raw, verifier = parameters()
                response = await user.get('/oauth/authorize', params=raw)
                assert response.status_code == 302 and response.headers['location'] == '/oauth/connect'
                assert all(flag in response.headers['set-cookie'] for flag in ('HttpOnly', 'Secure', 'SameSite=lax'))
                assert raw['state'] not in response.headers['location'] and not harness.requests
                response = await user.get('/oauth/connect')
                assert response.status_code == 302 and response.headers['location'] == '/auth/login'
                profile = await signin(user, code='unit-only-forbidden-code', target='/oauth/connect')
                assert profile['role'] == 'reader' and not profile['is_owner']
                assert (await user.get('/oauth/connect')).status_code == 200
                assert (await user.post('/oauth/connect/request', json={})).status_code == 403
                request = await user.post('/oauth/connect/request', json={}, headers=headers(profile))
                assert request.status_code == 200 and not request.json()['approved']
                assert not {'state', 'code_challenge', 'native_client', 'issuer'} & request.json().keys()
                assert not harness.requests
                assert (await user.get('/api/v1/oauth/connection-requests')).status_code == 403
                admin.headers['Authorization'] = 'Bearer ' + owner
                queue = (await admin.get('/api/v1/oauth/connection-requests')).json()['requests']
                assert len(queue) == 1 and queue[0]['username'] == 'member'
                assert raw['state'] not in json.dumps(queue)
                await approve(admin)
                assert len(harness.requests) == 2
                next_step = await user.post('/oauth/connect/continue', json={'scopes': ['c0:read']}, headers=headers(profile))
                assert next_step.status_code == 200 and next_step.json() == {'next': '/oauth/consent'}
                assert 'c0_onboarding' not in user.cookies
                with registry.access.database.engine.connect() as connection:
                    assert connection.execute(text('SELECT count(*) FROM c0_oauth_grants WHERE account_id=:id'), {'id': profile['id']}).scalar_one() == 0
                consent = await user.get('/oauth/consent/request')
                assert consent.status_code == 200 and consent.json()['eligible_scopes'] == ['c0:read']
                result = await user.post('/oauth/consent', json={'approve': True, 'scopes': ['c0:read']}, headers=headers(profile))
                assert result.status_code == 200
                callback = parse_qs(urlsplit(result.json()['redirect_uri']).query)
                assert callback['state'] == [raw['state']]
                result = await user.post('/oauth/token', data={'grant_type': 'authorization_code', 'client_id': URL,
                    'redirect_uri': CALLBACK, 'code': callback['code'][0], 'code_verifier': verifier, 'resource': RESOURCE})
                assert result.status_code == 200 and result.json()['scope'] == 'c0:read'
                pair = result.json()
                assert (await admin.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + pair['access_token']})).json()['id'] == profile['id']
                assert (await user.post('/oauth/connect/continue', json={'scopes': ['c0:read']}, headers=headers(profile))).status_code == 410
    asyncio.run(check())


def test_registered_read_client_can_explicitly_narrow_a_broader_reconnect_request(cimd_http, monkeypatch, certificates):
    async def check():
        app, owner, _ = cimd_http
        async with Harness(monkeypatch, certificates) as harness:
            app.state.cimd.fetcher = harness.fetcher
            async with browser(app) as user, browser(app) as admin:
                admin.headers['Authorization'] = 'Bearer ' + owner
                await approve(admin)
                raw, _ = parameters(scope='c0:read c0:write c0:admin')
                response = await user.get('/oauth/authorize', params=raw)
                assert response.status_code == 302 and response.headers['location'] == '/oauth/connect'
                profile = await signin(user, target='/oauth/connect')
                await user.post('/oauth/connect/request', json={}, headers=headers(profile))
                bad = await user.post('/oauth/connect/continue', json={'scopes': ['c0:admin']}, headers=headers(profile))
                assert bad.status_code == 410
                result = await user.post('/oauth/connect/continue', json={'scopes': ['c0:read']}, headers=headers(profile))
                assert result.status_code == 200
                consent = (await user.get('/oauth/consent/request')).json()
                assert consent['scopes'] == ['c0:read']
    asyncio.run(check())


@pytest.mark.parametrize('change', [{'resource': RESOURCE + '/wrong'}, {'redirect_uri': 'javascript:alert(1)'},
    {'code_challenge_method': 'plain'}, {'client_secret': 'rejected'}, {'response_type': 'token'}])
def test_invalid_first_connection_does_not_create_handoff_or_fetch(cimd_http, monkeypatch, certificates, change):
    async def check():
        app, _, registry = cimd_http
        async with Harness(monkeypatch, certificates) as harness:
            app.state.cimd.fetcher = harness.fetcher
            async with browser(app) as user:
                response = await user.get('/oauth/authorize', params=parameters(**change)[0])
                assert response.status_code == 400 and 'c0_onboarding' not in user.cookies
                assert not harness.requests
    asyncio.run(check())


def test_duplicate_known_or_unknown_fields_fail_before_handoff(cimd_http):
    async def check():
        app, *_ = cimd_http
        async with browser(app) as user:
            for method in ('GET', 'POST'):
                for field in ('client_id', 'future_extension'):
                    raw = parameters()[0]; raw['future_extension'] = 'ignored'
                    value = urlencode([*raw.items(), (field, raw[field])])
                    response = await user.get('/oauth/authorize?' + value) if method == 'GET' else await user.post('/oauth/authorize', content=value, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                    assert response.status_code == 400 and 'c0_onboarding' not in user.cookies
    asyncio.run(check())


def test_handoff_policy_change_binding_and_expired_page_are_human_readable(cimd_http):
    async def check():
        app, _, registry = cimd_http
        async with browser(app) as user, browser(app) as other:
            await user.get('/oauth/authorize', params=parameters()[0])
            profile = await signin(user, target='/oauth/connect')
            await user.post('/oauth/connect/request', json={}, headers=headers(profile))
            other.cookies.set('c0_onboarding', user.cookies.get('c0_onboarding'), domain='c0.example.test', path='/')
            assert (await other.post('/oauth/connect/request', json={}, headers=headers(profile))).status_code == 401
            registry.sync_policy(False); registry.sync_policy(True)
            assert (await user.post('/oauth/connect/request', json={}, headers=headers(profile))).status_code == 410
            page = await user.get('/oauth/connect')
            assert page.status_code == 200 and 'Back to setup' in page.text
            assert page.headers['cache-control'] == 'no-store' and page.headers['referrer-policy'] == 'no-referrer'
    asyncio.run(check())


@pytest.mark.parametrize('target', ['agents', 'admin', 'https://evil.example.test', '//evil.example.test'])
def test_normal_signin_returns_only_to_fixed_local_pages(application, target):
    async def check():
        async with browser(application[0]) as user:
            expected = '/' + target if target in ('agents', 'admin') else '/'
            await signin(user, target=expected, return_to=target)
            assert 'c0_login_return' not in user.cookies
    asyncio.run(check())
