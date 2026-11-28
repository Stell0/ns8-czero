# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed offline-provider responses through actual consent/OAuth/account HTTP."""
import asyncio
import os
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

from oauth_browser import OAuthBrowser
from httpx import ASGITransport
import pytest
from sqlalchemy import text

from test_session_renewal_http import renewing_app, login, refresh
from test_oauth_server_http import authorize, CALLBACK, RESOURCE
from test_auth_http import ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


async def background_pair(client, saved, state):
    original = await login(client,state)
    verifier, _ = await authorize(client,saved,scope='c0:read c0:write')
    initial = (await client.get('/oauth/consent/request')).json()
    assert initial['background_supported'] and not initial['background_ready'] and not initial['background_requested']
    headers = {'Origin':ORIGIN,'X-C0-CSRF':original['csrf_token']}
    result = await client.post('/oauth/consent/background',
        json={'draft_id': initial['draft_id'], 'scopes': ['c0:read', 'c0:write']}, headers=headers)
    assert result.status_code == 200 and urlsplit(result.json()['next']).path == '/auth/login'
    assert all(flag in result.headers['set-cookie'] for flag in ('Secure','HttpOnly','SameSite=lax','Max-Age=300'))
    started = await client.get('/auth/login')
    assert started.status_code == 302
    fields = parse_qs(urlsplit(started.headers['location']).query)
    assert fields['scope'] == ['openid profile offline_access'] and fields['prompt'] == ['login']
    state['nonce'] = fields['nonce'][0]; state['offline'] = True
    completed = await client.get('/auth/callback',params={'code':'private-code','state':fields['state'][0]})
    assert completed.status_code == 302 and urlsplit(completed.headers['location']).path == '/oauth/consent'
    assert 'Max-Age=28800' in completed.headers['set-cookie']
    view = (await client.get('/oauth/consent/request')).json()
    assert view['background_ready'] and view['background_requested'] and view['expires_at'] == initial['expires_at']
    assert view['draft_id'] == initial['draft_id']
    profile = (await client.get('/api/v1/me')).json()
    assert profile['id'] == original['id']
    accepted = await client.post('/oauth/consent',
        json={'draft_id': view['draft_id'], 'approve': True, 'scopes': ['c0:read', 'c0:write'], 'persistent': True},
        headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
    assert accepted.status_code == 200
    code = parse_qs(urlsplit(accepted.json()['redirect_uri']).query)['code'][0]
    issued = await client.post('/oauth/token',data={'grant_type':'authorization_code','client_id':saved['client_id'],
        'code':code,'redirect_uri':CALLBACK,'code_verifier':verifier,'resource':RESOURCE})
    assert issued.status_code == 200
    assert issued.json()['scope'] == 'c0:read c0:write' and 0 < issued.json()['expires_in'] <= 300
    return issued.json(), profile


@pytest.mark.parametrize(('renewing_app', 'background'), [
    ((43200, 3600), False),
    ((28800, 3600), True),
], indirect=['renewing_app'])
def test_registered_client_can_require_session_only_consent(renewing_app, background):
    async def check():
        app, saved, clock, state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            if background:
                _, profile = await background_pair(client, saved, state)
            else:
                profile = await login(client, state)
            headers = {'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']}
            verifier, request_state = await authorize(client, saved, method='POST' if background else 'GET',
                optional=(('c0_session_only', 'true'),))
            view = (await client.get('/oauth/consent/request')).json()
            assert not view['background_supported'] and not view['background_ready']

            pending = client.cookies.get(client.binding_cookie)
            browser_binding = pending
            client.cookies.set(client.binding_cookie, browser_binding.removeprefix('s-'),
                domain='c0.example.test', path='/')
            assert (await client.get('/oauth/consent/request')).status_code == 400
            client.cookies.set(client.binding_cookie, pending, domain='c0.example.test', path='/')

            choice = {'draft_id': view['draft_id'], 'scopes': ['c0:read']}
            offline = await client.post('/oauth/consent/background', json=choice, headers=headers)
            assert offline.status_code == 400
            persistent = await client.post('/oauth/consent', json={**choice, 'approve': True, 'persistent': True},
                headers=headers)
            assert persistent.status_code == 400

            accepted = await client.post('/oauth/consent', json={**choice, 'approve': True}, headers=headers)
            assert accepted.status_code == 200
            callback = parse_qs(urlsplit(accepted.json()['redirect_uri']).query)
            assert callback['state'] == [request_state]
            issued = await client.post('/oauth/token', data={
                'grant_type': 'authorization_code', 'client_id': saved['client_id'],
                'redirect_uri': CALLBACK, 'code': callback['code'][0],
                'code_verifier': verifier, 'resource': RESOURCE,
            })
            assert issued.status_code == 200 and issued.json()['refresh_token']
            with app.state.auth.access.database.engine.connect() as connection:
                expires = connection.execute(text('''SELECT extract(epoch FROM expires_at)
                    FROM c0_oauth_grants WHERE client_id=:id AND NOT persistent'''),
                    {'id': UUID(saved['client_id'])}).scalar_one()
            assert expires == clock[0] + (3600 if background else 8 * 3600)
            pair = issued.json()
            for advance in (0,) if background else (1800, 1801):
                clock[0] += advance
                renewed = await refresh(client, saved, pair)
                assert renewed.status_code == 200 and renewed.json()['refresh_token'] != pair['refresh_token']
                pair = renewed.json()
            clock[0] = int(expires)
            assert (await refresh(client, saved, pair)).status_code == 400
    asyncio.run(check())


def test_replaced_consent_draft_cannot_authorize_or_deny_a_different_client(renewing_app):
    async def check():
        app, first_client, _, state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            _, profile = await background_pair(client, first_client, state)
            headers = {'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']}
            registration = await client.post('/api/v1/oauth/clients', headers=headers, json={
                'client_name': 'Second consent client',
                'redirect_uris': [CALLBACK],
                'allowed_scopes': ['c0:read'],
            })
            assert registration.status_code == 201
            second_client = registration.json()
            try:
                await authorize(client, first_client)
                first = (await client.get('/oauth/consent/request')).json()
                verifier, second_state = await authorize(client, second_client)
                second = (await client.get('/oauth/consent/request')).json()
                assert first['client_id'] == first_client['client_id']
                assert second['client_id'] == second_client['client_id']
                assert first['draft_id'] != second['draft_id']
                assert second['background_ready'] and not second['background_requested']
                choice = {'draft_id': first['draft_id'], 'scopes': ['c0:read']}
                for path, payload in (
                    ('/oauth/consent', {**choice, 'approve': True}),
                    ('/oauth/consent', {**choice, 'approve': True, 'persistent': True}),
                    ('/oauth/consent', {**choice, 'approve': False}),
                    ('/oauth/consent/background', choice),
                ):
                    rejected = await client.post(path, json=payload, headers=headers)
                    assert rejected.status_code == 400 and rejected.json() == {'detail': 'invalid_consent'}
                    assert 'set-cookie' not in rejected.headers
                assert 'c0_background_login' not in client.cookies
                unchanged = (await client.get('/oauth/consent/request')).json()
                assert unchanged['draft_id'] == second['draft_id'] and not unchanged['background_requested']
                current_choice = {**choice, 'draft_id': second['draft_id']}
                accepted = await client.post('/oauth/consent', headers=headers,
                    json={**current_choice, 'approve': True, 'persistent': True})
                assert accepted.status_code == 200
                callback = parse_qs(urlsplit(accepted.json()['redirect_uri']).query)
                assert callback['state'] == [second_state]
                issued = await client.post('/oauth/token', data={
                    'grant_type': 'authorization_code', 'client_id': second_client['client_id'],
                    'redirect_uri': CALLBACK, 'code': callback['code'][0],
                    'code_verifier': verifier, 'resource': RESOURCE,
                })
                assert issued.status_code == 200 and issued.json()['scope'] == 'c0:read'
            finally:
                with app.state.auth.access.database.engine.begin() as connection:
                    connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),
                        {'id': UUID(second_client['client_id'])})
    asyncio.run(check())


@pytest.mark.parametrize('path,body', [
    ('/oauth/consent', {'approve': True, 'scopes': ['c0:read']}),
    ('/oauth/consent/background', {'scopes': ['c0:read']}),
])
def test_browser_choice_requires_a_well_formed_draft_id(renewing_app, path, body):
    async def check():
        app, saved, _, state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            profile = await login(client, state)
            await authorize(client, saved)
            headers = {'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']}
            for payload in (body, {**body, 'draft_id': 'private-draft-canary'}):
                rejected = await client.post(path, json=payload, headers=headers)
                assert rejected.status_code == 422 and rejected.json() == {'detail': 'invalid_consent'}
                assert 'private-draft-canary' not in rejected.text
            assert (await client.get('/oauth/consent/request')).status_code == 200
    asyncio.run(check())


def test_background_survives_logout_and_self_disconnect_stops_next_use(renewing_app):
    async def check():
        app,saved,clock,state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            pair,profile = await background_pair(client,saved,state)
            assert (await client.post('/auth/logout',json={},headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})).status_code == 200
            clock[0] += 86401
            renewed = await refresh(client,saved,pair)
            assert renewed.status_code == 200
            pair = renewed.json()
            bearer = {'Authorization':'Bearer '+pair['access_token']}
            assert (await client.get('/api/v1/profile',headers=bearer)).json()['id'] == profile['id']
            assert (await client.get('/api/v1/oauth/connections',headers=bearer)).status_code == 403
            state['offline'] = False
            current = await login(client,state)
            listing = await client.get('/api/v1/oauth/connections')
            assert listing.status_code == 200 and listing.headers['cache-control'] == 'no-store'
            connections = listing.json()['connections']
            assert len(connections) == 1 and connections[0]['persistent'] and connections[0]['expires_at'] is None
            assert connections[0]['last_used_at'] and connections[0]['idle_until']
            path = '/api/v1/oauth/connections/'+connections[0]['id']
            assert (await client.delete(path)).status_code == 403
            assert (await client.delete(path,headers={'Origin':ORIGIN,'X-C0-CSRF':current['csrf_token']})).status_code == 204
            assert (await refresh(client,saved,pair)).status_code == 400
            assert (await client.get('/api/v1/profile',headers=bearer)).status_code == 401
            assert (await client.get('/api/v1/oauth/connections')).json()['connections'] == []
    asyncio.run(check())


def test_background_activity_does_not_keep_browser_signed_in(renewing_app):
    async def check():
        app,saved,clock,state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            pair,_ = await background_pair(client,saved,state)
            clock[0] += 3601
            renewed = await refresh(client,saved,pair)
            assert renewed.status_code == 200
            assert (await client.get('/api/v1/me')).status_code == 401
            clock[0] += 86400
            assert (await refresh(client,saved,renewed.json())).status_code == 200
    asyncio.run(check())


def test_background_renewal_recovers_from_outage_but_replay_revokes(renewing_app):
    async def check():
        app,saved,clock,state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            pair,_ = await background_pair(client,saved,state)
            # The native provider is down while C0 and its database remain healthy.
            state['status'] = 503
            assert (await client.get('/api/v1/health')).status_code == 200
            offline = await refresh(client,saved,pair)
            assert offline.status_code == 503 and offline.json() == {
                'error':'temporarily_unavailable', 'c0_rotation':'not_started'}
            state['status'] = 200
            renewed = await refresh(client,saved,pair)
            assert renewed.status_code == 200
            replay = await client.post('/oauth/token',data={'grant_type':'refresh_token','client_id':saved['client_id'],
                'refresh_token':pair['refresh_token'],'resource':RESOURCE,'scope':'c0:admin'})
            assert replay.status_code == 400
            assert (await refresh(client,saved,renewed.json())).status_code == 400
    asyncio.run(check())


def test_offline_signin_requires_csrf_and_ignores_query_authority(renewing_app):
    async def check():
        app,saved,_,state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            profile = await login(client,state)
            await authorize(client,saved)
            view = (await client.get('/oauth/consent/request')).json()
            choice = {'draft_id': view['draft_id'], 'scopes': ['c0:read']}
            assert (await client.post('/oauth/consent/background', json=choice)).status_code == 403
            assert (await client.post('/oauth/consent', json={**choice, 'approve': True, 'persistent': True},
                headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})).status_code == 400
            response = await client.get('/auth/login?background=true&persistent=true')
            assert parse_qs(urlsplit(response.headers['location']).query)['scope'] == ['openid profile']
    asyncio.run(check())


@pytest.mark.parametrize('change', ['identity','scope'])
def test_background_callback_rejects_switched_identity_or_missing_offline_scope(renewing_app,change):
    async def check():
        app,saved,_,state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            profile = await login(client,state); await authorize(client,saved)
            view = (await client.get('/oauth/consent/request')).json()
            assert (await client.post('/oauth/consent/background',
                json={'draft_id': view['draft_id'], 'scopes': ['c0:read']},
                headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})).status_code == 200
            fields = parse_qs(urlsplit((await client.get('/auth/login')).headers['location']).query)
            state.update(nonce=fields['nonce'][0],offline=True)
            if change == 'identity': state['account_key'] = str(uuid4())
            else: state['offline_scope'] = 'openid profile'
            response = await client.get('/auth/callback',params={'code':'private-code','state':fields['state'][0]})
            assert response.status_code == 401
            assert all(value not in response.text for value in state['values'])
    asyncio.run(check())


@pytest.mark.parametrize('path,body', [
    ('/oauth/consent', {'approve':True,'persistent':'private-oauth-canary','scopes':['c0:read']}),
    ('/oauth/consent/background', {'scopes':['c0:read'],'extra':'private-oauth-canary'}),
])
def test_invalid_background_input_never_echoes_submitted_values(renewing_app,path,body):
    async def check():
        app,saved,_,state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            profile = await login(client,state); await authorize(client,saved)
            view = (await client.get('/oauth/consent/request')).json()
            response = await client.post(path, json={'draft_id': view['draft_id'], **body},
                headers={'Origin': ORIGIN, 'X-C0-CSRF': profile['csrf_token']})
            assert response.status_code == 422 and response.json() == {'detail':'invalid_consent'}
            assert 'private-oauth-canary' not in response.text
    asyncio.run(check())


def test_background_consent_keeps_the_chunked_body_limit(renewing_app):
    async def check():
        app,saved,_,state = renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            profile = await login(client,state); await authorize(client,saved)
            async def content():
                for _ in range(17):yield b'x'*1024
            response = await client.post('/oauth/consent/background',content=content(),
                headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token'],'Content-Type':'application/json'})
            assert response.status_code == 413
    asyncio.run(check())


@pytest.mark.parametrize('days',[7,45])
def test_new_connection_uses_current_policy_instead_of_previous_offline_signin(renewing_app,days):
    from czero_core.renewal import ConnectionPolicy
    async def check():
        app,saved,_,state=renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            old_pair,profile=await background_pair(client,saved,state)
            # A settings update restarts the app with a new policy; the saved
            # native authority and its existing grants retain their old limit.
            app.state.auth.sessions.authority.connection_policy=ConnectionPolicy(days*86400)
            await authorize(client,saved,scope='c0:read c0:write')
            view=(await client.get('/oauth/consent/request')).json()
            assert view['background_supported'] and not view['background_ready']
            assert view['connection_idle_seconds']==days*86400
            assert (await refresh(client,saved,old_pair)).status_code==200
    asyncio.run(check())


@pytest.mark.parametrize('days',[7,45])
def test_direct_consent_cannot_reuse_previous_policy_but_new_offline_signin_can(renewing_app,days):
    from czero_core.renewal import ConnectionPolicy
    from sqlalchemy import text
    from uuid import UUID
    async def check():
        app,saved,_,state=renewing_app
        async with OAuthBrowser(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            old_pair,profile=await background_pair(client,saved,state)
            app.state.auth.sessions.authority.connection_policy=ConnectionPolicy(days*86400)
            await authorize(client,saved,scope='c0:read c0:write')
            view = (await client.get('/oauth/consent/request')).json()
            result = await client.post('/oauth/consent',
                json={'draft_id': view['draft_id'], 'approve': True, 'scopes': ['c0:read', 'c0:write'], 'persistent': True},
                headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            assert result.status_code==400 and result.json()=={'detail':'invalid_consent'}
            state['offline']=False
            new_pair,current=await background_pair(client,saved,state)
            assert current['id']==profile['id'] and new_pair['refresh_token']!=old_pair['refresh_token']
            assert (await refresh(client,saved,old_pair)).status_code==200
            assert (await refresh(client,saved,new_pair)).status_code==200
            with app.state.auth.access.database.engine.connect() as c:
                durations=c.execute(text('''SELECT n.idle_seconds FROM c0_oauth_grants g
                    JOIN c0_native_authority n ON n.id=g.native_authority_id
                    WHERE g.account_id=:id AND g.persistent ORDER BY n.idle_seconds'''),
                    {'id':UUID(profile['id'])}).scalars().all()
            assert durations==sorted([30*86400,days*86400])
    asyncio.run(check())
