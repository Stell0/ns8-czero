# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Payload-free publication markers and lifetime extraction attempt counts."""
from alembic import op
from sqlalchemy import text

revision='0025_pdf_units'
down_revision='0024_extraction_units'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('ALTER TABLE c0_extraction_units ADD COLUMN lifetime_attempts integer NOT NULL DEFAULT 0 CHECK(lifetime_attempts>=0)')
    op.execute('UPDATE c0_extraction_units SET lifetime_attempts=attempts')
    connection=op.get_bind()
    # PostgreSQL names the original inline CHECKs. Select their definitions,
    # leaving ordinal, ownership, size and counter constraints untouched.
    names=connection.execute(text("""SELECT conname FROM pg_constraint
        WHERE conrelid='c0_extraction_units'::regclass AND contype='c'
        AND pg_get_constraintdef(oid) LIKE '%state%'""")).scalars().all()
    for name in names: op.drop_constraint(name,'c0_extraction_units',type_='check')
    op.execute("""ALTER TABLE c0_extraction_units
        ADD CONSTRAINT c0_unit_state CHECK(state IN ('queued','leased','succeeded','retry_wait','failed','cancelled','published')),
        ADD CONSTRAINT c0_unit_deadline CHECK((state='leased')=(lease_deadline IS NOT NULL)),
        ADD CONSTRAINT c0_unit_token CHECK(state NOT IN ('leased','succeeded') OR lease_token IS NOT NULL),
        ADD CONSTRAINT c0_unit_body CHECK((state='succeeded')=(body IS NOT NULL AND locations IS NOT NULL)),
        ADD CONSTRAINT c0_unit_no_partial CHECK(state='succeeded' OR (body IS NULL AND locations IS NULL)),
        ADD CONSTRAINT c0_unit_hash CHECK((state IN ('succeeded','published'))=(result_sha256 IS NOT NULL AND text_sha256 IS NOT NULL)),
        ADD CONSTRAINT c0_unit_no_hash CHECK(state IN ('succeeded','published') OR (result_sha256 IS NULL AND text_sha256 IS NULL))""")


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
