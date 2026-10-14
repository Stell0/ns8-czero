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


def registered(browser, profile):
    descriptor={'client_name':'Disposable TLS MCP client',
        'redirect_uris':['http://127.0.0.1:8765/callback'], 'allowed_scopes':['c0:read','c0:write','c0:admin']}
    status, body, _=browser.api('/api/v1/oauth/clients',descriptor,'POST',profile['csrf_token'])
    assert status==201,'Disposable OAuth client approval failed'
    return json.loads(body)


def issue(browser, profile, client, *, scope='c0:read'):
    verifier=secrets.token_urlsafe(32);state=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    parameters={'client_id':client['client_id'],'redirect_uri':client['redirect_uris'][0],
        'response_type':'code','code_challenge':challenge,'code_challenge_method':'S256',
        'state':state,'scope':scope,'resource':browser.origin+'/mcp'}
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
    assert result.returncode==0,'Installed TLS SDK protocol assertions failed'
    assert result.stdout.strip().endswith(b'checks passed'),'Installed TLS SDK success marker missing'


def run(module_id):
    personas=json.loads((STATE/'personas.json').read_text())
    browser=Browser('https://'+personas['host']);profile=browser.login('c0owner',personas['password'])
    client=registered(browser,profile);pair=issue(browser,profile,client)
    sdk(module_id,browser.origin,pair)
    headers={'Content-Type':'application/x-www-form-urlencoded'}
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
    try:run(sys.argv[1])
    except AssertionError as error:print(str(error),file=sys.stderr);sys.exit(1)
    except Exception as error:print('Disposable OAuth failed: '+type(error).__name__,file=sys.stderr);sys.exit(1)
