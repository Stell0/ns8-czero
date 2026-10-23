# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable real-provider offline authorization; no token in arguments/output."""
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

EXPECTED = {'configuration_changed':False,'application_content_written':False,'existing_c0_client':True,
    'offline_scope_granted':True,'verified_same_identity':True,'provider_refresh_expires_in':0,
    'owned_provider_logout_completed':True,'initial_offline_access_checked_after_logout':True,
    'refresh_after_owned_logout':True,'new_adapter_offline_renewal_after_logout':True,
    'revoked_refresh_rejected':True,'passed':True,'owned_offline_credentials_revoked':True}


def provider_probe(payload):
    import base64, hashlib, json, os, secrets, ssl, sys
    from html.parser import HTMLParser
    from http.cookiejar import CookieJar
    from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
    from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, HTTPSHandler, Request, build_opener
    from urllib.error import HTTPError
    from authlib.integrations.httpx_client import OAuth2Client
    import httpx2
    from czero_core.oidc import OidcClient, OidcConfig

    config=OidcConfig(os.environ['CZERO_OIDC_ISSUER'],os.environ['CZERO_OIDC_CLIENT_ID'],os.environ['CZERO_OIDC_CLIENT_SECRET'],os.environ['CZERO_AUTH_PUBLIC_ORIGIN'])
    assert config.client_id==payload['module_id'] and config.public_origin==payload['origin']
    oidc=OidcClient(config);metadata=oidc._discovery();refreshes=[]
    proof={'configuration_changed':False,'application_content_written':False,'existing_c0_client':True}
    def origin(url):
     p=urlsplit(url);assert p.scheme=='https' and not p.username and not p.password
     return p.scheme+'://'+p.netloc.lower()
    issuer_origin=origin(config.issuer)
    class Captured(Exception):
     def __init__(self,url):self.url=url
    class Guard(HTTPRedirectHandler):
     def redirect_request(self,request,fp,code,msg,headers,newurl):
      if origin(newurl)==origin(config.public_origin):
       assert urlsplit(newurl).path in ('/auth/callback','/')
       raise Captured(newurl)
      assert origin(newurl)==issuer_origin
      return super().redirect_request(request,fp,code,msg,headers,newurl)
    class Form(HTMLParser):
     def __init__(self):super().__init__();self.action=None;self.fields={};self.form_id=None
     def handle_starttag(self,tag,attrs):
      a=dict(attrs)
      if tag=='form':self.action=a.get('action');self.form_id=a.get('id')
      if tag=='input' and a.get('type')=='hidden' and a.get('name'):self.fields[a['name']]=a.get('value','')
    jar=CookieJar();browser=build_opener(Guard(),HTTPCookieProcessor(jar),HTTPSHandler(context=ssl.create_default_context()))
    def request(url,data=None):
     assert origin(url)==issuer_origin
     req=Request(url,data=None if data is None else urlencode(data).encode(),headers={} if data is None else {'Content-Type':'application/x-www-form-urlencoded'})
     with browser.open(req,timeout=15) as response:return response.read().decode(),response.geturl()
    def provider_post(endpoint,data):
     assert origin(endpoint)==issuer_origin
     return oidc._http.post(endpoint,data=data,auth=httpx2.BasicAuth(config.client_id,config.client_secret))
    try:
     state,nonce,verifier=(secrets.token_urlsafe(32) for _ in range(3))
     with OAuth2Client(config.client_id,config.client_secret,scope='openid profile offline_access',redirect_uri=config.callback_uri,code_challenge_method='S256',timeout=5,follow_redirects=False) as client:
      authorization,_=client.create_authorization_url(metadata['authorization_endpoint'],state=state,nonce=nonce,code_verifier=verifier,prompt='login')
      page,url=request(authorization);form=Form();form.feed(page)
      assert form.form_id=='kc-form-login' and form.action
      fields={**form.fields,'username':payload['username'],'password':payload['password']}
      callback=None
      try:
       page,url=request(urljoin(url,form.action),fields)
       form=Form();form.feed(page)
       assert form.action and form.form_id=='kc-oauth'
       request(urljoin(url,form.action),{**form.fields,'accept':'Yes'})
      except Captured as captured:callback=captured.url
      assert callback and urlsplit(callback).path=='/auth/callback'
      query=parse_qs(urlsplit(callback).query);assert query.get('state')==[state] and len(query.get('code',[]))==1 and 'error' not in query
      tokens=client.fetch_token(metadata['token_endpoint'],grant_type='authorization_code',code=query['code'][0],code_verifier=verifier)
      refreshes.append(tokens['refresh_token'])
      identity=oidc._token_verifier().verify_id_token(tokens['id_token'],nonce=nonce,access_token=tokens['access_token'])
      assert identity.account_key==os.environ['CZERO_OWNER_LDAP_UUID'] and 'offline_access' in tokens.get('scope','').split()
      proof.update({'offline_scope_granted':True,'verified_same_identity':True,'provider_refresh_expires_in':tokens.get('refresh_expires_in')})
      endpoint=metadata['end_session_endpoint'];assert origin(endpoint)==issuer_origin
      try:
       page,url=request(endpoint+'?'+urlencode({'client_id':config.client_id,'id_token_hint':tokens['id_token'],'post_logout_redirect_uri':config.logout_return_uri}))
       form=Form();form.feed(page);assert form.action and form.form_id=='kc-logout-confirm'
       request(urljoin(url,form.action),{**form.fields,'confirm':'yes'})
      except Captured as captured:
       assert urlsplit(captured.url).path=='/'
       proof['owned_provider_logout_completed']=True
      assert proof.get('owned_provider_logout_completed')
      initial_context=oidc._token_verifier()._decode(tokens['id_token'])
      initial_context={key:initial_context[key] for key in ('iss','sub','aud','azp','auth_time') if key in initial_context}
      initial_saved=json.dumps({'access':tokens['access_token'],'refresh':refreshes[-1],'nonce':nonce,'id_context':initial_context,'refresh_after':__import__('time').time()+270,'offline':True})
      initial_checked=oidc.check_renewal(initial_saved)
      assert initial_checked.offline
      refreshes.append(json.loads(initial_checked.credential)['refresh'])
      proof['initial_offline_access_checked_after_logout']=True
      response=provider_post(metadata['token_endpoint'],{'grant_type':'refresh_token','refresh_token':refreshes[-1]})
      assert response.status_code==200
      replacement=response.json();refreshes.append(replacement.get('refresh_token',refreshes[-1]))
      renewed=oidc.verify_access_token(replacement['access_token']);assert renewed.account_key==identity.account_key and renewed.subject==identity.subject
      proof['refresh_after_owned_logout']=True
      original=oidc._token_verifier()._decode(tokens['id_token'])
      original={key:original[key] for key in ('iss','sub','aud','azp','auth_time') if key in original}
      saved=json.dumps({'access':replacement['access_token'],'refresh':refreshes[-1],'nonce':nonce,'id_context':original,'refresh_after':0,'offline':True})
      checked=oidc.check_renewal(saved)
      assert checked.offline and checked.identity.account_key==identity.account_key
      refreshes.append(json.loads(checked.credential)['refresh'])
      proof['new_adapter_offline_renewal_after_logout']=True
      response=provider_post(metadata['revocation_endpoint'],{'token':refreshes[-1],'token_type_hint':'refresh_token'})
      assert response.status_code==200
      response=provider_post(metadata['token_endpoint'],{'grant_type':'refresh_token','refresh_token':refreshes[-1]})
      assert response.status_code in (400,401) and response.json().get('error')=='invalid_grant'
      proof['revoked_refresh_rejected']=True;proof['passed']=True
    except Exception as error:
     proof.update({'passed':False,'error_class':type(error).__name__})
    finally:
     cleanup=[]
     for token in dict.fromkeys(refreshes):
      try:cleanup.append(provider_post(metadata['revocation_endpoint'],{'token':token,'token_type_hint':'refresh_token'}).status_code==200)
      except Exception:cleanup.append(False)
     proof['owned_offline_credentials_revoked']=bool(cleanup) and all(cleanup)
     oidc.close()
    print(json.dumps(proof));raise SystemExit(0 if proof.get('passed') and proof['owned_offline_credentials_revoked'] else 1)


def validate(proof):
    if not isinstance(proof,dict) or proof!=EXPECTED or any(type(proof[key]) is not type(value) for key,value in EXPECTED.items()):
        raise AssertionError('Offline provider evidence invalid')
    return dict(EXPECTED)


def run(module_id):
    from oidc_fixture import STATE
    assert re.fullmatch(r'czero[0-9]+',module_id), 'Invalid disposable module'
    personas=json.loads((STATE/'personas.json').read_text())
    assert personas['host'].endswith('.test'), 'Offline provider probe requires disposable HTTPS'
    payload={'module_id':module_id,'origin':'https://'+personas['host'],
             'username':'c0owner','password':personas['password']}
    source=inspect.getsource(provider_probe)+'\nimport json,sys\nprovider_probe(json.load(sys.stdin))'
    result=subprocess.run(['runagent','-m',module_id,'podman','exec','-i','czero','python','-c',source],
        input=json.dumps(payload).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    assert result.returncode==0, 'Installed offline provider probe failed'
    proof=json.loads(result.stdout)
    print('C0 offline provider: '+json.dumps(validate(proof),sort_keys=True))


if __name__=='__main__':
    try:run(sys.argv[1])
    except Exception as error:
        print('Disposable offline provider failed: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(1)
