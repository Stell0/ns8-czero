# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fence browser login attempts and record bounded consent decisions."""
from alembic import op

revision = '0048_consent_flows'
down_revision = '0047_collection_diagnostics'
branch_labels = depends_on = None


def upgrade():
    op.execute("""ALTER TABLE c0_login_states
        ADD COLUMN return_target varchar(2048),
        ADD COLUMN prior_session_hash varchar(64),
        ADD COLUMN owner_hash varchar(64),
        ADD COLUMN successor_session_hash varchar(64),
        ADD COLUMN prior_csrf_hash varchar(64),
        ADD COLUMN prior_native_id uuid,
        ADD COLUMN claimed boolean NOT NULL DEFAULT false""")
    op.execute("""ALTER TABLE c0_oauth_consent
        ADD COLUMN request_fingerprint varchar(64),
        ADD COLUMN state_hash varchar(64),
        ADD COLUMN decision boolean""")


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
