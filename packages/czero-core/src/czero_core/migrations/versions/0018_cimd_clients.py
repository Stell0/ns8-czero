# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0018_cimd_clients'
down_revision = '0017_session_renewal'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_cimd_policy',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint('id=1'),
        sa.CheckConstraint('revision BETWEEN 1 AND 2147483646'))
    op.execute('INSERT INTO c0_cimd_policy(id) VALUES (1)')
    op.create_table('c0_cimd_clients',
        sa.Column('client_id', sa.Uuid(), sa.ForeignKey('c0_oauth_clients.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('metadata_url', sa.String(2048), nullable=False, unique=True),
        sa.Column('approved_descriptor', JSONB(), nullable=False),
        sa.Column('metadata_digest', sa.String(64), nullable=False),
        sa.Column('review_required', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fresh_until', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('fresh_until>=verified_at'),
        sa.CheckConstraint("jsonb_typeof(approved_descriptor)='object'"))


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
