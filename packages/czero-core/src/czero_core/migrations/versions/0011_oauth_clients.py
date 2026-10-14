# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0011_oauth_clients'
down_revision = '0010_embeddings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_oauth_clients',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('descriptor_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('redirect_uris', JSONB(), nullable=False),
        sa.Column('scopes', JSONB(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('revision BETWEEN 1 AND 2147483646'),
        sa.CheckConstraint("jsonb_typeof(redirect_uris)='array' AND jsonb_array_length(redirect_uris) BETWEEN 1 AND 4"),
        sa.CheckConstraint("jsonb_typeof(scopes)='array' AND jsonb_array_length(scopes) BETWEEN 1 AND 3"))


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
