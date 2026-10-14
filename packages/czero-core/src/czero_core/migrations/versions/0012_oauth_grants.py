# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0012_oauth_grants'
down_revision = '0011_oauth_clients'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_oauth_grants',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('account_id', sa.Uuid(), sa.ForeignKey('c0_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_id', sa.Uuid(), sa.ForeignKey('c0_oauth_clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_revision', sa.Integer(), nullable=False),
        sa.Column('issuer', sa.String(1024), nullable=False),
        sa.Column('native_client', sa.String(128), nullable=False),
        sa.Column('resource', sa.String(1024), nullable=False),
        sa.Column('scopes', JSONB(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("jsonb_typeof(scopes)='array' AND jsonb_array_length(scopes) BETWEEN 1 AND 3"))
    op.create_index('ix_oauth_grants_account', 'c0_oauth_grants', ['account_id'])
    op.create_index('ix_oauth_grants_expiry', 'c0_oauth_grants', ['expires_at'])
    op.create_table('c0_oauth_codes',
        sa.Column('hash', sa.String(64), primary_key=True),
        sa.Column('grant_id', sa.Uuid(), sa.ForeignKey('c0_oauth_grants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('redirect_uri', sa.String(1024), nullable=False),
        sa.Column('challenge', sa.String(43), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('c0_oauth_tokens',
        sa.Column('hash', sa.String(64), primary_key=True),
        sa.Column('grant_id', sa.Uuid(), sa.ForeignKey('c0_oauth_grants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(7), nullable=False),
        sa.Column('consumed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('access','refresh')"))
    op.create_index('ix_oauth_tokens_grant', 'c0_oauth_tokens', ['grant_id'])


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
