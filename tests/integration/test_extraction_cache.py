# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from collections import Counter
from dataclasses import replace
import os
from uuid import uuid4
import pytest
from sqlalchemy import text
from czero_core.current_content import ContentSuperseded
from czero_core.extraction import extract_isolated
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool
from test_access import access
from test_sources import sources,upload
from test_spaces import spaces
from test_pdf_unit_pipeline import FIXTURES

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def queued(sources,body=b'Current cache evidence caf\xc3\xa9',*,queue=None,**kwargs):
    service,owner,_,_=sources
    version=upload(sources,body,retain_original=True,**kwargs)
    queue=queue or ExtractionQueue(service.database,service.access,service.originals,enabled=True)
    return queue,owner,version,queue.enqueue(owner,version['id'],expected_generation=1)


def test_current_pdf_outputs_reuse_exact_page_slices_including_blank_pages(sources,monkeypatch):
    import czero_core.extraction_queue as module
    original=(FIXTURES/'blank-pages.pdf').read_bytes()
    queue,owner,first,run=queued(sources,original,media_type='application/pdf')
    ExtractionPool(queue).tick()
    _,_,second,later=queued(sources,original,media_type='application/pdf',title='Duplicate current original')
    monkeypatch.setattr(module,'extract_page_isolated',lambda *args:pytest.fail('Eligible page was reparsed'))
    assert ExtractionPool(queue).tick()['processed']==5
    left=sources[0].document(owner,first['id']); right=sources[0].document(owner,second['id'])
    assert left['body']==right['body'] and left['locations']==right['locations'] and left['id']!=right['id']
    status=queue.status(owner,later['id'])
    assert status['cache_hits']==5 and status['cache_misses']==0 and status['reused_bytes']==len(right['body'].replace('\n\n','').encode())


def test_current_body_without_structure_reuses_exact_text_units(sources,monkeypatch):
    import czero_core.extraction_queue as module
    original=(FIXTURES/'multipart.md').read_bytes()
    queue,owner,first,run=queued(sources,original,media_type='text/markdown')
    ExtractionPool(queue).tick()
    _,_,second,later=queued(sources,original,media_type='text/markdown',title='Current unstructured duplicate')
    monkeypatch.setattr(module,'extract_unit_isolated',lambda *args:pytest.fail('Eligible current text was reparsed'))
    assert ExtractionPool(queue).tick()['processed']==run['expected_units']
    service=sources[0]
    left=service.document(owner,first['id'],include_derivatives=True)
    right=service.document(owner,second['id'],include_derivatives=True)
    assert left['body']==right['body'] and left['locations']==right['locations'] and left['id']!=right['id']
    assert left['structure'] is right['structure'] is None
    assert left['chunking_profile']==right['chunking_profile']=='fixed-v1'
    status=queue.status(owner,later['id'])
    assert status['cache_hits']==run['expected_units'] and status['cache_misses']==0


def test_live_staging_reuse_is_private_and_duplicate_completion_does_not_count_twice(sources):
    queue,owner,first,run=queued(sources)
    claim=queue.claim(); evidence=extract_isolated(queue.originals.check(claim.original),'text/plain')
    assert queue.complete(claim,evidence)
    _,_,second,later=queued(sources,title='Second private original')
    target=queue.claim(); cached=queue.cached(target)
    assert cached is not None and sources[0].search(owner,'cache')==[]
    assert queue.complete(target,cached.evidence,reused=cached)
    assert queue.complete(target,cached.evidence,reused=cached)
    assert queue.status(owner,later['id'])['cache_hits']==1
    assert queue.publish(later['id']) and sources[0].document(owner,second['id'])['body']==evidence.text


def test_retiring_cache_owner_between_lookup_and_commit_forces_recomputation(sources):
    queue,owner,first,run=queued(sources)
    ExtractionPool(queue).tick()
    _,_,second,later=queued(sources,title='Race target')
    target=queue.claim(); cached=queue.cached(target); assert cached is not None
    changed=upload(sources,b'Replacement B',source_id=first['source_id'],expected_revision=1)
    from test_sources import execute
    execute(sources,'source.extract',changed['id'])
    assert not queue.complete(target,cached.evidence,reused=cached)
    assert queue.complete(target,extract_isolated(queue.originals.check(target.original),'text/plain'))
    assert queue.publish(later['id']) and queue.status(owner,later['id'])['cache_hits']==0
    assert queue.status(owner,later['id'])['cache_misses']==1


def test_profiles_cold_setting_and_corrupt_current_slice_do_not_reuse(sources):
    service,owner,_,_=sources
    queue,_,first,run=queued(sources); ExtractionPool(queue).tick()
    fixed=ExtractionQueue(service.database,service.access,service.originals,enabled=True,chunking_profile='fixed-v1')
    _,_,_,later=queued(sources,queue=fixed,title='Different profile')
    target=fixed.claim(); assert fixed.cached(target) is None
    assert fixed.cached(replace(target,profile={})) is None
    assert fixed.fail(target,'invalid_file')
    _,_,_,corrupt=queued(sources,title='Corruption target')
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_documents SET body='Damaged cache evidence' WHERE version_id=:id"),{'id':first['id']})
    target=queue.claim(); assert queue.cached(target) is None
    cold=ExtractionQueue(service.database,service.access,service.originals,enabled=True,cache_enabled=False)
    assert cold.cached(target) is None


def test_a_to_b_to_a_has_no_retired_cache_and_fresh_exact_ids(sources):
    queue,owner,first,run=queued(sources); ExtractionPool(queue).tick()
    previous=sources[0].document(owner,first['id']); old=sources[0].chunks(owner,previous['id'])[0]['id']
    _,_,second,_=queued(sources,b'Current B evidence',source_id=first['source_id'],expected_revision=1)
    ExtractionPool(queue).tick()
    _,_,third,later=queued(sources,source_id=first['source_id'],expected_revision=2)
    ExtractionPool(queue).tick()
    assert third['id']!=first['id'] and queue.status(owner,later['id'])['cache_hits']==0
    with pytest.raises(ContentSuperseded): sources[0].citation(owner,old)
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':first['id']}).scalar_one()==0


def test_identical_originals_never_cross_protected_spaces(spaces,sources):
    service,owner,_,created=sources
    queue,_,_,_=queued(sources); ExtractionPool(queue).tick()
    private=spaces[0].create(owner,'Cache isolation '+uuid4().hex,idempotency_key=uuid4().hex)
    spaces[2].append(private['id'])
    scoped=service.in_space(private['id'])
    version=scoped.ingest(owner,__import__('io').BytesIO(b'Current cache evidence caf\xc3\xa9'),title='Protected',filename='protected.txt',media_type='text/plain')
    created.append(version['source_id'])
    bound=queue.in_space(private['id']); run=bound.enqueue(owner,version['id'],expected_generation=1)
    claim=queue.claim(); assert bound.cached(claim) is None
    assert bound.complete(claim,extract_isolated(queue.originals.check(claim.original),'text/plain'))
    assert bound.publish(run['id']) and bound.status(owner,run['id'])['cache_hits']==0


@pytest.mark.parametrize('expired',[True,False])
def test_expired_or_revoked_staging_owner_cannot_supply_reuse(sources,expired):
    from czero_core.identity import Role
    from test_access import record_unadmitted,account_named,identity
    service,owner,_,_=sources
    key=uuid4(); record_unadmitted(service.access,key,'cache-editor')
    account=account_named(service.access,owner,'cache-editor')['id']
    service.access.set_role(owner,account,Role.EDITOR)
    editor=service.access.resolve(identity(service.access,key,'cache-editor'))
    first=upload(sources,retain_original=True)
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True)
    run=queue.enqueue(editor,first['id'],expected_generation=1)
    claim=queue.claim(); assert queue.complete(claim,extract_isolated(queue.originals.check(claim.original),'text/plain'))
    if expired:
        with queue.database.engine.begin() as c:
            c.execute(text("UPDATE c0_extraction_runs SET expires_at=now()-interval '1 second' WHERE id=:id"),{'id':run['id']})
    else: service.access.set_role(owner,account,Role.READER)
    version=upload(sources,title='Fresh target',retain_original=True)
    later=queue.enqueue(owner,version['id'],expected_generation=1)
    target=queue.claim(); assert queue.cached(target) is None
    assert queue.complete(target,extract_isolated(queue.originals.check(target.original),'text/plain'))
    assert queue.publish(later['id']) and queue.status(owner,later['id'])['cache_hits']==0


def test_ocr_reuse_keeps_provenance_and_language_change_forces_actual_recompute(sources,monkeypatch):
    from ocr_original import PHRASE,scanned_original
    import czero_core.extraction_queue as module
    service,owner,_,_=sources; original=scanned_original()
    english=ExtractionQueue(service.database,service.access,service.originals,enabled=True,ocr_language='eng')
    _,_,first,_=queued(sources,original,queue=english,media_type='application/pdf')
    ExtractionPool(english).tick()
    actual=module.ocr_extract; calls=[]
    def observe(path,page,profile):
        calls.append(profile['language']); return actual(path,page,profile)
    monkeypatch.setattr(module,'ocr_extract',observe)
    _,_,second,run=queued(sources,original,queue=english,media_type='application/pdf',title='Warm OCR')
    ExtractionPool(english).tick()
    assert calls==[] and english.status(owner,run['id'])['cache_hits']==1
    left=service.document(owner,first['id'],include_derivatives=True)
    right=service.document(owner,second['id'],include_derivatives=True)
    assert left['structure']['ocr']==right['structure']['ocr'] and right['body']==PHRASE
    bilingual=ExtractionQueue(service.database,service.access,service.originals,enabled=True,ocr_language='eng+ita')
    _,_,third,later=queued(sources,original,queue=bilingual,media_type='application/pdf',title='Changed OCR language')
    ExtractionPool(bilingual).tick()
    assert calls==['eng+ita'] and bilingual.status(owner,later['id'])['cache_hits']==0
    assert service.document(owner,third['id'])['body']==PHRASE
