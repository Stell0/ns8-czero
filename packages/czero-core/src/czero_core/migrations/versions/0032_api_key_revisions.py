# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bind keys to revisions understood by older permission writers."""
from alembic import op
revision = '0032_api_key_revisions'
down_revision = '0031_api_keys'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE c0_api_keys ADD COLUMN account_revision bigint NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE c0_api_keys ADD COLUMN space_revisions jsonb NOT NULL DEFAULT '{}'::jsonb")
    # Historical issuance revisions cannot be reconstructed from current grants.
    # Never promote credentials from the preserved first producer candidate.
    op.execute('UPDATE c0_api_keys SET revoked_at=COALESCE(revoked_at,now())')
    op.execute('ALTER TABLE c0_api_keys ALTER COLUMN account_revision DROP DEFAULT')
    op.execute('ALTER TABLE c0_api_keys ALTER COLUMN space_revisions DROP DEFAULT')


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
