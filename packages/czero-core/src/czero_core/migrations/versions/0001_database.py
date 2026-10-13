# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0001_database"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("instance_metadata",
        sa.Column("singleton_id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_space_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("singleton_id = 1", name="instance_metadata_singleton"))
    metadata = sa.table("instance_metadata", sa.column("singleton_id", sa.Integer()),
                        sa.column("knowledge_space_id", sa.Uuid()))
    op.execute(metadata.insert().values(singleton_id=1, knowledge_space_id=uuid.uuid4()))


def downgrade():
    # Operator-driven schema downgrades are intentionally unsupported.
    raise RuntimeError("C0 schema downgrades are not supported")
