# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""First-party intents, signed offline issuance and successful-browser-only renewal."""
import asyncio
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text

from test_session_renewal_http import renewing_app, login, refresh
from test_auth_http import ORIGIN, application
from czero_core.sessions import REMEMBER_SECONDS


class SignInForm(HTMLParser):
    def __init__(self):
        super().__init__();self.intent=None;self.remember=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='input' and attrs.get('name')=='intent':self.intent=attrs['value']
        if tag=='input' and attrs.get('name')=='remember':self.remember=attrs


async def form(client):
    page=await client.get('/auth/sign-in?remember=yes')
    assert page.status_code==200 and page.headers['cache-control']=='no-store'
    assert page.headers['referrer-policy']=='no-referrer'
    parsed=SignInForm();parsed.feed(page.text)
    assert parsed.intent and parsed.remember is not None and 'checked' not in parsed.remember
    assert all(flag in page.headers['set-cookie'] for flag in ('Secure','HttpOnly','SameSite=lax','Max-Age=300'))
    return {'intent':parsed.intent,'return_to':''}


async def remembered_login(client,state):
    data=await form(client)
    started=await client.post('/auth/sign-in',data={**data,'remember':'yes'},headers={'Origin':ORIGIN})
    assert started.status_code==302
    fields=parse_qs(urlsplit(started.headers['location']).query)
    assert fields['scope']==['openid profile offline_access'] and 'consent' in fields['prompt'][0]
    state['nonce']=fields['nonce'][0];state['offline']=True
    completed=await client.get('/auth/callback',params={'code':'private-code','state':fields['state'][0]})
    assert completed.status_code==302
    assert all(flag in completed.headers['set-cookie'] for flag in ('Secure','HttpOnly','SameSite=lax','Max-Age=604800'))
    return (await client.get('/api/v1/me')).json()


def test_rolling_cookie_survives_restart_hour_day_and_expires_at_seven_days(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            profile=await remembered_login(client,state)
            assert profile['browser_session']=={'remembered':True,'idle_seconds':604800}
            for elapsed in (3601,28801,6*86400):
                clock[0]+=elapsed
                result=await client.get('/api/v1/me')
                assert result.status_code==200 and 'Max-Age=604800' in result.headers['set-cookie']
            cookies=client.cookies
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,cookies=cookies) as restarted:
            clock[0]+=REMEMBER_SECONDS-1
            assert (await restarted.get('/api/v1/me')).status_code==200
            clock[0]+=REMEMBER_SECONDS
            expired=await restarted.get('/api/v1/me')
            assert expired.status_code==401 and 'set-cookie' not in expired.headers
    asyncio.run(check())


def test_ordinary_form_and_compatibility_entry_cannot_be_upgraded_by_query(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            data=await form(client)
            started=await client.post('/auth/sign-in?remember=yes',data=data,headers={'Origin':ORIGIN})
            fields=parse_qs(urlsplit(started.headers['location']).query)
            assert fields['scope']==['openid profile']
            state['nonce']=fields['nonce'][0]
            completed=await client.get('/auth/callback',params={'code':'private-code','state':fields['state'][0]})
            assert completed.status_code==302 and 'Max-Age=28800' in completed.headers['set-cookie']
            assert (await client.get('/api/v1/me')).json()['browser_session']['remembered'] is False
            clock[0]+=3600
            assert (await client.get('/api/v1/me')).status_code==401
            started=await client.get('/auth/login?remember=yes')
            assert parse_qs(urlsplit(started.headers['location']).query)['scope']==['openid profile']
    asyncio.run(check())


def test_intent_origin_binding_replay_duplicates_size_and_expiry(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            data=await form(client)
            for origin in (None,'https://attacker.example.test'):
                result=await client.post('/auth/sign-in',data={**data,'remember':'yes'},headers={'Origin':origin} if origin else {})
                assert result.status_code==403
            async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as other:
                assert (await other.post('/auth/sign-in',data=data,headers={'Origin':ORIGIN})).status_code==400
            headers={'Origin':ORIGIN,'Content-Type':'application/x-www-form-urlencoded'}
            for body in ('intent='+data['intent']+'&remember=yes&remember=yes','intent='+data['intent']+'&unknown=yes','intent='+'x'*16384):
                assert (await client.post('/auth/sign-in',content=body,headers=headers)).status_code==400
            assert (await client.post('/auth/sign-in',data=data,headers={'Origin':ORIGIN})).status_code==302
            assert (await client.post('/auth/sign-in',data=data,headers={'Origin':ORIGIN})).status_code==400
            data=await form(client);clock[0]+=300
            assert (await client.post('/auth/sign-in',data=data,headers={'Origin':ORIGIN})).status_code==400
    asyncio.run(check())


@pytest.mark.parametrize('failure',['scope','provider','account','code','refresh'])
def test_offline_failure_explains_ordinary_signin_and_never_sets_remembered_cookie(renewing_app,failure):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            data=await form(client)
            started=await client.post('/auth/sign-in',data={**data,'remember':'yes'},headers={'Origin':ORIGIN})
            fields=parse_qs(urlsplit(started.headers['location']).query);state['nonce']=fields['nonce'][0];state['offline']=True
            if failure=='scope':state['offline_scope']='openid profile'
            elif failure=='provider':state['status']=503
            elif failure=='refresh':state['omit_refresh']=True
            elif failure=='code':pass
            else:state['nonce']='wrong-nonce'
            response=await client.get('/auth/callback',params={'code':'' if failure=='code' else 'private-code','state':fields['state'][0]})
            assert response.status_code==403 and 'ordinary sign-in' in response.text
            assert 'Max-Age=604800' not in response.headers.get('set-cookie','')
            assert (await client.get('/api/v1/me')).status_code==401
            assert (await client.get('/auth/callback',params={'code':'private-code','state':fields['state'][0]})).status_code==400
    asyncio.run(check())


def test_failed_public_bearer_and_mcp_requests_do_not_renew_browser(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            profile=await remembered_login(client,state);clock[0]+=86400
            for path,headers in (('/',{}),('/api/v1/auth/status',{}),('/api/v1/me',{'Authorization':'Bearer invalid'}),('/mcp',{})):
                response=await client.get(path,headers=headers)
                assert 'c0_session=' not in response.headers.get('set-cookie','')
            failed=await client.post('/api/v1/wiki/pages',json={})
            assert failed.status_code>=400 and 'set-cookie' not in failed.headers
            response=await client.get('/api/v1/me')
            assert response.status_code==200 and 'Max-Age=604800' in response.headers['set-cookie']
            logout=await client.post('/auth/logout',headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            assert logout.status_code==200 and 'Max-Age=0' in logout.headers['set-cookie']
    asyncio.run(check())


def test_background_consent_preserves_remembered_browser_and_profile_isolation(renewing_app):
    async def check():
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            await remembered_login(client,state)
            # Existing helper begins ordinary login; stage the actual background flow here instead.
            from test_oauth_server_http import authorize,CALLBACK,RESOURCE
            verifier,_=await authorize(client,saved,scope='c0:read')
            profile=(await client.get('/api/v1/me')).json()
            result=await client.post('/oauth/consent/background',json={'scopes':['c0:read']},headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            assert result.status_code==200
            started=await client.get('/auth/login');fields=parse_qs(urlsplit(started.headers['location']).query)
            assert 'consent' in fields['prompt'][0]
            state['nonce']=fields['nonce'][0]
            completed=await client.get('/auth/callback',params={'code':'private-code','state':fields['state'][0]})
            assert completed.status_code==302 and 'Max-Age=604800' in completed.headers['set-cookie']
            profile=(await client.get('/api/v1/me')).json();assert profile['browser_session']['remembered']
            accepted=await client.post('/oauth/consent',json={'approve':True,'scopes':['c0:read'],'persistent':True},headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            assert accepted.status_code==200
            code=parse_qs(urlsplit(accepted.json()['redirect_uri']).query)['code'][0]
            pair=(await client.post('/oauth/token',data={'grant_type':'authorization_code','client_id':saved['client_id'],'code':code,'redirect_uri':CALLBACK,'code_verifier':verifier,'resource':RESOURCE})).json()
            delegated=await client.get('/api/v1/me',headers={'Authorization':'Bearer '+pair['access_token']})
            assert delegated.status_code==200 and 'browser_session' not in delegated.json() and 'set-cookie' not in delegated.headers
            assert 'browser_session' not in (await client.get('/api/v1/profile',headers={'Authorization':'Bearer '+pair['access_token']})).json()
    asyncio.run(check())


def test_unavailable_offline_support_offers_ordinary_signin(application):
    async def check():
        app,*_=application
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            data=await form(client)
            response=await client.post('/auth/sign-in',data={**data,'remember':'yes'},headers={'Origin':ORIGIN})
            assert response.status_code==403 and 'ordinary sign-in' in response.text
            assert 'Max-Age=604800' not in response.headers.get('set-cookie','')
    asyncio.run(check())


def test_reauthentication_retires_old_cookie_and_retains_existing_connection(renewing_app):
    async def check():
        from test_oauth_server_http import authorize,CALLBACK,RESOURCE
        app,saved,clock,state=renewing_app
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            profile=await remembered_login(client,state)
            old=next(c.value for c in client.cookies.jar if c.name=='c0_session')
            verifier,_=await authorize(client,saved,scope='c0:read')
            accepted=await client.post('/oauth/consent',json={'approve':True,'scopes':['c0:read']},
                headers={'Origin':ORIGIN,'X-C0-CSRF':profile['csrf_token']})
            assert accepted.status_code==200
            code=parse_qs(urlsplit(accepted.json()['redirect_uri']).query)['code'][0]
            pair=(await client.post('/oauth/token',data={'grant_type':'authorization_code','client_id':saved['client_id'],
                'code':code,'redirect_uri':CALLBACK,'code_verifier':verifier,'resource':RESOURCE})).json()
            state['offline']=False
            ordinary=await login(client,state)
            assert ordinary['browser_session']['remembered'] is False
            assert (await client.get('/api/v1/me',headers={'Cookie':'c0_session='+old})).status_code==401
            assert (await client.get('/api/v1/me')).json()['id']==profile['id']
            delegated=await client.get('/api/v1/me',headers={'Authorization':'Bearer '+pair['access_token']})
            assert delegated.status_code==200 and 'set-cookie' not in delegated.headers
            rotated=await refresh(client,saved,pair)
            assert rotated.status_code==200 and rotated.json()['scope']=='c0:read'
    asyncio.run(check())
