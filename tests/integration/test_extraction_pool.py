# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real concurrent parsers, process death and independent ordinary work."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import os
import subprocess
import sys
from threading import Barrier, Lock

import pytest
from sqlalchemy import text

from czero_core.extraction import Extracted
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool
from czero_core.worker import Worker
from test_access import access
from test_sources import sources,upload
from test_job_services import service as job_service
from test_pdf_unit_pipeline import pdf,FIXTURES
from test_spaces import spaces

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='separate disposable PostgreSQL required')


def test_real_parallel_parsers_leave_ordinary_worker_available_and_rotate_documents(sources,job_service,monkeypatch):
    import czero_core.extraction_queue as module
    queue,owner,_,first=pdf(sources,'blank-pages.pdf',title='Pool first')
    _,_,_,second=pdf(sources,'blank-pages.pdf',title='Pool second')
    jobs,_=job_service; health=jobs.enqueue(owner,'health',{},'pool-health')
    barrier=Barrier(2); lock=Lock(); observed=[]; actual=module.extract_page_isolated
    def parse(path,page):
        with lock:
            ordinal=len(observed); observed.append((str(path),page))
        if ordinal<2:
            barrier.wait(timeout=10)
            assert queue.metrics()['active_units']==2
            if ordinal==0:
                code=("import os; from czero_core.database import Database; from czero_core.jobs import default_registry; "
                    "from czero_core.worker import Worker; from czero_core.sources import OriginalStore,register_source_handlers; "
                    "d=Database(os.environ['CZERO_TEST_DATABASE_URL']); r=default_registry(); "
                    f"register_source_handlers(r,d,OriginalStore({str(queue.originals.root)!r})); assert Worker(d,r).tick()==1; d.close()")
                ordinary=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=10)
                assert ordinary.returncode==0
            barrier.wait(timeout=10)
        return actual(path,page)
    monkeypatch.setattr(module,'extract_page_isolated',parse)
    result=ExtractionPool(queue).tick()
    assert result['processed']==10 and result['workers']==2
    assert jobs.get_job(owner,health['id'])['state']=='succeeded'
    assert observed[0][0]!=observed[1][0]
    assert queue.status(owner,first['id'])['state']==queue.status(owner,second['id'])['state']=='ready'
    assert all(count==1 for count in Counter(observed).values())
    assert not any(word in str(result) for word in ('title','path','token','body','source_id'))


def test_overlapping_claimants_obey_instance_document_and_space_budgets(sources):
    queue,owner,_,first=pdf(sources,'blank-pages.pdf',title='Budget first')
    _,_,_,second=pdf(sources,'blank-pages.pdf',title='Budget second')
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims=list(pool.map(lambda _:queue.claim(),range(4)))
    owned=[claim for claim in claims if claim]
    assert len(owned)==2 and {claim.run_id for claim in owned}=={first['id'],second['id']}
    assert queue.metrics()['active_units']==2 and len({claim.unit_id for claim in owned})==2


def test_queue_admission_keeps_legacy_job_intact_when_capacity_is_full(sources):
    service,owner,_,_=sources
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True,max_queued_units=200)
    for index in range(3):
        version=upload(sources,(FIXTURES/'readable-100.pdf').read_bytes(),title='Queue '+str(index),media_type='application/pdf')
        if index<2: queue.enqueue(owner,version['id'],expected_generation=1)
        else:
            with pytest.raises(ValueError,match='extraction_queue_full'):
                queue.enqueue(owner,version['id'],expected_generation=1)
            with queue.database.engine.connect() as c:
                assert c.execute(text('SELECT state FROM c0_jobs WHERE id=:id'),{'id':version['job_id']}).scalar_one()=='queued'
    assert queue.metrics()['queue_depth']==200


def test_staging_backpressure_never_exceeds_aggregate_byte_budget(sources):
    service,owner,_,_=sources
    body='é'*600000
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True,max_staging_bytes=2097152)
    runs=[]
    for index in range(2):
        version=upload(sources,body.encode(),title='Bytes '+str(index),retain_original=True)
        runs.append(queue.enqueue(owner,version['id'],expected_generation=1))
    first=queue.claim(); second=queue.claim()
    result=Extracted(body,[{'kind':'body','index':1,'start':0,'end':len(body)}])
    assert queue.complete(first,result)
    assert not queue.complete(second,result)
    assert queue.status(owner,second.run_id)['error_code']=='resource_limit'
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT sum(result_bytes) FROM c0_extraction_runs')).scalar_one()<=2097152


def child_configuration(queue):
    return ("import os; from uuid import UUID; from czero_core.database import Database; "
        "from czero_core.access import AccessService; from czero_core.sources import OriginalStore; "
        "from czero_core.extraction_queue import ExtractionQueue,ExtractionPool; "
        "d=Database(os.environ['CZERO_TEST_DATABASE_URL']); "
        f"q=ExtractionQueue(d,AccessService(d,{queue.access.issuer!r},UUID('{queue.access.owner_account_key}')),")+f"OriginalStore({str(queue.originals.root)!r}),enabled=True); "


def test_killed_pool_preserves_completed_siblings_and_reclaims_only_expired_units(sources):
    queue,owner,_,run=pdf(sources,'blank-pages.pdf')
    from czero_core.pdf_units import extract_page_isolated
    first=queue.claim(); assert queue.complete(first,extract_page_isolated(queue.originals.check(first.original),first.ordinal))
    code=child_configuration(queue)+"""
import signal
from threading import Barrier
import czero_core.extraction_queue as module
barrier=Barrier(2)
def die(path,page):
    barrier.wait(timeout=10)
    os.kill(os.getpid(),signal.SIGKILL)
module.extract_page_isolated=die
ExtractionPool(q).tick()
"""
    killed=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=15)
    assert killed.returncode==-9
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET lease_deadline=now()-interval '1 second' WHERE run_id=:id AND state='leased'"),{'id':run['id']})
    assert queue.claim() is None and queue.claim() is None
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_extraction_units SET available_at=now() WHERE run_id=:id AND state='retry_wait'"),{'id':run['id']})
    result=ExtractionPool(queue).tick()
    assert result['processed']==4 and queue.status(owner,run['id'])['state']=='ready'
    with queue.database.engine.connect() as c:
        attempts=dict(c.execute(text('SELECT ordinal,lifetime_attempts FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).all())
    assert attempts=={1:1,2:2,3:2,4:1,5:1}


def test_sigterm_finishes_claimed_attempts_and_admits_no_more_work(sources):
    import json
    queue,owner,_,run=pdf(sources,'blank-pages.pdf')
    code="""
import os,signal,sys
from threading import Barrier
import czero_core.extraction_queue as module
from czero_app.extraction_worker import main
barrier=Barrier(2); actual=module.extract_page_isolated
def interrupted(path,page):
    if barrier.wait(timeout=10)==0: os.kill(os.getpid(),signal.SIGTERM)
    return actual(path,page)
module.extract_page_isolated=interrupted
sys.exit(main())
"""
    environment={**os.environ,'CZERO_EXTRACTION_UNITS':'1','CZERO_EXTRACTION_WORKERS':'2',
        'CZERO_DATABASE_URL':queue.database.engine.url.render_as_string(hide_password=False),
        'CZERO_OIDC_ISSUER':queue.access.issuer,'CZERO_OWNER_LDAP_UUID':str(queue.access.owner_account_key),
        'CZERO_SOURCE_DIR':str(queue.originals.root)}
    child=subprocess.run([sys.executable,'-c',code],env=environment,capture_output=True,text=True,timeout=15)
    assert child.returncode==0 and json.loads(child.stdout)['processed']==2
    assert queue.status(owner,run['id'])['succeeded']==2
    assert ExtractionPool(queue).tick()['processed']==3
    assert queue.status(owner,run['id'])['state']=='ready'


@pytest.mark.parametrize('workers',[2,4])
def test_native_fixture_exercises_real_core_before_systemd_acceptance(spaces,sources,monkeypatch,workers):
    import importlib.util
    import json
    from pathlib import Path
    from uuid import UUID
    path=Path(__file__).resolve().parents[1]/'extraction_pool_fixture.py'
    spec=importlib.util.spec_from_file_location('disposable_pool_fixture',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    from ocr_original import PHRASE,scanned_original
    module.PHRASE=PHRASE; module.scanned_original=scanned_original
    service,owner,_,created=sources
    monkeypatch.setenv('CZERO_DISPOSABLE_TEST','1')
    monkeypatch.setenv('CZERO_DATABASE_URL',service.database.engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv('CZERO_OIDC_ISSUER',service.access.issuer)
    monkeypatch.setenv('CZERO_OWNER_LDAP_UUID',str(service.access.owner_account_key))
    monkeypatch.setattr(module,'OriginalStore',lambda _:service.originals)
    module.main('seed',workers)
    value=json.loads((service.originals.root/('.c0-extraction-acceptance-'+str(workers)+'.json')).read_text())
    spaces[2].append(value['space'])
    with service.database.engine.connect() as c:
        source=c.execute(text('SELECT source_id FROM c0_source_versions WHERE id=:id'),{'id':UUID(value['version'])}).scalar_one()
    created.append(source)
    queue=ExtractionQueue(service.database,service.access,service.originals,enabled=True,
        instance_workers=workers,document_workers=workers,space_workers=workers,ocr_language='eng')
    assert ExtractionPool(queue,workers=workers).tick()['processed']==9
    module.main('verify',workers)
