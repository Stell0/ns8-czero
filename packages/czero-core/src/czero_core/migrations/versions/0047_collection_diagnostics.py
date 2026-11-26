# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Retain bounded collection outcomes after obsolete frontiers are cleared."""
from alembic import op

revision = '0047_collection_diagnostics'
down_revision = '0046_pdf_authorization'
branch_labels = depends_on = None


def upgrade():
    op.execute("""ALTER TABLE c0_source_update_runs
        ADD COLUMN diagnostics jsonb NOT NULL DEFAULT '{}'
        CHECK (jsonb_typeof(diagnostics) = 'object' AND octet_length(diagnostics::text) <= 8192)""")


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
