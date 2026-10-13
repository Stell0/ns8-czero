# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa

revision = "0003_sessions"
down_revision = "0002_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("c0_login_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("issuer", sa.String(1024), nullable=False),
        sa.Column("client_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("c0_login_states_expiry", "c0_login_states", ["expires_at"])
    op.create_table("c0_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("c0_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("csrf_token", sa.String(128), nullable=False),
        sa.Column("issuer", sa.String(1024), nullable=False),
        sa.Column("client_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("c0_sessions_expiry", "c0_sessions", ["expires_at"])


def downgrade():
    raise RuntimeError("C0 schema downgrades are not supported")
