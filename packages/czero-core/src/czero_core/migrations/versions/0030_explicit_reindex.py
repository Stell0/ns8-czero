# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit reindex intent; no content or automatic work is added."""
from alembic import op
revision='0030_explicit_reindex'
down_revision='0029_extraction_cache'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('ALTER TABLE c0_source_versions ADD COLUMN force_reindex boolean NOT NULL DEFAULT false')


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
