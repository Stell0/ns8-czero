# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_jobs"
down_revision = "0003_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("c0_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("idempotency_key", sa.String(192), nullable=False, unique=True),
        sa.Column("handler", sa.String(64), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("result", JSONB()),
        sa.Column("error_code", sa.String(32)),
        sa.CheckConstraint("state IN ('queued','running','succeeded','failed')"),
        sa.CheckConstraint("attempts >= 0 AND attempts <= max_attempts"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 5"),
        sa.CheckConstraint("timeout_seconds BETWEEN 1 AND 30"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 32768"),
        sa.CheckConstraint("result IS NULL OR (jsonb_typeof(result) = 'object' AND octet_length(result::text) <= 32768)"))
    op.create_index("c0_jobs_due", "c0_jobs", ["state", "available_at", "created_at"])
    op.create_table("c0_job_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("c0_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(32)),
        sa.UniqueConstraint("job_id", "attempt"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 5"),
        sa.CheckConstraint("state IN ('running','succeeded','failed')"))
    op.create_table("c0_scheduled_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("handler", sa.String(64), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("interval_seconds BETWEEN 60 AND 2678400"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 32768"))
    op.create_index("c0_scheduled_tasks_due", "c0_scheduled_tasks", ["enabled", "next_run_at"])
    op.create_table("c0_task_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("schedule_id", sa.Uuid(), sa.ForeignKey("c0_scheduled_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("c0_jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.UniqueConstraint("schedule_id", "due_at"))
    tasks = sa.table("c0_scheduled_tasks", sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()), sa.column("handler", sa.String()),
        sa.column("payload", JSONB()), sa.column("interval_seconds", sa.Integer()),
        sa.column("next_run_at", sa.DateTime(timezone=True)))
    op.execute(tasks.insert().values(id=uuid4(), name="health-hourly", handler="health",
        payload={}, interval_seconds=3600, next_run_at=sa.func.now()))
    op.execute(tasks.insert().values(id=uuid4(), name="maintenance-weekly", handler="maintenance",
        payload={}, interval_seconds=604800, next_run_at=sa.func.now() + sa.text("interval '7 days'")))


def downgrade():
    raise RuntimeError("C0 schema downgrades are not supported")
