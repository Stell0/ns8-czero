# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real native remembered issuance/recovery; cookies and rows stay private."""
from contextlib import redirect_stdout
import io
import json
import re
import subprocess
import sys
import time
from urllib.parse import urlencode,urljoin,urlsplit

from persistent_fixture import Form

FIELDS={'seed':{'offline_issued','persistent_cookie','rolling_cookie','browser_restart','ordinary_control','finite_delegation','mcp_no_browser_renewal'},
        'update':{'exact_rows_preserved','remembered_read'},
        'restore':{'exact_rows_preserved','old_cookie_rejected','fresh_remembered_read','provider_revocation_rejected'}}


def validate(proof):
    if (not isinstance(proof,dict) or type(proof.get('stage')) is not str or proof['stage'] not in FIELDS
            or set(proof)!=FIELDS[proof['stage']]|{'stage'}
            or any(type(proof[k]) is not bool or not proof[k] for k in FIELDS[proof['stage']])):
        raise AssertionError('Remembered browser evidence invalid')
    return dict(proof)


def require_recovery(proofs):
    checked=[validate(proof) for proof in proofs]
    if len(checked)!=3 or {proof['stage'] for proof in checked}!=set(FIELDS):
        raise AssertionError('All three remembered browser recovery stages required')
    return sorted(checked,key=lambda proof:list(FIELDS).index(proof['stage']))


CONTAINER=r'''
import hashlib,json,os,sys
import httpx2
from datetime import datetime,timezone
from urllib.parse import urlsplit
from sqlalchemy import text
from czero_core.database import Database
from czero_app.auth import AppAuth
payload=json.load(sys.stdin);database=Database();auth=None
try:
 auth=AppAuth.from_env(database,os.getenv('CZERO_BASE_PATH',''));assert auth is not None
 with database.engine.connect() as c:
  row=c.execute(text("SELECT to_jsonb(s) AS browser,to_jsonb(n) AS native FROM c0_sessions s JOIN c0_native_authority n ON n.id=s.native_authority_id WHERE s.token_hash=:hash"),
   {'hash':hashlib.sha256(payload['cookie'].encode()).hexdigest()}).mappings().one()
 if payload['operation']=='rows':print(json.dumps(dict(row)))
 elif payload['operation']=='finite':
  with database.engine.connect() as c:
   grant=c.execute(text('SELECT expires_at,persistent FROM c0_oauth_grants WHERE native_authority_id=:id'),{'id':row['native']['id']}).mappings().one()
  assert grant['expires_at'] is not None and not grant['persistent']
  assert 0 < (grant['expires_at']-datetime.now(timezone.utc)).total_seconds() <= auth.sessions.authority.policy.absolute_seconds
  print(json.dumps({'finite_delegation':True}))
 else:
  with database.engine.connect() as c:
   native=c.execute(text('SELECT * FROM c0_native_authority WHERE id=:id'),{'id':row['native']['id']}).mappings().one()
  assert row['browser']['remembered'] and row['browser']['browser_idle_seconds']==604800
  saved=json.loads(auth.sessions.authority._open(native));assert saved['offline'] is True
  if payload['operation']=='revoke':
   endpoint=auth.oidc._discovery()['revocation_endpoint']
   assert urlsplit(endpoint).scheme=='https' and urlsplit(endpoint).netloc==urlsplit(auth.oidc.config.issuer).netloc
   response=auth.oidc._http.post(endpoint,data={'token':saved['refresh'],'token_type_hint':'refresh_token'},
       auth=httpx2.BasicAuth(auth.oidc.config.client_id,auth.oidc.config.client_secret))
   assert response.status_code==200
  print(json.dumps({'offline_issued':True}))
finally:
 if auth is not None:auth.oidc.close()
 database.close()
'''


def native(module,cookie,operation):
    result=subprocess.run(['runagent','-m',module,'podman','exec','-i','czero','python','-c',CONTAINER],
        input=json.dumps({'cookie':cookie,'operation':operation}).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
    assert result.returncode==0,'Installed remembered browser probe failed'
    return json.loads(result.stdout)


def sign_in(browser,password):
    status,body,_=browser.request('/auth/sign-in');assert status==200
    form=Form('website-sign-in');form.feed(body.decode());assert form.action
    assert b'name="remember" value="yes"' in body and b' checked' not in body
    status,body,url=browser.request(form.action,urlencode({**form.fields,'remember':'yes'}).encode(),'POST',
        {'Origin':browser.origin,'Content-Type':'application/x-www-form-urlencoded'})
    assert status==200
    form=Form('kc-form-login');form.feed(body.decode());assert form.action
    action=urljoin(url,form.action);assert urlsplit(action).scheme=='https' and urlsplit(action).netloc==urlsplit(url).netloc
    status,body,url=browser.request(action,urlencode({**form.fields,'username':'c0owner','password':password}).encode(),'POST',
        {'Content-Type':'application/x-www-form-urlencoded'})
    assert status==200
    form=Form('kc-oauth');form.feed(body.decode())
    if form.action:
        action=urljoin(url,form.action);assert urlsplit(action).scheme=='https' and urlsplit(action).netloc==urlsplit(url).netloc
        status,_,_=browser.request(action,urlencode({**form.fields,'accept':'Yes'}).encode(),'POST',{'Content-Type':'application/x-www-form-urlencoded'})
        assert status==200
    status,body,_=browser.api('/api/v1/me');assert status==200
    profile=json.loads(body);assert profile['browser_session']=={'remembered':True,'idle_seconds':604800}
    cookies=[c for c in browser.cookies if c.name=='c0_session'];assert len(cookies)==1
    cookie=cookies[0]
    assert cookie.secure and cookie.has_nonstandard_attr('HttpOnly') and cookie.get_nonstandard_attr('SameSite').lower()=='lax'
    assert not cookie.discard and 604700<=cookie.expires-time.time()<=604800
    return profile,cookie.value


def run(module,operation):
    from oidc_fixture import STATE
    from oidc_probe import Browser
    assert re.fullmatch(r'czero[0-9]+',module)
    personas=json.loads((STATE/'personas.json').read_text());assert personas['host'].endswith('.test')
    browser=Browser('https://'+personas['host']);path=STATE/'remembered-browser.json'
    if operation=='seed':
        ordinary=Browser(browser.origin);profile=ordinary.login('c0owner',personas['password'])
        assert profile['browser_session']['remembered'] is False
        profile,cookie=sign_in(browser,personas['password'])
        assert native(module,cookie,'attest')=={'offline_issued':True}
        # A new browser process can replay only the opaque persisted cookie.
        restarted=Browser(browser.origin)
        assert restarted.request('/api/v1/me',headers={'Cookie':'c0_session='+cookie})[0]==200
        before=next(c.expires for c in browser.cookies if c.name=='c0_session')
        time.sleep(2)
        assert browser.api('/api/v1/me')[0]==200
        after=next(c.expires for c in browser.cookies if c.name=='c0_session');assert after>before
        from oauth_fixture import registered,issue,sdk
        client=registered(browser,profile,client_name='Disposable remembered browser')
        try:
            pair=issue(browser,profile,client)
            assert native(module,cookie,'finite')=={'finite_delegation':True}
            before=native(module,cookie,'rows')['browser']
            with redirect_stdout(io.StringIO()):sdk(module,browser.origin,pair)
            assert native(module,cookie,'rows')['browser']==before,'MCP renewed browser inactivity'
        finally:
            assert browser.api('/api/v1/oauth/clients/'+client['client_id'],
                {'expected_revision':client['revision'],'enabled':False},'PUT',profile['csrf_token'])[0]==200
        value={'module':module,'cookie':cookie,'rows':native(module,cookie,'rows')}
        path.write_text(json.dumps(value));path.chmod(0o600)
        stage='seed'
    else:
        value=json.loads(path.read_text());cookie=value['cookie']
        assert native(module,cookie,'rows')==value['rows'],'Remembered rows changed during recovery'
        restored=value['module']!=module;stage='restore' if restored else 'update'
        status,_,_=browser.request('/api/v1/me',headers={'Cookie':'c0_session='+cookie})
        if restored:
            assert status==401
            _,fresh=sign_in(browser,personas['password'])
            assert native(module,fresh,'attest')=={'offline_issued':True}
            native(module,fresh,'revoke')
            assert browser.api('/api/v1/me')[0]==401,'Provider revocation did not stop remembered access'
        else:
            assert status==200
            value['rows']=native(module,cookie,'rows');path.write_text(json.dumps(value));path.chmod(0o600)
    print('C0 remembered browser: '+json.dumps(validate({'stage':stage,**{key:True for key in FIELDS[stage]}}),sort_keys=True))


if __name__=='__main__':
    try:run(sys.argv[1],sys.argv[2])
    except Exception as error:
        print('Disposable remembered browser failed: '+type(error).__name__,file=sys.stderr);raise SystemExit(1)
