# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text

from test_auth_http import application, ORIGIN

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


def cleanup(application,owner_id):
    database=application[4]
    with database.engine.begin() as c:
        c.execute(text('DELETE FROM c0_jobs WHERE idempotency_key LIKE :prefix'),{'prefix':'request:'+owner_id+':%'})
        c.execute(text("DELETE FROM c0_scheduled_tasks WHERE name LIKE 'http-test-%'"))


def test_signed_rest_queue_and_schedule_contracts(application):
    async def check():
        app,owner,*_=application
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            assert (await client.get('/api/v1/jobs')).status_code==401
            client.headers['Authorization']='Bearer '+owner
            owner_id=(await client.get('/api/v1/me')).json()['id']
            try:
                handlers=await client.get('/api/v1/jobs/handlers')
                assert handlers.status_code==200 and len(handlers.json()['handlers'])==2
                data={'handler':'health','payload':{},'idempotency_key':'http-one'}
                first=await client.post('/api/v1/jobs',json=data)
                assert first.status_code==201
                job=first.json()
                assert job['state']=='queued' and 'fingerprint' not in job and 'idempotency_key' not in job
                assert (await client.post('/api/v1/jobs',json=data)).json()['id']==job['id']
                assert (await client.post('/api/v1/jobs',json={**data,'handler':'maintenance'})).status_code==409
                assert (await client.get('/api/v1/jobs/'+job['id'])).json()['id']==job['id']
                assert (await client.get('/api/v1/jobs/'+job['id']+'/runs')).json()=={'runs':[]}
                assert (await client.get('/api/v1/jobs/'+str(uuid4()))).status_code==404
                assert (await client.post('/api/v1/jobs',json={**data,'handler':'os.system'})).status_code==422
                assert (await client.post('/api/v1/jobs',json={**data,'payload':{'command':'do something'}})).status_code==422
                task_data={'name':'http-test-'+uuid4().hex,'handler':'health','payload':{},'interval_seconds':60}
                created=await client.post('/api/v1/schedules',json=task_data)
                assert created.status_code==201
                task=created.json()
                changed=await client.put('/api/v1/schedules/'+task['id'],json={'enabled':False,'interval_seconds':120})
                assert changed.status_code==200 and changed.json()['enabled'] is False
                assert (await client.get('/api/v1/schedules/'+task['id']+'/runs')).json()=={'runs':[]}
                assert (await client.post('/api/v1/schedules',json={**task_data,'name':'http-test-bad','interval_seconds':True})).status_code==422
                schema=(await client.get('/openapi.json')).json()
                assert schema['paths']['/api/v1/jobs']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/JobsView')
            finally:cleanup(application,owner_id)
    asyncio.run(check())


def test_reader_editor_and_revoked_admin_cannot_manage_jobs(application):
    async def check():
        app,owner,member,*_=application
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            client.headers['Authorization']='Bearer '+member
            assert (await client.get('/api/v1/me')).status_code==403
            client.headers['Authorization']='Bearer '+owner
            rows=(await client.get('/api/v1/access/accounts')).json()['accounts']
            target=next(row for row in rows if row['username']=='member')['id']
            for role in ('reader','editor','admin'):
                assert (await client.put('/api/v1/access/accounts/'+target,json={'role':role})).status_code==204
                client.headers['Authorization']='Bearer '+member
                assert (await client.get('/api/v1/schedules')).status_code==(200 if role=='admin' else 403)
                if role!='admin':
                    assert (await client.post('/api/v1/jobs',json={'handler':'health','payload':{},'idempotency_key':'not-allowed'})).status_code==403
                client.headers['Authorization']='Bearer '+owner
            assert (await client.put('/api/v1/access/accounts/'+target,json={'role':None})).status_code==204
            client.headers['Authorization']='Bearer '+member
            assert (await client.get('/api/v1/jobs')).status_code==403
    asyncio.run(check())


def test_schedule_cookie_writes_reuse_origin_and_csrf_boundary(application):
    async def check():
        app=application[0]
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            from urllib.parse import urlsplit,parse_qs
            started=await client.get('/auth/login')
            state=parse_qs(urlsplit(started.headers['location']).query)['state'][0]
            assert (await client.get('/auth/callback',params={'state':state,'code':'fixture-only'})).status_code==302
            profile=(await client.get('/api/v1/me')).json()
            schedules=(await client.get('/api/v1/schedules')).json()['schedules']
            task=next(t for t in schedules if t['name']=='health-hourly')
            path='/api/v1/schedules/'+task['id']
            data={'enabled':task['enabled'],'interval_seconds':task['interval_seconds']}
            assert (await client.put(path,json=data)).status_code==403
            assert (await client.put(path,json=data,headers={'X-C0-CSRF':profile['csrf_token'],'Origin':'https://wrong.example.test'})).status_code==403
            assert (await client.put(path,json=data,headers={'X-C0-CSRF':profile['csrf_token'],'Origin':ORIGIN})).status_code==200
    asyncio.run(check())
