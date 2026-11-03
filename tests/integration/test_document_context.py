# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import os
from uuid import uuid4
import pytest
from czero_core.current_content import ContentSuperseded
from czero_core.documents import DocumentService
from czero_core.extraction import ExtractionError
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool
from czero_core.identity import PermissionDenied
from test_access import access
from test_sources import sources,upload,execute

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')

BODY=('# Prerequisite\n\nUse isolation key K17 before starting café 東京.\n\n'+
    '# Background\n\n'+'Unrelated historical housing details.\n\n'*2200+
    '# Procedure\n\nRead [the prerequisite](#prerequisite), then turn the switch clockwise.\n')


def ready(sources,*,queued=True,body=BODY):
    service,owner,_,_=sources
    version=upload(sources,body.encode(),media_type='text/markdown',retain_original=True)
    if queued:
        queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True)
        queue.enqueue(owner,version['id'],expected_generation=1); ExtractionPool(queue).tick()
    else: execute(sources,'source.extract',version['id'])
    return DocumentService(service.database,service.access),owner,version


@pytest.mark.parametrize('queued',[True,False])
def test_exact_outline_bundle_references_and_source_citations(sources,queued):
    service,owner,version=ready(sources,queued=queued)
    outline=service.outline(owner,version['source_id'])
    assert outline['revision_id']==str(version['id']) and outline['total_sections']==4
    assert outline['structure_origin']==('persisted' if queued else 'derived_current_body')
    reference=service.references(owner,version['source_id'],revision_id=version['id'],reference_ids=['r0'])
    assert reference['references'][0]['resolved'] and reference['references'][0]['section']=='s1'
    bundle=service.context_bundle(owner,[{'logical_document_id':str(version['source_id']),'revision_id':str(version['id']),
        'selection_ids':['s3'],'reference_ids':['r0']}])
    assert not bundle['complete_document'] and bundle['no_fallback'] and not bundle['omitted']
    assert [row['selection_id'] for row in bundle['sections']]==['s3','s1']
    assert 'K17' in bundle['sections'][1]['body'] and 'clockwise' in bundle['sections'][0]['body']
    encoded=json.dumps(bundle,ensure_ascii=False,separators=(',', ':')).encode()
    assert bundle['response_bytes']==len(encoded)<len(BODY.encode())//5
    assert bundle['estimated_tokens']==(len(encoded)+2)//3
    for selected in bundle['sections']:
        assert selected['body']==BODY[selected['start_offset']:selected['end_offset']]
        assert selected['content_hash']==hashlib.sha256(selected['body'].encode()).hexdigest()
        for citation in selected['citations']:
            actual=sources[0].citation(owner,citation['chunk_id'])
            assert actual['start_offset']==citation['start_offset'] and actual['content_hash']==citation['content_hash']
            assert actual['body']==BODY[citation['document_start_offset']:citation['document_end_offset']]


def test_oversized_selection_is_omitted_without_truncation_or_fallback(sources):
    service,owner,version=ready(sources)
    value=service.sections(owner,version['source_id'],revision_id=version['id'],selection_ids=['s2'],max_bytes=4096)
    assert value['sections']==[] and value['omitted'][0]['selection_id']=='s2'
    assert value['omitted'][0]['reason']=='too_large' and value['response_bytes']<=4096
    blocks=service.outline(owner,version['source_id'],view='blocks',limit=2)
    assert blocks['sections']==[] and blocks['blocks'] and blocks['next_offset']==2
    selected=service.sections(owner,version['source_id'],revision_id=version['id'],selection_ids=[blocks['blocks'][0]['id']])
    assert selected['sections'][0]['kind']=='heading'


def test_current_generation_and_selected_space_are_required(sources):
    service,owner,version=ready(sources)
    changed=upload(sources,b'# Current replacement\n\nNew text.',media_type='text/markdown',source_id=version['source_id'],expected_revision=1)
    execute(sources,'source.extract',changed['id'])
    with pytest.raises(ContentSuperseded): service.sections(owner,version['source_id'],revision_id=version['id'],selection_ids=['s1'])
    with pytest.raises(PermissionDenied): service.in_space(uuid4()).outline(owner,version['source_id'])


@pytest.mark.parametrize('plan',[
    [],[{'logical_document_id':'invalid'}],
    [{'logical_document_id':str(uuid4()),'revision_id':str(uuid4()),'selection_ids':['s0'],'reference_ids':[],'url':'https://example.org'}],
    [{'logical_document_id':str(uuid4()),'revision_id':str(uuid4()),'selection_ids':['s0','s0'],'reference_ids':[]}],
])
def test_closed_plans_do_not_trigger_fetches_or_fallback(sources,plan):
    service,owner,version=ready(sources,body='# Small\n\nText.')
    with pytest.raises(ValueError): service.context_bundle(owner,plan)


def test_concurrent_publication_keeps_one_exact_snapshot_then_returns_410(sources,monkeypatch):
    import czero_core.document_context as module
    service,owner,version=ready(sources)
    original=module._selection; published=[]
    def raced(*args,**kwargs):
        if not published:
            changed=upload(sources,b'# Replacement\n\nNew current body.',media_type='text/markdown',
                source_id=version['source_id'],expected_revision=1)
            execute(sources,'source.extract',changed['id']); published.append(changed['id'])
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'_selection',raced)
    result=service.sections(owner,version['source_id'],revision_id=version['id'],selection_ids=['s3','s1'])
    assert all(row['revision_id']==str(version['id']) for row in result['sections'])
    assert result['sections'][0]['body']==BODY[BODY.index('# Procedure'):]
    with pytest.raises(ContentSuperseded): service.sections(owner,version['source_id'],revision_id=version['id'],selection_ids=['s1'])


def test_selected_ocr_page_exposes_only_its_observed_provenance(sources):
    from ocr_original import PHRASE,scanned_original
    source,owner,_,_=sources
    version=upload(sources,scanned_original(),media_type='application/pdf',retain_original=True)
    queue=ExtractionQueue(source.database,source.access,source.originals,enabled=True,ocr_language='eng')
    queue.enqueue(owner,version['id'],expected_generation=1); ExtractionPool(queue).tick()
    reader=DocumentService(source.database,source.access)
    outline=reader.outline(owner,version['source_id'],view='blocks')
    assert outline['has_ocr'] and outline['blocks'][0]['kind']=='page'
    selected=reader.sections(owner,version['source_id'],revision_id=version['id'],selection_ids=['b0'])['sections'][0]
    assert selected['body']==PHRASE and selected['extraction']['ocr_pages'][0]['words']==4
    assert 0<=selected['extraction']['ocr_pages'][0]['confidence']<=100
