# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real loopback HTTPS/MCP/PostgreSQL/worker with existing signed SSO identities."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import shutil
import ssl
import sys
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlencode
from uuid import uuid4
import zipfile

import httpx
import httpx2
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

class PrivateLive(SimpleNamespace):
    def __repr__(self):return '<private disposable browser fixture>'


ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tests/integration'),str(ROOT/'samples/ingestion/src')]
from test_auth_http import application
from test_knowledge_http import knowledge_http
from test_spaces_http import space_http
from test_mcp_http import transport
from c0_ingest import auth
from c0_ingest.client import C0, CredentialAuth
from c0_projects.model import Item, sha
from c0_projects.publish import parts, sync_part, save_snapshot
from test_project_ingestion_http import setup
from czero_core.worker import Worker


@pytest.fixture
def browser_database(monkeypatch):
    url=os.getenv('CZERO_TEST_DATABASE_URL')
    if not url:pytest.fail('CZERO_TEST_DATABASE_URL with disposable CREATE DATABASE authority is required')
    parsed=make_url(url);name='c0_browser_'+uuid4().hex
    engine=create_engine(parsed,hide_parameters=True)
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.execute(text('CREATE DATABASE '+name))
    monkeypatch.setenv('CZERO_TEST_DATABASE_URL',parsed.set(database=name).render_as_string(hide_password=False))
    try:yield
    finally:
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
        engine.dispose()


@pytest.fixture
def live(browser_database,request,monkeypatch,tmp_path):
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin='https://localhost:'+str(port)
    import test_auth_http, test_mcp_http
    monkeypatch.setattr(test_auth_http,'ORIGIN',origin)
    for field,value in [('ORIGIN',origin),('RESOURCE',origin+'/mcp'),('ISSUER',origin+'/oauth')]:monkeypatch.setattr(test_mcp_http,field,value)
    fixture=request.getfixturevalue('transport')
    request.getfixturevalue('knowledge_http');spaces=request.getfixturevalue('space_http')
    app, _, _, descriptor, pair, _, owner, member=fixture
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    now=datetime.now(timezone.utc)
    cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False).sign(key,hashes.SHA256())
    cert_path=tmp_path/'tls.pem';key_path=tmp_path/'tls-key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));key_path.chmod(0o600)
    # Only the disposable provider is controlled. C0's signed callback/session,
    # cookie, CSRF, current-role and space checks are the real application code.
    monkeypatch.setattr(app.state.auth.oidc,'authorization_url',lambda pending,**_:origin+'/fixture-provider?'+urlencode({'state':pending.state}))
    from fastapi import Request
    from fastapi.responses import RedirectResponse
    @app.get('/fixture-provider',include_in_schema=False)
    def provider(request:Request,state:str):
        code='unit-only-forbidden-code' if request.cookies.get('fixture_persona')=='reader' else 'owner-code'
        return RedirectResponse(origin+'/auth/callback?'+urlencode({'state':state,'code':code}),status_code=302)
    monkeypatch.setattr(app.state.auth.oidc,'logout_url',lambda:origin+'/fixture-provider/logout')
    @app.get('/fixture-provider/logout',include_in_schema=False)
    def provider_logout():
        from fastapi.responses import HTMLResponse
        return HTMLResponse('<h1>Signed out of disposable provider</h1>')
    # The real MCP transport is mounted last at '/', so register the disposable
    # provider ahead of that catch-all without replacing any C0 route.
    providers=[route for route in app.router.routes if route.path in ('/fixture-provider','/fixture-provider/logout')]
    app.router.routes[:]=providers+[route for route in app.router.routes if route not in providers]
    delay=SimpleNamespace(id=None,captured=threading.Event(),release=threading.Event())
    async def delayed_app(scope,receive,send):
        if scope['type']=='http' and delay.id and scope['path']=='/api/v1/source-documents/'+delay.id:
            import asyncio
            messages=[]
            async def capture(message):messages.append(message)
            await app(scope,receive,capture)
            delay.captured.set()
            await asyncio.to_thread(delay.release.wait,20)
            for message in messages:await send(message)
        else:await app(scope,receive,send)
    ready=threading.Event();stop=threading.Event();condition=threading.Condition();errors=[]
    class Server(uvicorn.Server):
        async def startup(self,*args,**kwargs):
            await super().startup(*args,**kwargs);ready.set()
    server=Server(uvicorn.Config(delayed_app,log_level='critical',access_log=False,ssl_keyfile=str(key_path),ssl_certfile=str(cert_path)))
    worker=None;client=None;rest=None
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    def shutdown():
        delay.release.set();stop.set()
        if worker is not None:worker.join(35)
        try:
            if client is not None:client.close()
            if rest is not None:rest.close()
        finally:
            server.should_exit=True;thread.join(15);sock.close()
            for private in (key_path,cert_path,tmp_path/'oauth.json'):
                private.unlink(missing_ok=True)
            originals=app.state.sources.originals.root.resolve()
            if originals.is_relative_to(tmp_path.resolve()):shutil.rmtree(originals,ignore_errors=True)
        assert (worker is None or not worker.is_alive()) and not thread.is_alive(),'Disposable server/worker failed to stop'
        assert not errors,'Disposable worker failed'
    request.addfinalizer(shutdown)
    assert ready.wait(15),'Disposable HTTP server did not start'
    worker_control=SimpleNamespace(paused=threading.Event(),idle=threading.Event())
    def pause_worker():
        worker_control.paused.set()
        assert worker_control.idle.wait(35),'Worker did not reach a bounded pause'
    def resume_worker():worker_control.paused.clear()
    def work():
        try:
            while not stop.is_set():
                if worker_control.paused.is_set():
                    worker_control.idle.set();stop.wait(.05);continue
                worker_control.idle.clear()
                completed=subprocess.run([sys.executable,'-m','czero_app.worker'],capture_output=True,timeout=30,
                    env={**os.environ,'CZERO_DATABASE_URL':os.environ['CZERO_TEST_DATABASE_URL'],'CZERO_SOURCE_DIR':str(app.state.sources.originals.root)})
                if completed.returncode:raise RuntimeError('Standalone extraction worker failed')
                with condition:condition.notify_all()
                stop.wait(.1)
        except BaseException as error:errors.append(type(error).__name__)
    worker=threading.Thread(target=work,daemon=True);worker.start()
    rest=httpx.Client(base_url=origin,verify=ssl.create_default_context(cafile=str(cert_path)),headers={'Authorization':'Bearer '+owner},timeout=30)
    @asynccontextmanager
    async def connection(config):
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        async with httpx2.AsyncClient(auth=CredentialAuth(config),verify=ssl.create_default_context(cafile=str(cert_path)),follow_redirects=False) as http:
            async with Client(streamable_http_client(config['url'],http_client=http)) as client:yield client
    monkeypatch.setattr('c0_ingest.client.connection',connection)
    http_client=httpx2.Client
    def trusted_http(*args,**kwargs):
        kwargs.setdefault('verify',ssl.create_default_context(cafile=str(cert_path)))
        return http_client(*args,**kwargs)
    monkeypatch.setattr(httpx2,'Client',trusted_http)
    private=rest.post('/api/v1/spaces',json={'name':'Synthetic documentation','idempotency_key':'private'}).json();spaces[1].append(private['id'])
    second=rest.post('/api/v1/spaces',json={'name':'Other protected documents','idempotency_key':'second'}).json();spaces[1].append(second['id'])
    profile=rest.get('/api/v1/profile').json()
    config={'url':origin+'/mcp','client_id':descriptor['client_id'],'credentials_file':str(tmp_path/'oauth.json'),
        'identity':profile['nickname'],'account_id':profile['id'],'scopes':'c0:read c0:write c0:admin','space_id':private['id']}
    auth.save_tokens(config,{'access_token':pair.access_token,'refresh_token':pair.refresh_token,'expires_in':pair.expires_in})
    client,definition=setup(config)
    denied=rest.get('/api/v1/me',headers={'Authorization':'Bearer '+member});assert denied.status_code==403
    account=next(a for a in rest.get('/api/v1/access/accounts').json()['accounts'] if a['username']=='member')
    assert rest.put('/api/v1/access/accounts/'+account['id'],json={'role':'reader'}).status_code==204
    grant_path='/api/v1/spaces/'+private['id']+'/grants/'+account['id']
    assert rest.put(grant_path,json={'role':'reader','expected_revision':0,'idempotency_key':'reader'}).status_code==200
    def upload(body,title='Firewall manual',media='text/markdown',space=None,**values):
        result=rest.post('/api/v1/sources/upload',params={'space_id':space or private['id']},
            data={'title':title,'media_type':media,'metadata':json.dumps({'canonical_url':'https://example.org/manual','provenance':{'product':'Synthetic product','version':'8','path':['Administrator Manual','Configuration']}}),**values},
            files={'file':('manual.md',body.encode(),media)})
        assert result.status_code==202
        version=result.json();deadline=time.monotonic()+20
        with condition:
            while True:
                versions=rest.get('/api/v1/sources/'+version['source_id']+'/versions',params={'space_id':space or private['id']}).json()['versions']
                current=next(v for v in versions if v['id']==version['id'])
                if current['state']=='ready':return current
                assert current['state']!='failed','Actual extraction worker failed'
                remaining=deadline-time.monotonic();assert remaining>0,'Actual extraction worker did not become ready'
                condition.wait(remaining)
    def publish(body,*,legacy=True):
        item=Item('documents','legacy-manual.md','Complete legacy manual',body.encode(),'text/markdown',canonical_url='https://example.org/legacy-manual',
            provenance={'product':'Synthetic product','version':'8','path':['Administrator Manual','Configuration']})
        results=[sync_part(client,part,tmp_path/'parts.json',definition_hash=sha(definition),attempts=100,seconds=.1) for part in parts(item,limit=131072 if legacy else None)]
        return save_snapshot(client,item,results),results
    def legacy_metadata(receipts):
        # Older imports can have verified receipts without a source metadata
        # parent hint. Preserve real bodies/versions/receipts; simulate that shape.
        with app.state.sources.database.engine.begin() as connection:
            result=connection.execute(text("UPDATE c0_sources SET metadata=metadata-'parent_external_id' WHERE space_id=:space AND id=ANY(CAST(:ids AS uuid[]))"),
                {'space':private['id'],'ids':[row['source_id'] for row in receipts]})
            assert result.rowcount==len(receipts)
    value=PrivateLive(origin=origin,rest=rest,client=client,definition=definition,space=private['id'],second=second['id'],upload=upload,publish=publish,legacy_metadata=legacy_metadata,
        member=member,grant_path=grant_path,errors=errors,tmp=tmp_path,delay=delay,pause_worker=pause_worker,resume_worker=resume_worker)
    yield value


@pytest.fixture
def browser(live,request,tmp_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        chromium=playwright.chromium.launch(headless=True)
        context=chromium.new_context(ignore_https_errors=True)
        context.add_cookies([{'name':'fixture_persona','value':'reader','url':live.origin}])
        page=context.new_page()
        response=page.goto(live.origin+'/auth/login')
        from urllib.parse import urlsplit
        if response.status!=200:pytest.fail('Browser sign-in failed at '+urlsplit(page.url).path+' with HTTP '+str(response.status),pytrace=False)
        if urlsplit(page.url).path!='/':pytest.fail('Browser sign-in ended at '+urlsplit(page.url).path,pytrace=False)
        page.wait_for_url(live.origin+'/')
        page.locator('#sign-out').wait_for(state='visible')
        context.tracing.start(screenshots=False,snapshots=True,sources=False)
        yield page
        if getattr(request.node,'rep_call',None) and request.node.rep_call.failed:
            directory=Path(os.getenv('CZERO_BROWSER_ARTIFACTS',str(tmp_path/'failure')));directory.mkdir(mode=0o700,parents=True,exist_ok=True)
            page.screenshot(path=str(directory/(request.node.name+'.png')),full_page=False)
            raw=tmp_path/'private-trace.zip';context.tracing.stop(path=str(raw))
            # Keep actions/DOM snapshots only. Network events/resources can contain
            # cookies, CSRF values and OAuth responses and are never uploaded.
            with zipfile.ZipFile(raw) as source,zipfile.ZipFile(directory/(request.node.name+'.zip'),'w') as target:
                for name in source.namelist():
                    if name.endswith('.trace'):target.writestr(name,source.read(name))
            raw.unlink()
        else:context.tracing.stop()
        context.close();chromium.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    result=yield
    setattr(item,'rep_'+result.get_result().when,result.get_result())


@pytest.fixture
def documentation_site(monkeypatch):
    """Real HTTP origin in isolated test transport; no production bypass option."""
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    state=SimpleNamespace(body='',requests=[],etag='"generation-1"',fail=False)
    origin='http://documentation.example.org'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            state.requests.append((self.path,self.headers.get('If-None-Match')))
            status=200;media='text/html; charset=utf-8'
            if self.path=='/robots.txt':body='User-agent: *\nDisallow: /manual/denied\nSitemap: '+origin+'/sitemap.xml\n';media='text/plain'
            elif self.path=='/sitemap.xml':body='<urlset><url><loc>'+origin+'/manual/article</loc></url></urlset>';media='application/xml'
            elif self.path=='/manual/article':
                if state.fail:status=503;body='Temporary origin failure'
                elif self.headers.get('If-None-Match')==state.etag:status=304;body=''
                else:body=state.body
            else:status=404;body='Not found'
            data=body.encode();self.send_response(status);self.send_header('Content-Type',media)
            self.send_header('Content-Length',str(len(data)))
            if self.path=='/manual/article':self.send_header('ETag',state.etag)
            self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    real_resolve=socket.getaddrinfo;real_connect=socket.create_connection
    # DNS and socket redirection are confined to this synthetic hostname. The
    # actual Fetcher still runs every public-DNS, redirect/path and robots check.
    def resolve(host,port,*args,**kwargs):
        if host=='documentation.example.org':return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('1.1.1.1',port))]
        return real_resolve(host,port,*args,**kwargs)
    def connect(address,*args,**kwargs):
        if address==('1.1.1.1',80):address=('127.0.0.1',server.server_port)
        return real_connect(address,*args,**kwargs)
    monkeypatch.setattr(socket,'getaddrinfo',resolve);monkeypatch.setattr(socket,'create_connection',connect)
    yield SimpleNamespace(origin=origin,state=state)
    server.shutdown();server.server_close();thread.join(5)
