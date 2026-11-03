# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Canonical rich/text originals and selective recovery through real parsers."""
from collections import Counter
import hashlib
from io import BytesIO
import os

import pytest
from sqlalchemy import text

from czero_core.current_content import ContentSuperseded
from czero_core.document_units import DOCX,inventory_isolated,text_blocks
from czero_core.extraction import ExtractionError,extract_isolated
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool
from test_access import access
from test_sources import sources,upload,execute
from test_pdf_unit_pipeline import FIXTURES

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='separate disposable PostgreSQL required')


def queue_version(sources,body,media,**kwargs):
    version=upload(sources,body,media_type=media,retain_original=True,**kwargs)
    service,owner,_,_=sources
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True)
    run=queue.enqueue(owner,version['id'],expected_generation=1)
    return queue,owner,version,run


@pytest.mark.parametrize('name,media',[('structured.docx',DOCX),('fenced.md','text/markdown'),('plain.txt','text/plain')])
def test_frozen_small_originals_use_one_unit_and_publish_identical_complete_body(sources,name,media):
    original=(FIXTURES/name).read_bytes()
    queue,owner,version,run=queue_version(sources,original,media)
    baseline=extract_isolated(queue.originals.check(version),media)
    assert run['expected_units']==1
    assert ExtractionPool(queue).tick()['processed']==1
    document=sources[0].document(owner,version['id'])
    assert document['body']==baseline.text and document['text_hash']==baseline.text_hash
    assert document['locations']==baseline.locations
    assert queue.status(owner,run['id'])['state']=='ready'


def large_docx():
    from docx import Document
    from docx.enum.section import WD_SECTION_START
    document=Document(); expected=[]
    for index in range(100):
        label='Paragraph '+str(index)+': '+('café 東京 source '+str(index)+' ')*50
        document.add_paragraph(label); expected.append(label)
    table=document.add_table(rows=1,cols=2)
    for cell,label in zip(table.rows[0].cells,('Asset','Ready')):
        cell.text=label; expected.append(label)
    document.sections[0].header.paragraphs[0].text='Header one'
    document.sections[0].footer.paragraphs[0].text='Footer one'
    section=document.add_section(WD_SECTION_START.NEW_PAGE)
    section.header.is_linked_to_previous=False; section.footer.is_linked_to_previous=False
    section.header.paragraphs[0].text='Header two'; section.footer.paragraphs[0].text='Footer two'
    stream=BytesIO(); document.save(stream)
    return stream.getvalue(),'\n\n'.join([*expected,'Header one','Footer one','Header two','Footer two'])


def test_docx_block_retry_preserves_headers_tables_unicode_and_successful_siblings(sources,monkeypatch):
    import czero_core.extraction_queue as module
    original,expected=large_docx()
    queue,owner,version,run=queue_version(sources,original,DOCX)
    baseline=extract_isolated(queue.originals.check(version),DOCX)
    assert baseline.text==expected and run['expected_units']>=3
    actual=module.extract_unit_isolated; calls=Counter()
    def parse(path,media,locator):
        key=locator['first']; calls[key]+=1
        evidence=actual(path,media,locator)
        if key==33 and calls[key]==1: raise ExtractionError('parser_timeout')
        return evidence
    monkeypatch.setattr(module,'extract_unit_isolated',parse)
    ExtractionPool(queue).tick()
    assert queue.status(owner,run['id'])['succeeded']==run['expected_units']-1
    assert sources[0].search(owner,'Paragraph')==[]
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET available_at=now() WHERE run_id=:id AND state='retry_wait'"),{'id':run['id']})
    ExtractionPool(queue).tick()
    document=sources[0].document(owner,version['id'])
    assert document['body']==expected and document['locations']==baseline.locations
    assert document['text_hash']==hashlib.sha256(expected.encode()).hexdigest()
    assert calls[33]==2 and all(count==1 for first,count in calls.items() if first!=33)


def markdown_body():
    return '# Prerequisite\n\n'+('Required café 東京. '*2500)+'\n\n````text\n# Fenced heading\n'+('code café. '*7000)+'\n```\n## Still fenced\n````\n\n## Procedure\n\n'+('Follow the prerequisite. '*2000)+'\n'


def test_markdown_units_never_split_fences_or_use_fenced_headings_as_boundaries(sources):
    body=markdown_body()
    original=b'\xef\xbb\xbf'+body.replace('\n','\r\n').encode()
    queue,owner,version,run=queue_version(sources,original,'text/markdown')
    spec=inventory_isolated(queue.originals.check(version),'text/markdown')
    boundaries={start for start,_ in spec['ranges']}
    assert body.index('# Fenced heading') not in boundaries and body.index('## Still fenced') not in boundaries
    assert run['expected_units']>=3
    ExtractionPool(queue).tick()
    document=sources[0].document(owner,version['id'])
    assert document['body']==body and document['text_hash']==hashlib.sha256(body.encode()).hexdigest()
    assert [entry['start'] for entry in document['locations']]==[0,body.index('## Procedure')]
    for chunk in sources[0].chunks(owner,document['id']):
        assert chunk['body']==body[chunk['start_offset']:chunk['end_offset']]
        assert sources[0].citation(owner,chunk['id'])['body']==chunk['body']


def test_whitespace_units_and_trailing_separators_are_not_dropped(sources):
    body=' '*70000+'\n\nVisible café 東京.\n\n'+'\t'*70000+'\n'
    queue,owner,version,run=queue_version(sources,body.encode(),'text/plain')
    assert run['expected_units']>=2
    ExtractionPool(queue).tick()
    document=sources[0].document(owner,version['id'])
    assert document['body']==body and document['text_hash']==hashlib.sha256(body.encode()).hexdigest()
    assert queue.status(owner,run['id'])['state']=='ready'


def test_new_original_normalizing_to_same_text_has_fresh_exact_evidence(sources):
    body=markdown_body()
    old=upload(sources,body.encode(),media_type='text/markdown',retain_original=True)
    execute(sources,'source.extract',old['id'])
    previous=sources[0].document(sources[1],old['id'])
    old_citation=sources[0].chunks(sources[1],previous['id'])[0]['id']
    changed=body.replace('\n','\r\n').encode()
    queue,owner,version,run=queue_version(sources,changed,'text/markdown',source_id=old['source_id'],expected_revision=1)
    ExtractionPool(queue).tick()
    assert version['id']!=old['id'] and sources[0].document(owner,version['id'])['body']==body
    with pytest.raises(ContentSuperseded): sources[0].citation(owner,old_citation)
    unchanged=upload(sources,changed,media_type='text/markdown',retain_original=True,source_id=old['source_id'],expected_revision=2)
    assert unchanged['id']==version['id'] and queue.status(owner,run['id'])['state']=='ready'
