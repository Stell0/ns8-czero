# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import os
from uuid import UUID, uuid4
import pytest
from sqlalchemy import text
from czero_core.automatic_sources import AutomaticSourceService, UpdateConflict
from czero_core.identity import Actor, Role, PermissionDenied
from czero_core.source_updates import SourceUpdater
from czero_core.worker import Worker
from test_access import access, owner_actor, record_unadmitted, account_named, identity
from test_sources import sources
from test_personal_core_compatibility import personal, provision

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


@pytest.fixture
def automatic(sources):
    source_service,owner,registry,created=sources
    service=AutomaticSourceService(source_service.database,source_service.access)
    yield service,source_service,owner,registry
    if hasattr(source_service,'_test_retained'): created.append(source_service._test_retained)
    with source_service.database.engine.begin() as c:
        ids=c.execute(text('SELECT id FROM c0_automatic_sources WHERE owner_id IN (SELECT id FROM c0_accounts WHERE issuer=:issuer)'),{'issuer':source_service.access.issuer}).scalars().all()
        for source_id in c.execute(text('SELECT source_id FROM c0_automatic_source_items WHERE definition_id=ANY(CAST(:ids AS uuid[]))'),{'ids':ids}).scalars():
            if source_id not in created:created.append(source_id)
        c.execute(text('DELETE FROM c0_automatic_sources WHERE id=ANY(CAST(:ids AS uuid[]))'),{'ids':ids})


def definition(automatic,**kwargs):
    service,_,owner,_=automatic
    args=dict(name='Public docs',kind='github',config={'repositories':['synthetic/example']},enabled=True,interval_seconds=3600,idempotency_key=str(uuid4()))
    args.update(kwargs)
    return service.save(owner,**args)


def collector(body=b'# Verified\n\nComplete original evidence.'):
    def collect(*args,**kwargs):
        return [{'key':'f'*64,'title':'Evidence','body':body,'media_type':'text/markdown','metadata':{'original_url':'https://example.org/docs'}}],{},True
    return collect


def test_definition_replay_revision_pause_and_retention(automatic):
    service,sources,owner,registry=automatic
    key=str(uuid4());saved=definition(automatic,idempotency_key=key)
    assert definition(automatic,idempotency_key=key)==saved
    with pytest.raises(UpdateConflict):definition(automatic,name='changed',idempotency_key=key)
    row=service.list(owner)[0]
    assert row['revision']==1
    updater=SourceUpdater(service,sources,collector=collector())
    updater.tick();assert service.runs(owner,saved['id'])[0]['state']=='pending'
    Worker(sources.database,registry).tick()
    updater.tick();assert service.runs(owner,saved['id'])[0]['state']=='complete'
    assert service.list(owner)[0]['last_success_at'] is not None
    stored=sources.list(owner,external_key='f'*64)[0]
    assert stored['metadata']['automatic_source_id']==saved['id']
    automatic[1]._test_retained = stored['id']
    service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='remove')
    assert sources.get(owner,stored['id'])['title']=='Evidence'


def test_pause_during_fetch_prevents_publication(automatic):
    service,sources,owner,_=automatic;saved=definition(automatic)
    def paused(*args):
        service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='pause')
        return collector()()
    SourceUpdater(service,sources,collector=paused).tick()
    assert service.runs(owner,saved['id'])[0]['state']=='cancelled'
    assert not any(row['metadata'].get('automatic_source_id')==saved['id'] for row in sources.list(owner,external_key='f'*64))


def test_unchanged_update_reuses_source_and_version(automatic):
    service,sources,owner,registry=automatic;saved=definition(automatic)
    updater=SourceUpdater(service,sources,collector=collector());updater.tick()
    Worker(sources.database,registry).tick();updater.tick()
    before=sources.list(owner,external_key='f'*64)[0]
    service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    updater.tick();updater.tick()
    after=sources.list(owner,external_key='f'*64)[0]
    assert before==after


def test_manual_and_scheduled_claims_do_not_overlap(automatic):
    service,_,owner,_=automatic;saved=definition(automatic)
    first=service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    second=service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    assert first==second
    claimed=service.claim();assert claimed
    assert service.claim() is None
    with service.database.engine.begin() as c:
        c.execute(text("UPDATE c0_source_update_runs SET lease_until=now()-interval '1 second' WHERE id=:id"),{'id':claimed['run_id']})
    resumed=service.claim();assert resumed['run_id']==claimed['run_id'] and resumed['lease']!=claimed['lease']
    with service.database.engine.begin() as c:
        with pytest.raises(UpdateConflict):service.fenced(c,claimed)


def test_reader_and_other_space_denied(automatic):
    from czero_core.spaces import SpaceService
    service,source_service,owner,_=automatic
    acl=source_service.access;key=uuid4();record_unadmitted(acl,key,'reader')
    account=account_named(acl,owner,'reader');acl.set_role(owner,account['id'],Role.READER)
    reader=acl.resolve(identity(acl,key,'reader'))
    assert service.list(reader)==[]
    with pytest.raises(PermissionDenied):service.save(reader,name='denied',kind='github',config={'repositories':['a/b']},enabled=True,interval_seconds=300,idempotency_key=str(uuid4()))
    space=SpaceService(service.database,acl).create(owner,'Isolated',idempotency_key=str(uuid4()))
    try:
        with pytest.raises(PermissionDenied):service.in_space(space['id']).list(reader)
    finally:
        with service.database.engine.begin() as c:c.execute(text('DELETE FROM c0_spaces WHERE id=:id'),{'id':space['id']})


def test_space_grant_revision_change_blocks_captured_authority(automatic):
    from czero_core.spaces import SpaceService
    service,sources,owner,_=automatic
    spaces=SpaceService(service.database,service.access)
    space=spaces.create(owner,'Source authority '+uuid4().hex[:8],idempotency_key=str(uuid4()))
    selected=service.in_space(space['id'])
    saved=selected.save(owner,name='Scoped',kind='github',config={'repositories':['a/b']},enabled=True,interval_seconds=3600,idempotency_key=str(uuid4()))
    try:
        claim=service.claim()
        spaces.set_grant(owner,space['id'],owner.user_id,Role.EDITOR,expected_revision=0,idempotency_key=str(uuid4()))
        with service.database.engine.begin() as c:
            with pytest.raises(PermissionDenied):selected.fenced(c,claim)
    finally:
        with service.database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_automatic_sources WHERE id=:id'),{'id':saved['id']})
            c.execute(text('DELETE FROM c0_knowledge_receipts WHERE space_id=:id'),{'id':space['id']})
            c.execute(text('DELETE FROM c0_spaces WHERE id=:id'),{'id':space['id']})


def test_manual_replacement_blocks_automatic_completion(automatic):
    from io import BytesIO
    service,sources,owner,registry=automatic;saved=definition(automatic)
    updater=SourceUpdater(service,sources,collector=collector());updater.tick()
    Worker(sources.database,registry).tick()
    stored=next(v for v in sources.list(owner,external_key='f'*64) if v['metadata'].get('automatic_source_id')==saved['id'])
    sources.ingest(owner,BytesIO(b'Manually replaced content'),title='Manual',filename='manual.txt',media_type='text/plain',source_id=stored['id'],expected_revision=stored['revision'])
    Worker(sources.database,registry).tick();updater.tick()
    assert service.runs(owner,saved['id'])[0]['state']=='blocked'
    assert sources.get(owner,stored['id'])['title']=='Manual'


def test_partial_run_retains_durable_cursor_and_backs_off(automatic):
    from czero_core.source_http import CollectionError
    service,sources,owner,registry=automatic;saved=definition(automatic)
    def first(*args):
        items,_,_=collector()();return items,{'page':2},False
    SourceUpdater(service,sources,collector=first).tick();Worker(sources.database,registry).tick()
    def unavailable(*args):raise CollectionError('source_http_429')
    SourceUpdater(service,sources,collector=unavailable).tick()
    assert service.runs(owner,saved['id'])[0]['state']=='partial'
    with service.database.engine.begin() as c:
        delay=c.execute(text('SELECT extract(epoch FROM next_run_at-now()) FROM c0_automatic_sources WHERE id=:id'),{'id':saved['id']}).scalar_one()
        assert 0<delay<=30
    service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    assert service.claim()['cursor']['page']==2


def test_changed_document_replaces_current_generation_atomically(automatic):
    service,sources,owner,registry=automatic;saved=definition(automatic)
    SourceUpdater(service,sources,collector=collector()).tick()
    Worker(sources.database,registry).tick()
    SourceUpdater(service,sources,collector=collector()).tick()
    old=next(v for v in sources.list(owner,external_key='f'*64) if v['metadata'].get('automatic_source_id')==saved['id'])
    service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    SourceUpdater(service,sources,collector=collector(b'# Changed\n\nNew complete evidence.')).tick()
    assert sources.get(owner,old['id'])['current_version_id']==old['current_version_id']
    Worker(sources.database,registry).tick()
    SourceUpdater(service,sources,collector=collector()).tick()
    fresh=sources.get(owner,old['id'])
    assert fresh['current_version_id']!=old['current_version_id']
    with pytest.raises(ValueError,match='content_superseded'):sources.document(owner,old['current_version_id'])


def test_remote_retry_after_is_honored_without_installing_another_schedule(automatic):
    from datetime import datetime,timedelta,timezone
    from czero_core.source_http import FetchError
    service,sources,owner,_=automatic;saved=definition(automatic)
    retry_at=datetime.now(timezone.utc)+timedelta(hours=1)
    def limited(*args):raise FetchError('source_http_429',retry_at.isoformat())
    SourceUpdater(service,sources,collector=limited).tick()
    row=service.list(owner)[0]
    assert row['next_run_at']>=retry_at
    assert service.runs(owner,saved['id'])[0]['error_code']=='source_http_429'


def test_permanent_collection_denial_blocks_automatic_retries(automatic):
    from czero_core.source_http import CollectionError
    service,sources,owner,_=automatic;saved=definition(automatic)
    def denied(*args):raise CollectionError('source_private_destination_denied')
    updater=SourceUpdater(service,sources,collector=denied)
    updater.tick()
    assert service.runs(owner,saved['id'])[0]['state']=='blocked'
    assert service.list(owner)[0]['next_run_at'] is None
    assert updater.tick()==0


def test_transient_retries_are_bounded_per_scheduled_occurrence(automatic):
    from czero_core.source_http import FetchError
    service,sources,owner,_=automatic;saved=definition(automatic)
    def unavailable(*args):raise FetchError('source_http_503')
    updater=SourceUpdater(service,sources,collector=unavailable)
    for attempt in range(5):
        if attempt:
            with service.database.engine.begin() as c:
                c.execute(text('UPDATE c0_automatic_sources SET next_run_at=now() WHERE id=:id'),{'id':saved['id']})
        updater.tick()
    with service.database.engine.connect() as c:
        delay=c.execute(text('SELECT extract(epoch FROM next_run_at-now()) FROM c0_automatic_sources WHERE id=:id'),{'id':saved['id']}).scalar_one()
        assert 3500<delay<=3600
    assert len(service.runs(owner,saved['id']))==5


def test_concurrent_workers_claim_one_source_run(automatic):
    from concurrent.futures import ThreadPoolExecutor
    service,_,owner,_=automatic;definition(automatic)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims=list(pool.map(lambda _:service.claim(),range(2)))
    assert sum(row is not None for row in claims)==1


def test_regranting_editor_does_not_revive_old_background_authority(automatic):
    service,sources,owner,_=automatic;acl=sources.access;key=uuid4()
    record_unadmitted(acl,key,'source-editor')
    account=account_named(acl,owner,'source-editor')
    acl.set_role(owner,account['id'],Role.EDITOR)
    editor=acl.resolve(identity(acl,key,'source-editor'))
    saved=service.save(editor,name='Owned public source',kind='github',config={'repositories':['synthetic/example']},enabled=True,interval_seconds=3600,idempotency_key=str(uuid4()))
    claimed=service.claim()
    acl.set_role(owner,account['id'],Role.READER)
    acl.set_role(owner,account['id'],Role.EDITOR)
    with service.database.engine.begin() as c:
        with pytest.raises(PermissionDenied):service.fenced(c,claimed)
    assert str(claimed['id'])==saved['id']


def test_expired_collection_cannot_publish_or_block_the_recovering_run(automatic):
    service,sources,owner,_=automatic;saved=definition(automatic);leases=[]
    def expired(*args):
        with service.database.engine.begin() as c:
            leases.append(c.execute(text("UPDATE c0_source_update_runs SET lease_until=clock_timestamp()-interval '1 second' WHERE definition_id=:id AND state='running' RETURNING lease"),{'id':saved['id']}).scalar_one())
        return collector()()
    SourceUpdater(service,sources,collector=expired).tick()
    resumed=service.claim()
    assert resumed and resumed['lease']!=leases[0]
    assert service.documents(owner,saved['id'])==[]


def test_run_order_and_resume_do_not_depend_on_wall_clock(automatic):
    service,sources,owner,_=automatic;saved=definition(automatic)
    def partial(*args):return [],{'page':2},False
    SourceUpdater(service,sources,collector=partial).tick()
    with service.database.engine.begin() as c:
        first=c.execute(text("UPDATE c0_source_update_runs SET state='partial',created_at=now()+interval '1 day' WHERE definition_id=:id RETURNING id"),{'id':saved['id']}).scalar_one()
    service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    def complete(*args):return [],{},True
    updater=SourceUpdater(service,sources,collector=complete);updater.tick();updater.tick()
    assert service.runs(owner,saved['id'])[0]['state']=='complete'
    service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    assert service.claim()['cursor']=={}
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT cursor FROM c0_source_update_runs WHERE id=:id'),{'id':first}).scalar_one()=={}


def test_checkpoints_are_moved_and_old_run_metadata_is_bounded(automatic):
    service,sources,owner,_=automatic;saved=definition(automatic)
    def partial(*args):return [],{'page':2},False
    SourceUpdater(service,sources,collector=partial).tick()
    with service.database.engine.begin() as c:
        first=c.execute(text("UPDATE c0_source_update_runs SET state='partial',created_at=now()-interval '40 days' WHERE definition_id=:id RETURNING id"),{'id':saved['id']}).scalar_one()
    service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    with service.database.engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM c0_source_update_runs WHERE definition_id=:id AND cursor<>'{}'"),{'id':saved['id']}).scalar_one()==1
    service._prune_runs()
    assert len(service.runs(owner,saved['id']))==1
    with service.database.engine.begin() as c:
        c.execute(text("UPDATE c0_source_update_runs SET state='complete',cursor='{}',created_at=now()-interval '40 days' WHERE definition_id=:id"),{'id':saved['id']})
    service._prune_runs()
    assert len(service.runs(owner,saved['id']))==1


def test_personal_editor_background_authority_stays_in_its_owned_space(personal):
    native,admin,provider,_,login,_=personal
    owner=provision(personal)
    actor=login(owner['directory_id'])
    service=AutomaticSourceService(native.database,native.access)
    selected=service.in_space(owner['space_id'])
    args=dict(name='Public original',kind='github',config={'repositories':['synthetic/example']},
              enabled=True,interval_seconds=3600,idempotency_key=str(uuid4()))
    with pytest.raises(PermissionDenied):service.save(actor,**args)
    saved=selected.save(actor,**args)
    claimed=service.claim()
    with service.database.engine.begin() as c:
        assert selected.fenced(c,claimed).role is Role.EDITOR
    native.reconcile_directory(provider_id=provider,entries=[],complete=True)
    with service.database.engine.begin() as c:
        with pytest.raises(PermissionDenied):selected.fenced(c,claimed)
    assert selected.runs(admin,saved['id'])[0]['state']=='running'


@pytest.mark.parametrize('existing',[False,True])
@pytest.mark.parametrize('stop',['pause','revoke','remove'])
def test_staged_publication_is_fenced_and_explicit_resume_keeps_source_id(automatic,existing,stop):
    service,sources,owner,registry=automatic
    acl=sources.access;key=uuid4();record_unadmitted(acl,key,'publication-editor')
    account=account_named(acl,owner,'publication-editor');acl.set_role(owner,account['id'],Role.EDITOR)
    editor=acl.resolve(identity(acl,key,'publication-editor'))
    args=dict(name='Fenced public original',kind='github',config={'repositories':['synthetic/example']},
              enabled=True,interval_seconds=3600)
    saved=service.save(editor,**args,idempotency_key=str(uuid4()))
    if existing:
        updater=SourceUpdater(service,sources,collector=collector());updater.tick()
        Worker(service.database,registry).tick();updater.tick()
        service.command(editor,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    SourceUpdater(service,sources,collector=collector(b'# Replacement\n\nComplete replacement.')).tick()
    with service.database.engine.connect() as c:
        staged=dict(c.execute(text('SELECT * FROM c0_automatic_source_items WHERE definition_id=:id'),{'id':saved['id']}).mappings().one())
        previous=c.execute(text('SELECT current_version_id FROM c0_sources WHERE id=:id'),{'id':staged['source_id']}).scalar_one()
    if stop in ('pause','remove'):service.command(editor,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action=stop)
    else:acl.set_role(owner,account['id'],Role.READER)
    for _ in range(2):Worker(service.database,registry).tick()
    assert sources.get(owner,staged['source_id'])['current_version_id']==previous
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT 1 FROM c0_source_versions WHERE id=:id'),{'id':staged['version_id']}).scalar_one_or_none() is None
    assert not sources.originals.path(staged['version_id']).exists()
    if stop=='remove':
        sources._test_retained=staged['source_id']
        return
    acl.set_role(owner,account['id'],Role.EDITOR)
    editor=acl.resolve(identity(acl,key,'publication-editor'))
    service.save(editor,**args,identifier=saved['id'],expected_revision=2 if stop=='pause' else 1,idempotency_key=str(uuid4()))
    updater=SourceUpdater(service,sources,collector=collector(b'# Resumed\n\nFresh authorized content.'))
    updater.tick();Worker(service.database,registry).tick();updater.tick()
    assert service.runs(owner,saved['id'])[0]['state']=='complete'
    result=service.documents(owner,saved['id'])
    assert len(result)==1 and result[0]['id']==staged['source_id']
    assert '_automatic_source_revision' not in sources.get(owner,staged['source_id'])['metadata']


def test_forged_stage_metadata_cannot_cancel_another_definition(automatic):
    from czero_core.automatic_sources import guard_publication
    service,sources,owner,registry=automatic;saved=definition(automatic)
    SourceUpdater(service,sources,collector=collector()).tick()
    forged=sources.ingest_text(owner,title='Unmanaged fake marker',body='Manually submitted text.',
        metadata={'automatic_source_id':saved['id'],'_automatic_source_revision':1},idempotency_key=str(uuid4()))
    automatic[1]._test_retained=UUID(forged['source_id'])
    with service.database.engine.begin() as c:
        version=c.execute(text('SELECT * FROM c0_source_versions WHERE id=:id'),{'id':forged['id']}).mappings().one()
        assert guard_publication(c,version,service.access) is None
        assert c.execute(text('SELECT publication_metadata FROM c0_source_versions WHERE id=:id'),{'id':forged['id']}).scalar_one()==version['publication_metadata']
        assert c.execute(text('SELECT state FROM c0_source_versions WHERE id=(SELECT version_id FROM c0_automatic_source_items WHERE definition_id=:id)'),{'id':saved['id']}).scalar_one()=='queued'
    assert service.runs(owner,saved['id'])[0]['state']=='pending'
    with service.database.engine.begin() as c:
        registry.get('source.extract').execute(c,{'version_id':forged['id']})
    assert sources.get(owner,forged['source_id'])['metadata']['_automatic_source_revision']==1


@pytest.mark.parametrize('revoke',[False,True])
def test_parallel_extraction_rechecks_native_authority_before_publication(automatic,revoke):
    from czero_core.extraction import extract_isolated
    from czero_core.extraction_queue import ExtractionQueue
    service,sources,owner,_=automatic
    acl=sources.access;key=uuid4();record_unadmitted(acl,key,'pool-editor')
    account=account_named(acl,owner,'pool-editor');acl.set_role(owner,account['id'],Role.EDITOR)
    editor=acl.resolve(identity(acl,key,'pool-editor'))
    saved=service.save(editor,name='Pool original',kind='github',config={'repositories':['synthetic/example']},
        enabled=True,interval_seconds=3600,idempotency_key=str(uuid4()))
    updater=SourceUpdater(service,sources,collector=collector());updater.tick()
    with service.database.engine.connect() as c:
        item=dict(c.execute(text('SELECT * FROM c0_automatic_source_items WHERE definition_id=:id'),{'id':saved['id']}).mappings().one())
    queue=ExtractionQueue(service.database,acl,sources.originals,enabled=True)
    run=queue.enqueue(owner,item['version_id'],expected_generation=1)
    claim=queue.claim()
    result=extract_isolated(sources.originals.check(claim.original),claim.original['media_type'])
    assert queue.complete(claim,result)
    if revoke:acl.set_role(owner,account['id'],Role.READER)
    assert queue.publish(run['id']) is (not revoke)
    current=sources.get(owner,item['source_id'])['current_version_id']
    if revoke:
        assert current is None
        with service.database.engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).scalar_one()==0
        assert service.runs(owner,saved['id'])[0]['state']=='blocked'
    else:
        assert current==item['version_id']
        updater.tick()
        assert service.runs(owner,saved['id'])[0]['state']=='complete'


def test_manual_metadata_edit_before_extraction_cannot_be_overwritten(automatic):
    service,sources,owner,registry=automatic;saved=definition(automatic)
    updater=SourceUpdater(service,sources,collector=collector());updater.tick()
    Worker(service.database,registry).tick();updater.tick()
    stored=service.documents(owner,saved['id'])[0]
    previous=sources.get(owner,stored['id'])
    service.command(owner,saved['id'],expected_revision=1,idempotency_key=str(uuid4()),action='run')
    SourceUpdater(service,sources,collector=collector(b'Automatic replacement waiting for extraction.')).tick()
    current=sources.get(owner,stored['id'])
    sources.ingest_text(owner,title='Manually retitled',body=collector()()[0][0]['body'].decode(),
        media_type='text/markdown',source_id=stored['id'],expected_revision=current['revision'],idempotency_key=str(uuid4()))
    Worker(service.database,registry).tick()
    assert sources.get(owner,stored['id'])['title']=='Manually retitled'
    assert sources.get(owner,stored['id'])['current_version_id']==previous['current_version_id']
    assert service.runs(owner,saved['id'])[0]['state']=='blocked'


@pytest.fixture
def website_pdf(tmp_path, request):
    listing_tag = getattr(request, 'param', 'article')
    from pathlib import Path
    from runpy import run_path
    from czero_core.source_collectors import collect

    origin = 'https://publisher.example.org'
    listing = origin + '/notices'
    notice = origin + '/files/notice.pdf'
    second = origin + '/files/other.pdf'
    generate = run_path(str(Path(__file__).resolve().parents[1] / 'fixtures/evidence/pipeline/generate.py'))['pdf']
    files = {}
    etags = {}
    requests = []

    def update(label, pages, *, url=notice, etag=None):
        path = tmp_path / label
        generate(path, pages)
        files[url] = path.read_bytes()
        if etag:
            etags[url] = etag
        else:
            etags.pop(url, None)
        return files[url]

    class Fetch:
        requests = 0
        downloaded = 0

        def response(self, url, *, validate_url=None, **options):
            if validate_url:
                validate_url(url)
            self.requests += 1
            requests.append(url)
            if url == origin + '/robots.txt':
                body, media = b'User-agent: *\nAllow: /', 'text/plain'
            elif url == listing:
                links = ''.join(f'<a href="{target}">Notice</a>' for target in [notice, '/files/notice.pdf#featured', *[target for target in files if target != notice]])
                body, media = f'<{listing_tag}><h1>Notices</h1>{links}</{listing_tag}>'.encode(), 'text/html'
            else:
                body, media = files[url], 'application/pdf'
                validator = (options.get('first_request_headers') or {}).get('If-None-Match')
                if validator and validator == etags.get(url):
                    return b'', url, '', {'status': 304, 'etag': validator}
            self.downloaded += len(body)
            return body, url, media, {'status': 200, 'etag': etags.get(url)}

        def close(self):
            pass

    def collector(kind, config, cursor, **options):
        return collect(kind, config, cursor, fetcher=Fetch(), **options)

    config = {'website': {'seeds': [listing], 'allowed_roots': [listing]}, 'max_items': 1,
              'attachments': {'allowed_roots': [origin + '/files']}}
    return config, collector, update, notice, second, requests


def published_run(service, sources, owner, registry, definition_id, collect_pdf, *, queue=None):
    from czero_core.extraction_queue import ExtractionWorker

    # Recreate the updater between ticks to exercise persisted continuation.
    for _ in range(14):
        SourceUpdater(service, sources, collector=collect_pdf, extraction_queue=queue).tick()
        Worker(sources.database, registry).tick()
        if queue:
            ExtractionWorker(queue).tick(max_units=4)
        result = service.runs(owner, definition_id)[0]
        if result['state'] not in ('queued', 'running', 'pending'):
            return result
    pytest.fail('Automatic publication failed to reach a terminal state')


def test_website_pdf_continuation_readback_and_failed_replacement(automatic, website_pdf, monkeypatch):
    import hashlib
    from czero_core.current_content import ContentSuperseded
    from czero_core.extraction_queue import ExtractionQueue
    from czero_core.extraction_status import reconciliation

    service, sources, owner, registry = automatic
    config, collect_pdf, update, notice, second, requests = website_pdf
    first = update('first.pdf', ['Synthetic notice original'], etag='"synthetic-v1"')
    update('other.pdf', ['Independent synthetic act'], url=second)
    saved = definition(automatic, kind='website', config=config, interval_seconds=None)
    params = (service, sources, owner, registry, saved['id'], collect_pdf)
    run = published_run(*params)
    assert run['state'] == 'complete'
    assert run['diagnostics']['pdf'] == {'new': 2, 'fetched': 2, 'published': 2, 'selected': 2}
    assert requests.count(notice) == 1
    assert len(service.documents(owner, saved['id'])) == 3
    doc = next(row for row in service.documents(owner, saved['id']) if row['title'] == 'notice.pdf')
    before = sources.get(owner, doc['id'])
    current = before['current_version_id']
    path, version = sources.original(owner, current)
    assert path.read_bytes() == first and version['content_hash'] == hashlib.sha256(first).hexdigest()
    evidence = sources.document(owner, current)
    assert 'Synthetic notice original' in evidence['body']
    citation = sources.citation(owner, sources.chunks(owner, evidence['id'])[0]['id'])
    assert citation['version_id'] == current and citation['locations'][0]['index'] == 1

    def run_again():
        service.command(owner, saved['id'], expected_revision=1, action='run', idempotency_key=str(uuid4()))
        return published_run(*params)

    assert run_again()['diagnostics']['pdf'] == {'fetched': 1, 'not_modified': 1, 'unchanged': 2, 'selected': 2}
    assert sources.get(owner, doc['id']) == before
    check_original = sources.originals.check
    missing = False

    def lose_after_first_check(row):
        nonlocal missing
        original = check_original(row)
        if not missing and row['id'] == current:
            original.unlink()
            missing = True
        return original

    with monkeypatch.context() as patch:
        patch.setattr(sources.originals, 'check', lose_after_first_check)
        assert run_again()['error_code'] == 'website_retained_original_missing'
    assert run_again()['diagnostics']['pdf']['restored_original'] == 1
    assert sources.get(owner, doc['id']) == before
    assert sources.original(owner, current)[0].read_bytes() == first

    update('mixed.pdf', ['Synthetic unpublished marker', 'SCAN'])
    failed = run_again()
    assert failed['state'] == 'partial'
    assert failed['diagnostics']['reasons']['unsupported_scan'] == 1
    assert sources.get(owner, doc['id'])['current_version_id'] == current
    assert not any('unpublished marker' in hit['body'] for hit in sources.search(owner, 'Synthetic unpublished marker'))
    queue = ExtractionQueue(sources.database, sources.access, sources.originals)
    diagnostic = next(row for row in reconciliation(queue, owner) if row['source_id'] == UUID(str(doc['id'])))
    assert diagnostic['state'] == 'failed' and diagnostic['current_available']
    assert diagnostic['next_step'] == 'reacquire_original'
    assert run_again()['state'] == 'partial'

    before_repair = sources.get(owner, doc['id'])
    sources.originals.path(current).unlink()
    assert update('first.pdf', ['Synthetic notice original']) == first
    restored = run_again()
    assert restored['state'] == 'complete'
    assert restored['diagnostics']['pdf']['restored_original'] == 1
    assert sources.get(owner, doc['id']) == before_repair
    assert sources.original(owner, current)[0].read_bytes() == first

    updated = update('replacement.pdf', ['Synthetic replacement evidence'])
    assert run_again()['state'] == 'complete'
    new_version = sources.get(owner, doc['id'])['current_version_id']
    assert new_version != current
    assert sources.original(owner, new_version)[0].read_bytes() == updated
    with pytest.raises(ContentSuperseded):
        sources.citation(owner, citation['chunk_id'])


@pytest.mark.parametrize('pause', [False, True])
def test_website_pdf_page_queue_handoff_and_pause(automatic, website_pdf, pause):
    from czero_core.extraction_queue import ExtractionQueue, ExtractionWorker
    from czero_core.extraction_status import reconciliation

    service, sources, owner, registry = automatic
    config, collect_pdf, update, *_ = website_pdf
    config['attachments']['page_queue'] = True
    update('first.pdf', ['Native page one', 'Native page two'])
    saved = definition(automatic, kind='website', config=config, interval_seconds=None)
    queue = ExtractionQueue(sources.database, sources.access, sources.originals, enabled=True)
    params = (service, sources, owner, registry, saved['id'], collect_pdf)
    updater = SourceUpdater(service, sources, collector=collect_pdf, extraction_queue=queue)
    updater.tick()  # Commit the listing.
    Worker(sources.database, registry).tick()
    updater.tick()  # Commit a queue-only PDF version.
    doc = next(row for row in service.documents(owner, saved['id']) if row['title'] == 'notice.pdf')
    assert sources.get(owner, doc['id'])['current_version_id'] is None
    Worker(sources.database, registry).tick()
    assert sources.get(owner, doc['id'])['current_version_id'] is None
    updater.tick()  # Resume and hand off the staged original.
    def diagnostic_state():
        return next(row['state'] for row in reconciliation(queue, owner)
                    if row['source_id'] == UUID(str(doc['id'])))

    assert diagnostic_state() == 'queued'
    claim = queue.claim()
    assert claim is not None
    assert diagnostic_state() == 'running'
    if pause:
        service.command(owner, saved['id'], expected_revision=1, action='pause', idempotency_key=str(uuid4()))
        assert not queue.fail(claim, 'parser_failed')
        assert service.runs(owner, saved['id'])[0]['state'] == 'cancelled'
        assert sources.get(owner, doc['id'])['current_version_id'] is None
    else:
        from czero_core.pdf_units import extract_page_isolated
        assert queue.complete(claim, extract_page_isolated(sources.originals.path(claim.version_id), claim.ordinal))
        ExtractionWorker(queue).tick(max_units=2)
        assert published_run(*params, queue=queue)['state'] == 'complete'
        current = sources.get(owner, doc['id'])['current_version_id']
        evidence = sources.document(owner, current)
        assert [location['index'] for location in evidence['locations']] == [1, 2]


@pytest.mark.parametrize('website_pdf', ['body'], indirect=True)
@pytest.mark.parametrize('attachment_include', [[], ['*']], ids=['suffix', 'glob'])
def test_website_pdf_publishes_from_listing_without_article(automatic, website_pdf, attachment_include):
    service, sources, owner, registry = automatic
    config, collect_pdf, update, *_ = website_pdf
    config['attachments']['include'] = attachment_include
    original = update('first.pdf', ['Selected PDF from plain listing'])
    saved = definition(automatic, kind='website', config=config, interval_seconds=None)
    result = published_run(service, sources, owner, registry, saved['id'], collect_pdf)
    assert result['state'] == 'partial'
    assert result['diagnostics']['reasons'] == {'website_article_missing_or_javascript_only': 1}
    document, = service.documents(owner, saved['id'])
    current = sources.get(owner, document['id'])['current_version_id']
    assert sources.original(owner, current)[0].read_bytes() == original


def test_website_pdf_retries_after_page_queue_is_enabled(automatic, website_pdf):
    from czero_core.extraction_queue import ExtractionQueue

    service, sources, owner, registry = automatic
    config, collect_pdf, update, *_ = website_pdf
    config['attachments']['page_queue'] = True
    original = update('first.pdf', ['Native page one', 'Native page two'])
    saved = definition(automatic, kind='website', config=config, interval_seconds=None)
    params = (service, sources, owner, registry, saved['id'], collect_pdf)
    failed = published_run(*params)
    assert failed['state'] == 'partial'
    assert failed['diagnostics']['reasons'] == {'extraction_units_disabled': 1}
    doc = next(row for row in service.documents(owner, saved['id']) if row['title'] == 'notice.pdf')

    service.command(owner, saved['id'], expected_revision=1, action='run', idempotency_key=str(uuid4()))
    queue = ExtractionQueue(sources.database, sources.access, sources.originals, enabled=True)
    assert published_run(*params, queue=queue)['state'] == 'complete'
    current = sources.get(owner, doc['id'])['current_version_id']
    assert sources.original(owner, current)[0].read_bytes() == original
