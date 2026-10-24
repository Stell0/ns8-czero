# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa

revision = '0021_workspace_access'
down_revision = '0020_persistent_oauth'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('c0_accounts', sa.Column('access_revision', sa.BigInteger(), nullable=False, server_default='1'))
    op.create_check_constraint('ck_account_access_revision', 'c0_accounts', 'access_revision >= 1')
    op.add_column('c0_client_onboarding', sa.Column('id', sa.Uuid(), nullable=False,
                                                  server_default=sa.text('gen_random_uuid()')))
    op.create_unique_constraint('uq_client_onboarding_id', 'c0_client_onboarding', ['id'])


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
