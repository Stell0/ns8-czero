# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Page recovery and publication use real PostgreSQL and isolated parsers."""
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from uuid import UUID

import pytest
from sqlalchemy import text

from czero_core.current_content import ContentSuperseded
from czero_core.extraction import ExtractionError
from czero_core.extraction_queue import ExtractionQueue, ExtractionWorker
from czero_core.sources import SourceConflict
from czero_core.identity import PermissionDenied, Role
from test_access import access
from test_sources import sources, upload, execute
from test_spaces import spaces, create, member

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')
FIXTURES=Path(__file__).resolve().parents[1]/'fixtures/evidence/pipeline'


def pdf(sources,name='readable-100.pdf',**kwargs):
    version=upload(sources,(FIXTURES/name).read_bytes(),filename=name,media_type='application/pdf',
        retain_original=True,**kwargs)
    service,owner,_,_=sources
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True)
    run=queue.enqueue(owner,version['id'],expected_generation=1)
    return queue,owner,version,run


def drain(queue):
    worker=ExtractionWorker(queue)
    for _ in range(12):
        if worker.tick()==0: break


def test_100_pages_two_failures_real_worker_kill_and_only_failed_pages_repeat(sources,monkeypatch):
    import czero_core.extraction_queue as module
    queue,owner,version,run=pdf(sources)
    calls=Counter(); actual=module.extract_page_isolated
    def parse(path,page):
        calls[page]+=1
        if page==37 and calls[page]==1: raise ExtractionError('parser_timeout')
        return actual(path,page)
    monkeypatch.setattr(module,'extract_page_isolated',parse)
    worker=ExtractionWorker(queue)
    # Complete through page 71; page 37 waits rather than retrying early.
    assert worker.tick(max_units=20)==20
    assert worker.tick(max_units=17)==17
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET available_at=now()+interval '1 day' WHERE run_id=:id AND ordinal=37"),{'id':run['id']})
    assert worker.tick(max_units=20)==20
    assert worker.tick(max_units=14)==14
    code="""
import os, signal
from uuid import UUID
from czero_core.database import Database
from czero_core.access import AccessService
from czero_core.sources import OriginalStore
from czero_core.extraction_queue import ExtractionQueue
from czero_core.pdf_units import extract_page_isolated
d=Database(os.environ['CZERO_TEST_DATABASE_URL'])
q=ExtractionQueue(d,AccessService(d,ISSUER,UUID(OWNER)),OriginalStore(ROOT),enabled=True)
claim=q.claim()
assert claim.ordinal==72
assert extract_page_isolated(q.originals.check(claim.original),72).text
os.kill(os.getpid(),signal.SIGKILL)
""".replace('ISSUER',repr(queue.access.issuer)).replace('OWNER',repr(str(queue.access.owner_account_key))).replace('ROOT',repr(str(queue.originals.root)))
    killed=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=15)
    assert killed.returncode==-9
    drain(queue)
    assert queue.status(owner,run['id'])['succeeded']==98
    assert sources[0].search(owner,'Pipeline')==[]
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET lease_deadline=now()-interval '1 second' WHERE run_id=:id AND ordinal=72"),{'id':run['id']})
    assert queue.claim() is None  # expiry fences the killed attempt before backoff
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET available_at=now() WHERE run_id=:id AND state='retry_wait'"),{'id':run['id']})
    drain(queue)
    status=queue.status(owner,run['id'])
    assert status['state']=='ready' and status['succeeded']==100
    assert calls[37]==2 and calls[72]==1
    assert all(calls[page]==1 for page in range(1,101) if page not in (37,72))
    document=sources[0].document(owner,version['id'])
    expected=next(row for row in json.loads((FIXTURES/'manifest.json').read_text())['files'] if row['name']=='readable-100.pdf')
    assert document['text_hash']==expected['text_sha256'] and document['locations']==expected['locations']
    assert queue.publish(run['id']) and queue.publish(run['id'])
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':version['id']}).scalar_one()==1
        assert c.execute(text('SELECT count(*) FROM c0_extraction_units WHERE run_id=:id AND body IS NOT NULL'),{'id':run['id']}).scalar_one()==0
        attempts=dict(c.execute(text('SELECT ordinal,lifetime_attempts FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).all())
    assert attempts[37]==attempts[72]==2
    assert all(attempts[p]==1 for p in range(1,101) if p not in (37,72))


def test_failed_replacement_preserves_current_and_manual_retry_is_revision_bound(sources,monkeypatch):
    import czero_core.extraction_queue as module
    old=upload(sources,b'Previous complete evidence',retain_original=True)
    execute(sources,'source.extract',old['id'])
    previous=sources[0].document(sources[1],old['id'])
    citation=sources[0].chunks(sources[1],previous['id'])[0]['id']
    queue,owner,version,run=pdf(sources,'blank-pages.pdf',source_id=old['source_id'],expected_revision=1)
    actual=module.extract_page_isolated
    def fail(path,page):
        if page==4: raise ExtractionError('parser_failed')
        return actual(path,page)
    monkeypatch.setattr(module,'extract_page_isolated',fail)
    for _ in range(3):
        with queue.database.engine.begin() as c:
            c.execute(text("UPDATE c0_extraction_units SET available_at=now() WHERE run_id=:id AND state='retry_wait'"),{'id':run['id']})
        drain(queue)
    status=queue.status(owner,run['id'])
    assert status['state']=='failed'
    assert sources[0].citation(owner,citation)['body']
    assert sources[0].document(owner,old['id'])['body']=='Previous complete evidence'
    with pytest.raises(SourceConflict):
        queue.retry_failed(owner,run['id'],expected_revision=status['revision']-1,idempotency_key=uuid4().hex)
    key=uuid4().hex
    saved=queue.retry_failed(owner,run['id'],expected_revision=status['revision'],idempotency_key=key)
    assert queue.retry_failed(owner,run['id'],expected_revision=status['revision'],idempotency_key=key)==saved
    monkeypatch.setattr(module,'extract_page_isolated',actual)
    drain(queue)
    assert queue.status(owner,run['id'])['state']=='ready'
    with pytest.raises(ContentSuperseded): sources[0].citation(owner,citation)
    assert sources[0].document(owner,version['id'])['body']
    with queue.database.engine.connect() as c:
        attempts=c.execute(text('SELECT attempts,lifetime_attempts,fence FROM c0_extraction_units WHERE run_id=:id AND ordinal=4'),{'id':run['id']}).one()
    assert attempts[0]==1 and attempts[1]==4 and attempts[2]==4


def test_corrupt_staged_result_never_publishes(sources):
    queue,owner,version,run=pdf(sources,'blank-pages.pdf')
    for _ in range(5):
        claim=queue.claim()
        from czero_core.pdf_units import extract_page_isolated
        assert queue.complete(claim,extract_page_isolated(queue.originals.check(claim.original),claim.ordinal))
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET body='Corrupt' WHERE run_id=:id AND ordinal=2"),{'id':run['id']})
    assert not queue.publish(run['id'])
    assert queue.status(owner,run['id'])['state']=='failed'
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':version['id']}).scalar_one()==0


def test_expired_retry_never_recreates_successful_siblings(sources):
    queue,owner,_,run=pdf(sources,'mixed-scan.pdf')
    drain(queue)
    status=queue.status(owner,run['id'])
    assert status['state']=='failed' and status['succeeded']==1
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_runs SET expires_at=now()-interval '1 second' WHERE id=:id"),{'id':run['id']})
    with pytest.raises(ValueError,match='staging_expired'):
        queue.retry_failed(owner,run['id'],expected_revision=status['revision'],idempotency_key=uuid4().hex)
    queue.cleanup()
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_extraction_units WHERE run_id=:id AND body IS NOT NULL'),{'id':run['id']}).scalar_one()==0


def test_publication_rechecks_selected_space_and_current_editor_authority(spaces,sources):
    catalog,owner,_=spaces
    private=create(spaces)
    selected=sources[0].in_space(private['id'])
    scoped=(selected,owner,sources[2],sources[3])
    version=upload(scoped,(FIXTURES/'blank-pages.pdf').read_bytes(),media_type='application/pdf',retain_original=True)
    editor=member(spaces,Role.EDITOR)
    catalog.set_grant(owner,private['id'],editor.user_id,Role.EDITOR,expected_revision=0,idempotency_key=uuid4().hex)
    queue=ExtractionQueue(selected.database,selected.access,selected.originals,enabled=True).in_space(private['id'])
    run=queue.enqueue(editor,version['id'],expected_generation=1)
    from czero_core.pdf_units import extract_page_isolated
    for _ in range(5):
        claim=queue.claim()
        result=extract_page_isolated(queue.originals.check(claim.original),claim.ordinal)
        assert queue.complete(claim,result)
    with pytest.raises(PermissionDenied): queue.in_space(uuid4()).status(editor,run['id'])
    catalog.set_grant(owner,private['id'],editor.user_id,None,expected_revision=1,idempotency_key=uuid4().hex)
    assert not queue.publish(run['id'])
    assert queue.status(owner,run['id'])['error_code']=='authority_lost'
    with selected.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':version['id']}).scalar_one()==0


def test_two_assemblers_publish_once_without_holding_parser_locks(sources,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    import czero_core.extraction_queue as module
    from czero_core.current_content import CONTENT_LOCK
    from czero_core.worker import WORKER_LOCK
    queue,owner,version,run=pdf(sources,'blank-pages.pdf')
    from czero_core.pdf_units import extract_page_isolated
    for _ in range(5):
        claim=queue.claim()
        result=extract_page_isolated(queue.originals.check(claim.original),claim.ordinal)
        assert queue.complete(claim,result)
    actual=module.assemble_pdf
    phase=Barrier(2); probes=Lock()
    def observed(rows,pages):
        phase.wait(timeout=10)
        # Serialize only the independent probes so they cannot contend with
        # each other, then let both assemblers race through publication.
        with probes:
            with queue.database.engine.begin() as c:
                for key in (CONTENT_LOCK,WORKER_LOCK):
                    assert c.execute(text('SELECT pg_try_advisory_xact_lock(:key)'),{'key':key}).scalar_one()
        phase.wait(timeout=10)
        return actual(rows,pages)
    monkeypatch.setattr(module,'assemble_pdf',observed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(pool.map(lambda _:queue.publish(run['id']),range(2)))
    assert queue.status(owner,run['id'])['state']=='ready'
    assert queue.complete(claim,result)  # lost completion acknowledgement after publication
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':version['id']}).scalar_one()==1


def test_actual_native_operator_command_retries_only_failed_units(sources):
    queue,owner,_,run=pdf(sources,'mixed-scan.pdf')
    drain(queue)
    status=queue.status(owner,run['id'])
    command=[sys.executable,'-m','czero_app.extraction_admin','--run',str(run['id']),
        '--space',str(run['space_id']),'--expected-revision',str(status['revision']),
        '--idempotency-key',uuid4().hex]
    environment={**os.environ,'CZERO_EXTRACTION_UNITS':'1',
        'CZERO_DATABASE_URL':queue.database.engine.url.render_as_string(hide_password=False),
        'CZERO_OIDC_ISSUER':queue.access.issuer,'CZERO_OWNER_LDAP_UUID':str(queue.access.owner_account_key),
        'CZERO_SOURCE_DIR':str(queue.originals.root)}
    rejected=subprocess.run(command,env={**environment,'CZERO_OWNER_LDAP_UUID':str(uuid4())},capture_output=True,text=True,timeout=10)
    assert rejected.returncode==1 and rejected.stderr=='C0 extraction retry failed\n'
    child=subprocess.run(command,env=environment,capture_output=True,text=True,timeout=10)
    assert child.returncode==0 and json.loads(child.stdout)['retried_units']==1
    repeat=subprocess.run(command,env=environment,capture_output=True,text=True,timeout=10)
    assert repeat.returncode==0 and repeat.stdout==child.stdout
    assert queue.status(owner,run['id'])['succeeded']==1


def test_expired_unpublished_original_requires_explicit_new_generation_and_full_parse(sources):
    queue,owner,version,run=pdf(sources,'blank-pages.pdf')
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_source_versions SET created_at=now()-interval '25 hours' WHERE id=:id"),{'id':version['id']})
        c.execute(text("UPDATE c0_extraction_runs SET expires_at=now()-interval '1 second' WHERE id=:id"),{'id':run['id']})
    queue.cleanup()
    assert queue.enqueue(owner,version['id'],expected_generation=1)['error_code']=='staging_expired'
    generation=sources[0].retry(owner,version['id'],expected_generation=1)
    assert generation['generation']==2
    next_run=queue.enqueue(owner,version['id'],expected_generation=2)
    assert next_run['id']!=run['id'] and next_run['succeeded']==0
    # Ordinary abandoned-version maintenance must not remove a newly authorized
    # run's retained original merely because the initial upload is old.
    execute(sources,'source.cleanup',UUID(int=0))
    drain(queue)
    assert queue.status(owner,next_run['id'])['state']=='ready'
    assert sources[0].document(owner,version['id'])['body']


def test_missing_retained_original_prevents_failed_unit_retry(sources):
    queue,owner,version,run=pdf(sources,'mixed-scan.pdf')
    drain(queue)
    status=queue.status(owner,run['id'])
    queue.originals.path(version['id']).unlink()
    with pytest.raises(ExtractionError,match='invalid_file'):
        queue.retry_failed(owner,run['id'],expected_revision=status['revision'],idempotency_key=uuid4().hex)
    assert queue.status(owner,run['id'])['revision']==status['revision']
