# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Crash a result transaction, restart PostgreSQL and start a fresh real worker."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from threading import Event
import time
from uuid import uuid4
from sqlalchemy import text,event
from sqlalchemy.exc import DBAPIError
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.extraction_queue import ExtractionQueue
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.migrate import migrate_database
from czero_core.pdf_units import extract_page_isolated
from czero_core.sources import OriginalStore,SourceService,register_source_handlers
from evaluation.fixture import database_parameters,disposable_database
from benchmarks.ingestion import source_proof

ROOT=Path(__file__).resolve().parents[2]
IMAGE='docker.io/pgvector/pgvector:0.8.7-pg17-bookworm@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d'


def validate_container(info,url):
    parsed=database_parameters(url)
    if (not re.fullmatch(r'c0-ingestion-restart-[0-9]{8}(?:-[a-z0-9]+)?',info.get('Name','').lstrip('/'))
        or info.get('Config',{}).get('Labels',{}).get('io.czero.disposable-ingestion')!='true'
        or info.get('ImageName') not in (IMAGE,IMAGE.replace(':0.8.7-pg17-bookworm',''))
        or not re.fullmatch('[0-9a-f]{64}',info.get('Id',''))):
        raise ValueError('owned_disposable_database_required')
    ports=info.get('NetworkSettings',{}).get('Ports',{}).get('5432/tcp',[])
    if ports!=[{'HostIp':'127.0.0.1','HostPort':str(parsed.port or 5432)}]:
        raise ValueError('disposable_loopback_port_mismatch')
    return info['Id']


def wait_ready(database):
    deadline=time.monotonic()+30
    while True:
        try:
            with database.engine.connect() as c:c.execute(text('SELECT 1'))
            return
        except DBAPIError:
            if time.monotonic()>=deadline:raise
            time.sleep(.1)


def prove(url,container_id,private):
    database=Database(url);renewed=None
    try:
        migrate_database(database);key=uuid4()
        access=AccessService(database,'https://idp.example.test/restart-proof',key)
        owner=access.resolve(VerifiedIdentity(access.issuer,str(key),str(key),'restart-owner','Restart owner',time.time()+3600))
        originals=OriginalStore(Path(private)/'originals');registry=default_registry();register_source_handlers(registry,database,originals)
        sources=SourceService(database,access,registry,originals)
        original=(ROOT/'tests/fixtures/evidence/pipeline/blank-pages.pdf').read_bytes()
        expected=next(v for v in json.loads((ROOT/'tests/fixtures/evidence/pipeline/manifest.json').read_text())['files'] if v['name']=='blank-pages.pdf')
        version=sources.ingest(owner,BytesIO(original),title='Restart proof',filename='pages.pdf',media_type='application/pdf',retain_original=True)
        queue=ExtractionQueue(database,access,originals,enabled=True)
        run=queue.enqueue(owner,version['id'],expected_generation=1)
        first=queue.claim();assert first.ordinal==1
        assert queue.complete(first,extract_page_isolated(originals.check(first.original),1))
        interrupted=queue.claim();assert interrupted.ordinal==2
        result=extract_page_isolated(originals.check(interrupted.original),2)
        boundary,resume=Event(),Event()
        def block_result(conn,cursor,statement,parameters,context,many):
            if "UPDATE c0_extraction_units SET state='succeeded'" in statement:
                boundary.set();assert resume.wait(30),'Restart controller did not resume'
        event.listen(database.engine,'after_cursor_execute',block_result)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(queue.complete,interrupted,result)
            try:
                assert boundary.wait(10),'Result persistence boundary not reached'
                # Stable inspected ID: never a mutable production container name.
                subprocess.run(['podman','restart','--time','5',container_id],check=True,capture_output=True)
            finally:resume.set()
            try:pending.result(15)
            except DBAPIError:pass
            else:raise AssertionError('Uncommitted result survived database restart')
        event.remove(database.engine,'after_cursor_execute',block_result)
        wait_ready(database)
        with database.engine.connect() as c:
            units=c.execute(text('SELECT ordinal,state,body,lifetime_attempts FROM c0_extraction_units WHERE run_id=:id ORDER BY ordinal'),{'id':run['id']}).mappings().all()
            assert units[0]['state']=='succeeded' and units[0]['body']=='' and units[0]['lifetime_attempts']==1
            assert units[1]['state']=='leased' and units[1]['body'] is None
        renewed=Database(url);acl=AccessService(renewed,access.issuer,key)
        recovered=ExtractionQueue(renewed,acl,originals,enabled=True)
        with renewed.engine.begin() as c:
            c.execute(text("UPDATE c0_extraction_units SET lease_deadline=clock_timestamp()-interval '1 second' WHERE id=:id"),{'id':interrupted.unit_id})
        assert recovered.claim() is None
        with renewed.engine.begin() as c:
            c.execute(text('UPDATE c0_extraction_units SET available_at=clock_timestamp() WHERE id=:id'),{'id':interrupted.unit_id})
        current=recovered.claim();assert current.ordinal==2 and current.token!=interrupted.token
        assert not recovered.complete(interrupted,result)
        assert recovered.complete(current,extract_page_isolated(originals.check(current.original),2))
        environment={**{k:v for k,v in os.environ.items() if not k.startswith(('CZERO_','C0_','PG'))},'CZERO_EXTRACTION_OCR_ENABLED':'0','CZERO_EXTRACTION_CACHE_ENABLED':'1','CZERO_DATABASE_URL':url,'CZERO_OIDC_ISSUER':access.issuer,
            'CZERO_OWNER_LDAP_UUID':str(key),'CZERO_SOURCE_DIR':str(originals.root),'CZERO_EXTRACTION_UNITS':'1','CZERO_EXTRACTION_WORKERS':'2'}
        worker=subprocess.run([sys.executable,'-m','czero_app.extraction_worker'],env=environment,capture_output=True,text=True,timeout=90)
        assert worker.returncode==0 and json.loads(worker.stdout)['processed']==3,'Fresh worker failed'
        assert recovered.status(owner,run['id'])['state']=='ready'
        document=sources.document(owner,version['id'])
        assert hashlib.sha256(document['body'].encode()).hexdigest()==expected['text_sha256']
        assert document['locations']==expected['locations'] and originals.check(version).read_bytes()==original
        with renewed.engine.connect() as c:
            attempts=dict(c.execute(text('SELECT ordinal,lifetime_attempts FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).all())
            assert attempts=={1:1,2:2,3:1,4:1,5:1}
            assert c.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':version['id']}).scalar_one()==1
            assert c.execute(text('SELECT count(*) FROM c0_extraction_units WHERE run_id=:id AND body IS NOT NULL'),{'id':run['id']}).scalar_one()==0
        return {'database_restarted':True,'uncommitted_result_rolled_back':True,'successful_unit_preserved':True,
            'stale_completion_rejected':True,'fresh_worker_process':True,'original_hash_verified':True,
            'single_complete_publication':True,'private_results_cleared':True,'unit_attempts':[attempts[i] for i in range(1,6)]}
    finally:
        database.close()
        if renewed is not None:renewed.close()


async def run(args):
    provenance=source_proof()
    info=json.loads(subprocess.check_output(['podman','inspect',args.container],text=True))
    if len(info)!=1:raise ValueError('one_owned_container_required')
    identifier=validate_container(info[0],args.database_url)
    output=Path(args.output);output.mkdir(mode=0o700,parents=True,exist_ok=False)
    async with disposable_database(args.database_url) as url:
        with tempfile.TemporaryDirectory(prefix='c0-restart-proof-') as private:
            proof={**provenance,**prove(url,identifier,private)}
            (output/'restart-observation.json').write_text(json.dumps(proof,indent=2)+'\n')
    proof['owned_database_cleanup_completed']=True
    (output/'restart.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--container',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();args.database_url=os.environ.get('CZERO_EVAL_DATABASE_URL','')
    asyncio.run(run(args))
