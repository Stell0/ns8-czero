# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Private publication ordering and bounded maintenance metadata; no bodies."""
from alembic import op

revision = '0034_compilation_maintenance'
down_revision = '0033_compilation_state'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE SEQUENCE c0_compilation_publications')
    for table in ('c0_sources', 'c0_objects'):
        op.execute(f'ALTER TABLE {table} ADD COLUMN compilation_publication bigint')
    op.execute("UPDATE c0_sources SET compilation_publication=nextval('c0_compilation_publications')")
    op.execute("UPDATE c0_objects SET compilation_publication=nextval('c0_compilation_publications') WHERE type_name='c0_project_source_snapshot_v1'")
    op.execute("CREATE INDEX c0_compilation_part_source ON c0_objects(space_id,(data->>'source_id')) WHERE type_name IN ('c0_project_source_part_v1','c0_project_source_sync_v1')")
    op.execute("CREATE INDEX c0_compilation_snapshot_identity ON c0_objects(space_id,(data->>'connector_id'),(data->>'external_id')) WHERE type_name='c0_project_source_snapshot_v1'")
    op.execute('CREATE INDEX c0_sources_publication ON c0_sources(space_id,compilation_publication,id)')
    op.execute("CREATE INDEX c0_objects_publication ON c0_objects(space_id,compilation_publication,id) WHERE type_name='c0_project_source_snapshot_v1'")
    op.execute("""CREATE FUNCTION c0_compilation_publication() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_TABLE_NAME='c0_sources' THEN
          IF TG_OP='INSERT' OR NEW.current_version_id IS DISTINCT FROM OLD.current_version_id
            OR NEW.deleted IS DISTINCT FROM OLD.deleted OR NEW.metadata IS DISTINCT FROM OLD.metadata THEN
            NEW.compilation_publication=nextval('c0_compilation_publications');
          END IF;
        ELSIF NEW.type_name='c0_project_source_snapshot_v1' THEN
          IF TG_OP='INSERT' OR NEW.data IS DISTINCT FROM OLD.data OR NEW.revision IS DISTINCT FROM OLD.revision THEN
            NEW.compilation_publication=nextval('c0_compilation_publications');
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    for table in ('c0_sources', 'c0_objects'):
        op.execute(f'CREATE TRIGGER c0_compilation_publication BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION c0_compilation_publication()')
    op.execute("""CREATE FUNCTION c0_compilation_parent_publication() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.compilation_publication IS DISTINCT FROM OLD.compilation_publication THEN
          UPDATE c0_objects parent SET compilation_publication=nextval('c0_compilation_publications')
          FROM c0_objects receipt WHERE receipt.space_id=NEW.space_id
            AND receipt.type_name='c0_project_source_part_v1' AND receipt.data->>'source_id'=NEW.id::text
            AND parent.space_id=NEW.space_id AND parent.type_name='c0_project_source_snapshot_v1'
            AND parent.data->>'connector_id'=receipt.data->>'connector_id'
            AND parent.data->>'external_id'=receipt.data->>'parent_external_id'
            AND parent.data->'part_receipt_ids' @> jsonb_build_array(receipt.id::text);
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER c0_compilation_parent_publication AFTER UPDATE ON c0_sources FOR EACH ROW EXECUTE FUNCTION c0_compilation_parent_publication()')
    # Extend only the predecessor's kind/state/lease checks; retain budget guards.
    for name, expression in {
        'kind_check': "kind IN ('manual','bootstrap','retrieval','daily','weekly','budget_day','budget_week','inventory','semantic_cursor')",
        'state_check': "state IN ('running','partial','blocked','complete','budget','cursor')",
        'check3': """((state='budget' AND window_start IS NOT NULL AND window_end IS NOT NULL
          AND isfinite(window_start) AND isfinite(window_end) AND window_end>window_start
          AND lease_expiry IS NULL AND invocation_deadline IS NULL AND attempts=0)
          OR (state NOT IN ('budget','cursor') AND window_start IS NULL AND window_end IS NULL
          AND lease_expiry IS NOT NULL AND invocation_deadline IS NOT NULL
          AND isfinite(lease_expiry) AND isfinite(invocation_deadline) AND lease_expiry<=invocation_deadline)
          OR (state='cursor' AND lease_expiry IS NULL AND invocation_deadline IS NULL AND attempts=0
          AND window_start IS NULL AND window_end IS NULL))""",
    }.items():
        op.execute(f'ALTER TABLE c0_compilation_runs DROP CONSTRAINT c0_compilation_runs_{name}')
        op.execute(f'ALTER TABLE c0_compilation_runs ADD CONSTRAINT c0_compilation_runs_{name} CHECK ({expression})')
    op.execute("ALTER TABLE c0_compilation_runs ADD CONSTRAINT c0_compilation_cursor_kind CHECK ((state='cursor')=(kind IN ('inventory','semantic_cursor')))")
    op.execute("ALTER TABLE c0_compilation_tasks ADD COLUMN purpose varchar(24) NOT NULL DEFAULT 'knowledge' CHECK(purpose IN ('knowledge','source_assessment'))")
    op.execute("ALTER TABLE c0_compilation_tasks ADD COLUMN assessment jsonb NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(assessment)='object' AND octet_length(assessment::text)<=16384)")
    op.execute('ALTER TABLE c0_compilation_tasks DROP CONSTRAINT c0_compilation_tasks_state_check')
    op.execute("""ALTER TABLE c0_compilation_tasks ADD CONSTRAINT c0_compilation_tasks_state_check
      CHECK(state IN ('queued','leased','planned','needs_review','deferred','conflict','failed','uncertain',
        'superseded','no_change','applied_pending_verify','succeeded','assessed'))""")
    op.execute('ALTER TABLE c0_compilation_sources ADD COLUMN assessment_task_id uuid, ADD COLUMN seen_sweep_id uuid, ADD COLUMN publication_marker bigint')
    op.execute('ALTER TABLE c0_compilation_sources ADD FOREIGN KEY(space_id,assessment_task_id) REFERENCES c0_compilation_tasks(space_id,id)')
    op.execute('CREATE INDEX c0_compilation_sources_sweep ON c0_compilation_sources(space_id,profile_id,logical_document_id)')
    op.execute("CREATE INDEX c0_compilation_assessments ON c0_compilation_tasks(space_id,purpose,state,id) WHERE purpose='source_assessment'")


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
