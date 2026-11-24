# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from uuid import UUID
from urllib.parse import parse_qs, urlsplit

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text

from czero_core.worker import Worker
from test_auth_http import application, ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def source_http(application, tmp_path):
    app = application[0]
    app.state.sources.originals.root = tmp_path / 'sources'
    created = []
    with application[4].engine.begin() as c:
        schedules = [dict(row) for row in c.execute(text('SELECT id,enabled,next_run_at FROM c0_scheduled_tasks')).mappings()]
        c.execute(text('UPDATE c0_scheduled_tasks SET enabled=false'))
    yield application, created
    db = application[4]
    with db.engine.begin() as c:
        for key in created:
            ids = c.execute(text("SELECT id FROM c0_source_versions WHERE source_id=:id UNION SELECT id FROM c0_content_tombstones WHERE kind='source_version' AND resource_id=:id"), {'id': key}).scalars().all()
            c.execute(text('DELETE FROM c0_chunks WHERE document_id IN (SELECT id FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id))'), {'id': key})
            c.execute(text('DELETE FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id)'), {'id': key})
            c.execute(text('DELETE FROM c0_source_versions WHERE source_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_sources WHERE id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_content_tombstones WHERE resource_id=:id'), {'id':key})
            c.execute(text('DELETE FROM c0_original_cleanup WHERE version_id=ANY(CAST(:ids AS uuid[]))'), {'ids':ids})
            for version in ids:
                c.execute(text("DELETE FROM c0_jobs WHERE payload->>'version_id'=:id"), {'id': str(version)})
        for row in schedules:
            c.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled,next_run_at=:next_run_at WHERE id=:id'), row)


def test_signed_upload_worker_full_text_citation_search_reference_and_dedup(source_http):
    async def check():
        application, created = source_http
        app, owner, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get('/api/v1/sources')).status_code == 401
            client.headers['Authorization'] = 'Bearer ' + owner
            content = '# Inventory\n\nEvidence café 東京'
            fields = {'title': 'Inventory', 'media_type': 'text/markdown'}
            response = await client.post('/api/v1/sources/upload', data=fields, files={'file': ('../../display.md', content.encode())})
            assert response.status_code == 202
            version = response.json()
            created.append(version['source_id'])
            assert version['state'] == 'queued' and version['original_present']
            assert (await client.get('/api/v1/source-versions/' + version['id'] + '/document')).status_code == 404
            source = (await client.get('/api/v1/sources/' + version['source_id'])).json()
            assert source['revision'] == 1 and source['title'] == 'Inventory'
            Worker(application[4], app.state.jobs.registry).tick()
            versions = (await client.get('/api/v1/sources/' + source['id'] + '/versions')).json()['versions']
            assert versions[0]['state'] == 'ready' and not versions[0]['original_present']
            document = (await client.get('/api/v1/source-versions/' + version['id'] + '/document')).json()
            assert document['body'] == content
            chunk = (await client.get('/api/v1/documents/' + document['id'] + '/chunks')).json()['chunks'][0]
            citation = (await client.get('/api/v1/chunks/' + chunk['id'] + '/citation')).json()
            assert citation['body'] == content and citation['source_hash'] == version['content_hash']
            assert (await client.get('/api/v1/sources/search', params={'query': 'Inventory'})).json()['citations'][0]['chunk_id'] == chunk['id']
            for kind, key in [('source', source['id']), ('document', document['id']), ('chunk', chunk['id'])]:
                ref = await client.get('/api/v1/references/' + kind + '/' + key, params={'type_name': kind})
                assert ref.status_code == 200 and ref.json()['id'] == key
            duplicate = await client.post('/api/v1/sources/upload', data={**fields, 'source_id': source['id'], 'expected_revision': '1'}, files={'file': ('copy.md', content.encode())})
            assert duplicate.status_code == 202 and duplicate.json()['id'] == version['id']
            assert (await client.delete('/api/v1/sources/' + source['id'], params={'expected_revision': 7})).status_code == 409
            deleted = await client.delete('/api/v1/sources/' + source['id'], params={'expected_revision': 1})
            assert deleted.status_code == 200 and deleted.json()['deleted']
            assert (await client.get('/api/v1/chunks/' + chunk['id'] + '/citation')).json()['deleted']
            assert (await client.get('/api/v1/sources/search', params={'query': 'Inventory'})).json()['citations'] == []
            schema = (await client.get('/openapi.json')).json()
            assert schema['paths']['/api/v1/chunks/{chunk_id}/citation']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/CitationView')
    asyncio.run(check())


def test_source_roles_revocation_cookie_csrf_and_failed_original_retry(source_http):
    async def check():
        application, created = source_http
        app, owner, member, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.headers['Authorization'] = 'Bearer ' + owner
            fields = {'title': 'Failed fixture', 'media_type': 'text/plain'}
            uploaded = await client.post('/api/v1/sources/upload', data=fields, files={'file': ('invalid.txt', b'\xff')})
            assert uploaded.status_code == 202
            row = uploaded.json(); created.append(row['source_id'])
            Worker(application[4], app.state.jobs.registry).tick()
            versions = (await client.get('/api/v1/sources/' + row['source_id'] + '/versions')).json()['versions']
            assert versions[0]['state'] == 'failed' and versions[0]['error_code'] == 'invalid_text'
            assert app.state.sources.originals.path(UUID(row['id'])).read_bytes() == b'\xff'
            original = await client.get('/api/v1/source-versions/' + row['id'] + '/original')
            assert original.status_code == 200 and original.content == b'\xff'
            assert original.headers['content-type'] == 'application/octet-stream'
            assert original.headers['content-disposition'].startswith('attachment;')
            assert (await client.post('/api/v1/source-versions/' + row['id'] + '/retry', json={'expected_generation': 1})).status_code == 202
            assert (await client.post('/api/v1/source-versions/' + row['id'] + '/retry', json={'expected_generation': 1})).status_code == 409
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/me')).status_code == 403
            client.headers['Authorization'] = 'Bearer ' + owner
            target = next(a['id'] for a in (await client.get('/api/v1/access/accounts')).json()['accounts'] if a['username'] == 'member')
            await client.put('/api/v1/access/accounts/' + target, json={'role': 'reader'})
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/sources/' + row['source_id'])).status_code == 200
            assert (await client.delete('/api/v1/sources/' + row['source_id'], params={'expected_revision': 1})).status_code == 403
            assert (await client.post('/api/v1/sources/upload', data=fields, files={'file': ('reader.txt', b'evidence')})).status_code == 403
            client.headers['Authorization'] = 'Bearer ' + owner
            await client.put('/api/v1/access/accounts/' + target, json={'role': None})
            client.headers['Authorization'] = 'Bearer ' + member
            assert (await client.get('/api/v1/sources/' + row['source_id'])).status_code == 403
            # Real stored cookie session still needs the existing CSRF contract.
            client.headers.pop('Authorization')
            start = await client.get('/auth/login')
            state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]
            assert (await client.get('/auth/callback', params={'state': state, 'code': 'fixture-only'})).status_code == 302
            profile = (await client.get('/api/v1/me')).json()
            assert (await client.post('/api/v1/sources/upload', data=fields, files={'file': ('cookie.txt', b'evidence')})).status_code == 403
            assert (await client.post('/api/v1/sources/upload', data=fields, files={'file': ('cookie.txt', b'evidence')}, headers={'X-C0-CSRF': profile['csrf_token'], 'Origin': 'https://wrong.example.test'})).status_code == 403
            accepted = await client.post('/api/v1/sources/upload', data=fields, files={'file': ('cookie.txt', b'evidence')}, headers={'X-C0-CSRF': profile['csrf_token'], 'Origin': ORIGIN})
            assert accepted.status_code == 202
            created.append(accepted.json()['source_id'])
    asyncio.run(check())


def test_unauthorized_uploads_never_read_the_multipart_body(source_http):
    from uuid import uuid4

    async def check():
        app, owner, member, *_ = source_http[0]
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=ORIGIN) as browser:
            async def reject(status, *, authorization=None, params=None, csrf=None):
                consumed = []
                async def unread():
                    consumed.append(True)
                    yield b'--fixture--\r\n'
                headers = {'Content-Type':'multipart/form-data; boundary=fixture',
                           'Content-Length':str(100 * 1024 * 1024)}
                if authorization:
                    headers['Authorization'] = 'Bearer ' + authorization
                if csrf:
                    headers.update(csrf)
                response = await browser.post('/api/v1/sources/upload', params=params,
                                              content=unread(), headers=headers)
                assert response.status_code == status
                assert not consumed

            await reject(401)
            await reject(401, authorization='invalid')
            await reject(403, authorization=member)
            await reject(403, authorization=owner, params={'space_id':str(uuid4())})
            await reject(422, authorization=owner, params={'space_id':'malformed'})
            start = await browser.get('/auth/login')
            state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]
            await browser.get('/auth/callback', params={'state':state,'code':'fixture-only'})
            me = (await browser.get('/api/v1/me')).json()
            csrf = {'Origin':ORIGIN, 'X-C0-CSRF':me['csrf_token']}
            await reject(403)
            await reject(403, csrf={**csrf, 'Origin':'https://other.example.test'})

            # A signed Reader still lacks the selected space's Editor grant.
            accounts = (await browser.get('/api/v1/access/accounts')).json()['accounts']
            account = next(record for record in accounts if record['username']=='member')
            access_path = '/api/v1/access/accounts/' + account['id']
            assert (await browser.put(access_path, json={'role':'reader'}, headers=csrf)).status_code == 204
            await reject(403, authorization=member)

            shared = next(space['id'] for space in (await browser.get('/api/v1/spaces')).json()['spaces']
                          if space['shared'])
            response = await browser.post('/api/v1/api-keys', headers=csrf, json={
                'name':'Read-only upload fixture', 'scopes':['c0:read'], 'space_ids':[shared],
                'lifetime_days':1})
            assert response.status_code == 201
            await reject(403, authorization=response.json()['key'], params={'space_id':shared})
            # An Editor can start a transfer, but loses write authority before
            # the form is complete. The normal handler must recheck membership.
            assert (await browser.put(access_path, json={'role':'editor'}, headers=csrf)).status_code == 204
            async def revoke_then_send():
                assert (await browser.put(access_path, json={'role':'reader'}, headers=csrf)).status_code == 204
                yield (b'--fixture\r\nContent-Disposition: form-data; name="title"\r\n\r\nExample\r\n'
                       b'--fixture\r\nContent-Disposition: form-data; name="media_type"\r\n\r\ntext/plain\r\n'
                       b'--fixture\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\n'
                       b'\r\nexample\r\n--fixture--\r\n')
            result = await browser.post('/api/v1/sources/upload', headers={
                'Content-Type':'multipart/form-data; boundary=fixture','Authorization':'Bearer '+member},
                content=revoke_then_send())
            assert result.status_code == 403
            schema = (await browser.get('/openapi.json')).json()
            upload = schema['paths']['/api/v1/sources/upload']['post']['requestBody']
            form = upload['content']['multipart/form-data']['schema']['$ref'].split('/')[-1]
            assert set(schema['components']['schemas'][form]['required']) == {'file','title','media_type'}
    asyncio.run(check())


def test_upload_limits_invalid_boolean_and_chunked_body(source_http, monkeypatch):
    import starlette.formparsers
    real_spool = starlette.formparsers.SpooledTemporaryFile
    spools = []
    def spool(*args, **kwargs):
        file = real_spool(*args, **kwargs)
        spools.append(file)
        return file
    monkeypatch.setattr(starlette.formparsers, 'SpooledTemporaryFile', spool)
    async def check():
        application, _ = source_http
        app, owner, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN, headers={'Authorization': 'Bearer ' + owner}) as client:
            fields = {'title': 'Bounded', 'media_type': 'text/plain'}
            assert (await client.post('/api/v1/sources/upload', data={**fields, 'retain_original': 'maybe'}, files={'file': ('file', b'evidence')})).status_code == 422
            assert (await client.post('/api/v1/sources/upload', data=fields, files={'file': ('file', b'x' * (10 * 1024 * 1024 + 1))})).status_code == 413
            async def oversized():
                yield b'--fixture\r\nContent-Disposition: form-data; name="file"; filename="file"\r\n\r\n'
                from czero_core import extraction
                maximum = getattr(extraction, 'MAX_PDF_BYTES', extraction.MAX_UPLOAD)
                for _ in range(maximum // 65536 + 2):
                    yield b'x' * 65536
                yield b'\r\n--fixture--\r\n'
            response = await client.post('/api/v1/sources/upload', content=oversized(), headers={'Content-Type': 'multipart/form-data; boundary=fixture'})
            assert response.status_code == 413 and response.json()['detail'] == 'upload_too_large'
            assert list(app.state.sources.originals.root.iterdir()) == []
            assert spools and all(file.closed for file in spools)
    asyncio.run(check())


def replace_original_during_delivery(fixture, service, actor, version):
    from io import BytesIO
    source=service.get(actor,version['source_id'])
    changed=service.ingest(actor,BytesIO(b'NEW-ORIGINAL-BODY'),title=source['title'],filename='evidence.txt',
        media_type='text/plain',retain_original=True,metadata=source['metadata'],source_id=source['id'],expected_revision=source['revision'])
    import os,subprocess,sys
    worker='''import sys
from czero_core.database import Database
from czero_core.jobs import default_registry
from czero_core.sources import OriginalStore,register_source_handlers
from czero_core.worker import Worker
database=Database();registry=default_registry()
register_source_handlers(registry,database,OriginalStore(sys.argv[1]))
Worker(database,registry).tick()
'''
    result=subprocess.run([sys.executable,'-c',worker,str(service.originals.root)],capture_output=True,timeout=45,
        env={**os.environ,'CZERO_DATABASE_URL':fixture[4].engine.url.render_as_string(hide_password=False)})
    log=service.originals.root.parent/'original-delivery-worker.log'
    log.write_bytes(result.stdout+result.stderr);log.chmod(0o600)
    assert result.returncode==0,'Standalone original replacement worker failed; inspect private fixture log'
    assert service.document(actor,changed['id'])['body']=='NEW-ORIGINAL-BODY'
    with fixture[4].engine.begin() as connection:
        fixture[0].state.jobs.registry.get('source.cleanup').execute(connection,{'version_id':str(UUID(int=0))})
    return changed


@pytest.mark.parametrize('revoke',[False,True])
def test_original_retired_before_open_rechecks_expiry_and_current_authority(source_http,monkeypatch,revoke):
    from czero_core.identity import Role
    from czero_core.sources import SourceService
    fixture,created=source_http;app,owner,member,*_=fixture
    access=app.state.auth.access
    owner_actor=access.resolve(app.state.auth.oidc.verify_access_token(owner))
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app,raise_app_exceptions=False),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+owner}) as http:
            response=await http.post('/api/v1/sources/upload',data={'title':'Original delivery fixture','media_type':'text/plain','retain_original':'true'},
                files={'file':('evidence.txt',b'OLD-ORIGINAL-BODY')})
            assert response.status_code==202
            initial=response.json();created.append(initial['source_id']);Worker(fixture[4],app.state.jobs.registry).tick()
            if revoke:
                assert (await http.get('/api/v1/me',headers={'Authorization':'Bearer '+member})).status_code==403
                target=next(row for row in access.list_accounts(owner_actor) if row['username']=='member')
                access.set_role(owner_actor,target['id'],Role.READER)
                http.headers['Authorization']='Bearer '+member
            original=SourceService.original;retired=[]
            def retire_after_lookup(service,actor,version_id):
                path,version=original(service,actor,version_id)
                if str(version_id)==initial['id'] and not retired:
                    retired.append(True);replace_original_during_delivery(fixture,service,owner_actor,version)
                    assert not path.exists()
                    if revoke:access.set_role(owner_actor,target['id'],None)
                return path,version
            monkeypatch.setattr(SourceService,'original',retire_after_lookup)
            expired=await http.get('/api/v1/source-versions/'+initial['id']+'/original')
            assert expired.status_code==(403 if revoke else 410)
            if revoke:assert 'superseded' not in expired.text
            else:assert expired.json()['detail']=='content_superseded'
    asyncio.run(check())


@pytest.mark.parametrize('range_header',[None,'bytes=4-12'])
def test_open_original_remains_exact_and_identified_when_retired_during_delivery(source_http,monkeypatch,range_header):
    import hashlib
    from czero_app.sources import OriginalFileResponse
    fixture,created=source_http;app,owner,*_=fixture
    actor=app.state.auth.access.resolve(app.state.auth.oidc.verify_access_token(owner))
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as http:
            body=b'OLD-ORIGINAL-BODY'
            response=await http.post('/api/v1/sources/upload',data={'title':'Pinned original fixture','media_type':'text/plain','retain_original':'true'},
                files={'file':('evidence.txt',body)})
            assert response.status_code==202
            initial=response.json();created.append(initial['source_id']);Worker(fixture[4],app.state.jobs.registry).tick()
            original=OriginalFileResponse.__call__;replacement=[]
            async def retire_before_send(response,scope,receive,send):
                if response.headers['x-c0-source-version']==initial['id'] and not replacement:
                    changed=await asyncio.to_thread(replace_original_during_delivery,fixture,app.state.sources,actor,initial)
                    replacement.append(changed)
                    assert not app.state.sources.originals.path(UUID(initial['id'])).exists()
                return await original(response,scope,receive,send)
            monkeypatch.setattr(OriginalFileResponse,'__call__',retire_before_send)
            downloaded=await http.get('/api/v1/source-versions/'+initial['id']+'/original',headers={'Range':range_header} if range_header else {})
            assert downloaded.status_code==(206 if range_header else 200)
            assert downloaded.content==(body[4:13] if range_header else body)
            assert downloaded.headers['x-c0-source-version']==initial['id']
            assert downloaded.headers['x-c0-content-sha256']==hashlib.sha256(body).hexdigest()
            if range_header:assert downloaded.headers['content-range']=='bytes 4-12/'+str(len(body))
            assert (await http.get('/api/v1/source-versions/'+initial['id']+'/original')).status_code==410
            current=await http.get('/api/v1/source-versions/'+str(replacement[0]['id'])+'/original')
            assert current.status_code==200 and current.content==b'NEW-ORIGINAL-BODY'
            assert current.headers['x-c0-source-version']==str(replacement[0]['id'])
            contract=(await http.get('/openapi.json')).json()['paths']['/api/v1/source-versions/{version_id}/original']['get']['responses']
            assert 'superseded' in contract['410']['description']
            assert contract['200']['headers']['X-C0-Source-Version']['schema']['format']=='uuid'
    asyncio.run(check())


@pytest.mark.parametrize('oversized',[False,True])
def test_original_revalidates_bounded_bytes_before_delivery(source_http,monkeypatch,oversized):
    from czero_core.extraction import MAX_UPLOAD
    from czero_core.sources import SourceService
    fixture,created=source_http;app,owner,*_=fixture
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN,headers={'Authorization':'Bearer '+owner}) as http:
            response=await http.post('/api/v1/sources/upload',data={'title':'Original integrity fixture','media_type':'text/plain','retain_original':'true'},
                files={'file':('evidence.txt',b'ORIGINAL-INTEGRITY-BODY')})
            assert response.status_code==202
            initial=response.json();created.append(initial['source_id']);Worker(fixture[4],app.state.jobs.registry).tick()
            original=SourceService.original
            def changed_after_check(service,*args,**kwargs):
                path,version=original(service,*args,**kwargs)
                path.write_bytes(b'x'*(MAX_UPLOAD+1) if oversized else b'CORRUPT-BYTES')
                return path,version
            monkeypatch.setattr(SourceService,'original',changed_after_check)
            failed=await http.get('/api/v1/source-versions/'+initial['id']+'/original')
            assert failed.status_code==409 and failed.json()['detail']=='source_original_changed'
            assert (await http.get('/api/v1/source-versions/'+initial['id']+'/document')).json()['body']=='ORIGINAL-INTEGRITY-BODY'
    asyncio.run(check())


def combined_limit_pdf(path):
    from io import BytesIO
    from pathlib import Path
    from pypdf import PdfReader, PdfWriter
    from czero_core.extraction import MAX_PDF_BYTES, MAX_PDF_PAGES

    seed = PdfReader(Path(__file__).resolve().parents[1]/'fixtures/evidence/pipeline/readable-100.pdf')
    writer = PdfWriter()
    for index in range(MAX_PDF_PAGES):
        writer.add_page(seed.pages[index % len(seed.pages)])
    encoded = BytesIO()
    writer.write(encoded)
    data = encoded.getvalue()
    xref = data.index(b'\nxref\n') + 1
    eof = data.rindex(b'startxref\n') + len(b'startxref\n')
    tail = b'\n%%EOF\n'
    offset = MAX_PDF_BYTES - (eof - xref + len(tail) + len(str(MAX_PDF_BYTES)))
    # Sparse PDF whitespace between objects and the offset table keeps the
    # combined boundary fixture cheap to generate without expanding RAM.
    with path.open('wb') as stream:
        stream.write(data[:xref])
        stream.seek(offset - 1)
        stream.write(b'\n' + data[xref:eof] + str(offset).encode() + tail)
    assert path.stat().st_size == MAX_PDF_BYTES
    return path


def test_pdf_upload_limit_and_retained_original(source_http, tmp_path):
    from czero_core.extraction import MAX_PDF_BYTES
    app, owner, *_, database, _ = source_http[0]
    created = source_http[1]
    maximum = MAX_PDF_BYTES
    original = combined_limit_pdf(tmp_path/'large.pdf')

    async def check():
        from czero_core.worker import Worker
        fields = {'title': 'Large PDF', 'media_type': 'application/pdf', 'retain_original': 'true'}
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                               headers={'Authorization': 'Bearer ' + owner}) as client:
            with original.open('rb') as stream:
                result = await client.post('/api/v1/sources/upload', data=fields,
                                           files={'file': ('large.pdf', stream, 'application/pdf')})
            assert result.status_code == 202
            version = result.json()
            created.append(version['source_id'])
            assert version['size_bytes'] == maximum
            Worker(database, app.state.jobs.registry).tick()
            doc = await client.get('/api/v1/source-versions/' + version['id'] + '/document')
            assert doc.status_code == 200
            document = doc.json()
            assert [item['index'] for item in document['locations']] == list(range(1,2001))
            endpoint = '/api/v1/documents/' + document['id'] + '/chunks'
            offset = 0
            while True:
                page = (await client.get(endpoint, params={'offset':offset, 'limit':100})).json()['chunks']
                assert page
                if page[-1]['end_offset'] == len(document['body']):
                    break
                offset += len(page)
            citation = await client.get('/api/v1/chunks/' + page[-1]['id'] + '/citation')
            assert citation.status_code == 200
            assert citation.json()['locations'][-1]['index'] == 2000
            assert citation.json()['source_hash'] == version['content_hash']
            response = await client.get('/api/v1/source-versions/' + version['id'] + '/original',
                                        headers={'Range': 'bytes=0-4'})
            assert response.status_code == 206 and response.content == b'%PDF-'
            with original.open('ab') as stream:
                stream.write(b' ')
            with original.open('rb') as stream:
                result = await client.post('/api/v1/sources/upload', data=fields,
                                           files={'file': ('large.pdf', stream, 'application/pdf')})
            assert result.status_code == 413
    asyncio.run(check())


@pytest.fixture
def pdf_key(monkeypatch, tmp_path):
    key = tmp_path / 'pdf.key'
    key.touch(mode=0o600)
    key.write_bytes(os.urandom(32))
    monkeypatch.setenv('CZERO_PDF_UNLOCK_KEY_FILE', str(key))


@pytest.fixture
def protected_source_http(pdf_key, source_http):
    return source_http


def protected_pdf_bytes(password, *, restricted):
    from io import BytesIO
    from pathlib import Path
    from pypdf import PdfReader, PdfWriter
    from pypdf.constants import UserAccessPermissions

    reader = PdfReader(Path(__file__).resolve().parents[1] / 'fixtures/evidence/pipeline/readable-100.pdf')
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    permissions = UserAccessPermissions(-1)
    writer.encrypt(password, owner_password='synthetic-owner-credential', algorithm='AES-256',
        permissions_flag=permissions & ~UserAccessPermissions.EXTRACT if restricted else permissions)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def test_protected_upload_approval_publication_and_reprocessing(protected_source_http):
    async def check():
        (app, owner, member, *_), created = protected_source_http
        database = protected_source_http[0][4]
        password = 'synthetic-open-password'
        original = protected_pdf_bytes(password, restricted=True)
        other = protected_pdf_bytes(password, restricted=True)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                               headers={'Authorization': 'Bearer ' + owner}) as client:
            fields = {'title': 'Protected fixture', 'media_type': 'application/pdf', 'retain_original': 'true'}

            async def upload(body=original, **extras):
                return await client.post('/api/v1/sources/upload', data={**fields, **extras},
                    files={'file': ('protected.pdf', body, 'application/pdf')})

            assert (await upload()).json() == {'detail': 'pdf_password_required'}
            assert (await upload(pdf_password='incorrect')).json() == {'detail': 'pdf_password_incorrect'}
            challenge = await upload(pdf_password=password)
            assert challenge.status_code == 422 and challenge.json()['detail'] == 'pdf_extraction_approval_required'
            token = challenge.json()['approval_token']
            assert (await upload(other, pdf_password=password, pdf_approval_token=token)).status_code == 422
            with database.engine.connect() as c:
                assert c.execute(text('SELECT count(*) FROM c0_pdf_authorizations')).scalar_one() == 0

            response = await upload(pdf_password=password, pdf_approval_token=token)
            assert response.status_code == 202, response.json()
            version = response.json()
            created.append(version['source_id'])
            duplicate = await upload(pdf_password=password, pdf_approval_token=token)
            assert duplicate.json()['id'] == version['id']
            with database.engine.connect() as c:
                saved = c.execute(text('SELECT sealed_password,restricted FROM c0_pdf_authorizations')).one()
                assert saved.restricted and password not in saved.sealed_password
                assert password not in str(c.execute(text('SELECT payload FROM c0_jobs WHERE id=:id'),
                    {'id': version['job_id']}).scalar_one())
            Worker(database, app.state.jobs.registry).tick()
            endpoint = '/api/v1/source-versions/' + version['id']
            assert (await client.get(endpoint + '/document')).status_code == 200
            assert (await client.get(endpoint + '/original')).content == original

            source_endpoint = '/api/v1/sources/' + version['source_id']
            source = (await client.get(source_endpoint)).json()
            member_headers = {'Authorization': 'Bearer ' + member}
            await client.get('/api/v1/me', headers=member_headers)
            accounts = (await client.get('/api/v1/access/accounts')).json()['accounts']
            member_id = next(row['id'] for row in accounts if row['username'] == 'member')
            account = '/api/v1/access/accounts/' + member_id
            request = {'expected_revision': source['revision'], 'idempotency_key': 'fixture-protected-reindex'}
            assert (await client.put(account, json={'role': 'reader'})).status_code == 204
            assert (await client.post(source_endpoint + '/reindex', json=request, headers=member_headers)).status_code == 403
            assert (await client.put(account, json={'role': 'editor'})).status_code == 204
            reindex = await client.post(source_endpoint + '/reindex', json=request, headers=member_headers)
            assert reindex.status_code == 202, reindex.json()
            Worker(database, app.state.jobs.registry).tick()
            new_endpoint = '/api/v1/source-versions/' + reindex.json()['id']
            assert (await client.get(new_endpoint + '/document')).status_code == 200
            assert (await client.get(new_endpoint + '/original')).content == original
            with database.engine.connect() as c:
                assert c.execute(text('SELECT version_id::text FROM c0_pdf_authorizations')).scalar_one() == reindex.json()['id']
    asyncio.run(check())


@pytest.mark.parametrize('partitioned', [False, True])
def test_retained_legacy_pdf_review_and_extraction(protected_source_http, partitioned):
    from io import BytesIO
    from czero_core.extraction_queue import ExtractionQueue, ExtractionWorker
    from czero_core.identity import Actor, Role

    async def check():
        (app, owner, *_), created = protected_source_http
        database = protected_source_http[0][4]
        service = app.state.sources
        original = protected_pdf_bytes('', restricted=True)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                               headers={'Authorization': 'Bearer ' + owner}) as client:
            profile = (await client.get('/api/v1/me')).json()
            actor = Actor(UUID(profile['id']), Role.READER)
            version = service.ingest(actor, BytesIO(original), title='Legacy restricted PDF',
                media_type='application/pdf', filename='legacy.pdf', retain_original=True)
            created.append(version['source_id'])
            Worker(database, app.state.jobs.registry).tick()
            assert service.versions(actor, version['source_id'])[0]['error_code'] == 'encrypted_pdf'
            with database.engine.begin() as c:
                c.execute(text("UPDATE c0_source_versions SET created_at=now()-interval '2 days' WHERE id=:id"),
                    {'id': version['id']})

            endpoint = '/api/v1/source-versions/' + str(version['id'])
            payload = {'expected_generation': version['generation']}
            assert (await client.post(endpoint + '/retry', json=payload)).status_code == 422
            approval = await client.post(endpoint + '/pdf-retry', json=payload)
            assert approval.status_code == 422
            assert approval.json()['detail'] == 'pdf_extraction_approval_required'
            payload['pdf_approval_token'] = approval.json()['approval_token']
            retry = await client.post(endpoint + '/pdf-retry', json=payload)
            assert retry.status_code == 202, retry.json()
            assert (await client.post(endpoint + '/pdf-retry', json=payload)).status_code == 409
            with database.engine.connect() as c:
                grant = c.execute(text('SELECT restricted,sealed_password FROM c0_pdf_authorizations WHERE version_id=:id'),
                    {'id': version['id']}).one()
                assert grant == (True, None)

            if partitioned:
                queue = ExtractionQueue(database, service.access, service.originals, enabled=True, pdf_access=service.pdf_access)
                queue.enqueue(actor, version['id'], expected_generation=retry.json()['generation'])
                assert ExtractionWorker(queue).tick() == 1
            else:
                Worker(database, app.state.jobs.registry).tick()
            assert (await client.get(endpoint + '/document')).status_code == 200
            assert (await client.get(endpoint + '/original')).content == original
    asyncio.run(check())


def test_archived_pending_protected_pdf_does_not_publish(protected_source_http):
    async def check():
        (app, owner, *_), created = protected_source_http
        database = protected_source_http[0][4]
        original = protected_pdf_bytes('synthetic-password', restricted=False)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN,
                               headers={'Authorization': 'Bearer ' + owner}) as client:
            upload = await client.post('/api/v1/sources/upload',
                data={'title': 'Archive before extraction', 'media_type': 'application/pdf',
                      'pdf_password': 'synthetic-password'},
                files={'file': ('archive.pdf', original, 'application/pdf')})
            assert upload.status_code == 202, upload.json()
            version = upload.json()
            created.append(version['source_id'])
            source = '/api/v1/sources/' + version['source_id']
            revision = (await client.get(source)).json()['revision']
            assert (await client.delete(source, params={'expected_revision':revision})).status_code == 200
            Worker(database, app.state.jobs.registry).tick()
            with database.engine.connect() as c:
                assert c.execute(text('SELECT current_version_id FROM c0_sources WHERE id=:id'),
                    {'id': version['source_id']}).scalar_one() is None
                assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),
                    {'id': version['id']}).scalar_one() == 0
    asyncio.run(check())
