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
            ids = c.execute(text('SELECT id FROM c0_source_versions WHERE source_id=:id'), {'id': key}).scalars().all()
            c.execute(text('DELETE FROM c0_chunks WHERE document_id IN (SELECT id FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id))'), {'id': key})
            c.execute(text('DELETE FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id)'), {'id': key})
            c.execute(text('DELETE FROM c0_source_versions WHERE source_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_sources WHERE id=:id'), {'id': key})
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
                for _ in range(162):
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
