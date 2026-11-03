# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from urllib.parse import parse_qs,urlsplit
from uuid import UUID,uuid4
import os
import pytest
from httpx import ASGITransport,AsyncClient
from czero_core.extraction_queue import ExtractionQueue
from test_auth_http import application,ORIGIN
from test_sources_http import source_http
from test_pdf_unit_pipeline import FIXTURES
from test_mcp_http import transport
from test_knowledge_http import knowledge_http

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_actual_reader_editor_admin_cookie_csrf_and_recovery(source_http):
    async def check():
        fixture,created=source_http
        app,owner,member,*_=fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            assert (await client.get('/api/v1/extraction-runs')).status_code==401
            client.headers['Authorization']='Bearer '+owner
            response=await client.post('/api/v1/sources/upload',data={'title':'Metadata only','media_type':'application/pdf','retain_original':'true'},
                files={'file':('scan.pdf',(FIXTURES/'blank-pages.pdf').read_bytes())})
            assert response.status_code==202
            version=response.json();created.append(version['source_id'])
            actor=app.state.auth.access.resolve(app.state.auth.oidc.verify_access_token(owner))
            q=ExtractionQueue(app.state.sources.database,app.state.auth.access,app.state.sources.originals,enabled=True)
            run=q.enqueue(actor,version['id'],expected_generation=1)
            claim=q.claim();assert q.fail(claim,'invalid_file')
            current=(await client.get('/api/v1/sources/'+version['source_id']+'/extraction')).json()
            assert current['state']=='failed' and current['run']['completed']==0
            units=await client.get('/api/v1/extraction-runs/'+str(run['id'])+'/units?limit=1')
            assert units.status_code==200 and len(units.json()['units'])==1
            serialized=units.text
            for private in ('body','lease_token','manifest_sha256','original_sha256','filename','credential'):
                assert '"'+private+'"' not in serialized
            assert (await client.get('/api/v1/extraction-runs/'+str(run['id'])+'/units?limit=101')).status_code==422
            # A real cookie action preserves the original native run authority.
            client.headers.pop('Authorization')
            start=await client.get('/auth/login');state=parse_qs(urlsplit(start.headers['location']).query)['state'][0]
            assert (await client.get('/auth/callback',params={'state':state,'code':'fixture-only'})).status_code==302
            profile=(await client.get('/api/v1/me')).json()
            path='/api/v1/extraction-runs/'+str(run['id'])+'/retry'
            payload={'expected_revision':current['run']['revision'],'idempotency_key':uuid4().hex}
            assert (await client.post(path,json=payload)).status_code==403
            headers={'X-C0-CSRF':profile['csrf_token'],'Origin':ORIGIN}
            result=await client.post(path,json=payload,headers=headers)
            assert result.status_code==200 and result.json()['retried_units']==1
            assert (await client.post(path,json=payload,headers=headers)).json()==result.json()
            assert (await client.post(path,json={**payload,'private':'RAW-PRIVATE-TEST'},headers=headers)).status_code==422
            assert 'RAW-PRIVATE-TEST' not in (await client.post(path,json={'expected_revision':'RAW-PRIVATE-TEST'},headers=headers)).text
            # Persistent role reduction wins over a captured token and cookie.
            client.headers['Authorization']='Bearer '+owner
            await client.get('/api/v1/me',headers={'Authorization':'Bearer '+member})
            accounts=(await client.get('/api/v1/access/accounts')).json()['accounts']
            account=next(a for a in accounts if a['username']=='member')
            assert (await client.put('/api/v1/access/accounts/'+account['id'],json={'role':'reader'})).status_code==204
            client.headers['Authorization']='Bearer '+member
            assert (await client.get('/api/v1/sources/'+version['source_id']+'/extraction')).status_code==200
            assert (await client.get('/api/v1/extraction-runs')).status_code==403
            assert (await client.get('/api/v1/extraction-runs/'+str(run['id'])+'/units')).status_code==403
            assert (await client.post(path,json=payload)).status_code==403
            assert (await client.post('/api/v1/sources/'+version['source_id']+'/reindex',json={'expected_revision':1,'idempotency_key':uuid4().hex})).status_code==403
    asyncio.run(check())


def test_delegated_scopes_never_inherit_native_admin_authority(transport,source_http):
    from test_document_context_http import seed
    app,_,_,_,_,issue,owner_token,_=transport
    _,version=seed(app,owner_token,source_http[1])
    identity=app.state.auth.oidc.verify_access_token(owner_token)
    read=issue(identity,{'c0:read'})
    write=issue(identity,{'c0:write'})
    admin=issue(identity,{'c0:read','c0:write','c0:admin'})
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as http:
            http.headers['Authorization']='Bearer '+read.access_token
            assert (await http.get('/api/v1/sources/'+str(version['source_id'])+'/extraction')).status_code==200
            assert (await http.get('/api/v1/extraction-runs')).status_code==403
            path='/api/v1/sources/'+str(version['source_id'])+'/reindex'
            payload={'expected_revision':1,'idempotency_key':uuid4().hex}
            assert (await http.post(path,json=payload)).status_code==403
            http.headers['Authorization']='Bearer '+write.access_token
            assert (await http.get('/api/v1/sources/'+str(version['source_id'])+'/extraction')).status_code==403
            assert (await http.get('/api/v1/extraction-runs')).status_code==403
            http.headers['Authorization']='Bearer '+admin.access_token
            runs=await http.get('/api/v1/extraction-runs');assert runs.status_code==200
            run=runs.json()['runs'][0]
            assert (await http.get('/api/v1/extraction-runs/'+run['id']+'/units')).status_code==200
            http.headers['Authorization']='Bearer '+write.access_token
            assert (await http.post(path,json=payload)).status_code==202
    asyncio.run(check())
