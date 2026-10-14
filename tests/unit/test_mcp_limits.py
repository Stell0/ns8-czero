# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from types import SimpleNamespace

import pytest
from starlette.responses import JSONResponse

from czero_app.mcp_transport import MAX_RESPONSE_BYTES, PrivateAccessToken, TransportLimits, _json, create_mcp_app
from czero_core.operations import OperationRejected


def test_sdk_token_representation_hides_raw_bearer():
    token = PrivateAccessToken(token='synthetic-private-bearer', client_id='unit-client', scopes=['c0:read'])
    assert 'synthetic-private-bearer' not in repr(token)


@pytest.mark.parametrize('resource,issuer,error', [
    ('https://c0.example.test/czero/czero900/mcp', 'https://c0.example.test/oauth', 'mcp_requires_hostname_root'),
    ('https://c0.example.test/mcp', 'https://other.example.test/oauth', 'invalid_mcp_issuer'),
    ('https://c0.example.test/mcp', 'https://c0.example.test/oauth?', 'invalid_mcp_issuer'),
])
def test_factory_requires_hostname_root_and_exact_same_origin_issuer(resource, issuer, error):
    with pytest.raises(ValueError, match='^' + error + '$'):
        create_mcp_app(None, SimpleNamespace(resource=resource), issuer_url=issuer)


def test_result_limit_is_byte_bounded_and_does_not_truncate_evidence():
    assert _json({'value':'é'}) == '{"value":"\\u00e9"}'
    with pytest.raises(OperationRejected, match='invalid_operation_request'):
        _json({'value':'x' * MAX_RESPONSE_BYTES})


def test_transport_concurrency_rejects_ninth_without_queueing():
    async def check():
        release, full = asyncio.Event(), asyncio.Event()
        active = [0]
        async def app(scope, receive, send):
            active[0] += 1
            if active[0] == 8:
                full.set()
            await release.wait()
            await JSONResponse({'ok':True})(scope, receive, send)
        limited = TransportLimits(app)
        scope = {'type':'http', 'method':'POST', 'path':'/mcp'}
        async def request():
            messages = []
            async def receive():
                return {'type':'http.request', 'body':b'', 'more_body':False}
            async def send(message):
                messages.append(message)
            await limited(scope, receive, send)
            return messages
        tasks = [asyncio.create_task(request()) for _ in range(8)]
        await asyncio.wait_for(full.wait(), timeout=5)
        rejected = await request()
        assert rejected[0]['status'] == 503
        assert rejected[1]['body'] == b'{"error":"server_busy"}'
        assert (b'cache-control', b'no-store') in rejected[0]['headers']
        release.set()
        assert all(result[0]['status'] == 200 for result in await asyncio.gather(*tasks))
        assert (await request())[0]['status'] == 200
    asyncio.run(check())
