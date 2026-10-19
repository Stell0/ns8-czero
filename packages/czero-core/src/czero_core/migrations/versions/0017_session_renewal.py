# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa

revision = '0017_session_renewal'
down_revision = '0016_annotations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_native_authority',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('account_id', sa.Uuid(), sa.ForeignKey('c0_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('issuer', sa.String(1024), nullable=False),
        sa.Column('native_client', sa.String(128), nullable=False),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('credential', sa.Text(), nullable=True),
        sa.Column('verified_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('idle_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('idle_seconds', sa.Integer(), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('checking', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint('idle_seconds BETWEEN 60 AND 86400'),
        sa.CheckConstraint('idle_until <= expires_at'),
        sa.CheckConstraint("credential IS NULL OR octet_length(credential) <= 65536"))
    op.create_index('ix_native_authority_expiry', 'c0_native_authority', ['expires_at'])
    for table in ('c0_sessions', 'c0_oauth_grants'):
        # NULL leaves all existing authority and expiry semantics unchanged.
        op.add_column(table, sa.Column('native_authority_id', sa.Uuid(),
            sa.ForeignKey('c0_native_authority.id'), nullable=True))
        op.create_index('ix_' + table + '_native_authority', table, ['native_authority_id'])


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
