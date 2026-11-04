# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
import pytest
from sqlalchemy import text
from httpx import ASGITransport, AsyncClient
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from czero_core.api_keys import ApiKeyService
from czero_core.identity import PermissionDenied, Role, TokenRejected
from czero_core.operations import ScopeDenied
from czero_core.spaces import SpaceService
from test_access import access, identity, owner_actor, record_unadmitted, account_named
from test_auth_http import application, ORIGIN
from test_knowledge_http import knowledge_http
from test_mcp_http import transport


def setup(access, **kwargs):
    service, db, _ = access
    owner = owner_actor(access)
    shared = SpaceService(db, service).list(owner)['spaces'][0]['id']
    keys = ApiKeyService(service, client_id='fixture', client_secret='synthetic', resource=ORIGIN+'/mcp', **kwargs)
    return keys, owner, shared


def test_key_is_hashed_fixed_scoped_and_revocable(access):
    keys, owner, shared = setup(access)
    result = keys.create(owner, name='Workflow', scopes={'c0:read'}, space_ids=[shared])
    token = result.pop('key')
    assert token.startswith('c0k_')
    with access[1].engine.connect() as c:
        assert token not in repr(c.execute(text('SELECT * FROM c0_api_keys')).mappings().all())
    principal = keys.verify(token, resource=keys.resource)
    assert principal.scopes == {'c0:read'}
    assert 'key' not in keys.list(owner)[0]
    spaces = SpaceService(access[1], access[0])
    assert len(spaces.list(principal.actor)['spaces']) == 1
    with access[1].engine.connect() as c:
        with pytest.raises(ScopeDenied): spaces.authorize(c, principal.actor, Role.EDITOR, space_id=shared)
    with pytest.raises(PermissionDenied): keys.create(principal.actor, name='Escalate', scopes={'c0:read'}, space_ids=[shared])
    keys.revoke(owner, result['id'])
    with pytest.raises(TokenRejected): keys.verify(token, resource=keys.resource)
    with pytest.raises(PermissionDenied): access[0].authorize(principal.actor, Role.READER)


def test_expiry_and_configuration_binding(access):
    now = [datetime.now(timezone.utc)]
    keys, owner, shared = setup(access, now=lambda:now[0])
    expiring = keys.create(owner,name='Expiring',scopes={'c0:read'},space_ids=[shared],lifetime_days=1)['key']
    permanent = keys.create(owner,name='Permanent',scopes={'c0:read'},space_ids=[shared],lifetime_days=None)['key']
    now[0] += timedelta(days=2)
    with pytest.raises(TokenRejected): keys.verify(expiring,resource=keys.resource)
    assert keys.verify(permanent,resource=keys.resource).expires_at is None
    changed = ApiKeyService(access[0],client_id='fixture',client_secret='replaced',resource=keys.resource)
    with pytest.raises(TokenRejected): changed.verify(permanent,resource=keys.resource)


def test_membership_change_and_regrant_never_revive_keys(access):
    keys, owner, shared = setup(access)
    key = uuid4();record_unadmitted(access[0], key, 'member')
    account = account_named(access[0], owner, 'member')
    access[0].set_role(owner,account['id'],Role.EDITOR)
    member = access[0].resolve(identity(access[0],key,'member'))
    token = keys.create(member,name='Member',scopes={'c0:read','c0:write'},space_ids=[shared])['key']
    access[0].set_role(owner,member.user_id,None)
    access[0].set_role(owner,member.user_id,Role.EDITOR)
    with pytest.raises(TokenRejected): keys.verify(token,resource=keys.resource)


@pytest.mark.parametrize('scopes,spaces,days', [({'c0:admin'},[],90),({'c0:read'},[],90),({'c0:read'},None,0)])
def test_invalid_creation(access,scopes,spaces,days):
    keys,owner,shared=setup(access)
    with pytest.raises(ValueError):keys.create(owner,name='Invalid',scopes=scopes,space_ids=spaces or [],lifetime_days=days)


def test_browser_create_rest_mcp_logout_and_revoke(knowledge_http):
    application = knowledge_http
    async def check():
        app,owner,_,_,db,_ = application
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as browser:
            state=parse_qs(urlsplit((await browser.get('/auth/login')).headers['location']).query)['state'][0]
            await browser.get('/auth/callback',params={'state':state,'code':'unit-only-code'})
            me=(await browser.get('/api/v1/me')).json()
            spaces=(await browser.get('/api/v1/spaces')).json()['spaces']
            shared=spaces[0]['id']
            headers={'Origin':ORIGIN,'X-C0-CSRF':me['csrf_token']}
            payload={'name':'Actions','scopes':['c0:read','c0:write'],'space_ids':[shared],'lifetime_days':None}
            assert (await browser.post('/api/v1/api-keys',json=payload)).status_code==403
            created=await browser.post('/api/v1/api-keys',json=payload,headers=headers)
            assert created.status_code==201,created.text
            data=created.json();bearer={'Authorization':'Bearer '+data['key']}
            assert (await browser.get('/api/v1/me',headers=bearer)).status_code==200
            assert (await browser.get('/api/v1/api-keys',headers=bearer)).status_code==403
            child=app.state.mcp_app
            async with child.router.lifespan_context(child):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,headers=bearer) as http:
                    for mode in ('auto','legacy'):
                        async with Client(streamable_http_client(ORIGIN+'/mcp',http_client=http),mode=mode) as client:
                            tools=(await client.list_tools()).tools
                            assert any(t.name=='wiki_pages_create' for t in tools)
                            assert not any(t.name=='access_list' for t in tools)
                            result=await client.call_tool('get_profile',{})
                            assert not result.is_error and result.structured_content['id']==me['id']
                            page = await client.call_tool('wiki_pages_create', {'space_id':shared, 'data':{'slug':'key-'+uuid4().hex,
                                'title':'Workflow fixture', 'body':'Key-authored body',
                                'idempotency_key':uuid4().hex}})
                            assert not page.is_error
                            readback = await client.call_tool('wiki_pages_get', {'page_id':page.structured_content['id'],'space_id':shared})
                            assert not readback.is_error and 'Key-authored body' in str(readback.structured_content)

            await browser.post('/auth/logout',headers=headers)
            assert (await browser.get('/api/v1/me',headers=bearer)).status_code==200
            # Re-enter through a fresh browser to revoke the independently held key.
            state=parse_qs(urlsplit((await browser.get('/auth/login')).headers['location']).query)['state'][0]
            await browser.get('/auth/callback',params={'state':state,'code':'unit-only-code'})
            headers['X-C0-CSRF']=(await browser.get('/api/v1/me')).json()['csrf_token']
            assert (await browser.delete('/api/v1/api-keys/'+data['id'],headers=headers)).status_code==204
            assert (await browser.get('/api/v1/me',headers=bearer)).status_code==401
    asyncio.run(check())


def test_space_allowlist_precedes_owner_bypass_and_regrant_revokes(access):
    keys, owner, shared = setup(access)
    spaces=SpaceService(access[1],access[0])
    private=spaces.create(owner,name='Private fixture '+uuid4().hex,idempotency_key=uuid4().hex)
    try:
        token=keys.create(owner,name='Shared only',scopes={'c0:read','c0:write'},space_ids=[shared])['key']
        actor=keys.verify(token,resource=keys.resource).actor
        with access[1].engine.connect() as c:
            with pytest.raises(PermissionDenied): spaces.authorize(c,actor,space_id=private['id'])
        assert [s['id'] for s in spaces.list(actor)['spaces']]==[shared]
        other_key=uuid4();record_unadmitted(access[0],other_key,'reader')
        account=account_named(access[0],owner,'reader')
        access[0].set_role(owner,account['id'],Role.READER)
        other=access[0].resolve(identity(access[0],other_key,'reader'))
        mine=keys.create(other,name='Read',scopes={'c0:read'},space_ids=[shared])
        keys.revoke(other,keys.list(owner)[0]['id'])
        assert keys.verify(token,resource=keys.resource)
        with pytest.raises(PermissionDenied): keys.create(other,name='Escalate',scopes={'c0:write'},space_ids=[shared])
        spaces.set_grant(owner,private['id'],other.user_id,Role.READER,expected_revision=0,idempotency_key=uuid4().hex)
        with pytest.raises(TokenRejected):keys.verify(mine['key'],resource=keys.resource)
    finally:
        with access[1].engine.begin() as c:
            c.execute(text('DELETE FROM c0_space_grants WHERE space_id=:id'),{'id':private['id']})
            c.execute(text('DELETE FROM c0_space_receipts WHERE actor_id=:id'),{'id':owner.user_id})
            c.execute(text('DELETE FROM c0_spaces WHERE id=:id'),{'id':private['id']})


def test_revoke_waits_for_captured_authority_transaction(access):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    from czero_core.spaces import hold_authority
    keys,owner,shared=setup(access)
    result=keys.create(owner,name='Concurrent',scopes={'c0:read'},space_ids=[shared])
    actor=keys.verify(result['key'],resource=keys.resource).actor
    started=Event()
    def revoke():
        started.set();keys.revoke(owner,result['id'])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with access[1].engine.begin() as c:
            hold_authority(c)
            access[0].checked_actor(c,actor)
            pending=pool.submit(revoke)
            assert started.wait(3)
            with pytest.raises(TimeoutError):pending.result(timeout=.1)
        pending.result(timeout=3)
    with pytest.raises(PermissionDenied):access[0].authorize(actor,Role.READER)


def test_legacy_oauth_token_with_api_key_prefix_remains_valid(transport):
    import hashlib
    app,child,_,_,pair,_,_,_=transport
    token='c0k_'+'a'*39  # Existing OAuth credentials are exactly 43 characters.
    with app.state.auth.access.database.engine.begin() as c:
        c.execute(text('UPDATE c0_oauth_tokens SET hash=:new WHERE hash=:old'),
            {'new':hashlib.sha256(token.encode()).hexdigest(),
             'old':hashlib.sha256(pair.access_token.encode()).hexdigest()})
    async def check():
        headers={'Authorization':'Bearer '+token}
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers=headers) as rest:
            assert (await rest.get('/api/v1/me')).status_code==200
        async with child.router.lifespan_context(child):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url=ORIGIN,headers=headers) as http:
                async with Client(streamable_http_client(ORIGIN+'/mcp',http_client=http)) as client:
                    assert not (await client.call_tool('get_profile',{})).is_error
    asyncio.run(check())
