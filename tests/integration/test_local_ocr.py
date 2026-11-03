# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from collections import Counter
from io import BytesIO
import os
import pytest
from sqlalchemy import text
from czero_core.extraction import ExtractionError
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool
from czero_core.local_ocr import preflight,extract_unit
from czero_core.pdf_units import extract_page_isolated
from ocr_original import PHRASE,scanned_original
from test_access import access
from test_sources import sources,upload

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_real_scan_requires_opt_in_and_preserves_observed_provenance(sources,tmp_path):
    original=scanned_original(); path=tmp_path/'scan.pdf'; path.write_bytes(original)
    with pytest.raises(ExtractionError,match='unsupported_scan'): extract_page_isolated(path,1)
    parsed=extract_unit(path,1,preflight())
    assert parsed.evidence.text==PHRASE and 0<=parsed.provenance['confidence']<=100
    assert parsed.provenance['words']==4
    service,owner,_,_=sources
    version=upload(sources,original,media_type='application/pdf',retain_original=True)
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True,ocr_language='eng')
    run=queue.enqueue(owner,version['id'],expected_generation=1)
    assert ExtractionPool(queue).tick()['processed']==1
    document=service.document(owner,version['id'],include_derivatives=True)
    assert document['body']==PHRASE and document['structure']['ocr']['pages'][0]==parsed.provenance
    with queue.database.engine.connect() as c:
        row=c.execute(text('SELECT body,provenance,provenance_sha256 FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).mappings().one()
        assert row['body'] is row['provenance'] is None and len(row['provenance_sha256'])==64


def test_disabled_scan_fails_explicitly_without_invoking_local_adapter(sources,monkeypatch):
    import czero_core.extraction_queue as module
    service,owner,_,_=sources
    version=upload(sources,scanned_original(),media_type='application/pdf')
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True)
    run=queue.enqueue(owner,version['id'],expected_generation=1)
    def forbidden(*args): raise AssertionError('OCR must not run')
    monkeypatch.setattr(module,'ocr_extract',forbidden)
    assert ExtractionPool(queue).tick()['processed']==1
    assert queue.status(owner,run['id'])['error_code']=='unsupported_scan'
    assert service.search(owner,'SCANNED')==[]


def test_disabling_ocr_stops_pending_scan_work(sources,monkeypatch):
    import czero_core.extraction_queue as module
    service,owner,_,_=sources
    version=upload(sources,scanned_original(),media_type='application/pdf')
    enabled=ExtractionQueue(service.database,service.access,service.originals,enabled=True,ocr_language='eng')
    run=enabled.enqueue(owner,version['id'],expected_generation=1)
    disabled=ExtractionQueue(service.database,service.access,service.originals,enabled=True)
    monkeypatch.setattr(module,'ocr_extract',lambda *args:pytest.fail('Disabled OCR executed'))
    assert ExtractionPool(disabled).tick()['processed']==1
    assert disabled.status(owner,run['id'])['error_code']=='unsupported_scan'


def test_ocr_retry_does_not_repeat_readable_sibling(sources,monkeypatch):
    from pypdf import PdfReader,PdfWriter
    from test_pdf_unit_pipeline import FIXTURES
    writer=PdfWriter(); writer.add_page(PdfReader(FIXTURES/'readable-100.pdf').pages[0])
    writer.add_page(PdfReader(BytesIO(scanned_original())).pages[0]); output=BytesIO(); writer.write(output)
    service,owner,_,_=sources
    version=upload(sources,output.getvalue(),media_type='application/pdf',retain_original=True)
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True,ocr_language='eng')
    run=queue.enqueue(owner,version['id'],expected_generation=1)
    import czero_core.extraction_queue as module
    calls=Counter(); actual=module.ocr_extract
    def fail_once(path,page,profile):
        calls[page]+=1
        if calls[page]==1: raise ExtractionError('parser_timeout')
        return actual(path,page,profile)
    monkeypatch.setattr(module,'ocr_extract',fail_once)
    ExtractionPool(queue).tick()
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET available_at=now() WHERE run_id=:id AND state='retry_wait'"),{'id':run['id']})
    ExtractionPool(queue).tick()
    assert queue.status(owner,run['id'])['state']=='ready'
    assert calls=={2:2}
    with queue.database.engine.connect() as c:
        assert dict(c.execute(text('SELECT ordinal,lifetime_attempts FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).all())=={1:1,2:2}


def test_ocr_timeout_kills_real_descendants_and_drops_credentials(monkeypatch,tmp_path):
    import sys
    import time
    import czero_core.local_ocr as module
    profile=preflight(); actual=module.subprocess.Popen; saved=tmp_path/'child-pid'
    code=('import subprocess,sys,time;from pathlib import Path;'
        'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
        f'Path({str(saved)!r}).write_text(str(p.pid));time.sleep(60)')
    monkeypatch.setenv('CZERO_PRIVATE_TEST','private-test-canary')
    def launch(command,**kwargs):
        assert kwargs['start_new_session'] is True
        assert not any(key.startswith('CZERO_') for key in kwargs['env'])
        return actual([sys.executable,'-c',code],**kwargs)
    monkeypatch.setattr(module.subprocess,'Popen',launch)
    monkeypatch.setattr(module,'PARENT_SECONDS',1)
    with pytest.raises(ExtractionError,match='parser_timeout'): extract_unit(tmp_path/'unused.pdf',1,profile)
    descendant=int(saved.read_text())
    for _ in range(20):
        status=__import__('pathlib').Path('/proc')/str(descendant)/'stat'
        if not status.exists() or status.read_text().split()[2]=='Z': break
        time.sleep(.05)
    else: pytest.fail('OCR descendant survived its parent deadline')
