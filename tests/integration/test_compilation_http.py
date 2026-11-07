# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import text

from czero_core.compilation_schema import defaults
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport


def test_rest_and_both_mcp_modes_use_core_policy_and_fixed_errors(knowledge_http, transport):
    app, owner, _, _, database, _ = knowledge_http
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization': 'Bearer ' + owner}) as http:
            space = (await http.get('/api/v1/spaces')).json()['spaces'][0]['id']
            path = '/api/v1/compilation'
            assert (await http.get(path + '/policy')).status_code == 422
            disabled = await http.get(path + '/policy', params={'space_id': space})
            assert disabled.status_code == 200 and disabled.json()['revision'] == 0
            invalid = await http.put(path + '/policy', params={'space_id': space},
                json={'data': {'query': 'PRIVATE-MUST-NOT-ECHO'}, 'expected_revision': 0, 'idempotency_key': 'bad'})
            assert invalid.status_code == 422 and 'PRIVATE-MUST-NOT-ECHO' not in invalid.text
            saved = await http.put(path + '/policy', params={'space_id': space},
                json={'data': defaults(), 'expected_revision': 0, 'idempotency_key': 'disabled'})
            assert saved.status_code == 200 and saved.json()['policy']['revision'] == 1
            child = app.state.mcp_app
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                        headers={'Authorization': 'Bearer ' + transport[4].access_token}) as wire:
                    for mode in ('auto', 'legacy'):
                        async with Client(streamable_http_client(ORIGIN + '/mcp', http_client=wire), mode=mode) as client:
                            tools = (await client.list_tools()).tools
                            selected = [t for t in tools if t.name.startswith('compilation_')]
                            assert len(selected) == 13
                            assert all(not t.annotations.open_world_hint for t in selected)
                            result = await client.call_tool('compilation_policy_get', {'space_id': space})
                            assert not result.is_error and result.structured_content['revision'] == 1
                            denied = await client.call_tool('compilation_run_claim', {'space_id': space,
                                'data': {'data': {'kind': 'manual', 'cycle_key': 'test', 'lease_owner': 'runner', 'policy_revision': 1},
                                    'idempotency_key': uuid4().hex}})
                            assert denied.is_error and 'compilation_disabled' in str(denied.content)
                            foreign = await client.call_tool('compilation_status_get', {'space_id': str(uuid4())})
                            assert foreign.is_error and 'permission_denied' in str(foreign.content)
    try:
        asyncio.run(check())
    finally:
        with database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_compilation_events'))
            c.execute(text('DELETE FROM c0_compilation_policies'))


def test_legacy_mount_sanitizes_invalid_inputs(knowledge_http):
    from pathlib import Path
    from czero_app.main import create_app
    app, owner, _, _, database, _ = knowledge_http
    legacy = create_app('czero900', Path(__file__).parents[2]/'app/frontend/dist',
        '/czero/czero900', database, auth=app.state.auth)
    async def check():
        async with AsyncClient(transport=ASGITransport(app=legacy), base_url=ORIGIN,
                headers={'Authorization': 'Bearer '+owner}) as http:
            response = await http.put('/czero/czero900/api/v1/compilation/policy',
                params={'space_id': str(uuid4())}, json={'unrecognized': 'PRIVATE-DO-NOT-ECHO'})
            assert response.status_code == 422
            assert response.json() == {'detail': 'invalid_compilation_request'}
    asyncio.run(check())
