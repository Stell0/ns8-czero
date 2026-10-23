# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the exact recovery helpers through HTTP/SQL with controlled native proof.

Actual HTTPS/IdP/SDK, native update and encrypted restore remain QEMU gates.
"""
import json
import os
from pathlib import Path
import secrets
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import text

from czero_core.oidc import OidcConfig
from czero_core.oauth_grants import pkce_challenge
from czero_core.renewal import ConnectionPolicy,NativeAuthorityService,RenewalResult
from czero_core.sessions import SessionService
from test_persistent_oauth import persistent,RESOURCE


def test_exact_recovery_helpers_keep_null_expiry_and_reject_previous_native_binding(persistent,monkeypatch,tmp_path):
    f=persistent;root=Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root/'tests'))
    monkeypatch.setenv('CZERO_MODULE_ID','czero901')
    monkeypatch.setenv('CZERO_DATABASE_URL',os.environ['CZERO_TEST_DATABASE_URL'])
    from czero_app.auth import AppAuth
    from czero_app.main import create_app
    import oauth_fixture,oidc_fixture
    monkeypatch.setattr(oauth_fixture,'STATE',tmp_path)
    def command(arguments):
        with f['database'].engine.connect() as c:return json.dumps(c.execute(text(arguments[-1])).scalar_one())
    monkeypatch.setattr(oidc_fixture,'command',command)
    selected=[];opened=[];extra=None
    def setup(native,secret):
        authority=NativeAuthorityService(f['access'],native,secret,f['authority'].check,
            connection_policy=ConnectionPolicy(7*86400),now=lambda:f['current'][0])
        sessions=SessionService(f['access'],native,authority=authority,now=lambda:f['current'][0])
        provider=SimpleNamespace(config=OidcConfig(f['access'].issuer,native,secret,'https://c0.example.test'),close=lambda:None)
        auth=AppAuth(f['access'],sessions,provider)
        app=create_app('czero901',root/'app/static','',f['database'],auth=auth)
        app.state.delegated_grants._now=lambda:f['current'][0]
        http=TestClient(app,base_url='https://c0.example.test');opened.append(http)
        cookie=sessions.create(f['identity'],renewal=RenewalResult(f['identity'],'offline-fixture',offline=True),
            background=True,expected_account_key=str(f['key']))
        http.cookies.set('c0_session',cookie)
        selected[:]=[SimpleNamespace(app=app,http=http,auth=auth)]
        return http.get('/api/v1/me').json()
    class Browser:
        origin='https://c0.example.test'
        def request(self,path,data=None,method=None,headers=None):
            result=selected[0].http.request(method or 'GET',path,content=data,headers=headers or {})
            return result.status_code,result.content,str(result.url)
        def api(self,path,data=None,method=None,csrf=None):
            headers={'Origin':self.origin}
            if csrf:headers['X-C0-CSRF']=csrf
            result=selected[0].http.request(method or 'GET',path,json=data,headers=headers)
            return result.status_code,result.content,str(result.url)
    browser=Browser();filename='expected-persistent-grant.json'
    def issue(active,profile,client):
        auth=selected[0].auth;grants=selected[0].app.state.delegated_grants
        session=auth.sessions.get(selected[0].http.cookies.get('c0_session'))
        verifier=secrets.token_urlsafe(32)
        code=grants.issue_code(session,client['client_id'],callback=client['redirect_uris'][0],
            scopes={'c0:read'},challenge=pkce_challenge(verifier),resource=RESOURCE,persistent=True)
        pair=grants.exchange_code(code,client['client_id'],callback=client['redirect_uris'][0],verifier=verifier,resource=RESOURCE)
        return {'access_token':pair.access_token,'refresh_token':pair.refresh_token,'scope':'c0:read','expires_in':pair.expires_in}
    def verify_access(module,origin,pair):
        assert browser.request('/api/v1/object-types',headers={'Authorization':'Bearer '+pair['access_token']})[0]==200
    try:
        profile=setup('native1','s'*32)
        oauth_fixture.seed_persistence('czero901',browser,profile,issue_fn=issue,filename=filename)
        before=json.loads((tmp_path/filename).read_text());extra=before['client']['client_id']
        assert before['rows']['grants'][0]['persistent'] is True and before['rows']['grants'][0]['expires_at'] is None
        oauth_fixture.verify_persistence('czero901',browser,profile,issue_fn=issue,filename=filename,sdk_fn=verify_access)
        updated=json.loads((tmp_path/filename).read_text())
        assert updated['pair']['refresh_token']!=before['pair']['refresh_token']
        profile=setup('native2','x'*32)
        oauth_fixture.verify_persistence('czero902',browser,profile,issue_fn=issue,filename=filename,sdk_fn=verify_access)
        after=json.loads((tmp_path/filename).read_text())
        assert after['module_id']=='czero902' and after['pair']['refresh_token']!=updated['pair']['refresh_token']
    finally:
        for http in opened:http.close()
        if extra is not None:
            with f['database'].engine.begin() as c:c.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),{'id':UUID(extra)})
