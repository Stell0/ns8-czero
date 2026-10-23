# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa

revision = '0020_persistent_oauth'
down_revision = '0019_client_onboarding'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('c0_native_authority', sa.Column('authority_kind', sa.String(10), nullable=False, server_default='session'))
    op.alter_column('c0_native_authority', 'expires_at', nullable=True)
    for constraint in sa.inspect(op.get_bind()).get_check_constraints('c0_native_authority'):
        if 'idle_seconds' in constraint['sqltext']:
            op.drop_constraint(constraint['name'], 'c0_native_authority', type_='check')
    op.create_check_constraint('ck_native_authority_policy', 'c0_native_authority',
        "idle_seconds >= 60 AND ((authority_kind='session' AND expires_at IS NOT NULL AND idle_seconds<=86400) OR "
        "(authority_kind='background' AND expires_at IS NULL AND idle_seconds<=31536000))")
    op.add_column('c0_login_states', sa.Column('background', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('c0_login_states', sa.Column('expected_account_key', sa.String(128), nullable=True))
    op.create_check_constraint('ck_background_login_identity', 'c0_login_states',
        '(background AND expected_account_key IS NOT NULL) OR (NOT background AND expected_account_key IS NULL)')
    op.add_column('c0_sessions', sa.Column('browser_idle_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('c0_sessions', sa.Column('browser_idle_seconds', sa.Integer(), nullable=True))
    op.create_check_constraint('ck_background_browser_idle', 'c0_sessions',
        '(browser_idle_until IS NULL AND browser_idle_seconds IS NULL) OR '
        '(browser_idle_until IS NOT NULL AND browser_idle_seconds IS NOT NULL '
        'AND browser_idle_seconds BETWEEN 60 AND 86400 AND browser_idle_until<=expires_at)')
    op.add_column('c0_oauth_consent', sa.Column('background_requested', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('c0_oauth_consent', sa.Column('expected_account_id', sa.Uuid(), sa.ForeignKey('c0_accounts.id', ondelete='CASCADE'), nullable=True))
    op.alter_column('c0_oauth_grants', 'expires_at', nullable=True)
    op.add_column('c0_oauth_grants', sa.Column('persistent', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('c0_oauth_grants', sa.Column('idle_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('c0_oauth_grants', sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('c0_oauth_grants', sa.Column('refresh_family', sa.String(24), nullable=True))
    op.add_column('c0_oauth_grants', sa.Column('refresh_generation', sa.BigInteger(), nullable=False, server_default='0'))
    op.create_index('ix_oauth_persistent_family', 'c0_oauth_grants', ['refresh_family'], unique=True)
    op.create_check_constraint('ck_oauth_grant_lifetime', 'c0_oauth_grants',
        "(persistent AND expires_at IS NULL AND idle_until IS NOT NULL AND refresh_family IS NOT NULL AND native_authority_id IS NOT NULL) OR "
        "(NOT persistent AND expires_at IS NOT NULL AND idle_until IS NULL AND refresh_family IS NULL)")
    op.create_check_constraint('ck_oauth_refresh_generation', 'c0_oauth_grants', 'refresh_generation BETWEEN 0 AND 4294967295')


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
