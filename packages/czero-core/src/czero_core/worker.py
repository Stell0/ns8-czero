# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Serial standalone worker; database effects and completion share a transaction."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import logging
import signal
import sys
import threading
import time
from uuid import uuid4

from sqlalchemy import text

from .database import Database
from .jobs import JobService, Registry, bounded_json, default_registry

WORKER_LOCK = 49374
logger = logging.getLogger("czero.worker")


class JobTimedOut(BaseException):
    pass


class WorkerInterrupted(BaseException):
    pass


@contextmanager
def deadline(seconds):
    previous = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame):
        raise JobTimedOut()
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class Worker:
    """One worker per instance. Crash recovery is bounded at-least-once.

    Handlers use the supplied transaction and return bounded JSON. File/network
    effects must be idempotent. Run from a standalone POSIX main thread, with
    the native container lifetime guard for non-interruptible extension code.
    """
    def __init__(self, database: Database, registry: Registry):
        self.database, self.registry = database, registry
        self.jobs = JobService(database, registry)

    def _fail(self, connection, job, code, now, *, retry=True):
        again = retry and job["attempts"] < job["max_attempts"]
        delay = min(300, 10 * 2 ** max(0, job["attempts"] - 1))
        changed = connection.execute(text("""UPDATE c0_jobs SET state = :state,
            available_at = :available, finished_at = :finished, error_code = :code
            WHERE id = :id AND state = 'running' RETURNING id"""),
            {"id":job["id"],"state":"queued" if again else "failed",
             "available":now+timedelta(seconds=delay),"finished":None if again else now,"code":code}).scalar_one_or_none()
        # A signal/connection exception can arrive after a successful COMMIT.
        # Never requeue already committed effects and successful completion.
        if changed is None:
            return
        connection.execute(text("""UPDATE c0_job_runs SET state = 'failed',
            finished_at = :now, error_code = :code WHERE job_id = :id AND attempt = :attempt
            AND state = 'running'"""), {"id":job["id"],"attempt":job["attempts"],"now":now,"code":code})
        logger.warning("C0 job failed (%s)", code)

    def _recover(self, connection, now):
        # The session lock guarantees no other worker still owns these jobs.
        rows = connection.execute(text("""SELECT * FROM c0_jobs WHERE state = 'running'
            ORDER BY created_at,id LIMIT 100 FOR UPDATE""")).mappings().all()
        for row in rows:
            self._fail(connection,row,"interrupted",now)

    def _claim(self, connection, now):
        row = connection.execute(text("""SELECT id FROM c0_jobs
            WHERE state = 'queued' AND available_at <= :now AND attempts < max_attempts
            ORDER BY available_at,created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED"""), {"now":now}).scalar_one_or_none()
        if row is None:
            return None
        job = connection.execute(text("""UPDATE c0_jobs SET state = 'running',
            attempts = attempts + 1, error_code = NULL WHERE id = :id RETURNING *"""), {"id":row}).mappings().one()
        connection.execute(text("""INSERT INTO c0_job_runs(id,job_id,attempt,state,started_at)
            VALUES (:id,:job,:attempt,'running',:now)"""),
            {"id":uuid4(),"job":job["id"],"attempt":job["attempts"],"now":now})
        return dict(job)

    def _execute(self, connection, job):
        try:
            spec = self.registry.get(job["handler"])
        except ValueError:
            with connection.begin():
                self._fail(connection,job,"handler_unavailable",datetime.now(timezone.utc),retry=False)
            return
        try:
            with deadline(min(spec.timeout_seconds,job["timeout_seconds"])):
                with connection.begin():
                    payload = spec.validate(job["payload"])
                    bounded_json(payload)
                    result = bounded_json(spec.execute(connection,payload))
                    now = datetime.now(timezone.utc)
                    connection.execute(text("""UPDATE c0_jobs SET state = 'succeeded',
                        result = CAST(:result AS jsonb), finished_at = :now WHERE id = :id"""),
                        {"id":job["id"],"result":result,"now":now})
                    connection.execute(text("""UPDATE c0_job_runs SET state = 'succeeded',
                        finished_at = :now WHERE job_id = :id AND attempt = :attempt"""),
                        {"id":job["id"],"attempt":job["attempts"],"now":now})
        except (Exception,JobTimedOut) as error:
            code = "timeout" if isinstance(error,JobTimedOut) else "handler_failed"
            with connection.begin():
                self._fail(connection,job,code,datetime.now(timezone.utc))

    def tick(self, *, max_jobs: int = 20, budget_seconds: int = 90) -> int:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Worker requires a standalone main thread")
        if type(max_jobs) is not int or not 1 <= max_jobs <= 20 or type(budget_seconds) is not int or not 1 <= budget_seconds <= 90:
            raise ValueError("invalid_worker_limit")
        processed = 0
        started = time.monotonic()
        with self.database.engine.connect() as connection:
            locked = False
            try:
                locked = connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key":WORKER_LOCK}).scalar_one()
                connection.commit()
                if not locked:
                    return 0
                now = datetime.now(timezone.utc)
                with connection.begin():
                    self._recover(connection,now)
                    self.jobs._enqueue_due(connection,now)
                while processed < max_jobs and time.monotonic() - started < budget_seconds:
                    with connection.begin():
                        job = self._claim(connection,datetime.now(timezone.utc))
                    if job is None:
                        break
                    self._execute(connection,job)
                    processed += 1
                return processed
            finally:
                if locked:
                    try:
                        connection.rollback()
                        connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key":WORKER_LOCK})
                        connection.commit()
                    except Exception:
                        # Never return a session-lock-bearing connection to a pool.
                        connection.invalidate()


def main(registry: Registry | None = None) -> int:
    database = None
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(signum,frame):
        raise WorkerInterrupted()
    signal.signal(signal.SIGTERM,terminate)
    try:
        database = Database()
        count = Worker(database,registry or default_registry()).tick()
        print(json.dumps({"processed":count}))
        return 0
    except WorkerInterrupted:
        print("C0 worker interrupted",file=sys.stderr)
        return 0
    except Exception as error:
        print("C0 worker failed ("+type(error).__name__+")",file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM,previous)
        if database is not None:
            database.close()


if __name__ == "__main__":
    sys.exit(main())
