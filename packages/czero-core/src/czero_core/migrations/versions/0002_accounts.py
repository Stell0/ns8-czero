# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa

revision = "0002_accounts"
down_revision = "0001_database"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("c0_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("issuer", sa.String(1024), nullable=False),
        sa.Column("account_key", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("issuer", "account_key", name="c0_accounts_identity"))
    op.create_table("c0_memberships",
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("c0_accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.CheckConstraint("role IN ('reader', 'editor', 'admin')", name="c0_memberships_role"))


def downgrade():
    raise RuntimeError("C0 schema downgrades are not supported")
