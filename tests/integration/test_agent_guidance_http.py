# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent signed SDK sessions exercise the installed guidance workflow."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path

import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest

from czero_core.worker import Worker
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_spaces_http import space_http, create_space
from test_mcp_http import transport, RESOURCE
from test_bundle_http import bundle_http

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def native_probe():
    path=Path(__file__).parents[1]/'mcp_tls_probe.py'
    spec=importlib.util.spec_from_file_location('am6_installed_guided_workflow',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('modes',[('auto','legacy'),('legacy','auto')])
def test_independent_sdk_grants_read_evidence_update_search_and_reuse(bundle_http, modes):
    async def check():
        fixture, spaces, delegated = bundle_http
        app, child, grants, _, pair, token, owner_token, _ = delegated
        identity=app.state.auth.oidc.verify_access_token(owner_token)
        second=token(identity,{'c0:read','c0:write','c0:admin'})
        assert second.access_token != pair.access_token
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner_token}) as rest:
            private=await create_space(rest,spaces)
        probe=native_probe();state=None
        async with child.router.lifespan_context(child):
            for mode, credential in zip(modes,(pair,second)):
                # Distinct HTTP clients and grant credentials; no shared SDK
                # session/cache can substitute for persisted evidence/history.
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+credential.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        state=await probe.agent_workflow(client,private['id'],state,
                            extraction=lambda:Worker(fixture[4],app.state.jobs.registry).tick())
            assert state['current']['revision']==3
            assert 'independently reused' in state['current']['content']['body']
            assert grants.verify(pair.access_token,resource=RESOURCE).actor.user_id==grants.verify(second.access_token,resource=RESOURCE).actor.user_id
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_http_openapi_and_sdk_guidance_match_actual_scope_capabilities(transport, mode):
    async def check():
        app, child, _, _, _, issue, owner_token, _ = transport
        identity=app.state.auth.oidc.verify_access_token(owner_token)
        pair=issue(identity,{'c0:read'})
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as rest:
            public=await rest.get('/agents/capabilities.json')
            assert public.status_code==200 and public.json()['guidance']['workflows']==[]
            assert public.headers['cache-control']=='no-store'
            schema=(await rest.get('/openapi.json')).json()
            assert len(schema['x-c0-agent-guidance']['workflows'])==6
            rest.headers['Authorization']='Bearer '+pair.access_token
            actual=(await rest.get('/agents/capabilities.json')).json()
            assert {flow['id'] for flow in actual['guidance']['workflows']}=={'research','structured-research'}
            assert all(item['read_only'] for item in actual['operations'])
            wire=[]
            async def observe(response):
                await response.aread()
                if response.content: wire.append(json.loads(response.content))
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+pair.access_token},event_hooks={'response':[observe]}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        assert any('Read c0://capabilities' in message.get('result',{}).get('instructions','') for message in wire)
                        resource=json.loads((await client.read_resource('c0://capabilities')).contents[0].text)
                        assert resource['guidance']==actual['guidance']
                        # Role-eligible tool scan may include upgrades, but that
                        # does not authorize write workflows under actual scopes.
                        assert 'wiki_pages_upsert' in {tool.name for tool in (await client.list_tools()).tools}
                        assert not any(flow['id']=='update' for flow in resource['guidance']['workflows'])
    asyncio.run(check())
