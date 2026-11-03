# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual PostgreSQL leases and isolated extraction; no published unit bodies."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.extraction import Extracted, ExtractionError
from czero_core.extraction_queue import ExtractionQueue, ExtractionWorker
from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.jobs import default_registry
from czero_core.worker import Worker, WORKER_LOCK
from czero_core.current_content import CONTENT_LOCK
from test_access import access, account_named, identity, record_unadmitted
from test_sources import sources, upload
from test_job_services import service as job_service
from test_spaces import spaces, create, member

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='disposable PostgreSQL required')


@pytest.fixture
def staged(sources):
    service, owner, _, _ = sources
    version = upload(sources, b'Unit evidence caf\xc3\xa9', retain_original=True)
    queue = ExtractionQueue(service.database, service.access, service.originals, enabled=True)
    run = queue.enqueue(owner, version['id'], expected_generation=1)
    return queue, owner, version, run


def expire(queue, claim):
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET lease_deadline=now()-interval '1 second' WHERE id=:id"), {'id':claim.unit_id})


def make_due(queue):
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET available_at=now() WHERE state='retry_wait'"))


def test_disabled_default_and_idempotent_handoff(staged, sources):
    queue, owner, version, run = staged
    assert queue.enqueue(owner, version['id'], expected_generation=1) == run
    assert run['state'] == 'extracting' and run['expected_units'] == 1
    service, _, registry, _ = sources
    disabled = ExtractionQueue(service.database, service.access, service.originals)
    with pytest.raises(ValueError, match='extraction_units_disabled'):
        disabled.enqueue(owner, version['id'], expected_generation=1)
    assert disabled.claim() is None
    assert Worker(service.database, registry).tick() == 0
    assert service.versions(owner, version['source_id'])[0]['state'] == 'queued'


def test_competing_claimants_fencing_and_duplicate_ack(staged):
    queue, owner, _, run = staged
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(lambda _: queue.claim(), range(2)))
    claim, = [value for value in attempts if value is not None]
    assert claim.fence == 1
    result = Extracted('Unit evidence café', [{'kind':'body','index':1,'start':0,'end':18}])
    assert queue.complete(claim, result)
    assert queue.complete(claim, result)
    assert not queue.complete(replace(claim, token=uuid4()), result)
    assert not queue.complete(claim, Extracted('Different evidence', []))
    status = queue.status(owner, run['id'])
    assert status['state'] == 'assembling' and status['succeeded'] == 1
    assert 'body' not in str(status) and 'token' not in str(status)


def test_expired_lease_retries_only_after_backoff_and_rejects_zombie(staged):
    queue, _, _, _ = staged
    first = queue.claim(); expire(queue, first)
    assert queue.claim() is None
    assert not queue.complete(first, Extracted('late', []))
    make_due(queue)
    second = queue.claim()
    assert second.unit_id == first.unit_id and second.fence == 2 and second.token != first.token
    assert not queue.complete(first, Extracted('late', []))
    assert queue.complete(second, Extracted('Current result', []))


def test_real_process_death_and_reconstructed_worker_resume(staged):
    queue, owner, _, run = staged
    acl = queue.access
    code = ("import os; from uuid import UUID; from czero_core.database import Database; "
            "from czero_core.access import AccessService; from czero_core.sources import OriginalStore; "
            "from czero_core.extraction_queue import ExtractionQueue; "
            "d=Database(os.environ['CZERO_TEST_DATABASE_URL']); "
            f"q=ExtractionQueue(d,AccessService(d,{acl.issuer!r},UUID('{acl.owner_account_key}')),")
    code += f"OriginalStore({str(queue.originals.root)!r}),enabled=True); assert q.claim(); os._exit(17)"
    child = subprocess.run([sys.executable,'-c',code], capture_output=True, timeout=10)
    assert child.returncode == 17
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET lease_deadline=now()-interval '1 second' WHERE run_id=:id"), {'id':run['id']})
    assert queue.claim() is None
    make_due(queue)
    later = ExtractionQueue(queue.database, acl, queue.originals, enabled=True)
    assert ExtractionWorker(later).tick() == 1
    assert later.status(owner, run['id'])['state'] == 'ready'
    assert ExtractionWorker(later).tick() == 0


def test_parser_has_no_transaction_or_locks_and_ordinary_jobs_continue(staged, sources, job_service, monkeypatch):
    import czero_core.extraction_queue as module
    queue, owner, version, run = staged
    service, _, registry, _ = sources
    jobs, _ = job_service
    health = jobs.enqueue(owner, 'health', {}, 'concurrent-health')
    real = module.extract_isolated
    def observed(path, media_type):
        assert queue.database.engine.pool.checkedout() == 0
        assert service.search(owner,'evidence')==[]
        with queue.database.engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':version['id']}).scalar_one()==0
        with queue.database.engine.begin() as c:
            for key in (CONTENT_LOCK, WORKER_LOCK):
                assert c.execute(text('SELECT pg_try_advisory_xact_lock(:key)'), {'key':key}).scalar_one()
        assert Worker(service.database, registry).tick() == 1
        return real(path, media_type)
    monkeypatch.setattr(module, 'extract_isolated', observed)
    assert ExtractionWorker(queue).tick() == 1
    assert jobs.get_job(owner, health['id'])['state'] == 'succeeded'
    assert queue.status(owner, run['id'])['succeeded'] == 1
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'), {'id':version['id']}).scalar_one() == 1
    assert service.document(owner,version['id'])['body']=='Unit evidence café'
    assert service.search(owner, 'evidence')


@pytest.mark.parametrize('code,attempts', [('parser_timeout',3),('invalid_file',1),('unsupported_scan',1)])
def test_transient_and_terminal_errors_are_bounded(staged, code, attempts):
    queue, owner, _, run = staged
    for index in range(attempts):
        make_due(queue)
        claim = queue.claim()
        assert claim is not None and queue.fail(claim, code)
    assert queue.status(owner, run['id'])['state'] == 'failed'
    assert queue.claim() is None


@pytest.mark.parametrize('action', ['delete','retry','replace','expire','cancel'])
def test_source_and_generation_invalidation_fence_results(staged, sources, action):
    queue, owner, version, run = staged
    claim = queue.claim()
    service = sources[0]
    if action == 'delete': service.delete(owner, version['source_id'], expected_revision=1)
    elif action == 'retry':
        service.retry(owner, version['id'], expected_generation=1)
    elif action == 'replace':
        upload(sources, b'Replacement', source_id=version['source_id'], expected_revision=1)
    elif action == 'cancel': queue.cancel(owner, run['id'])
    else:
        with queue.database.engine.begin() as c:
            c.execute(text("UPDATE c0_extraction_runs SET expires_at=now()-interval '1 second' WHERE id=:id"), {'id':run['id']})
        queue.cleanup()
    assert not queue.complete(claim, Extracted('Must not survive', []))
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_extraction_units WHERE run_id=:id AND body IS NOT NULL'), {'id':run['id']}).scalar_one() == 0


def test_current_roles_selected_space_and_unsupported_handoff(staged, sources):
    queue, owner, version, run = staged
    with pytest.raises(PermissionDenied): queue.in_space(uuid4()).status(owner, run['id'])
    with pytest.raises(PermissionDenied): queue.in_space(uuid4()).enqueue(owner, version['id'], expected_generation=1)
    with pytest.raises(ValueError, match='unsupported_extraction_handoff'):
        queue.enqueue(replace(owner, delegated_scopes=frozenset({'c0:write'})), version['id'], expected_generation=1)
    acl = sources[0].access
    key = uuid4(); record_unadmitted(acl, key, 'editor')
    account = account_named(acl, owner, 'editor')['id']
    acl.set_role(owner, account, Role.EDITOR)
    editor = acl.resolve(identity(acl, key, 'editor'))
    # A fresh run owned by this native Editor loses authority before processing.
    next_version = upload(sources, b'Another source', title='Another source')
    next_run = queue.enqueue(editor, next_version['id'], expected_generation=1)
    acl.set_role(owner, account, Role.READER)
    assert queue.claim() is not None  # original owner run
    assert queue.claim() is None     # revoked Editor run is fenced
    assert queue.status(owner, next_run['id'])['error_code'] == 'authority_lost'


def test_protected_spaces_and_revocation_are_enforced_in_result_transaction(spaces, sources):
    catalog, owner, _ = spaces
    private = create(spaces)
    service, _, registry, created = sources
    selected = service.in_space(private['id'])
    version = upload((selected,owner,registry,created), b'Private evidence')
    editor = member(spaces,Role.EDITOR)
    queue = ExtractionQueue(service.database,service.access,service.originals,enabled=True).in_space(private['id'])
    with pytest.raises(PermissionDenied): queue.enqueue(editor,version['id'],expected_generation=1)
    catalog.set_grant(owner,private['id'],editor.user_id,Role.EDITOR,expected_revision=0,idempotency_key=uuid4().hex)
    run = queue.enqueue(editor,version['id'],expected_generation=1)
    from czero_core.sources import SourceNotFound
    with pytest.raises(SourceNotFound):
        ExtractionQueue(service.database,service.access,service.originals).status(owner,run['id'])
    claim = queue.claim()
    catalog.set_grant(owner,private['id'],editor.user_id,None,expected_revision=1,idempotency_key=uuid4().hex)
    assert not queue.complete(claim,Extracted('Private evidence',[]))
    assert queue.status(owner,run['id'])['error_code']=='authority_lost'


def test_protocol_and_composite_foreign_keys_reject_invalid_writes(spaces, staged):
    from sqlalchemy.exc import DBAPIError, IntegrityError
    queue, _, _, run = staged
    other = create(spaces)
    for table in ('c0_extraction_runs','c0_extraction_units'):
        with pytest.raises(DBAPIError,match='writer protocol changed'):
            with queue.database.engine.begin() as c:
                c.execute(text("SET LOCAL c0.content_protocol='0'"))
                c.execute(text('UPDATE '+table+' SET state=state'))
    with pytest.raises(IntegrityError):
        with queue.database.engine.begin() as c:
            c.execute(text('UPDATE c0_extraction_units SET space_id=:space WHERE run_id=:id'), {'space':UUID(other['id']),'id':run['id']})


@pytest.mark.parametrize('field', ['manifest_sha256','profile','input_sha256','locator'])
def test_corrupt_or_changed_manifest_never_reaches_parser(staged,field):
    queue, owner, _, run = staged
    table = 'c0_extraction_runs' if field in ('manifest_sha256','profile') else 'c0_extraction_units'
    replacement = "'{}'::jsonb" if field in ('profile','locator') else "'"+'0'*64+"'"
    with queue.database.engine.begin() as c:
        c.execute(text('UPDATE '+table+' SET '+field+'='+replacement))
    assert queue.claim() is None
    assert queue.status(owner,run['id'])['error_code']=='manifest_mismatch'


def test_modified_original_fails_safely_without_private_result(staged):
    queue, owner, version, run = staged
    queue.originals.path(version['id']).write_bytes(b'Changed original')
    assert ExtractionWorker(queue).tick()==1
    result = queue.status(owner,run['id'])
    assert result['state']=='failed' and result['error_code']=='invalid_file'


def test_successful_staging_expires_without_body_retention(staged):
    queue, owner, _, run = staged
    claim = queue.claim()
    assert queue.complete(claim,Extracted('Successful staging',[]))
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_runs SET expires_at=now()-interval '1 second' WHERE id=:id"),{'id':run['id']})
    assert queue.status(owner,run['id'])['error_code']=='staging_expired'
    assert queue.cleanup()==1 and queue.cleanup()==0
    assert not queue.complete(claim,Extracted('Successful staging',[]))
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT body FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).scalar_one() is None


def test_actual_opt_in_app_worker_uses_saved_native_configuration(staged):
    import json
    queue, owner, _, run = staged
    child = subprocess.run([sys.executable,'-m','czero_app.extraction_worker'],
        env={**os.environ,'CZERO_EXTRACTION_UNITS':'1',
             'CZERO_DATABASE_URL':queue.database.engine.url.render_as_string(hide_password=False),
             'CZERO_OIDC_ISSUER':queue.access.issuer,
             'CZERO_OWNER_LDAP_UUID':str(queue.access.owner_account_key),
             'CZERO_SOURCE_DIR':str(queue.originals.root)},
        capture_output=True,text=True,timeout=10)
    output=json.loads(child.stdout)
    assert child.returncode==0 and output['processed']==1 and output['workers']==2
    assert not any(word in child.stdout for word in ('lease_token','original','password','body'))
    assert queue.status(owner,run['id'])['state']=='ready'
