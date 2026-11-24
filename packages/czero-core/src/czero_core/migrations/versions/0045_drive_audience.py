# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bind Drive work to the destination audience approved by its owner."""
from alembic import op

revision = '0045_drive_audience'
down_revision = '0044_pdf_limits'
branch_labels = depends_on = None


def upgrade():
    op.execute('ALTER TABLE c0_drive_bindings ADD COLUMN approved_audience char(64)')
    # Old bindings have no durable record of the audience their owner reviewed.
    op.execute("DELETE FROM c0_drive_previews")
    op.execute("""UPDATE c0_source_update_runs SET state='blocked',error_code='drive_audience_changed',
        cursor='{}',lease=NULL,finished_at=now() WHERE state IN ('queued','running','pending')
        AND definition_id IN (SELECT definition_id FROM c0_drive_bindings)""")
    op.execute("""UPDATE c0_automatic_sources SET enabled=false,revision=revision+1,
        next_run_at=NULL,updated_at=now() WHERE kind='google_drive' AND enabled""")


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
