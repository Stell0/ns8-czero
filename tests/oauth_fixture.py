# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real disposable OAuth consent/token assertions; private fixtures stay on host."""
import hashlib
import base64
import json
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import urlencode, urlsplit, parse_qs

from oidc_fixture import STATE
from oidc_probe import Browser


def registered(browser, profile, *, client_name='Disposable TLS MCP client'):
    descriptor={'client_name':client_name,
        'redirect_uris':['http://127.0.0.1:8765/callback'], 'allowed_scopes':['c0:read','c0:write','c0:admin']}
    status, body, _=browser.api('/api/v1/oauth/clients',descriptor,'POST',profile['csrf_token'])
    assert status==201,'Disposable OAuth client approval failed'
    return json.loads(body)


def issue(browser, profile, client, *, scope='c0:read'):
    verifier=secrets.token_urlsafe(32);state=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    parameters={'client_id':client['client_id'],'redirect_uri':client['redirect_uris'][0],
        'response_type':'code','code_challenge':challenge,'code_challenge_method':'S256',
        'state':state,'scope':scope,'resource':browser.origin+'/mcp',
        'ui_locales':'en-US','future_extension':'ignored'}
    for name in ('resource', 'ui_locales', 'future_extension'):
        duplicate=urlencode(list(parameters.items())+[(name,parameters[name])])
        assert browser.request('/oauth/authorize?'+duplicate)[0]==400,'Installed duplicate authorization field accepted'
        assert browser.request('/oauth/authorize',duplicate.encode(),'POST',
            {'Content-Type':'application/x-www-form-urlencoded'})[0]==400,'Installed duplicate authorization form field accepted'
    # Both methods ignore future optional fields while retaining explicit consent.
    assert browser.request('/oauth/authorize',urlencode(parameters).encode(),'POST',
        {'Content-Type':'application/x-www-form-urlencoded'})[0]==200,'Installed optional authorization form failed'
    status, _, _=browser.request('/oauth/authorize?'+urlencode(parameters))
    assert status==200,'Installed OAuth consent page unavailable'
    status, body, _=browser.api('/oauth/consent/request')
    assert status==200,'Installed consent details unavailable'
    view=json.loads(body)
    assert view['client_id']==client['client_id'] and view['profile']['id']==profile['id'],'Installed consent identity mismatch'
    assert browser.api('/oauth/consent',{'approve':True},'POST')[0]==403,'Installed consent CSRF bypass'
    status, body, _=browser.api('/oauth/consent',{'approve':True,'scopes':scope.split()},'POST',profile['csrf_token'])
    assert status==200,'Installed explicit consent failed'
    values=parse_qs(urlsplit(json.loads(body)['redirect_uri']).query)
    assert values['state']==[state],'Installed OAuth state mismatch'
    request={'grant_type':'authorization_code','client_id':client['client_id'],'code':values['code'][0],
        'redirect_uri':client['redirect_uris'][0],'code_verifier':verifier,'resource':browser.origin+'/mcp'}
    headers={'Content-Type':'application/x-www-form-urlencoded'}
    for changes in ({'resource':browser.origin+'/other'},{'code_verifier':'x'*43}):
        assert browser.request('/oauth/token',urlencode({**request,**changes}).encode(),'POST',headers)[0]==400,'Installed OAuth binding bypass'
    status, body, _=browser.request('/oauth/token',urlencode(request).encode(),'POST',headers)
    assert status==200,'Installed OAuth code exchange failed'
    pair=json.loads(body)
    assert pair['scope']==scope and pair['token_type']=='Bearer','Installed token scope/type mismatch'
    assert browser.request('/oauth/token',urlencode(request).encode(),'POST',headers)[0]==400,'Installed OAuth code replay accepted'
    return pair


def sdk(module_id, origin, pair, *, scope='c0:read'):
    # No credentials in command arguments or Git; public probe code is passed
    # as the command and the private JSON arrives only on stdin.
    source=Path('/tmp/mcp_tls_probe.py').read_text()
    payload={'origin':origin,'address':'10.0.2.2','ca':'/czero-test-ca.pem',
        'access_token':pair['access_token'],'scope':scope}
    result=subprocess.run(['runagent','-m',module_id,'podman','exec','-i','czero','python','-c',source],
        input=json.dumps(payload).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode:
        # Emit only our fixed labels or exception class, never SDK traces.
        safe = next((line for line in result.stderr.decode(errors='replace').splitlines()
                     if line.startswith(('Installed MCP client failed: ', 'Installed MCP assertion failed: '))), '')
        raise AssertionError(safe or 'Installed TLS SDK protocol assertions failed')
    assert result.stdout.strip().endswith(b'checks passed'),'Installed TLS SDK success marker missing'
    if 'c0:write' in scope.split():
        assert b'Installed text evidence lifecycles completed: 2' in result.stdout, 'Installed text evidence lifecycle proof missing'
        print('Disposable installed text ingestion, chunks and sourced claims: current and legacy')
    if {'c0:read','c0:write','c0:admin'} <= set(scope.split()):
        assert b'Installed typed object lifecycles completed: 2' in result.stdout, 'Installed full typed CRUD evidence missing'
        print('Disposable installed typed CRUD: current and legacy (two complete lifecycles)')



def snapshot(module_id, client_id):
    from uuid import UUID
    from oidc_fixture import command
    client = str(UUID(client_id))
    query = """SELECT json_build_object(
        'grants',(SELECT json_agg(g ORDER BY id) FROM c0_oauth_grants g WHERE client_id='%s'),
        'tokens',(SELECT json_agg(t ORDER BY hash) FROM c0_oauth_tokens t JOIN c0_oauth_grants g
                  ON g.id=t.grant_id WHERE g.client_id='%s'),
        'codes',(SELECT json_agg(c ORDER BY hash) FROM c0_oauth_codes c JOIN c0_oauth_grants g
                 ON g.id=c.grant_id WHERE g.client_id='%s'));""" % (client, client, client)
    # Captured only in private Python memory/files, never Robot output.
    return json.loads(command(['runagent','-m',module_id,'podman','exec','czero-postgres',
                              'psql','-U','czero','-d','czero','-At','-c',query]))


def seed_persistence(module_id, browser, profile, *, snapshot_fn=snapshot):
    client = registered(browser, profile, client_name='Disposable active grant recovery')
    pair = issue(browser, profile, client)
    rows = snapshot_fn(module_id, client['client_id'])
    assert len(rows['grants'] or []) == 1 and len(rows['tokens'] or []) == 2, 'Active recovery grant missing'
    path = STATE / 'expected-oauth-grant.json'
    path.write_text(json.dumps({'module_id':module_id,'client':client,'pair':pair,'rows':rows}))
    path.chmod(0o600)


def verify_persistence(module_id, browser, profile, *, snapshot_fn=snapshot, sdk_fn=sdk):
    path = STATE / 'expected-oauth-grant.json'
    expected = json.loads(path.read_text())
    client, pair = expected['client'], expected['pair']
    assert snapshot_fn(module_id, client['client_id']) == expected['rows'], 'Recovered OAuth grant/token/code rows changed'
    headers = {'Content-Type':'application/x-www-form-urlencoded'}
    refresh = {'grant_type':'refresh_token','client_id':client['client_id'],
               'refresh_token':pair['refresh_token'],'resource':browser.origin+'/mcp'}
    restored = module_id != expected['module_id']
    # An expired grant would not prove restored native-client binding.
    from datetime import datetime, timezone
    assert all(datetime.fromisoformat(row['expires_at']).astimezone(timezone.utc) > datetime.now(timezone.utc)
               for row in expected['rows']['grants']), 'Recovery grant expired before binding assertion'
    status, body, _ = browser.request('/oauth/token',urlencode(refresh).encode(),'POST',headers)
    if restored:
        assert status == 400, 'Clean restore accepted previous native-client refresh'
        assert browser.request('/api/v1/object-types',headers={'Authorization':'Bearer '+pair['access_token']})[0] == 401, 'Clean restore accepted previous native-client access'
        pair = issue(browser, profile, client)
    else:
        assert status == 200, 'Update lost active refresh authority'
        pair = json.loads(body)
    sdk_fn(module_id, browser.origin, pair)
    expected.update(module_id=module_id, pair=pair, rows=snapshot_fn(module_id,client['client_id']))
    path.write_text(json.dumps(expected)); path.chmod(0o600)


def persistence(module_id, operation):
    personas=json.loads((STATE/'personas.json').read_text())
    browser=Browser('https://'+personas['host']);profile=browser.login('c0owner',personas['password'])
    if operation == 'seed': seed_persistence(module_id, browser, profile)
    else: verify_persistence(module_id, browser, profile)
    browser.logout(profile)
    print('Disposable exact active-grant recovery, native-client binding and TLS SDK checks passed')



def prepare_browser(module_id, role):
    personas=json.loads((STATE/'personas.json').read_text())
    browser=Browser('https://'+personas['host']);profile=browser.login('c0owner',personas['password'])
    if role != 'admin':
        status, body, _=browser.api('/api/v1/access/accounts')
        assert status == 200, 'Cannot prepare consent browser membership'
        member=next(a for a in json.loads(body)['accounts'] if a['username']=='c0member')
        assert browser.api('/api/v1/access/accounts/'+member['id'],{'role':role},'PUT',profile['csrf_token'])[0] == 204, 'Cannot set consent browser role'
    descriptor={'client_name':'<img src=x onerror=alert(1)> consent browser client',
                'redirect_uris':[browser.origin+'/agents'],'allowed_scopes':['c0:read','c0:write','c0:admin']}
    status, body, _=browser.api('/api/v1/oauth/clients',descriptor,'POST',profile['csrf_token'])
    assert status == 201, 'Cannot approve consent browser client'
    client=json.loads(body);verifier=secrets.token_urlsafe(32);state=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    parameters={'client_id':client['client_id'],'redirect_uri':client['redirect_uris'][0],
                'response_type':'code','code_challenge':challenge,'code_challenge_method':'S256',
                'scope':'c0:read c0:write c0:admin','resource':browser.origin+'/mcp','state':state}
    value={'client':client,'verifier':verifier,'state':state,'role':role,
           'origin':browser.origin,'authorization_url':browser.origin+'/oauth/authorize?'+urlencode(parameters)}
    path=STATE/'browser-oauth.json';path.write_text(json.dumps(value));path.chmod(0o600)
    browser.logout(profile)
    print('Disposable consent browser request prepared')


def complete_browser(module_id):
    from urllib.parse import urlsplit
    value=json.loads((STATE/'browser-oauth.json').read_text())
    callback=value['returned_callback'];parts=urlsplit(callback);expected=urlsplit(value['client']['redirect_uris'][0])
    assert (parts.scheme,parts.netloc,parts.path)==(expected.scheme,expected.netloc,expected.path), 'Consent browser callback changed'
    query=parse_qs(parts.query)
    assert query.get('state')==[value['state']] and len(query.get('code',[]))==1, 'Consent browser state/code missing'
    browser=Browser(value['origin'])
    data={'grant_type':'authorization_code','client_id':value['client']['client_id'],'code':query['code'][0],
          'redirect_uri':value['client']['redirect_uris'][0],'code_verifier':value['verifier'],'resource':browser.origin+'/mcp'}
    status, body, _=browser.request('/oauth/token',urlencode(data).encode(),'POST',{'Content-Type':'application/x-www-form-urlencoded'})
    assert status == 200, 'Consent browser code exchange failed'
    pair=json.loads(body); scopes={'reader':['c0:read'],'editor':['c0:read','c0:write'],
                                 'admin':['c0:admin','c0:read','c0:write']}[value['role']]
    assert set(pair['scope'].split())==set(scopes), 'Consent browser granted unavailable scope'
    sdk(module_id,browser.origin,pair,scope=pair['scope'])
    status, _, _=browser.request('/api/v1/access/accounts',headers={'Authorization':'Bearer '+pair['access_token']})
    assert status == (200 if value['role']=='admin' else 403), 'Consent browser delegated Admin boundary failed'
    print('Disposable real consent controls, role narrowing and TLS SDK checks passed')


def run(module_id):
    personas=json.loads((STATE/'personas.json').read_text())
    browser=Browser('https://'+personas['host']);profile=browser.login('c0owner',personas['password'])
    client=registered(browser,profile);pair=issue(browser,profile,client)
    sdk(module_id,browser.origin,pair)
    headers={'Content-Type':'application/x-www-form-urlencoded'}
    # An upgrade is a separate, explicit SSO/CSRF consent, never a refresh
    # escalation. The read-only grant remains read-only afterward.
    upgrade={'grant_type':'refresh_token','client_id':client['client_id'],
        'refresh_token':pair['refresh_token'],'resource':browser.origin+'/mcp','scope':'c0:read c0:write'}
    assert browser.request('/oauth/token',urlencode(upgrade).encode(),'POST',headers)[0]==400,'Installed refresh increased scopes'
    upgraded=issue(browser,profile,client,scope='c0:read c0:write')
    sdk(module_id,browser.origin,upgraded,scope='c0:read c0:write')
    full=issue(browser,profile,client,scope='c0:admin c0:read c0:write')
    sdk(module_id,browser.origin,full,scope=full['scope'])
    sdk(module_id,browser.origin,pair)
    refresh={'grant_type':'refresh_token','client_id':client['client_id'],
        'refresh_token':pair['refresh_token'],'resource':browser.origin+'/mcp'}
    status, body, _=browser.request('/oauth/token',urlencode(refresh).encode(),'POST',headers)
    assert status==200,'Installed refresh rotation failed'
    rotated=json.loads(body);sdk(module_id,browser.origin,rotated)
    assert browser.request('/oauth/token',urlencode(refresh).encode(),'POST',headers)[0]==400,'Installed refresh replay accepted'
    assert browser.request('/api/v1/object-types',headers={'Authorization':'Bearer '+rotated['access_token']})[0]==401,'Installed replay family remained valid'
    pair=issue(browser,profile,client)
    revoke={'client_id':client['client_id'],'resource':browser.origin+'/mcp','token':pair['refresh_token']}
    assert browser.request('/oauth/revoke',urlencode(revoke).encode(),'POST',headers)[0]==200,'Installed public-client revocation failed'
    assert browser.request('/api/v1/object-types',headers={'Authorization':'Bearer '+pair['access_token']})[0]==401,'Installed revoked access accepted'
    browser.logout(profile)
    print('Disposable real SSO consent, S256, exact resource, one-use, TLS SDK parity, refresh/replay and revocation passed')


if __name__=='__main__':
    try:
        if len(sys.argv) > 2 and sys.argv[2] == 'browser-prepare': prepare_browser(sys.argv[1],sys.argv[3])
        elif len(sys.argv) > 2 and sys.argv[2] == 'browser-complete': complete_browser(sys.argv[1])
        elif len(sys.argv) > 2: persistence(sys.argv[1], sys.argv[2])
        else: run(sys.argv[1])
    except AssertionError as error:print(str(error),file=sys.stderr);sys.exit(1)
    except Exception as error:print('Disposable OAuth failed: '+type(error).__name__,file=sys.stderr);sys.exit(1)
