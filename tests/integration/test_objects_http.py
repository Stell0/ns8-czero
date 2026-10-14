# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from urllib.parse import parse_qs,urlsplit
from uuid import uuid4

from httpx import ASGITransport,AsyncClient
import pytest
from sqlalchemy import text
from test_auth_http import application,ORIGIN

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')
SCHEMA={'type':'object','properties':{'name':{'type':'string','maxLength':64}},'required':['name']}


def cleanup(db,names):
    with db.engine.begin() as c:
        for name in names:
            c.execute(text('DELETE FROM c0_objects WHERE type_name=:name'),{'name':name})
            c.execute(text('DELETE FROM c0_object_events WHERE type_name=:name'),{'name':name})
            c.execute(text('DELETE FROM c0_object_types WHERE name=:name'),{'name':name})


def test_signed_rest_objects_types_batches_references_and_events(application):
    async def check():
        app,owner,*_=application; db=application[4]; names=['http-inv-'+uuid4().hex,'http-proj-'+uuid4().hex]
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            assert (await client.get('/api/v1/object-types')).status_code==401
            client.headers['Authorization']='Bearer '+owner
            try:
                for name in names:
                    result=await client.post('/api/v1/object-types',json={'name':name,'label':'Fixture','schema':SCHEMA,'unique_fields':['name']})
                    assert result.status_code==201 and result.json()['schema']['additionalProperties'] is False
                assert (await client.get('/api/v1/object-types/'+names[0])).json()['name']==names[0]
                first=await client.post('/api/v1/objects',json={'type_name':names[0],'data':{'name':'server'},'tags':['priority']})
                assert first.status_code==201; row=first.json(); path='/api/v1/objects/'+row['id']
                assert (await client.get(path)).json()['revision']==1
                assert (await client.get('/api/v1/objects',params={'type_name':names[0],'where':'{"name":"server"}','tag':'priority'})).json()['objects'][0]['id']==row['id']
                assert (await client.post('/api/v1/objects',json={'type_name':names[0],'data':{'name':'server'}})).status_code==409
                changed=await client.put(path,json={'data':{'name':'new'},'expected_revision':1})
                assert changed.status_code==200 and changed.json()['revision']==2
                assert (await client.put(path,json={'data':{'name':'lost'},'expected_revision':1})).status_code==409
                invalid=await client.put(path,json={'data':{'name':3},'expected_revision':2})
                assert invalid.status_code==422 and invalid.json()['detail']=='record_invalid:name:type'
                target=(await client.post('/api/v1/objects',json={'type_name':names[1],'data':{'name':'project'}})).json()
                relation=await client.post('/api/v1/object-relations',json={'source_id':row['id'],'target_id':target['id'],'kind':'belongs-to','source_type':names[0],'target_type':names[1]})
                assert relation.status_code==201
                assert (await client.get(path+'/relations')).json()['relations'][0]['target_type']==names[1]
                reference=await client.get('/api/v1/references/object/'+target['id'],params={'type_name':names[1]})
                assert reference.status_code==200 and reference.json()['data']==target['data']
                assert (await client.delete('/api/v1/object-relations/'+relation.json()['id'])).status_code==204
                failed=await client.post('/api/v1/objects/batch',json={'operations':[
                    {'operation':'create','type_name':names[0],'data':{'name':'rolled-back'}},
                    {'operation':'delete','id':row['id'],'expected_revision':1}]})
                assert failed.status_code==409
                assert len((await client.get('/api/v1/objects',params={'type_name':names[0]})).json()['objects'])==1
                success=await client.post('/api/v1/objects/batch',json={'operations':[
                    {'operation':'create','type_name':names[0],'data':{'name':'batch-created'}},
                    {'operation':'delete','id':row['id'],'expected_revision':2}]})
                assert success.status_code==200 and success.json()['results'][1]['deleted'] is True
                events=(await client.get('/api/v1/object-events')).json()['events']
                assert any(e['object_id']==row['id'] and e['operation']=='delete' for e in events)
                assert (await client.get(path)).status_code==404
                for params in ({'limit':101},{'where':'invalid'},{'where':'[]'},{'where':'{"bad":true}'}):
                    assert (await client.get('/api/v1/objects',params={'type_name':names[0],**params})).status_code==422
                assert (await client.get('/api/v1/references/os-system/'+target['id'],params={'type_name':'profile'})).status_code==422
                assert (await client.post('/api/v1/objects/batch',json={'operations':[{'operation':'sql','command':'anything'}]})).status_code==422
                schema=(await client.get('/openapi.json')).json()
                assert schema['paths']['/api/v1/objects']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/ObjectsView')
            finally:cleanup(db,names)
    asyncio.run(check())


def test_roles_revocation_and_cookie_csrf_protect_object_writes(application):
    async def check():
        app,owner,member,*_=application; db=application[4]; name='http-roles-'+uuid4().hex
        async with AsyncClient(transport=ASGITransport(app=app),base_url=ORIGIN) as client:
            client.headers['Authorization']='Bearer '+owner
            try:
                assert (await client.post('/api/v1/object-types',json={'name':name,'label':'Roles','schema':SCHEMA})).status_code==201
                client.headers['Authorization']='Bearer '+member
                assert (await client.get('/api/v1/me')).status_code==403
                client.headers['Authorization']='Bearer '+owner
                target=next(a for a in (await client.get('/api/v1/access/accounts')).json()['accounts'] if a['username']=='member')['id']
                for role in ('reader','editor','admin'):
                    assert (await client.put('/api/v1/access/accounts/'+target,json={'role':role})).status_code==204
                    client.headers['Authorization']='Bearer '+member
                    assert (await client.get('/api/v1/object-types')).status_code==200
                    result=await client.post('/api/v1/objects',json={'type_name':name,'data':{'name':role}})
                    assert result.status_code==(403 if role=='reader' else 201)
                    grant=await client.post('/api/v1/object-types',json={'name':name,'label':'Roles','schema':SCHEMA})
                    assert grant.status_code==(409 if role=='admin' else 403)
                    reg=await client.post('/api/v1/object-types',json={'name':'invalid-name','label':'Role check','schema':{'type':'object','$ref':'https://untrusted.invalid'}})
                    # The shared operation boundary denies non-admins before
                    # inspecting schema semantics. Admin invalid schemas still
                    # fail validation without a remote fetch or write.
                    assert reg.status_code==(422 if role=='admin' else 403)
                    client.headers['Authorization']='Bearer '+owner
                assert (await client.put('/api/v1/access/accounts/'+target,json={'role':None})).status_code==204
                client.headers['Authorization']='Bearer '+member
                assert (await client.get('/api/v1/objects',params={'type_name':name})).status_code==403
                client.headers.pop('Authorization')
                start=await client.get('/auth/login');state=parse_qs(urlsplit(start.headers['location']).query)['state'][0]
                assert (await client.get('/auth/callback',params={'state':state,'code':'fixture-only'})).status_code==302
                profile=(await client.get('/api/v1/me')).json();data={'type_name':name,'data':{'name':'cookie'}}
                assert (await client.post('/api/v1/objects',json=data)).status_code==403
                assert (await client.post('/api/v1/objects',json=data,headers={'X-C0-CSRF':profile['csrf_token'],'Origin':'https://wrong.example.test'})).status_code==403
                assert (await client.post('/api/v1/objects',json=data,headers={'X-C0-CSRF':profile['csrf_token'],'Origin':ORIGIN})).status_code==201
            finally:cleanup(db,[name])
    asyncio.run(check())
