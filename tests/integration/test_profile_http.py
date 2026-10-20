# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Profile identity is resolved from actual verified request authority."""
import asyncio
from dataclasses import replace
import json
import os
from uuid import UUID, uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from sqlalchemy import text

from czero_core.identity import PermissionDenied, Role
from test_auth_http import application, ORIGIN
from test_mcp_http import transport, RESOURCE

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_profile_rest_uses_account_identity_and_omits_private_context(application, monkeypatch):
    async def check():
        app, owner_token, member_token, _, _, _ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
            assert (await http.get('/api/v1/profile')).status_code == 401
            assert (await http.get('/api/v1/profile', headers={'Authorization':'Bearer '+member_token})).status_code == 403
            http.headers['Authorization'] = 'Bearer '+owner_token
            before = (await http.get('/api/v1/me')).json()
            profile = (await http.get('/api/v1/profile')).json()
            assert profile == {'id':before['id'], 'name':'owner', 'nickname':'owner'}
            assert str(UUID(profile['id'])) == profile['id']
            identity = app.state.auth.oidc.verify_access_token(owner_token)
            original = app.state.auth.oidc.verify_access_token
            monkeypatch.setattr(app.state.auth.oidc, 'verify_access_token', lambda token: (
                replace(identity, username='renamed', display_name='Updated label') if token==owner_token else original(token)))
            assert (await http.get('/api/v1/profile')).json() == {
                'id':profile['id'], 'name':'Updated label', 'nickname':'renamed'}
            current = app.state.auth.access.resolve(replace(identity, username='owner'))
            member_id = next(row['id'] for row in app.state.auth.access.list_accounts(current) if row['username']=='member')
            app.state.auth.access.set_role(current, member_id, Role.READER)
            http.headers['Authorization']='Bearer '+member_token
            member = (await http.get('/api/v1/profile')).json()
            assert member['id'] != profile['id'] and member['nickname']=='member'
            app.state.auth.access.set_role(current, member_id, None)
            assert (await http.get('/api/v1/profile')).status_code == 403
    asyncio.run(check())


@pytest.mark.parametrize('invalid', [None, '', '   ', 'not-an-id', 7])
def test_invalid_persisted_identity_fails_without_placeholder(application, monkeypatch, invalid):
    async def check():
        app, owner_token, *_ = application
        monkeypatch.setattr(app.state.auth.access, 'profile', lambda actor: {
            'id':invalid, 'username':'synthetic-private-name', 'role':'admin'})
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner_token}) as http:
            response=await http.get('/api/v1/profile')
            assert response.status_code==503 and response.json()=={'detail':'invalid_operation_result'}
            assert 'synthetic-private-name' not in response.text
    asyncio.run(check())


def test_profile_browser_dto_does_not_expose_csrf(application):
    async def check():
        app, owner_token, *_=application
        auth=app.state.auth
        cookie=auth.sessions.create(auth.oidc.verify_access_token(owner_token))
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                cookies={'c0_session':cookie}) as http:
            me=(await http.get('/api/v1/me')).json()
            assert 'csrf_token' in me
            assert (await http.get('/api/v1/profile')).json()=={'id':me['id'],'name':'owner','nickname':'owner'}
            assert (await http.post('/auth/logout',json={},headers={'Origin':ORIGIN,'X-C0-CSRF':me['csrf_token']})).status_code==200
            assert (await http.get('/api/v1/profile')).status_code==401
    asyncio.run(check())


def test_profile_sdk_wire_schema_metadata_and_current_credential_parity(transport):
    async def check():
        app,child,grants,client_record,pair,issue,owner_token,_=transport
        identity=app.state.auth.oidc.verify_access_token(owner_token)
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner_token}) as rest:
            expected=(await rest.get('/api/v1/profile')).json()
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN) as http:
                for scopes in ({'c0:read'},{'c0:read','c0:write'}, {'c0:write'},{'c0:admin'}):
                    current=issue(identity,scopes)
                    http.headers['Authorization']='Bearer '+current.access_token
                    for mode in ('auto','legacy'):
                        async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                            tools=(await client.list_tools()).tools
                            designated=[tool for tool in tools if (tool.meta or {}).get('openai/profile') is True]
                            assert len(designated)==1 and designated[0].name=='get_profile'
                            tool=designated[0]
                            schema=tool.output_schema
                            assert schema['type']=='object' and schema['required']==['id'] and schema['additionalProperties'] is False
                            assert set(schema['properties'])=={'id','name','email','nickname'}
                            assert all(field['type']=='string' for field in schema['properties'].values())
                            assert tool.input_schema['properties']=={} and tool.input_schema['additionalProperties'] is False
                            assert tool.meta['securitySchemes']==[{'type':'oauth2','scopes':['c0:read']}]
                            assert tool.annotations.read_only_hint and tool.annotations.idempotent_hint
                            assert tool.annotations.destructive_hint is False and tool.annotations.open_world_hint is False
                            result=await client.call_tool('get_profile',{})
                            if 'c0:read' in scopes:
                                assert not result.is_error and result.structured_content==expected
                                assert json.loads(result.content[0].text)==expected
                                Draft202012Validator(schema).validate(expected)
                                for bad in ({'id':''},{'id':'  '},{'id':expected['id'],'role':'admin'},{'id':expected['id'],'name':None}):
                                    assert not Draft202012Validator(schema).is_valid(bad)
                                assert (await client.call_tool('get_profile',{'id':expected['id']})).is_error
                            else:
                                assert result.is_error and result.content[0].text=='insufficient_scope'
                                assert 'scope="c0:read"' in result.meta['mcp/www_authenticate'][0]
                    # Raw current/legacy HTTP must retain profile and OAuth metadata too.
                    for version in ('2025-11-25','2024-11-05'):
                        response=await http.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}},
                            headers={'Accept':'application/json, text/event-stream','MCP-Protocol-Version':version})
                        tool=next(t for t in response.json()['result']['tools'] if t['name']=='get_profile')
                        assert tool['_meta']['openai/profile'] is True
                        assert tool['securitySchemes']==tool['_meta']['securitySchemes']==[{'type':'oauth2','scopes':['c0:read']}]
                refreshed=grants.refresh(pair.refresh_token,client_record['client_id'],resource=RESOURCE,scopes={'c0:read'})
                for current in (refreshed,issue(identity,{'c0:read'})):
                    http.headers['Authorization']='Bearer '+current.access_token
                    response=await http.get('/api/v1/profile')
                    assert response.status_code==200 and response.json()==expected
                grants.revoke(current.access_token,client_record['client_id'],resource=RESOURCE)
                assert (await http.get('/api/v1/profile')).status_code==401
    asyncio.run(check())


def test_same_username_on_different_account_never_reuses_profile(application):
    app,owner_token,*_=application
    access=app.state.auth.access;identity=app.state.auth.oidc.verify_access_token(owner_token)
    original=access.resolve(identity)
    other_identity=replace(identity,account_key=str(uuid4()),subject=str(uuid4()))
    with pytest.raises(PermissionDenied):access.resolve(other_identity)
    other=next(row for row in access.list_accounts(original) if row['account_key']==UUID(other_identity.account_key))
    assert other['username']==identity.username and other['id']!=original.user_id


def test_profile_omits_unavailable_metadata_and_never_projects_private_fields(application, monkeypatch):
    async def check():
        app,owner_token,*_=application
        original=app.state.auth.access.profile
        def stored(actor):
            row=original(actor)
            return {**row,'username':'','display_name':' \t','email':'unverified@example.test','csrf_token':'private-fixture'}
        monkeypatch.setattr(app.state.auth.access,'profile',stored)
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner_token}) as http:
            value=(await http.get('/api/v1/profile')).json()
            assert set(value)=={'id'} and str(UUID(value['id']))==value['id']
    asyncio.run(check())


def test_independent_database_assigns_distinct_identity_for_same_native_account(application):
    from sqlalchemy.engine import make_url
    from czero_core.access import AccessService
    from czero_core.database import Database
    from czero_core.migrate import migrate_database
    app,owner_token,_,_,database,_=application
    access=app.state.auth.access;identity=app.state.auth.oidc.verify_access_token(owner_token)
    first=access.resolve(identity)
    name='czero_profile_'+uuid4().hex
    with database.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.execute(text('CREATE DATABASE '+name))
    other=Database(str(make_url(os.environ['CZERO_TEST_DATABASE_URL']).set(database=name)))
    try:
        migrate_database(other)
        service=AccessService(other,access.issuer,access.owner_account_key)
        second=service.resolve(identity)
        assert second.user_id!=first.user_id
        assert service.profile(second)['id']==second.user_id
        assert access.profile(first)['id']==first.user_id
    finally:
        other.close()
        with database.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.execute(text('DROP DATABASE '+name))


@pytest.mark.parametrize('tamper', [False, True])
def test_exact_predecessor_profile_fixture_uses_old_me_then_verified_new_profile(application, monkeypatch, tmp_path, tamper):
    import sys
    from pathlib import Path
    from fastapi.testclient import TestClient
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    import profile_fixture, oidc_probe
    monkeypatch.setattr(profile_fixture,'STATE',tmp_path)
    (tmp_path/'personas.json').write_text(json.dumps({'host':'c0.example.test','password':'fixture-only'}))
    app,owner_token,member_token,*_=application
    phase=['seed'];calls=[]
    verifier=app.state.auth.oidc.verify_access_token
    def native_names(raw):
        identity=verifier(raw)
        return replace(identity,username='c0'+identity.username)
    monkeypatch.setattr(app.state.auth.oidc,'verify_access_token',native_names)
    class Browser:
        def __init__(self,origin):
            self.origin=origin;self.http=TestClient(app,base_url=origin)
        def login(self,username,password,expected=200):
            self.http.headers['Authorization']='Bearer '+(owner_token if username=='c0owner' else member_token)
            response=self.http.get('/api/v1/me');assert response.status_code==expected
            return {**response.json(),'csrf_token':'fixture-only'} if expected==200 else None
        def api(self,path,data=None,method=None,csrf=None):
            calls.append((phase[0],path))
            if phase[0]=='seed':assert path!='/api/v1/profile'
            response=self.http.request(method or 'GET',path,json=data)
            return response.status_code,response.content,str(response.url)
        def logout(self,me):self.http.close()
    monkeypatch.setattr(oidc_probe,'Browser',Browser)
    profile_fixture.predecessor('seed')
    saved=tmp_path/'predecessor-profiles.json'
    assert saved.stat().st_mode & 0o777==0o600
    values=json.loads(saved.read_text());assert values['c0owner']!=values['c0member']
    phase[0]='verify'
    if tamper:
        saved.write_text(json.dumps({**values,'c0owner':str(uuid4())}))
        with pytest.raises(AssertionError,match='Genuine predecessor profile identity changed'):
            profile_fixture.predecessor('verify')
    else:
        profile_fixture.predecessor('verify')
        assert sum(path=='/api/v1/profile' for _,path in calls)==2
        async def rejected():
            async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+member_token}) as http:
                assert (await http.get('/api/v1/profile')).status_code==403
        asyncio.run(rejected())


@pytest.mark.parametrize('mode', ['auto','legacy'])
def test_profile_sdk_invalid_identity_never_returns_a_fallback(transport, monkeypatch, mode):
    async def check():
        app,child,_,_,pair,*_=transport
        monkeypatch.setattr(app.state.auth.access,'profile',lambda actor: {'id':None,'username':'private-fixture-label'})
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as sdk:
                    result=await sdk.call_tool('get_profile',{})
                    assert result.is_error and result.structured_content is None
                    assert result.content[0].text=='invalid_operation_request'
                    assert 'private-fixture-label' not in result.content[0].text
    asyncio.run(check())
