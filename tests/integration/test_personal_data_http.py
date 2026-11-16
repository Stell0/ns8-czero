# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real signed REST and current MCP SDK, with immutable personal owner binding."""
import asyncio
import os
from uuid import UUID,uuid4
import pytest
import httpx2
from httpx import ASGITransport,AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import text
from czero_core.personal_data import PersonalDataService
from test_auth_http import application,ORIGIN
from test_mcp_http import transport,RESOURCE
from test_spaces_http import dispose_spaces

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


@pytest.fixture
def personal_http(transport):
    app,child,grants,client,pair,issue,owner_token,member_token=transport
    access=app.state.auth.access
    access.admit_readers=True
    owner=access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    identity=app.state.auth.oidc.verify_access_token(member_token)
    old_read=issue(identity,{'c0:read'})
    service=PersonalDataService(access.database,access)
    provider=uuid4()
    service.configure(owner,provider_id=provider,enabled=True,services={'webtop':str(uuid4())},expected_generation=0)
    row=service.reconcile_directory(provider_id=provider,entries=[{'directory_id':identity.account_key,'username':identity.username,'active':True}])[0]
    try:yield transport,row,old_read,identity
    finally:
        with access.database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_personal_owners WHERE issuer=:issuer'),{'issuer':access.issuer})
            c.execute(text('DELETE FROM c0_personal_config WHERE issuer=:issuer'),{'issuer':access.issuer})
        dispose_spaces(access.database,[row['space_id']])


def test_personal_reader_rest_crud_denials_and_fresh_write_scope(personal_http):
    async def check():
        transport,row,old,identity=personal_http
        app,_,_,_,_,issue,_,member=transport
        write=issue(identity,{'c0:read','c0:write'})
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                               headers={'Authorization':'Bearer '+write.access_token}) as client:
            listed=(await client.get('/api/v1/spaces')).json()['spaces']
            assert next(s for s in listed if s['id']==row['space_id'])['personal'] is True
            params={'space_id':row['space_id']}
            payload={'slug':'personal','title':'Personal note','body':'Written in my space','idempotency_key':uuid4().hex}
            first=await client.post('/api/v1/wiki/pages/upsert',params=params,json=payload)
            assert first.status_code==200,first.text
            page=first.json()
            assert (await client.get('/api/v1/wiki/pages/'+page['id'],params=params)).json()['content']['body']=='Written in my space'
            edit=await client.put('/api/v1/wiki/pages/'+page['id'],params=params,
                json={'title':'Edited','body':'My correction','expected_revision':page['revision'],'idempotency_key':uuid4().hex})
            assert edit.status_code==200,edit.text
            assert (await client.post('/api/v1/wiki/pages/upsert',json={**payload,'idempotency_key':uuid4().hex})).status_code==403
            assert (await client.post('/api/v1/wiki/pages/upsert',params={'space_id':str(uuid4())},json=payload)).status_code==403
            assert (await client.put('/api/v1/spaces/'+row['space_id']+'/access',json={'readable_by_all':True,'expected_revision':1,'idempotency_key':uuid4().hex})).status_code==403
            assert (await client.get('/api/v1/me')).json()['role']=='reader'
            assert (await client.get('/api/v1/me',params=params)).json()['role']=='editor'
            client.headers['Authorization']='Bearer '+old.access_token
            assert (await client.post('/api/v1/wiki/pages/upsert',params=params,json={**payload,'idempotency_key':uuid4().hex})).status_code==403
    asyncio.run(check())


def test_personal_reader_current_mcp_sdk_scope_and_selection(personal_http):
    async def check():
        transport,row,old,identity=personal_http
        app,child,_,_,_,issue,_,_=transport
        write=issue(identity,{'c0:read','c0:write'})
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                    headers={'Authorization':'Bearer '+write.access_token}) as http:
                async with Client(streamable_http_client(RESOURCE,http_client=http)) as client:
                    tools={t.name for t in (await client.list_tools()).tools}
                    assert 'wiki_pages_upsert' in tools and 'spaces_create' not in tools
                    args={'space_id':row['space_id'],'data':{'slug':'mcp-personal','title':'Personal','body':'My own space','idempotency_key':uuid4().hex}}
                    result=await client.call_tool('wiki_pages_upsert',args)
                    assert not result.is_error,result
                    denied=await client.call_tool('wiki_pages_upsert',{**args,'space_id':None})
                    assert denied.is_error and denied.content[0].text=='permission_denied'
                http.headers['Authorization']='Bearer '+old.access_token
                async with Client(streamable_http_client(RESOURCE,http_client=http)) as client:
                    result=await client.call_tool('wiki_pages_upsert',args)
                    assert result.is_error and result.content[0].text=='insufficient_scope'
    asyncio.run(check())
