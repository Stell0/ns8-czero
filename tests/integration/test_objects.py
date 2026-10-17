# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.objects import ObjectService, ObjectConflict, ObjectNotFound
from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.migrate import migrate_database
from test_access import access, identity, owner_actor, record_unadmitted, account_named

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')
SCHEMA={'type':'object','properties':{'name':{'type':'string','maxLength':64},'count':{'type':'integer','minimum':0}},'required':['name']}


@pytest.fixture
def objects(access):
    acl,db,_=access; owner=owner_actor(access); service=ObjectService(db,acl)
    suffix=uuid4().hex
    inventory='inventory-'+suffix; projects='projects-'+suffix
    service.register_type(owner,inventory,'Inventory',SCHEMA,['name'])
    service.register_type(owner,projects,'Projects',SCHEMA,['name'])
    yield service,owner,inventory,projects
    with db.engine.begin() as c:
        c.execute(text('DELETE FROM c0_objects WHERE type_name IN (:i,:p)'),{'i':inventory,'p':projects})
        c.execute(text('DELETE FROM c0_object_events WHERE type_name IN (:i,:p)'),{'i':inventory,'p':projects})
        c.execute(text('DELETE FROM c0_object_types WHERE name IN (:i,:p)'),{'i':inventory,'p':projects})


def test_two_domains_crud_tags_filter_and_revision_conflict(objects):
    svc,owner,inv,proj=objects
    a=svc.create(owner,inv,{'name':'server','count':2},record_tags=['priority','inventory'])
    b=svc.create(owner,proj,{'name':'server','count':0})
    assert a['id']!=b['id'] and a['revision']==1
    assert svc.list(owner,inv,where={'count':2},tag='priority')[0]['id']==a['id']
    assert svc.list(owner,inv,where={'count':3})==[]
    changed=svc.update(owner,a['id'],{'name':'updated','count':3},expected_revision=1)
    assert changed['revision']==2 and changed['tags']==a['tags']
    with pytest.raises(ObjectConflict): svc.update(owner,a['id'],{'name':'lost'},expected_revision=1)
    assert svc.get(owner,a['id'])['data']['name']=='updated'
    svc.delete(owner,a['id'],expected_revision=2)
    with pytest.raises(ObjectNotFound): svc.get(owner,a['id'])
    events=[e for e in svc.events(owner) if e['object_id']==a['id']]
    assert [e['operation'] for e in events]==['create','update','delete']
    assert all('data' not in e for e in events)


def test_unique_fields_conflicts_and_atomic_batch_rollback(objects):
    svc,owner,inv,_=objects
    row=svc.create(owner,inv,{'name':'existing'})
    before=len(svc.events(owner))
    with pytest.raises(ObjectConflict): svc.batch(owner,[
        {'operation':'create','type_name':inv,'data':{'name':'rolled-back'}},
        {'operation':'update','id':str(row['id']),'data':{'name':'stale'},'expected_revision':7}])
    assert len(svc.events(owner))==before
    assert [r['data']['name'] for r in svc.list(owner,inv)]==['existing']
    with pytest.raises(ObjectConflict): svc.create(owner,inv,{'name':'existing'})
    assert svc.get(owner,row['id'])['revision']==1


def test_concurrent_unique_writes_and_revision_updates(objects):
    svc,owner,inv,_=objects
    def create(_):
        try: return svc.create(owner,inv,{'name':'concurrent'})
        except ObjectConflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(create,range(2)))
    assert sum(r is not None for r in results)==1
    row=next(r for r in results if r)
    def update(i):
        try: return svc.update(owner,row['id'],{'name':f'updated-{i}'},expected_revision=1)
        except ObjectConflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(update,range(2)))
    assert sum(r is not None for r in results)==1
    assert svc.get(owner,row['id'])['revision']==2


@pytest.mark.parametrize('role',list(Role))
def test_role_and_revocation_rechecked_in_core_transactions(objects,role):
    svc,owner,inv,_=objects; acl=svc.access; key=uuid4()
    record_unadmitted(acl,key,'member'); target=account_named(acl,owner,'member')['id']
    acl.set_role(owner,target,role); member=acl.resolve(identity(acl,key,'member'))
    forged=Actor(member.user_id,Role.ADMIN,True)
    assert svc.get_type(forged,inv)['name']==inv
    if role==Role.READER:
        with pytest.raises(PermissionDenied): svc.create(forged,inv,{'name':'denied'})
    else: svc.create(member,inv,{'name':'admitted'})
    if role!=Role.ADMIN:
        with pytest.raises(PermissionDenied): svc.register_type(forged,'forbidden','Forbidden',SCHEMA)
    acl.set_role(owner,target,None)
    with pytest.raises(PermissionDenied): svc.list(member,inv)
    with pytest.raises(PermissionDenied): svc.create(member,inv,{'name':'revoked'})


def test_typed_references_deduplicate_resolve_and_delete_without_dangling_rows(objects):
    svc,owner,inv,proj=objects
    source=svc.create(owner,inv,{'name':'rack'}); target=svc.create(owner,proj,{'name':'upgrade'})
    with pytest.raises(ValueError,match='reference_type_mismatch'):
        svc.add_relation(owner,source['id'],target['id'],'used-by',source_type=proj,target_type=inv)
    relation=svc.add_relation(owner,source['id'],target['id'],'used-by',source_type=inv,target_type=proj)
    assert svc.add_relation(owner,source['id'],target['id'],'used-by',source_type=inv,target_type=proj)['id']==relation['id']
    assert svc.relations(owner,source['id'])[0]['target_type']==proj
    svc.remove_relation(owner,relation['id']); assert svc.relations(owner,source['id'])==[]
    svc.add_relation(owner,source['id'],target['id'],'used-by',source_type=inv,target_type=proj)
    svc.delete(owner,target['id'],expected_revision=1)
    assert svc.relations(owner,source['id'])==[]
    with pytest.raises(ObjectNotFound): svc.add_relation(owner,source['id'],uuid4(),'used-by',source_type=inv,target_type=proj)


def test_limits_schema_rejection_and_no_partial_writes(objects):
    svc,owner,inv,_=objects
    for kwargs in ({'limit':101},{'offset':-1},{'where':{'unknown':1}},{'tag':'SQL injection'}):
        with pytest.raises(ValueError): svc.list(owner,inv,**kwargs)
    for data in ({'name':5},{'name':'valid','count':-1},{'name':'valid','extra':1}):
        with pytest.raises(ValueError): svc.create(owner,inv,data)
    with pytest.raises(ValueError): svc.batch(owner,[{'operation':'sql','data':'DROP TABLE c0_objects'}])
    assert svc.list(owner,inv)==[]
    assert ObjectService(svc.database,None).access is None
    with pytest.raises(PermissionDenied): ObjectService(svc.database,None).list(owner,inv)


def test_repeat_migration_preserves_types_records_relations_and_events(objects):
    svc,owner,inv,proj=objects
    source=svc.create(owner,inv,{'name':'stable'}); target=svc.create(owner,proj,{'name':'other'})
    relation=svc.add_relation(owner,source['id'],target['id'],'depends-on',source_type=inv,target_type=proj)
    migrate_database(svc.database)
    assert svc.get(owner,source['id'])['id']==source['id']
    assert svc.get_type(owner,inv)['unique_fields']==['name']
    assert svc.relations(owner,source['id'])[0]['id']==relation['id']
    events=svc.events(owner); after=events[0]['id']
    assert all(e['id']>after for e in svc.events(owner,after=after))
    assert svc.database.health()['schema_revision']=='0015_content_spaces'


def test_event_cursor_cannot_skip_an_uncommitted_earlier_write(objects,monkeypatch):
    from threading import Event
    svc,owner,inv,_=objects
    first_written=Event(); release=Event(); second_started=Event()
    original=svc._event
    def delayed(c,actor,row,operation):
        original(c,actor,row,operation)
        if row['data'].get('name')=='first':
            first_written.set()
            assert release.wait(5)
    monkeypatch.setattr(svc,'_event',delayed)
    def second():
        second_started.set()
        return svc.create(owner,inv,{'name':'second'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(svc.create,owner,inv,{'name':'first'})
        assert first_written.wait(5)
        later=pool.submit(second); assert second_started.wait(5)
        try:
            assert not later.done()
            assert not [e for e in svc.events(owner) if e['type_name']==inv]
        finally: release.set()
        a=first.result(timeout=5); b=later.result(timeout=5)
    events=[e for e in svc.events(owner) if e['type_name']==inv]
    assert [e['object_id'] for e in events]==[a['id'],b['id']]
    assert svc.events(owner,after=events[0]['id'])[0]['object_id']==b['id']


def test_trusted_relational_resolvers_do_not_import_request_kinds(objects):
    svc,owner,inv,_=objects
    row=svc.create(owner,inv,{'name':'typed'})
    assert svc.resolve_reference(owner,'object',row['id'],inv)['data']==row['data']
    def account(c,current,key):
        assert current.user_id==owner.user_id
        profile=c.execute(text('SELECT display_name FROM c0_accounts WHERE id=:id'),{'id':key}).scalar_one_or_none()
        return {'type_name':'profile','data':{'display_name':profile}} if profile else None
    extended=ObjectService(svc.database,svc.access,reference_resolvers={'account':account})
    assert extended.resolve_reference(owner,'account',owner.user_id,'profile')['data']['display_name']=='Owner'
    with pytest.raises(ValueError,match='unknown_reference_kind'):
        extended.resolve_reference(owner,'os-system',owner.user_id,'profile')
    with pytest.raises(ObjectNotFound): extended.resolve_reference(owner,'account',uuid4(),'profile')
    with pytest.raises(ValueError,match='reference_type_mismatch'):
        extended.resolve_reference(owner,'account',owner.user_id,'wrong')
