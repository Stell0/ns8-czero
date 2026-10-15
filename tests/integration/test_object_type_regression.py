# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent REST/SDK regressions for bounded structured type registration."""
import asyncio
import copy
from contextlib import asynccontextmanager
import json
import os
from uuid import uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest

from czero_core.objects import ObjectNotFound
from czero_core.identity import PermissionDenied, Role
from test_mcp_http import transport, RESOURCE
from test_objects_http import cleanup
from test_auth_http import application, ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
SCHEMA = {'type':'object', 'required':['name'], 'properties':{'name':{'type':'string'}},
          'additionalProperties':False}


@asynccontextmanager
async def object_channel(fixture, channel, credential=None):
    """Send independent HTTP requests or actual SDK calls; assert wire errors."""
    app, child, _, _, pair, _, owner_token, _ = fixture
    async def result(client, operation, arguments, status=200, error=None):
        if channel == 'rest':
            routes = {
                'object_types_create':('POST','/api/v1/object-types'),
                'object_types_get':('GET','/api/v1/object-types/' + arguments.get('type_name','')),
                'object_types_list':('GET','/api/v1/object-types'),
                'objects_create':('POST','/api/v1/objects'),
                'objects_list':('GET','/api/v1/objects'),
                'objects_get':('GET','/api/v1/objects/' + arguments.get('object_id','')),
                'objects_update':('PUT','/api/v1/objects/' + arguments.get('object_id','')),
                'objects_delete':('DELETE','/api/v1/objects/' + arguments.get('object_id','')),
            }
            method, path = routes[operation]
            options = {'json':arguments['data']} if method in ('POST','PUT') else {
                'params':{k:v for k,v in arguments.items() if k not in ('object_id',)}}
            response = await client.request(method, path, **options)
            assert response.status_code == status, response.text
            value = response.json()
            if error:
                detail = 'forbidden' if error in ('permission_denied','insufficient_scope') else error
                assert value == {'detail':detail}
            return value
        response = await client.call_tool(operation, arguments)
        assert response.is_error == bool(error)
        if error:
            assert response.content[0].text == error
            if error == 'permission_denied':
                assert not response.meta or 'mcp/www_authenticate' not in response.meta
            elif error == 'insufficient_scope':
                assert 'scope="c0:admin"' in response.meta['mcp/www_authenticate'][0]
            else:
                assert response.meta['c0/error'] == {'code':error,'status':status}
            return None
        assert json.loads(response.content[0].text) == response.structured_content
        return response.structured_content

    if channel == 'rest':
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization':'Bearer ' + (credential or owner_token)}) as client:
            yield lambda operation, arguments, **options: result(client, operation, arguments, **options)
    else:
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                    headers={'Authorization':'Bearer ' + (credential or pair.access_token)}) as http:
                async with Client(streamable_http_client(RESOURCE, http_client=http), mode=channel) as client:
                    yield lambda operation, arguments, **options: result(client, operation, arguments, **options)


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


@pytest.mark.parametrize('channel', ['rest', 'auto', 'legacy'])
def test_type_guidance_and_unexpected_validation_error_privacy(transport, monkeypatch, channel):
    async def check():
        app, child, _, _, pair, _, owner_token, _ = transport
        name = 'type-private-' + uuid4().hex
        def unexpected(*args, **kwargs):
            raise ValueError('synthetic-private-database-diagnostic')
        monkeypatch.setattr(app.state.objects, 'register_type', unexpected)
        data = {'name':name, 'label':'Fixture', 'schema':SCHEMA, 'unique_fields':[]}
        if channel == 'rest':
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                    headers={'Authorization':'Bearer ' + owner_token}) as client:
                response = await client.post('/api/v1/object-types', json=data)
                assert response.status_code == 422 and response.json() == {'detail':'invalid_object_request'}
                schema = (await client.get('/openapi.json')).json()['components']['schemas']['TypeCreate']
                assert 'maxLength <=128' in schema['properties']['unique_fields']['description']
        else:
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                        headers={'Authorization':'Bearer ' + pair.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE, http_client=http), mode=channel) as client:
                        tool = next(t for t in (await client.list_tools()).tools if t.name == 'object_types_create')
                        assert 'maxLength <=128' in tool.description
                        assert 'maxLength <=128' in tool.input_schema['$defs']['TypeCreate']['properties']['unique_fields']['description']
                        response = await client.call_tool('object_types_create', {'data':data})
                        assert response.is_error and response.content[0].text == 'invalid_object_request'
                        assert response.meta['c0/error'] == {'code':'invalid_object_request','status':422}
                        assert 'synthetic-private' not in str(response.model_dump())
    asyncio.run(check())


ROBOT_SCHEMA = {'type':'object', 'required':['name','manufacturer'], 'properties':{
    'name':{'type':'string','maxLength':128}, 'manufacturer':{'type':'string'},
    'category':{'type':'string'}, 'source_url':{'type':'string'}}, 'additionalProperties':False}


@pytest.mark.parametrize('channel', ['rest','auto','legacy'])
def test_supported_type_variants_are_discoverable_with_normalized_schema(transport, channel):
    async def check():
        names = ['type-variant-' + uuid4().hex for _ in range(3)]
        variants = [SCHEMA, {'type':'object','properties':{
            'name':{'type':'string'}, 'quantity':{'type':'integer','minimum':0},
            'active':{'type':'boolean'}}}, ROBOT_SCHEMA]
        try:
            async with object_channel(transport, channel) as call:
                for name, schema in zip(names, variants):
                    created = await call('object_types_create', {'data':{
                        'name':name,'label':'Schema variants','schema':schema}}, status=201)
                    got = await call('object_types_get', {'type_name':name})
                    assert got == created and got['unique_fields'] == []
                    assert got['schema']['additionalProperties'] is False
                    assert got['schema'].get('required',[]) == schema.get('required',[])
                    for field, definition in schema['properties'].items():
                        assert definition.items() <= got['schema']['properties'][field].items()
                    listed = await call('object_types_list', {'limit':100})
                    assert got in listed['types']
        finally:
            cleanup(transport[0].state.auth.access.database, names)
    asyncio.run(check())


@pytest.mark.parametrize('channel', ['rest','auto','legacy'])
def test_complete_validated_object_lifecycle_and_type_isolation(transport, channel):
    async def check():
        names = ['robot-regression-' + uuid4().hex for _ in range(2)]
        record = {'name':'Digit 5','manufacturer':'Isolated fixture','category':'test',
                  'source_url':'https://example.invalid/fixture'}
        try:
            async with object_channel(transport, channel) as call:
                payload = {'name':names[0],'label':'Isolated CRUD','schema':ROBOT_SCHEMA,'unique_fields':['name']}
                created_type = await call('object_types_create', {'data':payload}, status=201)
                await call('object_types_create', {'data':payload}, status=409, error='object_conflict')
                assert await call('object_types_get', {'type_name':names[0]}) == created_type
                await call('object_types_create', {'data':{**payload,'name':names[1]}}, status=201)
                other = await call('objects_create', {'data':{'type_name':names[1],'data':record}}, status=201)
                row = await call('objects_create', {'data':{'type_name':names[0],'data':record,'tags':['regression']}}, status=201)
                assert row['data'] == record and row['revision'] == 1
                assert await call('objects_get', {'object_id':row['id']}) == row
                query = {'type_name':names[0],'where':json.dumps({'manufacturer':'Isolated fixture'}),'tag':'regression'}
                assert (await call('objects_list', query))['objects'] == [row]
                await call('objects_create', {'data':{'type_name':names[0],'data':record}}, status=409, error='object_conflict')
                for data, code in [({'name':'missing'},'record_invalid::required'),
                        ({**record,'name':42},'record_invalid:name:type'),
                        ({**record,'extra':'private-value'},'record_invalid::additionalProperties'),
                        ({**record,'name':'x'*129},'record_invalid:name:maxLength')]:
                    await call('objects_create', {'data':{'type_name':names[0],'data':data}}, status=422, error=code)
                assert (await call('objects_list', query))['objects'] == [row]
                updated_data = {**record,'category':'updated'}
                updated = await call('objects_update', {'object_id':row['id'],
                    'data':{'data':updated_data,'expected_revision':row['revision']}})
                assert updated['revision'] == 2 and updated['data'] == updated_data and updated['tags'] == ['regression']
                await call('objects_update', {'object_id':row['id'],
                    'data':{'data':record,'expected_revision':1}}, status=409, error='object_conflict')
                await call('objects_update', {'object_id':row['id'],
                    'data':{'data':{**record,'name':42},'expected_revision':2}}, status=422, error='record_invalid:name:type')
                assert await call('objects_get', {'object_id':row['id']}) == updated
                await call('objects_delete', {'object_id':row['id'],'expected_revision':1}, status=409, error='object_conflict')
                deleted = await call('objects_delete', {'object_id':row['id'],'expected_revision':2})
                assert deleted == {'id':row['id'],'revision':2,'deleted':True}
                await call('objects_get', {'object_id':row['id']}, status=404, error='object_not_found')
                assert (await call('objects_list', {'type_name':names[0]}))['objects'] == []
                assert await call('objects_get', {'object_id':other['id']}) == other
                await call('objects_delete', {'object_id':other['id'],'expected_revision':1})
        finally:
            cleanup(transport[0].state.auth.access.database, names)
    asyncio.run(check())


@pytest.mark.parametrize('channel', ['rest','auto','legacy'])
def test_invalid_and_unsupported_schemas_return_precise_errors_without_registration(transport, channel):
    async def check():
        name = 'schema-rejected-' + uuid4().hex
        try:
            async with object_channel(transport, channel) as call:
                for schema, code in [({'type':'array'},'invalid_schema'),
                        ({'type':'object','required':'name'},'invalid_schema'),
                        ({'type':'object','$ref':'https://example.invalid/schema'},'unsupported_schema'),
                        ({'type':'object','properties':{'url':{'type':'string','format':'uri'}}},'unsupported_schema'),
                        ({'type':'object','additionalProperties':True},'unsupported_schema')]:
                    await call('object_types_create', {'data':{'name':name,'label':'Rejected','schema':schema}},
                        status=422, error=code)
                    await call('object_types_get', {'type_name':name}, status=404, error='object_not_found')
                for fields in (['missing'], ['name','name']):
                    await call('object_types_create', {'data':{'name':name,'label':'Rejected',
                        'schema':ROBOT_SCHEMA,'unique_fields':fields}}, status=422, error='invalid_unique_fields')
                assert name not in {row['name'] for row in (await call('object_types_list', {'limit':100}))['types']}
        finally:
            cleanup(transport[0].state.auth.access.database, [name])
    asyncio.run(check())


@pytest.mark.parametrize('channel', ['rest','auto','legacy'])
@pytest.mark.parametrize('role', [Role.READER,Role.EDITOR])
def test_type_registration_requires_admin_while_editor_can_manage_records(transport, channel, role):
    async def check():
        app, _, _, _, _, issue, owner_token, member_token = transport
        name = 'type-role-' + uuid4().hex
        access = app.state.auth.access
        owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        identity = app.state.auth.oidc.verify_access_token(member_token)
        with pytest.raises(PermissionDenied):
            access.resolve(identity)
        member = next(a for a in access.list_accounts(owner) if a['username'] == 'member')
        access.set_role(owner, member['id'], role)
        delegated = issue(identity, {'c0:read'} if role is Role.READER else {'c0:read','c0:write'})
        try:
            # Seed once through REST; each SDK manager has one lifespan, as in
            # production. Role assertions below use the selected transport.
            async with object_channel(transport, 'rest') as call:
                await call('object_types_create', {'data':{'name':name,'label':'Roles','schema':ROBOT_SCHEMA}}, status=201)
            async with object_channel(transport, channel, delegated.access_token) as call:
                assert (await call('object_types_get', {'type_name':name}))['name'] == name
                # Persisted role takes precedence over malformed schema and scopes.
                await call('object_types_create', {'data':{'name':name,'label':'Roles','schema':{'type':'array'}}},
                    status=403, error='permission_denied')
                arguments = {'data':{'type_name':name,'data':{'name':'Fixture','manufacturer':'Fixture'}}}
                if role is Role.READER:
                    await call('objects_create', arguments, status=403, error='permission_denied')
                else:
                    row = await call('objects_create', arguments, status=201)
                    changed = await call('objects_update', {'object_id':row['id'],
                        'data':{'data':{**row['data'],'category':'editor'},'expected_revision':1}})
                    assert changed['revision'] == 2
                    await call('objects_delete', {'object_id':row['id'],'expected_revision':2})
        finally:
            cleanup(access.database, [name])
    asyncio.run(check())


@pytest.mark.parametrize('channel', ['rest','auto','legacy'])
def test_admin_read_token_cannot_register_type_without_scope_upgrade(transport, channel):
    async def check():
        app, _, _, _, _, issue, owner_token, _ = transport
        pair = issue(app.state.auth.oidc.verify_access_token(owner_token), {'c0:read'})
        async with object_channel(transport, channel, pair.access_token) as call:
            await call('object_types_create', {'data':{'name':'scope-'+uuid4().hex,'label':'Scope','schema':SCHEMA}},
                status=403, error='insufficient_scope')
    asyncio.run(check())


@pytest.mark.parametrize('channel', ['rest','auto','legacy'])
@pytest.mark.parametrize('authority', ['missing','revoked'])
def test_missing_or_revoked_delegation_cannot_register_a_type(transport, channel, authority):
    async def check():
        app, _, grants, client, pair, _, _, _ = transport
        if authority == 'revoked':
            grants.revoke(pair.access_token, client['client_id'], resource=RESOURCE)
        data = {'name':'revoked-'+uuid4().hex,'label':'Revoked','schema':SCHEMA}
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization':'Bearer '+pair.access_token} if authority == 'revoked' else {}) as http:
            if channel == 'rest':
                response = await http.post('/api/v1/object-types', json=data)
            else:
                response = await http.post('/mcp', headers={'Accept':'application/json, text/event-stream',
                    'MCP-Protocol-Version':'2025-11-25'}, json={'jsonrpc':'2.0','id':1,
                    'method':'tools/call','params':{'name':'object_types_create','arguments':{'data':data}}})
            assert response.status_code == 401
            assert 'schema' not in response.text
    asyncio.run(check())
