# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen originals, real parsing/publication and explicitly scoped observations."""
import argparse
import asyncio
from collections import defaultdict
import hashlib
from importlib.metadata import version
from io import BytesIO
import json
import math
import os
from pathlib import Path
import platform
import resource
import re
import statistics
import subprocess
import sys
import tempfile
from threading import Event,Thread,Lock
import time
from uuid import uuid4

from sqlalchemy import text,event
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.migrate import migrate_database
from czero_core.sources import OriginalStore,SourceService,register_source_handlers
from evaluation.fixture import disposable_database,database_parameters

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'tests/fixtures/evidence/pipeline'
ARMS=('whole','units-1-cold','units-1-warm','units-2-cold','units-2-warm','units-4-cold','units-4-warm')


def digest(value):return hashlib.sha256(value).hexdigest()


def corpus():
    raw=(FIXTURES/'manifest.json').read_bytes()
    values={row['name']:row for row in json.loads(raw)['files'] if 'text_sha256' in row}
    for name,row in values.items():
        if Path(name).name!=name or digest((FIXTURES/name).read_bytes())!=row['original_sha256']:
            raise ValueError('frozen_original_changed')
    return digest(raw),values


def percentile(values,fraction):
    if not values or not 0<fraction<=1:raise ValueError('invalid_sample')
    return sorted(values)[max(0,math.ceil(len(values)*fraction)-1)]


def usage():
    own=resource.getrusage(resource.RUSAGE_SELF);children=resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'cpu_seconds':own.ru_utime+own.ru_stime+children.ru_utime+children.ru_stime,
        'self_lifetime_peak_rss_kib':own.ru_maxrss,'child_lifetime_peak_rss_kib':children.ru_maxrss}


class MemoryProbe:
    """Linux process-tree RSS sampled at 50 ms; this is not an exact peak."""
    def __init__(self):self.stop=Event();self.peak=0;self.thread=Thread(target=self.sample,daemon=True)
    def sample(self):
        while not self.stop.is_set():
            rows={}
            for entry in Path('/proc').iterdir():
                if not entry.name.isdigit():continue
                try:
                    fields=dict(line.split(':',1) for line in (entry/'status').read_text().splitlines() if ':' in line)
                    rows[int(entry.name)]=(int(fields['PPid']),int(fields.get('VmRSS','0 kB').split()[0]))
                except (OSError,ValueError,KeyError):continue
            family={os.getpid()}
            while True:
                following=family|{pid for pid,(parent,_) in rows.items() if parent in family}
                if following==family:break
                family=following
            self.peak=max(self.peak,sum(rss for pid,(_,rss) in rows.items() if pid in family))
            self.stop.wait(.05)
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*_):self.stop.set();self.thread.join(2)


def database_observation(database):
    with database.engine.connect() as c:
        c.execute(text('SELECT pg_stat_clear_snapshot()'))
        size=c.execute(text('SELECT pg_database_size(current_database())')).scalar_one()
        stats=c.execute(text('''SELECT blks_read,blks_hit,tup_inserted,tup_updated,tup_deleted,
            blk_read_time,blk_write_time FROM pg_stat_database WHERE datname=current_database()''')).mappings().one()
        tables=c.execute(text("SELECT sum(pg_total_relation_size(oid)) FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r'")).scalar_one()
        return {'database_bytes':size,'public_table_bytes':int(tables or 0),'reported_stats':dict(stats)}


def drain(queue,actor,run_id):
    for _ in range(20):
        ExtractionPool(queue,workers=queue.instance_workers).tick()
        state=queue.status(actor,run_id)
        if state['state']=='ready':return state
        if state['state'] in ('failed','superseded'):raise AssertionError('benchmark_extraction_failed')
    raise AssertionError('benchmark_drain_limit')


def measure(spec,url,directory):
    parsed=database_parameters(url)
    if not re.fullmatch(r'czero_eval_[0-9a-f]{32}',parsed.database or ''):
        raise ValueError('measurement_requires_owned_random_database')
    frozen,values=corpus()
    if spec['corpus_sha256']!=frozen or spec['case'] not in values or spec['arm'] not in ARMS:
        raise ValueError('invalid_frozen_measurement')
    expected=values[spec['case']];original=(FIXTURES/spec['case']).read_bytes()
    database=Database(url)
    try:
        migrate_database(database)
        key=uuid4();access=AccessService(database,'https://idp.example.test/benchmark',key)
        actor=access.resolve(VerifiedIdentity(access.issuer,str(key),str(key),'benchmark-owner','Benchmark owner',time.time()+3600))
        registry=default_registry();originals=OriginalStore(Path(directory)/'originals')
        register_source_handlers(registry,database,originals)
        sources=SourceService(database,access,registry,originals)
        with database.engine.begin() as c:c.execute(text('UPDATE c0_scheduled_tasks SET enabled=false'))
        arm=spec['arm'];workers=0 if arm=='whole' else int(arm.split('-')[1]);warm=arm.endswith('warm')
        queue=ExtractionQueue(database,access,originals,enabled=True,instance_workers=max(1,workers),
            document_workers=max(1,workers),space_workers=max(1,workers),cache_enabled=warm)
        def submit(title):return sources.ingest(actor,BytesIO(original),title=title,filename=spec['case'],media_type=expected['media_type'],retain_original=True)
        if warm:
            seed=submit('Warm current owner');seed_run=queue.enqueue(actor,seed['id'],expected_generation=1)
            drain(queue,actor,seed_run['id'])
        before=database_observation(database);prior=usage();sql={'statements':0,'elapsed_seconds_sum':0.0};lock=Lock()
        def sql_started(conn,cursor,statement,parameters,context,many):context._benchmark_start=time.perf_counter()
        def sql_finished(conn,cursor,statement,parameters,context,many):
            elapsed=time.perf_counter()-context._benchmark_start
            with lock:sql['statements']+=1;sql['elapsed_seconds_sum']+=elapsed
        event.listen(database.engine,'before_cursor_execute',sql_started)
        event.listen(database.engine,'after_cursor_execute',sql_finished)
        started=time.perf_counter();manifest_seconds=None
        with MemoryProbe() as memory:
            upload_started=time.perf_counter();version=submit('Measured current document')
            assert version['content_hash']==expected['original_sha256']
            upload_seconds=time.perf_counter()-upload_started
            extraction_started=time.perf_counter()
            if arm=='whole':
                with database.engine.begin() as c:registry.get('source.extract').execute(c,{'version_id':str(version['id'])})
                status=None
            else:
                manifest_started=time.perf_counter()
                run=queue.enqueue(actor,version['id'],expected_generation=1)
                manifest_seconds=time.perf_counter()-manifest_started
                status=drain(queue,actor,run['id'])
            extraction_seconds=time.perf_counter()-extraction_started
            document=sources.document(actor,version['id'])
            chunks=sources.chunks(actor,document['id'],limit=100)
            # Page through every chunk; default reads never establish full coverage.
            all_chunks=list(chunks)
            while len(chunks)==100:
                chunks=sources.chunks(actor,document['id'],limit=100,offset=len(all_chunks));all_chunks.extend(chunks)
            exact_spans=all(row['body']==document['body'][row['start_offset']:row['end_offset']]
                and digest(row['body'].encode())==row['content_hash'] for row in all_chunks)
            quality={'text_hash_exact':document['text_hash']==digest(document['body'].encode())==expected['text_sha256'],
                'character_count_exact':len(document['body'])==expected['characters'],
                'locations_exact':document['locations']==expected['locations'],'chunk_spans_exact':exact_spans}
            assert all(quality.values()),'extraction_quality_regression'
            wall=time.perf_counter()-started
        event.remove(database.engine,'before_cursor_execute',sql_started)
        event.remove(database.engine,'after_cursor_execute',sql_finished)
        after_usage=usage();after=database_observation(database)
        if warm:assert status['cache_hits']==status['expected_units'] and status['cache_misses']==0
        result={**spec,'source_sha256':expected['original_sha256'],'text_sha256':document['text_hash'],
            'quality':quality,'workers':workers,'output_cache':'warm-current' if warm else 'disabled' if workers else 'legacy-none',
            'os_disk_cache':'uncontrolled','upload_seconds':upload_seconds,'extraction_seconds':extraction_seconds,
            'manifest_seconds':manifest_seconds,'sql_during_submission_execution_readback':sql,
            'end_to_end_seconds':wall,'cpu_seconds':after_usage['cpu_seconds']-prior['cpu_seconds'],
            'sampled_process_tree_peak_rss_kib':memory.peak,'sampling_seconds':.05,
            'lifetime_peak_rss_includes_setup':True,**{k:v for k,v in after_usage.items() if k!='cpu_seconds'},
            'database_before':before,'database_after':after,'database_growth_bytes':after['database_bytes']-before['database_bytes'],
            'queue':{k:status[k] for k in ('expected_units','claimed','succeeded','retried','wait_ms','run_ms','retry_wait_ms','cache_hits','cache_misses','reused_bytes')} if status else None,
            'observed_characters_per_second':len(document['body'])/extraction_seconds,
            'reported_ocr_cost':None,'ocr_mode':'disabled','postgres_stats_are_asynchronous':True,
            'driver':'continuous bounded one-shot drains; native timer waiting excluded'}
        return result
    finally:database.close()


def summarize(rows):
    groups=defaultdict(list)
    for row in rows:groups[(row['case'],row['arm'])].append(row)
    result=[]
    for (case,arm),items in groups.items():
        timing=[row['extraction_seconds'] for row in items]
        result.append({'case':case,'arm':arm,'samples':len(items),'p50_seconds':statistics.median(timing),
            'p95_seconds':percentile(timing,.95),'p95_method':'nearest rank',
            'max_sampled_tree_rss_kib':max(row['sampled_process_tree_peak_rss_kib'] for row in items),
            'all_exact':all(all(row['quality'].values()) for row in items)})
    return result


async def benchmark(args):
    database_parameters(args.database_url)
    output=Path(args.output);output.mkdir(mode=0o700,parents=True,exist_ok=False)
    frozen,values=corpus();cases=args.cases or list(values)
    if not set(cases)<=values.keys():raise ValueError('unknown_frozen_case')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    proof={'source':source,'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
        'kind':'extraction fidelity and observed execution; no retrieval or model-quality claim',
        'corpus_sha256':frozen,'arms':args.arms,'cases':cases,'repeats':args.repeats,'smoke_only':args.smoke,
        'platform':platform.system(),'machine':platform.machine(),'python':platform.python_version(),
        'runtime_versions':{name:version(name) for name in ('czero-core','pypdf','python-docx','sqlalchemy','psycopg')},
        'core_mode':'explicit local producer','rows':[]}
    (output/'measurement.json').write_text(json.dumps(proof,indent=2)+'\n')
    # Rotate arm order by repeat to reduce a fixed ordering bias. No disk-cache
    # flush, CPU quota change or host tuning is part of this experiment.
    for repeat in range(1 if args.smoke else args.repeats):
        arms=args.arms[repeat%len(args.arms):]+args.arms[:repeat%len(args.arms)]
        for case in cases:
            for arm in arms:
                spec={'case':case,'arm':arm,'repeat':repeat,'corpus_sha256':frozen}
                trial=output/(str(repeat)+'-'+case+'-'+arm);trial.mkdir(mode=0o700)
                path=trial/'spec.json';path.write_text(json.dumps(spec))
                async with disposable_database(args.database_url) as url:
                    with tempfile.TemporaryDirectory(prefix='c0-extraction-benchmark-') as private:
                        with (trial/'stderr.log').open('xb') as stderr:
                            child=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'scripts/benchmark-ingestion.py'),
                                '--measure',str(path),'--directory',private,env={**os.environ,'CZERO_BENCH_DATABASE_URL':url},
                                stdout=asyncio.subprocess.PIPE,stderr=stderr)
                            try:raw,_=await asyncio.wait_for(child.communicate(),600)
                            except BaseException:
                                child.kill();await child.wait();raise
                        if child.returncode:raise RuntimeError('measurement_failed; preserved private stderr')
                        row=json.loads(raw);(trial/'result.json').write_text(json.dumps(row,indent=2)+'\n')
                        proof['rows'].append(row);proof['summary']=summarize(proof['rows'])
                        (output/'measurement.json').write_text(json.dumps(proof,indent=2)+'\n')
                        print(case+' '+arm+' '+str(repeat)+' exact',flush=True)
    return proof


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output');parser.add_argument('--cases',nargs='+');parser.add_argument('--arms',nargs='+',choices=ARMS,default=list(ARMS))
    parser.add_argument('--repeats',type=int,choices=range(3,11),default=5);parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--measure',type=Path,help=argparse.SUPPRESS);parser.add_argument('--directory',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.measure:
        print(json.dumps(measure(json.loads(args.measure.read_text()),os.environ['CZERO_BENCH_DATABASE_URL'],args.directory)))
    else:
        if not args.output:parser.error('--output is required')
        args.database_url=os.environ.get('CZERO_EVAL_DATABASE_URL','')
        asyncio.run(benchmark(args))
