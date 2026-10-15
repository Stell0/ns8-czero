# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import os
import secrets
import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlencode
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.client.auth.oauth2 import OAuthClientProvider
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, AuthorizationCodeResult
from czero_app.mcp_transport import create_mcp_app

from czero_core.oauth_grants import pkce_challenge
from czero_core.identity import PermissionDenied, Role
from czero_app.oauth_server import install_oauth_server
from test_auth_http import application, ORIGIN, PrivateFixture

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
CALLBACK = 'https://client.example.test/callback'
RESOURCE = ORIGIN + '/mcp'


@pytest.fixture
def oauth_app(application):
    app, owner_token, *_ = application
    owner = app.state.auth.access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    saved = app.state.oauth_clients.register(owner, 'OAuth HTTP ' + uuid4().hex, [CALLBACK],
        scopes=['c0:read','c0:write','c0:admin'])
    grants, consent = app.state.delegated_grants, app.state.oauth_consent
    yield PrivateFixture((app,saved,grants,consent))
    with grants.access.database.engine.begin() as connection:
        connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id': UUID(saved['client_id'])})


async def authorize(client, saved, *, scope='c0:read', method='GET', optional=()):
    verifier = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(32)
    parameters = {'client_id':saved['client_id'],
        'redirect_uri':CALLBACK,'response_type':'code','code_challenge':pkce_challenge(verifier),
        'code_challenge_method':'S256','state':state,'scope':scope,'resource':RESOURCE}
    response = await authorization_request(client, method, list(parameters.items()) + list(optional))
    assert response.status_code == 302 and response.headers['location'] == ORIGIN + '/oauth/consent'
    flags = response.headers['set-cookie']
    assert 'HttpOnly' in flags and 'Secure' in flags and 'SameSite=lax' in flags
    return PrivateFixture((verifier,state))


async def authorization_request(client, method, parameters):
    encoded = urlencode(parameters)
    if method == 'GET':
        return await client.get('/oauth/authorize?' + encoded)
    return await client.post('/oauth/authorize', content=encoded,
        headers={'Content-Type':'application/x-www-form-urlencoded'})


@pytest.mark.parametrize('method', ['GET', 'POST'])
@pytest.mark.parametrize('optional', [
    [('ui_locales', 'en-US')],
    [('future_extension', 'ignored value')],
    [('ui_locales', 'en-US'), ('future_extension', '<untrusted>&value'), ('empty_extension', '')],
])
@pytest.mark.parametrize('scope', ['c0:read', 'c0:read c0:write c0:admin'])
def test_optional_authorization_fields_are_ignored_before_core(oauth_app, monkeypatch, method, optional, scope):
    from czero_app.oauth_provider import raw_request
    app, saved, grants, consent = oauth_app
    begin = consent.begin
    captured = []
    def checked_begin(*args, **kwargs):
        captured.append(dict(raw_request.get()))
        return begin(*args, **kwargs)
    monkeypatch.setattr(consent, 'begin', checked_begin)
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            verifier, state = await authorize(client, saved, scope=scope, method=method, optional=optional)
            assert len(captured) == 1
            assert set(captured[0]) == {'client_id', 'redirect_uri', 'response_type', 'code_challenge',
                'code_challenge_method', 'state', 'scope', 'resource'}
            assert captured[0]['state'] == state and captured[0]['scope'] == scope
            profile = await login(client)
            view = (await client.get('/oauth/consent/request')).json()
            assert set(view['scopes']) == set(scope.split())
            assert set(view['eligible_scopes']) == set(scope.split())
            response = await client.post('/oauth/consent', json={'approve':True, 'scopes':['c0:read']},
                headers={'Origin':ORIGIN, 'X-C0-CSRF':profile['csrf_token']})
            assert response.status_code == 200
            callback = urlsplit(response.json()['redirect_uri'])
            values = parse_qs(callback.query)
            assert values['state'] == [state] and set(values) == {'code', 'state'}
            assert callback._replace(query='').geturl() == CALLBACK
            response = await client.post('/oauth/token', data={'grant_type':'authorization_code',
                'client_id':saved['client_id'], 'redirect_uri':CALLBACK, 'code':values['code'][0],
                'code_verifier':verifier, 'resource':RESOURCE})
            assert response.status_code == 200
            pair = response.json()
            assert pair['scope'] == 'c0:read'
            assert grants.verify(pair['access_token'], resource=RESOURCE).scopes == frozenset({'c0:read'})
    asyncio.run(check())


@pytest.mark.parametrize('method', ['GET', 'POST'])
@pytest.mark.parametrize('duplicate', ['client_id', 'resource', 'scope', 'state', 'ui_locales', 'future_extension'])
def test_duplicate_authorization_fields_remain_rejected(oauth_app, method, duplicate):
    async def check():
        app, saved, _, _ = oauth_app
        parameters = {'client_id':saved['client_id'], 'redirect_uri':CALLBACK, 'response_type':'code',
            'code_challenge':pkce_challenge('x' * 43), 'code_challenge_method':'S256',
            'state':'preserved-state', 'scope':'c0:read', 'resource':RESOURCE,
            'ui_locales':'en-US', 'future_extension':''}
        values = list(parameters.items()) + [(duplicate, parameters[duplicate])]
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            response = await authorization_request(client, method, values)
            assert response.status_code == 400 and response.json() == {'error':'invalid_request'}
            assert 'location' not in response.headers and 'set-cookie' not in response.headers
    asyncio.run(check())


@pytest.mark.parametrize('method', ['GET', 'POST'])
@pytest.mark.parametrize('overrides', [
    {'code_challenge_method':'plain'}, {'code_challenge':'short'},
    {'resource':ORIGIN + '/other'}, {'client_id':str(UUID(int=0))},
    {'redirect_uri':CALLBACK + '/'}, {'scope':'c0:unknown'},
    {'scope':'c0:read unknown'}, {'state':'invalid\x01state'},
])
def test_optional_authorization_fields_do_not_relax_security(oauth_app, method, overrides):
    async def check():
        app, saved, _, _ = oauth_app
        parameters = {'client_id':saved['client_id'], 'redirect_uri':CALLBACK, 'response_type':'code',
            'code_challenge':pkce_challenge('x' * 43), 'code_challenge_method':'S256',
            'state':'preserved-state', 'scope':'c0:read', 'resource':RESOURCE, 'ui_locales':'en-US', **overrides}
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            response = await authorization_request(client, method, parameters)
            assert response.status_code in (400, 302)
            assert 'set-cookie' not in response.headers
            if response.status_code == 302:
                callback = urlsplit(response.headers['location'])
                assert callback._replace(query='').geturl() == CALLBACK
                assert 'error' in parse_qs(callback.query)
            else:
                assert 'error' in response.json() and 'location' not in response.headers
    asyncio.run(check())


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_optional_authorization_fields_cannot_exceed_request_limit(oauth_app, method):
    async def check():
        app, saved, _, _ = oauth_app
        parameters = {'client_id':saved['client_id'], 'redirect_uri':CALLBACK, 'response_type':'code',
            'code_challenge':pkce_challenge('x' * 43), 'code_challenge_method':'S256',
            'state':'preserved-state', 'scope':'c0:read', 'resource':RESOURCE, 'future_extension':'x' * 16385}
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            response = await authorization_request(client, method, parameters)
            assert response.status_code == (400 if method == 'GET' else 413)
            assert 'set-cookie' not in response.headers and 'location' not in response.headers
            if method == 'POST':
                encoded = urlencode(parameters).encode()
                async def chunks():
                    yield encoded[:8192]
                    yield encoded[8192:]
                response = await client.post('/oauth/authorize', content=chunks(),
                    headers={'Content-Type':'application/x-www-form-urlencoded'})
                assert response.status_code == 413
    asyncio.run(check())


def test_optional_fields_remain_rejected_on_token_and_revocation(oauth_app):
    async def check():
        app, saved, grants, _ = oauth_app
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            verifier, _ = await authorize(client, saved)
            profile = await login(client)
            response = await client.post('/oauth/consent', json={'approve':True, 'scopes':['c0:read']},
                headers={'Origin':ORIGIN, 'X-C0-CSRF':profile['csrf_token']})
            code = parse_qs(urlsplit(response.json()['redirect_uri']).query)['code'][0]
            token = {'grant_type':'authorization_code', 'client_id':saved['client_id'], 'redirect_uri':CALLBACK,
                'code':code, 'code_verifier':verifier, 'resource':RESOURCE}
            for name in ('ui_locales', 'future_extension'):
                response = await client.post('/oauth/token', data={**token, name:'ignored-only-at-authorize'})
                assert response.status_code == 400 and response.json() == {'error':'invalid_request'}
            response = await client.post('/oauth/token', data=token)
            assert response.status_code == 200  # Invalid optional fields did not consume the code.
            pair = response.json()
            revoke = {'client_id':saved['client_id'], 'token':pair['refresh_token'], 'resource':RESOURCE}
            for name in ('ui_locales', 'future_extension'):
                response = await client.post('/oauth/revoke', data={**revoke, name:'ignored-only-at-authorize'})
                assert response.status_code == 400 and response.json() == {'error':'invalid_request'}
                assert grants.verify(pair['access_token'], resource=RESOURCE).scopes == frozenset({'c0:read'})
            assert (await client.post('/oauth/revoke', data=revoke)).status_code == 200
    asyncio.run(check())


async def login(client, *, code='unit-only-code'):
    response = await client.get('/auth/login')
    state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
    response = await client.get('/auth/callback', params={'state':state,'code':code})
    assert response.status_code == 302 and response.headers['location'] == '/oauth/consent'
    return (await client.get('/api/v1/me')).json()


async def issued_pair(client, saved, *, scope='c0:read', login_code='unit-only-code'):
    verifier,_ = await authorize(client,saved,scope=scope)
    profile = await login(client,code=login_code)
    response = await client.post('/oauth/consent',json={'approve':True,'scopes':scope.split()},
        headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
    assert response.status_code == 200
    code=parse_qs(urlsplit(response.json()['redirect_uri']).query)['code'][0]
    response=await client.post('/oauth/token',data={'grant_type':'authorization_code','client_id':saved['client_id'],
        'code':code,'redirect_uri':CALLBACK,'code_verifier':verifier,'resource':RESOURCE})
    assert response.status_code==200
    return response.json()


@pytest.mark.parametrize('role', [Role.READER, Role.EDITOR, Role.ADMIN])
def test_scope_upgrade_requires_new_role_eligible_explicit_consent(oauth_app, application, role):
    async def check():
        app, saved, grants, _ = oauth_app
        _, owner_token, member_token, *_ = application
        access = app.state.auth.access
        owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        with pytest.raises(PermissionDenied):
            access.resolve(app.state.auth.oidc.verify_access_token(member_token))
        member_id = next(row['id'] for row in access.list_accounts(owner) if row['username'] == 'member')
        access.set_role(owner, member_id, role)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            pair = await issued_pair(client, saved, login_code='unit-only-forbidden-code')
            original = grants.verify(pair['access_token'], resource=RESOURCE)
            refresh = {'grant_type':'refresh_token', 'client_id':saved['client_id'],
                'refresh_token':pair['refresh_token'], 'resource':RESOURCE, 'scope':'c0:read c0:write'}
            assert (await client.post('/oauth/token', data=refresh)).status_code == 400
            assert grants.verify(pair['access_token'], resource=RESOURCE).scopes == {'c0:read'}
            verifier, state = await authorize(client, saved, scope='c0:read c0:write')
            view = (await client.get('/oauth/consent/request')).json()
            assert set(view['eligible_scopes']) == ({'c0:read'} if role is Role.READER else {'c0:read','c0:write'})
            profile = (await client.get('/api/v1/me')).json()
            response = await client.post('/oauth/consent', json={'approve':True,'scopes':['c0:read','c0:write']},
                headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            if role is Role.READER:
                assert response.status_code == 403
                return
            assert response.status_code == 200
            callback = parse_qs(urlsplit(response.json()['redirect_uri']).query)
            assert callback['state'] == [state]
            response = await client.post('/oauth/token', data={'grant_type':'authorization_code',
                'client_id':saved['client_id'], 'code':callback['code'][0], 'redirect_uri':CALLBACK,
                'code_verifier':verifier, 'resource':RESOURCE})
            assert response.status_code == 200
            upgraded = grants.verify(response.json()['access_token'], resource=RESOURCE)
            assert upgraded.actor == original.actor and upgraded.scopes == {'c0:read','c0:write'}
            assert grants.verify(pair['access_token'], resource=RESOURCE).scopes == {'c0:read'}
    asyncio.run(check())


def test_explicit_cookie_csrf_consent_s256_token_refresh_replay_and_metadata(oauth_app):
    async def check():
        app,saved,grants,_ = oauth_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            metadata = (await client.get('/.well-known/oauth-authorization-server/oauth')).json()
            assert metadata['issuer'] == ORIGIN + '/oauth' and metadata['token_endpoint'] == ORIGIN + '/oauth/token'
            assert metadata['token_endpoint_auth_methods_supported'] == ['none']
            assert 'registration_endpoint' not in metadata and metadata['code_challenge_methods_supported'] == ['S256']
            verifier,state = await authorize(client,saved)
            assert (await client.get('/oauth/consent')).headers['location'] == '/auth/login'
            profile = await login(client)
            assert (await client.get('/oauth/consent')).status_code == 200
            view = (await client.get('/oauth/consent/request')).json()
            assert view['client_name'] == saved['client_name'] and view['eligible_scopes'] == ['c0:read']
            assert not {'state','challenge','binding'} & view.keys()
            assert (await client.post('/oauth/consent',json={'approve':True})).status_code == 403
            headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']}
            response = await client.post('/oauth/consent',json={'approve':True,'scopes':['c0:read']},headers=headers)
            assert response.status_code == 200
            values = parse_qs(urlsplit(response.json()['redirect_uri']).query)
            assert values['state'] == [state]
            token_request = {'grant_type':'authorization_code','client_id':saved['client_id'],'code':values['code'][0],
                'redirect_uri':CALLBACK,'code_verifier':verifier,'resource':RESOURCE}
            for overrides in [{'resource':ORIGIN+'/other'},{'resource':None},{'redirect_uri':CALLBACK+'/'},
                              {'code_verifier':'x'*43}]:
                wrong={**token_request,**overrides};wrong={k:v for k,v in wrong.items() if v is not None}
                assert (await client.post('/oauth/token',data=wrong)).status_code == 400
            response = await client.post('/oauth/token',data=token_request)
            assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
            pair=response.json();assert pair['scope']=='c0:read' and pair['token_type']=='Bearer'
            assert grants.verify(pair['access_token'],resource=RESOURCE).actor.user_id==UUID(profile['id'])
            assert (await client.post('/oauth/token',data=token_request)).status_code==400
            refresh={'grant_type':'refresh_token','client_id':saved['client_id'],
                'refresh_token':pair['refresh_token'],'resource':RESOURCE}
            assert (await client.post('/oauth/token',data={**refresh,'resource':ORIGIN+'/other'})).status_code==400
            response=await client.post('/oauth/token',data=refresh)
            assert response.status_code==200
            second=response.json()
            assert (await client.post('/oauth/token',data=refresh)).status_code==400
            from czero_core.oauth_grants import GrantRejected
            with pytest.raises(GrantRejected):grants.verify(second['access_token'],resource=RESOURCE)
    asyncio.run(check())


def test_denial_duplicate_raw_parameters_oversize_and_no_public_registration(oauth_app):
    async def check():
        app,saved,_,_=oauth_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            _,state=await authorize(client,saved)
            profile=await login(client)
            response=await client.post('/oauth/consent',json={'approve':False,'scopes':[]},
                headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            assert response.status_code==200
            values=parse_qs(urlsplit(response.json()['redirect_uri']).query)
            assert values=={'error':['access_denied'],'state':[state]}
            assert (await client.post('/oauth/register',json={})).status_code==404
            assert (await client.post('/oauth/token',content=b' ' * 16385,
                headers={'Content-Type':'application/x-www-form-urlencoded'})).status_code==413
            async def body():
                yield b' ' * 8192
                yield b' ' * 8193
            assert (await client.post('/oauth/token',content=body(),
                headers={'Content-Type':'application/x-www-form-urlencoded'})).status_code==413
            encoded=urlencode({'resource':RESOURCE,'client_id':saved['client_id']})+'&resource='+RESOURCE
            assert (await client.post('/oauth/token',content=encoded,
                headers={'Content-Type':'application/x-www-form-urlencoded'})).status_code==400
    asyncio.run(check())


def test_real_sdk_and_rest_share_issued_scopes_and_public_revocation(oauth_app):
    async def check():
        app,saved,grants,_=oauth_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            pair=await issued_pair(client,saved)
            client.headers['Authorization']='Bearer '+pair['access_token']
            expected=(await client.get('/api/v1/object-types')).json()
            assert 'types' in expected
            assert (await client.get('/api/v1/access/accounts')).status_code==403
            assert (await client.post('/auth/logout',json={})).status_code==403
            assert (await client.post('/api/v1/wiki/pages',json={'slug':'denied','title':'Denied','body':'Denied',
                'idempotency_key':'denied'})).status_code==403
            async with app.router.lifespan_context(app):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair['access_token']}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http)) as sdk:
                        names={tool.name for tool in (await sdk.list_tools()).tools}
                        assert 'object_types_list' in names and 'objects_create' in names
                        result=await sdk.call_tool('object_types_list',{})
                        assert not result.is_error and result.structured_content==expected
                        assert (await sdk.call_tool('objects_create',{'data':{'type_name':'absent','data':{}}})).is_error
            client.headers.pop('Authorization')
            response=await client.post('/oauth/revoke',data={'client_id':saved['client_id'],
                'token':pair['refresh_token'],'resource':RESOURCE,'token_type_hint':'refresh_token'})
            assert response.status_code==200
            client.headers['Authorization']='Bearer '+pair['access_token']
            assert (await client.get('/api/v1/object-types')).status_code==401
            client.headers.pop('Authorization')
            assert (await client.post('/oauth/revoke',data={'client_id':saved['client_id'],
                'token':pair['refresh_token'],'resource':RESOURCE})).status_code==200
    asyncio.run(check())


def test_reader_can_narrow_client_consent_and_cannot_grant_write(oauth_app, application):
    async def check():
        app,saved,_,_=oauth_app
        _,owner_token,member_token,*_=application
        access=app.state.auth.access
        owner=access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        with pytest.raises(PermissionDenied):
            access.resolve(app.state.auth.oidc.verify_access_token(member_token))
        identifier=next(row['id'] for row in access.list_accounts(owner) if row['username']=='member')
        access.set_role(owner,identifier,Role.READER)
        identity=app.state.auth.oidc.verify_access_token(member_token)
        cookie=app.state.auth.sessions.create(identity)
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            await authorize(client,saved,scope='c0:read c0:write')
            client.cookies.set('c0_session',cookie,domain='c0.example.test',path='/')
            view=(await client.get('/oauth/consent/request')).json()
            assert view['profile']['role']=='reader' and view['eligible_scopes']==['c0:read']
            headers={'Origin':ORIGIN,'X-C0-CSRF':view['csrf_token']}
            assert (await client.post('/oauth/consent',json={'approve':True,'scopes':['c0:write']},headers=headers)).status_code==403
            assert (await client.get('/oauth/consent/request')).status_code==200
            assert (await client.post('/oauth/consent',json={'approve':True,'scopes':['c0:read']},headers=headers)).status_code==200
    asyncio.run(check())


def test_callback_comparison_preserves_exact_raw_spelling_before_sdk_normalization(oauth_app):
    async def check():
        app,saved,_,_=oauth_app
        # Use the already-approved callback and its normalized-equivalent spelling.
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            verifier=secrets.token_urlsafe(32)
            parameters={'client_id':saved['client_id'],'redirect_uri':'https://CLIENT.EXAMPLE.TEST:443/callback',
                'response_type':'code','code_challenge':pkce_challenge(verifier),'code_challenge_method':'S256',
                'scope':'c0:read','state':'unit-state','resource':RESOURCE}
            assert (await client.get('/oauth/authorize',params=parameters)).status_code==400
            parameters['redirect_uri']=CALLBACK
            response=await client.get('/oauth/authorize',params=parameters)
            assert response.status_code==302
            profile=await login(client)
            response=await client.post('/oauth/consent',json={'approve':True},
                headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            code=parse_qs(urlsplit(response.json()['redirect_uri']).query)['code'][0]
            token={'client_id':saved['client_id'],'grant_type':'authorization_code','code':code,
                'redirect_uri':'https://CLIENT.EXAMPLE.TEST:443/callback','code_verifier':verifier,'resource':RESOURCE}
            assert (await client.post('/oauth/token',data=token)).status_code==400
            token['redirect_uri']=CALLBACK
            assert (await client.post('/oauth/token',data=token)).status_code==200
    asyncio.run(check())


def test_official_oauth_client_discovers_authorizes_and_calls_mcp(oauth_app):
    async def check():
        app,saved,_,_=oauth_app
        class Storage:
            def __init__(self):
                self.tokens=None
                self.client=OAuthClientInformationFull(client_id=saved['client_id'],
                    redirect_uris=[CALLBACK],scope='c0:read',token_endpoint_auth_method='none',
                    grant_types=['authorization_code','refresh_token'],response_types=['code'])
            async def get_tokens(self):return self.tokens
            async def set_tokens(self,value):self.tokens=value
            async def get_client_info(self):return self.client
            async def set_client_info(self,value):self.client=value
        storage=Storage()
        result=[None]
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as browser:
            async def redirect(url):
                response=await browser.get(url + '&' + urlencode({'ui_locales':'en-US', 'future_extension':'ignored'}))
                assert response.status_code==302
                profile=await login(browser)
                response=await browser.post('/oauth/consent',json={'approve':True,'scopes':['c0:read']},
                    headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
                assert response.status_code==200
                values=parse_qs(urlsplit(response.json()['redirect_uri']).query)
                result[0]=AuthorizationCodeResult(code=values['code'][0],state=values['state'][0])
            async def callback():return result[0]
            auth=OAuthClientProvider(server_url=RESOURCE,
                client_metadata=OAuthClientMetadata(redirect_uris=[CALLBACK],scope='c0:read',
                    token_endpoint_auth_method='none',grant_types=['authorization_code','refresh_token'],response_types=['code']),
                storage=storage,redirect_handler=redirect,callback_handler=callback)
            async with app.router.lifespan_context(app):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,auth=auth) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http)) as client:
                        names={tool.name for tool in (await client.list_tools()).tools}
                        assert 'object_types_list' in names and 'objects_create' in names
                        assert not (await client.call_tool('object_types_list',{})).is_error
            assert storage.tokens is not None and storage.tokens.scope=='c0:read'
    asyncio.run(check())


@pytest.mark.parametrize("restored", [False, True])
def test_exact_disposable_oauth_issue_helper_uses_real_signed_http(oauth_app, application, tmp_path, monkeypatch, restored):
    app,_,_,_=oauth_app
    _,owner_token,*_=application
    path=Path(__file__).resolve().parents[1]/'oauth_fixture.py'
    import sys
    directory=str(path.parent)
    sys.path.insert(0,directory)
    try:
        spec=importlib.util.spec_from_file_location('native_oauth_fixture',path)
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    finally:
        sys.path.remove(directory)
    with TestClient(app,base_url=ORIGIN) as client:
        identity=app.state.auth.oidc.verify_access_token(owner_token)
        cookie=app.state.auth.sessions.create(identity)
        client.cookies.set('c0_session',cookie,domain='c0.example.test',path='/')
        profile=client.get('/api/v1/me').json()
        class Browser:
            origin=ORIGIN
            def request(self,path,data=None,method=None,headers=None):
                response=client.request(method or 'GET',path,content=data,headers=headers,follow_redirects=True)
                return response.status_code,response.content,str(response.url)
            def api(self,path,data=None,method=None,csrf=None):
                headers={'Origin':ORIGIN}
                if csrf:headers['X-C0-CSRF']=csrf
                response=client.request(method or 'GET',path,json=data,headers=headers)
                return response.status_code,response.content,str(response.url)
        saved=fixture.registered(Browser(),profile,client_name='Disposable active grant recovery')
        preceding=fixture.registered(Browser(),profile)
        try:
            # Simulate the failed preceding protocol probe's retained grant.
            fixture.issue(Browser(),profile,preceding)
            monkeypatch.setattr(fixture, 'STATE', tmp_path)
            def snapshot(_module, client_id):
                with app.state.auth.access.database.engine.connect() as connection:
                    return connection.execute(text('''SELECT json_build_object(
                        'grants',(SELECT json_agg(g ORDER BY id) FROM c0_oauth_grants g WHERE client_id=:id),
                        'tokens',(SELECT json_agg(t ORDER BY hash) FROM c0_oauth_tokens t JOIN c0_oauth_grants g
                                  ON g.id=t.grant_id WHERE g.client_id=:id),
                        'codes',(SELECT json_agg(c ORDER BY hash) FROM c0_oauth_codes c JOIN c0_oauth_grants g
                                 ON g.id=c.grant_id WHERE g.client_id=:id))'''), {'id':UUID(client_id)}).scalar_one()
            def sdk(_module, _origin, pair):
                assert app.state.delegated_grants.verify(pair['access_token'],resource=RESOURCE).scopes==frozenset(('c0:read',))
                assert client.get('/api/v1/object-types',headers={'Authorization':'Bearer '+pair['access_token']}).status_code==200
            fixture.seed_persistence('czero1',Browser(),profile,snapshot_fn=snapshot)
            assert (tmp_path/'expected-oauth-grant.json').stat().st_mode & 0o777 == 0o600
            if restored:
                app.state.delegated_grants.native_client='restored-native-client'
            fixture.verify_persistence('czero2' if restored else 'czero1',Browser(),profile,
                snapshot_fn=snapshot,sdk_fn=sdk)
            if not restored:
                browser=Browser()
                browser.login=lambda *_:profile
                browser.logout=lambda *_:None
                monkeypatch.setattr(fixture,'Browser',lambda *_:browser)
                def sdk_scoped(_module, _origin, pair, *, scope='c0:read'):
                    assert app.state.delegated_grants.verify(pair['access_token'],resource=RESOURCE).scopes==frozenset(scope.split())
                    assert client.get('/api/v1/object-types',headers={
                        'Authorization':'Bearer '+pair['access_token']}).status_code==200
                monkeypatch.setattr(fixture,'sdk',sdk_scoped)
                (tmp_path/'personas.json').write_text(json.dumps({'host':'c0.example.test','password':'unused'}))
                fixture.run('czero1')
                fixture.prepare_browser('czero1','admin')
                request_path=tmp_path/'browser-oauth.json'
                value=json.loads(request_path.read_text())
                assert request_path.stat().st_mode & 0o777 == 0o600
                assert browser.request(value['authorization_url'])[0]==200
                status,body,_=browser.api('/oauth/consent',{'approve':True,'scopes':['c0:read','c0:write','c0:admin']},'POST',profile['csrf_token'])
                assert status==200
                value['returned_callback']=json.loads(body)['redirect_uri']
                request_path.write_text(json.dumps(value))
                def sdk_admin(_module,_origin,pair,**_):
                    assert app.state.delegated_grants.verify(pair['access_token'],resource=RESOURCE).scopes==frozenset(('c0:read','c0:write','c0:admin'))
                monkeypatch.setattr(fixture,'sdk',sdk_admin)
                try:fixture.complete_browser('czero1')
                finally:
                    with app.state.auth.access.database.engine.begin() as connection:
                        connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),{'id':UUID(value['client']['client_id'])})
        finally:
            with app.state.auth.access.database.engine.begin() as connection:
                for row in (saved,preceding):
                    connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),{'id':UUID(row['client_id'])})
