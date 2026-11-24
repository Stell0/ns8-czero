# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Allow larger original PDFs while preserving other media and extracted-text limits."""
from alembic import op

revision = '0044_pdf_limits'
down_revision = '0043_google_drive_sources'
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TABLE c0_source_versions DROP CONSTRAINT c0_source_versions_size_bytes_check")
    op.execute("""ALTER TABLE c0_source_versions ADD CONSTRAINT c0_source_versions_size_bytes_check
        CHECK (size_bytes >= 1 AND size_bytes <= CASE WHEN media_type='application/pdf'
        THEN 104857600 ELSE 10485760 END)""")


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
