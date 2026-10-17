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


@pytest.mark.parametrize('oversized',[False,True])
def test_sdk_bad_envelope_response_hides_input_and_keeps_bounded_protocol_error(oversized):
    import json
    async def check():
        secret='SYNTHETIC_BAD_RPC_EVIDENCE'
        body=json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32700,
            'message':secret+('x'*1048576 if oversized else '')}}).encode()
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':400,'headers':[
                (b'content-length',str(len(body)).encode()),(b'content-type',b'application/json'),
                (b'x-protocol-guard',b'preserved')]})
            for offset in range(0,len(body),4096):
                await send({'type':'http.response.body','body':body[offset:offset+4096],
                    'more_body':offset+4096<len(body)})
        messages=[]
        async def receive():return {'type':'http.request','body':b''}
        async def send(message):messages.append(message)
        await TransportLimits(app)({'type':'http','method':'POST','path':'/mcp'},receive,send)
        assert len(messages)==2 and messages[0]['status']==400
        result=json.loads(messages[1]['body'])
        assert result=={'jsonrpc':'2.0','id':None,'error':{
            'code':-32600 if oversized else -32700,'message':'invalid_mcp_request'}}
        assert secret.encode() not in messages[1]['body']
        headers=dict(messages[0]['headers'])
        assert headers[b'content-length']==str(len(messages[1]['body'])).encode()
        assert headers[b'cache-control']==b'no-store' and headers[b'x-protocol-guard']==b'preserved'
    asyncio.run(check())


def test_unavailable_after_pending_sdk_error_keeps_service_failure_response():
    from czero_app.mcp_transport import TransportUnavailable
    async def check():
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':400,'headers':[]})
            await send({'type':'http.response.body','body':b'private diagnostic','more_body':True})
            raise TransportUnavailable()
        messages=[]
        async def receive():return {'type':'http.request','body':b''}
        async def send(message):messages.append(message)
        await TransportLimits(app)({'type':'http','method':'POST','path':'/mcp'},receive,send)
        assert len(messages)==2 and messages[0]['status']==503
        assert messages[1]['body']==b'{"error":"service_unavailable"}'
    asyncio.run(check())
