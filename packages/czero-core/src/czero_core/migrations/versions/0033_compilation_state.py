# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Add empty, disabled-by-default metadata-only compilation coordination."""
from alembic import op

revision = '0033_compilation_state'
down_revision = '0032_api_key_revisions'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE c0_compilation_policies (
        space_id uuid PRIMARY KEY REFERENCES c0_spaces(id) ON DELETE CASCADE,
        revision integer NOT NULL CHECK (revision BETWEEN 1 AND 2147483646),
        data jsonb NOT NULL CHECK (jsonb_typeof(data)='object' AND octet_length(data::text)<=16384),
        actor_id uuid NOT NULL, updated_at timestamptz NOT NULL)''')
    op.execute('''CREATE TABLE c0_compilation_runs (
        id uuid PRIMARY KEY, space_id uuid NOT NULL REFERENCES c0_compilation_policies(space_id) ON DELETE CASCADE,
        kind varchar(16) NOT NULL CHECK (kind IN ('manual','bootstrap','retrieval','daily','weekly','budget_day','budget_week')),
        cycle_key varchar(128) NOT NULL, revision integer NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 2147483646),
        state varchar(16) NOT NULL CHECK (state IN ('running','partial','blocked','complete','budget')),
        policy_revision integer NOT NULL CHECK (policy_revision BETWEEN 1 AND 2147483646), actor_id uuid NOT NULL,
        lease_owner varchar(128) NOT NULL DEFAULT '', fencing_generation bigint NOT NULL CHECK (fencing_generation BETWEEN 1 AND 9223372036854775806),
        lease_expiry timestamptz, invocation_deadline timestamptz, database_epoch varchar(64) NOT NULL CHECK (database_epoch ~ '^[0-9a-f]{64}$'),
        attempts integer NOT NULL CHECK (attempts BETWEEN 0 AND 5), started_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
        day_budget_id uuid, week_budget_id uuid, window_start timestamptz, window_end timestamptz,
        data jsonb NOT NULL CHECK (jsonb_typeof(data)='object' AND octet_length(data::text)<=262144),
        UNIQUE(space_id,id), UNIQUE(space_id,kind,cycle_key),
        FOREIGN KEY(space_id,day_budget_id) REFERENCES c0_compilation_runs(space_id,id),
        FOREIGN KEY(space_id,week_budget_id) REFERENCES c0_compilation_runs(space_id,id),
        CHECK ((state='budget')=(kind IN ('budget_day','budget_week'))),
        CHECK (state<>'budget' OR (data ?& ARRAY['caps','requests','charged_tokens','observed_tokens','unknown_requests','usage_unknown']
          AND (data->>'requests')::bigint BETWEEN 0 AND 1000000
          AND (data->>'charged_tokens')::bigint BETWEEN 0 AND 1000000000000
          AND (data->>'observed_tokens')::bigint BETWEEN 0 AND 1000000000000
          AND (data->>'unknown_requests')::bigint BETWEEN 0 AND 1000000)),
        CHECK (isfinite(started_at) AND isfinite(updated_at)),
        CHECK ((state='budget' AND window_start IS NOT NULL AND window_end IS NOT NULL
          AND isfinite(window_start) AND isfinite(window_end) AND window_end>window_start
          AND lease_expiry IS NULL AND invocation_deadline IS NULL AND attempts=0)
          OR (state<>'budget' AND window_start IS NULL AND window_end IS NULL
          AND lease_expiry IS NOT NULL AND invocation_deadline IS NOT NULL
          AND isfinite(lease_expiry) AND isfinite(invocation_deadline) AND lease_expiry<=invocation_deadline)))''')
    op.execute('CREATE INDEX c0_compilation_runs_active ON c0_compilation_runs(space_id,state,lease_expiry)')
    op.execute('CREATE INDEX c0_compilation_runs_windows ON c0_compilation_runs(space_id,kind,window_end) WHERE state=\'budget\'')
    op.execute('''CREATE TABLE c0_compilation_tasks (
        id uuid PRIMARY KEY, space_id uuid NOT NULL REFERENCES c0_compilation_policies(space_id) ON DELETE CASCADE,
        profile_id varchar(64) NOT NULL, profile_version integer NOT NULL CHECK (profile_version BETWEEN 1 AND 2147483646),
        topic_key varchar(128) NOT NULL, target_key varchar(160) NOT NULL, reason varchar(32) NOT NULL CHECK (reason IN ('missing_concept','incomplete_page','stale_support','distributed_evidence','missing_relationship','terminology_gap','contradiction','applicability_gap','missing_link','source_changed','initial_compilation')),
        origin varchar(16) NOT NULL CHECK (origin IN ('manual','bootstrap','retrieval','daily','weekly')),
        dedup_key varchar(64) NOT NULL CHECK (dedup_key ~ '^[0-9a-f]{64}$'), family_key varchar(64) NOT NULL CHECK (family_key ~ '^[0-9a-f]{64}$'),
        source_bindings jsonb NOT NULL CHECK (jsonb_typeof(source_bindings)='array' AND jsonb_array_length(source_bindings) BETWEEN 1 AND 3 AND octet_length(source_bindings::text)<=16384),
        target jsonb NOT NULL CHECK (jsonb_typeof(target)='object' AND octet_length(target::text)<=4096),
        source_label varchar(160) NOT NULL DEFAULT '',
        state varchar(24) NOT NULL CHECK (state IN ('queued','leased','planned','needs_review','deferred','conflict','failed','uncertain','superseded','no_change','applied_pending_verify','succeeded')),
        revision integer NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 2147483646),
        attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5), prior_attempts integer NOT NULL DEFAULT 0 CHECK (prior_attempts BETWEEN 0 AND 2147483646),
        not_before timestamptz NOT NULL, run_id uuid, fencing_generation bigint NOT NULL DEFAULT 0 CHECK (fencing_generation BETWEEN 0 AND 9223372036854775806),
        policy_revision integer NOT NULL CHECK (policy_revision BETWEEN 1 AND 2147483646), predecessor_id uuid,
        plan_hash varchar(64) CHECK (plan_hash IS NULL OR plan_hash ~ '^[0-9a-f]{64}$'), error_code varchar(64) NOT NULL DEFAULT '',
        created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
        UNIQUE(space_id,id), UNIQUE(space_id,dedup_key),
        FOREIGN KEY(space_id,run_id) REFERENCES c0_compilation_runs(space_id,id),
        FOREIGN KEY(space_id,predecessor_id) REFERENCES c0_compilation_tasks(space_id,id))''')
    op.execute("CREATE UNIQUE INDEX c0_compilation_tasks_family ON c0_compilation_tasks(space_id,family_key) WHERE state IN ('queued','leased','planned','needs_review','deferred','uncertain')")
    op.execute("CREATE INDEX c0_compilation_tasks_pending ON c0_compilation_tasks(space_id,not_before,id) WHERE state IN ('queued','deferred')")
    op.execute('CREATE INDEX c0_compilation_tasks_state ON c0_compilation_tasks(space_id,state,id)')
    op.execute('CREATE INDEX c0_compilation_tasks_topic ON c0_compilation_tasks(space_id,topic_key,profile_id)')
    op.execute('CREATE INDEX c0_compilation_tasks_predecessor ON c0_compilation_tasks(space_id,predecessor_id)')
    op.execute('CREATE INDEX c0_compilation_tasks_run ON c0_compilation_tasks(space_id,run_id,fencing_generation)')
    op.execute('''CREATE TABLE c0_compilation_sources (
        space_id uuid NOT NULL REFERENCES c0_compilation_policies(space_id) ON DELETE CASCADE,
        logical_document_id uuid NOT NULL, profile_id varchar(64) NOT NULL, profile_version integer NOT NULL CHECK (profile_version BETWEEN 1 AND 2147483646),
        observed_revision uuid NOT NULL, source_number integer NOT NULL CHECK (source_number BETWEEN 1 AND 2147483646), multipart boolean NOT NULL,
        text_hash varchar(64) NOT NULL CHECK (text_hash ~ '^[0-9a-f]{64}$'), content_hash varchar(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
        metadata_hash varchar(64) NOT NULL CHECK (metadata_hash ~ '^[0-9a-f]{64}$'), parts_hash varchar(64) NOT NULL CHECK (parts_hash ~ '^[0-9a-f]{64}$'),
        parts jsonb NOT NULL CHECK (jsonb_typeof(parts)='array' AND jsonb_array_length(parts) BETWEEN 1 AND 100 AND octet_length(parts::text)<=262144),
        last_compiled_revision uuid, last_compiled_hash varchar(64) CHECK (last_compiled_hash IS NULL OR last_compiled_hash ~ '^[0-9a-f]{64}$'), last_metadata_hash varchar(64) CHECK (last_metadata_hash IS NULL OR last_metadata_hash ~ '^[0-9a-f]{64}$'), last_parts_hash varchar(64) CHECK (last_parts_hash IS NULL OR last_parts_hash ~ '^[0-9a-f]{64}$'),
        last_compiled_at timestamptz, task_id uuid,
        state varchar(16) NOT NULL CHECK (state IN ('observed','no_change','partial','stale','unavailable')),
        updated_at timestamptz NOT NULL,
        PRIMARY KEY(space_id,logical_document_id,profile_id),
        FOREIGN KEY(space_id,task_id) REFERENCES c0_compilation_tasks(space_id,id))''')
    op.execute('CREATE INDEX c0_compilation_sources_task ON c0_compilation_sources(space_id,task_id)')
    op.execute('CREATE INDEX c0_compilation_sources_state ON c0_compilation_sources(space_id,state,logical_document_id)')
    op.execute('''CREATE TABLE c0_compilation_dependencies (
        id uuid PRIMARY KEY, space_id uuid NOT NULL REFERENCES c0_compilation_policies(space_id) ON DELETE CASCADE, target_kind varchar(16) NOT NULL CHECK (target_kind IN ('page','entity','claim','relation','object')),
        target_id uuid NOT NULL, target_revision integer NOT NULL CHECK (target_revision>0), target_hash varchar(64) NOT NULL CHECK (target_hash ~ '^[0-9a-f]{64}$'),
        target_content_id uuid, logical_document_id uuid NOT NULL, source_revision uuid NOT NULL,
        metadata_hash varchar(64) NOT NULL CHECK (metadata_hash ~ '^[0-9a-f]{64}$'), parts_hash varchar(64) NOT NULL CHECK (parts_hash ~ '^[0-9a-f]{64}$'), text_hash varchar(64) NOT NULL CHECK (text_hash ~ '^[0-9a-f]{64}$'),
        source_id uuid NOT NULL, version_id uuid NOT NULL, document_id uuid NOT NULL, chunk_id uuid,
        evidence_identity varchar(64) NOT NULL CHECK (evidence_identity ~ '^[0-9a-f]{64}$'), chunk_hash varchar(64) CHECK (chunk_hash IS NULL OR chunk_hash ~ '^[0-9a-f]{64}$'), source_hash varchar(64) NOT NULL CHECK (source_hash ~ '^[0-9a-f]{64}$'),
        start_offset integer, end_offset integer, profile_id varchar(64) NOT NULL, profile_version integer NOT NULL CHECK (profile_version BETWEEN 1 AND 2147483646),
        task_id uuid NOT NULL, state varchar(16) NOT NULL CHECK (state IN ('observed','current','stale')),
        managed_target_hash varchar(64) CHECK (managed_target_hash IS NULL OR managed_target_hash ~ '^[0-9a-f]{64}$'), last_verified_at timestamptz, updated_at timestamptz NOT NULL,
        UNIQUE(space_id,target_kind,target_id,logical_document_id,evidence_identity),
        FOREIGN KEY(space_id,task_id) REFERENCES c0_compilation_tasks(space_id,id),
        FOREIGN KEY(space_id,logical_document_id,profile_id) REFERENCES c0_compilation_sources(space_id,logical_document_id,profile_id),
        CHECK ((start_offset IS NULL AND end_offset IS NULL) OR (start_offset>=0 AND end_offset>start_offset)))''')
    op.execute('CREATE INDEX c0_compilation_dependencies_task ON c0_compilation_dependencies(space_id,task_id)')
    op.execute('CREATE INDEX c0_compilation_dependencies_source ON c0_compilation_dependencies(space_id,logical_document_id,source_revision,target_kind,target_id)')
    op.execute('CREATE INDEX c0_compilation_dependencies_target ON c0_compilation_dependencies(space_id,target_kind,target_id,id)')
    op.execute('CREATE INDEX c0_compilation_dependencies_stale ON c0_compilation_dependencies(space_id,state,target_kind,target_id)')
    op.execute('''CREATE TABLE c0_compilation_events (
        id uuid PRIMARY KEY, space_id uuid NOT NULL REFERENCES c0_compilation_policies(space_id) ON DELETE CASCADE,
        actor_id uuid NOT NULL, request_key varchar(64) NOT NULL CHECK (request_key ~ '^[0-9a-f]{64}$'), fingerprint varchar(64) NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
        operation varchar(64) NOT NULL, kind varchar(32) NOT NULL, outcome varchar(64) NOT NULL,
        run_id uuid, task_id uuid, policy_revision integer NOT NULL CHECK (policy_revision BETWEEN 0 AND 2147483646),
        fencing_generation bigint NOT NULL DEFAULT 0 CHECK (fencing_generation BETWEEN 0 AND 9223372036854775806), call_id uuid,
        day_budget_id uuid, week_budget_id uuid,
        metrics jsonb NOT NULL CHECK (jsonb_typeof(metrics)='object' AND octet_length(metrics::text)<=16384),
        created_at timestamptz NOT NULL, UNIQUE(space_id,actor_id,request_key),
        FOREIGN KEY(space_id,run_id) REFERENCES c0_compilation_runs(space_id,id),
        FOREIGN KEY(space_id,task_id) REFERENCES c0_compilation_tasks(space_id,id),
        FOREIGN KEY(space_id,day_budget_id) REFERENCES c0_compilation_runs(space_id,id),
        FOREIGN KEY(space_id,week_budget_id) REFERENCES c0_compilation_runs(space_id,id))''')
    op.execute('CREATE INDEX c0_compilation_events_run ON c0_compilation_events(space_id,run_id,created_at,id)')
    op.execute('CREATE INDEX c0_compilation_events_day ON c0_compilation_events(space_id,day_budget_id,kind)')
    op.execute('CREATE INDEX c0_compilation_events_week ON c0_compilation_events(space_id,week_budget_id,kind)')
    op.execute("CREATE UNIQUE INDEX c0_compilation_events_call ON c0_compilation_events(space_id,call_id) WHERE kind='model_reserve'")


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
