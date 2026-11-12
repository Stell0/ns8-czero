# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit authenticated-reader audiences; existing protected spaces stay restricted."""
from alembic import op
import sqlalchemy as sa

revision = '0039_space_audiences'
down_revision = '0038_cross_space_references'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('c0_spaces', sa.Column('readable_by_all', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute('UPDATE c0_spaces SET readable_by_all=true WHERE shared')


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
