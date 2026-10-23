# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real disposable OAuth consent/token assertions; private fixtures stay on host."""
import hashlib
import base64
import json
from datetime import datetime, timezone
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


def recover_consent_session(module_id, browser, client, *, expire_session=None):
    """Keep a real pending request while its disposable C0 session expires."""
    verifier = secrets.token_urlsafe(32)
    parameters = {'client_id':client['client_id'], 'redirect_uri':client['redirect_uris'][0],
        'response_type':'code', 'code_challenge_method':'S256',
        'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(),
        'state':secrets.token_urlsafe(32), 'scope':'c0:read', 'resource':browser.origin+'/mcp'}
    assert browser.request('/oauth/authorize?'+urlencode(parameters))[0] == 200, 'Installed recovery request failed'
    cookies = [cookie for cookie in browser.cookies if cookie.name == 'c0_session']
    assert len(cookies) == 1, 'Disposable recovery session missing'
    old_cookie = cookies[0].value
    if expire_session is not None:
        expire_session(old_cookie)
    else:
        # Expire only this fixture-owned session. Private SQL travels on stdin,
        # and no raw cookie, token or query enters arguments or Robot output.
        hashed = hashlib.sha256(old_cookie.encode()).hexdigest()
        sql = "UPDATE c0_sessions SET expires_at=now()-interval '1 second' WHERE token_hash='"+hashed+"';"
        result = subprocess.run(['runagent','-m',module_id,'podman','exec','-i','czero-postgres',
            'psql','-U','czero','-d','czero','-v','ON_ERROR_STOP=1'],
            input=sql.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        assert result.returncode == 0 and b'UPDATE 1' in result.stdout, 'Disposable session expiry failed'
    assert browser.api('/oauth/consent/request')[0] == 401, 'Installed expired session remained valid'
    assert browser.request('/oauth/consent')[0] == 200, 'Installed expired consent session did not recover through SSO'
    cookies = [cookie for cookie in browser.cookies if cookie.name == 'c0_session']
    assert len(cookies) == 1 and cookies[0].value != old_cookie, 'Installed recovery reused expired session'
    status, body, _ = browser.api('/api/v1/me')
    assert status == 200, 'Installed recovered profile unavailable'
    profile = json.loads(body)
    status, body, _ = browser.api('/oauth/consent/request')
    assert status == 200 and json.loads(body)['client_id'] == client['client_id'], 'Installed recovery lost pending consent'
    assert browser.api('/oauth/consent', {'approve':True}, 'POST')[0] == 403, 'Installed recovery bypassed explicit CSRF consent'
    print('Disposable expired consent session recovered through real SSO; explicit consent still required')
    return profile


def issue(browser, profile, client, *, scope='c0:read', prepare_connection=None):
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
    if prepare_connection is not None:
        assert browser.api('/oauth/connect/request', {}, 'POST')[0] == 403, 'Installed onboarding CSRF bypass'
        status, body, _ = browser.api('/oauth/connect/request', {}, 'POST', profile['csrf_token'])
        assert status == 200, 'Installed connection handoff unavailable'
        pending = json.loads(body)
        assert not pending['approved'] and pending['metadata_url'] == client['client_id'], 'Unknown client bypassed approval'
        assert browser.api('/oauth/consent/request')[0] != 200, 'Unknown client obtained consent before approval'
        prepare_connection()
        status, body, _ = browser.api('/oauth/connect/continue', {'scopes': scope.split()}, 'POST', profile['csrf_token'])
        assert status == 200 and json.loads(body)['next'] == '/oauth/consent', 'Approved connection lost its consent handoff'
        assert browser.api('/oauth/connect/request', {}, 'POST', profile['csrf_token'])[0] == 410, 'Installed connection handoff replay accepted'
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
        input=json.dumps(payload).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
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
        assert b'Installed applicability and structured retrieval lifecycles completed: 2' in result.stdout, 'Installed annotation/structured retrieval proof missing'
        assert b'Installed atomic consolidation lifecycles completed: 2' in result.stdout, 'Installed atomic consolidation proof missing'
        assert b'Installed guided agent lifecycles completed: 2' in result.stdout, 'Installed guided independent-session proof missing'
        print('Disposable installed typed CRUD: current and legacy (two complete lifecycles)')



def snapshot(module_id, client_id):
    from uuid import UUID
    from oidc_fixture import command
    client = str(UUID(client_id))
    query = """SELECT json_build_object(
        'grants',(SELECT json_agg(to_jsonb(g) || jsonb_build_object(
            'native_authority_id',to_jsonb(g)->'native_authority_id',
            'persistent',COALESCE(to_jsonb(g)->'persistent','false'::jsonb),
            'idle_until',to_jsonb(g)->'idle_until','last_used_at',to_jsonb(g)->'last_used_at',
            'refresh_family',to_jsonb(g)->'refresh_family',
            'refresh_generation',COALESCE(to_jsonb(g)->'refresh_generation','0'::jsonb)) ORDER BY id)
            FROM c0_oauth_grants g WHERE client_id='%s'),
        'tokens',(SELECT json_agg(t ORDER BY hash) FROM c0_oauth_tokens t JOIN c0_oauth_grants g
                  ON g.id=t.grant_id WHERE g.client_id='%s'),
        'codes',(SELECT json_agg(c ORDER BY hash) FROM c0_oauth_codes c JOIN c0_oauth_grants g
                 ON g.id=c.grant_id WHERE g.client_id='%s'));""" % (client, client, client)
    # Captured only in private Python memory/files, never Robot output.
    return json.loads(command(['runagent','-m',module_id,'podman','exec','czero-postgres',
                              'psql','-U','czero','-d','czero','-At','-c',query]))


def seed_persistence(module_id, browser, profile, *, snapshot_fn=snapshot, issue_fn=issue,
        filename='expected-oauth-grant.json', client_name='Disposable active grant recovery'):
    client = registered(browser, profile, client_name=client_name)
    pair = issue_fn(browser, profile, client)
    rows = snapshot_fn(module_id, client['client_id'])
    assert len(rows['grants'] or []) == 1 and len(rows['tokens'] or []) == 2, 'Active recovery grant missing'
    path = STATE / filename
    path.write_text(json.dumps({'module_id':module_id,'client':client,'pair':pair,'rows':rows}))
    path.chmod(0o600)


def parse_grant_expiry(value):
    # PostgreSQL omits trailing fractional zeros. Python 3.9 fromisoformat
    # accepts only three or six fractional digits; strptime accepts one to six.
    pattern = '%Y-%m-%dT%H:%M:%S' + ('.%f' if '.' in value else '') + '%z'
    return datetime.strptime(value, pattern).astimezone(timezone.utc)


def verify_persistence(module_id, browser, profile, *, snapshot_fn=snapshot, sdk_fn=sdk, issue_fn=issue,
        filename='expected-oauth-grant.json'):
    path = STATE / filename
    expected = json.loads(path.read_text())
    client, pair = expected['client'], expected['pair']
    assert snapshot_fn(module_id, client['client_id']) == expected['rows'], 'Recovered OAuth grant/token/code rows changed'
    headers = {'Content-Type':'application/x-www-form-urlencoded'}
    refresh = {'grant_type':'refresh_token','client_id':client['client_id'],
               'refresh_token':pair['refresh_token'],'resource':browser.origin+'/mcp'}
    restored = module_id != expected['module_id']
    # An expired grant would not prove restored native-client binding.
    assert all(parse_grant_expiry(row['idle_until'] if row.get('persistent') else row['expires_at']) > datetime.now(timezone.utc)
               for row in expected['rows']['grants']), 'Recovery grant expired before binding assertion'
    status, body, _ = browser.request('/oauth/token',urlencode(refresh).encode(),'POST',headers)
    if restored:
        assert status == 400, 'Clean restore accepted previous native-client refresh'
        assert browser.request('/api/v1/object-types',headers={'Authorization':'Bearer '+pair['access_token']})[0] == 401, 'Clean restore accepted previous native-client access'
        pair = issue_fn(browser, profile, client)
    else:
        assert status == 200, 'Update lost active refresh authority'
        pair = json.loads(body)
        assert pair['refresh_token'] != expected['pair']['refresh_token'], 'Recovered refresh did not rotate'
    sdk_fn(module_id, browser.origin, pair)
    expected.update(module_id=module_id, pair=pair, rows=snapshot_fn(module_id,client['client_id']))
    path.write_text(json.dumps(expected)); path.chmod(0o600)


def persistence(module_id, operation):
    personas=json.loads((STATE/'personas.json').read_text())
    browser=Browser('https://'+personas['host']);profile=browser.login('c0owner',personas['password'])
    if operation == 'seed': seed_persistence(module_id, browser, profile)
    else: verify_persistence(module_id, browser, profile)
    # Retain the originating native authority for exact update/restart/restore
    # assertions. Logging out would correctly revoke its linked delegation.
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
    if value.get('persistent'):
        from uuid import UUID
        from oidc_fixture import command
        identifier=str(UUID(value['client']['client_id']))
        query="SELECT json_build_object('native',native_authority_id,'persistent',persistent) FROM c0_oauth_grants WHERE client_id='"+identifier+"'"
        row=json.loads(command(['runagent','-m',module_id,'podman','exec','czero-postgres','psql','-U','czero','-d','czero','-At','-c',query]))
        assert row['persistent'] is True and row['native'], 'Browser background grant was not persisted'
        value['native_authority_id']=str(UUID(row['native']))
        path=STATE/'browser-oauth.json';path.write_text(json.dumps(value));path.chmod(0o600)
    print('Disposable real consent controls, role narrowing and TLS SDK checks passed')


def browser_disconnected(module_id):
    from uuid import UUID
    from oidc_fixture import command
    value=json.loads((STATE/'browser-oauth.json').read_text());identifier=str(UUID(value['client']['client_id']))
    query="SELECT count(*) FROM c0_oauth_grants WHERE client_id='"+identifier+"'"
    assert command(['runagent','-m',module_id,'podman','exec','czero-postgres','psql','-U','czero','-d','czero','-At','-c',query]).strip()=='0'
    print('Disposable account disconnect removed the client authority')


def cleanup_browser(module_id):
    value=json.loads((STATE/'browser-oauth.json').read_text())
    personas=json.loads((STATE/'personas.json').read_text());assert personas['host'].endswith('.test')
    if value.get('persistent'):
        from persistent_fixture import native
        assert native(module_id,{'operation':'revoke','id':value['native_authority_id']})=={'provider_revoked':True}
    browser=Browser(value['origin']);profile=browser.login('c0owner',personas['password'])
    assert browser.api('/api/v1/oauth/clients/'+value['client']['client_id'],
        {'enabled':False,'expected_revision':value['client']['revision']},'PUT',profile['csrf_token'])[0]==200
    browser.logout(profile)
    print('Disposable browser client disabled and owned offline credentials revoked')


def run(module_id):
    personas=json.loads((STATE/'personas.json').read_text())
    browser=Browser('https://'+personas['host']);profile=browser.login('c0owner',personas['password'])
    client=registered(browser,profile)
    profile=recover_consent_session(module_id,browser,client)
    pair=issue(browser,profile,client)
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
        elif len(sys.argv) > 2 and sys.argv[2] == 'browser-disconnected': browser_disconnected(sys.argv[1])
        elif len(sys.argv) > 2 and sys.argv[2] == 'browser-cleanup': cleanup_browser(sys.argv[1])
        elif len(sys.argv) > 2: persistence(sys.argv[1], sys.argv[2])
        else: run(sys.argv[1])
    except AssertionError as error:print(str(error),file=sys.stderr);sys.exit(1)
    except Exception as error:print('Disposable OAuth failed: '+type(error).__name__,file=sys.stderr);sys.exit(1)
