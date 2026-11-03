# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from io import BytesIO
import os
import pytest
from sqlalchemy import text
from czero_core.current_content import ContentSuperseded
from czero_core.document_units import DOCX
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool
from test_access import access
from test_sources import sources,upload,execute
from test_document_unit_formats import queue_version
from test_pdf_unit_pipeline import FIXTURES

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_styled_docx_structure_is_published_atomically_and_retired_with_body(sources):
    from docx import Document
    word=Document(); word.add_heading('Preparation',0); word.add_heading('Required key',1)
    word.add_paragraph('Install café 東京 key.'); word.add_heading('Start procedure',2)
    word.add_paragraph('Turn the switch.'); word.add_table(rows=1,cols=1).cell(0,0).text='Ready'
    stream=BytesIO(); word.save(stream)
    queue,owner,version,run=queue_version(sources,stream.getvalue(),DOCX)
    ExtractionPool(queue).tick()
    document=sources[0].document(owner,version['id'],include_derivatives=True)
    structure=document['structure']
    assert document['chunking_profile']=='sections-v1'
    assert [document['body'][s['heading']['start']:s['heading']['end']] for s in structure['sections'][1:]]==['Required key','Start procedure']
    assert any(b['kind']=='table' for b in structure['blocks'])
    chunks=sources[0].chunks(owner,document['id']); old=chunks[0]['id']
    assert all(c['body']==document['body'][c['start_offset']:c['end_offset']] for c in chunks)
    replacement=upload(sources,b'New original',source_id=version['source_id'],expected_revision=1)
    execute(sources,'source.extract',replacement['id'])
    with pytest.raises(ContentSuperseded): sources[0].citation(owner,old)
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_documents WHERE id=:id'),{'id':document['id']}).scalar_one()==0


def test_legacy_index_stays_fixed_and_explicit_comparison_profile_is_bound(sources):
    body='# Setup\n\nSafety key.\n\n## Procedure\n\nTurn switch.\n'
    first=upload(sources,body.encode(),media_type='text/markdown'); execute(sources,'source.extract',first['id'])
    assert sources[0].document(sources[1],first['id'],include_derivatives=True)['structure'] is None
    version=upload(sources,(body+'Changed.\n').encode(),media_type='text/markdown')
    service,owner,_,_=sources
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True,chunking_profile='fixed-v1')
    run=queue.enqueue(owner,version['id'],expected_generation=1)
    assert ExtractionPool(queue).tick()['processed']==1
    assert service.document(owner,version['id'],include_derivatives=True)['chunking_profile']=='fixed-v1'
    with queue.database.engine.connect() as c:
        assert c.execute(text("SELECT profile->>'chunking' FROM c0_extraction_runs WHERE id=:id"),{'id':run['id']}).scalar_one()=='fixed-v1'


def test_structure_bounds_preserve_complete_legacy_compatible_markdown(sources):
    import json
    from czero_core.extraction import extract_isolated
    original=(FIXTURES/'multipart.md').read_bytes()
    queue,owner,version,run=queue_version(sources,original,'text/markdown')
    baseline=extract_isolated(queue.originals.check(version),'text/markdown')
    assert ExtractionPool(queue).tick()['processed']==run['expected_units']
    assert queue.status(owner,run['id'])['state']=='ready'
    document=sources[0].document(owner,version['id'],include_derivatives=True)
    assert document['body']==baseline.text and document['text_hash']==baseline.text_hash
    assert document['locations']==baseline.locations
    assert document['structure'] is None and document['chunking_profile']=='fixed-v1'
    expected=next(row for row in json.loads((FIXTURES/'manifest.json').read_text())['files'] if row['name']=='multipart.md')
    assert document['text_hash']==expected['text_sha256'] and document['locations']==expected['locations']
    chunks=[]
    while True:
        rows=sources[0].chunks(owner,document['id'],limit=100,offset=len(chunks))
        chunks.extend(rows)
        if len(rows)<100: break
    assert chunks[0]['start_offset']==0 and chunks[-1]['end_offset']==len(baseline.text)
    assert all(row['body']==baseline.text[row['start_offset']:row['end_offset']] for row in chunks)
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_extraction_units WHERE run_id=:id AND body IS NOT NULL'),{'id':run['id']}).scalar_one()==0


def test_structure_parser_failure_cannot_fall_back_or_replace_current(sources,monkeypatch):
    import czero_core.extraction_queue as module
    from czero_core.extraction import ExtractionError
    first=upload(sources,b'Existing complete evidence');execute(sources,'source.extract',first['id'])
    queue,owner,version,run=queue_version(sources,b'# Replacement\n\nNew evidence.','text/markdown',
        source_id=first['source_id'],expected_revision=1)
    def failed(*args):raise ExtractionError('parser_failed')
    monkeypatch.setattr(module,'build_structure',failed)
    ExtractionPool(queue).tick()
    assert queue.status(owner,run['id'])['error_code']=='parser_failed'
    assert sources[0].document(owner,first['id'])['body']=='Existing complete evidence'
    assert sources[0].get(owner,first['source_id'])['current_version_id']==first['id']
