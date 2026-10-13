# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.jobs import JobConflict, JobService, default_registry, health_handler, maintenance_handler
from czero_core.identity import Actor, PermissionDenied, Role
from test_access import access, identity, owner_actor, record_unadmitted, account_named

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


@pytest.fixture
def service(access):
    access_service,database,_=access
    owner=owner_actor(access)
    queue=JobService(database,default_registry(),access_service)
    with database.engine.begin() as c:
        schedules=[dict(r) for r in c.execute(text('SELECT id,enabled,next_run_at FROM c0_scheduled_tasks')).mappings()]
        c.execute(text('UPDATE c0_scheduled_tasks SET enabled=false'))
    yield queue,owner
    with database.engine.begin() as c:
        c.execute(text("DELETE FROM c0_jobs WHERE idempotency_key LIKE :prefix"),{'prefix':'request:'+str(owner.user_id)+':%'})
        tasks=c.execute(text("SELECT id FROM c0_scheduled_tasks WHERE name LIKE 'test-%'")).scalars().all()
        for task in tasks:
            c.execute(text('DELETE FROM c0_jobs WHERE id IN (SELECT job_id FROM c0_task_runs WHERE schedule_id=:id)'),{'id':task})
            c.execute(text('DELETE FROM c0_scheduled_tasks WHERE id=:id'),{'id':task})
        for row in schedules:
            c.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled,next_run_at=:next WHERE id=:id'),
                      {'id':row['id'],'enabled':row['enabled'],'next':row['next_run_at']})


def test_enqueue_is_idempotent_and_conflicting_request_is_atomic(service):
    queue,owner=service
    first=queue.enqueue(owner,'health',{},'one')
    assert first['state']=='queued' and first['attempts']==0
    assert queue.enqueue(owner,'health',{},'one')['id']==first['id']
    with pytest.raises(JobConflict):queue.enqueue(owner,'maintenance',{},'one')
    assert [j['id'] for j in queue.list_jobs(owner)]==[first['id']]
    assert queue.job_runs(owner,first['id'])==[]


def test_health_handler_reports_aggregate_counts_without_profiles(service):
    queue,owner=service
    queue.enqueue(owner,'health',{},'counted')
    with queue.database.engine.begin() as connection:
        result=health_handler(connection,{})
    assert set(result)=={'accounts','active_sessions','queued_jobs'}
    assert result['accounts']>=1 and result['queued_jobs']==1
    assert all(type(value) is int for value in result.values())


@pytest.mark.parametrize('role',[Role.READER,Role.EDITOR,Role.ADMIN])
def test_queue_rights_use_current_membership_not_actor_claims(service,role):
    queue,owner=service
    access=queue.access;key=uuid4()
    record_unadmitted(access,key,'member')
    target=account_named(access,owner,'member')['id'];access.set_role(owner,target,role)
    actor=access.resolve(identity(access,key,'member'))
    forged=Actor(actor.user_id,Role.ADMIN,True)
    if role!=Role.ADMIN:
        for current in (actor,forged):
            with pytest.raises(PermissionDenied):queue.enqueue(current,'health',{},'forged')
            with pytest.raises(PermissionDenied):queue.list_schedules(current)
    else:
        assert queue.list_schedules(actor)
        access.set_role(owner,target,None)
        with pytest.raises(PermissionDenied):queue.list_jobs(actor)


def test_schedule_due_once_and_missed_intervals_coalesce(service):
    queue,owner=service
    task=queue.create_schedule(owner,name='test-'+uuid4().hex,handler='health',payload={},interval_seconds=60)
    due=datetime.now(timezone.utc)-timedelta(minutes=4)
    with queue.database.engine.begin() as c:
        c.execute(text('UPDATE c0_scheduled_tasks SET next_run_at=:due WHERE id=:id'),{'due':due,'id':task['id']})
        now=due+timedelta(minutes=4,seconds=5)
        assert queue._enqueue_due(c,now)==1
        assert queue._enqueue_due(c,now)==0
    runs=queue.task_runs(owner,task['id'])
    assert len(runs)==1 and runs[0]['due_at']==due and runs[0]['state']=='queued'
    current=next(s for s in queue.list_schedules(owner) if s['id']==task['id'])
    assert current['next_run_at']==due+timedelta(minutes=5)
    changed=queue.update_schedule(owner,task['id'],enabled=False,interval_seconds=120)
    assert changed['enabled'] is False and changed['interval_seconds']==120


def test_registered_payloads_intervals_and_unknown_ids_fail_without_writes(service):
    queue,owner=service
    for handler,payload in [('os.system',{}),('health',{'command':'DROP TABLE c0_jobs'})]:
        with pytest.raises(ValueError):queue.enqueue(owner,handler,payload,'bad')
    for interval in (True,0,59,2678401):
        with pytest.raises(ValueError):queue.create_schedule(owner,name='test-invalid',handler='health',payload={},interval_seconds=interval)
    with pytest.raises(ValueError,match='schedule_not_found'):
        queue.update_schedule(owner,uuid4(),enabled=True,interval_seconds=60)
    assert queue.list_jobs(owner)==[]


def test_schedule_name_conflict_and_repeat_migration_preserve_config(service):
    from czero_core.migrate import migrate_database
    queue,owner=service;name='test-'+uuid4().hex
    task=queue.create_schedule(owner,name=name,handler='maintenance',payload={},interval_seconds=604800)
    with pytest.raises(JobConflict):queue.create_schedule(owner,name=name,handler='health',payload={},interval_seconds=60)
    queue.update_schedule(owner,task['id'],enabled=False,interval_seconds=86400)
    migrate_database(queue.database)
    current=next(s for s in queue.list_schedules(owner) if s['id']==task['id'])
    assert not current['enabled'] and current['interval_seconds']==86400


def test_maintenance_bounds_expired_session_work_and_preserves_accounts(service):
    queue,owner=service
    from czero_core.sessions import SessionService, SessionRejected
    access=queue.access
    sessions=SessionService(access,'test-client')
    cookie=sessions.create(identity(access,access.owner_account_key))
    with queue.database.engine.begin() as c:
        c.execute(text("UPDATE c0_sessions SET expires_at=now()-interval '1 hour' WHERE account_id=:id"),{'id':owner.user_id})
        before=c.execute(text('SELECT count(*) FROM c0_sessions WHERE expires_at<=now()')).scalar_one()
        c.execute(text("""INSERT INTO c0_sessions(token_hash,account_id,csrf_token,issuer,client_id,expires_at)
            SELECT md5(:seed || n::text) || md5(n::text || :seed), :account, 'fixture-only',
            :issuer, 'test-client', now()-interval '1 hour' FROM generate_series(1,1005) n"""),
            {'seed':str(uuid4()),'account':owner.user_id,'issuer':access.issuer})
        result=maintenance_handler(c,{})
        assert result['sessions_removed']==1000
        assert c.execute(text('SELECT count(*) FROM c0_sessions WHERE expires_at<=now()')).scalar_one()==before+5
    with pytest.raises(SessionRejected):sessions.get(cookie)
    assert access.profile(owner)['is_owner']
