# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from test_auth_http import application, ORIGIN
from test_spaces_http import space_http, create_space
from test_mcp_http import transport

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_projects_use_explicit_protected_selection_and_actual_signed_http(space_http):
    async def check():
        app, owner, member, *_ = space_http[0]
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                               headers={'Authorization': 'Bearer ' + owner}) as client:
            space = await create_space(client, space_http)
            selector = {'space_id': space['id']}
            values = {'manifest': {'project_id': space['id'], 'space_id': space['id'], 'name': 'Synthetic project',
                'purpose': 'Test research', 'scope': 'Fabricated records only'},
                'authorization_ref': 'synthetic-user-turn:setup', 'idempotency_key': 'setup'}
            assert (await client.post('/api/v1/project/initialize', json=values)).status_code == 422
            first = await client.post('/api/v1/project/initialize', params=selector, json=values)
            assert first.status_code == 200, first.text
            assert (await client.post('/api/v1/project/initialize', params=selector, json=values)).json() == first.json()
            stored = await client.get('/api/v1/project', params=selector)
            assert stored.status_code == 200 and stored.json() == first.json()
            assert stored.headers['cache-control'] == 'no-store'
            assert (await client.get('/api/v1/project', params={'space_id': str(uuid4())})).status_code == 403
            duplicate = '/api/v1/project?space_id=' + space['id'] + '&space_id=' + space['id']
            assert (await client.get(duplicate)).status_code == 422
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/project', params=selector)).status_code == 403
            client.headers['Authorization'] = 'Bearer ' + owner
            record_id = first.json()['id']
            forbidden = await client.put('/api/v1/objects/' + record_id, params=selector,
                json={'data': first.json()['data'], 'expected_revision': 1})
            assert forbidden.status_code == 403
            history = await client.get('/api/v1/project/records', params={**selector, 'kind': 'config_v1'})
            assert len(history.json()['objects']) == 1
            schemas = (await client.get('/openapi.json')).json()
            assert schemas['paths']['/api/v1/project']['get']['x-c0-operation']['required_scope'] == 'c0:read'
            assert schemas['paths']['/api/v1/project/initialize']['post']['x-c0-operation']['required_scope'] == 'c0:admin'
    asyncio.run(check())


@pytest.mark.parametrize('mode', ['auto', 'legacy'])
def test_actual_sdk_reads_project_and_rejects_missing_or_foreign_space(space_http, transport, mode):
    import json
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    from test_mcp_http import RESOURCE
    async def check():
        app, child, _, _, pair, _, owner_token, _ = transport
        assert app is space_http[0][0]
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization':'Bearer ' + owner_token}) as http:
            space = await create_space(http, space_http)
            payload = {'manifest': {'project_id':space['id'], 'space_id':space['id'], 'name':'SDK synthetic project',
                'purpose':'SDK contract', 'scope':'Synthetic records only'}, 'authorization_ref':'synthetic setup', 'idempotency_key':'sdk-setup'}
            expected = await http.post('/api/v1/project/initialize',params={'space_id':space['id']},json=payload)
            assert expected.status_code == 200
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                    headers={'Authorization':'Bearer ' + pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http), mode=mode) as sdk:
                    saved = await sdk.call_tool('project_get', {'space_id':space['id']})
                    assert not saved.is_error and saved.structured_content == expected.json()
                    assert json.loads(saved.content[0].text) == expected.json()
                    assert (await sdk.call_tool('project_get', {})).is_error
                    assert (await sdk.call_tool('project_get', {'space_id':str(uuid4())})).is_error
    asyncio.run(check())
