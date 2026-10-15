# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent REST/SDK regressions for bounded structured type registration."""
import asyncio
import copy
import os
from uuid import uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest

from czero_core.objects import ObjectNotFound
from test_mcp_http import transport, RESOURCE
from test_objects_http import cleanup
from test_auth_http import application, ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
SCHEMA = {'type':'object', 'required':['name'], 'properties':{'name':{'type':'string'}},
          'additionalProperties':False}


def test_reported_schema_reaches_core_unique_string_limit(transport):
    app, _, _, _, _, _, owner_token, _ = transport
    access = app.state.auth.access
    owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    name = 'type-core-' + uuid4().hex
    with pytest.raises(ValueError, match='^unique_string_too_long$'):
        app.state.objects.register_type(owner, name, 'Fixture', SCHEMA, ['name'])
    with pytest.raises(ObjectNotFound):
        app.state.objects.get_type(owner, name)
    assert 'maxLength' not in SCHEMA['properties']['name']


@pytest.mark.parametrize('channel', ['rest', 'auto', 'legacy'])
def test_unbounded_unique_string_has_precise_transport_error(transport, channel):
    async def check():
        app, child, _, _, pair, _, owner_token, _ = transport
        name = 'type-error-' + uuid4().hex
        data = {'name':name, 'label':'Fixture', 'schema':SCHEMA, 'unique_fields':['name']}
        try:
            if channel == 'rest':
                async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                        headers={'Authorization':'Bearer ' + owner_token}) as client:
                    response = await client.post('/api/v1/object-types', json=data)
                    assert response.status_code == 422
                    assert response.json() == {'detail':'unique_string_too_long'}
            else:
                async with child.router.lifespan_context(child):
                    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                            headers={'Authorization':'Bearer ' + pair.access_token}) as http:
                        async with Client(streamable_http_client(RESOURCE, http_client=http), mode=channel) as client:
                            response = await client.call_tool('object_types_create', {'data':data})
                            assert response.is_error
                            assert response.content[0].text == 'unique_string_too_long'
            with pytest.raises(ObjectNotFound):
                app.state.objects.get_type(app.state.auth.access.resolve(
                    app.state.auth.oidc.verify_access_token(owner_token)), name)
        finally:
            cleanup(app.state.auth.access.database, [name])
    asyncio.run(check())


@pytest.mark.parametrize('channel', ['rest', 'auto', 'legacy'])
def test_bounded_unique_schema_creation_already_supported(transport, channel):
    async def check():
        app, child, _, _, pair, _, owner_token, _ = transport
        name = 'type-valid-' + uuid4().hex
        schema = copy.deepcopy(SCHEMA)
        schema['properties']['name']['maxLength'] = 128
        data = {'name':name, 'label':'Fixture', 'schema':schema, 'unique_fields':['name']}
        try:
            if channel == 'rest':
                async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                        headers={'Authorization':'Bearer ' + owner_token}) as client:
                    response = await client.post('/api/v1/object-types', json=data)
                    assert response.status_code == 201
                    created = response.json()
                    assert (await client.get('/api/v1/object-types/' + name)).json() == created
            else:
                async with child.router.lifespan_context(child):
                    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                            headers={'Authorization':'Bearer ' + pair.access_token}) as http:
                        async with Client(streamable_http_client(RESOURCE, http_client=http), mode=channel) as client:
                            response = await client.call_tool('object_types_create', {'data':data})
                            assert not response.is_error
                            created = response.structured_content
                            assert (await client.call_tool('object_types_get', {'type_name':name})).structured_content == created
            assert created['schema'] == schema and created['unique_fields'] == ['name']
        finally:
            cleanup(app.state.auth.access.database, [name])
    asyncio.run(check())
