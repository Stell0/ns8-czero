# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import os
import secrets
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
    grants = OAuthGrantService(access, 'czero900', RESOURCE)
    child = create_mcp_app(app.state.operations, grants, issuer_url=ISSUER)
    app.mount('/', child)
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
        pages = connection.execute(text('SELECT DISTINCT page_id FROM c0_wiki_revisions WHERE actor_id=:actor'),
            {'actor': owner.user_id}).scalars().all()
        for page in pages:
            connection.execute(text('DELETE FROM c0_wiki_revisions WHERE page_id=:id'), {'id': page})
            connection.execute(text('DELETE FROM c0_wiki_pages WHERE id=:id'), {'id': page})
        connection.execute(text('DELETE FROM c0_knowledge_receipts WHERE actor_id=:actor'), {'actor': owner.user_id})
        connection.execute(text('DELETE FROM c0_knowledge_events WHERE actor_id=:actor'), {'actor': owner.user_id})
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
                    access.set_role(owner, member_id, None)
                    response = await http.post('/mcp', json={})
                    assert response.status_code == 401 and 'resource_metadata=' in response.headers['www-authenticate']
        assert grants.verify(owner_pair.access_token, resource=RESOURCE).actor == owner
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
                assert set(metadata['scopes_supported']) == {'c0:read', 'c0:write', 'c0:admin'}
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
