# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted deterministic handlers and PostgreSQL queue/schedule operations."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .access import AccessService
from .database import Database
from .identity import Actor, PermissionDenied, Role

_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
_KEY = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
MAX_JSON_BYTES = 16384


class JobConflict(ValueError):
    def __init__(self):
        super().__init__("job_conflict")


def bounded_json(value: dict) -> str:
    if not isinstance(value, dict):
        raise ValueError("invalid_payload")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
            raise ValueError()
        return encoded
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise ValueError("invalid_payload") from None


def empty_payload(value: dict) -> dict:
    if value != {}:
        raise ValueError("invalid_payload")
    return {}


@dataclass(frozen=True)
class Handler:
    name: str
    execute: Callable
    validate: Callable = empty_payload
    max_attempts: int = 3
    timeout_seconds: int = 10

    def __post_init__(self):
        if not isinstance(self.name, str) or not _NAME.fullmatch(self.name):
            raise ValueError("invalid_handler")
        if not callable(self.execute) or not callable(self.validate):
            raise ValueError("invalid_handler")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ValueError("invalid_attempt_limit")
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 30:
            raise ValueError("invalid_timeout")


class Registry:
    def __init__(self, handlers=()):
        self._handlers = {}
        for handler in handlers:
            self.register(handler)

    def register(self, handler: Handler) -> None:
        if not isinstance(handler, Handler) or handler.name in self._handlers:
            raise ValueError("invalid_handler")
        self._handlers[handler.name] = handler

    def get(self, name: str) -> Handler:
        if not isinstance(name, str) or name not in self._handlers:
            raise ValueError("unknown_handler")
        return self._handlers[name]

    def describe(self) -> list[dict]:
        return [{"name": item.name, "max_attempts": item.max_attempts,
                 "timeout_seconds": item.timeout_seconds} for item in self._handlers.values()]


def health_handler(connection, payload):
    row = connection.execute(text("""SELECT
        (SELECT count(*) FROM c0_accounts) AS accounts,
        (SELECT count(*) FROM c0_sessions WHERE expires_at > now()) AS active_sessions,
        (SELECT count(*) FROM c0_jobs WHERE state = 'queued') AS queued_jobs
    """)).mappings().one()
    return dict(row)


def maintenance_handler(connection, payload):
    result = {}
    for table, key in (("c0_sessions", "token_hash"), ("c0_login_states", "state_hash")):
        # Identifiers are fixed trusted code, never handler/request input.
        removed = connection.execute(text(f"""WITH expired AS MATERIALIZED
            (SELECT {key} FROM {table} WHERE expires_at <= now()
             ORDER BY expires_at LIMIT 1000 FOR UPDATE SKIP LOCKED)
            DELETE FROM {table} USING expired WHERE {table}.{key}=expired.{key}"""))
        result[table.removeprefix("c0_") + "_removed"] = removed.rowcount
    result["jobs_removed"] = connection.execute(text("""WITH expired AS MATERIALIZED
        (SELECT id FROM c0_jobs WHERE state IN ('succeeded','failed')
         AND finished_at < now() - interval '30 days'
         ORDER BY finished_at LIMIT 1000 FOR UPDATE SKIP LOCKED)
        DELETE FROM c0_jobs USING expired WHERE c0_jobs.id=expired.id""")).rowcount
    return result


def default_registry() -> Registry:
    return Registry((Handler("health", health_handler), Handler("maintenance", maintenance_handler)))


class JobService:
    """Public calls authorize Admin; private methods serve the trusted worker."""
    def __init__(self, database: Database, registry: Registry, access: AccessService | None = None):
        self.database, self.registry, self.access = database, registry, access

    def _authorize(self, connection, actor: Actor):
        if self.access is None:
            raise PermissionDenied()
        self.access._actor(connection, actor.user_id).require(Role.ADMIN)

    @staticmethod
    def _limit(limit):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid_limit")

    def _enqueue(self, connection, name, payload, key):
        handler = self.registry.get(name)
        bounded_json(payload)
        encoded = bounded_json(handler.validate(payload))
        fingerprint = hashlib.sha256((name + "\n" + encoded).encode()).hexdigest()
        if not isinstance(key, str) or not 1 <= len(key) <= 192:
            raise ValueError("invalid_idempotency_key")
        row = connection.execute(text("""INSERT INTO c0_jobs
            (id,idempotency_key,handler,payload,fingerprint,max_attempts,timeout_seconds)
            VALUES (:id,:key,:handler,CAST(:payload AS jsonb),:fingerprint,:attempts,:timeout)
            ON CONFLICT (idempotency_key) DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
            RETURNING *"""), {"id":uuid4(), "key":key, "handler":name, "payload":encoded,
                "fingerprint":fingerprint, "attempts":handler.max_attempts,
                "timeout":handler.timeout_seconds}).mappings().one()
        if row["fingerprint"] != fingerprint:
            raise JobConflict()
        return dict(row)

    def enqueue(self, actor: Actor, name: str, payload: dict, idempotency_key: str) -> dict:
        with self.database.engine.begin() as connection:
            self._authorize(connection, actor)
            if not isinstance(idempotency_key, str) or not _KEY.fullmatch(idempotency_key):
                raise ValueError("invalid_idempotency_key")
            return self._enqueue(connection, name, payload, "request:" + str(actor.user_id) + ":" + idempotency_key)

    def list_jobs(self, actor: Actor, *, limit=50) -> list[dict]:
        self._limit(limit)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return [dict(row) for row in connection.execute(text("""SELECT * FROM c0_jobs
                ORDER BY created_at DESC,id LIMIT :limit"""), {"limit":limit}).mappings()]

    def list_handlers(self, actor: Actor) -> list[dict]:
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return self.registry.describe()

    def get_job(self, actor: Actor, job_id: UUID) -> dict:
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor)
            row=connection.execute(text("SELECT * FROM c0_jobs WHERE id=:id"),{"id":job_id}).mappings().one_or_none()
            if row is None:
                raise ValueError("job_not_found")
            return dict(row)

    def job_runs(self, actor: Actor, job_id: UUID, *, limit=50) -> list[dict]:
        self._limit(limit)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return [dict(row) for row in connection.execute(text("""SELECT * FROM c0_job_runs
                WHERE job_id = :id ORDER BY attempt DESC LIMIT :limit"""), {"id":job_id,"limit":limit}).mappings()]

    def list_schedules(self, actor: Actor, *, limit=50) -> list[dict]:
        self._limit(limit)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return [dict(row) for row in connection.execute(text("""SELECT * FROM c0_scheduled_tasks
                ORDER BY name,id LIMIT :limit"""), {"limit":limit}).mappings()]

    def update_schedule(self, actor: Actor, schedule_id: UUID, *, enabled: bool, interval_seconds: int) -> dict:
        with self.database.engine.begin() as connection:
            self._authorize(connection, actor)
            if type(enabled) is not bool or type(interval_seconds) is not int or not 60 <= interval_seconds <= 2678400:
                raise ValueError("invalid_schedule")
            row = connection.execute(text("""UPDATE c0_scheduled_tasks SET enabled = :enabled,
                next_run_at = CASE WHEN interval_seconds <> :interval OR (NOT enabled AND :enabled)
                    THEN now() + make_interval(secs => :interval) ELSE next_run_at END,
                interval_seconds = :interval WHERE id = :id RETURNING *"""),
                {"id":schedule_id,"enabled":enabled,"interval":interval_seconds}).mappings().one_or_none()
            if row is None:
                raise ValueError("schedule_not_found")
            return dict(row)

    def create_schedule(self, actor: Actor, *, name: str, handler: str, payload: dict, interval_seconds: int) -> dict:
        with self.database.engine.begin() as connection:
            self._authorize(connection, actor)
            if not isinstance(name,str) or not _NAME.fullmatch(name) or type(interval_seconds) is not int or not 60 <= interval_seconds <= 2678400:
                raise ValueError("invalid_schedule")
            spec = self.registry.get(handler)
            bounded_json(payload)
            encoded = bounded_json(spec.validate(payload))
            try:
                row = connection.execute(text("""INSERT INTO c0_scheduled_tasks
                    (id,name,handler,payload,interval_seconds,next_run_at)
                    VALUES (:id,:name,:handler,CAST(:payload AS jsonb),:interval,
                        now() + make_interval(secs => :interval)) RETURNING *"""),
                    {"id":uuid4(),"name":name,"handler":handler,"payload":encoded,
                     "interval":interval_seconds}).mappings().one()
            except IntegrityError:
                raise JobConflict() from None
            return dict(row)

    def task_runs(self, actor: Actor, schedule_id: UUID, *, limit=50) -> list[dict]:
        self._limit(limit)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return [dict(row) for row in connection.execute(text("""SELECT t.id,t.due_at,t.job_id,
                j.state,j.attempts,j.finished_at,j.error_code FROM c0_task_runs t
                JOIN c0_jobs j ON j.id = t.job_id WHERE t.schedule_id = :id
                ORDER BY t.due_at DESC LIMIT :limit"""), {"id":schedule_id,"limit":limit}).mappings()]

    def _enqueue_due(self, connection, now: datetime) -> int:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("UTC-aware time required")
        now = now.astimezone(timezone.utc)
        rows = connection.execute(text("""SELECT * FROM c0_scheduled_tasks
            WHERE enabled AND next_run_at <= :now ORDER BY next_run_at,id
            LIMIT 100 FOR UPDATE SKIP LOCKED"""), {"now":now}).mappings().all()
        for row in rows:
            due = row["next_run_at"].astimezone(timezone.utc)
            job = self._enqueue(connection,row["handler"],row["payload"],
                                "schedule:" + str(row["id"]) + ":" + due.isoformat())
            connection.execute(text("""INSERT INTO c0_task_runs(id,schedule_id,due_at,job_id)
                VALUES (:id,:schedule,:due,:job) ON CONFLICT(schedule_id,due_at) DO NOTHING"""),
                {"id":uuid4(),"schedule":row["id"],"due":due,"job":job["id"]})
            elapsed = (now - due).total_seconds()
            count = int(elapsed // row["interval_seconds"]) + 1
            connection.execute(text("UPDATE c0_scheduled_tasks SET next_run_at = :next WHERE id = :id"),
                {"id":row["id"],"next":due + timedelta(seconds=count*row["interval_seconds"])})
        return len(rows)
