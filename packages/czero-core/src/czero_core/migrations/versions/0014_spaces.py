# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Protected spaces retain the original shared knowledge identity."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0014_spaces'
down_revision = '0013_oauth_consent'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_spaces',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False, unique=True),
        sa.Column('shared', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by', sa.Uuid()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('revision BETWEEN 1 AND 2147483646'))
    op.create_index('c0_spaces_shared', 'c0_spaces', ['shared'], unique=True,
                    postgresql_where=sa.text('shared'))
    op.execute('''INSERT INTO c0_spaces(id,name,shared,created_at)
        SELECT knowledge_space_id,'Shared',true,created_at FROM instance_metadata''')
    op.create_table('c0_space_grants',
        sa.Column('space_id', sa.Uuid(), sa.ForeignKey('c0_spaces.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('account_id', sa.Uuid(), sa.ForeignKey('c0_accounts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('role', sa.String(16)),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IS NULL OR role IN ('reader','editor')"),
        sa.CheckConstraint('revision BETWEEN 1 AND 2147483646'))
    op.create_index('c0_space_grants_account', 'c0_space_grants', ['account_id', 'space_id'])
    op.create_table('c0_space_receipts',
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('c0_accounts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('key', sa.String(128), primary_key=True),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('result', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("jsonb_typeof(result)='object' AND octet_length(result::text)<=1048576"))


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
