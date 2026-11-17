# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
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
            schema=app.openapi()
            response=schema['paths']['/api/v1/automatic-sources']['post']['responses']['422']['content']['application/json']['schema']
            assert response['$ref'].endswith('/SourceErrorBody')
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
                        tools=await sdk.list_tools()
                        definition=next(tool for tool in tools.tools if tool.name=='automatic_sources_save')
                        assert 'owner/repository_name' in json.dumps(definition.input_schema)
                        draft={'space_id':space,'data':{'name':'SDK definition','kind':'github','config':{'repositories':['synthetic/example']},'enabled':False,'idempotency_key':str(uuid4())}}
                        invalid=await sdk.call_tool('automatic_sources_save',{**draft,'data':{**draft['data'],'config':{'repositories':['synthetic']}}})
                        assert invalid.is_error
                        explanation=json.loads(invalid.content[0].text)
                        assert explanation['detail']=='invalid_automatic_source'
                        assert explanation['reason']=='invalid_github_repositories'
                        assert explanation['field']=='config.repositories'
                        assert 'owner/repository_name' in explanation['message']
                        assert invalid.meta['c0/error']['status']==422
                        assert invalid.meta['c0/error']['reason']=='invalid_github_repositories'
                        malformed=await sdk.call_tool('automatic_sources_save',{**draft,'data':{**draft['data'],'name':{'private':'PRIVATE_REQUEST_MARKER'}}})
                        assert malformed.is_error and malformed.meta['c0/error']['status']==422
                        assert json.loads(malformed.content[0].text)['message']
                        assert 'PRIVATE_REQUEST_MARKER' not in malformed.content[0].text
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
                        assert stale.meta['c0/error']['status']==409
                        assert json.loads(stale.content[0].text)['reason']=='automatic_source_conflict'
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
            assert result.json()['detail']=='invalid_automatic_source' and marker not in result.text
            assert result.json()['reason']=='invalid_source_name'
            assert result.json()['field']=='name'
            assert '1–256' in result.json()['message']
            assert result.headers['Cache-Control']=='no-store'
    asyncio.run(check())


@pytest.mark.parametrize('config,reason,field',[
    ({'repositories':['synthetic'],'include':['issues','pull_requests','releases'],'paths':['README*','docs/*'],'exclude':[],'ref':'HEAD'},'invalid_github_repositories','config.repositories'),
    ({'repositories':['synthetic/docs','synthetic/docs']},'invalid_github_repositories','config.repositories'),
    ({'repositories':['synthetic/docs'],'include':[]},'invalid_github_selection','config.include'),
    ({'repositories':['synthetic/docs'],'ref':'../main'},'invalid_github_ref','config.ref'),
    ({'repositories':['synthetic/docs'],'max_items':21},'invalid_source_limit','config'),
    ({'repositories':['synthetic/docs'],'github_token':'PRIVATE_CREDENTIAL_MARKER'},'invalid_source_configuration','config'),
])
def test_source_validation_identifies_safe_reason_and_field(application,config,reason,field):
    async def check():
        app,owner,_,_,database,_=application
        with database.engine.connect() as c:space=str(c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one())
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
            for endpoint in ('','/preview'):
                draft={'kind':'github','config':config}
                if not endpoint:draft.update(name='Public documentation',idempotency_key=str(uuid4()))
                result=await client.post('/api/v1/automatic-sources'+endpoint,params={'space_id':space},json=draft)
                assert result.status_code==422,result.text
                value=result.json()
                assert value['detail']=='invalid_automatic_source' and value['reason']==reason and value['field']==field
                assert value['message'] and 'PRIVATE_CREDENTIAL_MARKER' not in result.text
                assert result.headers['Cache-Control']=='no-store'
    asyncio.run(check())


def test_unrecognized_collector_error_never_exposes_exception_text(application,monkeypatch):
    from czero_core import source_collectors
    def fail(*args,**kwargs):raise RuntimeError('PRIVATE_REMOTE_BODY_MARKER')
    monkeypatch.setattr(source_collectors,'collect',fail)
    async def check():
        app,owner,_,_,database,_=application
        with database.engine.connect() as c:space=str(c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one())
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as client:
            result=await client.post('/api/v1/automatic-sources/preview',params={'space_id':space},json={'kind':'github','config':{'repositories':['synthetic/docs']}})
            assert result.status_code==422
            assert result.json()['reason']=='invalid_automatic_source'
            assert result.json()['message'] and 'PRIVATE_REMOTE_BODY_MARKER' not in result.text
    asyncio.run(check())


def test_source_diagnostics_do_not_replace_role_or_space_denials(application):
    async def check():
        app,owner,member,_,database,_=application
        with database.engine.connect() as c:space=str(c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one())
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+member}) as client:
            assert (await client.get('/api/v1/me')).status_code==403
            client.headers['Authorization']='Bearer '+owner
            account=next(row for row in (await client.get('/api/v1/access/accounts')).json()['accounts'] if row['username']=='member')
            assert (await client.put('/api/v1/access/accounts/'+account['id'],json={'role':'reader'})).status_code==204
            client.headers['Authorization']='Bearer '+member
            for selected in (space,str(uuid4())):
                for endpoint in ('','/preview'):
                    draft={'kind':'github','config':{'repositories':['synthetic']}}
                    if not endpoint:draft.update(name='Public documentation',idempotency_key=str(uuid4()))
                    result=await client.post('/api/v1/automatic-sources'+endpoint,params={'space_id':selected},json=draft)
                    assert result.status_code==403,result.text
                    assert 'invalid_github_repositories' not in result.text and 'reason' not in result.json()
    asyncio.run(check())
