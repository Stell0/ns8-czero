# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from czero_core.identity import PermissionDenied, Role
from czero_core.operations import OperationRejected, ScopeDenied
from test_auth_http import application, ORIGIN
from test_objects_http import cleanup, SCHEMA

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_signed_discovery_and_direct_operations_match_rest_and_recheck_roles(application):
    async def check():
        app, owner_token, member_token, _, db, _ = application
        registry = app.state.operations
        access = app.state.auth.access
        owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        name = 'operations-' + uuid4().hex
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            anonymous = await client.get('/agents/capabilities.json')
            assert anonymous.status_code == 200 and anonymous.headers['cache-control'] == 'no-store'
            assert anonymous.json()['operations'] == [] and not anonymous.json()['authenticated']
            assert anonymous.json()['interfaces']['mcp'] is True
            assert anonymous.json()['mcp_url'] == ORIGIN + '/mcp'
            assert anonymous.json()['oauth']['authorization_server'] == ORIGIN + '/oauth'
            assert (await client.get('/agents')).text.count('Remote MCP Streamable HTTP is available') == 1
            assert 'data-copy-target="agent-mcp-url"' in (await client.get('/agents')).text
            assert (await client.get('/agents/capabilities.json', headers={'Authorization':'Bearer invalid'})).status_code == 401
            client.headers['Authorization'] = 'Bearer ' + owner_token
            try:
                capabilities = (await client.get('/agents/capabilities.json')).json()
                definitions = {op['name']:op for op in capabilities['operations']}
                assert capabilities['role'] == 'admin' and len(definitions) == 77
                assert definitions['objects_create']['required_scope'] == 'c0:write'
                assert definitions['schedules_list']['minimum_role'] == 'admin'
                assert 'multipart source upload' in capabilities['rest_attachments']
                schema = (await client.get('/openapi.json')).json()
                assert schema['x-c0-interfaces']['mcp_url'] == capabilities['mcp_url']
                assert schema['x-c0-interfaces']['oauth'] == capabilities['oauth']
                assert schema['paths']['/api/v1/objects']['post']['operationId'] == 'objects_create'
                assert schema['paths']['/api/v1/objects']['post']['x-c0-operation']['required_scope'] == 'c0:write'
                created = await client.post('/api/v1/object-types', json={'name':name,'label':'Parity','schema':SCHEMA})
                assert created.status_code == 201
                direct = registry.execute('object_types_get', owner, {'type_name':name}, scopes={'c0:read'})
                assert direct == (await client.get('/api/v1/object-types/' + name)).json()
                record = registry.execute('objects_create', owner, {'data':{'type_name':name,'data':{'name':'fixture'}}}, scopes={'c0:write'})
                assert record == (await client.get('/api/v1/objects/' + record['id'])).json()
                with pytest.raises(ScopeDenied):
                    registry.execute('objects_create', owner, {'data':{'type_name':name,'data':{'name':'denied'}}}, scopes={'c0:read'})
                with pytest.raises(OperationRejected):
                    registry.execute('objects_get', owner, {'object_id':record['id'],'sql':'untrusted'}, scopes={'c0:read'})
                with pytest.raises(OperationRejected):
                    registry.execute('objects_get', owner, {'object_id':'not-a-uuid'}, scopes={'c0:read'})
                with pytest.raises(PermissionDenied):
                    access.resolve(app.state.auth.oidc.verify_access_token(member_token))
                member_id = next(a['id'] for a in access.list_accounts(owner) if a['username'] == 'member')
                access.set_role(owner, member_id, Role.READER)
                reader = access.resolve(app.state.auth.oidc.verify_access_token(member_token))
                client.headers['Authorization'] = 'Bearer ' + member_token
                reader_metadata = (await client.get('/agents/capabilities.json')).json()
                assert reader_metadata['role'] == 'reader'
                assert all(op['read_only'] and op['minimum_role']=='reader' for op in reader_metadata['operations'])
                assert registry.execute('objects_get', reader, {'object_id':record['id']}, scopes={'c0:read'}) == record
                assert (await client.post('/api/v1/objects', json={'type_name':name,'data':{'name':'denied'}})).status_code == 403
                with pytest.raises(PermissionDenied):
                    registry.execute('objects_create', reader, {'data':{'type_name':name,'data':{'name':'denied'}}}, scopes={'c0:write'})
                access.set_role(owner, member_id, None)
                with pytest.raises(PermissionDenied):
                    registry.describe(reader)
                assert (await client.get('/agents/capabilities.json')).status_code == 403
            finally:
                cleanup(db, [name])
    asyncio.run(check())


def test_configured_legacy_prefix_keeps_rest_and_does_not_advertise_mcp(application):
    from czero_app.main import create_app
    configured, *_, database, _ = application
    legacy = create_app('czero17', base_path='/czero/czero17', database=database, auth=configured.state.auth)
    async def check():
        async with AsyncClient(transport=ASGITransport(app=legacy), base_url=ORIGIN) as client:
            value = (await client.get('/czero/czero17/agents/capabilities.json')).json()
            assert value['interfaces'] == {'rest': True, 'mcp': False}
            assert value['mcp_url'] is None and value['oauth'] is None
            assert value['rest_base'] == '/czero/czero17/api/v1' and value['operations'] == []
            schema = (await client.get('/czero/czero17/openapi.json')).json()
            assert schema['x-c0-interfaces']['mcp_url'] is None
            assert '/api/v1/wiki/pages' in schema['paths']
            assert (await client.get('/mcp')).status_code == 404
    asyncio.run(check())
