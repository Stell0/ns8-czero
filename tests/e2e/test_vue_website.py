# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Vue candidate against genuine HTTPS, cookies, Core, database and extraction."""
from pathlib import Path
from urllib.parse import urlencode
import pytest
from playwright.sync_api import expect, sync_playwright


@pytest.fixture(autouse=True)
def vue_candidate(monkeypatch):
    directory=Path(__file__).resolve().parents[2]/'app/frontend/dist'
    assert (directory/'index.html').is_file(), 'Build the frozen frontend before browser acceptance'
    monkeypatch.setenv('CZERO_FRONTEND_DIR', str(directory))


@pytest.fixture
def vue_browser(live):
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(ignore_https_errors=True)
        context.add_cookies([{'name':'fixture_persona','value':'reader','url':live.origin}])
        page=context.new_page()
        page.goto(live.origin+'/auth/login')
        expect(page.get_by_role('button',name='Knowledge space Shared',exact=True)).to_be_visible()
        yield page
        context.close();browser.close()


def test_vue_actual_source_and_wiki_readback_and_csp(live,vue_browser):
    page=vue_browser
    version=live.upload('# Original evidence\n\nRetained source body.\n\n<script>window.executed=true</script>')
    stored=live.client.call('wiki_pages_create',data={'slug':'manual/setup','title':'Setup manual','body':'# Procedure\n\nAssistant-authored knowledge.','idempotency_key':'vue-readback'})
    errors=[];external=[];writes=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:external.append(request.url) if not request.url.startswith(live.origin) else None)
    page.on('request',lambda request:writes.append(request.url) if request.method!='GET' else None)
    response=page.goto(live.origin+'/wiki/'+stored['id']+'?'+urlencode({'space_id':live.space}))
    assert "script-src 'self'" in response.headers['content-security-policy']
    expect(page.locator('article')).to_contain_text('Assistant-authored knowledge.')
    page.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode({'space_id':live.space}))
    expect(page.locator('article')).to_contain_text('Retained source body.')
    expect(page.locator('article script,article img')).to_have_count(0)
    assert page.evaluate('window.executed') is None
    expect(page.get_by_role('button',name='Upload replacement',exact=True)).to_have_count(0)
    expect(page.get_by_role('link',name='Administration',exact=True)).to_have_count(0)
    assert not errors and not external and not writes


def test_vue_native_signin_form_and_owner_key_lifecycle(live,vue_browser):
    page=vue_browser
    page.context.clear_cookies()
    page.goto(live.origin+'/auth/sign-in')
    expect(page.get_by_role('checkbox',name='Remember this device',exact=True)).not_to_be_checked()
    page.get_by_role('button',name='Continue with NethServer',exact=True).click()
    expect(page.get_by_role('link',name='Administration',exact=True)).to_be_visible()
    page.goto(live.origin+'/account')
    page.get_by_role('button',name='Create API key',exact=True).click()
    dialog=page.get_by_role('dialog')
    from test_nebula_theme import assert_accessibility
    assert_accessibility(page)
    dialog.get_by_role('textbox',name='Name',exact=True).fill('Disposable workflow')
    dialog.get_by_role('checkbox',name='Shared',exact=True).check()
    dialog.get_by_role('button',name='Create API key',exact=True).click()
    expect(page.get_by_role('textbox',name='Copy this key now. It will not be shown again.',exact=True)).to_be_visible()
    key=page.get_by_role('textbox',name='Copy this key now. It will not be shown again.',exact=True).input_value()
    assert key.startswith('c0k_')
    assert live.rest.get('/api/v1/me',headers={'Authorization':'Bearer '+key}).status_code==200
    page.get_by_role('button',name='I saved the key',exact=True).click()
    expect(page.get_by_role('textbox',name='Copy this key now. It will not be shown again.',exact=True)).to_have_count(0)
    expect(page.get_by_role('button',name='Revoke API key',exact=True)).to_be_visible()
    assert_accessibility(page)
    page.get_by_role('button',name='Revoke API key',exact=True).click()
    page.get_by_role('dialog').get_by_role('button',name='Revoke API key',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    assert live.rest.get('/api/v1/me',headers={'Authorization':'Bearer '+key}).status_code==401
    assert key not in page.content()


def test_vue_protected_denial_and_late_response(live,vue_browser):
    page=vue_browser
    version=live.upload('PRIVATE-LATE-BODY')
    live.delay.id=version['source_id']
    page.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode({'space_id':live.space}))
    assert live.delay.captured.wait(10)
    page.goto(live.origin+'/wiki?'+urlencode({'space_id':live.second}))
    expect(page.get_by_text('Sign in or choose a space you can access.',exact=True)).to_be_visible()
    live.delay.release.set()
    expect(page.locator('main')).not_to_contain_text('PRIVATE-LATE-BODY')
    expect(page.get_by_role('heading',name='Knowledge sections',exact=True)).to_have_count(0)


def test_vue_replacement_preserves_published_body_until_ready_and_retires_exact_evidence(live,vue_browser):
    page=vue_browser
    version=live.upload('# Original\n\nPublished-before-replacement.',retain_original='true')
    params={'space_id':live.space}
    before=live.rest.get('/api/v1/source-documents/'+version['source_id'],params=params).json()
    page.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin}])
    page.goto(live.origin+'/auth/login')
    page.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode(params))
    expect(page.locator('article')).to_contain_text('Published-before-replacement.')
    live.pause_worker()
    try:
        page.get_by_role('button',name='Upload replacement',exact=True).click()
        dialog=page.get_by_role('dialog')
        expect(dialog.get_by_role('checkbox',name='Retain the original file',exact=True)).not_to_be_checked()
        dialog.locator('input[type=file]').set_input_files({'name':'replacement.md','mimeType':'text/markdown','buffer':b'# Replacement\n\nValidated-after-replacement.'})
        dialog.get_by_role('button',name='Upload replacement',exact=True).click()
        expect(dialog).to_have_count(0)
        expect(page.locator('article')).to_contain_text('Published-before-replacement.')
        expect(page.get_by_text('A replacement is processing. The published document stays available until validation completes.',exact=True)).to_be_visible()
        pending=live.rest.get('/api/v1/source-documents/'+version['source_id'],params=params).json()
        assert pending['revision_id']==before['revision_id'] and pending['body']==before['body']
    finally:
        live.resume_worker()
    expect(page.locator('article')).to_contain_text('Validated-after-replacement.',timeout=15000)
    after=live.rest.get('/api/v1/source-documents/'+version['source_id'],params=params).json()
    assert after['revision_id']!=before['revision_id'] and after['original_version_ids']==[]
    assert live.rest.get('/api/v1/source-versions/'+version['id']+'/full-document',params=params).status_code==410
    page.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode({**params,'version':version['id']}))
    expect(page.get_by_text('This exact evidence has been superseded and is unavailable.',exact=True)).to_be_visible()
    expect(page.locator('main')).not_to_contain_text('Validated-after-replacement.')
    expect(page.locator('main')).not_to_contain_text('Published-before-replacement.')


def test_vue_unavailable_remembered_signin_and_provider_logout(live,vue_browser):
    page=vue_browser
    page.context.clear_cookies()
    page.goto(live.origin+'/auth/sign-in')
    page.get_by_role('checkbox',name='Remember this device',exact=True).check()
    page.get_by_role('button',name='Continue with NethServer',exact=True).click()
    expect(page.get_by_role('heading',name='Remembered sign-in unavailable',exact=True)).to_be_visible()
    page.get_by_role('link',name='Return to sign-in',exact=True).click()
    expect(page.get_by_role('checkbox',name='Remember this device',exact=True)).not_to_be_checked()
    page.get_by_role('button',name='Continue with NethServer',exact=True).click()
    expect(page.get_by_role('link',name='Administration',exact=True)).to_be_visible()
    profile=page.request.get(live.origin+'/api/v1/me').json()
    assert profile['browser_session']['remembered'] is False
    page.goto(live.origin+'/account')
    page.get_by_role('button',name='Sign out',exact=True).click()
    expect(page.get_by_role('heading',name='Signed out of disposable provider',exact=True)).to_be_visible()
    assert page.request.get(live.origin+'/api/v1/me').status==401
    page.go_back()
    expect(page.get_by_role('button',name='Create API key',exact=True)).to_have_count(0)
    expect(page.get_by_role('link',name='Administration',exact=True)).to_have_count(0)


from test_session_renewal_http import renewing_app


@pytest.fixture
def renewable_live(browser_database,vue_candidate,monkeypatch,request,tmp_path):
    """Real HTTPS C0 with the existing signed, rotating offline-provider fixture."""
    import socket,threading,uvicorn
    from datetime import datetime,timedelta,timezone
    from urllib.parse import urlsplit,parse_qs
    from types import SimpleNamespace
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from fastapi import Request
    from fastapi.responses import RedirectResponse,HTMLResponse
    import test_session_renewal_http
    sock=socket.socket();sock.bind(('127.0.0.1',0))
    origin='https://localhost:'+str(sock.getsockname()[1])
    monkeypatch.setattr(test_session_renewal_http,'ORIGIN',origin)
    app,saved,clock,state=request.getfixturevalue('renewing_app')
    original=app.state.auth.oidc.authorization_url
    def authorization(pending,**kwargs):
        fields=parse_qs(urlsplit(original(pending,**kwargs)).query)
        state['nonce']=fields['nonce'][0]
        state['offline']='offline_access' in fields['scope'][0].split()
        return origin+'/fixture-renewable?'+urlencode({'state':fields['state'][0]})
    monkeypatch.setattr(app.state.auth.oidc,'authorization_url',authorization)
    monkeypatch.setattr(app.state.auth.oidc,'logout_url',lambda:origin+'/fixture-renewable/logout')
    @app.get('/fixture-renewable',include_in_schema=False)
    def provider(state:str):
        return RedirectResponse(origin+'/auth/callback?'+urlencode({'state':state,'code':'private-code'}),status_code=302)
    @app.get('/fixture-renewable/logout',include_in_schema=False)
    def logout():return HTMLResponse('<h1>Signed out of disposable provider</h1>')
    providers=[route for route in app.router.routes if route.path.startswith('/fixture-renewable')]
    app.router.routes[:]=providers+[route for route in app.router.routes if route not in providers]
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]);now=datetime.now(timezone.utc)
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False).sign(key,hashes.SHA256())
    key_path=tmp_path/'renewable-key.pem';cert_path=tmp_path/'renewable-cert.pem'
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));key_path.chmod(0o600)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ready=threading.Event()
    class Server(uvicorn.Server):
        async def startup(self,*args,**kwargs):
            await super().startup(*args,**kwargs);ready.set()
    server=Server(uvicorn.Config(app,log_level='critical',access_log=False,ssl_keyfile=str(key_path),ssl_certfile=str(cert_path)))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    assert ready.wait(15)
    try:yield SimpleNamespace(origin=origin,saved=saved,clock=clock,state=state)
    finally:
        server.should_exit=True;thread.join(15);sock.close()
        key_path.unlink(missing_ok=True);cert_path.unlink(missing_ok=True)
        assert not thread.is_alive()


def test_vue_signed_offline_login_oauth_consent_disconnect_and_logout(renewable_live):
    import secrets
    from urllib.parse import urlsplit,parse_qs
    from czero_core.oauth_grants import pkce_challenge
    live=renewable_live
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(ignore_https_errors=True)
        page=context.new_page()
        try:
            page.goto(live.origin+'/auth/sign-in')
            page.get_by_role('checkbox',name='Remember this device',exact=True).check()
            page.get_by_role('button',name='Continue with NethServer',exact=True).click()
            expect(page.get_by_role('link',name='Administration',exact=True)).to_be_visible()
            assert page.request.get(live.origin+'/api/v1/me').json()['browser_session']['remembered'] is True
            # Real signed renewable responses cross the ordinary browser request path.
            live.clock[0]+=3601
            assert page.request.get(live.origin+'/api/v1/me').status==200
            assert live.state['refreshes']>=1
            callback='https://client.example.test/callback'
            page.route(callback+'**',lambda route:route.fulfill(status=200,body='<h1>Disposable client callback</h1>',content_type='text/html'))
            verifier=secrets.token_urlsafe(32);state=secrets.token_urlsafe(32)
            page.goto(live.origin+'/oauth/authorize?'+urlencode({'client_id':live.saved['client_id'],'redirect_uri':callback,'response_type':'code','code_challenge':pkce_challenge(verifier),'code_challenge_method':'S256','state':state,'scope':'c0:read c0:write','resource':live.origin+'/mcp'}))
            expect(page.get_by_role('checkbox',name='Read',exact=True)).to_be_checked()
            page.get_by_role('checkbox',name='Write',exact=True).uncheck()
            page.get_by_role('button',name='Authorize',exact=True).click()
            expect(page.get_by_role('heading',name='Disposable client callback',exact=True)).to_be_visible()
            result=parse_qs(urlsplit(page.url).query)
            assert result['state']==[state]
            response=page.request.post(live.origin+'/oauth/token',form={'grant_type':'authorization_code','client_id':live.saved['client_id'],'redirect_uri':callback,'code':result['code'][0],'code_verifier':verifier,'resource':live.origin+'/mcp'})
            assert response.status==200
            token=response.json()
            assert token['scope']=='c0:read'
            page.goto(live.origin+'/account')
            page.get_by_role('button',name='Disconnect',exact=True).click()
            page.get_by_role('dialog').get_by_role('button',name='Disconnect',exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)
            assert page.request.get(live.origin+'/api/v1/me',headers={'Authorization':'Bearer '+token['access_token']}).status==401
            page.get_by_role('button',name='Sign out',exact=True).click()
            expect(page.get_by_role('heading',name='Signed out of disposable provider',exact=True)).to_be_visible()
            assert page.request.get(live.origin+'/api/v1/me').status==401
        finally:
            context.close();browser.close()


def test_vue_admin_surfaces_space_creation_and_reader_denial(live,vue_browser):
    page=vue_browser
    page.goto(live.origin+'/admin')
    expect(page.get_by_role('grid')).to_have_count(0)
    page.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin}])
    page.goto(live.origin+'/auth/login')
    failures=[];errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('response',lambda response:failures.append((response.status,response.url.split('/api/v1/')[-1])) if '/api/v1/' in response.url and response.status>=400 and '/oauth/cimd' not in response.url else None)
    page.goto(live.origin+'/admin')
    expect(page.get_by_role('grid')).to_contain_text('member')
    for area in ('advanced','work','spaces'):
        page.goto(live.origin+'/admin/'+area)
        expect(page.get_by_role('heading',name='Administration',exact=True)).to_be_visible()
        expect(page.get_by_text('Cannot load content',exact=True)).to_have_count(0)
    page.get_by_role('textbox',name='Name',exact=True).fill('Browser-created protected space')
    page.get_by_role('button',name='Create protected space',exact=True).click()
    expect(page.get_by_role('button',name='Knowledge space Browser-created protected space',exact=True)).to_be_visible()
    expect(page.get_by_role('button',name='member No protected-space grant',exact=True)).to_be_visible()
    space=next(row for row in live.rest.get('/api/v1/spaces').json()['spaces'] if row['name']=='Browser-created protected space')
    assert not space['shared']
    assert live.rest.get('/api/v1/spaces/'+space['id'],headers={'Authorization':'Bearer '+live.member}).status_code==403
    assert not failures and not errors


def test_vue_admin_can_identify_and_inspect_each_queued_job(live,vue_browser):
    page=vue_browser
    page.context.clear_cookies();page.goto(live.origin+'/auth/login')
    page.goto(live.origin+'/admin/work')
    for _ in range(2):
        page.get_by_role('button',name='Queue job',exact=True).click()
        dialog=page.get_by_role('dialog')
        dialog.get_by_role('button',name='Handler',exact=False).click()
        page.get_by_role('option',name='health',exact=True).click()
        dialog.get_by_role('textbox',name='Parameters (JSON)',exact=True).fill('{}')
        dialog.get_by_role('button',name='Queue job',exact=True).click()
        expect(dialog).to_have_count(0)
    jobs=[row for row in live.rest.get('/api/v1/jobs').json()['jobs'] if row['handler']=='health']
    assert len(jobs)==2 and jobs[0]['id']!=jobs[1]['id']
    for job in jobs:
        row=page.locator('main li').filter(has_text=job['id'])
        expect(row).to_be_visible()
        row.get_by_role('button',name='Details',exact=True).click()
        expect(page.locator('main pre')).to_contain_text(job['id'])
