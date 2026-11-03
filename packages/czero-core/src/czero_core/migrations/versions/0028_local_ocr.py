# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded current/staging page provenance, without retired body copies."""
from alembic import op

revision='0028_local_ocr'
down_revision='0027_document_structure'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('ALTER TABLE c0_extraction_units ADD COLUMN provenance jsonb, ADD COLUMN provenance_sha256 varchar(64)')
    op.execute("ALTER TABLE c0_extraction_units ADD CONSTRAINT c0_ocr_provenance CHECK ((provenance IS NULL AND (provenance_sha256 IS NULL OR provenance_sha256 ~ '^[0-9a-f]{64}$')) OR (provenance IS NOT NULL AND provenance_sha256 IS NOT NULL AND jsonb_typeof(provenance)='object' AND octet_length(provenance::text)<=2048 AND provenance_sha256 ~ '^[0-9a-f]{64}$'))")


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
