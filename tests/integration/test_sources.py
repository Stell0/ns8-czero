# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from io import BytesIO
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.jobs import default_registry
from czero_core.sources import OriginalStore, SourceService, SourceConflict, register_source_handlers
from czero_core.worker import Worker
from test_access import access, owner_actor, record_unadmitted, account_named, identity

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def sources(access, tmp_path):
    acl, database, _ = access
    registry = default_registry()
    originals = OriginalStore(tmp_path / 'originals')
    register_source_handlers(registry, database, originals)
    service = SourceService(database, acl, registry, originals)
    created = []
    with database.engine.begin() as c:
        schedules = [dict(row) for row in c.execute(text('SELECT id,enabled,next_run_at FROM c0_scheduled_tasks')).mappings()]
        c.execute(text('UPDATE c0_scheduled_tasks SET enabled=false'))
    yield service, owner_actor(access), registry, created
    with database.engine.begin() as c:
        for source_id in created:
            ids = c.execute(text("SELECT id FROM c0_source_versions WHERE source_id=:id UNION SELECT id FROM c0_content_tombstones WHERE kind='source_version' AND resource_id=:id"), {'id': source_id}).scalars().all()
            c.execute(text('DELETE FROM c0_chunks WHERE document_id IN (SELECT id FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id))'), {'id': source_id})
            c.execute(text('DELETE FROM c0_documents WHERE version_id IN (SELECT id FROM c0_source_versions WHERE source_id=:id)'), {'id': source_id})
            c.execute(text('DELETE FROM c0_source_versions WHERE source_id=:id'), {'id': source_id})
            c.execute(text('DELETE FROM c0_sources WHERE id=:id'), {'id': source_id})
            c.execute(text('DELETE FROM c0_content_tombstones WHERE resource_id=:id'),{'id':source_id})
            c.execute(text('DELETE FROM c0_original_cleanup WHERE version_id=ANY(CAST(:ids AS uuid[]))'),{'ids':ids})
            for key in ids:
                c.execute(text('DELETE FROM c0_jobs WHERE payload->>\'version_id\'=:id'), {'id': str(key)})
        for row in schedules:
            c.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled,next_run_at=:next_run_at WHERE id=:id'), row)


def upload(fixture, data=b'Inventory evidence caf\xc3\xa9', **kwargs):
    service, owner, _, created = fixture
    args = dict(title='Inventory', filename='../../display-only.txt', media_type='text/plain')
    args.update(kwargs)
    row = service.ingest(owner, BytesIO(data), **args)
    if row['source_id'] not in created:
        created.append(row['source_id'])
    return row


def execute(fixture, name, version_id):
    service, _, registry, _ = fixture
    with service.database.engine.begin() as connection:
        return registry.get(name).execute(connection, {'version_id': str(version_id)})


def test_full_text_commits_before_cleanup_and_citations_survive_delete(sources):
    service, owner, _, _ = sources
    content = '# Section\n\nInventory café 東京 ' + 'full evidence ' * 300
    row = upload(sources, content.encode(), media_type='text/markdown')
    path = service.originals.path(row['id'])
    assert path.name == row['id'].hex and path.stat().st_mode & 0o777 == 0o600
    assert service.originals.root.stat().st_mode & 0o777 == 0o700
    assert execute(sources, 'source.cleanup', row['id']) == {'removed': False}
    assert path.exists()
    execute(sources, 'source.extract', row['id'])
    assert path.exists()  # Extraction COMMIT alone never removes an original.
    document = service.document(owner, row['id'])
    assert document['body'] == content
    assert document['text_hash'] == hashlib.sha256(content.encode()).hexdigest()
    segments = service.chunks(owner, document['id'])
    assert len(segments) > 1
    for chunk in segments:
        assert chunk['body'] == content[chunk['start_offset']:chunk['end_offset']]
        assert chunk['content_hash'] == hashlib.sha256(chunk['body'].encode()).hexdigest()
    citation = service.citation(owner, segments[0]['id'])
    assert citation['source_hash'] == row['content_hash'] and citation['version'] == 1
    assert service.search(owner, 'Inventory')[0]['source_id'] == row['source_id']
    execute(sources, 'source.cleanup', row['id'])
    assert not path.exists() and not service.versions(owner, row['source_id'])[0]['original_present']
    execute(sources, 'source.cleanup', row['id'])
    service.delete(owner, row['source_id'], expected_revision=1)
    assert service.search(owner, 'Inventory') == []
    assert service.list(owner) == []
    assert service.citation(owner, segments[0]['id'])['deleted'] is True
    assert service.document(owner, row['id'])['body'] == content


def test_retention_failure_retry_and_modified_original_quarantine(sources):
    service, owner, _, _ = sources
    retained = upload(sources, retain_original=True)
    execute(sources, 'source.extract', retained['id'])
    assert execute(sources, 'source.cleanup', retained['id']) == {'removed': False}
    assert service.originals.path(retained['id']).exists()
    bad = upload(sources, b'\xff')
    assert execute(sources, 'source.extract', bad['id']) == {'state': 'failed', 'error_code': 'invalid_text'}
    assert service.originals.path(bad['id']).read_bytes() == b'\xff'
    assert execute(sources, 'source.cleanup', bad['id']) == {'removed': False}
    retry = service.retry(owner, bad['id'], expected_generation=1)
    assert retry['generation'] == 2 and retry['state'] == 'queued'
    with pytest.raises(SourceConflict): service.retry(owner, bad['id'], expected_generation=1)
    execute(sources, 'source.extract', bad['id'])
    corrupt = upload(sources, title='Corrupt original')
    service.originals.path(corrupt['id']).write_bytes(b'changed original')
    assert execute(sources, 'source.extract', corrupt['id'])['error_code'] == 'invalid_file'
    assert service.originals.path(corrupt['id']).exists()


def test_extraction_rollback_and_cleanup_crash_recovery(sources, monkeypatch):
    service, owner, registry, _ = sources
    row = upload(sources)
    with service.database.engine.connect() as c:
        transaction = c.begin()
        registry.get('source.extract').execute(c, {'version_id': str(row['id'])})
        with service.database.engine.connect() as observer:
            assert observer.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'), {'id': row['id']}).scalar_one() == 0
        assert service.originals.path(row['id']).exists()
        transaction.rollback()
    assert service.versions(owner, row['source_id'])[0]['state'] == 'queued'
    execute(sources, 'source.extract', row['id'])
    real_remove = service.originals.remove
    def interrupted(key):
        real_remove(key)
        raise RuntimeError('simulated cleanup interruption')
    monkeypatch.setattr(service.originals, 'remove', interrupted)
    with pytest.raises(RuntimeError): execute(sources, 'source.cleanup', row['id'])
    assert service.versions(owner, row['source_id'])[0]['original_present']
    assert service.document(owner, row['id'])['body'] == 'Inventory evidence café'
    monkeypatch.setattr(service.originals, 'remove', real_remove)
    assert execute(sources, 'source.cleanup', row['id']) == {'removed': True}


def test_duplicate_and_concurrent_version_revision_contract(sources):
    service, owner, _, _ = sources
    first = upload(sources)
    assert upload(sources)['id'] == first['id']
    duplicate = upload(sources, source_id=first['source_id'], expected_revision=1)
    assert duplicate['id'] == first['id']
    assert len(list(service.originals.root.iterdir())) == 1
    assert service.get(owner, first['source_id'])['revision'] == 1
    def add(index):
        try:
            return upload(sources, f'changed {index}'.encode(), source_id=first['source_id'], expected_revision=1)
        except SourceConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add, range(2)))
    assert sum(item is not None for item in results) == 1
    assert [v['number'] for v in service.versions(owner,first['source_id'])]==[2]
    assert service.get(owner, first['source_id'])['revision'] == 2


def test_concurrent_initial_uploads_deduplicate_same_provenance(sources):
    def add(index):
        return upload(sources, filename=f'display-{index}.txt')
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(add, range(2)))
    assert rows[0]['id'] == rows[1]['id'] and rows[0]['source_id'] == rows[1]['source_id']
    assert len(list(sources[0].originals.root.iterdir())) == 1
    different = upload(sources, metadata={'origin': 'separate evidence'})
    assert different['source_id'] != rows[0]['source_id']


@pytest.mark.parametrize('role', list(Role))
def test_persisted_shared_space_role_rechecked_for_ingest_read_delete(sources, role):
    service, owner, _, _ = sources
    row = upload(sources)
    acl = service.access
    key = uuid4()
    record_unadmitted(acl, key, 'member')
    account = account_named(acl, owner, 'member')['id']
    acl.set_role(owner, account, role)
    member = acl.resolve(identity(acl, key, 'member'))
    forged = Actor(member.user_id, Role.ADMIN, True)
    assert service.get(forged, row['source_id'])['id'] == row['source_id']
    if role == Role.READER:
        with pytest.raises(PermissionDenied): service.ingest(forged, BytesIO(b'denied'), title='Title', filename='file.txt', media_type='text/plain')
        with pytest.raises(PermissionDenied): service.delete(forged, row['source_id'], expected_revision=1)
    else:
        service.delete(member, row['source_id'], expected_revision=1)
    acl.set_role(owner, account, None)
    with pytest.raises(PermissionDenied): service.get(member, row['source_id'])


def test_real_worker_extracts_and_then_deletes_original(sources):
    service, owner, registry, _ = sources
    row = upload(sources)
    Worker(service.database, registry).tick()
    version = service.versions(owner, row['source_id'])[0]
    assert version['state'] == 'ready' and version['job_state'] == 'succeeded'
    assert not version['original_present']
    assert service.document(owner, row['id'])['body'] == 'Inventory evidence café'


@pytest.mark.parametrize('sample', ['sample.txt', 'sample.md', 'sample.pdf', 'sample.docx'])
def test_four_format_storage_roundtrip_stable_hashes_and_duplicate(sources, sample):
    root = Path(__file__).parents[1] / 'fixtures/evidence'
    fixture = next(row for row in json.loads((root / 'manifest.json').read_text()) if row['filename'] == sample)
    content = (root / sample).read_bytes()
    row = upload(sources, content, filename=sample, media_type=fixture['media_type'])
    execute(sources, 'source.extract', row['id'])
    execute(sources, 'source.cleanup', row['id'])
    svc, owner, _, _ = sources
    document = svc.document(owner, row['id'])
    assert document['body'] == fixture['text']
    assert row['content_hash'] == hashlib.sha256(content).hexdigest()
    chunk = svc.chunks(owner, document['id'])[0]
    citation = svc.citation(owner, chunk['id'])
    assert citation['version_id'] == row['id'] and citation['body'] == fixture['text']
    duplicate = upload(sources, content, filename=sample, media_type=fixture['media_type'])
    assert duplicate['id'] == row['id']
    assert svc.chunks(owner, document['id'])[0]['id'] == chunk['id']


def test_partial_docx_quarantine_never_schedules_default_original_deletion(sources):
    from docx import Document
    from docx.oxml import OxmlElement
    document = Document(); paragraph = document.add_paragraph('Supported body')
    control = OxmlElement('w:sdt'); content = OxmlElement('w:sdtContent')
    run = OxmlElement('w:r'); evidence = OxmlElement('w:t'); evidence.text = 'Omitted evidence'
    run.append(evidence); content.append(run); control.append(content); paragraph._p.append(control)
    stream = BytesIO(); document.save(stream)
    row = upload(sources, stream.getvalue(), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    assert execute(sources, 'source.extract', row['id']) == {'state': 'failed', 'error_code': 'unsupported_docx'}
    service, owner, _, _ = sources
    version = service.versions(owner, row['source_id'])[0]
    assert version['original_present'] and version['state'] == 'failed'
    path, _ = service.original(owner, row['id'])
    assert path.read_bytes() == stream.getvalue()
    with service.database.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'), {'id': row['id']}).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM c0_jobs WHERE handler='source.cleanup' AND payload->>'version_id'=:id"), {'id': str(row['id'])}).scalar_one() == 0
