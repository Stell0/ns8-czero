# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Git-only installed SDK client, fed private JSON on stdin inside the app.

Route only the synthetic application vhost to the disposable node gateway.
TLS/SNI/Host/resource identities stay canonical; provider DNS is untouched.
"""
import asyncio
import json
import ssl
import sys
from urllib.parse import urlsplit
from uuid import uuid4

import httpcore2
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


class ApplicationRoute(httpcore2.AsyncNetworkBackend):
    def __init__(self, host, address):
        self.host, self.address, self.backend = host, address, httpcore2.AnyIOBackend()

    async def connect_tcp(self, host, port, **options):
        return await self.backend.connect_tcp(self.address if host == self.host else host, port, **options)

    async def connect_unix_socket(self, path, **options):
        return await self.backend.connect_unix_socket(path, **options)

    async def sleep(self, seconds):
        await self.backend.sleep(seconds)


class ResponseBody(httpx2.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        async for part in self.stream:
            yield part

    async def aclose(self):
        await self.stream.aclose()


class NodeTransport(httpx2.AsyncBaseTransport):
    def __init__(self, host, address, ca):
        self.pool = httpcore2.AsyncConnectionPool(ssl_context=ssl.create_default_context(cafile=ca),
            network_backend=ApplicationRoute(host, address))

    async def handle_async_request(self, request):
        response = await self.pool.handle_async_request(httpcore2.Request(method=request.method,
            url=httpcore2.URL(scheme=request.url.raw_scheme, host=request.url.raw_host,
                port=request.url.port, target=request.url.raw_path), headers=request.headers.raw,
            content=request.stream, extensions=request.extensions))
        return httpx2.Response(response.status, headers=response.headers,
            stream=ResponseBody(response.stream), extensions=response.extensions)

    async def aclose(self):
        await self.pool.aclose()


async def typed_objects(client):
    """Disposable-only typed lifecycle through the real installed MCP wire."""
    name = 'robot-regression-' + uuid4().hex
    schema = {'type':'object','required':['name','manufacturer'],'properties':{
        'name':{'type':'string','maxLength':128}, 'manufacturer':{'type':'string'},
        'category':{'type':'string'}, 'source_url':{'type':'string'}},'additionalProperties':False}
    async def call(operation, arguments, error=None, status=None):
        result = await client.call_tool(operation, arguments)
        assert result.is_error == bool(error), 'Installed typed operation error state mismatch'
        if error:
            assert result.content[0].text == error, 'Installed typed validation/conflict code mismatch'
            assert result.meta['c0/error'] == {'code':error,'status':status}, 'Installed typed error metadata mismatch'
        else:
            assert json.loads(result.content[0].text) == result.structured_content, 'Installed typed result representations differ'
            return result.structured_content
    descriptor = {'name':name,'label':'Disposable typed CRUD','schema':schema,'unique_fields':['name']}
    await call('object_types_create', {'data':{**descriptor,'schema':{
        'type':'object','properties':{'name':{'type':'string'}}}}}, 'unique_string_too_long', 422)
    await call('object_types_create', {'data':{**descriptor,'schema':{'type':'array'}}}, 'invalid_schema', 422)
    created = await call('object_types_create', {'data':descriptor})
    assert created['schema']['properties']['name']['maxLength'] == 128, 'Installed unique schema changed'
    assert await call('object_types_get', {'type_name':name}) == created, 'Installed typed schema retrieval mismatch'
    assert created in (await call('object_types_list', {'limit':100}))['types'], 'Installed new type not discoverable'
    await call('object_types_create', {'data':descriptor}, 'object_conflict', 409)
    record = {'name':'Digit 5','manufacturer':'Disposable fixture','source_url':'https://example.invalid/fixture'}
    row = await call('objects_create', {'data':{'type_name':name,'data':record}})
    assert row['revision'] == 1 and row['data'] == record, 'Installed typed create mismatch'
    assert await call('objects_get', {'object_id':row['id']}) == row, 'Installed typed read mismatch'
    query = {'type_name':name,'where':json.dumps({'name':'Digit 5'})}
    assert (await call('objects_list', query))['objects'] == [row], 'Installed typed query mismatch'
    await call('objects_create', {'data':{'type_name':name,'data':record}}, 'object_conflict', 409)
    updated = await call('objects_update', {'object_id':row['id'],
        'data':{'expected_revision':1,'data':{**record,'category':'updated'}}})
    assert updated['revision'] == 2 and updated['data']['category'] == 'updated', 'Installed typed update mismatch'
    await call('objects_update', {'object_id':row['id'],
        'data':{'expected_revision':1,'data':record}}, 'object_conflict', 409)
    for data, error in [({'name':'Missing'},'record_invalid::required'),
            ({**record,'name':42},'record_invalid:name:type'),
            ({**record,'extra':'ignored?'},'record_invalid::additionalProperties')]:
        await call('objects_create', {'data':{'type_name':name,'data':data}}, error, 422)
    assert await call('objects_get', {'object_id':row['id']}) == updated, 'Installed failed write changed record'
    deleted = await call('objects_delete', {'object_id':row['id'],'expected_revision':2})
    assert deleted == {'id':row['id'],'revision':2,'deleted':True}, 'Installed typed delete mismatch'
    await call('objects_get', {'object_id':row['id']}, 'object_not_found', 404)
    assert (await call('objects_list', {'type_name':name}))['objects'] == [], 'Installed typed deletion incomplete'
    # Type definitions and their audit history are immutable; the disposable
    # installation owns their lifecycle. No direct database cleanup is used.


async def check(value):
    origin = value['origin']
    typed_lifecycles = 0
    transport = NodeTransport(urlsplit(origin).hostname, value['address'], value['ca'])
    async with httpx2.AsyncClient(transport=transport, base_url=origin, timeout=20,
            headers={'Authorization':'Bearer ' + value['access_token']}) as http:
        response = await http.get('/api/v1/object-types')
        assert response.status_code == 200, 'Installed scoped REST read failed'
        expected = response.json()
        profile = await http.get('/api/v1/me')
        assert profile.status_code == 200, 'Installed scoped profile read failed'
        role = profile.json()['role']
        metadata = await http.get('/.well-known/oauth-protected-resource/mcp')
        assert metadata.status_code == 200, 'Installed protected-resource metadata unavailable'
        metadata = metadata.json()
        assert metadata['resource'] == origin + '/mcp', 'Installed resource metadata audience mismatch'
        assert metadata['authorization_servers'] == [origin + '/oauth'], 'Installed authorization-server mismatch'
        assert metadata['scopes_supported'] == ['c0:read'], 'Installed initial read scope mismatch'
        authority = await http.get('/.well-known/oauth-authorization-server/oauth')
        assert authority.status_code == 200, 'Installed authorization metadata unavailable'
        authority = authority.json()
        assert authority['issuer'] == origin + '/oauth', 'Installed OAuth issuer mismatch'
        for field, path in [('authorization_endpoint','authorize'), ('token_endpoint','token'),
                ('revocation_endpoint','revoke')]:
            assert authority[field] == origin + '/oauth/' + path, 'Installed OAuth endpoint mismatch'
        assert set(authority['scopes_supported']) == {'c0:read','c0:write','c0:admin'}, 'Installed OAuth scope catalog mismatch'
        for mode in ('auto', 'legacy'):
            # A preceding mode can register an immutable isolated type.
            response = await http.get('/api/v1/object-types')
            assert response.status_code == 200, 'Installed current type discovery failed'
            expected = response.json()
            async with Client(streamable_http_client(origin + '/mcp', http_client=http), mode=mode) as client:
                tools = (await client.list_tools()).tools
                assert 'object_types_list' in {tool.name for tool in tools}, 'Installed MCP read tool missing'
                for tool in tools:
                    schemes = tool.meta.get('securitySchemes') if tool.meta else None
                    assert isinstance(schemes, list) and len(schemes) == 1, 'Installed tool OAuth metadata missing'
                    assert schemes[0]['type'] == 'oauth2' and len(schemes[0]['scopes']) == 1, 'Installed tool OAuth scheme invalid'
                    scope = schemes[0]['scopes'][0]
                    assert scope in {'c0:read','c0:write','c0:admin'}, 'Installed tool OAuth scope invalid'
                    assert scope != 'c0:admin' or role == 'admin', 'Installed Admin tool discovery crossed role'
                    assert scope != 'c0:write' or role in {'editor','admin'}, 'Installed write tool discovery crossed role'
                result = await client.call_tool('object_types_list', {})
                assert not result.is_error and result.structured_content == expected, 'Installed REST/MCP result mismatch'
                if role != 'admin' or 'c0:admin' not in value['scope'].split():
                    denied = await client.call_tool('object_types_create', {'data':{
                        'name':'denied-'+uuid4().hex,'label':'Disposable role boundary','schema':{'type':'object'}}})
                    assert denied.is_error, 'Installed type registration bypassed authorization'
                    if role != 'admin':
                        assert denied.content[0].text == 'permission_denied', 'Installed type role denial mismatch'
                        assert not denied.meta or 'mcp/www_authenticate' not in denied.meta, 'Type role denial requested scope upgrade'
                    else:
                        assert denied.content[0].text == 'insufficient_scope', 'Installed type scope denial mismatch'
                        assert 'scope="c0:admin"' in denied.meta['mcp/www_authenticate'][0], 'Installed type scope upgrade mismatch'
                else:
                    tool = next(t for t in tools if t.name == 'object_types_create')
                    assert 'maxLength <=128' in tool.description, 'Installed type bound guidance missing'
                    if 'c0:write' in value['scope'].split():
                        await typed_objects(client)
                        typed_lifecycles += 1
                if value['scope'] == 'c0:read':
                    denied = await client.call_tool('objects_create', {'data':{'type_name':'absent','data':{}}})
                    assert denied.is_error, 'Read token mutation scope not enforced'
                    if role == 'reader':
                        assert all(tool.annotations.read_only_hint for tool in tools), 'Reader discovered mutation'
                        assert denied.content[0].text == 'permission_denied', 'Installed Reader role not enforced'
                        assert not denied.meta or 'mcp/www_authenticate' not in denied.meta, 'Role denial requested scope upgrade'
                    else:
                        assert 'objects_create' in {tool.name for tool in tools}, 'Role-eligible write tool hidden'
                        assert denied.content[0].text == 'insufficient_scope', 'Missing scope upgrade response'
                        challenge, = denied.meta['mcp/www_authenticate']
                        assert 'error="insufficient_scope"' in challenge and 'error_description="' in challenge, 'Invalid scope upgrade challenge'
                        assert 'scope="c0:write"' in challenge and 'c0:admin' not in challenge, 'Scope upgrade requested excess authority'
                        assert 'resource_metadata="' + origin + '/.well-known/oauth-protected-resource/mcp"' in challenge, 'Scope upgrade metadata route mismatch'
                if 'c0:write' in value['scope'].split():
                    # Disposable-only fixture records; archive through the same
                    # delegated transport after checking the actual write result.
                    key = 'mcp-scope-' + uuid4().hex
                    created = await client.call_tool('wiki_pages_create', {'data':{
                        'slug':key, 'title':'Disposable scope-upgrade proof',
                        'body':'Isolated delegated-write fixture.', 'idempotency_key':key}})
                    assert not created.is_error, 'Installed scoped MCP write failed'
                    page = created.structured_content
                    archived = await client.call_tool('wiki_pages_archive', {'page_id':page['id'],
                        'data':{'expected_revision':page['revision'],'idempotency_key':key + '-archive'}})
                    assert not archived.is_error and archived.structured_content['deleted'], 'Installed scoped fixture archive failed'
                assert str((await client.list_resources()).resources[0].uri) == 'c0://capabilities', 'Installed resource missing'
        guard_body = {'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}
        guard_headers = {'Accept':'application/json, text/event-stream', 'MCP-Protocol-Version':'2025-11-25'}
        response = await http.post('/mcp', json=guard_body, headers=guard_headers)
        assert response.status_code == 200, 'Installed guard positive control failed'
        for tool in response.json()['result']['tools']:
            assert tool['securitySchemes'] == tool['_meta']['securitySchemes'], 'Installed wire OAuth extension lost'
        for label, headers, allowed in [('origin', {'Origin':'https://unapproved.invalid'}, (400,403,421)),
                ('host', {'Host':'unapproved.invalid'}, (400,403,404,421))]:
            # Traefik rejects unknown virtual hosts before the app with 404.
            # Origin still reaches the canonical route and must fail there.
            status = (await http.post('/mcp', json=guard_body, headers={**guard_headers, **headers})).status_code
            assert status in allowed, 'Installed %s guard returned HTTP %d' % (label, status)
    expected_typed = 2 if role == 'admin' and {'c0:read','c0:write','c0:admin'} <= set(value['scope'].split()) else 0
    assert typed_lifecycles == expected_typed, 'Installed typed lifecycle coverage mismatch'
    print('Installed typed object lifecycles completed: %d' % typed_lifecycles)
    print('Installed TLS SDK current/legacy tools, resources, REST parity, scopes and host/origin checks passed')


if __name__ == '__main__':
    try:
        asyncio.run(check(json.load(sys.stdin)))
    except AssertionError as error:
        print('Installed MCP assertion failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except BaseException as error:
        # SDK task groups may contain token/body/URL data in nested errors.
        print('Installed MCP client failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
