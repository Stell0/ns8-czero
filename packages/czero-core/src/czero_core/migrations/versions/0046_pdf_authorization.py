# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Keep PDF extraction authorization private and tied to one current version."""
from alembic import op

revision = '0046_pdf_authorization'
down_revision = '0045_drive_audience'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE c0_pdf_authorizations (
        version_id uuid PRIMARY KEY REFERENCES c0_source_versions(id) ON DELETE CASCADE,
        space_id uuid NOT NULL,
        approved_by uuid NOT NULL,
        approved_at timestamptz NOT NULL DEFAULT now(),
        restricted boolean NOT NULL,
        sealed_password text CHECK (length(sealed_password) <= 4096)
    )''')


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
