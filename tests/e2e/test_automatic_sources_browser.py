# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from urllib.parse import urlencode
from playwright.sync_api import expect
from test_nebula_theme import assert_accessibility


def test_automatic_source_form_theme_keyboard_and_real_persistence(live,browser):
    browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/automatic-sources?'+urlencode({'space_id':live.space}))
    expect(browser.get_by_role('heading',name='Automatic sources',exact=True)).to_be_visible()
    browser.get_by_role('button',name='Add automatic source',exact=True).press('Enter')
    dialog=browser.get_by_role('dialog')
    for theme in ('light','dark'):
        browser.emulate_media(color_scheme=theme)
        for width in (1440,390):
            browser.set_viewport_size({'width':width,'height':1000})
            assert_accessibility(browser)
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
    dialog.get_by_role('button',name='Source type Website').press('Enter')
    browser.get_by_role('option',name='GitHub',exact=True).press('Enter')
    dialog.get_by_role('textbox',name='Title',exact=True).fill('Public docs fixture')
    dialog.get_by_role('textbox',name='Repositories (owner/repository_name)',exact=True).fill('synthetic/example')
    dialog.get_by_role('button',name='Save configuration',exact=True).click()
    expect(dialog).to_have_count(0)
    expect(browser.get_by_text('Public docs fixture',exact=False)).to_be_visible()
    browser.reload()
    expect(browser.get_by_text('Public docs fixture',exact=False)).to_be_visible()
    # Reader visibility uses actual signed SSO and selected-space grants.
    browser.context.clear_cookies()
    browser.context.add_cookies([{'name':'fixture_persona','value':'reader','url':live.origin}])
    browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/automatic-sources?'+urlencode({'space_id':live.space}))
    expect(browser.get_by_text('Public docs fixture',exact=False)).to_be_visible()
    expect(browser.get_by_role('button',name='Add automatic source',exact=True)).to_have_count(0)
    expect(browser.get_by_role('button',name='Edit source',exact=True)).to_have_count(0)
    browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/automatic-sources?'+urlencode({'space_id':live.space}))
    browser.get_by_role('button',name='Remove configuration',exact=True).click()
    browser.get_by_role('dialog').get_by_role('button',name='Remove configuration',exact=True).press('Enter')
    expect(browser.get_by_role('dialog')).to_have_count(0)
    expect(browser.get_by_text('Public docs fixture',exact=False)).to_have_count(0)


def test_native_worker_collects_pinned_public_github_original(live,browser,tmp_path):
    import os
    import subprocess
    import sys
    from sqlalchemy import text
    from czero_core.database import Database
    revision='6845d45252a73327b7eabce38fe28fdc81e3e5d0'
    expected='5fa2fb198fbdc0b194d618c210b2c0e2c9397294cb94496b7fd4cf333a0cb680'
    owner=live.rest.get('/api/v1/me').json()
    assert owner['is_owner']
    database=Database(os.environ['CZERO_TEST_DATABASE_URL'])
    try:
        with database.engine.connect() as c:
            identity=c.execute(text('SELECT issuer,account_key FROM c0_accounts WHERE id=:id'),{'id':owner['id']}).mappings().one()
    finally:database.close()
    live.pause_worker()
    result=live.rest.post('/api/v1/automatic-sources',params={'space_id':live.space},json={
        'name':'Pinned public README','kind':'github','config':{'repositories':['Stell0/ns8-czero'],'include':['files'],'paths':['README.md'],'ref':revision},
        'enabled':True,'interval_seconds':None,'idempotency_key':'pinned-public-readme'})
    assert result.status_code==200,result.text
    identifier=result.json()['id']
    try:
        environment={key:value for key,value in os.environ.items() if key!='CZERO_TEST_GITHUB_TOKEN'}
        environment.update({'CZERO_DATABASE_URL':os.environ['CZERO_TEST_DATABASE_URL'],
            'CZERO_OIDC_ISSUER':identity['issuer'],'CZERO_OWNER_LDAP_UUID':str(identity['account_key']),
            'CZERO_SOURCE_DIR':str(live.originals.root)})
        token=os.getenv('CZERO_TEST_GITHUB_TOKEN')
        if token:
            credential=tmp_path/'github-token'
            descriptor=os.open(credential,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w') as stream:stream.write(token)
            environment['CZERO_GITHUB_TOKEN_FILE']=str(credential)
        for _ in range(2):
            worker=subprocess.run([sys.executable,'-m','czero_app.worker'],env=environment,capture_output=True,text=True,timeout=130)
            assert worker.returncode==0,'Native source worker failed; keep its private diagnostics'
        runs=live.rest.get('/api/v1/automatic-sources/'+identifier+'/runs',params={'space_id':live.space}).json()['runs']
        assert runs[0]['state']=='complete',runs[0]['error_code']
        documents=live.rest.get('/api/v1/automatic-sources/'+identifier+'/documents',params={'space_id':live.space}).json()['documents']
        assert len(documents)==1
        document=live.rest.get('/api/v1/source-documents/'+documents[0]['id'],params={'space_id':live.space})
        assert document.status_code==200
        original=document.json()
        assert original['content_hash']==expected and original['state']=='ready'
        assert revision in original['metadata']['original_url']
        browser.goto(live.origin+'/sources/'+documents[0]['id']+'?'+urlencode({'space_id':live.space}))
        expect(browser.get_by_role('article')).to_contain_text('self-hosted knowledge service')
    finally:
        (tmp_path/'github-token').unlink(missing_ok=True)
        response=live.rest.post('/api/v1/automatic-sources/'+identifier+'/actions',params={'space_id':live.space},json={'action':'remove','expected_revision':1,'idempotency_key':'remove-pinned-public-readme'})
        assert response.status_code==200
        live.resume_worker()


def test_browser_collects_and_reads_a_public_pdf(live, browser, tmp_path, monkeypatch):
    import hashlib
    import os
    from pathlib import Path
    import runpy
    import socket
    import ssl
    import subprocess
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from sqlalchemy import text
    from czero_core.automatic_sources import AutomaticSourceService
    from czero_core.source_updates import SourceUpdater
    from czero_core.worker import Worker

    origin = 'https://publisher.example.org'
    certificate, key = tmp_path / 'publisher.pem', tmp_path / 'publisher.key'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-subj', '/CN=publisher.example.org', '-addext', 'subjectAltName=DNS:publisher.example.org',
        '-keyout', str(key), '-out', str(certificate)], check=True, capture_output=True)
    path = tmp_path / 'notice.pdf'
    generator = Path(__file__).resolve().parents[1] / 'fixtures/evidence/pipeline/generate.py'
    runpy.run_path(str(generator))['pdf'](path, ['Synthetic browser publication'])
    pdf = path.read_bytes()
    requests = []

    class Publisher(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append(self.path)
            result = {
                '/robots.txt': ('text/plain', b'User-agent: *\nAllow: /'),
                '/notices': ('text/html', b'<title>Official notices</title><main><h1>Official notices</h1>'
                    b'<a href="/files/notice.pdf">Featured</a><a href="/files/notice.pdf#top">Archive</a></main>'),
                '/files/notice.pdf': ('application/pdf', pdf),
            }.get(self.path)
            if result is None:
                self.send_error(404)
                return
            media, body = result
            self.send_response(200)
            self.send_header('Content-Type', media)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Publisher)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(certificate, key)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    resolve, connect = socket.getaddrinfo, socket.create_connection
    monkeypatch.setattr(socket, 'getaddrinfo', lambda host, port, *a, **k:
        [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.1.1.1', port))] if host == 'publisher.example.org'
        else resolve(host, port, *a, **k))
    monkeypatch.setattr(socket, 'create_connection', lambda addr, *a, **k:
        connect(('127.0.0.1', server.server_port) if addr == ('1.1.1.1', 443) else addr, *a, **k))
    monkeypatch.setenv('SSL_CERT_FILE', str(certificate))
    live.pause_worker()
    database = None
    args = {'space_id': live.space}
    try:
        browser.context.clear_cookies()
        browser.goto(live.origin + '/auth/login')
        browser.goto(live.origin + '/automatic-sources?' + urlencode(args))
        browser.get_by_role('button', name='Add automatic source', exact=True).click()
        drawer = browser.get_by_role('dialog')
        drawer.get_by_role('textbox', name='Title', exact=True).fill('Synthetic public website')
        drawer.get_by_role('textbox', name='Starting URLs', exact=True).fill(origin + '/notices')
        drawer.get_by_text('Collect PDF attachments', exact=True).click()
        drawer.get_by_role('textbox', name='Approved attachment URLs', exact=True).fill(origin + '/files')
        drawer.get_by_role('button', name='Preview', exact=True).click()
        expect(drawer.get_by_text('PDF selected', exact=False)).to_have_count(1)
        assert live.rest.get('/api/v1/automatic-sources', params=args).json()['definitions'] == []
        drawer.get_by_text('Enable source updates', exact=True).click()
        drawer.get_by_role('button', name='Save configuration', exact=True).click()
        expect(drawer).to_have_count(0)
        browser.get_by_role('button', name='Update now', exact=True).click()
        definitions = live.client.call('automatic_sources_list')['definitions']
        assert len(definitions) == 1
        identifier = definitions[0]['id']
        # Run the genuine collector, standard worker and database fences in the
        # test process so the HTTPS origin mapping stays scoped to this fixture.
        from uuid import UUID
        from czero_core.access import AccessService
        from czero_core.database import Database
        from czero_core.jobs import default_registry
        from czero_core.sources import SourceService, register_source_handlers
        database = Database(os.environ['CZERO_TEST_DATABASE_URL'])
        owner = live.rest.get('/api/v1/me').json()['id']
        with database.engine.connect() as connection:
            identity = connection.execute(text('SELECT issuer,account_key FROM c0_accounts WHERE id=:id'),
                                          {'id': owner}).mappings().one()
        access = AccessService(database, identity['issuer'], UUID(str(identity['account_key'])))
        registry = default_registry()
        register_source_handlers(registry, database, live.originals, access=access)
        service = AutomaticSourceService(database, access)
        sources = SourceService(database, access, registry, live.originals)
        for _ in range(4):
            SourceUpdater(service, sources).tick()
            Worker(database, registry).tick()
        runs = live.client.call('automatic_source_runs_list', identifier=identifier)['runs']
        assert runs[0]['state'] == 'complete', runs
        assert runs[0]['diagnostics']['pdf']['published'] == 1
        docs = live.client.call('automatic_source_documents_list', identifier=identifier)['documents']
        assert len(docs) == 2 and requests.count('/files/notice.pdf') == 2  # One preview and one run.
        document = next(row for row in docs if row['title'] == 'notice.pdf')
        full = live.client.call('source_documents_get', logical_document_id=document['id'])
        assert full['content_hash'] == hashlib.sha256(pdf).hexdigest()
        part = full['parts'][0]
        original = live.rest.get('/api/v1/source-versions/' + part['version_id'] + '/original', params=args)
        assert original.status_code == 200 and original.content == pdf
        chunk = live.client.call('document_chunks_list', document_id=part['document_id'])['chunks'][0]
        citation = live.client.call('citations_get', chunk_id=chunk['id'])
        assert citation['version_id'] == part['version_id']
        browser.get_by_role('button', name='Recent runs', exact=True).click()
        browser.get_by_role('link', name='notice.pdf', exact=True).click()
        expect(browser.get_by_role('article')).to_contain_text('Synthetic browser publication')
        browser.goto(live.origin + '/sources?' + urlencode(args))
        browser.get_by_role('button', name='Inspect ingestion', exact=True).click()
        diagnostics = browser.get_by_role('row').filter(has_text='Open the current document.')
        expect(diagnostics.get_by_role('link', name='notice.pdf', exact=True)).to_be_visible()
    finally:
        for definition in live.rest.get('/api/v1/automatic-sources', params=args).json()['definitions']:
            assert live.rest.post('/api/v1/automatic-sources/' + definition['id'] + '/actions',
                params=args, json={'action': 'remove', 'expected_revision': definition['revision'],
                                   'idempotency_key': 'remove-synthetic-website'}).status_code == 200
        if database is not None:
            database.close()
        live.resume_worker()
        server.shutdown()
        server.server_close()
        thread.join(5)
