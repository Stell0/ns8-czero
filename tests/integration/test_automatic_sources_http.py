# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from uuid import uuid4
import pytest
from httpx import AsyncClient,ASGITransport
from sqlalchemy import text
from test_auth_http import application,ORIGIN

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


def test_rest_and_operation_catalog_share_source_contract(application):
    async def check():
        app,owner,_,_,database,_=application
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
            spaces=(await client.get('/api/v1/spaces')).json()['spaces'];space=next(v['id'] for v in spaces if v['shared'])
            path='/api/v1/automatic-sources?space_id='+space
            draft={'name':'Public documentation','kind':'github','config':{'repositories':['a/b']},'enabled':False,'interval_seconds':86400,'idempotency_key':str(uuid4())}
            result=await client.post(path,json=draft)
            assert result.status_code==200,result.text
            identifier=result.json()['id']
            try:
                assert (await client.post(path,json=draft)).json()==result.json()
                assert len((await client.get(path)).json()['definitions'])==1
                invalid=await client.post(path,json={**draft,'config':{'repositories':['a/b'],'command':'do something'}})
                assert invalid.status_code==422
                assert (await client.post('/api/v1/automatic-sources/'+identifier+'/actions?space_id='+space,json={'action':'pause','expected_revision':9,'idempotency_key':str(uuid4())})).status_code==409
                description=app.state.operation_catalog
                # Real catalogue registration is the MCP exposure boundary.
                assert 'automatic_sources_save' in description.registry._operations
            finally:
                with database.engine.begin() as c:c.execute(text('DELETE FROM c0_automatic_sources WHERE id=:id'),{'id':identifier})
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_real_sdk_source_operations_share_revision_and_replay_contract(application,mode):
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    from test_mcp_http import RESOURCE
    from czero_core.oauth_clients import OAuthClientService
    from czero_core.oauth_grants import pkce_challenge
    import secrets
    async def check():
        app,owner_token,_,_,database,_=application
        identity=app.state.auth.oidc.verify_access_token(owner_token)
        owner=app.state.auth.access.resolve(identity)
        clients=OAuthClientService(app.state.auth.access)
        client=clients.register(owner,'Native source SDK '+uuid4().hex,['https://client.example.test/callback'],scopes=['c0:read','c0:write'])
        cookie=app.state.auth.sessions.create(identity)
        session=app.state.auth.sessions.get(cookie)
        verifier=secrets.token_urlsafe(32);grants=app.state.delegated_grants
        code=grants.issue_code(session,client['client_id'],callback='https://client.example.test/callback',scopes={'c0:read','c0:write'},challenge=pkce_challenge(verifier),resource=RESOURCE)
        pair=grants.exchange_code(code,client['client_id'],callback='https://client.example.test/callback',verifier=verifier,resource=RESOURCE)
        with database.engine.connect() as c:space=str(c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one())
        identifier=None
        try:
            child=app.state.mcp_app
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+pair.access_token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as sdk:
                        draft={'space_id':space,'data':{'name':'SDK definition','kind':'github','config':{'repositories':['synthetic/example']},'enabled':False,'idempotency_key':str(uuid4())}}
                        saved=await sdk.call_tool('automatic_sources_save',draft)
                        assert not saved.is_error
                        identifier=saved.structured_content['id']
                        replay=await sdk.call_tool('automatic_sources_save',draft)
                        assert not replay.is_error and replay.structured_content==saved.structured_content
                        listing=await sdk.call_tool('automatic_sources_list',{'space_id':space})
                        assert not listing.is_error and any(row['id']==identifier for row in listing.structured_content['definitions'])
                        documents=await sdk.call_tool('automatic_source_documents_list',{'space_id':space,'identifier':identifier})
                        assert not documents.is_error and documents.structured_content['documents']==[]
                        stale=await sdk.call_tool('automatic_sources_command',{'space_id':space,'identifier':identifier,'data':{'action':'pause','expected_revision':9,'idempotency_key':str(uuid4())}})
                        assert stale.is_error
        finally:
            with database.engine.begin() as c:
                if identifier:c.execute(text('DELETE FROM c0_automatic_sources WHERE id=:id'),{'id':identifier})
                c.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),{'id':client['client_id']})
    asyncio.run(check())


def test_malformed_source_requests_do_not_echo_private_input(application):
    async def check():
        app,owner,_,_,database,_=application
        with database.engine.connect() as c:space=str(c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one())
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
            marker='PRIVATE_SOURCE_REQUEST_MARKER'
            result=await client.post('/api/v1/automatic-sources?space_id='+space,json={'name':{'private':marker},'kind':'github','config':{'repositories':['a/b']},'idempotency_key':str(uuid4())})
            assert result.status_code==422
            assert result.json()=={'detail':'invalid_automatic_source'} and marker not in result.text
            assert result.headers['Cache-Control']=='no-store'
    asyncio.run(check())
