# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real native access fixtures; browser UI performs all reviewed mutations."""
import json
from pathlib import Path
import secrets
import re
import sys
from urllib.parse import urlencode

from oidc_fixture import STATE, command
from oidc_probe import Browser
from oauth_fixture import issue, registered

URL='https://cdn.jsdelivr.net/gh/Stell0/ns8-czero@test-workspace-client-v1/tests/fixtures/workspace-client.json'
NAME='C0 disposable access browser'
DIGEST='8f2cafd1a4bfd3c7469bd0f9f59c0c5281c4c26464966ec36c7a43d161337d5b'
PATH=STATE/'workspace-access.json'


def checked(browser,path,data=None,method=None,csrf=None,status=200):
    code,body,_=browser.api(path,data,method,csrf)
    assert code==status,'Native access HTTP boundary failed'
    return json.loads(body) if body else None


def connection_status(browser,pair):
    return browser.request('/api/v1/profile',headers={'Authorization':'Bearer '+pair['access_token']})[0]


def run(module_id,phase):
    proof={'phase':phase}
    personas=json.loads((STATE/'personas.json').read_text());origin='https://'+personas['host']
    admin=Browser(origin);owner=admin.login('c0owner',personas['password'])
    rows=checked(admin,'/api/v1/access/workspace')['accounts']
    member=next(a for a in rows if a['username']=='c0member')
    if phase=='prepare':
        if member['role']!='reader' or member['blocked']:
            checked(admin,'/api/v1/access/accounts/'+member['id'],{'role':'reader','expected_revision':member['access_revision']},'PUT',owner['csrf_token'],204)
        user=Browser(origin);profile=user.login('c0member',personas['password'])
        assert profile['role']=='reader'
        raw={'client_id':URL,'redirect_uri':'https://client.example.test/callback','response_type':'code',
             'code_challenge_method':'S256','code_challenge':'a'*43,'state':secrets.token_urlsafe(32),
             'scope':'c0:read c0:write','resource':origin+'/mcp'}
        assert user.request('/oauth/authorize?'+urlencode(raw))[0]==200
        pending=checked(user,'/oauth/connect/request',{},'POST',profile['csrf_token'])
        assert pending['approved'] is False,'Native fixture application was already approved'
        request=checked(admin,'/api/v1/access/accounts/'+member['id']+'/applications')['applications'][0]
        proof.update(fresh_reader=profile['role']=='reader',pending_request=request['kind']=='request')
        value={'member_id':member['id'],'request_id':request['id'],'application_name':NAME}
        PATH.write_text(json.dumps(value));PATH.chmod(0o600)
        user.logout(profile)
    else:
        value=json.loads(PATH.read_text())
        if phase=='approved':
            clients=checked(admin,'/api/v1/oauth/cimd')['clients']
            app=next(c for c in clients if c['metadata_url']==URL)
            assert app['client_name']==NAME and app['allowed_scopes']==['c0:read'] and app['enabled']
            assert app['metadata_digest']==DIGEST,'Native approval differs from fixed public metadata'
            proof.update(allowed_scopes=app['allowed_scopes'],user_role=member['role'],metadata_verified=app['metadata_digest']==DIGEST)
            assert member['role']=='reader' and not member['blocked']
            value['approved_client']=app
            # A fresh independent pending request for Decline; existing approval stays.
            user=Browser(origin);profile=user.login('c0member',personas['password'])
            raw={'client_id':URL,'redirect_uri':'https://client.example.test/callback','response_type':'code',
                 'code_challenge_method':'S256','code_challenge':'b'*43,'scope':'c0:read c0:write',
                 'resource':origin+'/mcp'}
            assert user.request('/oauth/authorize?'+urlencode(raw))[0]==200
            checked(user,'/oauth/connect/request',{},'POST',profile['csrf_token'])
            user.logout(profile)
        elif phase=='declined':
            requests=[a for a in checked(admin,'/api/v1/access/accounts/'+member['id']+'/applications')['applications'] if a['kind']=='request']
            assert len(requests)==1,'Decline affected a sibling pending request'
            assert requests[0]['id']==value['request_id'],'Decline removed the wrong request'
            # The original handoff is no longer needed; cancel through the same public boundary.
            checked(admin,'/api/v1/access/requests/'+requests[0]['id'],None,'DELETE',owner['csrf_token'],204)
            client=registered(admin,owner,client_name='Access isolation '+secrets.token_hex(4))
            user=Browser(origin);profile=user.login('c0member',personas['password'])
            first=issue(user,profile,client);second=issue(user,profile,client)
            other=issue(admin,owner,client)
            entries=checked(admin,'/api/v1/access/accounts/'+member['id']+'/applications')['applications']
            ids=[a['id'] for a in entries if a['kind']=='connection' and a['client_id']==client['client_id']]
            assert len(ids)==2 and all(connection_status(user,p)==200 for p in (first,second,other))
            value.update(client=client,pairs=[first,second],owner_pair=other,connection_ids=ids)
            proof.update(remaining_requests=len(requests),consented_connections=len(ids))
        elif phase=='disconnected':
            user=Browser(origin)
            statuses=[connection_status(user,p) for p in value['pairs']]
            other_status=connection_status(user,value['owner_pair'])
            assert sorted(statuses)==[200,401] and other_status==200
            rejected=value['pairs'][statuses.index(401)]
            body=urlencode({'grant_type':'refresh_token','client_id':value['client']['client_id'],
                'refresh_token':rejected['refresh_token'],'resource':origin+'/mcp'}).encode()
            refresh_status=user.request('/oauth/token',body,'POST',{'Content-Type':'application/x-www-form-urlencoded'})[0]
            assert refresh_status==400
            proof.update(member_statuses=sorted(statuses),other_status=other_status,refresh_status=refresh_status)
            assert member['role']=='reader' and not member['blocked']
            value['disconnected']=True
        elif phase in ('blocked','blocked_after_restart'):
            assert member['blocked'] and member['role'] is None
            user=Browser(origin)
            statuses=[connection_status(user,p) for p in value['pairs']]
            other_status=connection_status(user,value['owner_pair'])
            assert statuses==[401,401] and other_status==200
            for _ in range(2):Browser(origin).login('c0member',personas['password'],expected=403)
            invocation=command(['runagent','-m',module_id,'systemctl','--user','show','czero.service','--property=InvocationID','--value']).strip()
            assert re.fullmatch(r'[0-9a-f]{32}',invocation) and invocation!='0'*32,'Native application invocation missing'
            if phase=='blocked':value['application_invocation']=invocation
            else:
                assert invocation!=value['application_invocation'],'Native application did not restart'
                proof['restart_changed']=True
            value['blocked']=True
            proof.update(member_statuses=statuses,other_status=other_status,blocked_signins=2,blocked=member['blocked'])
        elif phase=='unblocked':
            assert member['role']=='reader' and not member['blocked']
            user=Browser(origin);profile=user.login('c0member',personas['password'])
            statuses=[connection_status(user,p) for p in value['pairs']]
            assert statuses==[401,401]
            assert profile['role']=='reader'
            disabled=checked(admin,'/api/v1/oauth/clients/'+value['client']['client_id'],{'enabled':False,'expected_revision':value['client']['revision']},'PUT',owner['csrf_token'])
            app=value['approved_client']
            disabled_app=checked(admin,'/api/v1/oauth/clients/'+app['client_id'],{'enabled':False,'expected_revision':app['revision']},'PUT',owner['csrf_token'])
            assert disabled['enabled'] is False and disabled_app['enabled'] is False
            user.logout(profile)
            value['unblocked']=True
            proof.update(user_role=profile['role'],member_statuses=statuses,fresh_login=profile['role']=='reader',clients_disabled=not disabled['enabled'] and not disabled_app['enabled'])
        elif phase in ('editor_permissions','manage_permissions','reader_permissions'):
            expected={'editor_permissions':'editor','manage_permissions':'admin','reader_permissions':'reader'}[phase]
            assert member['role']==expected and not member['blocked']
            user=Browser(origin);profile=user.login('c0member',personas['password'])
            assert profile['role']==expected and profile['is_owner'] is False
            status=user.api('/api/v1/access/workspace')[0]
            assert status==(200 if expected=='admin' else 403)
            proof.update(user_role=profile['role'],workspace_status=status)
            user.logout(profile)
        else:raise ValueError('invalid_phase')
        PATH.write_text(json.dumps(value));PATH.chmod(0o600)
    if phase!='declined':admin.logout(owner)
    print('C0 workspace access: '+json.dumps(proof,sort_keys=True))


if __name__=='__main__':run(*sys.argv[1:])
