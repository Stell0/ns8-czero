# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed Reader approval, real metadata HTTPS and exact code redemption."""
import asyncio
import os
from urllib.parse import parse_qs, urlsplit

import pytest

from test_cimd_http import cimd_http, certificates, Harness, URL, document
from test_auth_http import application
from test_onboarding_http import browser, signin, headers, parameters
from test_oauth_server_http import RESOURCE

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1', '[::1]'])
@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_native_reader_approval_consent_reconnect_and_exact_token_callback(cimd_http, monkeypatch, certificates, host, method):
    async def check():
        app, _, registry = cimd_http
        registry.access.admit_readers = True
        registered = 'http://' + host + '/callback'
        async with Harness(monkeypatch, certificates) as harness:
            harness.body = document(redirect_uris=[registered])
            app.state.cimd.fetcher = harness.fetcher
            async with browser(app) as admin, browser(app) as user:
                admin_profile = await signin(admin)
                profile = await signin(user, code='unit-only-forbidden-code')
                assert profile['role'] == 'reader'
                for port in (53123, 53124):
                    callback = 'http://' + host + ':' + str(port) + '/callback'
                    raw, verifier = parameters(redirect_uri=callback)
                    response = (await user.get('/oauth/authorize', params=raw) if method == 'GET'
                                else await user.post('/oauth/authorize', data=raw))
                    if port == 53123:
                        assert response.status_code == 302 and response.headers['location'] == '/oauth/connect'
                        pending = await user.post('/oauth/connect/request', json={}, headers=headers(profile))
                        assert pending.status_code == 200 and not pending.json()['approved']
                        path = '/api/v1/access/accounts/' + profile['id'] + '/applications'
                        request = (await admin.get(path)).json()['applications'][0]
                        path = '/api/v1/access/requests/' + request['id']
                        review = await admin.post(path + '/preview', headers=headers(admin_profile))
                        assert review.status_code == 200
                        assert review.json()['request']['callback'] == callback
                        assert review.json()['descriptor']['redirect_uris'] == [registered]
                        body = {'metadata_digest': review.json()['metadata_digest'], 'allowed_scopes': ['c0:admin']}
                        denied = await admin.post(path + '/approve', json=body, headers=headers(admin_profile))
                        assert denied.status_code == 409
                        assert registry.clients._lookup(URL) is None
                        body['allowed_scopes'] = ['c0:read']
                        approved = await admin.post(path + '/approve', json=body, headers=headers(admin_profile))
                        assert approved.status_code == 200
                        for rejected in ('http://localhost.evil.test:53123/callback',
                                         'http://' + host + ':53123/other',
                                         'https://' + host + ':53123/callback'):
                            denied = await user.get('/oauth/authorize', params={**raw, 'redirect_uri': rejected})
                            assert denied.status_code == 400
                            assert 'location' not in denied.headers and 'set-cookie' not in denied.headers
                        pending = await user.post('/oauth/connect/request', json={}, headers=headers(profile))
                        assert pending.status_code == 200 and pending.json()['approved']
                        rows = (await admin.get('/api/v1/access/accounts/' + profile['id'] + '/applications')).json()['applications']
                        assert rows[0]['status'] == 'waiting_for_consent'
                        continued = await user.post('/oauth/connect/continue', json={'scopes': ['c0:read']}, headers=headers(profile))
                        assert continued.status_code == 200
                    else:
                        # Already approved: exercise both Core and the SDK's authorization guard.
                        assert response.status_code == 302 and response.headers['location'].endswith('/oauth/consent')
                    view = await user.get('/oauth/consent/request')
                    assert view.status_code == 200 and view.json()['callback'] == callback
                    assert view.json()['eligible_scopes'] == ['c0:read']
                    result = await user.post('/oauth/consent', json={'approve': True, 'scopes': ['c0:read']}, headers=headers(profile))
                    assert result.status_code == 200
                    target = urlsplit(result.json()['redirect_uri'])
                    assert target._replace(query='').geturl() == callback
                    query = parse_qs(target.query)
                    assert query['state'] == [raw['state']]
                    token = {'grant_type': 'authorization_code', 'client_id': URL, 'redirect_uri': callback,
                             'code': query['code'][0], 'code_verifier': verifier, 'resource': RESOURCE}
                    for changed in ({'redirect_uri': registered}, {'redirect_uri': callback.replace(str(port), '53125')},
                                    {'code_verifier': 'x' * 43}):
                        assert (await user.post('/oauth/token', data={**token, **changed})).status_code == 400
                    pair = await user.post('/oauth/token', data=token)
                    assert pair.status_code == 200 and pair.json()['scope'] == 'c0:read'
                    assert (await user.get('/api/v1/profile', headers={'Authorization': 'Bearer ' + pair.json()['access_token']})).status_code == 200
                    assert (await user.post('/oauth/token', data=token)).status_code == 400
                    saved = registry.clients._lookup(URL)
                    assert saved['redirect_uris'] == [registered] and saved['allowed_scopes'] == ['c0:read']
                    assert (await user.get('/api/v1/me')).json()['role'] == 'reader'
    asyncio.run(check())
