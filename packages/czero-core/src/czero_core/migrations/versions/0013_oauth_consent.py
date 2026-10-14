# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0013_oauth_consent'
down_revision = '0012_oauth_grants'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_oauth_consent',
        sa.Column('hash', sa.String(64), primary_key=True),
        sa.Column('browser_hash', sa.String(64), nullable=False),
        sa.Column('client_id', sa.Uuid(), sa.ForeignKey('c0_oauth_clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_revision', sa.Integer(), nullable=False),
        sa.Column('issuer', sa.String(1024), nullable=False),
        sa.Column('native_client', sa.String(128), nullable=False),
        sa.Column('resource', sa.String(1024), nullable=False),
        sa.Column('callback', sa.String(1024), nullable=False),
        sa.Column('scopes', JSONB(), nullable=False),
        sa.Column('challenge', sa.String(43), nullable=False),
        sa.Column('state', sa.String(512)),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("jsonb_typeof(scopes)='array' AND jsonb_array_length(scopes) BETWEEN 1 AND 3"))
    op.create_index('ix_oauth_consent_expiry', 'c0_oauth_consent', ['expires_at'])
    op.create_index('ix_oauth_consent_client', 'c0_oauth_consent', ['client_id'])


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
