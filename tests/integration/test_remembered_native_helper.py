# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the exact native sign-in helper against signed-provider app HTTP.

Actual provider HTTPS, native recovery and Chromium remain full CI gates.
"""
from pathlib import Path
from urllib.parse import parse_qs,urljoin,urlsplit

from fastapi.testclient import TestClient

from test_session_renewal_http import renewing_app
from test_auth_http import ORIGIN


def test_exact_native_form_helper_verifies_offline_issuance_and_cookie(renewing_app,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
    from remembered_fixture import sign_in
    app,_,_,state=renewing_app
    issuer=app.state.auth.oidc.config.issuer
    with TestClient(app,base_url=ORIGIN,follow_redirects=False) as http:
        class Browser:
            origin=ORIGIN
            cookies=http.cookies.jar
            pending=None
            def request(self,path,data=None,method=None,headers=None):
                target=urljoin(ORIGIN,path)
                if target.startswith(issuer+'/authorize?'):
                    fields=parse_qs(urlsplit(target).query)
                    assert fields['scope']==['openid profile offline_access']
                    state['nonce']=fields['nonce'][0];state['offline']=True;self.pending=fields['state'][0]
                    return 200,b'<form id="kc-form-login" action="/synthetic-login"></form>',target
                if urlsplit(target).netloc==urlsplit(issuer).netloc:
                    assert parse_qs(data.decode())=={'username':['c0owner'],'password':['synthetic-password']}
                    response=http.get('/auth/callback',params={'state':self.pending,'code':'private-code'},follow_redirects=True)
                else:
                    response=http.request(method or ('POST' if data is not None else 'GET'),target,content=data,headers=headers or {})
                    if response.status_code==302:
                        return self.request(response.headers['location'])
                return response.status_code,response.content,str(response.url)
            def api(self,path):
                return self.request(path,headers={'Origin':ORIGIN})
        profile,cookie=sign_in(Browser(),'synthetic-password')
        assert profile['browser_session']=={'remembered':True,'idle_seconds':604800}
        assert bool(cookie) and state['checks']>=1
