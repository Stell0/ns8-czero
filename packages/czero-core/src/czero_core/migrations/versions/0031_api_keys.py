# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Personal scoped automation credentials; no existing authority is changed."""
from alembic import op
revision = '0031_api_keys'
down_revision = '0030_explicit_reindex'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE c0_api_keys (
        id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES c0_accounts(id) ON DELETE CASCADE,
        digest text NOT NULL UNIQUE, configuration text NOT NULL, name varchar(128) NOT NULL,
        scopes text[] NOT NULL, space_ids uuid[] NOT NULL,
        created_at timestamptz NOT NULL, expires_at timestamptz,
        revoked_at timestamptz, last_used_at timestamptz,
        CHECK (cardinality(scopes) BETWEEN 1 AND 2),
        CHECK (scopes <@ ARRAY['c0:read','c0:write']::text[]),
        CHECK (cardinality(space_ids) BETWEEN 1 AND 100),
        CHECK (expires_at IS NULL OR expires_at > created_at))""")
    op.execute('CREATE INDEX c0_api_keys_account ON c0_api_keys(account_id)')


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
