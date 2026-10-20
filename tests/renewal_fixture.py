# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable native renewal measurement; private tokens travel only on stdin."""
import hashlib
import json
import re
import subprocess
import sys
import time
from urllib.parse import urlencode

from oidc_fixture import STATE, task
from oidc_probe import Browser
from profile_fixture import verify_profile
from oauth_fixture import registered, issue, sdk

SNAPSHOT = r'''
import hashlib,json,os,sys
from sqlalchemy import text
from czero_core.database import Database
from czero_app.auth import AppAuth
request=json.load(sys.stdin)
database=Database()
auth=None
try:
    auth=AppAuth.from_env(database,os.getenv('CZERO_BASE_PATH',''))
    assert auth is not None and auth.sessions.authority is not None
    with database.engine.connect() as c:
        row=c.execute(text("""SELECT n.* FROM c0_native_authority n
            JOIN c0_sessions s ON s.native_authority_id=n.id
            WHERE s.token_hash=:hash AND s.issuer=:issuer AND s.client_id=:client"""),
            {'hash':hashlib.sha256(request['cookie'].encode()).hexdigest(),
             'issuer':auth.access.issuer,'client':auth.sessions.client_id}).mappings().one()
        saved=json.loads(auth.sessions.authority._open(row))
        identity=auth.oidc._token_verifier().verify_access_token(saved['access'])
        print(json.dumps({'id':str(row['id']),'absolute':row['expires_at'].timestamp(),
            'idle':row['idle_until'].timestamp(),'native_expiry':identity.expires_at,
            'access_fingerprint':hashlib.sha256(saved['access'].encode()).hexdigest(),
            'refresh_fingerprint':hashlib.sha256(saved['refresh'].encode()).hexdigest()}))
finally:
    if auth is not None:auth.oidc.close()
    database.close()
'''


def native_snapshot(module_id, browser):
    cookies=[item.value for item in browser.cookies if item.name=='c0_session']
    assert len(cookies)==1, 'Renewal browser cookie missing'
    result=subprocess.run(['runagent','-m',module_id,'podman','exec','-i','czero','python','-c',SNAPSHOT],
        input=json.dumps({'cookie':cookies[0]}).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    assert result.returncode==0, 'Installed renewal authority snapshot failed'
    return json.loads(result.stdout)


def public_refresh(browser, client, pair):
    status,body,_=browser.request('/oauth/token',urlencode({'grant_type':'refresh_token',
        'client_id':client['client_id'],'resource':browser.origin+'/mcp',
        'refresh_token':pair['refresh_token']}).encode(),'POST',
        {'Content-Type':'application/x-www-form-urlencoded'})
    return status,json.loads(body)


def run(module_id, *, browser_factory=Browser, snapshot_fn=native_snapshot, sdk_fn=sdk,
        configure_fn=None, policy=None, clock=time, register_fn=registered):
    assert re.fullmatch(r'czero[0-9]+',module_id), 'Invalid disposable renewal instance'
    personas=json.loads((STATE/'personas.json').read_text())
    assert personas['host'].endswith('.test'), 'Renewal probe requires a disposable hostname'
    origin='https://'+personas['host']
    if configure_fn is None:
        settings=task('module/'+module_id+'/get-configuration',{})
        assert settings['host']==personas['host'], 'Renewal fixture instance differs'
        policy=settings['session_policy']
        def configure_fn(value):
            task('module/'+module_id+'/configure-module',{'host':settings['host'],
                'lets_encrypt':settings['lets_encrypt'],'session_policy':value})
    assert policy=={'absolute_seconds':28800,'idle_seconds':3600}, 'Unexpected native renewal baseline policy'
    browser=browser_factory(origin)
    profile=browser.login('c0owner',personas['password'])
    expected_profile=verify_profile(browser,profile)
    client=register_fn(browser,profile,client_name='Disposable renewable session lifetime')
    pair=issue(browser,profile,client)
    initial=snapshot_fn(module_id,browser)
    started=clock.monotonic()
    assert 0<initial['native_expiry']-clock.time()<=300, 'Native token lifetime cannot establish five-minute renewal'
    assert 28700<initial['absolute']-clock.time()<=28800, 'Native default absolute policy was not applied'
    policy_changed=False
    try:
        # Two isolated new sessions prove inactivity and absolute bounds while
        # the original session retains its snapshotted longer policy.
        policy_changed=True
        configure_fn({'absolute_seconds':120,'idle_seconds':60})
        absolute_browser=browser_factory(origin)
        absolute_start=clock.monotonic()
        absolute_profile=absolute_browser.login('c0owner',personas['password'])
        absolute_pair=issue(absolute_browser,absolute_profile,client)
        absolute_state=snapshot_fn(module_id,absolute_browser)
        # Check the remaining fixture window before setting up the second
        # browser; that setup time is not evidence of the configured limit.
        assert 75<absolute_state['absolute']-clock.time()<=120, 'Insufficient short absolute fixture window'
        idle_browser=browser_factory(origin)
        idle_profile=idle_browser.login('c0owner',personas['password'])
        idle_pair=issue(idle_browser,idle_profile,client)
        idle_start=clock.monotonic()
        idle_state=snapshot_fn(module_id,idle_browser)
        assert 30<idle_state['idle']-clock.time()<=60, 'Insufficient short idle fixture window'
        configure_fn(policy)
        policy_changed=False
        assert snapshot_fn(module_id,absolute_browser)['absolute']==absolute_state['absolute'], 'Configuration extended an existing short session'
        assert snapshot_fn(module_id,browser)['absolute']==initial['absolute'], 'Configuration changed original absolute bound'
        idle_done=absolute_done=False
        absolute_refreshes=reads=0
        while clock.monotonic()-started<330 or not (idle_done and absolute_done):
            assert clock.monotonic()-started<420, 'Renewal measurement exceeded its fixture bound'
            status,body,_=browser.api('/api/v1/me')
            assert status==200 and json.loads(body)['id']==profile['id'], 'Original browser session did not renew'
            reads+=1
            if not idle_done and clock.time()>=idle_state['idle']+1:
                assert idle_browser.api('/api/v1/me')[0]==401, 'Inactive native session revived'
                assert public_refresh(idle_browser,client,idle_pair)[0]==400, 'Inactive delegated session revived'
                idle_elapsed=int(clock.monotonic()-idle_start)
                assert idle_elapsed>=60, 'Inactivity was not measured with elapsed time'
                idle_done=True
            if not absolute_done:
                if clock.time()>=absolute_state['absolute']+1:
                    assert absolute_browser.api('/api/v1/me')[0]==401, 'Absolute native deadline was extended'
                    assert public_refresh(absolute_browser,client,absolute_pair)[0]==400, 'Absolute delegated deadline was extended'
                    absolute_elapsed=int(clock.monotonic()-absolute_start)
                    assert absolute_elapsed>=120, 'Absolute limit was not measured with elapsed time'
                    absolute_done=True
                elif clock.time()<absolute_state['absolute']-3:
                    assert absolute_browser.api('/api/v1/me')[0]==200, 'Active short session ended before its bound'
                    if clock.monotonic()-absolute_start>=70 and not absolute_refreshes:
                        status,renewed=public_refresh(absolute_browser,client,absolute_pair)
                        assert status==200 and renewed['scope']=='c0:read', 'Short session refresh failed'
                        assert renewed['refresh_token']!=absolute_pair['refresh_token'], 'Short refresh did not rotate'
                        absolute_pair=renewed;absolute_refreshes+=1
            clock.sleep(min(20,max(1,330-(clock.monotonic()-started))))
        assert absolute_refreshes==1, 'Active short session refresh was not exercised'
        assert verify_profile(browser,profile)==expected_profile, 'Renewal changed profile identity'
        after=snapshot_fn(module_id,browser)
        assert after['id']==initial['id'] and after['absolute']==initial['absolute'], 'Renewal changed native authority or its absolute bound'
        assert after['native_expiry']>initial['native_expiry'] and after['access_fingerprint']!=initial['access_fingerprint'], 'Native provider access did not renew'
        assert browser.request('/api/v1/object-types',headers={'Authorization':'Bearer '+pair['access_token']})[0]==401, 'Original short access token did not expire'
        status,renewed=public_refresh(browser,client,pair)
        assert status==200 and renewed['scope']=='c0:read' and 0<renewed['expires_in']<=300, 'Bounded delegated renewal failed'
        assert renewed['refresh_token']!=pair['refresh_token'], 'Public refresh did not rotate'
        sdk_fn(module_id,origin,renewed)
        status,_,_=browser.api('/auth/logout',{},'POST',profile['csrf_token'])
        assert status==200 and browser.api('/api/v1/me')[0]==401, 'Local renewable logout failed'
        assert public_refresh(browser,client,renewed)[0]==400, 'Local logout left linked delegation valid'
        fresh=browser_factory(origin)
        fresh_profile=fresh.login('c0owner',personas['password'])
        assert fresh_profile['id']==profile['id'], 'Fresh login changed account identity'
        assert verify_profile(fresh,fresh_profile)==expected_profile, 'Reconnect changed profile identity'
        assert public_refresh(fresh,client,renewed)[0]==400, 'Fresh login revived old delegation'
        status,_,_=fresh.api('/api/v1/oauth/clients/'+client['client_id'],
            {'enabled':False,'expected_revision':client['revision']},'PUT',fresh_profile['csrf_token'])
        assert status==200, 'Renewal fixture client cleanup failed'
        assert fresh.api('/auth/logout',{},'POST',fresh_profile['csrf_token'])[0]==200, 'Renewal fixture local cleanup failed'
        return {'elapsed_seconds':int(clock.monotonic()-started),'browser_reads':reads,
            'native_access_renewals':1,'native_refresh_rotated':int(after['refresh_fingerprint']!=initial['refresh_fingerprint']),
            'public_refresh_rotations':2,'idle_elapsed_seconds':idle_elapsed,
            'absolute_elapsed_seconds':absolute_elapsed,'absolute_bound_preserved':1,
            'logout_and_reconnect':1,'client_disabled':1}
    finally:
        if policy_changed:configure_fn(policy)


if __name__=='__main__':
    try:
        print(json.dumps(run(sys.argv[1]),sort_keys=True))
    except AssertionError as error:
        print(str(error),file=sys.stderr);sys.exit(1)
    except Exception as error:
        print('Disposable renewal failed: '+type(error).__name__,file=sys.stderr);sys.exit(1)
