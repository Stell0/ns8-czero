# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Google connection endpoints use browser session and exact-origin CSRF authority."""
import asyncio
import os
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from czero_app.google_drive import GoogleDrive, SCOPE
from czero_app.google_drive_routes import CALLBACK, ROOT
from test_auth_http import application, ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='disposable PostgreSQL required')


def test_google_browser_authorization_and_callback_binding(application, monkeypatch):
    async def check():
        app, owner_token, _, _, _, _ = application
        google = GoogleDrive('client', 'secret', Fernet(Fernet.generate_key()))
        monkeypatch.setattr(app.state, 'google_drive', google)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            forbidden = {'Authorization': 'Bearer ' + owner_token}
            space = next(row['id'] for row in (await client.get('/api/v1/spaces', headers=forbidden)).json()['spaces'] if row['shared'])
            selector = {'space_id': space}
            assert (await client.get(ROOT + '/connection', headers=forbidden, params=selector)).status_code == 403
            auth = app.state.auth
            identity = auth.oidc.verify_access_token(owner_token)
            cookie = auth.sessions.create(identity)
            client.cookies.set('c0_session', cookie)
            headers = {'Origin': ORIGIN, 'X-C0-CSRF': auth.sessions.get(cookie).csrf_token}
            assert (await client.get(ROOT + '/connection', params=selector)).json()['connected'] is False
            for missing in ({}, {'Origin': ORIGIN}, {**headers, 'Origin': 'https://other.example'}):
                assert (await client.post(ROOT + '/connect', params=selector, headers=missing, json={'offline': False})).status_code == 403
            r = await client.post(ROOT + '/connect', params=selector, headers=headers, json={'offline': False})
            assert r.status_code == 200, r.text
            query = parse_qs(urlsplit(r.json()['url']).query)
            assert query['scope'] == [SCOPE] and query['redirect_uri'] == [ORIGIN + CALLBACK]
            state = query['state'][0]
            parameters = [('state', state), ('error', 'access_denied')]
            assert (await client.get(CALLBACK, params=parameters + [('state', state)])).status_code == 400
            assert (await client.get(CALLBACK, params=parameters, headers={'Host': 'elsewhere.example'})).status_code == 400
            client.cookies.set('c0_session', auth.sessions.create(identity))
            assert (await client.get(CALLBACK, params=parameters)).status_code == 403
            client.cookies.set('c0_session', cookie)
            cancelled = await client.get(CALLBACK, params=parameters)
            assert cancelled.status_code == 303
            assert cancelled.headers['referrer-policy'] == 'no-referrer'
            assert parse_qs(urlsplit(cancelled.headers['location']).query) == {
                'google_drive': ['cancelled'], 'space_id': [space], 'offline': ['0']}
            assert (await client.get(CALLBACK, params=parameters)).status_code == 403
            assert (await client.get(ROOT + '/connection', params=selector)).json()['connected'] is False
            assert not any('google_drive' in name for name in app.state.operation_catalog.registry._operations)
    asyncio.run(check())
