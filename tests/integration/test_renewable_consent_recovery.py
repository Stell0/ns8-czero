# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the native expiry SQL against an actual renewable signed-HTTP session."""
import json
from pathlib import Path
import time
from types import SimpleNamespace
from urllib.parse import parse_qs,urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import text

from test_session_renewal_http import renewing_app
from test_auth_http import ORIGIN


def test_native_recovery_expires_both_browser_bounds_before_fresh_sso(renewing_app,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
    import oauth_fixture
    app,saved,clock,state=renewing_app
    with TestClient(app,base_url=ORIGIN,follow_redirects=False) as http:
        class Browser:
            origin=ORIGIN
            cookies=http.cookies.jar
            def request(self,path,data=None,method=None,headers=None):
                response=http.request(method or ('POST' if data is not None else 'GET'),path,content=data,headers=headers or {})
                for _ in range(8):
                    if response.status_code!=302:return response.status_code,response.content,str(response.url)
                    target=response.headers['location']
                    if urlsplit(target).hostname=='idp.example.test':
                        fields=parse_qs(urlsplit(target).query);state['nonce']=fields['nonce'][0]
                        response=http.get('/auth/callback',params={'state':fields['state'][0],'code':'private-code'})
                    else:response=http.get(target)
                raise AssertionError('Native consent recovery redirect loop')
            def api(self,path,data=None,method=None,csrf=None):
                headers={'Origin':ORIGIN}
                if csrf:headers['X-C0-CSRF']=csrf
                if data is not None:headers['Content-Type']='application/json'
                return self.request(path,json.dumps(data).encode() if data is not None else None,method,headers)
        browser=Browser()
        assert browser.request('/auth/login')[0]==200
        status,body,_=browser.api('/api/v1/me');assert status==200
        old=next(c.value for c in browser.cookies if c.name=='c0_session')
        def run(arguments,*,input,**kwargs):
            assert arguments[:3]==['runagent','-m','czero901'] and 'psql' in arguments
            assert old not in ' '.join(arguments)
            with app.state.auth.access.database.engine.begin() as connection:
                assert connection.execute(text(input.decode())).rowcount==1
            clock[0]=time.time()
            return SimpleNamespace(returncode=0,stdout=b'UPDATE 1',stderr=b'')
        monkeypatch.setattr(oauth_fixture.subprocess,'run',run)
        profile=oauth_fixture.recover_consent_session('czero901',browser,saved)
        assert profile['is_owner'] and profile['csrf_token']
        assert (http.get('/api/v1/me',headers={'Cookie':'c0_session='+old})).status_code==401
