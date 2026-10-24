# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real signed browser cookies, PostgreSQL and verified metadata HTTPS."""
import asyncio
import os
from uuid import UUID

import pytest
from sqlalchemy import text

from czero_core.identity import Role
from test_auth_http import application, ORIGIN
from test_cimd_http import cimd_http, certificates, Harness, URL
from test_onboarding_http import browser, signin, headers, parameters
from test_oauth_server_http import issued_pair

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


async def request(user,profile):
    raw,_=parameters(scope='c0:read c0:write')
    assert (await user.get('/oauth/authorize',params=raw)).status_code==302
    assert (await user.post('/oauth/connect/request',json={},headers=headers(profile))).status_code==200


async def member_row(admin):
    value=await admin.get('/api/v1/access/workspace')
    assert value.status_code==200 and value.headers['cache-control']=='no-store'
    return next(a for a in value.json()['accounts'] if a['username']=='member')


def test_browser_approval_decline_disconnect_and_persistent_block_are_separate(cimd_http,monkeypatch,certificates):
    async def check():
        app,owner,registry=cimd_http;registry.access.admit_readers=True
        async with Harness(monkeypatch,certificates) as h:
            app.state.cimd.fetcher=h.fetcher
            async with browser(app) as admin,browser(app) as user:
                adm=await signin(admin);person=await signin(user,code='unit-only-forbidden-code')
                assert person['role']=='reader'
                for path in ('/api/v1/access/workspace','/api/v1/access/accounts/'+adm['id']+'/applications'):
                    assert (await user.get(path)).status_code==403
                    assert (await admin.get(path,headers={'Authorization':'Bearer '+owner})).status_code==403
                await request(user,person)
                account=await member_row(admin)
                assert account['permissions']=={'read':True,'write':False,'manage':False} and not account['blocked']
                apps='/api/v1/access/accounts/'+person['id']+'/applications'
                pending=(await admin.get(apps)).json()['applications'][0]
                assert pending['status']=='needs_approval' and not pending['permissions']['write']
                route='/api/v1/access/requests/'+pending['id']
                assert (await admin.post(route+'/preview')).status_code==403
                assert (await user.post(route+'/preview',headers=headers(person))).status_code==403
                preview=await admin.post(route+'/preview',headers=headers(adm))
                assert preview.status_code==200 and len(h.requests)==1
                value=preview.json()
                body={'metadata_digest':value['metadata_digest'],'allowed_scopes':['c0:read']}
                assert (await admin.post(route+'/approve',json=body)).status_code==403
                assert (await admin.post(route+'/approve',json=body,headers=headers(adm))).status_code==200
                assert len(h.requests)==2 and (await member_row(admin))['role']=='reader'
                assert registry.clients._lookup(URL)['allowed_scopes']==['c0:read']
                assert (await admin.delete(route)).status_code==403
                assert (await admin.delete(route,headers=headers(adm))).status_code==204
                assert (await user.post('/oauth/connect/continue',json={'scopes':['c0:read']},headers=headers(person))).status_code==410
                assert (await admin.delete(route,headers=headers(adm))).status_code==410
                # Two independent explicit consents for the same user/application.
                first=await issued_pair(user,{'client_id':URL},login_code='unit-only-forbidden-code')
                second=await issued_pair(user,{'client_id':URL},login_code='unit-only-forbidden-code')
                rows=(await admin.get(apps)).json()['applications']
                assert len(rows)==2 and all(r['permissions']=={'read':True,'write':False,'manage':False} for r in rows)
                # Unchanged UI save preserves both; stale edits cannot elevate.
                current=await member_row(admin);rolepath='/api/v1/access/accounts/'+person['id']
                unchanged={'role':'reader','expected_revision':current['access_revision']}
                assert (await admin.put(rolepath,json=unchanged,headers=headers(adm))).status_code==204
                assert (await user.get('/api/v1/profile',headers={'Authorization':'Bearer '+first['access_token']})).status_code==200
                from czero_core.oauth_grants import _digest
                with registry.access.database.engine.connect() as c:
                    key=c.execute(text('SELECT grant_id FROM c0_oauth_tokens WHERE hash=:hash'),{'hash':_digest(first['access_token'])}).scalar_one()
                disconnect='/api/v1/access/connections/'+str(key)
                assert (await admin.delete(disconnect)).status_code==403
                assert (await admin.delete(disconnect,headers=headers(adm))).status_code==204
                assert (await user.get('/api/v1/profile',headers={'Authorization':'Bearer '+first['access_token']})).status_code==401
                assert (await user.get('/api/v1/profile',headers={'Authorization':'Bearer '+second['access_token']})).status_code==200
                assert (await member_row(admin))['role']=='reader' and registry.clients._lookup(URL)
                assert (await admin.put(rolepath,json={'role':None,'expected_revision':current['access_revision']},headers=headers(adm))).status_code==204
                blocked=await member_row(admin);assert blocked['blocked'] and blocked['role'] is None
                assert (await admin.put(rolepath,json={'role':'admin','expected_revision':current['access_revision']},headers=headers(adm))).status_code==409
                assert (await user.get('/api/v1/profile',headers={'Authorization':'Bearer '+second['access_token']})).status_code==401
                for _ in range(2):
                    started=await user.get('/auth/login')
                    from urllib.parse import parse_qs,urlsplit
                    state=parse_qs(urlsplit(started.headers['location']).query)['state'][0]
                    assert (await user.get('/auth/callback',params={'state':state,'code':'unit-only-forbidden-code'})).status_code==403
                assert registry.clients._lookup(URL) is not None
                assert (await admin.put(rolepath,json={'role':'reader','expected_revision':blocked['access_revision']},headers=headers(adm))).status_code==204
                await signin(user,code='unit-only-forbidden-code')
                assert (await user.get('/api/v1/profile',headers={'Authorization':'Bearer '+second['access_token']})).status_code==401
                # An approved application still cannot grant protected-space access.
                from czero_core.spaces import SpaceService
                actor=registry.access.resolve(app.state.auth.oidc.verify_access_token(owner))
                spaces=SpaceService(registry.access.database,registry.access)
                protected=spaces.create(actor,'Workspace access isolation',idempotency_key='workspace-http-isolation')
                try:assert (await user.get('/api/v1/spaces/'+str(protected['id']))).status_code==403
                finally:
                    with registry.access.database.engine.begin() as c:
                        c.execute(text('DELETE FROM c0_space_receipts WHERE actor_id=:id'),{'id':actor.user_id})
                        c.execute(text('DELETE FROM c0_spaces WHERE id=:id'),{'id':protected['id']})
    asyncio.run(check())


def test_preview_and_approval_recheck_request_after_metadata_io(cimd_http,monkeypatch,certificates):
    async def check():
        app,_,registry=cimd_http
        async with Harness(monkeypatch,certificates) as h:
            app.state.cimd.fetcher=h.fetcher
            async with browser(app) as admin:
                profile=await signin(admin);await request(admin,profile)
                rows=(await admin.get('/api/v1/access/accounts/'+profile['id']+'/applications')).json()['applications']
                identifier=rows[0]['id'];original=app.state.cimd.preview
                async def expired(actor,url):
                    fetched=await original(actor,url)
                    with registry.access.database.engine.begin() as c:
                        c.execute(text('DELETE FROM c0_client_onboarding WHERE id=:id'),{'id':UUID(identifier)})
                    return fetched
                monkeypatch.setattr(app.state.cimd,'preview',expired)
                result=await admin.post('/api/v1/access/requests/'+identifier+'/preview',headers=headers(profile))
                assert result.status_code==410 and registry.clients._lookup(URL) is None
    asyncio.run(check())


@pytest.mark.parametrize('path,method,body',[
    ('/api/v1/access/workspace?limit=private-canary','GET',None),
    ('/api/v1/access/accounts/private-canary/applications','GET',None),
    ('/api/v1/access/requests/private-canary/preview','POST',None),
    ('/api/v1/access/connections/private-canary','DELETE',None),
    ('/api/v1/access/requests/00000000-0000-4000-8000-000000000001/approve','POST',
     {'metadata_digest':'private-canary','allowed_scopes':['c0:read']}),
])
def test_invalid_access_input_is_static_and_never_reflected(application,path,method,body):
    async def check():
        app,*_=application
        async with browser(app) as admin:
            profile=await signin(admin)
            result=await admin.request(method,path,json=body,headers=headers(profile))
            assert result.status_code==422 and result.json()=={'detail':'invalid_access_request'}
            assert result.headers['cache-control']=='no-store' and 'private-canary' not in result.text
    asyncio.run(check())


def test_legacy_access_ui_keeps_role_management_without_exposing_oauth_or_mcp(application):
    async def check():
        from pathlib import Path
        from czero_app.main import create_app
        app,owner,member,*_=application
        auth=app.state.auth;db=application[4];prefix='/czero/czero900'
        legacy=create_app('czero900',Path(__file__).resolve().parents[2]/'app/static',prefix,db,auth=auth)
        identity=auth.oidc.verify_access_token(owner)
        cookie=auth.sessions.create(identity)
        try:
            auth.access.resolve(auth.oidc.verify_access_token(member))
        except Exception as error:
            from czero_core.identity import PermissionDenied
            assert isinstance(error,PermissionDenied)
        from httpx import AsyncClient,ASGITransport
        async with AsyncClient(transport=ASGITransport(app=legacy),base_url=ORIGIN) as http:
            http.cookies.set('c0_session',cookie,domain='c0.example.test',path=prefix)
            profile=(await http.get(prefix+'/api/v1/me')).json()
            result=await http.get(prefix+'/api/v1/access/workspace')
            assert result.status_code==200 and result.json()['connections_available'] is False
            target=next(a for a in result.json()['accounts'] if a['username']=='member')
            rolepath=prefix+'/api/v1/access/accounts/'+target['id']
            assert (await http.put(rolepath,json={'role':'reader','expected_revision':target['access_revision']},headers=headers(profile))).status_code==204
            assert (await http.get(prefix+'/api/v1/access/accounts/'+target['id']+'/applications')).json()['applications']==[]
            assert (await http.get(prefix+'/oauth/authorize')).status_code==404
            assert (await http.post(prefix+'/mcp',json={})).status_code==404
            assert (await http.get(prefix+'/api/v1/access/workspace?limit=private-canary')).json()=={'detail':'invalid_access_request'}
            response=await http.post(prefix+'/api/v1/access/requests/00000000-0000-4000-8000-000000000001/preview',headers=headers(profile))
            assert response.status_code==409
            current=next(a for a in (await http.get(prefix+'/api/v1/access/workspace')).json()['accounts'] if a['username']=='member')
            assert (await http.put(rolepath,json={'role':None,'expected_revision':current['access_revision']},headers=headers(profile))).status_code==204
            blocked=next(a for a in (await http.get(prefix+'/api/v1/access/workspace')).json()['accounts'] if a['username']=='member')
            assert blocked['blocked'] and blocked['role'] is None
    asyncio.run(check())
