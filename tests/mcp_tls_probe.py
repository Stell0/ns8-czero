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


async def check(value):
    origin = value['origin']
    transport = NodeTransport(urlsplit(origin).hostname, value['address'], value['ca'])
    async with httpx2.AsyncClient(transport=transport, base_url=origin, timeout=20,
            headers={'Authorization':'Bearer ' + value['access_token']}) as http:
        response = await http.get('/api/v1/object-types')
        assert response.status_code == 200, 'Installed scoped REST read failed'
        expected = response.json()
        for mode in ('auto', 'legacy'):
            async with Client(streamable_http_client(origin + '/mcp', http_client=http), mode=mode) as client:
                tools = (await client.list_tools()).tools
                assert 'object_types_list' in {tool.name for tool in tools}, 'Installed MCP read tool missing'
                result = await client.call_tool('object_types_list', {})
                assert not result.is_error and result.structured_content == expected, 'Installed REST/MCP result mismatch'
                if value['scope'] == 'c0:read':
                    assert all(tool.annotations.read_only_hint for tool in tools), 'Read token discovered mutation'
                    assert (await client.call_tool('objects_create', {'data':{'type_name':'absent','data':{}}})).is_error, 'Read token mutated'
                assert str((await client.list_resources()).resources[0].uri) == 'c0://capabilities', 'Installed resource missing'
        guard_body = {'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}
        guard_headers = {'Accept':'application/json, text/event-stream', 'MCP-Protocol-Version':'2025-11-25'}
        assert (await http.post('/mcp', json=guard_body, headers=guard_headers)).status_code == 200, 'Installed guard positive control failed'
        for label, headers, allowed in [('origin', {'Origin':'https://unapproved.invalid'}, (400,403,421)),
                ('host', {'Host':'unapproved.invalid'}, (400,403,404,421))]:
            # Traefik rejects unknown virtual hosts before the app with 404.
            # Origin still reaches the canonical route and must fail there.
            status = (await http.post('/mcp', json=guard_body, headers={**guard_headers, **headers})).status_code
            assert status in allowed, 'Installed %s guard returned HTTP %d' % (label, status)
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
