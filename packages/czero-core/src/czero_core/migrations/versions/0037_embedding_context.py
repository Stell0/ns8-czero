# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Version contextual inputs and retire vectors when their labels change."""
from alembic import op

revision = '0037_embedding_context'
down_revision = '0036_document_bm25'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE c0_embedding_profiles ADD COLUMN input_format text
        NOT NULL DEFAULT 'legacy' CHECK(input_format IN ('legacy','context-v1'))""")
    op.execute("""
    CREATE FUNCTION c0_embedding_context_invalidate() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.title IS DISTINCT FROM OLD.title OR NEW.metadata IS DISTINCT FROM OLD.metadata THEN
        IF TG_TABLE_NAME='c0_sources' THEN
          DELETE FROM c0_embeddings e USING c0_chunks c,c0_documents d,c0_source_versions v,c0_embedding_profiles p
          WHERE e.source_chunk_id=c.id AND c.document_id=d.id AND d.version_id=v.id
            AND v.source_id=NEW.id AND e.profile_id=p.id AND p.input_format='context-v1';
        ELSE
          DELETE FROM c0_embeddings e USING c0_wiki_chunks w,c0_embedding_profiles p
          WHERE e.wiki_chunk_id=w.id AND w.revision_id=NEW.id
            AND e.profile_id=p.id AND p.input_format='context-v1';
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER c0_source_embedding_context AFTER UPDATE OF title,metadata ON c0_sources
      FOR EACH ROW EXECUTE FUNCTION c0_embedding_context_invalidate();
    CREATE TRIGGER c0_wiki_embedding_context AFTER UPDATE OF title,metadata ON c0_wiki_revisions
      FOR EACH ROW EXECUTE FUNCTION c0_embedding_context_invalidate();
    """)


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
