# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa

revision = '0022_remembered_browsers'
down_revision = '0021_workspace_access'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('c0_login_states', 'c0_sessions'):
        op.add_column(table, sa.Column('remembered', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('c0_native_authority', sa.Column('connection_idle_seconds', sa.Integer(), nullable=True))
    op.drop_constraint('ck_native_authority_policy', 'c0_native_authority', type_='check')
    op.create_check_constraint('ck_native_authority_policy', 'c0_native_authority',
        "idle_seconds >= 60 AND ((authority_kind='session' AND expires_at IS NOT NULL AND idle_seconds<=86400) OR "
        "(authority_kind IN ('background','remembered') AND expires_at IS NULL AND idle_seconds<=31536000))")
    op.create_check_constraint('ck_native_connection_idle', 'c0_native_authority',
        "connection_idle_seconds IS NULL OR (authority_kind='background' AND connection_idle_seconds BETWEEN 60 AND 31536000 "
        "AND connection_idle_seconds<=idle_seconds)")
    op.drop_constraint('ck_background_browser_idle', 'c0_sessions', type_='check')
    op.create_check_constraint('ck_background_browser_idle', 'c0_sessions',
        '(NOT remembered AND ((browser_idle_until IS NULL AND browser_idle_seconds IS NULL) OR '
        '(browser_idle_until IS NOT NULL AND browser_idle_seconds IS NOT NULL AND browser_idle_seconds BETWEEN 60 AND 86400 AND browser_idle_until<=expires_at))) OR '
        '(remembered AND native_authority_id IS NOT NULL AND browser_idle_seconds IS NOT NULL AND browser_idle_seconds=604800 '
        'AND browser_idle_until IS NOT NULL AND browser_idle_until=expires_at)')
    op.create_table('c0_signin_intents',
        sa.Column('hash', sa.String(64), primary_key=True),
        sa.Column('browser_hash', sa.String(64), nullable=False),
        sa.Column('issuer', sa.String(1024), nullable=False),
        sa.Column('client_id', sa.String(128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_signin_intent_expiry', 'c0_signin_intents', ['expires_at'])


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
