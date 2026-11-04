# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import os
from uuid import uuid4
import pytest
from sqlalchemy import text
from czero_core.current_content import ContentSuperseded
from czero_core.extraction_queue import ExtractionPool
from czero_core.identity import PermissionDenied,Role
from czero_core.sources import SourceConflict
from test_access import access
from test_sources import sources,upload,execute
from test_spaces import spaces,member
from test_pdf_unit_pipeline import pdf

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_progress_diagnostics_are_bounded_metadata_and_page_ordered(sources):
    q,owner,v,run=pdf(sources)
    assert q.progress(owner,v['source_id'])['state']=='queued'
    claim=q.claim()
    progress=q.progress(owner,v['source_id'])
    assert progress['state']=='processing' and progress['run']['completed']==0
    detail=q.units(owner,run['id'],limit=2,offset=35)
    assert [u['ordinal'] for u in detail['units']]==[36,37]
    assert detail['units'][1]['locator']=={'kind':'page','first':37,'last':37}
    assert not {'body','locations','result_sha256','profile','lease_token'} & detail['units'][0].keys()
    assert detail['parser']['partitioner']=='pdf-page-v1'
    assert q.runs(owner,limit=1)[0]['id']==run['id']
    for kwargs in ({'limit':101},{'offset':-1},{'limit':True}):
        with pytest.raises(ValueError):q.units(owner,run['id'],**kwargs)
    q.fail(claim,'invalid_file')
    assert q.progress(owner,v['source_id'])['state']=='failed'


def test_editor_can_cancel_with_revision_and_reader_cannot_inspect_units(spaces,sources):
    q,owner,v,run=pdf(sources)
    reader=member(spaces,Role.READER)
    assert q.progress(reader,v['source_id'])['run']['expected_units']==100
    with pytest.raises(PermissionDenied):q.units(reader,run['id'])
    with pytest.raises(PermissionDenied):q.cancel(reader,run['id'],expected_revision=1)
    editor=member(spaces,Role.EDITOR)
    with pytest.raises(SourceConflict):q.cancel(editor,run['id'],expected_revision=99)
    cancelled=q.cancel(editor,run['id'],expected_revision=1)
    assert cancelled['error_code']=='cancelled'
    assert q.cancel(editor,run['id'],expected_revision=1)==cancelled
    assert q.progress(reader,v['source_id'])['state']=='cancelled'
    assert q.claim() is None
    sources[0].access.set_role(owner,editor.user_id,None)
    with pytest.raises(PermissionDenied):q.cancel(editor,run['id'],expected_revision=1)


def test_protected_status_does_not_fall_back(spaces,sources):
    from czero_core.extraction_queue import ExtractionQueue
    from czero_core.sources import SourceNotFound
    service,owner,_,created=sources
    private=spaces[0].create(owner,'Progress '+uuid4().hex,idempotency_key=uuid4().hex)
    spaces[2].append(private['id'])
    selected=service.in_space(private['id'])
    from io import BytesIO
    v=selected.ingest(owner,BytesIO(b'Private progress'),title='Private',filename='private.txt',media_type='text/plain')
    created.append(v['source_id'])
    q=ExtractionQueue(service.database,service.access,service.originals,enabled=True)
    run=q.in_space(private['id']).enqueue(owner,v['id'],expected_generation=1)
    with pytest.raises(SourceNotFound):q.progress(owner,v['source_id'])
    reader=member(spaces,Role.READER)
    with pytest.raises(PermissionDenied):q.in_space(private['id']).progress(reader,v['source_id'])
    with pytest.raises(PermissionDenied):q.in_space(private['id']).units(reader,run['id'])


def test_expired_staging_requires_full_restart(sources):
    q,owner,v,run=pdf(sources,'blank-pages.pdf')
    with q.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_runs SET expires_at=clock_timestamp()-interval '1 second' WHERE id=:id"),{'id':run['id']})
    assert q.progress(owner,v['source_id'])['error_code']=='staging_expired'
    with pytest.raises(ValueError,match='staging_expired'):q.retry_failed(owner,run['id'],expected_revision=1,idempotency_key=uuid4().hex)
    q.cleanup()


def test_ready_counts_remain_complete_after_staging_is_erased_and_cancel_is_rejected(sources):
    q,owner,v,run=pdf(sources,'blank-pages.pdf')
    ExtractionPool(q).tick()
    assert q.progress(owner,v['source_id'])['run']['completed']==5
    with pytest.raises(SourceConflict):q.cancel(owner,run['id'],expected_revision=q.status(owner,run['id'])['revision'])


def test_explicit_reindex_keeps_current_until_new_publication_and_retires_exact_evidence(sources):
    service,owner,_,_=sources
    v=upload(sources,b'# Original\n\nRetained reindex evidence',media_type='text/markdown',retain_original=True)
    execute(sources,'source.extract',v['id'])
    before=service.document(owner,v['id']); old=service.chunks(owner,before['id'])[0]['id']
    key=uuid4().hex
    next_version=service.reindex(owner,v['source_id'],expected_revision=1,idempotency_key=key)
    assert next_version['id']!=str(v['id']) and next_version['number']==2
    assert service.reindex(owner,v['source_id'],expected_revision=1,idempotency_key=key)==next_version
    assert service.citation(owner,old)['body']
    execute(sources,'source.extract',next_version['id'])
    after=service.document(owner,next_version['id'])
    assert after['body']==before['body'] and after['id']!=before['id']
    with pytest.raises(ContentSuperseded):service.citation(owner,old)
    with pytest.raises(ContentSuperseded):service.document(owner,v['id'])
    with pytest.raises(SourceConflict):service.reindex(owner,v['source_id'],expected_revision=1,idempotency_key=uuid4().hex)


def test_reindex_requires_actual_retained_original_and_does_not_recreate_text(sources):
    service,owner,_,_=sources
    v=upload(sources)
    execute(sources,'source.extract',v['id']);execute(sources,'source.cleanup',v['id'])
    with pytest.raises(ValueError,match='original_unavailable'):
        service.reindex(owner,v['source_id'],expected_revision=1,idempotency_key=uuid4().hex)
    assert service.document(owner,v['id'])['body']
