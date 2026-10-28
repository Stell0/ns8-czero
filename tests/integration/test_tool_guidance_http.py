# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real catalog/wire/authorization checks, separate from model evaluations."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest
from project_contract import PROJECT_OPERATIONS, DOCUMENT_OPERATIONS, TOOL_COUNT

from czero_app.tool_guidance import DESCRIPTIONS
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport, RESOURCE
from test_objects_http import cleanup

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
spec = importlib.util.spec_from_file_location('tool_contract', Path(__file__).parents[1] / 'tool_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def test_complete_m17_validation_and_authority_contract_is_preserved(application):
    app = application[0]
    frozen = json.loads((Path(__file__).parents[1] / 'fixtures/tool_guidance/m17_contract.json').read_text())
    actual = [app.state.operations.definition(name) for name in sorted(app.state.operations._operations)]
    assert len(actual) == TOOL_COUNT
    assert {item['name'] for item in actual} - {item['name'] for item in frozen['operations']} == PROJECT_OPERATIONS | DOCUMENT_OPERATIONS
    original = [item for item in actual if item['name'] not in PROJECT_OPERATIONS | DOCUMENT_OPERATIONS]
    assert len(original) == len(frozen['operations']) == 77
    assert [contract.operation_contract(item) for item in original] == frozen['operations']
    assert set(DESCRIPTIONS) == {item['name'] for item in actual}
    schema = app.openapi()
    assert [item for item in contract.route_contract(schema) if item['operation'] not in PROJECT_OPERATIONS | DOCUMENT_OPERATIONS] == frozen['rest_bindings']
    for methods in schema['paths'].values():
        for route in methods.values():
            if isinstance(route, dict) and 'x-c0-operation' in route:
                metadata = route['x-c0-operation']
                assert route['description'] == app.state.operations.definition(metadata['name'])['description']
                assert set(metadata['annotations']) == {'readOnlyHint','destructiveHint','idempotentHint','openWorldHint'}


@pytest.mark.parametrize('mode', ['auto','legacy'])
def test_all_sdk_wire_capability_and_openapi_hints_match_actual_behavior(transport, mode):
    async def check():
        app, child, _, _, pair, _, owner_token, _ = transport
        expected = {
            'get_profile': (True, False, True, False),
            'wiki_pages_update': (False, True, True, False),
            'objects_create': (False, False, False, False),
            'objects_delete': (False, True, False, False),
            'sources_ingest_text': (False, False, True, False),
            'knowledge_search': (True, False, True, True),
            'oauth_clients_configure': (False, True, False, False),
            'jobs_enqueue': (False, True, True, True),
            'schedules_update': (False, True, False, True),
        }
        keys = ('readOnlyHint','destructiveHint','idempotentHint','openWorldHint')
        wire = []
        async def capture(response):
            await response.aread()
            if not response.content or "json" not in response.headers.get("content-type", ""):
                return
            value = json.loads(response.content)
            wire.extend(value.get('result',{}).get('tools',[]))
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner_token}) as http:
            rest = (await http.get('/agents/capabilities.json')).json()
            rest_by_name = {item['name']:item for item in rest['operations']}
            assert len(rest_by_name) == TOOL_COUNT and rest['guidance']['version'] == 2
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token},
                        event_hooks={'response':[capture]}) as transport_http:
                    async with Client(streamable_http_client(RESOURCE,http_client=transport_http), mode=mode) as client:
                        tools = (await client.list_tools()).tools
                        assert len(tools) == len(wire) == TOOL_COUNT
                        capability = json.loads((await client.read_resource('c0://capabilities')).contents[0].text)
                        assert capability['operations'] == rest['operations']
                        for tool, raw in zip(tools, wire):
                            hints = tool.annotations.model_dump(by_alias=True, exclude_none=True)
                            assert set(hints) == set(keys) and all(type(v) is bool for v in hints.values())
                            item = rest_by_name[tool.name]
                            assert hints == raw['annotations'] == item['annotations']
                            assert hints['readOnlyHint'] is item['read_only']
                            assert tool.description == item['description'] == DESCRIPTIONS[tool.name]
                            schemes = [{'type':'oauth2','scopes':[item['required_scope']]}]
                            assert raw['securitySchemes'] == raw['_meta']['securitySchemes'] == schemes
                            assert bool(tool.meta.get('openai/profile')) == (tool.name == 'get_profile')
                            if tool.name in expected:
                                assert tuple(hints[k] for k in keys) == expected[tool.name]
                            if hints['readOnlyHint']:
                                assert not hints['destructiveHint'] and hints['idempotentHint']
    asyncio.run(check())


@pytest.mark.parametrize('mode', ['auto','legacy'])
def test_guidance_discovery_does_not_add_invocation_scopes(transport, mode):
    async def check():
        app, child, _, _, _, issue, owner_token, _ = transport
        identity = app.state.auth.oidc.verify_access_token(owner_token)
        pair = issue(identity, {'c0:read'})
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+pair.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http), mode=mode) as client:
                    assert 'wiki_pages_create' in {tool.name for tool in (await client.list_tools()).tools}
                    actual = json.loads((await client.read_resource('c0://capabilities')).contents[0].text)
                    assert all(item['required_scope']=='c0:read' and item['annotations']['readOnlyHint'] for item in actual['operations'])
                    assert (await client.call_tool('get_profile', {})).structured_content['id']
                    denied = await client.call_tool('wiki_pages_create', {'data':{'slug':'guidance-denied-'+uuid4().hex,
                        'title':'Denied write','body':'Must not publish','idempotency_key':uuid4().hex}})
                    assert denied.is_error and denied.content[0].text=='insufficient_scope'
                    assert 'scope="c0:write"' in denied.meta['mcp/www_authenticate'][0]
    asyncio.run(check())


def test_durable_replay_and_ordinary_create_have_different_real_effects(knowledge_http):
    async def check():
        app, token, _, _, db, _ = knowledge_http
        name = 'guidance-'+uuid4().hex
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+token}) as http:
            try:
                schema = {'type':'object','properties':{'title':{'type':'string','maxLength':32}},
                    'required':['title'],'additionalProperties':False}
                assert (await http.post('/api/v1/object-types',json={'name':name,'label':'Guidance','schema':schema})).status_code==201
                body = {'type_name':name,'data':{'title':'Same payload'}}
                a = await http.post('/api/v1/objects',json=body)
                b = await http.post('/api/v1/objects',json=body)
                assert a.status_code==b.status_code==201 and a.json()['id']!=b.json()['id']
                page = {'slug':name,'title':'Replay','body':'One immutable revision','idempotency_key':name}
                a = await http.post('/api/v1/wiki/pages',json=page)
                b = await http.post('/api/v1/wiki/pages',json=page)
                assert a.status_code==b.status_code==201 and a.json()==b.json()
                assert (await http.get('/api/v1/wiki/pages/'+a.json()['id'])).json()['revision']==1
            finally:
                cleanup(db,[name])
    asyncio.run(check())
