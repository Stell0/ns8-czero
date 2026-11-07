# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bound assessment lookups and foreign-key checks without changing stored state."""
from alembic import op

revision = '0035_compilation_assessment'
down_revision = '0034_compilation_maintenance'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE INDEX c0_compilation_sources_assessment
        ON c0_compilation_sources(space_id,assessment_task_id)
        WHERE assessment_task_id IS NOT NULL""")


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
