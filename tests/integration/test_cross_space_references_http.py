# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual signed REST and current/legacy SDK authorization contracts."""
import asyncio
import json
import os
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx2
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import pytest

from czero_core.identity import Role, PermissionDenied
from czero_core.spaces import SpaceService
from czero_core.objects import ObjectService
from czero_core.wiki import WikiService
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport, RESOURCE
from test_spaces_http import dispose_spaces

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
PATH = '/api/v1/cross-space-references'


@pytest.fixture(params=[False, True], ids=['protected-documentation','shared-documentation'])
def reference_http(transport, request):
    app, _, _, _, _, _, owner_token, member_token = transport
    acl = app.state.auth.access
    owner = acl.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    spaces = SpaceService(acl.database, acl)
    source_space = spaces.create(owner, 'Support '+uuid4().hex, idempotency_key=uuid4().hex)['id']
    with acl.database.engine.connect() as c:
        shared = str(spaces.shared_id(c))
    target_space = (shared if request.param else
                    spaces.create(owner, 'Documentation '+uuid4().hex, idempotency_key=uuid4().hex)['id'])
    objects = ObjectService(acl.database, acl)
    type_name = 'ticket-'+uuid4().hex
    objects.register_type(owner, type_name, 'Ticket', {'type':'object','properties':{'private':{'type':'string','maxLength':64}}}, [])
    source = objects.in_space(source_space).create(owner, type_name, {'private':'synthetic ticket'})
    wiki = WikiService(acl.database, acl).in_space(target_space)
    target = wiki.create_page(owner, 'guide-'+uuid4().hex, 'SIP guide', 'Synthetic troubleshooting procedure.', idempotency_key=uuid4().hex)
    data = {'source': {'kind':'object','id':str(source['id']),'type_name':type_name},
            'target': {'kind':'page','id':target['id'],'space_id':target_space},
            'idempotency_key':uuid4().hex}
    yield transport, owner, source_space, target_space, data
    dispose_spaces(acl.database, [source_space] + ([] if request.param else [target_space]), [type_name])


def list_args(source_space, target_space, data):
    return {'space_id':source_space, 'source_kind':'object', 'source_id':data['source']['id'],
            'source_type_name':data['source']['type_name'], 'target_space_ids':[target_space]}


def test_rest_reader_scope_errors_replay_and_independent_follow(reference_http):
    async def check():
        fixture, owner, source, target, data = reference_http
        app, _, _, _, _, issue, owner_token, member_token = fixture
        acl, spaces = app.state.auth.access, app.state.spaces
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                               headers={'Authorization':'Bearer '+owner_token}) as rest:
            native = app.state.auth.oidc.verify_access_token(member_token)
            with pytest.raises(PermissionDenied): acl.resolve(native)
            member = next(a for a in acl.list_accounts(owner) if a['username']=='member')
            acl.set_role(owner, member['id'], Role.EDITOR)
            spaces.set_grant(owner, source, member['id'], Role.EDITOR, expected_revision=0, idempotency_key=uuid4().hex)
            with acl.database.engine.connect() as c:
                shared = str(spaces.shared_id(c)) == target
            if not shared:
                spaces.set_grant(owner, target, member['id'], Role.READER, expected_revision=0, idempotency_key=uuid4().hex)
            native = app.state.auth.oidc.verify_access_token(member_token)
            pair = issue(native, {'c0:read','c0:write'})
            rest.headers['Authorization']='Bearer '+pair.access_token
            created = await rest.post(PATH, params={'space_id':source}, json=data)
            assert created.status_code == 200, created.text
            ack = created.json()
            assert (await rest.post(PATH, params={'space_id':source}, json=data)).json() == ack
            listed = await rest.get(PATH, params=list_args(source,target,data))
            assert listed.status_code == 200 and listed.json()['next_after'] is None
            assert listed.json()['references'][0]['id'] == ack['reference_id']
            assert (await rest.get('/api/v1/wiki/pages/'+data['target']['id'],params={'space_id':target})).json()['content']['body']=='Synthetic troubleshooting procedure.'
            # Source Editor/target Reader cannot edit the target.
            if not shared:
                edit = await rest.post('/api/v1/wiki/pages/upsert',params={'space_id':target},json={
                    'slug':'forbidden','title':'Forbidden','body':'Forbidden','idempotency_key':uuid4().hex})
                assert edit.status_code == 403
            for scopes in ({'c0:read'}, {'c0:write'}):
                scoped = issue(native, scopes)
                rest.headers['Authorization']='Bearer '+scoped.access_token
                denied = await rest.post(PATH,params={'space_id':source},json=data)
                assert denied.status_code == 403 and denied.headers['cache-control']=='no-store'
            rest.headers['Authorization']='Bearer '+owner_token
            # All invalid targets have one sanitized response, without IDs or labels.
            hidden = await rest.post(PATH,params={'space_id':source},json={**data,
                'target':{**data['target'],'id':str(uuid4())},'idempotency_key':uuid4().hex})
            assert hidden.status_code == 404 and hidden.json()=={'detail':'reference_target_unavailable'}
            for params, body in [({},data), ({'space_id':source},{**data,'extra':'private'}),
                ({'space_id':source},{**data,'source':{**data['source'],'type_name':None}})]:
                invalid=await rest.post(PATH,params=params,json=body)
                assert invalid.status_code==422 and invalid.json()=={'detail':'invalid_reference_request'}
                assert invalid.headers['cache-control']=='no-store'
            assert (await rest.get(PATH,params={**list_args(source,target,data),'target_space_ids':[target]*11})).status_code==422
            # Blind deletes have byte-identical empty responses.
            for reference_id in (str(uuid4()), ack['reference_id'], ack['reference_id']):
                deleted=await rest.request('DELETE',PATH,params={'space_id':source},json={
                    'source':data['source'],'reference_id':reference_id,'idempotency_key':uuid4().hex})
                assert deleted.status_code==204 and deleted.content==b'' and deleted.headers['cache-control']=='no-store'
            rest.headers['Authorization']='Bearer '+pair.access_token
            assert (await rest.post(PATH,params={'space_id':source},json=data)).json()==ack
            assert (await rest.get(PATH,params=list_args(source,target,data))).json()['references']==[]
    asyncio.run(check())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_sdk_both_scopes_security_metadata_errors_and_blind_delete(reference_http, mode):
    async def check():
        fixture, owner, source, target, data = reference_http
        app, child, _, _, pair, issue, owner_token, _ = fixture
        native=app.state.auth.oidc.verify_access_token(owner_token)
        async with child.router.lifespan_context(child):
            for scopes in ({'c0:read','c0:write'}, {'c0:write'}, {'c0:read'}):
                token=issue(native,scopes).access_token
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,
                        headers={'Authorization':'Bearer '+token}) as http:
                    async with Client(streamable_http_client(RESOURCE,http_client=http),mode=mode) as client:
                        tools={tool.name:tool for tool in (await client.list_tools()).tools}
                        assert tools['cross_space_ref_create'].meta['securitySchemes']==[
                            {'type':'oauth2','scopes':['c0:write','c0:read']}]
                        result=await client.call_tool('cross_space_ref_create',{'space_id':source,'data':data})
                        if scopes != {'c0:read','c0:write'}:
                            assert result.is_error and result.meta['c0/error']=={'code':'insufficient_scope','status':403}
                            continue
                        assert not result.is_error
                        ack=result.structured_content
                        listed=await client.call_tool('cross_space_refs_list',list_args(source,target,data))
                        assert not listed.is_error and listed.structured_content['references'][0]['id']==ack['reference_id']
                        missing=await client.call_tool('cross_space_ref_create',{'space_id':source,'data':{**data,
                            'target':{**data['target'],'id':str(uuid4())},'idempotency_key':uuid4().hex}})
                        assert missing.is_error and missing.meta['c0/error']=={'code':'reference_target_unavailable','status':404}
                        invalid=await client.call_tool('cross_space_refs_list',{**list_args(source,target,data),'limit':0})
                        assert invalid.is_error and invalid.meta['c0/error']=={'code':'invalid_reference_request','status':422}
                        deleted=await client.call_tool('cross_space_ref_delete',{'space_id':source,'data':{
                            'source':data['source'],'reference_id':ack['reference_id'],'idempotency_key':uuid4().hex}})
                        assert not deleted.is_error and json.loads(deleted.content[0].text) is None
    asyncio.run(check())


def test_browser_mutations_keep_csrf(reference_http):
    async def check():
        fixture, _, source, _, data=reference_http
        app=fixture[0]
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as browser:
            state=parse_qs(urlsplit((await browser.get('/auth/login')).headers['location']).query)['state'][0]
            await browser.get('/auth/callback',params={'state':state,'code':'unit-only-code'})
            csrf=(await browser.get('/api/v1/me')).json()['csrf_token']
            denied=await browser.post(PATH,params={'space_id':source},json=data)
            assert denied.status_code==403
            allowed=await browser.post(PATH,params={'space_id':source},json=data,
                headers={'Origin':ORIGIN,'X-C0-CSRF':csrf})
            assert allowed.status_code==200
    asyncio.run(check())


def test_oauth_revocation_regrant_and_blind_delete(reference_http):
    async def check():
        fixture, owner, source, target, data = reference_http
        app, _, _, _, _, issue, _, member_token = fixture
        access, spaces = app.state.auth.access, app.state.spaces
        with access.database.engine.connect() as c:
            if str(spaces.shared_id(c)) == target:
                # Shared access cannot be independently revoked by a protected grant.
                return
        native=app.state.auth.oidc.verify_access_token(member_token)
        with pytest.raises(PermissionDenied): access.resolve(native)
        member=next(a for a in access.list_accounts(owner) if a['username']=='member')
        access.set_role(owner,member['id'],Role.EDITOR)
        for space,role in ((source,Role.EDITOR),(target,Role.READER)):
            spaces.set_grant(owner,space,member['id'],role,expected_revision=0,idempotency_key=uuid4().hex)
        pair=issue(native,{'c0:read','c0:write'})
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+pair.access_token}) as rest:
            ack=(await rest.post(PATH,params={'space_id':source},json=data)).json()
            assert 'reference_id' in ack
            spaces.set_grant(owner,target,member['id'],None,expected_revision=1,idempotency_key=uuid4().hex)
            assert (await rest.get(PATH,params=list_args(source,target,data))).status_code==401
            rest.headers['Authorization']='Bearer '+issue(native,{'c0:read','c0:write'}).access_token
            assert (await rest.get(PATH,params=list_args(source,target,data))).json()=={'references':[],'next_after':None}
            hidden=await rest.post(PATH,params={'space_id':source},json={**data,'idempotency_key':uuid4().hex})
            missing=await rest.post(PATH,params={'space_id':source},json={**data,'idempotency_key':uuid4().hex,
                'target':{**data['target'],'id':str(uuid4())}})
            assert hidden.status_code==missing.status_code==404
            assert hidden.content==missing.content==b'{"detail":"reference_target_unavailable"}'
            assert hidden.headers['cache-control']==missing.headers['cache-control']=='no-store'
            deleted=await rest.request('DELETE',PATH,params={'space_id':source},json={
                'source':data['source'],'reference_id':ack['reference_id'],'idempotency_key':uuid4().hex})
            assert deleted.status_code==204 and deleted.content==b''
            spaces.set_grant(owner,target,member['id'],Role.READER,expected_revision=2,idempotency_key=uuid4().hex)
            assert (await rest.get(PATH,params=list_args(source,target,data))).status_code==401
            rest.headers['Authorization']='Bearer '+issue(native,{'c0:read','c0:write'}).access_token
            assert (await rest.get(PATH,params=list_args(source,target,data))).json()['references']==[]
            assert (await rest.post(PATH,params={'space_id':source},json=data)).json()==ack
            assert (await rest.get(PATH,params=list_args(source,target,data))).json()['references']==[]
    asyncio.run(check())
