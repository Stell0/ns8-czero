# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""User-owned Google connections and private, preview-bound folder selections."""
from alembic import op

revision = '0043_google_drive_sources'
down_revision = '0042_automatic_sources'
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TABLE c0_automatic_sources DROP CONSTRAINT c0_automatic_sources_kind_check")
    op.execute("""ALTER TABLE c0_automatic_sources ADD CONSTRAINT c0_automatic_sources_kind_check
        CHECK(kind IN ('github','website','google_drive'))""")
    op.execute("""CREATE TABLE c0_drive_connections (
        account_id uuid NOT NULL REFERENCES c0_accounts(id) ON DELETE CASCADE,
        space_id uuid NOT NULL REFERENCES c0_spaces(id) ON DELETE CASCADE,
        generation bigint NOT NULL DEFAULT 1, subject_hash char(64) NOT NULL,
        credential varchar(32768), offline boolean NOT NULL,
        reconnect_required boolean NOT NULL DEFAULT false,
        PRIMARY KEY(account_id,space_id))""")
    op.execute("""CREATE TABLE c0_drive_oauth_states (
        account_id uuid NOT NULL REFERENCES c0_accounts(id) ON DELETE CASCADE,
        space_id uuid NOT NULL REFERENCES c0_spaces(id) ON DELETE CASCADE,
        state_hash char(64) NOT NULL UNIQUE, session_hash char(64) NOT NULL,
        verifier varchar(256) NOT NULL, offline boolean NOT NULL,
        exchanging boolean NOT NULL DEFAULT false, expires_at timestamptz NOT NULL,
        PRIMARY KEY(account_id,space_id))""")
    op.execute("""CREATE TABLE c0_drive_previews (
        account_id uuid NOT NULL, space_id uuid NOT NULL,
        proof_hash char(64) NOT NULL UNIQUE, folder_id varchar(256) NOT NULL,
        generation bigint NOT NULL, definition_id uuid REFERENCES c0_automatic_sources(id) ON DELETE CASCADE,
        revision bigint, expires_at timestamptz NOT NULL,
        PRIMARY KEY(account_id,space_id),
        FOREIGN KEY(account_id,space_id) REFERENCES c0_drive_connections(account_id,space_id) ON DELETE CASCADE)""")
    op.execute("""CREATE TABLE c0_drive_bindings (
        definition_id uuid PRIMARY KEY REFERENCES c0_automatic_sources(id) ON DELETE CASCADE,
        account_id uuid NOT NULL, space_id uuid NOT NULL, generation bigint NOT NULL, folder_id varchar(256) NOT NULL,
        FOREIGN KEY(account_id,space_id) REFERENCES c0_drive_connections(account_id,space_id) ON DELETE CASCADE)""")


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
