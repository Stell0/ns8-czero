# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded aggregate extraction metrics and fair run admission."""
from alembic import op

revision='0026_extraction_pool'
down_revision='0025_pdf_units'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('ALTER TABLE c0_extraction_runs ADD COLUMN last_claimed_at timestamptz')
    for column in ('wait_ms','run_ms','retry_wait_ms','timeout_count'):
        op.execute('ALTER TABLE c0_extraction_runs ADD COLUMN '+column+' bigint NOT NULL DEFAULT 0 CHECK('+column+'>=0)')
    op.execute("CREATE INDEX c0_extraction_fair ON c0_extraction_runs((COALESCE(last_claimed_at,created_at)),created_at,id) WHERE state='extracting'")
    op.execute("CREATE INDEX c0_extraction_space_leases ON c0_extraction_units(space_id,lease_deadline) WHERE state='leased'")


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
