# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Current-document derivatives only; no body or index backfill."""
from alembic import op

revision='0027_document_structure'
down_revision='0026_extraction_pool'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("ALTER TABLE c0_documents ADD COLUMN structure jsonb CHECK(structure IS NULL OR (jsonb_typeof(structure)='object' AND octet_length(structure::text)<=2097152))")
    op.execute("ALTER TABLE c0_documents ADD COLUMN chunking_profile text NOT NULL DEFAULT 'fixed-v1' CHECK(chunking_profile IN ('fixed-v1','sections-v1'))")
    op.execute("ALTER TABLE c0_chunks ADD COLUMN section_context jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(section_context)='array' AND jsonb_array_length(section_context)<=6)")


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
