# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the installed library without importing the application or collectors."""
import importlib.util
import json
import os
import time
import tempfile
from pathlib import Path
from uuid import uuid4
from czero_core.access import AccessService
from czero_core.automatic_sources import AutomaticSourceService,UpdateConflict
from czero_core.database import Database
from czero_core.identity import VerifiedIdentity
from czero_core.spaces import SpaceService

assert os.environ.get('CZERO_DISPOSABLE_TEST')=='1'
assert importlib.util.find_spec('czero_app') is None
key=uuid4();issuer='https://idp.example.test/'+uuid4().hex
database=Database()
try:
    access=AccessService(database,issuer,key)
    owner=access.resolve(VerifiedIdentity(issuer,'synthetic-owner',str(key),'owner','Owner',time.time()+300))
    space=SpaceService(database,access).create(owner,'Native sources '+uuid4().hex,idempotency_key=uuid4().hex)['id']
    service=AutomaticSourceService(database,access).in_space(space)
    draft={'name':'Public repository','kind':'github','config':{'repositories':['synthetic/example']},'enabled':True,'interval_seconds':3600,'idempotency_key':uuid4().hex}
    saved=service.save(owner,**draft)
    assert service.save(owner,**draft)==saved
    assert str(service.list(owner)[0]['id'])==saved['id']
    run=service.claim()
    assert str(run['id'])==saved['id'] and str(run['space_id'])==str(space)
    with database.engine.begin() as connection:service.fenced(connection,run)
    service.command(owner,saved['id'],action='pause',expected_revision=1,idempotency_key=uuid4().hex)
    assert service.runs(owner,saved['id'])[0]['state']=='cancelled'
    with database.engine.begin() as connection:
        try:service.fenced(connection,run)
        except UpdateConflict:pass
        else:raise AssertionError('Paused source retained a publication fence')
    service.command(owner,saved['id'],action='remove',expected_revision=2,idempotency_key=uuid4().hex)
    assert service.list(owner)==[]
    from czero_core.jobs import default_registry
    from czero_core.sources import SourceService,OriginalStore,register_source_handlers
    from czero_core.source_updates import SourceUpdater
    from czero_core.worker import Worker
    with tempfile.TemporaryDirectory() as directory:
        originals=OriginalStore(Path(directory));registry=default_registry()
        register_source_handlers(registry,database,originals,access=access)
        sources=SourceService(database,access,registry,originals).in_space(space)
        def collected(*args):
            return [{'key':'a'*64,'title':'Standalone evidence','body':b'# Standalone\n\nComplete original.',
                     'media_type':'text/markdown','metadata':{'original_url':'https://example.org/original'}}],{},True
        draft['idempotency_key']=uuid4().hex
        saved=service.save(owner,**draft)
        updater=SourceUpdater(service,sources,collector=collected);updater.tick()
        source_id=service.documents(owner,saved['id'])[0]['id']
        service.command(owner,saved['id'],action='pause',expected_revision=1,idempotency_key=uuid4().hex)
        Worker(database,registry).tick()
        assert sources.get(owner,source_id)['current_version_id'] is None
        draft['idempotency_key']=uuid4().hex
        service.save(owner,**draft,identifier=saved['id'],expected_revision=2)
        updater.tick();Worker(database,registry).tick();updater.tick()
        assert service.runs(owner,saved['id'])[0]['state']=='complete'
        assert service.documents(owner,saved['id'])[0]['id']==source_id
        assert sources.get(owner,source_id)['current_version_id'] is not None
        from czero_core.sessions import SessionService
        browser=SessionService(access,'package-drive')
        cookie=browser.create(VerifiedIdentity(issuer,'synthetic-owner',str(key),'owner','Owner',time.time()+300))
        editor=browser.get(cookie).actor
        state=service.begin_drive_oauth(editor,session_key='browser',verifier='v'*64,offline=True)
        service.take_drive_oauth(editor,session_key='browser',state=state)
        service.finish_drive_oauth(editor,session_key='browser',state=state,subject='fixture',
            credential='sealed-fixture',offline=True)
        class DriveFixture:
            def preview(self,credential,folder):
                assert credential=='sealed-fixture' and folder=='fixture-folder'
                return {'folder_name':'Native folder','items':[],'complete':False}
            def collect(self,credential,folder,cursor):
                assert credential=='sealed-fixture' and folder=='fixture-folder'
                body=Path(__file__).with_name('drive-sample.pdf').read_bytes()
                return [{'key':'fixture-file','media_type':'application/pdf','title':'Folder PDF','body':body}],{},True
            def recheck(self,credential,folder,items):
                assert credential=='sealed-fixture' and folder=='fixture-folder' and items[0]['key']=='fixture-file'
        provider=DriveFixture()
        preview=service.preview_drive(editor,folder_id='fixture-folder',provider=provider)
        target=service.save_drive(editor,preview_token=preview['preview_token'],name='Native folder',
            interval_seconds=None,enabled=True,idempotency_key=uuid4().hex)
        drive_worker=SourceUpdater(service,sources,drive_collector=provider.collect,drive_recheck=provider.recheck)
        drive_worker.tick()
        document=service.documents(editor,target['id'])[0]
        assert document['title']=='Folder PDF'
        assert 'fixture-file' not in json.dumps(sources.get(editor,document['id'])['metadata'])
        service.disconnect_drive(editor)
        assert not service.drive_status(editor)['connected']
    print(json.dumps({'installed_automatic_sources':True,'background_fence':True,'source_configuration_replay':True,
                      'installed_staged_publication_fence':True,'installed_source_resume':True,'installed_drive_source':True}))
finally:database.close()
