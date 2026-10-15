# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import os
import secrets
import time
from uuid import UUID, uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from czero_core.identity import PermissionDenied, Role
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_grants import OAuthGrantService, pkce_challenge
from czero_app.mcp_transport import create_mcp_app
from test_auth_http import application, ORIGIN, PrivateFixture

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
RESOURCE = ORIGIN + '/mcp'
ISSUER = ORIGIN + '/oauth'
CALLBACK = 'https://client.example.test/callback'


@pytest.fixture
def transport(application):
    app, owner_token, member_token, _, _, _ = application
    access = app.state.auth.access
    owner_identity = app.state.auth.oidc.verify_access_token(owner_token)
    owner = access.resolve(owner_identity)
    clients = OAuthClientService(access)
    client = clients.register(owner, 'MCP HTTP fixture ' + uuid4().hex, [CALLBACK],
        scopes=['c0:read', 'c0:write', 'c0:admin'])
    grants = app.state.delegated_grants
    child = app.state.mcp_app
    def token(identity, scopes):
        cookie = app.state.auth.sessions.create(identity)
        session = app.state.auth.sessions.get(cookie)
        verifier = secrets.token_urlsafe(32)
        code = grants.issue_code(session, client['client_id'], callback=CALLBACK, scopes=scopes,
            challenge=pkce_challenge(verifier), resource=RESOURCE)
        return grants.exchange_code(code, client['client_id'], callback=CALLBACK,
            verifier=verifier, resource=RESOURCE)
    pair = token(owner_identity, {'c0:read', 'c0:write', 'c0:admin'})
    yield PrivateFixture((app, child, grants, client, pair, token, owner_token, member_token))
    with access.database.engine.begin() as connection:
        actors = {'issuer': access.issuer}
        pages = connection.execute(text('''SELECT DISTINCT page_id FROM c0_wiki_revisions
            WHERE actor_id IN (SELECT id FROM c0_accounts WHERE issuer=:issuer)'''), actors).scalars().all()
        for page in pages:
            connection.execute(text('DELETE FROM c0_wiki_revisions WHERE page_id=:id'), {'id': page})
            connection.execute(text('DELETE FROM c0_wiki_pages WHERE id=:id'), {'id': page})
        for table in ('c0_knowledge_receipts', 'c0_knowledge_events'):
            connection.execute(text(f'''DELETE FROM {table} WHERE actor_id IN
                (SELECT id FROM c0_accounts WHERE issuer=:issuer)'''), actors)
        connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id': UUID(client['client_id'])})


def test_official_sdk_current_legacy_tools_resources_match_real_rest(transport):
    async def check():
        app, child, _, _, pair, _, owner_token, _ = transport
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization': 'Bearer ' + owner_token}) as rest:
            response = await rest.get('/api/v1/object-types')
            assert response.status_code == 200
            expected_types = response.json()
            payload = {'slug':'mcp-' + uuid4().hex, 'title':'MCP parity', 'body':'Authored exact body.',
                       'idempotency_key':'mcp-' + uuid4().hex}
            page = await rest.post('/api/v1/wiki/pages', json=payload)
            assert page.status_code == 201
            expected_page = page.json()
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                    headers={'Authorization':'Bearer ' + pair.access_token}) as http:
                for mode in ('auto', 'legacy'):
                    async with Client(streamable_http_client(RESOURCE, http_client=http), mode=mode) as client:
                        tools = (await client.list_tools()).tools
                        assert len(tools) == 63 and any(t.name == 'wiki_pages_create' for t in tools)
                        assert next(t for t in tools if t.name == 'objects_list').annotations.read_only_hint
                        result = await client.call_tool('object_types_list', {})
                        assert not result.is_error and result.structured_content == expected_types
                        assert json.loads(result.content[0].text) == expected_types
                        page_result = await client.call_tool('wiki_pages_get', {'page_id':expected_page['id']})
                        assert page_result.structured_content == expected_page
                        assert str((await client.list_resources()).resources[0].uri) == 'c0://capabilities'
                        assert len((await client.list_resource_templates()).resource_templates) == 3
                        resource = await client.read_resource('c0://wiki/pages/' + expected_page['id'])
                        assert json.loads(resource.contents[0].text) == expected_page
                        descriptions = json.loads((await client.read_resource('c0://capabilities')).contents[0].text)
                        assert len(descriptions['operations']) == 63
                        assert (await client.call_tool('unregistered_operation', {})).is_error
                        assert (await client.call_tool('object_types_list', {'unknown':1})).is_error
                        with pytest.raises(MCPError, match='invalid_resource_request'):
                            await client.read_resource('https://unauthorized.invalid/resource')
    asyncio.run(check())


def test_reader_scope_and_current_revocation_are_enforced_by_real_sdk(transport):
    async def check():
        app, child, grants, _, owner_pair, token, owner_token, member_token = transport
        access = app.state.auth.access
        owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        with pytest.raises(PermissionDenied):
            access.resolve(app.state.auth.oidc.verify_access_token(member_token))
        member_id = next(row['id'] for row in access.list_accounts(owner) if row['username'] == 'member')
        access.set_role(owner, member_id, Role.READER)
        reader_pair = token(app.state.auth.oidc.verify_access_token(member_token), {'c0:read'})
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                    headers={'Authorization':'Bearer ' + reader_pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE, http_client=http)) as client:
                    tools = (await client.list_tools()).tools
                    assert tools and all(t.annotations.read_only_hint for t in tools)
                    assert 'wiki_pages_create' not in {t.name for t in tools}
                    result = await client.call_tool('objects_create', {'data':{'type_name':'not_registered','data':{}}})
                    assert result.is_error and result.content[0].text == 'permission_denied'
                    assert not result.meta or 'mcp/www_authenticate' not in result.meta
                    access.set_role(owner, member_id, None)
                    response = await http.post('/mcp', json={})
                    assert response.status_code == 401 and 'resource_metadata=' in response.headers['www-authenticate']
        assert grants.verify(owner_pair.access_token, resource=RESOURCE).actor == owner
    asyncio.run(check())


@pytest.mark.parametrize('mode', ['auto', 'legacy'])
@pytest.mark.parametrize('role', [Role.READER, Role.EDITOR, Role.ADMIN])
def test_role_eligible_discovery_and_explicit_scope_upgrade(transport, mode, role):
    async def check():
        app, child, _, _, _, token, owner_token, member_token = transport
        access = app.state.auth.access
        owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        identity = app.state.auth.oidc.verify_access_token(member_token)
        with pytest.raises(PermissionDenied):
            access.resolve(identity)
        member_id = next(row['id'] for row in access.list_accounts(owner) if row['username'] == 'member')
        access.set_role(owner, member_id, role)
        pair = token(identity, {'c0:read'})
        wire_tools = []
        async def capture(response):
            if response.status_code == 200 and response.request.url.path == '/mcp':
                body = json.loads(await response.aread())
                if 'tools' in body.get('result', {}):
                    wire_tools.extend(body['result']['tools'])
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                    headers={'Authorization':'Bearer ' + pair.access_token},
                    event_hooks={'response':[capture]}) as http:
                async with Client(streamable_http_client(RESOURCE, http_client=http), mode=mode) as client:
                    tools = (await client.list_tools()).tools
                    names = {tool.name for tool in tools}
                    assert ('wiki_pages_create' in names) == (role is not Role.READER)
                    assert ('job_handlers_list' in names) == (role is Role.ADMIN)
                    assert len(wire_tools) == len(tools)
                    for tool, wire in zip(tools, wire_tools):
                        scope = app.state.operations.definition(tool.name)['required_scope']
                        schemes = [{'type':'oauth2', 'scopes':[scope]}]
                        assert tool.meta['securitySchemes'] == schemes
                        assert wire['securitySchemes'] == wire['_meta']['securitySchemes'] == schemes
                    assert not (await client.call_tool('object_types_list', {})).is_error
                    # Resource and REST capabilities still reflect actual authority.
                    capabilities = json.loads((await client.read_resource('c0://capabilities')).contents[0].text)
                    assert all(item['required_scope'] == 'c0:read' for item in capabilities['operations'])
                    denied = await client.call_tool('objects_create', {'data':{'type_name':'absent','data':{}}})
                    assert denied.is_error
                    if role is Role.READER:
                        assert denied.content[0].text == 'permission_denied'
                        assert not denied.meta or 'mcp/www_authenticate' not in denied.meta
                        with pytest.raises(PermissionDenied):
                            token(identity, {'c0:read', 'c0:write'})
                    else:
                        assert denied.content[0].text == 'insufficient_scope'
                        challenge, = denied.meta['mcp/www_authenticate']
                        assert challenge.startswith('Bearer ')
                        for field in ('error="insufficient_scope"', 'error_description="',
                                'scope="c0:write"', 'resource_metadata="' + ORIGIN + '/.well-known/oauth-protected-resource/mcp"'):
                            assert field in challenge
                        assert 'c0:admin' not in challenge
                    admin = await client.call_tool('job_handlers_list', {})
                    assert admin.is_error
                    if role is Role.ADMIN:
                        assert 'scope="c0:admin"' in admin.meta['mcp/www_authenticate'][0]
                    else:
                        assert admin.content[0].text == 'permission_denied'
                        assert not admin.meta or 'mcp/www_authenticate' not in admin.meta
                # A newly consented token is needed; an existing token cannot gain scopes.
                if role is not Role.READER:
                    upgraded = token(identity, {'c0:read', 'c0:write'})
                    http.headers['Authorization'] = 'Bearer ' + upgraded.access_token
                    async with Client(streamable_http_client(RESOURCE, http_client=http), mode=mode) as client:
                        result = await client.call_tool('wiki_pages_create', {'data':{
                            'slug':'scope-' + uuid4().hex, 'title':'Scoped write', 'body':'Isolated fixture.',
                            'idempotency_key':'scope-' + uuid4().hex}})
                        assert not result.is_error and result.structured_content['title'] == 'Scoped write'
                if role is Role.ADMIN:
                    admin_pair = token(identity, {'c0:admin'})
                    http.headers['Authorization'] = 'Bearer ' + admin_pair.access_token
                    async with Client(streamable_http_client(RESOURCE, http_client=http), mode=mode) as client:
                        assert not (await client.call_tool('job_handlers_list', {})).is_error
                        read = await client.call_tool('object_types_list', {})
                        assert read.is_error and 'scope="c0:read"' in read.meta['mcp/www_authenticate'][0]
    asyncio.run(check())


@pytest.mark.parametrize('failure', ['revoked', 'expired', 'audience', 'role_downgrade', 'client_disabled'])
def test_invalidated_tokens_cannot_discover_or_request_scope_upgrades(transport, monkeypatch, failure):
    async def check():
        app, child, grants, saved, pair, _, owner_token, _ = transport
        access = app.state.auth.access
        owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        if failure == 'revoked':
            grants.revoke(pair.access_token, saved['client_id'], resource=RESOURCE)
        elif failure == 'expired':
            monkeypatch.setattr(grants, '_now', lambda: time.time() + 301)
        elif failure == 'audience':
            # A different configured audience must reject a real, otherwise valid token.
            other = OAuthGrantService(access, grants.native_client, ORIGIN + '/other-mcp')
            monkeypatch.setattr(grants, 'verify', lambda value, *, resource: other.verify(value, resource=other.resource))
        elif failure == 'client_disabled':
            OAuthClientService(access).set_enabled(owner, UUID(saved['client_id']), enabled=False,
                expected_revision=saved['revision'])
        else:
            # An ordinary member's grants are removed atomically on role downgrade.
            # The fixture owner itself cannot be downgraded.
            _, _, _, _, _, issue, _, member_token = transport
            identity = app.state.auth.oidc.verify_access_token(member_token)
            with pytest.raises(PermissionDenied):
                access.resolve(identity)
            member_id = next(row['id'] for row in access.list_accounts(owner) if row['username'] == 'member')
            access.set_role(owner, member_id, Role.EDITOR)
            pair = issue(identity, {'c0:read', 'c0:write'})
            access.set_role(owner, member_id, Role.READER)
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                    headers={'Authorization':'Bearer ' + pair.access_token}) as http:
                for method in ('tools/list', 'tools/call'):
                    response = await http.post('/mcp', json={'jsonrpc':'2.0','id':1,'method':method,
                        'params':{} if method == 'tools/list' else {'name':'objects_create','arguments':{}}})
                    assert response.status_code == 401
                    assert 'resource_metadata=' in response.headers['www-authenticate']
                    assert 'securitySchemes' not in response.text and 'mcp/www_authenticate' not in response.text
    asyncio.run(check())


def test_protected_metadata_host_origin_body_and_cookie_do_not_bypass_bearer(transport):
    async def check():
        _, child, _, _, pair, _, _, _ = transport
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=child), base_url=ORIGIN) as http:
                response = await http.post('/mcp', json={})
                assert response.status_code == 401 and response.headers['cache-control'] == 'no-store'
                metadata = (await http.get('/.well-known/oauth-protected-resource/mcp')).json()
                assert metadata['resource'] == RESOURCE and metadata['authorization_servers'] == [ISSUER]
                assert metadata['scopes_supported'] == ['c0:read']
                assert (await http.post('/mcp', json={}, headers={'Cookie':'c0_session=unverified'})).status_code == 401
                http.headers['Authorization'] = 'Bearer ' + pair.access_token
                for headers in [{'Host':'unauthorized.invalid'}, {'Origin':'https://unauthorized.invalid'}]:
                    assert (await http.post('/mcp', json={}, headers=headers)).status_code in (400, 403, 421)
                response = await http.post('/mcp', content=b' ' * (1024 * 1024 + 1),
                    headers={'Content-Type':'application/json', 'Accept':'application/json, text/event-stream'})
                assert response.status_code == 413
                async def chunked():
                    yield b' ' * (1024 * 1024)
                    yield b' '
                response = await http.post('/mcp', content=chunked(), headers={
                    'Content-Type':'application/json', 'Accept':'application/json, text/event-stream'})
                assert response.status_code == 413
    asyncio.run(check())


def test_token_database_failure_has_static_diagnostics(transport, monkeypatch, caplog):
    async def check():
        _, child, grants, _, pair, _, _, _ = transport
        def unavailable(*args, **kwargs):
            raise SQLAlchemyError('synthetic-private-database-diagnostic')
        monkeypatch.setattr(grants, 'verify', unavailable)
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=child), base_url=ORIGIN,
                    headers={'Authorization':'Bearer ' + pair.access_token}) as http:
                response = await http.post('/mcp', json={})
                assert response.status_code == 503 and response.json() == {'error':'service_unavailable'}
                assert 'synthetic-private-database-diagnostic' not in caplog.text
    asyncio.run(check())


@pytest.mark.parametrize('bypass_origin', [False, True])
@pytest.mark.parametrize('role,scope', [(Role.READER,'c0:read'), (Role.EDITOR,'c0:read'),
    (Role.ADMIN,'c0:read'), (Role.EDITOR,'c0:read c0:write'), (Role.ADMIN,'c0:read c0:write')])
def test_exact_installed_probe_requires_valid_positive_control_and_proxy_rejection(transport, monkeypatch, bypass_origin, role, scope):
    import importlib.util
    from pathlib import Path
    from starlette.responses import Response
    app,child,_,_,pair,token,owner_token,member_token=transport
    access=app.state.auth.access
    owner=access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    identity=app.state.auth.oidc.verify_access_token(member_token)
    with pytest.raises(PermissionDenied):
        access.resolve(identity)
    member_id=next(row['id'] for row in access.list_accounts(owner) if row['username']=='member')
    access.set_role(owner,member_id,role)
    read_pair=token(identity,set(scope.split()))
    path=Path(__file__).resolve().parents[1]/'mcp_tls_probe.py'
    spec=importlib.util.spec_from_file_location('installed_tls_probe',path)
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    async def proxy(scope,receive,send):
        headers=dict(scope.get('headers',[]))
        if headers.get(b'host')==b'unapproved.invalid':
            return await Response(status_code=404)(scope,receive,send)
        if bypass_origin:
            scope={**scope,'headers':[(k,v) for k,v in scope.get('headers',[]) if k!=b'origin']}
        await app(scope,receive,send)
    monkeypatch.setattr(probe,'NodeTransport',lambda *_:httpx2.ASGITransport(app=proxy))
    async def check():
        async with app.router.lifespan_context(app):
            value={'origin':ORIGIN,'address':None,'ca':None,'access_token':read_pair.access_token,'scope':scope}
            if bypass_origin:
                with pytest.raises(AssertionError,match='^Installed origin guard returned HTTP 200$'):
                    await probe.check(value)
            else:
                await probe.check(value)
    asyncio.run(check())
