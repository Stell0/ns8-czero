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
    with pytest.raises(PersonalDataConflict):Runner(service,before_publish=lambda owner:False).tick(snapshot,credentials)
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_sources')).scalar_one()==0
    assert Runner(service,before_publish=lambda owner:True).tick(snapshot,credentials)['imports']['managed']==1


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
    assert result['users'][0]['status']=='suspended' and result['users'][0]['error_code']=='identity_ambiguous'
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


@pytest.mark.parametrize('head_unavailable',[False,True])
def test_backfill_reads_new_arrivals_without_losing_historical_progress(personal,monkeypatch,head_unavailable):
    from types import SimpleNamespace
    from czero_app.personal_data.runner import Runner
    from czero_app.personal_data.connectors import Document,Unavailable
    from czero_core.personal_data import record_checkpoint
    import czero_app.personal_data.runner as module
    service,_,provider,instance,_,_=personal
    row=provision(personal);scan=str(uuid4());calls=[]
    import hashlib,json
    folder_hash=hashlib.sha256(json.dumps(['INBOX','Sent']).encode()).hexdigest()
    record_checkpoint(service,owner_id=row['id'],generation=1,connector='webtop',instance_id=instance,
        cursor={'page_size':5,'page':7,'folder_index':0,'head_folder_index':1,'scan_id':scan,'folder_hash':folder_hash},status='backfill')
    class Mail:
        def __init__(self,*args,**kwargs):self.client=SimpleNamespace(close=lambda:None)
        def folders(self):return [{'id':'INBOX'},{'id':'Sent'}]
        def page(self,folder,*,page,size):
            calls.append((folder,page,size))
            if folder=='Sent' and head_unavailable:raise Unavailable('session_unavailable')
            recent=folder=='Sent'
            return [Document('recent' if recent else 'historical','message','Mail',b'Fresh body' if recent else b'Old body')],{'complete':False,'issues':[]}
    monkeypatch.setattr(module,'WebTop',Mail)
    snapshot={'configuration':{'enabled':True,'webtop':str(instance)},'provider_id':str(provider),
        'provider_verified':True,'directory_complete':True,'directory':[{'directory_id':row['directory_id'],'username':'person','active':True}],
        'endpoints':{'webtop':'https://mail.example.test'},'mail_domain':'example.test'}
    result=Runner(service,before_publish=lambda owner:True).tick(snapshot,{'webtop':{str(instance):{'api_key':'synthetic-dedicated-key'}}})
    assert calls==[('INBOX',7,5),('Sent',0,5)]
    assert result['imports']['managed']==(1 if head_unavailable else 2)
    checkpoint=result['users'][0]
    assert checkpoint['cursor']['page']==8 and checkpoint['cursor']['scan_id']==scan
    assert checkpoint['last_inventory'] is None
    assert checkpoint['error_code']==('session_unavailable' if head_unavailable else None)
    assert checkpoint['status']==('suspended' if head_unavailable else 'backfill')


def test_status_includes_directory_people_before_their_first_ingestion_attempt(personal):
    from czero_app.personal_data.runner import Runner
    from pathlib import Path
    import json,jsonschema
    service,_,_,instance,_,_=personal
    provision(personal,username='alice')
    provision(personal,username='bob')
    value=Runner(service).status()
    assert [(r['username'],r['status'],r['inventory_overdue']) for r in value['users']]==[
        ('alice','unverified',True),('bob','unverified',True)]
    assert all(r['cursor']=={} and r['last_success'] is None for r in value['users'])
    schema=json.loads((Path(__file__).resolve().parents[2]/'imageroot/actions/get-personal-data-status/validate-output.json').read_text())
    jsonschema.validate(value,schema)


@pytest.mark.parametrize('historical_complete',[False,True])
def test_nethvoice_backfill_keeps_its_window_and_also_reads_current_calls(personal,monkeypatch,historical_complete):
    from datetime import datetime,timedelta,timezone
    from types import SimpleNamespace
    from czero_app.personal_data.runner import Runner
    from czero_app.personal_data.connectors import Document
    from czero_core.personal_data import record_checkpoint
    import czero_app.personal_data.runner as module
    service,admin,provider,instance,_,_=personal
    config=service.configure(admin,provider_id=provider,enabled=True,services={'nethvoice':str(instance)},expected_generation=1)
    row=provision(personal);calls=[]
    record_checkpoint(service,owner_id=row['id'],generation=config['generation'],connector='nethvoice',instance_id=instance,
        cursor={'page_size':5,'page':3,'window_end':'20260101','scan_id':str(uuid4())},status='backfill')
    class Voice:
        def __init__(self,*args,**kwargs):self.client=SimpleNamespace(close=lambda:None)
        def page(self,**kwargs):
            calls.append(kwargs)
            return [Document(str(kwargs['page']),'transcript','Call',b'Participated call',metadata={'uniqueid':'fixture-call'})],{'complete':historical_complete,'skipped':0}
    monkeypatch.setattr(module,'NethVoice',Voice)
    snapshot={'configuration':{'enabled':True,'nethvoice':str(instance)},'provider_id':str(provider),
        'provider_verified':True,'directory_complete':True,'directory':[{'directory_id':row['directory_id'],'username':'person','active':True}],
        'endpoints':{'nethvoice':'https://voice.example.test'}}
    value=Runner(service,before_publish=lambda owner:True).tick(snapshot,{'nethvoice':{str(instance):{'users':{row['directory_id']:'synthetic-selected-session'}}}})
    current_end=(datetime.now(timezone.utc)+timedelta(days=1)).strftime('%Y%m%d')
    expected=[{'start':'19000101','end':'20260101','page':3,'size':5}]
    if not historical_complete:expected.append({'start':'19000101','end':current_end,'page':1,'size':5})
    assert calls==expected
    assert value['imports']['managed']==(1 if historical_complete else 2)
    checkpoint=value['users'][0]
    assert checkpoint['cursor']['window_end']==(current_end if historical_complete else '20260101')
    assert checkpoint['cursor']['page']==(1 if historical_complete else 4)
    assert checkpoint['last_inventory'] is None and checkpoint['status']=='backfill'


def test_call_participants_have_separate_locally_linked_transcript_and_summary_copies(personal,monkeypatch):
    from types import SimpleNamespace
    from czero_app.personal_data.runner import Runner
    from czero_app.personal_data.connectors import Document
    import czero_app.personal_data.runner as module
    service,admin,provider,instance,_,_=personal
    service.configure(admin,provider_id=provider,enabled=True,services={'nethvoice':str(instance)},expected_generation=1)
    alice=provision(personal,username='alice');bob=provision(personal,username='bob')
    class Voice:
        def __init__(self,*args,**kwargs):self.client=SimpleNamespace(close=lambda:None)
        def page(self,**kwargs):
            return [Document('42','transcript','Call',b'Participated call',metadata={'uniqueid':'fixture-call'}),
                    Document('42','summary','Summary',b'Existing summary',metadata={'related_import_key':'42','uniqueid':'fixture-call'})],{'complete':True,'skipped':0}
    monkeypatch.setattr(module,'NethVoice',Voice)
    snapshot={'configuration':{'enabled':True,'nethvoice':str(instance)},'provider_id':str(provider),
        'provider_verified':True,'directory_complete':True,'directory':[
            {'directory_id':row['directory_id'],'username':row['username'],'active':True} for row in (alice,bob)],
        'endpoints':{'nethvoice':'https://voice.example.test'}}
    secrets={'nethvoice':{str(instance):{'users':{row['directory_id']:'synthetic-selected-session' for row in (alice,bob)}}}}
    assert Runner(service,before_publish=lambda owner:True).tick(snapshot,secrets)['imports']['managed']==4
    with service.database.engine.connect() as c:
        pairs=c.execute(text("""SELECT s.space_id,s.metadata->>'transcript_source_id' AS parent,t.source_id
            FROM c0_personal_imports summary JOIN c0_sources s ON s.id=summary.source_id
            JOIN c0_personal_imports t ON t.owner_id=summary.owner_id AND t.instance_id=summary.instance_id
                AND t.connector=summary.connector AND t.remote_key=summary.remote_key AND t.kind='transcript'
            WHERE summary.kind='summary'""")).mappings().all()
    assert len(pairs)==2 and len({r['space_id'] for r in pairs})==2
    assert all(r['parent']==str(r['source_id']) for r in pairs)
    assert len({r['parent'] for r in pairs})==2


def test_call_existence_checks_use_receipt_identity_after_a_local_metadata_override(personal):
    import hashlib,json
    from types import SimpleNamespace
    from czero_core.personal_data import record_checkpoint,inventory_candidates
    from czero_app.personal_data.runner import Runner
    from czero_app.personal_data.connectors import Unavailable
    service,admin,provider,instance,login,_=personal
    service.configure(admin,provider_id=provider,enabled=True,services={'nethvoice':str(instance)},expected_generation=1)
    service.validate_binding(generation=2,provider_id=provider,services={'nethvoice':str(instance)})
    row=provision(personal);actor=login(row['directory_id'])
    result=service.submit(owner_id=row['id'],generation=2,connector='nethvoice',instance_id=instance,
        remote_key='42',kind='transcript',title='Call',content=b'Original call',metadata={'uniqueid':'original-call','linkedid':'transfer-root'})
    source=service.sources.in_space(row['space_id'])
    source.ingest_text(actor,title='My correction',body='Local correction',source_id=result['source_id'],
        expected_revision=source.get(actor,result['source_id'])['revision'],metadata={'uniqueid':'edited-call'},idempotency_key='override')
    digest=hashlib.sha256(b'[]').hexdigest()
    record_checkpoint(service,owner_id=row['id'],generation=2,connector='nethvoice',instance_id=instance,
        cursor={'inventory_hash':digest},status='reconciled',complete=True)
    with service.database.engine.begin() as c:
        c.execute(text("UPDATE c0_personal_checkpoints SET last_inventory=now()-interval '6 minutes' WHERE owner_id=:id"),{'id':UUID(row['id'])})
    _,missing=inventory_candidates(service,owner_id=row['id'],generation=2,connector='nethvoice',instance_id=instance,scan_id=str(uuid4()))
    assert len(missing)==1 and json.loads(missing[0]['slot_key'])==['original-call','transfer-root']
    def read(path,*,params):
        assert path=='/transcripts/original-call' and params=={'id':42,'linkedid':'transfer-root'}
        raise Unavailable('source_not_found')
    Runner(service,before_publish=lambda owner:True)._confirm_missing(SimpleNamespace(client=SimpleNamespace(read=read)),
        'nethvoice',missing[0],row,2,str(instance))
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT state FROM c0_personal_imports WHERE source_id=:id'),{'id':UUID(result['source_id'])}).scalar_one()=='cleanup'


def test_disconnect_intent_fences_and_queues_only_the_replaced_connection(personal):
    from czero_core.personal_data import guard_publication
    from czero_core.current_content import ContentSuperseded
    service,admin,provider,instance,login,_=personal
    row=provision(personal);first=submit(personal,row)
    voice=str(uuid4());services={'webtop':str(instance),'nethvoice':voice}
    service.configure(admin,provider_id=provider,enabled=True,services=services,expected_generation=1)
    service.validate_binding(generation=2,provider_id=provider,services=services)
    kept=service.submit(owner_id=row['id'],generation=2,connector='nethvoice',instance_id=voice,
        remote_key='42',kind='transcript',title='Kept call',content=b'Synthetic kept call',metadata={'uniqueid':'kept-call'})
    replacement=str(uuid4())
    value=service.fence_native(services={'webtop':replacement,'nethvoice':voice})
    assert value['pending_cleanup']==1
    with service.database.engine.connect() as c:
        config=c.execute(text('SELECT services,validated,generation FROM c0_personal_config WHERE issuer=:issuer'),{'issuer':service.access.issuer}).mappings().one()
        assert config['services']==services and not config['validated'] and config['generation']==3
        with pytest.raises(ContentSuperseded):guard_publication(c,UUID(first['source_id']))
    service.cleanup()
    sources=service.sources.in_space(row['space_id']);actor=login(row['directory_id'])
    assert sources.get(actor,first['source_id'])['deleted']
    assert not sources.get(actor,kept['source_id'])['deleted']
    assert sources.get(actor,kept['source_id'])['managed_import']['state']=='managed'
    assert sources.originals.path(kept['version_id']).exists()


def test_administrator_can_identify_own_personal_space_without_matching_names(personal):
    service,admin,_,_,_,_=personal
    mine=provision(personal,key=service.access.owner_account_key,username='owner')
    other=provision(personal,username='other')
    spaces=SpaceService(service.database,service.access)
    visible=spaces.list(admin)['spaces']
    owned=[row for row in visible if row['personal_owner']]
    assert len(owned)==1 and owned[0]['id']==mine['space_id'] and owned[0]['name']=='Personal Data'
    assert not spaces.get(admin,other['space_id'])['personal_owner']
    assert spaces.get(admin,mine['space_id'])['personal_owner']
    assert service.access.profile(admin)['role']=='admin'


def test_observed_alias_reuse_suspends_import_but_preserves_own_space(personal,monkeypatch):
    from czero_app.personal_data.runner import Runner
    service,_,provider,instance,login,_=personal
    first=provision(personal,username='Person')
    renamed=provision(personal,first['directory_id'],'renamed')
    assert not renamed['source_identity_ambiguous']
    replacement=provision(personal,username='PERSON')
    assert replacement['source_identity_ambiguous']
    with pytest.raises(PersonalDataConflict):submit(personal,replacement)
    again=provision(personal,replacement['directory_id'],'fresh')
    assert again['source_identity_ambiguous']
    actor=login(again['directory_id'],'fresh')
    assert SpaceService(service.database,service.access).get(actor,again['space_id'])['role']=='editor'
    def forbidden(*args,**kwargs):raise AssertionError('ambiguous source identity must not be queried')
    monkeypatch.setattr('czero_app.personal_data.runner.WebTop',forbidden)
    snapshot={'issuer':service.access.issuer,'provider_id':str(provider),'provider_verified':True,
              'configuration':{'enabled':True,'webtop':str(instance),'nethvoice':None},
              'directory':[{'directory_id':again['directory_id'],'username':'fresh','active':True}],
              'directory_complete':True,'endpoints':{'webtop':'https://mail.example.test'},'mail_domain':'example.test'}
    result=Runner(service).tick(snapshot,{'webtop':{str(instance):{'api_key':'synthetic-only'}}})
    assert any(row['error_code']=='identity_ambiguous' for row in result['users'])


@pytest.mark.parametrize('folders_changed',[False,True])
def test_mail_inventory_resume_uses_stable_folder_set(personal,monkeypatch,folders_changed):
    import hashlib,json
    from types import SimpleNamespace
    from czero_app.personal_data.runner import Runner
    from czero_core.personal_data import record_checkpoint
    service,_,provider,instance,_,_=personal
    owner=provision(personal);scan=str(uuid4());calls=[]
    digest=hashlib.sha256(json.dumps(['INBOX','Sent']).encode()).hexdigest()
    record_checkpoint(service,owner_id=owner['id'],generation=1,connector='webtop',instance_id=instance,
        cursor={'page_size':5,'page':4,'folder_index':1,'scan_id':scan,'folder_hash':digest},status='backfill')
    class Mail:
        def __init__(self,*a,**kw):self.client=SimpleNamespace(close=lambda:None)
        def folders(self):return [{'id':'Sent'},{'id':'Archive' if folders_changed else 'INBOX'}]
        def page(self,folder,*,page,size):
            calls.append((folder,page))
            return [],{'complete':False,'issues':[]}
    monkeypatch.setattr('czero_app.personal_data.runner.WebTop',Mail)
    snapshot={'configuration':{'enabled':True,'webtop':str(instance)},'provider_id':str(provider),
        'provider_verified':True,'directory_complete':True,
        'directory':[{'directory_id':owner['directory_id'],'username':'person','active':True}],
        'endpoints':{'webtop':'https://mail.example.test'},'mail_domain':'example.test'}
    result=Runner(service).tick(snapshot,{'webtop':{str(instance):{'api_key':'synthetic-only'}}})
    cursor=result['users'][0]['cursor']
    assert calls[0]==(('Archive',0) if folders_changed else ('Sent',4))
    assert (cursor['scan_id']==scan) is not folders_changed
    assert (cursor['folder_hash']==digest) is not folders_changed
    assert result['users'][0]['last_inventory'] is None


def test_summary_removal_preserves_the_participants_transcript(personal):
    import json
    from types import SimpleNamespace
    from czero_app.personal_data.runner import Runner
    from czero_app.personal_data.connectors import Unavailable
    service,admin,provider,instance,_,_=personal
    service.configure(admin,provider_id=provider,enabled=True,services={'nethvoice':str(instance)},expected_generation=1)
    service.validate_binding(generation=2,provider_id=provider,services={'nethvoice':str(instance)})
    owner=provision(personal)
    args=dict(owner_id=owner['id'],generation=2,connector='nethvoice',instance_id=instance,
        remote_key='101',title='Call',content=b'Existing participated evidence',metadata={'uniqueid':'call.101'})
    transcript=service.submit(**args,kind='transcript')
    summary=service.submit(**args,kind='summary')
    def read(path,*,params):
        assert path=='/summary/call.101' and params=={'id':101,'linkedid':''}
        raise Unavailable('source_not_found')
    adapter=SimpleNamespace(client=SimpleNamespace(read=read))
    missing={'kind':'summary','remote_key':'101','slot_key':json.dumps(['call.101',''])}
    Runner(service,before_publish=lambda current:current['id']==owner['id'])._confirm_missing(adapter,'nethvoice',missing,owner,2,instance)
    with service.database.engine.connect() as c:
        assert dict(c.execute(text('SELECT kind,state FROM c0_personal_imports')).all())=={'transcript':'managed','summary':'cleanup'}
    service.cleanup()
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_source_versions WHERE source_id=:id'),{'id':UUID(transcript['source_id'])}).scalar_one()==1
        assert c.execute(text('SELECT count(*) FROM c0_source_versions WHERE source_id=:id'),{'id':UUID(summary['source_id'])}).scalar_one()==0


def test_late_provenance_updates_preserve_body_and_local_overrides(personal):
    service,_,_,_,login,registry=personal
    owner=provision(personal)
    first=submit(personal,owner,metadata={'related_import_key':'101'})
    with service.database.engine.begin() as c:
        registry.get('source.extract').execute(c,{'version_id':first['version_id']})
    linked={'related_import_key':'101','transcript_source_id':str(uuid4())}
    updated=submit(personal,owner,metadata=linked)
    assert updated['source_id']==first['source_id']
    selected=service.sources.in_space(owner['space_id']);actor=login(owner['directory_id'])
    source=selected.get(actor,first['source_id'])
    assert source['metadata']['transcript_source_id']==linked['transcript_source_id']
    assert submit(personal,owner,metadata=linked)['state']=='unchanged'
    # An authored metadata edit retains priority over subsequent remote provenance.
    selected.ingest_text(actor,idempotency_key='local-metadata',source_id=source['id'],title=source['title'],body='Original message body',metadata={'authored':'kept'},expected_revision=source['revision'])
    assert submit(personal,owner,metadata=linked)['state']=='overridden'
    assert selected.get(actor,source['id'])['metadata']=={'authored':'kept'}


def test_unsupported_attachment_does_not_block_confirmed_other_message_removal(personal,monkeypatch):
    import json
    from types import SimpleNamespace
    from czero_app.personal_data.runner import Runner
    from czero_app.personal_data.connectors import Document,Unavailable
    service,_,provider,instance,login,_=personal
    owner=provision(personal)
    missing=json.dumps(['INBOX',42,'missing'],separators=(',',':'))
    old=service.submit(owner_id=owner['id'],generation=1,connector='webtop',instance_id=instance,
        remote_key=missing,kind='message',title='Removed message',content=b'Synthetic old mail')
    current=json.dumps(['INBOX',43,'current'],separators=(',',':'))
    class Mail:
        def __init__(self,*a,**kw):self.client=SimpleNamespace(close=lambda:None,read=self.read)
        def folders(self):return [{'id':'INBOX'}]
        def page(self,*a,**kw):return [Document(current,'message','Current mail',b'Synthetic current mail')],{
            'complete':True,'issues':[{'attachment_id':'1','code':'unsupported_attachment'}]}
        def read(self,path,*,params):
            assert path=='/me/messages' and params=={'folder_id':'INBOX','uid':42,'set_seen':'false'}
            raise Unavailable('source_not_found')
    monkeypatch.setattr('czero_app.personal_data.runner.WebTop',Mail)
    snapshot={'configuration':{'enabled':True,'webtop':str(instance)},'provider_id':str(provider),
        'provider_verified':True,'directory_complete':True,
        'directory':[{'directory_id':owner['directory_id'],'username':'person','active':True}],
        'endpoints':{'webtop':'https://mail.example.test'},'mail_domain':'example.test'}
    runner=Runner(service);secrets={'webtop':{str(instance):{'api_key':'synthetic-only'}}}
    first=runner.tick(snapshot,secrets)
    assert first['users'][0]['status']=='partial'
    with service.database.engine.begin() as c:
        c.execute(text("UPDATE c0_personal_checkpoints SET last_inventory=now()-interval '301 seconds' WHERE owner_id=:id"),{'id':UUID(owner['id'])})
    second=runner.tick(snapshot,secrets)
    assert second['users'][0]['status']=='partial'
    assert service.sources.in_space(owner['space_id']).get(login(owner['directory_id']),old['source_id'])['deleted']
