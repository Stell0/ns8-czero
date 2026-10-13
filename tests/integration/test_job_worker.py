# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
import json
import os
import subprocess
import sys
import time

import pytest
from sqlalchemy import text

from czero_core.jobs import Handler, Registry
from czero_core.worker import JobTimedOut, Worker, WORKER_LOCK
from test_job_services import service, access

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


@pytest.fixture
def effects(service):
    queue,owner=service
    with queue.database.engine.begin() as c:
        c.execute(text('CREATE TABLE c0_worker_effects(id integer PRIMARY KEY)'))
    yield queue,owner
    with queue.database.engine.begin() as c:c.execute(text('DROP TABLE c0_worker_effects'))


def write_effect(connection,payload):
    connection.execute(text('INSERT INTO c0_worker_effects VALUES (1)'))
    return {'written':1}


def force_due(queue,job):
    with queue.database.engine.begin() as c:
        c.execute(text('UPDATE c0_jobs SET available_at=now() WHERE id=:id'),{'id':job['id']})


def find_job(queue,owner,job):
    return next(row for row in queue.list_jobs(owner) if row['id']==job['id'])


def test_database_effects_and_completion_commit_once_and_lock_is_released(effects):
    queue,owner=effects;queue.registry.register(Handler('write',write_effect))
    job=queue.enqueue(owner,'write',{},'write')
    worker=Worker(queue.database,queue.registry)
    assert worker.tick()==1 and worker.tick()==0
    current=find_job(queue,owner,job)
    assert current['state']=='succeeded' and current['result']=={'written':1}
    assert len(queue.job_runs(owner,job['id']))==1
    with queue.database.engine.begin() as c:
        assert c.execute(text('SELECT count(*) FROM c0_worker_effects')).scalar_one()==1
        assert c.execute(text('SELECT pg_try_advisory_lock(:key)'),{'key':WORKER_LOCK}).scalar_one()
        assert c.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':WORKER_LOCK}).scalar_one()


def test_failure_rolls_back_effects_and_retries_to_limit_without_error_text(effects,caplog):
    queue,owner=effects
    def fail(connection,payload):
        write_effect(connection,payload)
        raise ValueError('private payload must never reach logs')
    queue.registry.register(Handler('fail',fail))
    job=queue.enqueue(owner,'fail',{},'fail');worker=Worker(queue.database,queue.registry)
    for attempt in range(1,4):
        force_due(queue,job);assert worker.tick()==1
        current=find_job(queue,owner,job)
        assert current['attempts']==attempt
        assert current['state']==('failed' if attempt==3 else 'queued')
        assert current['error_code']=='handler_failed'
        with queue.database.engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM c0_worker_effects')).scalar_one()==0
    assert len(queue.job_runs(owner,job['id']))==3
    assert 'private payload' not in caplog.text


def test_timeout_rolls_back_effects_and_records_terminal_attempt(effects):
    queue,owner=effects
    def slow(connection,payload):
        write_effect(connection,payload);time.sleep(2);return {}
    queue.registry.register(Handler('slow',slow,max_attempts=1,timeout_seconds=1))
    job=queue.enqueue(owner,'slow',{},'slow')
    assert Worker(queue.database,queue.registry).tick()==1
    assert find_job(queue,owner,job)['error_code']=='timeout'
    assert find_job(queue,owner,job)['state']=='failed'
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_worker_effects')).scalar_one()==0


def test_post_commit_timeout_does_not_requeue_committed_effects(effects,monkeypatch):
    import czero_core.worker
    @contextmanager
    def after_commit(seconds):
        yield
        raise JobTimedOut()
    monkeypatch.setattr(czero_core.worker,'deadline',after_commit)
    queue,owner=effects;queue.registry.register(Handler('write',write_effect))
    job=queue.enqueue(owner,'write',{},'committed')
    worker=Worker(queue.database,queue.registry)
    assert worker.tick()==1 and worker.tick()==0
    assert find_job(queue,owner,job)['state']=='succeeded'
    assert queue.job_runs(owner,job['id'])[0]['state']=='succeeded'
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_worker_effects')).scalar_one()==1


def child_code(name,body):
    return (
        "import os,json; from sqlalchemy import text; "
        "from czero_core.database import Database; "
        "from czero_core.jobs import Handler,Registry; "
        "from czero_core.worker import Worker; "
        "database=Database(os.environ['CZERO_TEST_DATABASE_URL']); "
        "exec("+repr("def execute(connection,payload):\n"+body)+"); "
        "registry=Registry([Handler("+repr(name)+",execute)]); "
        "print(json.dumps({'processed':Worker(database,registry).tick()})); database.close()"
    )


def test_actual_process_death_rolls_back_and_recovers_attempt(effects):
    queue,owner=effects;queue.registry.register(Handler('crash',write_effect))
    job=queue.enqueue(owner,'crash',{},'crash')
    code=child_code('crash',"    connection.execute(text('INSERT INTO c0_worker_effects VALUES (1)'))\n    os._exit(17)")
    child=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=10)
    assert child.returncode==17
    assert find_job(queue,owner,job)['state']=='running'
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_worker_effects')).scalar_one()==0
    worker=Worker(queue.database,queue.registry)
    assert worker.tick()==0
    assert find_job(queue,owner,job)['error_code']=='interrupted'
    force_due(queue,job)
    assert worker.tick()==1
    assert find_job(queue,owner,job)['state']=='succeeded'
    assert [r['state'] for r in queue.job_runs(owner,job['id'])]==['succeeded','failed']


def test_concurrent_real_processes_do_not_execute_same_job(effects):
    queue,owner=effects;queue.registry.register(Handler('blocking',write_effect))
    job=queue.enqueue(owner,'blocking',{},'blocking')
    code=child_code('blocking',"    connection.execute(text('SELECT pg_advisory_xact_lock(999001)'))\n    connection.execute(text('INSERT INTO c0_worker_effects VALUES (1)'))\n    return {'written':1}")
    first=None
    with queue.database.engine.connect() as barrier:
        barrier.execute(text('SELECT pg_advisory_lock(999001)'));barrier.commit()
        try:
            first=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            stop=time.monotonic()+5
            while time.monotonic()<stop:
                if find_job(queue,owner,job)['state']=='running':break
                time.sleep(.02)
            else:pytest.fail('First worker did not claim')
            second=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=5)
            assert second.returncode==0 and json.loads(second.stdout)=={'processed':0}
            assert first.poll() is None
        finally:
            barrier.execute(text('SELECT pg_advisory_unlock(999001)'));barrier.commit()
            if first is not None:
                output,errors=first.communicate(timeout=10)
                assert first.returncode==0 and json.loads(output)=={'processed':1}
    assert find_job(queue,owner,job)['state']=='succeeded'
    assert len(queue.job_runs(owner,job['id']))==1
    with queue.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_worker_effects')).scalar_one()==1


def test_removed_handler_is_reported_without_import_or_retry(service):
    queue,owner=service;job=queue.enqueue(owner,'health',{},'missing')
    assert Worker(queue.database,Registry()).tick()==1
    current=find_job(queue,owner,job)
    assert current['state']=='failed' and current['error_code']=='handler_unavailable'


def test_due_schedule_executes_once_with_persisted_completion(service):
    from uuid import uuid4
    queue,owner=service
    task=queue.create_schedule(owner,name='test-'+uuid4().hex,handler='health',payload={},interval_seconds=60)
    with queue.database.engine.begin() as connection:
        connection.execute(text("UPDATE c0_scheduled_tasks SET next_run_at=now()-interval '1 second' WHERE id=:id"),{'id':task['id']})
    worker=Worker(queue.database,queue.registry)
    assert worker.tick()==1 and worker.tick()==0
    runs=queue.task_runs(owner,task['id'])
    assert len(runs)==1 and runs[0]['state']=='succeeded' and runs[0]['attempts']==1
    assert len(queue.job_runs(owner,runs[0]['job_id']))==1
