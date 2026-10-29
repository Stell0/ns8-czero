# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""New whole-document transport leaves original evidence contracts intact."""
import asyncio
import hashlib
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport,AsyncClient
from czero_core.worker import Worker
from test_auth_http import application,ORIGIN
from test_sources_http import source_http

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


def test_whole_document_rest_discovery_history_original_and_archive(source_http):
    async def check():
        fixture,created=source_http;app,owner,member,_,database,_=fixture
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            assert (await client.get('/api/v1/source-documents')).status_code==401
            client.headers['Authorization']='Bearer '+owner
            body='# Full original\n\n'+'Bounded complete Markdown café.\n\n'*5000
            response=await client.post('/api/v1/sources/upload',data={'title':'Whole original','media_type':'text/markdown'},files={'file':('original.md',body.encode(),'text/markdown')})
            assert response.status_code==202
            version=response.json();created.append(version['source_id'])
            path='/api/v1/source-documents/'+version['source_id']
            pending=(await client.get(path)).json();assert pending['state']=='incomplete' and pending['body'] is None
            Worker(database,app.state.jobs.registry).tick()
            summary=(await client.get('/api/v1/source-documents')).json()['documents']
            assert any(row['id']==version['source_id'] for row in summary) and all('body' not in row for row in summary)
            complete=await client.get(path);assert complete.status_code==200
            doc=complete.json();assert doc['body']==body and doc['text_hash']==hashlib.sha256(body.encode()).hexdigest()
            raw=(await client.get('/api/v1/source-versions/'+version['id']+'/document')).json()
            assert raw['body']==body and raw['id']==doc['parts'][0]['document_id']
            assert (await client.get('/api/v1/source-versions/'+version['id']+'/full-document')).json()==doc
            assert (await client.get(path+'/history')).json()['revisions'][0]['revision_id']==version['id']
            assert (await client.get(path,params={'revision_id':str(uuid4())})).status_code==404
            assert (await client.get(path,params={'space_id':str(uuid4())})).status_code==403
            duplicate=await client.get(path+'?space_id='+str(uuid4())+'&space_id='+str(uuid4()))
            assert duplicate.status_code==422
            assert (await client.get(path+'/history',params={'limit':101})).status_code==422
            assert (await client.delete('/api/v1/sources/'+version['source_id'],params={'expected_revision':1})).status_code==200
            assert all(row['id']!=version['source_id'] for row in (await client.get('/api/v1/source-documents')).json()['documents'])
            assert (await client.get(path,params={'revision_id':version['id']})).json()['body']==body
    asyncio.run(check())
