# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed provider responses through real browser, OAuth and MCP adapters."""
import asyncio
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from joserfc import jwt
from joserfc.jwk import RSAKey
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text

from czero_core.database import Database
from czero_core.identity import TokenVerifier, VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.oidc import OidcClient
from test_auth_http import ORIGIN, PrivateFixture
from test_oauth_server_http import authorize, CALLBACK, RESOURCE

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def renewing_app(monkeypatch, request):
    from czero_app.auth import AppAuth
    import czero_app.auth as auth_module
    import czero_core.oidc as oidc_module
    issuer = 'https://idp.example.test/' + uuid4().hex
    owner = uuid4()
    clock = [int(time.time())]
    state = {'nonce':None, 'active':True, 'status':200, 'refreshes':0, 'checks':0, 'values':[]}
    credentials = {}
    signer = RSAKey.generate_key(2048, {'kid':'trusted','use':'sig'})
    policy = getattr(request, 'param', (28800, 3600))
    for name, value in {'CZERO_MODULE_ID':'czero901', 'CZERO_OIDC_ISSUER':issuer,
            'CZERO_OIDC_CLIENT_ID':'czero901', 'CZERO_OIDC_CLIENT_SECRET':'s'*32,
            'CZERO_AUTH_PUBLIC_ORIGIN':ORIGIN, 'CZERO_OWNER_LDAP_UUID':str(owner),
            'CZERO_SESSION_ABSOLUTE_SECONDS':str(policy[0]), 'CZERO_SESSION_IDLE_SECONDS':str(policy[1])}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(oidc_module, 'time', SimpleNamespace(time=lambda:clock[0], monotonic=time.monotonic))
    def signed(kind, context, **claims):
        value = jwt.encode({'alg':'RS256','kid':'trusted'}, {'iss':issuer,'sub':'owner','aud':'czero901',
            'azp':'czero901','ldap_uuid':state.get('account_key',str(owner)),'preferred_username':'owner','typ':kind,
            'iat':clock[0]-1,'exp':clock[0]+state.get('access_seconds',300), **claims}, signer)
        state['values'].append(value)
        return value
    def handle(request):
        path = request.url.path
        if path.endswith('openid-configuration'):
            return httpx2.Response(200, json={'issuer':issuer, 'authorization_endpoint':issuer+'/authorize',
                'token_endpoint':issuer+'/token', 'jwks_uri':issuer+'/keys',
                'end_session_endpoint':issuer+'/logout', 'introspection_endpoint':issuer+'/check'})
        assert request.headers['authorization'].startswith('Basic ')
        body = parse_qs(request.content.decode())
        if state['status'] != 200:
            return httpx2.Response(state['status'], json={'error':'temporarily_unavailable','error_description':'PRIVATE provider detail'})
        if path.endswith('/check'):
            state['checks'] += 1
            return httpx2.Response(200, json={'active':state['active'] and clock[0]<state.get('provider_session_until',float('inf'))})
        if body['grant_type'] == ['authorization_code']:
            context = {'nonce':state['nonce'], 'auth_time':clock[0], 'offline':state.get('offline',False)}
            assert body['code'] == ['private-code']
        else:
            assert body['grant_type'] == ['refresh_token']
            context = credentials.pop(body['refresh_token'][0], None)
            if context is None or not state['active'] or clock[0]>=context.get('refresh_deadline',float('inf')):
                return httpx2.Response(400, json={'error':'invalid_grant'})
            state['refreshes'] += 1
        refresh = 'private-native-refresh-' + uuid4().hex
        credentials[refresh] = context
        state['values'].append(refresh)
        result={'token_type':'Bearer','expires_in':state.get('access_seconds',300),
            'access_token':signed('Bearer',context), 'refresh_token':refresh,
            'id_token':signed('ID',context,nonce=context['nonce'],auth_time=context['auth_time'])}
        if context['offline']:
            result['scope'] = state.get('offline_scope','openid profile offline_access')
        if state.get('refresh_seconds') is not None:
            result['refresh_expires_in']=state['refresh_seconds']
            context['refresh_deadline']=clock[0]+state['refresh_seconds']
            state['provider_session_until']=context['refresh_deadline']
        return httpx2.Response(200,json=result)
    def provider(config):
        client = OidcClient(config, transport=httpx2.MockTransport(handle))
        client._verifier = TokenVerifier(issuer, 'czero901', {'keys':[signer.as_dict(private=False)]}, now=lambda:clock[0])
        client._keys_until = time.monotonic()+86400
        return client
    monkeypatch.setattr(auth_module, 'OidcClient', provider)
    url = os.getenv('CZERO_APP_TEST_DATABASE_URL', os.environ['CZERO_TEST_DATABASE_URL'])
    monkeypatch.setenv('CZERO_DATABASE_URL', url)
    from czero_app.main import create_app
    database = Database(url)
    migrate_database(database)
    auth = AppAuth.from_env(database, '')
    assert auth is not None and auth.sessions.authority is not None
    auth.sessions._now = auth.sessions.authority._now = lambda:clock[0]
    app = create_app('czero901', Path(__file__).resolve().parents[2]/'app/static', '', database, auth=auth)
    app.state.delegated_grants._now = app.state.oauth_consent._now = lambda:clock[0]
    actor = auth.access.resolve(VerifiedIdentity(issuer,'owner',str(owner),'owner','Owner',clock[0]+300))
    saved = app.state.oauth_clients.register(actor, 'Renewable HTTP '+uuid4().hex, [CALLBACK], scopes=['c0:read','c0:write'])
    yield PrivateFixture((app, saved, clock, state))
    auth.oidc.close()
    with database.engine.begin() as c:
        c.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id':UUID(saved['client_id'])})
        c.execute(text('DELETE FROM c0_login_states WHERE issuer=:issuer'), {'issuer':issuer})
        c.execute(text('DELETE FROM c0_accounts WHERE issuer=:issuer'), {'issuer':issuer})
    database.close()


async def login(client, state):
    started = await client.get('/auth/login')
    assert started.status_code == 302
    fields = parse_qs(urlsplit(started.headers['location']).query)
    assert fields['scope'] == ['openid profile']
    state['nonce'] = fields['nonce'][0]
    completed = await client.get('/auth/callback', params={'code':'private-code','state':fields['state'][0]})
    assert completed.status_code == 302
    assert all(value not in completed.text for value in state['values'])
    me = await client.get('/api/v1/me')
    assert me.status_code == 200
    return me.json()


async def pair(client, saved, state):
    profile = await login(client, state)
    verifier, _ = await authorize(client, saved, scope='c0:read c0:write')
    accepted = await client.post('/oauth/consent', json={'approve':True,'scopes':['c0:read']},
        headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
    assert accepted.status_code == 200
    code = parse_qs(urlsplit(accepted.json()['redirect_uri']).query)['code'][0]
    issued = await client.post('/oauth/token', data={'grant_type':'authorization_code','client_id':saved['client_id'],
        'code':code,'redirect_uri':CALLBACK,'code_verifier':verifier,'resource':RESOURCE})
    assert issued.status_code == 200
    assert issued.json()['scope'] == 'c0:read'
    return issued.json(), profile


async def refresh(client, saved, current):
    return await client.post('/oauth/token', data={'grant_type':'refresh_token','client_id':saved['client_id'],
        'refresh_token':current['refresh_token'],'resource':RESOURCE})


def test_signed_browser_and_public_refresh_continue_beyond_original_token_expiry(renewing_app):
    async def check():
        app, saved, clock, state = renewing_app
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            current, profile = await pair(client, saved, state)
            assert app.state.delegated_grants.authority is app.state.auth.sessions.authority
            with app.state.auth.access.database.engine.connect() as c:
                row = c.execute(text('SELECT * FROM c0_native_authority WHERE account_id=:id'),{'id':UUID(profile['id'])}).mappings().one()
            absolute = row['expires_at']
            expected_profile=(await client.get('/api/v1/profile')).json()
            assert expected_profile['id']==profile['id']
            for _ in range(2):
                clock[0] += 301
                assert (await client.get('/api/v1/me')).json()['id'] == profile['id']
                assert (await client.get('/api/v1/profile')).json()==expected_profile
                assert (await client.get('/api/v1/profile',headers={'Authorization':'Bearer '+current['access_token']})).status_code==401
                assert (await client.get('/api/v1/me',headers={'Authorization':'Bearer '+current['access_token']})).status_code == 401
                renewed = await refresh(client,saved,current)
                assert renewed.status_code == 200
                updated = renewed.json()
                assert updated['refresh_token'] != current['refresh_token'] and updated['scope'] == 'c0:read'
                assert 0 < updated['expires_in'] <= 300
                current = updated
                assert (await client.get('/api/v1/profile',headers={'Authorization':'Bearer '+current['access_token']})).json()==expected_profile
            assert state['refreshes'] == 2 and state['checks'] > 0
            async with app.router.lifespan_context(app):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+current['access_token']}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http)) as sdk:
                        result=await sdk.call_tool('object_types_list',{})
                        assert not result.is_error and 'types' in result.structured_content
                        result=await sdk.call_tool('get_profile',{})
                        assert not result.is_error and result.structured_content==expected_profile
            with app.state.auth.access.database.engine.connect() as c:
                after=c.execute(text('SELECT * FROM c0_native_authority WHERE id=:id'),{'id':row['id']}).mappings().one()
            assert after['expires_at'] == absolute and after['credential'] != row['credential']
            assert all(value not in json.dumps(profile) for value in state['values'])
    asyncio.run(check())


def test_provider_outage_is_static_for_browser_mcp_refresh_and_local_logout_still_revokes(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            current,profile=await pair(client,saved,state)
            state['status']=503
            result=await client.get('/api/v1/me')
            assert result.status_code==503 and result.json()=={'detail':'authentication_unavailable'}
            token=await refresh(client,saved,current)
            assert token.status_code==503 and token.json()=={'error':'service_unavailable'}
            async with app.router.lifespan_context(app):
                result=await client.post('/mcp',headers={'Authorization':'Bearer '+current['access_token'],
                    'Accept':'application/json, text/event-stream'},json={'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}})
                assert result.status_code==503 and result.json()=={'error':'service_unavailable'}
            denied=await client.post('/auth/logout',headers={'Origin':'https://untrusted.example.test','X-C0-CSRF':profile['csrf_token']})
            assert denied.status_code==403
            # Cached provider metadata may still supply its logout URL. Local
            # revocation must neither authenticate nor require that URL to work.
            logout=await client.post('/auth/logout',headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            assert logout.status_code==200
            state['status']=200
            assert (await client.get('/api/v1/me')).status_code==401
            assert (await refresh(client,saved,current)).status_code==400
    asyncio.run(check())


def test_transient_outage_recovers_without_rotating_public_refresh_or_extending_absolute_bound(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            current,_=await pair(client,saved,state)
            state['status']=503
            assert (await refresh(client,saved,current)).status_code==503
            state['status']=200
            clock[0]+=10
            renewed=await refresh(client,saved,current)
            assert renewed.status_code==200 and renewed.json()['scope']=='c0:read'
    asyncio.run(check())


@pytest.mark.parametrize('renewing_app',[(60,60)],indirect=True)
def test_short_configured_bound_expires_browser_and_delegation_without_revival(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            current,_=await pair(client,saved,state)
            assert 0<current['expires_in']<=60
            clock[0]+=60
            assert (await client.get('/api/v1/me')).status_code==401
            assert (await refresh(client,saved,current)).status_code==400
            await login(client,state)
            assert (await refresh(client,saved,current)).status_code==400
    asyncio.run(check())


def test_provider_native_revocation_is_durable_until_fresh_signin(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            current,_=await pair(client,saved,state)
            state['active']=False
            result=await client.get('/api/v1/me')
            assert result.status_code==401 and result.json()=={'detail':'invalid_session'}
            state['active']=True
            assert (await client.get('/api/v1/me')).status_code==401
            assert (await client.get('/api/v1/me',headers={'Authorization':'Bearer '+current['access_token']})).status_code==401
            assert (await refresh(client,saved,current)).status_code==400
            await login(client,state)
            assert (await refresh(client,saved,current)).status_code==400
    asyncio.run(check())


def test_public_refresh_replay_revokes_family_even_during_provider_outage(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            current,_=await pair(client,saved,state)
            renewed=await refresh(client,saved,current)
            assert renewed.status_code==200
            state['status']=503
            replay=await refresh(client,saved,current)
            assert replay.status_code==400
            assert (await client.get('/api/v1/me',headers={'Authorization':'Bearer '+renewed.json()['access_token']})).status_code==401
    asyncio.run(check())


def test_native_revocation_on_consent_page_requires_fresh_browser_login(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            await login(client,state)
            await authorize(client,saved)
            state['active']=False
            response=await client.get('/oauth/consent')
            assert response.status_code==302 and response.headers['location']=='/auth/login'
            assert 'c0_session' not in client.cookies
            assert response.headers['cache-control']=='no-store'
    asyncio.run(check())


def test_exact_native_renewal_probe_through_signed_http_with_controlled_clock(renewing_app, monkeypatch, tmp_path):
    import hashlib
    import sys
    from fastapi.testclient import TestClient
    from czero_core.renewal import SessionPolicy
    app, saved, clock, state = renewing_app
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    import renewal_fixture
    from oauth_fixture import registered
    monkeypatch.setattr(renewal_fixture, 'STATE', tmp_path)
    (tmp_path/'personas.json').write_text(json.dumps({'host':'c0.example.test','password':'fixture-only'}))
    (tmp_path/'personas.json').chmod(0o600)
    clients=[]
    created=[]
    start=clock[0]
    class Browser:
        def __init__(self, origin):
            self.origin=origin
            self.http=TestClient(app,base_url=origin,follow_redirects=False)
            self.cookies=self.http.cookies.jar
            clients.append(self.http)
        def request(self,path,data=None,method=None,headers=None):
            response=self.http.request(method or 'GET',path,content=data,headers=headers)
            for _ in range(8):
                if response.status_code!=302:
                    return response.status_code,response.content,str(response.url)
                location=response.headers['location']
                if urlsplit(location).hostname=='idp.example.test':
                    fields=parse_qs(urlsplit(location).query)
                    state['nonce']=fields['nonce'][0]
                    response=self.http.get('/auth/callback',params={'state':fields['state'][0],'code':'private-code'})
                else:
                    response=self.http.get(location)
            raise AssertionError('Disposable renewal redirect loop')
        def api(self,path,data=None,method=None,csrf=None):
            headers={'Origin':self.origin,**({'X-C0-CSRF':csrf} if csrf else {})}
            if data is not None:headers['Content-Type']='application/json'
            return self.request(path,None if data is None else json.dumps(data).encode(),method,headers)
        def login(self,username,password):
            status,_,_=self.request('/auth/login')
            assert status==200
            status,body,_=self.api('/api/v1/me')
            assert status==200
            return json.loads(body)
    def snapshot(_,browser):
        cookie=next(item.value for item in browser.cookies if item.name=='c0_session')
        auth=app.state.auth
        with auth.access.database.engine.connect() as c:
            row=c.execute(text('''SELECT n.* FROM c0_native_authority n JOIN c0_sessions s
                ON s.native_authority_id=n.id WHERE s.token_hash=:hash'''),
                {'hash':hashlib.sha256(cookie.encode()).hexdigest()}).mappings().one()
            value=json.loads(auth.sessions.authority._open(row))
            identity=auth.oidc._token_verifier().verify_access_token(value['access'])
            return {'id':str(row['id']),'absolute':row['expires_at'].timestamp(),'idle':row['idle_until'].timestamp(),
                'native_expiry':identity.expires_at,
                'access_fingerprint':hashlib.sha256(value['access'].encode()).hexdigest(),
                'refresh_fingerprint':hashlib.sha256(value['refresh'].encode()).hexdigest()}
    def configure(policy):
        app.state.auth.sessions.authority.policy=SessionPolicy(**policy)
        app.state.auth.sessions.max_session_seconds=policy['absolute_seconds']
    def sdk(_,origin,current):
        # The exact native probe passes tokens to its actual TLS SDK client.
        # Here its private handoff is checked against the composed Core/HTTP;
        # the separate real SDK test above covers both adapters.
        assert origin==ORIGIN and current['scope']=='c0:read'
        assert app.state.delegated_grants.verify(current['access_token'],resource=RESOURCE).actor.is_owner
    def register(browser,profile,**kwargs):
        client=registered(browser,profile,**kwargs)
        created.append(client['client_id'])
        return client
    def sleep(seconds):clock[0]+=seconds
    fake=SimpleNamespace(monotonic=lambda:clock[0]-start,time=lambda:clock[0],sleep=sleep)
    try:
        metrics=renewal_fixture.run('czero901',browser_factory=Browser,snapshot_fn=snapshot,sdk_fn=sdk,
            configure_fn=configure,policy={'absolute_seconds':28800,'idle_seconds':3600},clock=fake,register_fn=register)
        assert metrics['elapsed_seconds']>=330 and metrics['idle_elapsed_seconds']>=60
        assert metrics['absolute_elapsed_seconds']>=120 and metrics['native_access_renewals']==1
        assert metrics['client_disabled']==metrics['logout_and_reconnect']==1
        assert all(type(value) is int and value >= 0 for value in metrics.values())
        assert all(value not in json.dumps(metrics) for value in state['values'])
    finally:
        for client in clients:client.close()
        with app.state.auth.access.database.engine.begin() as c:
            for client_id in created:c.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),{'id':UUID(client_id)})


@pytest.mark.parametrize('kind',['access_token','refresh_token'])
def test_public_sdk_revocation_does_not_depend_on_provider_availability(renewing_app,kind):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            current,_=await pair(client,saved,state)
            state['status']=503
            response=await client.post('/oauth/revoke',data={'client_id':saved['client_id'],
                'token':current[kind],'token_type_hint':kind,'resource':RESOURCE})
            assert response.status_code==200
            state['status']=200
            assert (await client.get('/api/v1/me',headers={'Authorization':'Bearer '+current['access_token']})).status_code==401
            assert (await refresh(client,saved,current)).status_code==400
    asyncio.run(check())


@pytest.mark.parametrize('kind',['access_token','refresh_token'])
def test_outage_revocation_cannot_delete_a_different_clients_grant(renewing_app,kind):
    async def check():
        app,saved,clock,state=renewing_app
        wrong_id=None
        try:
            async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
                current,profile=await pair(client,saved,state)
                registered=await client.post('/api/v1/oauth/clients',json={'client_name':'Other revocation caller '+uuid4().hex,
                    'redirect_uris':['https://other-client.example.test/callback'],'allowed_scopes':['c0:read']},
                    headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
                assert registered.status_code==201
                wrong_id=registered.json()['client_id']
                state['status']=503
                response=await client.post('/oauth/revoke',data={'client_id':wrong_id,
                    'token':current[kind],'token_type_hint':kind,'resource':RESOURCE})
                assert response.status_code==200
                state['status']=200
                assert (await client.get('/api/v1/me',headers={'Authorization':'Bearer '+current['access_token']})).status_code==200
                # The following ordinary token request must not inherit the
                # revocation-only adapter purpose from the preceding request.
                assert (await refresh(client,saved,current)).status_code==200
        finally:
            if wrong_id is not None:
                with app.state.auth.access.database.engine.begin() as c:
                    c.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),{'id':UUID(wrong_id)})
    asyncio.run(check())


def test_long_native_access_with_shorter_refresh_window_stays_active(renewing_app):
    app,saved,clock,state=renewing_app
    state.update(access_seconds=3600,refresh_seconds=1800)
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as browser:
            current,profile=await pair(browser,saved,state)
            with app.state.auth.access.database.engine.connect() as c:
                original=c.execute(text("SELECT id,expires_at,native_authority_id,scopes FROM c0_oauth_grants WHERE client_id=:client"),{'client':UUID(saved['client_id'])}).mappings().one()
            for _ in range(24):
                clock[0]+=300
                response=await browser.get('/api/v1/me')
                assert response.status_code==200,'Active native session missed its shorter provider refresh window'
                assert response.json()['id']==profile['id']
                response=await refresh(browser,saved,current)
                assert response.status_code==200 and response.json()['scope']==current['scope']
                assert response.json()['refresh_token']!=current['refresh_token']
                current=response.json()
            assert state['refreshes']>=12
            with app.state.auth.access.database.engine.connect() as c:
                after=c.execute(text("SELECT id,expires_at,native_authority_id,scopes FROM c0_oauth_grants WHERE client_id=:client"),{'client':UUID(saved['client_id'])}).mappings().one()
                assert after==original
    asyncio.run(run())
