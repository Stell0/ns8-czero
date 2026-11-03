# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Current-owned lookup index and actual reuse counters, without body copies."""
from alembic import op

revision='0029_extraction_cache'
down_revision='0028_local_ocr'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('CREATE INDEX c0_extraction_current_inputs ON c0_extraction_runs(space_id,original_sha256)')
    for name in ('cache_hits','cache_misses','reused_bytes'):
        op.execute('ALTER TABLE c0_extraction_runs ADD COLUMN '+name+' bigint NOT NULL DEFAULT 0 CHECK('+name+'>=0)')
    op.execute('ALTER TABLE c0_extraction_units ADD COLUMN reused boolean NOT NULL DEFAULT false')


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
