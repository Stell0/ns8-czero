# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import os
from uuid import uuid4
import pytest
from httpx import AsyncClient,ASGITransport
from sqlalchemy import text
from test_auth_http import application,ORIGIN
from test_mcp_http import RESOURCE,transport

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


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_reader_rest_and_mcp_use_the_same_explicit_space_for_source_reads(transport,mode,request,tmp_path):
    """A real read-only token sees granted data and is denied in another space."""
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    from czero_core.identity import PermissionDenied,Role
    from czero_core.worker import Worker
    from test_spaces_http import dispose_spaces

    app=transport[0]
    access=app.state.auth.access
    app.state.sources.originals.root=tmp_path/'sources'
    created=[]
    definitions=[]
    def cleanup():
        with access.database.engine.begin() as connection:
            for identifier in definitions:
                connection.execute(text('DELETE FROM c0_automatic_source_items WHERE definition_id=:id'),{'id':identifier})
                connection.execute(text('DELETE FROM c0_source_update_runs WHERE definition_id=:id'),{'id':identifier})
                connection.execute(text('DELETE FROM c0_automatic_sources WHERE id=:id'),{'id':identifier})
        dispose_spaces(access.database,created)
    request.addfinalizer(cleanup)

    async def check():
        app,child,_,_,_,issue,owner_token,member_token=transport
        owner=access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        identity=app.state.auth.oidc.verify_access_token(member_token)
        # The space grant narrows this globally Editor account to Reader.
        with pytest.raises(PermissionDenied):
            access.resolve(identity)
        account=next(row for row in access.list_accounts(owner) if row['username']=='member')
        access.set_role(owner,account['id'],Role.EDITOR)
        account_id=str(account['id'])
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner_token}) as admin:
            for name in ('Granted source reads','Denied source reads'):
                response=await admin.post('/api/v1/spaces',json={
                    'name':name+' '+uuid4().hex,'idempotency_key':uuid4().hex})
                assert response.status_code==201,response.text
                created.append(response.json()['id'])
            selected,other=created
            grant=await admin.put('/api/v1/spaces/'+selected+'/grants/'+account_id,json={
                'role':'reader','expected_revision':0,'idempotency_key':uuid4().hex})
            assert grant.status_code==200,grant.text
            saved=await admin.post('/api/v1/automatic-sources',params={'space_id':selected},json={
                'name':'Synthetic source '+uuid4().hex,'kind':'github',
                'config':{'repositories':['synthetic/example']},'enabled':True,
                'interval_seconds':None,'idempotency_key':uuid4().hex})
            assert saved.status_code==200,saved.text
            definition=saved.json();definitions.append(definition['id'])
            accepted=await admin.post('/api/v1/automatic-sources/'+definition['id']+'/actions',
                params={'space_id':selected},json={'action':'run','expected_revision':1,'idempotency_key':uuid4().hex})
            assert accepted.status_code==200
            run_id=accepted.json()['id']
            ingested=await admin.post('/api/v1/sources/ingest-text',params={'space_id':selected},json={
                'title':'Read-selector fixture '+uuid4().hex,'body':'Synthetic retained source body.',
                'media_type':'text/plain','metadata':{'origin':'transport regression'},
                'idempotency_key':uuid4().hex})
            assert ingested.status_code==202,ingested.text
            Worker(app.state.auth.access.database,app.state.jobs.registry).tick()
            summaries=await admin.get('/api/v1/source-documents',params={'space_id':selected})
            assert summaries.status_code==200,summaries.text
            logical_id=summaries.json()['documents'][0]['id']
            owner_document=await admin.get('/api/v1/source-documents/'+logical_id,params={'space_id':selected})
            assert owner_document.status_code==200,owner_document.text
            expected_body=owner_document.json()['body']

        reader_pair=issue(identity,{'c0:read'})
        reader_headers={'Authorization':'Bearer '+reader_pair.access_token}
        mcp_responses=[]
        async def capture_mcp_response(response):
            if response.request.url.path=='/mcp':
                mcp_responses.append(response)
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),
                    base_url=ORIGIN,headers=reader_headers,
                    event_hooks={'response':[capture_mcp_response]}) as http:
                # REST positive controls with the exact same selected ID.
                space_rest=await http.get('/api/v1/spaces/'+selected)
                definitions_rest=await http.get('/api/v1/automatic-sources',params={'space_id':selected})
                runs_rest=await http.get('/api/v1/automatic-sources/'+definitions[0]+'/runs',
                    params={'space_id':selected})
                document_rest=await http.get('/api/v1/source-documents/'+logical_id,
                    params={'space_id':selected})
                assert space_rest.status_code==200 and space_rest.json()['role']=='reader'
                assert definitions_rest.status_code==200 and any(
                    row['id']==definitions[0] for row in definitions_rest.json()['definitions'])
                assert runs_rest.status_code==200 and [run['id'] for run in runs_rest.json()['runs']]==[run_id]
                assert document_rest.status_code==200 and document_rest.json()['body']==expected_body
                missing_id=str(uuid4())
                missing_rest=await http.get('/api/v1/source-documents/'+missing_id,
                    params={'space_id':selected})
                assert missing_rest.status_code==404
                assert missing_rest.json()=={'detail':'source_not_found'}
                assert missing_rest.headers.get('x-c0-request-id')
                marker='PRIVATE_SYNTHETIC_REVISION_VALUE'
                bad_rest=await http.get('/api/v1/source-documents/'+logical_id,
                    params={'space_id':selected,'revision_id':marker})
                assert bad_rest.status_code==422 and bad_rest.json()=={'detail':'invalid_source_request'}
                assert marker not in bad_rest.text

                async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as sdk:
                    tools={tool.name:tool for tool in (await sdk.list_tools()).tools}
                    positive={
                        'spaces_get':{'space_id':selected},
                        'automatic_sources_list':{'space_id':selected},
                        'automatic_source_runs_list':{'space_id':selected,'identifier':definitions[0]},
                        'source_documents_get':{'space_id':selected,'logical_document_id':logical_id},
                    }
                    for name in positive:
                        assert name in tools
                        assert tools[name].annotations.read_only_hint
                        assert tools[name].meta['securitySchemes']==[{
                            'type':'oauth2','scopes':['c0:read']}]
                    space_mcp=await sdk.call_tool('spaces_get',positive['spaces_get'])
                    definitions_mcp=await sdk.call_tool('automatic_sources_list',positive['automatic_sources_list'])
                    runs_mcp=await sdk.call_tool('automatic_source_runs_list',positive['automatic_source_runs_list'])
                    document_mcp=await sdk.call_tool('source_documents_get',positive['source_documents_get'])
                    assert not any(result.is_error for result in (space_mcp,definitions_mcp,runs_mcp,document_mcp))
                    assert space_mcp.structured_content['id']==selected
                    assert space_mcp.structured_content['role']=='reader'
                    assert any(row['id']==definitions[0] for row in definitions_mcp.structured_content['definitions'])
                    assert runs_mcp.structured_content['runs']==runs_rest.json()['runs']
                    assert document_mcp.structured_content['body']==expected_body
                    missing_mcp=await sdk.call_tool('source_documents_get',{
                        'space_id':selected,'logical_document_id':missing_id})
                    assert missing_mcp.is_error and missing_mcp.content[0].text=='source_not_found'
                    assert missing_mcp.meta['c0/error']=={'code':'source_not_found','status':404}
                    assert missing_mcp.meta['c0/request_id']==mcp_responses[-1].headers['x-c0-request-id']
                    mcp_responses.pop()
                    bad_mcp=await sdk.call_tool('source_documents_get', {
                        'space_id':selected,'logical_document_id':logical_id,'revision_id':marker})
                    assert bad_mcp.is_error and bad_mcp.content[0].text=='invalid_source_request'
                    assert bad_mcp.meta['c0/error']=={'code':'invalid_source_request','status':422}
                    mcp_responses.pop()

                    # Same operation with a different, inaccessible selector must fail
                    # before it can expose the definition/document by its identifier.
                    denied={
                        'spaces_get':{'space_id':other},
                        'automatic_sources_list':{'space_id':other},
                        'automatic_source_runs_list':{'space_id':other,'identifier':definitions[0]},
                        'source_documents_get':{'space_id':other,'logical_document_id':logical_id},
                    }
                    async def assert_mcp_denied(name,arguments):
                        result=await sdk.call_tool(name,arguments)
                        assert result.is_error and result.content[0].text=='permission_denied'
                        assert not result.meta or 'mcp/www_authenticate' not in result.meta
                        assert mcp_responses[-1].headers.get('x-c0-request-id')
                        assert result.meta['c0/request_id']==mcp_responses[-1].headers['x-c0-request-id']
                        mcp_responses.pop()
                    await assert_mcp_denied('spaces_get',denied['spaces_get'])
                    await assert_mcp_denied('automatic_sources_list',denied['automatic_sources_list'])
                    await assert_mcp_denied('automatic_source_runs_list',denied['automatic_source_runs_list'])
                    await assert_mcp_denied('source_documents_get',denied['source_documents_get'])

                for path in (
                    '/api/v1/spaces/'+other,
                    '/api/v1/automatic-sources',
                    '/api/v1/automatic-sources/'+definitions[0]+'/runs',
                    '/api/v1/source-documents/'+logical_id,
                ):
                    params={} if path.startswith('/api/v1/spaces/') else {'space_id':other}
                    denied=await http.get(path,params=params)
                    assert denied.status_code==403,denied.text
                    assert denied.json()=={'detail':'forbidden'}
                    assert denied.headers.get('x-c0-request-id')
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
