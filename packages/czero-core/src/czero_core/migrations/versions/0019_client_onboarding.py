# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0019_client_onboarding'
down_revision = '0018_cimd_clients'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_account_blocks',
        sa.Column('account_id', sa.Uuid(), sa.ForeignKey('c0_accounts.id', ondelete='CASCADE'), primary_key=True))
    # Earlier versions represented both unadmitted and revoked users by a missing
    # membership. Preserve both as denied rather than guessing their history.
    op.execute('''INSERT INTO c0_account_blocks(account_id) SELECT a.id FROM c0_accounts a
        WHERE NOT EXISTS (SELECT 1 FROM c0_memberships m WHERE m.account_id=a.id)''')
    op.create_table('c0_client_onboarding',
        sa.Column('hash', sa.String(64), primary_key=True),
        sa.Column('browser_hash', sa.String(64), nullable=False),
        sa.Column('metadata_url', sa.String(2048), nullable=False),
        sa.Column('account_id', sa.Uuid(), sa.ForeignKey('c0_accounts.id', ondelete='CASCADE')),
        sa.Column('issuer', sa.String(2048), nullable=False),
        sa.Column('native_client', sa.String(128), nullable=False),
        sa.Column('resource', sa.String(2048), nullable=False),
        sa.Column('policy_revision', sa.Integer(), nullable=False),
        sa.Column('parameters', JSONB(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("jsonb_typeof(parameters)='object'"))
    op.create_index('ix_c0_onboarding_expiry', 'c0_client_onboarding', ['expires_at'])
    op.create_index('ix_c0_onboarding_client', 'c0_client_onboarding', ['metadata_url'])


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
