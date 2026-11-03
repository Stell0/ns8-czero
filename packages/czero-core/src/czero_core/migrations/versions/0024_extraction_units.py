# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Private extraction leases; migration never schedules existing documents."""
from alembic import op

revision = '0024_extraction_units'
down_revision = '0023_current_content'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE c0_extraction_runs (
        id uuid PRIMARY KEY, space_id uuid NOT NULL, version_id uuid NOT NULL,
        actor_id uuid REFERENCES c0_accounts(id) ON DELETE SET NULL,
        processing_generation integer NOT NULL CHECK(processing_generation>=1),
        original_sha256 varchar(64) NOT NULL CHECK(original_sha256 ~ '^[0-9a-f]{64}$'),
        manifest_sha256 varchar(64) NOT NULL CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
        profile jsonb NOT NULL CHECK(jsonb_typeof(profile)='object' AND octet_length(profile::text)<=16384),
        expected_units integer NOT NULL CHECK(expected_units BETWEEN 1 AND 4000),
        state varchar(16) NOT NULL CHECK(state IN ('staging','extracting','assembling','ready','failed','superseded')),
        error_code varchar(32), created_at timestamptz NOT NULL DEFAULT now(),
        expires_at timestamptz NOT NULL, revision integer NOT NULL DEFAULT 1 CHECK(revision>=1),
        claimed integer NOT NULL DEFAULT 0 CHECK(claimed>=0),
        succeeded integer NOT NULL DEFAULT 0 CHECK(succeeded>=0),
        failed integer NOT NULL DEFAULT 0 CHECK(failed>=0),
        retried integer NOT NULL DEFAULT 0 CHECK(retried>=0),
        result_bytes integer NOT NULL DEFAULT 0 CHECK(result_bytes BETWEEN 0 AND 2097152),
        result_characters integer NOT NULL DEFAULT 0 CHECK(result_characters BETWEEN 0 AND 1000000),
        UNIQUE(space_id,id), UNIQUE(version_id,processing_generation),
        FOREIGN KEY(space_id,version_id) REFERENCES c0_source_versions(space_id,id) ON DELETE CASCADE
    )""")
    op.execute("""CREATE TABLE c0_extraction_units (
        id uuid PRIMARY KEY, space_id uuid NOT NULL, run_id uuid NOT NULL,
        ordinal integer NOT NULL CHECK(ordinal BETWEEN 1 AND 4000),
        locator jsonb NOT NULL CHECK(jsonb_typeof(locator)='object' AND octet_length(locator::text)<=16384),
        input_sha256 varchar(64) NOT NULL CHECK(input_sha256 ~ '^[0-9a-f]{64}$'),
        state varchar(16) NOT NULL DEFAULT 'queued'
            CHECK(state IN ('queued','leased','succeeded','retry_wait','failed','cancelled')),
        attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
        fence integer NOT NULL DEFAULT 0 CHECK(fence>=0),
        lease_token uuid, lease_deadline timestamptz, available_at timestamptz NOT NULL DEFAULT now(),
        error_code varchar(32), started_at timestamptz, finished_at timestamptz,
        body text CHECK(char_length(body)<=1000000 AND octet_length(body)<=2097152),
        locations jsonb CHECK(jsonb_typeof(locations)='array' AND jsonb_array_length(locations)<=4000),
        result_sha256 varchar(64) CHECK(result_sha256 ~ '^[0-9a-f]{64}$'),
        text_sha256 varchar(64) CHECK(text_sha256 ~ '^[0-9a-f]{64}$'),
        UNIQUE(run_id,ordinal),
        FOREIGN KEY(space_id,run_id) REFERENCES c0_extraction_runs(space_id,id) ON DELETE CASCADE,
        CHECK((state='leased')=(lease_deadline IS NOT NULL)),
        CHECK(state NOT IN ('leased','succeeded') OR lease_token IS NOT NULL),
        CHECK((state='succeeded')=(body IS NOT NULL AND locations IS NOT NULL
              AND result_sha256 IS NOT NULL AND text_sha256 IS NOT NULL)),
        CHECK(state='succeeded' OR (body IS NULL AND locations IS NULL AND result_sha256 IS NULL AND text_sha256 IS NULL))
    )""")
    op.execute("CREATE INDEX c0_extraction_runs_due ON c0_extraction_runs(created_at,id) WHERE state='extracting'")
    op.execute('CREATE INDEX c0_extraction_runs_expiry ON c0_extraction_runs(expires_at,id)')
    op.execute('CREATE INDEX c0_extraction_units_due ON c0_extraction_units(run_id,state,available_at,ordinal)')
    op.execute("CREATE INDEX c0_extraction_units_leases ON c0_extraction_units(lease_deadline) WHERE state='leased'")
    for table in ('c0_extraction_runs', 'c0_extraction_units'):
        op.execute('CREATE TRIGGER c0_current_writer BEFORE INSERT OR UPDATE OR DELETE ON ' + table +
                   ' FOR EACH ROW EXECUTE FUNCTION c0_current_writer()')


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
