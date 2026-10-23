# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable native persistent OAuth acceptance; private data stays on stdin."""
import base64
from contextlib import redirect_stdout
import hashlib
from html.parser import HTMLParser
import io
import json
import re
import secrets
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

FIELDS = {'browser_absolute_seconds','elapsed_seconds','browser_expired','refresh_after_browser_expiry',
    'logout_preserved_background','read_write_sdk','old_generation_replay_revoked','self_disconnect_revoked',
    'client_disabled','provider_credential_revoked','policy_restored'}
RECOVERY_FIELDS = {
    'seed': {'rows_captured','background_consent'},
    'update': {'rows_preserved','refresh_rotated','old_grant_unexpired'},
    'restore': {'rows_preserved','old_grant_unexpired','old_authority_rejected',
        'fresh_background_consent','client_disabled','provider_credential_revoked','policy_restored'},
}


def validate(value):
    if (not isinstance(value,dict) or set(value)!=FIELDS
            or type(value['browser_absolute_seconds']) is not int or value['browser_absolute_seconds']!=120
            or type(value['elapsed_seconds']) is not int or not 120<=value['elapsed_seconds']<=300
            or any(type(value[key]) is not bool or not value[key] for key in FIELDS-{'browser_absolute_seconds','elapsed_seconds'})):
        raise AssertionError('Persistent connection evidence invalid')
    return dict(value)


def validate_recovery(value):
    if not isinstance(value,dict) or type(value.get('stage')) is not str or value['stage'] not in RECOVERY_FIELDS:
        raise AssertionError('Persistent recovery evidence invalid')
    fields=RECOVERY_FIELDS[value['stage']]
    if (set(value)!=fields|{'stage','inactivity_seconds'} or type(value['inactivity_seconds']) is not int
            or value['inactivity_seconds']!=7*86400
            or any(type(value[key]) is not bool or not value[key] for key in fields)):
        raise AssertionError('Persistent recovery evidence invalid')
    return dict(value)


def require_recovery(values):
    checked=[validate_recovery(value) for value in values]
    if len(checked)!=3 or {value['stage'] for value in checked}!=set(RECOVERY_FIELDS):
        raise AssertionError('All three measured persistent recovery stages required')
    return sorted(checked,key=lambda value:list(RECOVERY_FIELDS).index(value['stage']))


class Form(HTMLParser):
    def __init__(self,identifier):
        super().__init__();self.identifier=identifier;self.active=False;self.action=None;self.fields={}
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='form':
            self.active=values.get('id')==self.identifier
            if self.active:self.action=values.get('action')
        if self.active and tag=='input' and values.get('type')=='hidden' and values.get('name'):
            self.fields[values['name']]=values.get('value','')
    def handle_endtag(self,tag):
        if tag=='form':self.active=False


def issue(browser,profile,client,password,*,offline=False):
    verifier=secrets.token_urlsafe(32);state=secrets.token_urlsafe(32);scopes=['c0:read','c0:write']
    query={'client_id':client['client_id'],'redirect_uri':client['redirect_uris'][0],'response_type':'code',
        'code_challenge_method':'S256','code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(),
        'state':state,'scope':' '.join(scopes),'resource':browser.origin+'/mcp'}
    assert browser.request('/oauth/authorize?'+urlencode(query))[0]==200, 'Background consent unavailable'
    status,body,_=browser.api('/oauth/consent/request');assert status==200
    initial=json.loads(body)
    assert initial['background_supported'] and not initial['background_requested']
    if offline:
        status,body,_=browser.api('/oauth/consent/background',{'scopes':scopes},'POST',profile['csrf_token'])
        assert status==200 and json.loads(body)=={'next':'/auth/login'}, 'Background sign-in handoff failed'
        status,body,url=browser.request('/auth/login');assert status==200
        form=Form('kc-form-login');form.feed(body.decode());assert form.action, 'Background native login form missing'
        action=urljoin(url,form.action);assert urlsplit(action).scheme=='https' and urlsplit(action).netloc==urlsplit(url).netloc
        status,body,url=browser.request(action,urlencode({**form.fields,'username':'c0owner','password':password}).encode(),
            'POST',{'Content-Type':'application/x-www-form-urlencoded'})
        assert status==200, 'Background native callback failed'
        form=Form('kc-oauth');form.feed(body.decode())
        if form.action:
            action=urljoin(url,form.action);assert urlsplit(action).scheme=='https' and urlsplit(action).netloc==urlsplit(url).netloc
            status,_,url=browser.request(action,urlencode({**form.fields,'accept':'Yes'}).encode(),
                'POST',{'Content-Type':'application/x-www-form-urlencoded'})
            assert status==200, 'Background provider consent failed'
        assert url==browser.origin+'/oauth/consent', 'Background callback returned elsewhere'
        status,body,_=browser.api('/api/v1/me');assert status==200
        current=json.loads(body);assert current['id']==profile['id'], 'Background sign-in switched account'
        profile=current
    status,body,_=browser.api('/oauth/consent/request');assert status==200
    view=json.loads(body)
    assert view['background_ready'] and view['expires_at']==initial['expires_at'], 'Background request changed its lifetime'
    assert browser.api('/oauth/consent',{'approve':True,'scopes':scopes,'persistent':True},'POST')[0]==403
    status,body,_=browser.api('/oauth/consent',{'approve':True,'scopes':scopes,'persistent':True},'POST',profile['csrf_token'])
    assert status==200, 'Explicit background consent failed'
    values=parse_qs(urlsplit(json.loads(body)['redirect_uri']).query);assert values['state']==[state]
    status,body,_=browser.request('/oauth/token',urlencode({'grant_type':'authorization_code','client_id':client['client_id'],
        'redirect_uri':client['redirect_uris'][0],'code':values['code'][0],'code_verifier':verifier,'resource':browser.origin+'/mcp'}).encode(),
        'POST',{'Content-Type':'application/x-www-form-urlencoded'})
    assert status==200, 'Background code exchange failed'
    pair=json.loads(body);assert pair['scope']=='c0:read c0:write' and 0<pair['expires_in']<=300
    return pair,profile


CONTAINER = r"""
import hashlib,json,os,sys
from uuid import UUID
from urllib.parse import urlsplit
import httpx2
from sqlalchemy import text
from czero_core.database import Database
from czero_app.auth import AppAuth
request=json.load(sys.stdin);database=Database();auth=None
try:
 auth=AppAuth.from_env(database,os.getenv('CZERO_BASE_PATH',''));assert auth is not None
 with database.engine.connect() as c:
  if request['operation']=='snapshot':
   row=c.execute(text('''SELECT n.*,s.expires_at AS browser_expires FROM c0_native_authority n
    JOIN c0_sessions s ON s.native_authority_id=n.id WHERE s.token_hash=:hash
    AND n.issuer=:issuer AND n.native_client=:client'''),{'hash':hashlib.sha256(request['cookie'].encode()).hexdigest(),
    'issuer':auth.access.issuer,'client':auth.sessions.client_id}).mappings().one()
   assert row['authority_kind']=='background' and row['expires_at'] is None
   assert json.loads(auth.sessions.authority._open(row))['offline'] is True
   print(json.dumps({'id':str(row['id']),'browser_expires':row['browser_expires'].timestamp()}))
  else:
   row=c.execute(text('SELECT * FROM c0_native_authority WHERE id=:id AND issuer=:issuer AND native_client=:client'),
    {'id':UUID(request['id']),'issuer':auth.access.issuer,'client':auth.sessions.client_id}).mappings().one()
   assert row['authority_kind']=='background'
   refresh=json.loads(auth.sessions.authority._open(row))['refresh']
   endpoint=auth.oidc._discovery()['revocation_endpoint']
   assert urlsplit(endpoint).scheme=='https' and urlsplit(endpoint).netloc==urlsplit(auth.oidc.config.issuer).netloc
   result=auth.oidc._http.post(endpoint,data={'token':refresh,'token_type_hint':'refresh_token'},
     auth=httpx2.BasicAuth(auth.oidc.config.client_id,auth.oidc.config.client_secret))
   assert result.status_code==200
 if request['operation']=='revoke':
  auth.sessions.authority.revoke(UUID(request['id']));print(json.dumps({'provider_revoked':True}))
finally:
 if auth is not None:auth.oidc.close()
 database.close()
"""


def native(module_id,payload):
    result=subprocess.run(['runagent','-m',module_id,'podman','exec','-i','czero','python','-c',CONTAINER],
        input=json.dumps(payload).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
    assert result.returncode==0, 'Installed background authority probe failed'
    return json.loads(result.stdout)


def run(module_id):
    from oidc_fixture import STATE,task
    from oidc_probe import Browser
    from oauth_fixture import registered,sdk
    from renewal_fixture import public_refresh
    assert re.fullmatch(r'czero[0-9]+',module_id)
    personas=json.loads((STATE/'personas.json').read_text());assert personas['host'].endswith('.test')
    settings=task('module/'+module_id+'/get-configuration',{});assert settings['host']==personas['host']
    assert settings['session_policy']=={'absolute_seconds':28800,'idle_seconds':3600}
    def configure(policy):
        task('module/'+module_id+'/configure-module',{'host':settings['host'],'lets_encrypt':settings['lets_encrypt'],'session_policy':policy})
    origin='https://'+personas['host'];browser=Browser(origin);owner=browser.login('c0owner',personas['password'])
    client=registered(browser,owner,client_name='Disposable background access')
    changed=False;snapshot=None;started=time.monotonic()
    try:
        changed=True;configure({'absolute_seconds':120,'idle_seconds':60})
        pair,profile=issue(browser,owner,client,personas['password'],offline=True)
        cookies=[c.value for c in browser.cookies if c.name=='c0_session'];assert len(cookies)==1
        snapshot=native(module_id,{'operation':'snapshot','cookie':cookies[0]})
        assert 75<snapshot['browser_expires']-time.time()<=120, 'Insufficient background browser fixture window'
        other,_=issue(browser,profile,client,personas['password'])
        configure(settings['session_policy']);changed=False
        while time.time()<=snapshot['browser_expires']+1:
            assert time.monotonic()-started<240, 'Background fixture exceeded its bound'
            if time.time()<snapshot['browser_expires']-3:
                assert browser.api('/api/v1/me')[0]==200, 'Active background browser expired early'
            time.sleep(10)
        # Replay the captured cookie explicitly: CookieJar expiry alone is not
        # evidence that the server enforces the browser's absolute deadline.
        cookie_header={'Cookie':'c0_session='+cookies[0]}
        assert browser.request('/api/v1/me',headers=cookie_header)[0]==401, 'Background browser exceeded its absolute deadline'
        status,renewed=public_refresh(browser,client,pair);assert status==200
        pair=renewed
        assert browser.request('/auth/logout',b'{}','POST',
            {**cookie_header,'Origin':origin,'X-C0-CSRF':profile['csrf_token'],'Content-Type':'application/json'})[0]==200
        status,renewed=public_refresh(browser,client,pair);assert status==200
        pair=renewed
        with redirect_stdout(io.StringIO()):sdk(module_id,origin,pair,scope='c0:read c0:write')
        status,rotated=public_refresh(browser,client,other);assert status==200
        assert public_refresh(browser,client,other)[0]==400
        assert public_refresh(browser,client,rotated)[0]==400
        fresh=Browser(origin);owner=fresh.login('c0owner',personas['password'])
        status,body,_=fresh.api('/api/v1/oauth/connections');assert status==200
        matches=[c for c in json.loads(body)['connections'] if c['client_name']=='Disposable background access']
        assert len(matches)==1 and matches[0]['persistent'] and matches[0]['expires_at'] is None
        path='/api/v1/oauth/connections/'+matches[0]['id']
        assert fresh.api(path,None,'DELETE')[0]==403
        assert fresh.api(path,None,'DELETE',owner['csrf_token'])[0]==204
        assert public_refresh(fresh,client,pair)[0]==400
        assert fresh.api('/api/v1/oauth/clients/'+client['client_id'],
            {'enabled':False,'expected_revision':client['revision']},'PUT',owner['csrf_token'])[0]==200
        assert fresh.api('/auth/logout',{},'POST',owner['csrf_token'])[0]==200
        assert native(module_id,{'operation':'revoke','id':snapshot['id']})=={'provider_revoked':True}
        snapshot=None
        return validate({'browser_absolute_seconds':120,'elapsed_seconds':int(time.monotonic()-started),
            **{key:True for key in FIELDS-{'browser_absolute_seconds','elapsed_seconds'}}})
    finally:
        if changed:configure(settings['session_policy'])
        if snapshot is not None:native(module_id,{'operation':'revoke','id':snapshot['id']})


def recovery(module_id,operation):
    from oidc_fixture import STATE,task
    from oidc_probe import Browser
    from oauth_fixture import seed_persistence,verify_persistence,sdk,parse_grant_expiry
    assert re.fullmatch(r'czero[0-9]+',module_id) and operation in ('seed','verify')
    personas=json.loads((STATE/'personas.json').read_text());assert personas['host'].endswith('.test')
    settings=task('module/'+module_id+'/get-configuration',{});assert settings['host']==personas['host']
    def configure(seconds):
        task('module/'+module_id+'/configure-module',{'host':settings['host'],
            'lets_encrypt':settings['lets_encrypt'],'connection_idle_seconds':seconds})
    filename='expected-persistent-grant.json';path=STATE/filename
    original=settings['connection_idle_seconds'] if operation=='seed' else json.loads(path.read_text())['original_idle_seconds']
    if operation=='seed':configure(7*86400)
    else:assert settings['connection_idle_seconds']==7*86400, 'Background inactivity setting was not recovered'
    def create(active,actor,client):
        pair,_=issue(active,actor,client,personas['password'],offline=True)
        return pair
    def verified_sdk(module,origin,pair):
        with redirect_stdout(io.StringIO()):sdk(module,origin,pair,scope=pair['scope'])
    try:
        browser=Browser('https://'+personas['host']);profile=browser.login('c0owner',personas['password'])
        if operation=='seed':
            seed_persistence(module_id,browser,profile,issue_fn=create,filename=filename,
                client_name='Disposable persistent grant recovery')
            value=json.loads(path.read_text());value['original_idle_seconds']=original
            path.write_text(json.dumps(value));path.chmod(0o600);stage='seed'
        else:
            value=json.loads(path.read_text());stage='restore' if module_id!=value['module_id'] else 'update'
            verify_persistence(module_id,browser,profile,issue_fn=create,filename=filename,sdk_fn=verified_sdk)
        current=json.loads(path.read_text())
        assert current['rows']['grants'] and all(row['persistent'] and row['expires_at'] is None for row in current['rows']['grants'])
        for row in current['rows']['grants']:
            duration=(parse_grant_expiry(row['idle_until'])-parse_grant_expiry(row['last_used_at'])).total_seconds()
            # The two timestamps are sampled within one authenticated request;
            # tolerate scheduling without confusing a different configured day.
            assert abs(duration-7*86400)<1, 'Recovered background grant changed inactivity policy'
        if stage=='restore':
            cookies=[cookie.value for cookie in browser.cookies if cookie.name=='c0_session'];assert len(cookies)==1
            owned=native(module_id,{'operation':'snapshot','cookie':cookies[0]})
            status,body,_=browser.api('/api/v1/me');assert status==200
            actor=json.loads(body);client=current['client'];pair=current['pair']
            status,_,_=browser.request('/oauth/revoke',urlencode({'client_id':client['client_id'],
                'token':pair['refresh_token'],'resource':browser.origin+'/mcp'}).encode(),'POST',
                {'Content-Type':'application/x-www-form-urlencoded'})
            assert status==200
            from renewal_fixture import public_refresh
            assert public_refresh(browser,client,pair)[0]==400, 'Recovery cleanup left refresh authority'
            assert browser.api('/api/v1/oauth/clients/'+client['client_id'],
                {'enabled':False,'expected_revision':client['revision']},'PUT',actor['csrf_token'])[0]==200
            assert native(module_id,{'operation':'revoke','id':owned['id']})=={'provider_revoked':True}
            configure(original)
        return validate_recovery({'stage':stage,'inactivity_seconds':7*86400,
            **{key:True for key in RECOVERY_FIELDS[stage]}})
    except BaseException:
        if operation=='seed' or 'stage' in locals() and stage=='restore':configure(original)
        raise


if __name__=='__main__':
    try:
        if len(sys.argv)==3:print('C0 persistent recovery: '+json.dumps(recovery(sys.argv[1],sys.argv[2]),sort_keys=True))
        else:
            assert len(sys.argv)==2
            print('C0 persistent connection: '+json.dumps(run(sys.argv[1]),sort_keys=True))
    except Exception as error:
        print('Disposable persistent connection failed: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(1)
