# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""A synthetic Google API, real sessions, queues and PostgreSQL."""
from dataclasses import replace
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from czero_core.automatic_sources import UpdateConflict
from czero_core.current_content import ContentSuperseded
from czero_core.extraction import ExtractionError, MAX_PDF_BYTES, MAX_UPLOAD
from czero_core.identity import PermissionDenied, Role
from czero_core.sessions import SessionService
from czero_core.source_http import CollectionError
from czero_core.source_updates import SourceUpdater
from czero_core.spaces import SpaceService
from czero_core.worker import Worker
from test_access import access, account_named, identity, record_unadmitted
from test_automatic_sources import automatic
from test_sources import sources

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture(autouse=True)
def drive_database(monkeypatch):
    # Audience changes and worker claims affect the whole instance. Establish
    # the test instance before the ordinary access, source and worker fixtures.
    suite_url = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    name = 'c0_drive_case_' + uuid4().hex
    admin = create_engine(suite_url,isolation_level='AUTOCOMMIT',hide_parameters=True)
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql('CREATE DATABASE ' + name)
            try:
                monkeypatch.setenv('CZERO_TEST_DATABASE_URL',suite_url.set(database=name).render_as_string(hide_password=False))
                yield
            finally:
                connection.exec_driver_sql('DROP DATABASE ' + name + ' WITH (FORCE)')
    finally:
        admin.dispose()


@pytest.fixture
def drive(automatic):
    service, sources, _, registry = automatic
    sessions = SessionService(service.access, 'drive-test')
    cookie = sessions.create(identity(service.access, service.access.owner_account_key))
    actor = sessions.get(cookie).actor
    with service.database.engine.connect() as c:
        shared = SpaceService.shared_id(c)
    return service.in_space(shared), sources, actor, registry


class Provider:
    def __init__(self):
        self.title = 'Original filename'
        self.body = b'# Evidence\n\nTeam procedure.\n'

    def preview(self, credential, folder):
        assert credential == 'sealed-test-credential' and folder == 'private-folder'
        return {'folder_name': 'Personal notes',
                'items': [{'title': self.title, 'outcome': 'include'},
                          {'title': 'Video', 'outcome': 'skip', 'reason': 'unsupported_format'}],
                'complete': False}

    def collect(self, credential, folder, cursor):
        assert credential == 'sealed-test-credential' and folder == 'private-folder'
        return [{'key':'private-file-id', 'title':self.title, 'body':self.body, 'media_type':'text/markdown',
                 'metadata':{'original_url':'private-google-url','subject':'private-subject'}}], {}, True

    def recheck(self, credential, folder, items):
        assert credential == 'sealed-test-credential' and folder == 'private-folder'
        assert all('key' in item for item in items)


def connect(service, actor, *, offline=True, subject='private-subject'):
    state = service.begin_drive_oauth(actor, session_key='browser', verifier='V'*64, offline=offline)
    service.take_drive_oauth(actor, session_key='browser', state=state)
    service.finish_drive_oauth(actor, session_key='browser', state=state, subject=subject,
                              credential='sealed-test-credential', offline=offline)


def preview(service, actor, provider, **kw):
    return service.preview_drive(actor, folder_id='private-folder', provider=provider, **kw)


def save(service, actor, proof, *, enabled=False, **kw):
    return service.save_drive(actor, preview_token=proof, name='Team notes', enabled=enabled,
                              interval_seconds=None, idempotency_key=kw.pop('key',str(uuid4())), **kw)


def test_oauth_state_replay_wrong_browser_and_disconnect_during_exchange(drive):
    service, _, actor, _ = drive
    with pytest.raises(PermissionDenied):
        service.begin_drive_oauth(replace(actor,session_binding=None), session_key='browser', verifier='V'*64)
    state = service.begin_drive_oauth(actor, session_key='browser', verifier='V'*64, offline=True)
    with pytest.raises(PermissionDenied):
        service.take_drive_oauth(actor, session_key='wrong-browser', state=state)
    taken = service.take_drive_oauth(actor, session_key='browser', state=state)
    assert taken['verifier'] == 'V'*64 and taken['offline']
    with pytest.raises(PermissionDenied):
        service.take_drive_oauth(actor, session_key='browser', state=state)
    service.disconnect_drive(actor)
    with pytest.raises(PermissionDenied):
        service.finish_drive_oauth(actor, state=state, session_key='browser', subject='sub',
                                  credential='sealed-test-credential', offline=True)
    assert not service.drive_status(actor)['connected']


def test_preview_binding_replay_and_google_authority(drive):
    service, _, actor, _ = drive
    provider = Provider()
    connect(service,actor,offline=False)
    proof = preview(service,actor,provider)
    assert not proof['complete'] and proof['items'][1]['reason'] == 'unsupported_format'
    with pytest.raises(ValueError, match='drive_offline_required'):
        save(service,actor,proof['preview_token'],enabled=True)
    key = str(uuid4())
    created = save(service,actor,proof['preview_token'],key=key)
    assert save(service,actor,proof['preview_token'],key=key) == created
    with pytest.raises(ValueError, match='drive_preview_required'):
        save(service,actor,proof['preview_token'])
    assert service.list(actor)[0]['config'] == {}
    session = SessionService(service.access,'drive-test')
    account_key = uuid4()
    record_unadmitted(service.access,account_key,'other-drive-editor')
    other = account_named(service.access,actor,'other-drive-editor')
    service.access.set_role(actor,other['id'],Role.EDITOR)
    other_cookie = session.create(identity(service.access,account_key,'other-drive-editor'))
    other_actor = session.get(other_cookie).actor
    with pytest.raises(PermissionDenied):
        service.preview_drive(other_actor,folder_id=None,provider=provider,identifier=created['id'],expected_revision=1)
    with pytest.raises(PermissionDenied):
        service.command_drive(other_actor,created['id'],action='run',expected_revision=1,idempotency_key=str(uuid4()))
    with pytest.raises(PermissionDenied):
        service.command(actor,created['id'],action='run',expected_revision=1,idempotency_key=str(uuid4()))
    with pytest.raises(PermissionDenied):
        service.save(other_actor,name='Hijack',kind='github',config={'repositories':['fixture/demo']},
                     enabled=True,interval_seconds=None,identifier=created['id'],expected_revision=1,idempotency_key=str(uuid4()))
    changed = service.preview_drive(actor,folder_id=None,provider=provider,identifier=created['id'],expected_revision=1)
    service.command(other_actor,created['id'],action='pause',expected_revision=1,idempotency_key=str(uuid4()))
    with pytest.raises((ValueError,UpdateConflict)):
        save(service,actor,changed['preview_token'],identifier=created['id'],expected_revision=1)
    connect(service,actor)
    assert not service.list(actor)[0]['enabled']


def test_native_collection_rename_and_connection_fence(drive):
    service,sources,actor,registry = drive
    connect(service,actor)
    provider = Provider()
    created = save(service,actor,preview(service,actor,provider)['preview_token'],enabled=True)
    worker = SourceUpdater(service,sources,drive_collector=provider.collect,drive_recheck=provider.recheck)
    def run():
        service.command_drive(actor,created['id'],action='run',expected_revision=1,idempotency_key=str(uuid4()))
    worker.tick()
    docs = service.documents(actor,created['id'])
    assert len(docs)==1
    first = sources.get(actor,docs[0]['id'])
    assert first['current_version_id'] and first['title']==provider.title
    metadata = json.dumps(first['metadata'])
    assert 'private-' not in metadata and 'sealed' not in metadata
    provider.title = 'Renamed note'
    run()
    worker.tick()
    worker.tick()
    changed = sources.get(actor,first['id'])
    assert changed['current_version_id'] == first['current_version_id']
    assert changed['title'] == provider.title and changed['revision'] == first['revision']+1
    provider.body = b'An unpublished replacement'
    def disconnect(*args):
        assert service.disconnect_drive(actor) == 'sealed-test-credential'
    worker.drive_recheck = disconnect
    run()
    worker.tick()
    Worker(sources.database,registry).tick()
    assert sources.get(actor,first['id'])['current_version_id'] == first['current_version_id']
    assert not service.list(actor)[0]['enabled']
    assert not service.drive_status(actor)['connected']


def test_drive_proof_cannot_cross_spaces_or_survive_audience_change(drive):
    service, _, actor, _ = drive
    spaces = SpaceService(service.database, service.access)
    chosen = spaces.create(actor,'Drive audience '+uuid4().hex,idempotency_key=uuid4().hex)
    other = service.in_space(chosen['id'])
    connect(service,actor)
    connect(other,actor)
    proof = preview(service,actor,Provider())['preview_token']
    with pytest.raises(ValueError,match='drive_preview_required'):
        save(other,actor,proof)
    proof = preview(other,actor,Provider())['preview_token']
    account_key = uuid4()
    record_unadmitted(service.access,account_key,'new-space-reader')
    reader = account_named(service.access,actor,'new-space-reader')
    service.access.set_role(actor,reader['id'],Role.READER)
    spaces.set_grant(actor,chosen['id'],reader['id'],Role.READER,expected_revision=0,idempotency_key=uuid4().hex)
    with pytest.raises(ValueError,match='drive_preview_required'):
        save(other,actor,proof)
    proof = preview(other,actor,Provider())['preview_token']
    spaces.set_access(actor,chosen['id'],readable_by_all=True,
                      expected_revision=chosen['revision'],idempotency_key=uuid4().hex)
    with pytest.raises(ValueError,match='drive_preview_required'):
        save(other,actor,proof)
    proof = preview(other,actor,Provider())['preview_token']
    with service.database.engine.begin() as c:
        c.execute(text("""UPDATE c0_drive_previews SET expires_at=now()-interval '1 minute'
            WHERE account_id=:owner AND space_id=:space"""),{'owner':actor.user_id,'space':chosen['id']})
    with pytest.raises(ValueError,match='drive_preview_required'):
        save(other,actor,proof)


def test_google_revocation_and_disconnect_during_remote_preview(drive):
    service, sources, actor, _ = drive
    connect(service,actor)
    class Disconnect:
        def preview(self, *args):
            service.disconnect_drive(actor)
            return {'folder_name':'private', 'items':[], 'complete':True}
    with pytest.raises(CollectionError,match='drive_reconnect_required'):
        preview(service,actor,Disconnect())
    connect(service,actor)
    provider = Provider()
    save(service,actor,preview(service,actor,provider)['preview_token'],enabled=True)
    def invalid(*args):
        raise CollectionError('drive_reconnect_required')
    SourceUpdater(service,sources,drive_collector=invalid,drive_recheck=provider.recheck).tick()
    assert service.drive_status(actor) == {'connected':False,'offline':False,'reconnect_required':True}
    assert not service.list(actor)[0]['enabled']
    assert service.runs(actor,service.list(actor)[0]['id'])[0]['error_code']=='drive_reconnect_required'
    with pytest.raises(PermissionDenied):
        connect(service,actor,subject='another-subject')


def test_pdf_collection_rechecks_after_parsing_and_skips_invalid_siblings(drive):
    service,sources,actor,registry = drive
    connect(service,actor)
    provider = Provider()
    created = save(service,actor,preview(service,actor,provider)['preview_token'],enabled=True)
    path = Path(__file__).parents[1]/'fixtures/evidence/sample.pdf'
    files = [
        {'key':'valid-pdf','media_type':'application/pdf','title':'Meeting PDF','body':path.read_bytes()},
        {'key':'invalid-pdf','media_type':'application/pdf','title':'Broken PDF','body':b'not a PDF'},
    ]
    def collect(*args):
        return files,{},True
    def moved(*args):
        assert [item['key'] for item in args[2]] == ['valid-pdf']
        raise CollectionError('drive_item_unavailable')
    worker = SourceUpdater(service,sources,drive_collector=collect,drive_recheck=moved)
    worker.tick()
    assert not service.documents(actor,created['id'])
    assert service.runs(actor,created['id'])[0]['state'] == 'blocked'
    service.command_drive(actor,created['id'],action='run',expected_revision=1,idempotency_key=str(uuid4()))
    worker.drive_recheck = provider.recheck
    worker.tick()
    docs = service.documents(actor,created['id'])
    assert [doc['title'] for doc in docs] == ['Meeting PDF']
    current = sources.get(actor,docs[0]['id'])
    assert current['current_version_id']
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT job_id FROM c0_source_versions WHERE id=:id'),
                         {'id':current['current_version_id']}).scalar_one() is None
    assert service.runs(actor,created['id'])[0]['state'] == 'complete'


def test_pdf_parser_timeout_advances_to_later_pages_and_retries_on_next_scan(drive,monkeypatch):
    service,sources,actor,_ = drive
    import czero_core.source_updates as updates
    provider = Provider()
    connect(service,actor)
    created = save(service,actor,preview(service,actor,provider)['preview_token'],enabled=True)
    original = updates.prepare_drive_document
    def temporary_failure(body, media_type):
        if media_type=='application/pdf':
            raise ExtractionError('parser_timeout')
        return original(body,media_type)
    pdf = (Path(__file__).parents[1]/'fixtures/evidence/sample.pdf').read_bytes()
    page_calls = []
    def collect(credential,folder,cursor):
        page_calls.append(cursor.get('page'))
        items,_,_ = provider.collect(credential,folder,cursor)
        if cursor.get('page')==2:
            return [{**items[0],'key':'later-file','title':'Next page'}],{},True
        return items+[{'key':'delayed-pdf','media_type':'application/pdf','title':'Delayed','body':pdf}],{'page':2},False
    monkeypatch.setattr(updates,'prepare_drive_document',temporary_failure)
    worker = SourceUpdater(service,sources,drive_collector=collect,drive_recheck=provider.recheck)
    worker.tick()
    assert service.runs(actor,created['id'])[0]['state']=='pending'
    first = service.documents(actor,created['id'])
    assert len(first)==1 and first[0]['title']==provider.title
    first_version = sources.get(actor,first[0]['id'])['current_version_id']
    worker.tick()
    run = service.runs(actor,created['id'])[0]
    assert (run['state'],run['error_code']) == ('partial','drive_parser_incomplete')
    assert service.list(actor)[0]['last_success_at'] is None
    assert len(service.documents(actor,created['id']))==2
    monkeypatch.setattr(updates,'prepare_drive_document',original)
    service.command_drive(actor,created['id'],action='run',expected_revision=1,idempotency_key=str(uuid4()))
    worker.tick()
    worker.tick()
    assert service.runs(actor,created['id'])[0]['state']=='complete'
    assert len(service.documents(actor,created['id']))==3
    assert page_calls == [None,2,None,2]
    assert sources.get(actor,first[0]['id'])['current_version_id']==first_version


@pytest.mark.parametrize('grant_timing',['before_claim','during_fetch','manual_run'])
def test_new_reader_pauses_drive_and_requires_new_preview(drive,grant_timing):
    service,sources,actor,_ = drive
    spaces = SpaceService(service.database,service.access)
    space = spaces.create(actor,'Folder access '+uuid4().hex,idempotency_key=uuid4().hex)
    service = service.in_space(space['id'])
    record_unadmitted(service.access,uuid4(),'another-reader')
    reader = account_named(service.access,actor,'another-reader')
    service.access.set_role(actor,reader['id'],Role.READER)
    def grant():
        spaces.set_grant(actor,space['id'],reader['id'],Role.READER,expected_revision=0,idempotency_key=uuid4().hex)
    connect(service,actor)
    provider = Provider()
    created = save(service,actor,preview(service,actor,provider)['preview_token'],enabled=True)
    called = []
    def collect(*args):
        called.append(True)
        grant()
        return provider.collect(*args)
    if grant_timing != 'during_fetch':
        grant()
    worker = SourceUpdater(service,sources,drive_collector=collect,drive_recheck=provider.recheck)
    if grant_timing == 'manual_run':
        service.command_drive(actor,created['id'],action='run',expected_revision=1,idempotency_key=uuid4().hex)
    worker.tick()
    assert bool(called) == (grant_timing == 'during_fetch')
    assert not service.documents(actor,created['id'])
    row, = service.list(actor)
    assert not row['enabled'] and row['revision'] == 2
    run, = service.runs(actor,created['id'])
    assert (run['state'],run['error_code']) == ('blocked','drive_audience_changed')
    target = {'identifier':created['id'],'expected_revision':row['revision']}
    proof = service.preview_drive(actor,folder_id=None,provider=provider,**target)
    save(service,actor,proof['preview_token'],enabled=True,**target)
    worker.drive_collector = provider.collect
    worker.tick()
    assert len(service.documents(actor,created['id'])) == 1


def test_drive_reindexes_unchanged_bytes_with_new_media_and_skips_large_text(drive):
    service,sources,actor,_ = drive
    connect(service,actor)
    provider = Provider()
    created = save(service,actor,preview(service,actor,provider)['preview_token'],enabled=True)
    item = {'key':'stable','body':b'# Procedure\n\nFirst step','media_type':'text/plain','title':'Procedure.txt'}
    oversized = {'key':'big','body':b'x'*1_000_001,'media_type':'text/plain','title':'Large file'}
    collector = lambda *args: ([oversized,item],{},True)
    worker = SourceUpdater(service,sources,drive_collector=collector,drive_recheck=provider.recheck)
    worker.tick()
    doc, = service.documents(actor,created['id'])
    first = sources.get(actor,doc['id'])
    item.update(media_type='text/markdown',title='Procedure.md')
    service.command_drive(actor,created['id'],action='run',expected_revision=1,idempotency_key=uuid4().hex)
    worker.tick()
    latest = sources.get(actor,doc['id'])
    assert latest['title']=='Procedure.md' and latest['current_version_id']!=first['current_version_id']
    with sources.database.engine.connect() as conn:
        assert conn.execute(text('SELECT media_type,force_reindex FROM c0_source_versions WHERE id=:id'),
                            {'id':latest['current_version_id']}).one()==('text/markdown',True)
    with pytest.raises(ContentSuperseded):
        sources.document(actor,first['current_version_id'])
    assert len(service.documents(actor,created['id']))==1
    assert service.runs(actor,created['id'])[0]['state']=='complete'


def test_mixed_pdf_retains_omitted_pages_and_supersedes_the_original(drive):
    service,sources,actor,registry = drive
    connect(service,actor)
    provider = Provider()
    created = save(service,actor,preview(service,actor,provider)['preview_token'],enabled=True)
    fixtures = Path(__file__).parents[1]/'fixtures/evidence'
    mixed = (fixtures/'pipeline/mixed-scan.pdf').read_bytes()
    item = {'key':'private-file-id','title':'Scanned appendix','media_type':'application/pdf','body':mixed}
    worker = SourceUpdater(service,sources,drive_collector=lambda *args: ([item],{},True),
                           drive_recheck=provider.recheck)
    worker.tick()
    doc, = service.documents(actor,created['id'])
    first = sources.get(actor,doc['id'])
    assert first['metadata']['pdf_textless_page_count'] == 1
    assert first['metadata']['pdf_textless_pages'] == [2]
    path,version = sources.original(actor,first['current_version_id'])
    assert version['retain_original'] and path.read_bytes() == mixed
    item['body'] = (fixtures/'sample.pdf').read_bytes()
    service.command_drive(actor,created['id'],action='run',expected_revision=1,idempotency_key=str(uuid4()))
    worker.tick()
    latest = sources.get(actor,doc['id'])
    assert latest['current_version_id'] != first['current_version_id']
    assert 'pdf_textless_pages' not in latest['metadata']
    with pytest.raises(ContentSuperseded):
        sources.original(actor,first['current_version_id'])
    with service.database.engine.begin() as connection:
        registry.get('source.cleanup').execute(connection,{'version_id':str(UUID(int=0))})
    assert not path.exists()


def test_source_version_database_enforces_distinct_pdf_upload_bound(drive):
    service,sources,actor,_ = drive
    connect(service,actor)
    provider = Provider()
    created = save(service,actor,preview(service,actor,provider)['preview_token'],enabled=True)
    SourceUpdater(service,sources,drive_collector=provider.collect,drive_recheck=provider.recheck).tick()
    doc, = service.documents(actor,created['id'])
    version = sources.get(actor,doc['id'])['current_version_id']
    with service.database.engine.connect() as connection:
        def update(media, size):
            connection.execute(text('''UPDATE c0_source_versions SET media_type=:media,
                size_bytes=:size WHERE id=:version'''),{'version':version,'media':media,'size':size})
        update('application/pdf',MAX_PDF_BYTES)
        with pytest.raises(IntegrityError),connection.begin_nested():
            update('application/pdf',MAX_PDF_BYTES+1)
        with pytest.raises(IntegrityError),connection.begin_nested():
            update('text/plain',MAX_UPLOAD+1)


def test_operational_parser_failure_alone_cannot_report_coverage(drive, monkeypatch):
    import czero_core.source_updates as updates
    service, sources, actor, _ = drive
    provider = Provider()
    connect(service, actor)
    saved = save(service, actor, preview(service, actor, provider)['preview_token'], enabled=True)
    def unavailable(*_):
        raise ExtractionError('parser_failed')
    monkeypatch.setattr(updates, 'prepare_drive_document', unavailable)
    SourceUpdater(service, sources, drive_collector=provider.collect, drive_recheck=lambda *_: None).tick()
    row = service.runs(actor, saved['id'])[0]
    assert (row['state'], row['processed'], row['error_code']) == ('partial', 0, 'drive_parser_incomplete')
    assert service.list(actor)[0]['last_success_at'] is None


@pytest.mark.parametrize('change',['unblock_grantee','promote_admin','configured_owner'])
def test_restricted_drive_rechecks_effective_readers_during_fetch(drive,change):
    service,sources,admin,_ = drive
    access = service.access
    spaces = SpaceService(service.database,access)
    space = spaces.create(admin,'Restricted '+uuid4().hex,idempotency_key=uuid4().hex)
    service = service.in_space(space['id'])

    editor_key = uuid4()
    record_unadmitted(access,editor_key,'folder-editor')
    editor_id = account_named(access,admin,'folder-editor')['id']
    access.set_role(admin,editor_id,Role.EDITOR)
    spaces.set_grant(admin,space['id'],editor_id,Role.EDITOR,expected_revision=0,idempotency_key=uuid4().hex)
    sessions = SessionService(access,'drive-test')
    editor = sessions.get(sessions.create(identity(access,editor_key,'folder-editor'))).actor

    key = uuid4()
    record_unadmitted(access,key,'new-reader')
    account = account_named(access,admin,'new-reader')['id']
    access.set_role(admin,account,Role.READER)
    candidate = access.resolve(identity(access,key,'new-reader'))
    if change == 'unblock_grantee':
        spaces.set_grant(admin,space['id'],account,Role.READER,expected_revision=0,idempotency_key=uuid4().hex)
    if change != 'promote_admin':
        access.set_role(admin,account,None)
    with pytest.raises(PermissionDenied):
        spaces.get(candidate,space['id'])

    connect(service,editor)
    provider = Provider()
    saved = save(service,editor,preview(service,editor,provider)['preview_token'],enabled=True)
    def collect(*args):
        if change == 'configured_owner':
            access.owner_account_key = key
            with service.database.engine.connect() as c:
                assert c.execute(text('SELECT 1 FROM c0_account_blocks WHERE account_id=:id'),
                                 {'id':account}).scalar_one() == 1
        else:
            access.set_role(admin,account,Role.ADMIN if change == 'promote_admin' else Role.READER)
        assert spaces.get(candidate,space['id'])['role'] in ('admin','reader')
        return provider.collect(*args)
    SourceUpdater(service,sources,drive_collector=collect,drive_recheck=provider.recheck).tick()
    run, = service.runs(editor,saved['id'])
    assert (run['state'],run['error_code']) == ('blocked','drive_audience_changed')
    assert not service.list(editor)[0]['enabled']
    assert not service.documents(editor,saved['id'])


@pytest.mark.parametrize('destination',['shared','readable_by_all'])
def test_open_drive_audience_includes_later_eligible_accounts(drive,destination):
    service,sources,admin,_ = drive
    spaces = SpaceService(service.database,service.access)
    if destination == 'readable_by_all':
        space = spaces.create(admin,'Open '+uuid4().hex,idempotency_key=uuid4().hex)
        spaces.set_access(admin,space['id'],readable_by_all=True,expected_revision=space['revision'],idempotency_key=uuid4().hex)
        service = service.in_space(space['id'])
    connect(service,admin)
    provider = Provider()
    saved = save(service,admin,preview(service,admin,provider)['preview_token'],enabled=True)
    def collect(*args):
        key = uuid4()
        record_unadmitted(service.access,key,'later-signin')
        account = account_named(service.access,admin,'later-signin')
        service.access.set_role(admin,account['id'],Role.READER)
        return provider.collect(*args)
    SourceUpdater(service,sources,drive_collector=collect,drive_recheck=provider.recheck).tick()
    assert len(service.documents(admin,saved['id'])) == 1
    assert service.runs(admin,saved['id'])[0]['state'] == 'complete'
