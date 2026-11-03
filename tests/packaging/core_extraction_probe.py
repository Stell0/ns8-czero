# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Executed outside the checkout in each independently installed Core artifact."""
import json
import os
from io import BytesIO
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from sqlalchemy import text
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.extraction_queue import ExtractionQueue, ExtractionWorker, ExtractionPool
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.sources import OriginalStore, SourceService, register_source_handlers
from czero_core.extraction import extract_isolated

database = Database(os.environ['CZERO_DATABASE_URL'])
owner_key = uuid4()
access = AccessService(database,'https://idp.example.test/units/'+uuid4().hex,owner_key)
actor = access.resolve(VerifiedIdentity(access.issuer,'owner',str(owner_key),'owner','Owner',time.time()+300))
with tempfile.TemporaryDirectory() as directory:
    originals = OriginalStore(Path(directory)/'originals')
    registry = default_registry()
    register_source_handlers(registry,database,originals)
    sources = SourceService(database,access,registry,originals)
    version = sources.ingest(actor,BytesIO(b'Independent unit evidence'),title='Units',filename='units.txt',media_type='text/plain')
    queue = ExtractionQueue(database,access,originals,enabled=True)
    run = queue.enqueue(actor,version['id'],expected_generation=1)
    claim=queue.claim()
    assert queue.complete(claim,extract_isolated(originals.check(claim.original),claim.original['media_type']))
    assert queue.status(actor,run['id'])['state']=='assembling'
    with database.engine.connect() as connection:
        assert connection.execute(text('SELECT body FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).scalar_one()=='Independent unit evidence'
        assert connection.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':version['id']}).scalar_one()==0
    assert queue.publish(run['id']) and sources.document(actor,version['id'])['body']=='Independent unit evidence'
    sources.delete(actor,version['source_id'],expected_revision=1)
    assert queue.status(actor,run['id'])['state']=='superseded'
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject,DictionaryObject,NameObject
    writer=PdfWriter(); page=writer.add_blank_page(width=612,height=792)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 72 720 Td (Independent PDF evidence) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    original=BytesIO(); writer.write(original); original.seek(0)
    pdf=sources.ingest(actor,original,title='PDF',filename='pdf.pdf',media_type='application/pdf',retain_original=True)
    run=queue.enqueue(actor,pdf['id'],expected_generation=1)
    result=ExtractionPool(queue).tick()
    assert result['processed']==1 and result['workers']==2
    assert queue.status(actor,run['id'])['state']=='ready'
    assert queue.status(actor,run['id'])['run_ms']>0
    document=sources.document(actor,pdf['id'])
    assert document['body']=='Independent PDF evidence'
    assert sources.citation(actor,sources.chunks(actor,document['id'])[0]['id'])['body']==document['body']
    with database.engine.connect() as connection:
        assert connection.execute(text('SELECT body FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).scalar_one() is None
    from docx import Document
    word=Document(); labels=['Independent block '+str(index) for index in range(70)]
    for label in labels: word.add_paragraph(label)
    word.sections[0].header.paragraphs[0].text='Independent header'
    word.paragraphs[0].style='Heading 1'
    stream=BytesIO(); word.save(stream); stream.seek(0)
    docx=sources.ingest(actor,stream,title='Word',filename='word.docx',
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',retain_original=True)
    run=queue.enqueue(actor,docx['id'],expected_generation=1)
    assert run['expected_units']==3 and ExtractionPool(queue).tick()['processed']==3
    rich=sources.document(actor,docx['id'],include_derivatives=True)
    assert rich['body']=='\n\n'.join([*labels,'Independent header'])
    assert rich['chunking_profile']=='sections-v1' and rich['structure']['sections'][1]['heading']['start']==0
    stream.seek(0)
    duplicate=sources.ingest(actor,stream,title='Duplicate Word',filename='duplicate.docx',media_type=docx['media_type'])
    later=queue.enqueue(actor,duplicate['id'],expected_generation=1)
    assert ExtractionPool(queue).tick()['processed']==3 and queue.status(actor,later['id'])['cache_hits']==3
    assert sources.document(actor,duplicate['id'])['body']==rich['body']
    import runpy
    from czero_core.local_ocr import preflight,extract_unit
    fixture=runpy.run_path(str(Path(__file__).with_name('ocr_original.py')))
    scanned=originals.root/'synthetic-scan.pdf'; scanned.write_bytes(fixture['scanned_original']())
    assert extract_unit(scanned,1,preflight()).evidence.text==fixture['PHRASE']
database.close()
print(json.dumps({'installed_extraction_staging':True,'installed_pdf_publication':True,'installed_document_formats':True,'installed_local_ocr':True,'installed_current_cache':True}))
