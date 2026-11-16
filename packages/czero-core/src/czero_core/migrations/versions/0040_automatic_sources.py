# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op

revision = '0040_automatic_sources'
down_revision = '0039_space_audiences'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE c0_automatic_sources (
        id uuid PRIMARY KEY, space_id uuid NOT NULL REFERENCES c0_spaces(id),
        name varchar(256) NOT NULL, kind varchar(16) NOT NULL CHECK(kind IN ('github','website')),
        config jsonb NOT NULL CHECK(octet_length(config::text)<=32768),
        enabled boolean NOT NULL, interval_seconds integer CHECK(interval_seconds BETWEEN 300 AND 2678400),
        run_number bigint NOT NULL DEFAULT 0, retry_count integer NOT NULL DEFAULT 0, revision bigint NOT NULL DEFAULT 1, owner_id uuid NOT NULL REFERENCES c0_accounts(id),
        authority_revision bigint NOT NULL, space_revision bigint NOT NULL, grant_revision bigint NOT NULL,
        next_run_at timestamptz, last_success_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    )''')
    op.execute('''CREATE INDEX c0_automatic_sources_due ON c0_automatic_sources(next_run_at) WHERE enabled''')
    op.execute('''CREATE TABLE c0_source_update_runs (
        id uuid PRIMARY KEY, definition_id uuid NOT NULL REFERENCES c0_automatic_sources(id) ON DELETE CASCADE,
        number bigint NOT NULL, revision bigint NOT NULL, state varchar(16) NOT NULL DEFAULT 'queued'
            CHECK(state IN ('queued','running','pending','complete','partial','blocked','failed','cancelled')),
        cursor jsonb NOT NULL DEFAULT '{}', error_code varchar(64),
        lease uuid, lease_until timestamptz, processed integer NOT NULL DEFAULT 0,
        available_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
        UNIQUE(definition_id,number)
    )''')
    op.execute("CREATE INDEX c0_source_update_retired ON c0_source_update_runs(created_at,id) WHERE state NOT IN ('queued','running','pending')")
    op.execute("CREATE UNIQUE INDEX c0_source_update_active ON c0_source_update_runs(definition_id) WHERE state IN ('queued','running','pending')")
    op.execute('''CREATE TABLE c0_automatic_source_items (
        definition_id uuid NOT NULL REFERENCES c0_automatic_sources(id) ON DELETE CASCADE,
        external_key varchar(64) NOT NULL, source_id uuid NOT NULL REFERENCES c0_sources(id),
        source_revision integer NOT NULL, version_id uuid NOT NULL,
        content_hash varchar(64) NOT NULL,
        PRIMARY KEY(definition_id,external_key)
    )''')


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
