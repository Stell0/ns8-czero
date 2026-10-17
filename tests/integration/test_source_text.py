# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public text ingestion uses real PostgreSQL receipts, jobs and evidence."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import threading
from uuid import UUID, uuid4, uuid5

import pytest
from sqlalchemy import text

from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.sources import MAX_INGEST_TEXT_BYTES, SourceConflict, SourceNotFound, SourceService
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound, WikiService
from czero_core.worker import Worker
from test_access import access, identity, record_unadmitted, account_named
from test_sources import sources, execute
from test_knowledge import knowledge
from test_wiki import wiki, create_entity

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def text_sources(sources):
    yield sources
    service, *_ = sources
    with service.database.engine.begin() as c:
        c.execute(text('''DELETE FROM c0_knowledge_receipts WHERE actor_id IN
            (SELECT id FROM c0_accounts WHERE issuer=:issuer)'''), {'issuer': service.access.issuer})


def submit(fixture, *, actor=None, **values):
    service, owner, _, created = fixture
    payload = dict(idempotency_key=uuid4().hex, title='AM1 evidence', body='Selected evidence café 東京 🔧',
                   media_type='text/plain', metadata={'origin': 'synthetic investigation'})
    payload.update(values)
    row = service.ingest_text(owner if actor is None else actor, **payload)
    key = UUID(row['source_id'])
    if key not in created: created.append(key)
    return row


@pytest.mark.parametrize('media_type', ['text/plain', 'text/markdown'])
def test_text_receipt_actual_worker_chunks_hashes_and_immutable_replay(text_sources, media_type):
    service, owner, registry, _ = text_sources
    body = '# Selected observation\r\n\r\nCafé 東京 🔧\rno inference inside C0'
    values = dict(body=body, media_type=media_type, idempotency_key='delivery')
    receipt = submit(text_sources, **values)
    assert receipt['state'] == 'queued' and receipt['original_present'] and receipt['job_id']
    assert receipt['content_hash'] == hashlib.sha256(body.encode()).hexdigest()
    with pytest.raises(SourceNotFound): service.document(owner, receipt['id'])
    # Ordinary independent services retain IDs across application reconstruction.
    later = SourceService(service.database, service.access, registry, service.originals)
    assert later.ingest_text(owner, title='AM1 evidence', metadata={'origin':'synthetic investigation'}, **values) == receipt
    Worker(service.database, registry).tick()
    version = later.versions(owner, receipt['source_id'])[0]
    assert version['state'] == 'ready' and version['job_state'] == 'succeeded'
    document = later.document(owner, receipt['id'])
    assert document['body'] == body.replace('\r\n', '\n').replace('\r', '\n')
    chunk = later.chunks(owner, document['id'])[0]
    citation = later.citation(owner, chunk['id'])
    assert str(citation['source_id']) == receipt['source_id'] and str(citation['version_id']) == receipt['id']
    assert citation['source_hash'] == receipt['content_hash'] and citation['body'] == chunk['body']
    assert not version['original_present']  # ordinary successful cleanup, not a second storage path
    assert submit(text_sources, **values) == receipt  # a submission receipt is not a readiness promise
    dedup = submit(text_sources, **{**values, 'idempotency_key':'another-delivery'})
    assert dedup['id'] == receipt['id'] and dedup['state'] == 'ready'


@pytest.mark.parametrize('changes', [
    {'body':''}, {'body':' \n\t'}, {'body':'bad\0text'}, {'body':'bad\ud800'}, {'body':b'bytes'},
    {'body':'x'*(MAX_INGEST_TEXT_BYTES+1)}, {'body':'é'*(MAX_INGEST_TEXT_BYTES//2+1)},
    {'title':'bad\udfff'}, {'title':'bad\nlabel'}, {'media_type':'application/pdf'},
    {'media_type':None}, {'media_type':[]}, {'metadata':[]}, {'metadata':{'key':'bad\0text'}},
    {'metadata':{'key':'bad\ud800'}}, {'metadata':{'key':float('nan')}},
    {'metadata':{'key':'x'*16384}}, {'idempotency_key':''}, {'idempotency_key':'bad key'},
    {'expected_revision':1}, {'source_id':str(uuid4()),'expected_revision':True},
    {'source_id':str(uuid4()),'expected_revision':0},
])
def test_invalid_text_rejected_without_receipt_source_job_or_original(text_sources, changes):
    service, owner, *_ = text_sources
    with service.database.engine.connect() as c:
        counts = tuple(c.execute(text('SELECT (SELECT count(*) FROM c0_sources),(SELECT count(*) FROM c0_jobs),(SELECT count(*) FROM c0_knowledge_receipts)')).one())
    with pytest.raises(ValueError): submit(text_sources, **changes)
    with service.database.engine.connect() as c:
        assert tuple(c.execute(text('SELECT (SELECT count(*) FROM c0_sources),(SELECT count(*) FROM c0_jobs),(SELECT count(*) FROM c0_knowledge_receipts)')).one()) == counts
    assert not service.originals.root.exists()


def test_utf8_byte_boundary_and_serialized_request_budget(text_sources):
    service, *_ = text_sources
    row = submit(text_sources, body='é'*(MAX_INGEST_TEXT_BYTES//2))
    assert row['size_bytes'] == MAX_INGEST_TEXT_BYTES
    # Worst-case one-byte JSON escaping still leaves room for the full metadata,
    # title, RPC envelope and key inside the unchanged one-MiB request bound.
    payload={'data':{'body':'\x01'*MAX_INGEST_TEXT_BYTES,'title':'x'*256,
        'metadata':{'value':'\x01'*(16384-20)},'idempotency_key':'x'*128,'media_type':'text/markdown'}}
    envelope={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'sources_ingest_text','arguments':payload}}
    assert len(json.dumps(envelope).encode()) < 1048576


def test_key_binds_payload_and_operation_and_is_scoped_to_actor(text_sources):
    service, owner, *_ = text_sources
    original=submit(text_sources,idempotency_key='shared-key')
    for changes in ({'body':'changed'}, {'metadata':{'origin':'different'}}, {'title':'different'}, {'media_type':'text/markdown'}):
        with pytest.raises(SourceConflict): submit(text_sources,idempotency_key='shared-key',**changes)
    with pytest.raises(KnowledgeConflict):
        WikiService(service.database,service.access).create_page(owner,'separate-operation','Wiki','Body',idempotency_key='shared-key')
    key=uuid4();record_unadmitted(service.access,key,'editor')
    account=account_named(service.access,owner,'editor');service.access.set_role(owner,account['id'],Role.EDITOR)
    editor=service.access.resolve(identity(service.access,key,'editor'))
    other=submit(text_sources,actor=editor,idempotency_key='shared-key',body='different actor evidence')
    assert other['id'] != original['id']


def test_concurrent_replay_and_revision_writers_have_one_result(text_sources):
    service, owner, *_ = text_sources
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(lambda _:submit(text_sources,idempotency_key='concurrent'),range(2)))
    assert rows[0] == rows[1]
    row=rows[0]
    def update(index):
        try:return submit(text_sources,source_id=row['source_id'],expected_revision=1,
            body='Changed observation '+str(index),idempotency_key='version-'+str(index))
        except SourceConflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool: versions=list(pool.map(update,range(2)))
    winner=next(v for v in versions if v is not None)
    assert sum(v is not None for v in versions)==1 and winner['number']==2
    assert service.get(owner,row['source_id'])['revision']==2
    index=versions.index(winner)
    assert update(index)==winner  # replay must precede the stale expected revision check
    with pytest.raises(SourceConflict): submit(text_sources,source_id=row['source_id'],expected_revision=1,body='stale')
    with pytest.raises(SourceConflict): submit(text_sources,source_id=row['source_id'],expected_revision=2,title='Changed provenance')
    service.delete(owner,row['source_id'],expected_revision=2)
    with pytest.raises(SourceConflict): submit(text_sources,source_id=row['source_id'],expected_revision=3,body='archived')


@pytest.mark.parametrize('role', list(Role))
def test_current_role_checked_before_replay_even_with_forged_actor(text_sources,role):
    service, owner, *_ = text_sources
    key=uuid4();record_unadmitted(service.access,key,'member')
    member=account_named(service.access,owner,'member');service.access.set_role(owner,member['id'],role)
    actor=Actor(member['id'],Role.ADMIN,True)
    if role is Role.READER:
        with pytest.raises(PermissionDenied): submit(text_sources,actor=actor,idempotency_key='member')
    else:
        submit(text_sources,actor=actor,idempotency_key='member')
    service.access.set_role(owner,member['id'],None)
    with pytest.raises(PermissionDenied): submit(text_sources,actor=actor,idempotency_key='member')


def test_revocation_while_waiting_for_receipt_lock_blocks_write(text_sources,monkeypatch):
    service, owner, *_ = text_sources
    key=uuid4();record_unadmitted(service.access,key,'waiting-editor')
    account=account_named(service.access,owner,'waiting-editor');service.access.set_role(owner,account['id'],Role.EDITOR)
    editor=Actor(account['id'],Role.EDITOR); authorized=threading.Event()
    original=service._authorize
    def authorize(c,actor,role=Role.READER):
        result=original(c,actor,role)
        if actor.user_id==editor.user_id: authorized.set()
        return result
    monkeypatch.setattr(service,'_authorize',authorize)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with service.database.engine.connect() as c:
            transaction=c.begin();c.execute(text('SELECT pg_advisory_xact_lock(49376)'))
            try:
                future=pool.submit(submit,text_sources,actor=editor,idempotency_key='waiting')
                assert authorized.wait(5)
                service.access.set_role(owner,editor.user_id,None)
            finally:
                transaction.rollback()  # release even when a regression fails the assertion
        with pytest.raises(PermissionDenied): future.result(timeout=10)
    assert not service.originals.root.exists()


def test_interrupted_transaction_retries_without_partial_versions_or_receipts(text_sources,monkeypatch):
    service, owner, registry, _ = text_sources
    enqueue=service.jobs._enqueue
    def interrupted(*args,**kwargs):
        enqueue(*args,**kwargs)
        raise RuntimeError('simulated transaction interruption')
    monkeypatch.setattr(service.jobs,'_enqueue',interrupted)
    with pytest.raises(RuntimeError,match='simulated transaction interruption'):
        submit(text_sources,idempotency_key='interrupted')
    assert service.list(owner)==[]
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_knowledge_receipts WHERE actor_id=:id'),{'id':owner.user_id}).scalar_one()==0
    monkeypatch.setattr(service.jobs,'_enqueue',enqueue)
    row=submit(text_sources,idempotency_key='interrupted')
    with service.database.engine.connect() as c:
        transaction=c.begin();registry.get('source.extract').execute(c,{'version_id':row['id']});transaction.rollback()
    assert service.versions(owner,row['source_id'])[0]['state']=='queued'
    later=SourceService(service.database,service.access,registry,service.originals)
    assert later.ingest_text(owner,idempotency_key='interrupted',title='AM1 evidence',
        body='Selected evidence café 東京 🔧',metadata={'origin':'synthetic investigation'})==row
    Worker(service.database,registry).tick()
    assert later.document(owner,row['id'])['body']=='Selected evidence café 東京 🔧'
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_source_versions WHERE source_id=:id'),{'id':row['source_id']}).scalar_one()==1


def test_text_evidence_must_commit_real_chunks_before_sourced_claim(knowledge,text_sources):
    knowledge_service,wiki_fixture,_=knowledge
    service,owner,*_=text_sources
    entity=create_entity(wiki_fixture)
    row=submit(text_sources)
    future_chunk=uuid5(uuid5(UUID(row['id']),'document'),'0')
    with pytest.raises(KnowledgeNotFound):
        knowledge_service.create_claim(owner,entity['id'],'observation',{'result':'recorded'},
            evidence_chunk_ids=[str(future_chunk)],idempotency_key='sourced')
    execute(text_sources,'source.extract',row['id'])
    claim=knowledge_service.create_claim(owner,entity['id'],'observation',{'result':'recorded'},
        evidence_chunk_ids=[str(future_chunk)],idempotency_key='sourced')
    citation=knowledge_service.get_claim(owner,claim['id'])['evidence'][0]
    assert citation['version_id']==row['id'] and citation['source_hash']==row['content_hash']


def test_actual_worker_interruption_recovery_keeps_receipt_and_retries_evidence(text_sources):
    from dataclasses import replace
    from czero_core.jobs import Registry
    from czero_core.worker import WorkerInterrupted
    service,owner,registry,_=text_sources
    row=submit(text_sources,idempotency_key='worker-interruption')
    spec=registry.get('source.extract')
    def interrupt(connection,payload):
        spec.execute(connection,payload)
        raise WorkerInterrupted()
    broken=Registry([registry.get('health'),registry.get('maintenance'),
        replace(spec,execute=interrupt),registry.get('source.cleanup')])
    with pytest.raises(WorkerInterrupted): Worker(service.database,broken).tick()
    assert service.versions(owner,row['source_id'])[0]['state']=='queued'
    assert service.originals.path(row['id']).exists()
    with pytest.raises(SourceNotFound):service.document(owner,row['id'])
    assert submit(text_sources,idempotency_key='worker-interruption')==row
    restarted=Worker(service.database,registry)
    restarted.tick()  # recover the committed running attempt with ordinary backoff
    with service.database.engine.begin() as c:
        job=c.execute(text('SELECT state,error_code,attempts FROM c0_jobs WHERE id=:id'),{'id':row['job_id']}).mappings().one()
        assert dict(job)=={'state':'queued','error_code':'interrupted','attempts':1}
        # Only this isolated test job becomes due; no system clock/authority changes.
        c.execute(text("UPDATE c0_jobs SET available_at=now()-interval '1 second' WHERE id=:id"),{'id':row['job_id']})
    restarted.tick()
    assert service.versions(owner,row['source_id'])[0]['state']=='ready'
    document=service.document(owner,row['id'])
    assert service.chunks(owner,document['id'])[0]['body']=='Selected evidence café 東京 🔧'
    with service.database.engine.connect() as c:
        runs=c.execute(text('SELECT attempt,state,error_code FROM c0_job_runs WHERE job_id=:id ORDER BY attempt'),{'id':row['job_id']}).mappings().all()
        assert [dict(r) for r in runs]==[{'attempt':1,'state':'failed','error_code':'interrupted'},
            {'attempt':2,'state':'succeeded','error_code':None}]
