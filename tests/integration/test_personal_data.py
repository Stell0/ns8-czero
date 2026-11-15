# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real directory/space authorization and staged import lifecycle on PostgreSQL."""
import os
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import PermissionDenied, Role, VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.migrate import migrate_database
from czero_core.personal_data import PersonalDataConflict, PersonalDataService, require_consent_role
from czero_core.sources import OriginalStore, SourceService, register_source_handlers
from czero_core.spaces import SpaceService

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def personal(tmp_path):
    base = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    name = 'c0_personal_' + uuid4().hex
    admin = create_engine(base.set(database='postgres'), isolation_level='AUTOCOMMIT')
    with admin.connect() as c:
        c.exec_driver_sql(f'CREATE DATABASE {name}')
    db = Database(base.set(database=name).render_as_string(hide_password=False))
    try:
        migrate_database(db)
        migrate_database(db)
        issuer = 'https://idp.example.test/realms/test'
        access = AccessService(db, issuer, uuid4(), admit_readers=True)
        def login(key, username='person'):
            return access.resolve(VerifiedIdentity(issuer, str(key), str(key), username, username, time.time()+300))
        owner = login(access.owner_account_key, 'owner')
        registry = default_registry()
        originals = OriginalStore(tmp_path/'originals')
        register_source_handlers(registry, db, originals)
        sources = SourceService(db, access, registry, originals)
        service = PersonalDataService(db, access, sources)
        provider, instance = uuid4(), uuid4()
        config = service.configure(owner, provider_id=provider, enabled=True, services={'webtop':str(instance)}, expected_generation=0)
        service.validate_binding(generation=config['generation'], provider_id=provider, services={'webtop':str(instance)})
        yield service, owner, provider, instance, login, registry
    finally:
        db.close()
        with admin.connect() as c:
            c.exec_driver_sql(f'DROP DATABASE {name} WITH (FORCE)')
        admin.dispose()


def provision(f, key=None, username='person', active=True):
    service, _, provider, *_ = f
    key = key or uuid4()
    rows = service.reconcile_directory(provider_id=provider, entries=[{'directory_id':str(key),'username':username,'active':active}])
    return next(row for row in rows if row['directory_id']==str(key))


def submit(f, row, **changes):
    service, _, _, instance, *_ = f
    return service.submit(owner_id=row['id'], generation=1, connector='webtop', instance_id=instance,
        remote_key='INBOX/42', kind='message', title='Synthetic mail', content=b'Original message body', **changes)


def test_provision_before_login_rename_and_username_reuse(personal):
    service, _, _, _, login, _ = personal
    row = provision(personal)
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_accounts')).scalar_one()==1
    actor = login(row['directory_id'])
    spaces = SpaceService(service.database, service.access)
    assert spaces.get(actor,row['space_id'])['role']=='editor'
    assert service.access.profile(actor)['role']=='reader'
    renamed = provision(personal, row['directory_id'], 'renamed')
    assert renamed['space_id']==row['space_id']
    replacement = provision(personal, username='person')
    other = login(replacement['directory_id'])
    assert spaces.get(other,replacement['space_id'])['role']=='editor'
    with pytest.raises(PermissionDenied): spaces.get(other,row['space_id'])
    assert len([s for s in spaces.list(actor)['spaces'] if s['personal']])==1
    assert spaces.get(actor,row['space_id'])['name']==spaces.get(other,replacement['space_id'])['name']=='Personal Data'


def test_reader_personal_editor_never_global_admin_or_shared_editor(personal):
    service, owner, *_ = personal
    row = provision(personal)
    actor = personal[4](row['directory_id'])
    spaces = SpaceService(service.database, service.access)
    with service.database.engine.connect() as c:
        assert spaces.authorize(c,actor,Role.EDITOR,space_id=row['space_id']).role is Role.EDITOR
        assert spaces.authorize_many(c,actor,[row['space_id']],Role.EDITOR)[UUID(row['space_id'])].role is Role.EDITOR
        for selected in (None, row['space_id']):
            with pytest.raises(PermissionDenied): spaces.authorize(c,actor,Role.ADMIN,space_id=selected)
        with pytest.raises(PermissionDenied): spaces.authorize(c,actor,Role.EDITOR)
    for actor_arg in (actor,owner):
        with pytest.raises((ValueError,PermissionDenied)):
            spaces.set_access(actor_arg,row['space_id'],readable_by_all=True,expected_revision=1,idempotency_key=uuid4().hex)
        with pytest.raises((ValueError,PermissionDenied)):
            spaces.set_grant(actor_arg,row['space_id'],actor.user_id,Role.READER,expected_revision=0,idempotency_key=uuid4().hex)
    require_consent_role(service.access.authorize(actor,Role.READER),Role.EDITOR)
    with pytest.raises(PermissionDenied): require_consent_role(actor,Role.ADMIN)


def test_directory_loss_incomplete_inventory_and_persistent_block(personal):
    service, owner, provider, _, login, _ = personal
    row = provision(personal)
    actor = login(row['directory_id'])
    spaces = SpaceService(service.database, service.access)
    service.reconcile_directory(provider_id=provider,entries=[],complete=False)
    assert spaces.get(actor,row['space_id'])
    service.access.set_role(owner,actor.user_id,None)
    with pytest.raises(PermissionDenied): spaces.get(actor,row['space_id'])
    with pytest.raises(PermissionDenied): login(row['directory_id'])
    service.access.set_role(owner,actor.user_id,Role.READER)
    service.reconcile_directory(provider_id=provider,entries=[],complete=True)
    with pytest.raises(PermissionDenied): spaces.get(actor,row['space_id'])
    assert spaces.get(owner,row['space_id'])['role']=='admin'


def test_disable_fences_staging_and_preserves_space(personal):
    service, owner, provider, instance, login, registry = personal
    row = provision(personal)
    actor = login(row['directory_id'])
    staged = submit(personal,row)
    config = service.configure(owner,provider_id=provider,enabled=False,services={'webtop':str(instance)},expected_generation=1)
    assert config['generation']==2
    with pytest.raises(PersonalDataConflict): submit(personal,row)
    with service.database.engine.begin() as c:
        from czero_core.current_content import ContentSuperseded
        from czero_core.personal_data import guard_publication
        with pytest.raises(ContentSuperseded): guard_publication(c,UUID(staged['source_id']))
    assert service.cleanup()==1 and service.cleanup()==0
    assert SpaceService(service.database,service.access).get(actor,row['space_id'])['role']=='editor'
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_source_versions')).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM c0_documents')).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM c0_personal_imports WHERE content_hash IS NOT NULL')).scalar_one()==0


def test_local_delete_exclusion_survives_disable(personal):
    service,owner,provider,instance,login,_ = personal
    row=provision(personal); actor=login(row['directory_id'])
    first=submit(personal,row)
    selected=service.sources.in_space(row['space_id'])
    selected.delete(actor,first['source_id'],expected_revision=1)
    assert submit(personal,row)['state']=='excluded'
    service.configure(owner,provider_id=provider,enabled=False,services={'webtop':str(instance)},expected_generation=1)
    assert service.cleanup()==1  # payload is removed; the exclusion remains
    service.configure(owner,provider_id=provider,enabled=True,services={'webtop':str(instance)},expected_generation=2)
    service.validate_binding(generation=3,provider_id=provider,services={'webtop':str(instance)})
    assert service.submit(owner_id=row['id'],generation=3,connector='webtop',instance_id=instance,
        remote_key='INBOX/42',kind='message',title='Should stay excluded',content=b'new body')['state']=='excluded'


def test_wrong_provider_wrong_owner_and_ambiguous_directory_fail(personal):
    service,owner,provider,instance,_,_=personal
    row=provision(personal)
    with pytest.raises(PersonalDataConflict):
        service.reconcile_directory(provider_id=uuid4(),entries=[])
    with pytest.raises(ValueError):
        service.configure(owner,provider_id=uuid4(),enabled=True,services={'webtop':str(instance)},expected_generation=1)
    with pytest.raises(PersonalDataConflict):
        service.submit(owner_id=uuid4(),generation=1,connector='webtop',instance_id=instance,
            remote_key='x',kind='message',title='Wrong owner',content=b'should never publish')
    with pytest.raises(ValueError):
        service.reconcile_directory(provider_id=provider,entries=[{'directory_id':str(uuid4()),'username':'same','active':True},
            {'directory_id':str(uuid4()),'username':'same','active':True}])


def test_native_runner_reports_missing_session_without_deletion(personal):
    from czero_app.personal_data.runner import Runner
    service,owner,provider,instance,_,_=personal
    row=provision(personal)
    first=submit(personal,row)
    snapshot={'configuration':{'enabled':True,'webtop':str(instance),'nethvoice':None},
        'provider_id':str(provider),'provider_verified':True,'directory_complete':True,
        'directory':[{'directory_id':row['directory_id'],'username':'person','active':True}],
        'endpoints':{'webtop':'https://mail.example.test'},'mail_domain':'example.test'}
    result=Runner(service).tick(snapshot,{})
    assert result['users'][0]['status']=='suspended'
    assert result['users'][0]['error_code']=='session_unavailable'
    assert result['imports']['managed']==1 and result['pending_cleanup']==0
    # Even a native discovery outage cannot become source deletion.
    result=Runner(service).tick({**snapshot,'provider_verified':False},{})
    assert result['status']=='source_unavailable' and result['imports']['managed']==1
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_source_versions WHERE source_id=:id'),{'id':UUID(first['source_id'])}).scalar_one()==1
    service.reconcile_directory(provider_id=provider,entries=[],complete=True)
    inactive=Runner(service).status()['users'][0]
    assert inactive['status']=='suspended' and inactive['error_code']=='directory_inactive'


def test_native_runner_verified_provider_mismatch_retires_imports(personal):
    from czero_app.personal_data.runner import Runner
    service,_,provider,instance,_,_=personal
    row=provision(personal);submit(personal,row)
    snapshot={'configuration':{'enabled':True,'webtop':str(instance)},'provider_id':str(uuid4()),
              'provider_verified':False,'provider_mismatch':True}
    result=Runner(service).tick(snapshot,{})
    assert result['status']=='provider_mismatch' and result['imports']['removed']==1
    assert result['pending_cleanup']==0


def test_local_edit_can_publish_while_managed_pending_generation_is_fenced(personal):
    from czero_core.personal_data import guard_publication
    from czero_core.current_content import ContentSuperseded
    service,_,_,_,login,_=personal
    row=provision(personal);actor=login(row['directory_id']);first=submit(personal,row)
    edited=service.sources.in_space(row['space_id']).ingest_text(actor,idempotency_key=uuid4().hex,
        title='Locally edited',body='My own edited content',source_id=first['source_id'],expected_revision=1)
    with service.database.engine.begin() as c:
        guard_publication(c,UUID(first['source_id']),edited['id'])
        with pytest.raises(ContentSuperseded):guard_publication(c,UUID(first['source_id']),UUID(first['version_id']))
    assert submit(personal,row)['state']=='overridden'


def test_disable_reenable_reimports_without_turning_cleanup_into_user_exclusion(personal):
    service,owner,provider,instance,_,_=personal
    row=provision(personal);first=submit(personal,row)
    service.configure(owner,provider_id=provider,enabled=False,services={'webtop':str(instance)},expected_generation=1)
    assert service.cleanup()==1
    service.configure(owner,provider_id=provider,enabled=True,services={'webtop':str(instance)},expected_generation=2)
    service.validate_binding(generation=3,provider_id=provider,services={'webtop':str(instance)})
    second=service.submit(owner_id=row['id'],generation=3,connector='webtop',instance_id=instance,
        remote_key='INBOX/42',kind='message',title='Synthetic mail',content=b'Original message body')
    assert second['state']=='staged' and second['source_id']!=first['source_id']


def test_personal_api_key_write_ceiling_and_read_scope(personal):
    from czero_core.api_keys import ApiKeyService
    from czero_core.operations import ScopeDenied
    service,_,_,_,login,_=personal
    row=provision(personal);actor=login(row['directory_id'])
    keys=ApiKeyService(service.access,client_id='native-test',client_secret='synthetic-secret',resource='https://c0.example.test/mcp')
    writable=keys.create(actor,name='own personal data',scopes={'c0:read','c0:write'},space_ids=[row['space_id']])
    writer=keys.verify(writable['key'],resource='https://c0.example.test/mcp').actor
    source=service.sources.in_space(row['space_id'])
    assert source.ingest_text(writer,idempotency_key=uuid4().hex,title='My authored evidence',body='Separately authored personal evidence')
    with pytest.raises(PermissionDenied):service.sources.ingest_text(writer,idempotency_key=uuid4().hex,title='No Shared access',body='Forbidden')
    readonly=keys.create(actor,name='personal read',scopes={'c0:read'},space_ids=[row['space_id']])
    reader=keys.verify(readonly['key'],resource='https://c0.example.test/mcp').actor
    with pytest.raises(ScopeDenied):source.ingest_text(reader,idempotency_key=uuid4().hex,title='No write scope',body='Forbidden')
    with service.database.engine.connect() as c:shared=SpaceService.shared_id(c)
    shared_key=keys.create(actor,name='Shared only',scopes={'c0:read'},space_ids=[shared])
    shared_actor=keys.verify(shared_key['key'],resource='https://c0.example.test/mcp').actor
    assert not service.access.authorize(shared_actor,Role.READER).personal_editor


def test_operation_discovery_and_selected_personal_write(personal):
    from czero_core.operations import Operation,OperationRegistry,ScopeDenied
    service,_,_,_,login,_=personal
    row=provision(personal);actor=login(row['directory_id'])
    spaces=SpaceService(service.database,service.access)
    registry=OperationRegistry(service.access.authorize)
    def select(current,args):
        with service.database.engine.connect() as c:
            return spaces.authorize(c,current,Role.EDITOR,space_id=args['space_id'],check_scopes=False)
    registry.register(Operation('write_personal','Write selected personal content',Role.EDITOR,'c0:write',{}, {},
        lambda current,args:current.role.value,False,preauthorize=select))
    assert registry.describe(actor,scopes={'c0:read'})==[]
    assert len(registry.describe(actor,scopes={'c0:write'}))==1
    assert registry.execute('write_personal',actor,{'space_id':row['space_id']},scopes={'c0:write'})=='editor'
    with pytest.raises(ScopeDenied):registry.execute('write_personal',actor,{'space_id':row['space_id']},scopes={'c0:read'})
    with pytest.raises(PermissionDenied):registry.execute('write_personal',actor,{'space_id':None},scopes={'c0:write'})


def test_partial_inventory_cannot_supply_removal_candidates(personal):
    from datetime import datetime,timedelta,timezone
    from czero_core.personal_data import inventory_candidates,record_checkpoint,queue_confirmed_removal
    service,owner,provider,instance,_,_=personal
    row=provision(personal);first=submit(personal,row)
    scan=uuid4()
    # No prior complete inventory: an absent receipt is retained.
    digest,missing=inventory_candidates(service,owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,scan_id=scan)
    assert missing==[]
    record_checkpoint(service,owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,
        cursor={'inventory_hash':digest},status='partial',complete=False)
    _,missing=inventory_candidates(service,owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,scan_id=scan)
    assert missing==[]
    # Even two immediately repeated complete scans cannot delete during page shifts.
    record_checkpoint(service,owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,
        cursor={'inventory_hash':digest},status='reconciled',complete=True)
    _,missing=inventory_candidates(service,owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,scan_id=scan)
    assert missing==[]
    with service.database.engine.begin() as c:
        c.execute(text("UPDATE c0_personal_checkpoints SET last_inventory=now()-interval '6 minutes' WHERE owner_id=:owner"),{'owner':UUID(row['id'])})
    _,missing=inventory_candidates(service,owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,scan_id=scan)
    assert len(missing)==1 and str(missing[0]['source_id'])==first['source_id']
    # Candidates themselves did not delete anything; only a separately confirmed read can queue retirement.
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT deleted FROM c0_sources WHERE id=:id'),{'id':UUID(first['source_id'])}).scalar_one() is False
    queue_confirmed_removal(service,owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,remote_key='INBOX/42')
    assert service.cleanup()==1


def test_distinct_personal_copies_actual_extraction_and_privacy_cleanup(personal):
    from czero_app.personal_data.runner import Runner
    from czero_core.sources import SourceNotFound
    service,owner,provider,instance,login,registry=personal
    first_owner=provision(personal,username='first')
    second_owner=provision(personal,username='second')
    first=submit(personal,first_owner);second=submit(personal,second_owner)
    assert first['source_id']!=second['source_id'] and first['version_id']!=second['version_id']
    for imported in (first,second):
        with service.database.engine.begin() as c:
            assert registry.get('source.extract').execute(c,{'version_id':imported['version_id']})['state']=='ready'
    first_actor=login(first_owner['directory_id'],'first')
    selected=service.sources.in_space(first_owner['space_id'])
    assert selected.document(first_actor,first['version_id'])['body']=='Original message body'
    with pytest.raises(SourceNotFound):selected.document(first_actor,second['version_id'])
    local=selected.ingest_text(first_actor,idempotency_key=uuid4().hex,title='My correction',body='Local correction',
        source_id=first['source_id'],expected_revision=1)
    with service.database.engine.begin() as c:
        assert registry.get('source.extract').execute(c,{'version_id':str(local['id'])})['state']=='ready'
    assert selected.document(first_actor,local['id'])['body']=='Local correction'
    assert submit(personal,first_owner)['state']=='overridden'
    service.configure(owner,provider_id=provider,enabled=False,services={'webtop':str(instance)},expected_generation=1)
    Runner(service)._cleanup()
    assert Runner(service).status()['pending_cleanup']==0
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_documents')).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM c0_chunks')).scalar_one()==0
    assert not any(service.sources.originals.root.glob('[0-9a-f]*'))


def test_missing_message_id_local_exclusion_covers_ambiguous_uid_reuse(personal):
    service,_,_,instance,login,_=personal
    row=provision(personal);actor=login(row['directory_id'])
    args=dict(owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,kind='message',title='Missing Message-ID',
        metadata={'personal_import_slot':'["INBOX",42]','personal_identity_kind':'content_hash'})
    first=service.submit(**args,remote_key='["INBOX",42,"first"]',content=b'First body')
    service.sources.in_space(row['space_id']).delete(actor,first['source_id'],expected_revision=1)
    service.cleanup()
    changed=service.submit(**args,remote_key='["INBOX",42,"different"]',content=b'Changed or reused UID; ambiguous')
    assert changed['state']=='excluded' and changed['source_id'] is None


def test_native_post_read_binding_check_denies_publication(personal,monkeypatch):
    from types import SimpleNamespace
    from czero_app.personal_data.runner import Runner
    from czero_app.personal_data.connectors import Document
    import czero_app.personal_data.runner as module
    service,_,provider,instance,_,_=personal
    row=provision(personal)
    class Mail:
        def __init__(self,*args,**kwargs):self.client=SimpleNamespace(close=lambda:None)
        def folders(self):return [{'id':'INBOX'}]
        def page(self,*args,**kwargs):return [Document('message','message','Mail',b'Mail body')],{'complete':True,'issues':[]}
    monkeypatch.setattr(module,'WebTop',Mail)
    snapshot={'configuration':{'enabled':True,'webtop':str(instance)},'provider_id':str(provider),
        'provider_verified':True,'directory_complete':True,'directory':[{'directory_id':row['directory_id'],'username':'person','active':True}],
        'endpoints':{'webtop':'https://mail.example.test'},'mail_domain':'example.test'}
    credentials={'webtop':{str(instance):{'api_key':'dedicated-key'}}}
    with pytest.raises(PersonalDataConflict):Runner(service,before_publish=lambda:False).tick(snapshot,credentials)
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_sources')).scalar_one()==0
    assert Runner(service,before_publish=lambda:True).tick(snapshot,credentials)['imports']['managed']==1


def test_native_disable_is_not_blocked_by_running_collector_lock(personal):
    from czero_app.personal_data.runner import Runner,RUNNER_LOCK
    service,_,provider,instance,_,_=personal
    row=provision(personal);submit(personal,row)
    with service.database.engine.connect() as lock:
        lock.execute(text('SELECT pg_advisory_lock(:key)'),{'key':RUNNER_LOCK})
        try:
            result=Runner(service).tick({'configuration':{'enabled':False,'webtop':str(instance)},'provider_id':str(provider)}, {},configure_only=True)
            assert result['imports']['removed']==1 and result['pending_cleanup']==0
        finally:lock.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':RUNNER_LOCK})


def test_account_block_fences_already_staged_import(personal):
    from czero_core.personal_data import guard_publication
    from czero_core.current_content import ContentSuperseded
    service,owner,_,_,login,_=personal
    row=provision(personal);actor=login(row['directory_id'])
    staged=submit(personal,row)
    service.access.set_role(owner,actor.user_id,None)
    with service.database.engine.begin() as c:
        with pytest.raises(ContentSuperseded):
            guard_publication(c,UUID(staged['source_id']),UUID(staged['version_id']))


def test_attachment_observations_persist_without_payloads_and_clear_after_retry(personal):
    from czero_core.personal_data import record_attachment_issues
    service,_,_,instance,_,_=personal
    row=provision(personal)
    values=dict(owner_id=row['id'],generation=1,instance_id=instance,remote_key='message-slot')
    record_attachment_issues(service,**values,issues=[{'attachment_id':'part-1','code':'too_large'}])
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT attachment_id,code FROM c0_personal_issues')).one()==('part-1','too_large')
    record_attachment_issues(service,**values,issues=[])
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_personal_issues')).scalar_one()==0


def test_native_runner_does_not_read_source_for_blocked_account(personal,monkeypatch):
    from czero_app.personal_data.runner import Runner
    import czero_app.personal_data.runner as module
    service,owner,provider,instance,login,_=personal
    row=provision(personal);actor=login(row['directory_id'])
    service.access.set_role(owner,actor.user_id,None)
    def forbidden(*a,**kw):raise AssertionError('source read for blocked account')
    monkeypatch.setattr(module,'WebTop',forbidden)
    snapshot={'configuration':{'enabled':True,'webtop':str(instance),'nethvoice':None},
        'provider_id':str(provider),'provider_verified':True,'directory_complete':True,
        'directory':[{'directory_id':row['directory_id'],'username':'person','active':True}],
        'endpoints':{'webtop':'https://mail.example.test'},'mail_domain':'example.test'}
    result=Runner(service).tick(snapshot,{'webtop':{str(instance):{'api_key':'synthetic-test-key'}}})
    assert result['users'][0]['status']=='suspended' and result['users'][0]['error_code']=='account_blocked'


def test_local_message_deletion_excludes_attachments_and_future_parts(personal):
    service,_,_,instance,login,_=personal
    row=provision(personal);actor=login(row['directory_id']);parent=submit(personal,row)
    def attachment(part):
        return service.submit(owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,
            remote_key='INBOX/42/attachment/'+part,kind='attachment',title='Synthetic attachment',content=b'Attachment body',
            metadata={'parent_import_key':'INBOX/42'})
    child=attachment('one')
    service.sources.in_space(row['space_id']).delete(actor,parent['source_id'],expected_revision=1)
    assert attachment('one')['state']=='excluded' and attachment('two')['state']=='excluded'
    service.cleanup()
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_source_versions')).scalar_one()==0
        assert set(c.execute(text('SELECT state FROM c0_personal_imports')).scalars())=={'excluded'}


def test_reused_username_cannot_inherit_old_directory_credentials(personal,monkeypatch):
    from czero_app.personal_data.runner import Runner
    import czero_app.personal_data.runner as module
    service,owner,provider,instance,_,_=personal
    previous=provision(personal,username='person')
    voice=uuid4()
    service.configure(owner,provider_id=provider,enabled=True,services={'nethvoice':str(voice)},expected_generation=1)
    replacement=uuid4()
    def forbidden(*a,**kw):raise AssertionError('old credential routed to replacement identity')
    monkeypatch.setattr(module,'NethVoice',forbidden)
    snapshot={'configuration':{'enabled':True,'webtop':None,'nethvoice':str(voice)},
        'provider_id':str(provider),'provider_verified':True,'directory_complete':True,
        'directory':[{'directory_id':str(replacement),'username':'person','active':True}],
        'endpoints':{'nethvoice':'https://voice.example.test'}}
    result=Runner(service).tick(snapshot,{'nethvoice':{str(voice):{'users':{previous['directory_id']:'synthetic-old-session'}}}})
    assert result['users'][0]['status']=='suspended' and result['users'][0]['error_code']=='session_unavailable'
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_personal_owners WHERE active')).scalar_one()==1
        assert c.execute(text('SELECT count(*) FROM c0_personal_imports')).scalar_one()==0


def test_unchanged_pending_content_requires_fresh_read_after_config_generation(personal):
    from czero_core.personal_data import guard_publication
    from czero_core.current_content import ContentSuperseded
    service,owner,provider,instance,login,registry=personal
    row=provision(personal);first=submit(personal,row)
    services={'webtop':str(instance),'nethvoice':str(uuid4())}
    service.configure(owner,provider_id=provider,enabled=True,services=services,expected_generation=1)
    service.validate_binding(generation=2,provider_id=provider,services=services)
    with service.database.engine.begin() as c:
        with pytest.raises(ContentSuperseded):guard_publication(c,UUID(first['source_id']),UUID(first['version_id']))
    refreshed=service.submit(owner_id=row['id'],generation=2,connector='webtop',instance_id=instance,
        remote_key='INBOX/42',kind='message',title='Synthetic mail',content=b'Original message body')
    assert refreshed['state']=='staged' and refreshed['source_id']==first['source_id']
    with service.database.engine.begin() as c:
        registry.get('source.extract').execute(c,{'version_id':refreshed['version_id']})
    versions=service.sources.in_space(row['space_id']).versions(login(row['directory_id']),first['source_id'])
    assert len(versions)==1 and versions[0]['state']=='ready'


def test_provider_directory_registry_is_unique_and_cannot_follow_new_issuer(personal):
    service,_,provider,instance,_,_=personal
    row=provision(personal)
    issuer='https://other-idp.example.test/realm';key=uuid4()
    access=AccessService(service.database,issuer,key,admit_readers=True)
    other_owner=access.resolve(VerifiedIdentity(issuer,str(key),str(key),'owner','Owner',time.time()+300))
    other=PersonalDataService(service.database,access,service.sources)
    other.configure(other_owner,provider_id=provider,enabled=True,services={'webtop':str(instance)},expected_generation=0)
    with pytest.raises(PersonalDataConflict):
        other.reconcile_directory(provider_id=provider,entries=[{'directory_id':row['directory_id'],'username':'person','active':True}])
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_personal_owners')).scalar_one()==1


def test_native_early_fence_precedes_worker_and_identity_changes(personal):
    from czero_core.personal_data import guard_publication
    from czero_core.current_content import ContentSuperseded
    service,_,_,_,login,_=personal
    row=provision(personal);first=submit(personal,row)
    assert service.fence_native(disabled=True)=={'status':'unverified','pending_cleanup':1}
    with service.database.engine.begin() as c:
        with pytest.raises(ContentSuperseded):guard_publication(c,UUID(first['source_id']),UUID(first['version_id']))
    assert SpaceService(service.database,service.access).get(login(row['directory_id']),row['space_id'])['role']=='editor'
    assert service.cleanup()==1


def test_native_disable_cleanup_does_not_require_readable_source_credentials(personal,monkeypatch,capsys):
    import czero_app.personal_data.runner as module
    service,_,provider,instance,_,_=personal
    row=provision(personal);submit(personal,row)
    snapshot={'issuer':service.access.issuer,'provider_id':str(provider),
        'configuration':{'enabled':False,'webtop':str(instance),'nethvoice':None}}
    def private(path):
        assert path.endswith('runtime.json'),'Disabled cleanup attempted to load broken credentials'
        return snapshot
    monkeypatch.setattr(module,'private_json',private)
    monkeypatch.setattr(module,'Database',lambda:service.database)
    monkeypatch.setenv('CZERO_SOURCE_DIR',str(service.sources.originals.root))
    monkeypatch.setattr(module.sys,'argv',['runner'])
    assert module.main()==0
    import json
    assert json.loads(capsys.readouterr().out)['pending_cleanup']==0
    with service.database.engine.connect() as c:
        assert c.execute(text("SELECT state FROM c0_personal_imports")).scalar_one()=='removed'


def test_fresh_read_recovers_exhausted_extraction_without_duplicate_source(personal):
    service,_,_,_,login,registry=personal
    row=provision(personal);first=submit(personal,row)
    with service.database.engine.begin() as c:
        c.execute(text("UPDATE c0_jobs SET state='failed',error_code='interrupted' WHERE id=(SELECT job_id FROM c0_source_versions WHERE id=:id)"),{'id':UUID(first['version_id'])})
    from czero_app.personal_data.runner import Runner
    assert Runner(service).status()['extraction']=={'failed':1}
    recovered=submit(personal,row)
    assert recovered['state']=='staged' and recovered['source_id']==first['source_id'] and recovered['version_id']!=first['version_id']
    with service.database.engine.begin() as c:
        registry.get('source.extract').execute(c,{'version_id':recovered['version_id']})
    versions=service.sources.in_space(row['space_id']).versions(login(row['directory_id']),first['source_id'])
    assert len(versions)==1 and versions[0]['number']==2 and versions[0]['state']=='ready'
    assert submit(personal,row)['state']=='unchanged'
