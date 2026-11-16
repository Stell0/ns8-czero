# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Immutable directory owners and payload-free managed import state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0040_personal_data'
down_revision = '0039_space_audiences'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('c0_spaces', sa.Column('personal', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.drop_constraint('c0_spaces_name_key', 'c0_spaces', type_='unique')
    op.create_index('c0_spaces_ordinary_name', 'c0_spaces', ['name'], unique=True,
                    postgresql_where=sa.text('NOT personal'))
    op.create_check_constraint('c0_spaces_personal_private', 'c0_spaces', 'NOT personal OR (NOT shared AND NOT readable_by_all)')
    op.create_table('c0_personal_config',
        sa.Column('issuer', sa.Text(), primary_key=True),
        sa.Column('provider_id', sa.Uuid(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('generation', sa.BigInteger(), nullable=False, server_default='1'),
        sa.Column('services', JSONB(), nullable=False, server_default='{}'),
        sa.Column('runner_cursor', sa.Uuid()),
        sa.Column('validated', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint('generation > 0'),
        sa.CheckConstraint("jsonb_typeof(services)='object' AND octet_length(services::text)<=4096"))
    op.create_table('c0_personal_owners',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('issuer', sa.Text(), sa.ForeignKey('c0_personal_config.issuer'), nullable=False),
        sa.Column('provider_id', sa.Uuid(), nullable=False),
        sa.Column('directory_id', sa.Uuid(), nullable=False),
        sa.Column('space_id', sa.Uuid(), sa.ForeignKey('c0_spaces.id'), nullable=False, unique=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('username', sa.String(128), nullable=False),
        sa.UniqueConstraint('provider_id', 'directory_id'))
    op.create_table('c0_personal_imports',
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('c0_personal_owners.id'), primary_key=True),
        sa.Column('connector', sa.String(16), primary_key=True),
        sa.Column('instance_id', sa.Uuid(), primary_key=True),
        sa.Column('remote_key', sa.String(512), primary_key=True),
        sa.Column('kind', sa.String(32), primary_key=True),
        sa.Column('source_id', sa.Uuid(), sa.ForeignKey('c0_sources.id'), unique=True),
        sa.Column('source_revision', sa.Integer()),
        sa.Column('version_id', sa.Uuid()),
        sa.Column('slot_key', sa.String(512)),
        sa.Column('identity_kind', sa.String(32)),
        sa.Column('generation', sa.BigInteger(), nullable=False, server_default='1'),
        sa.Column('content_hash', sa.String(64)),
        sa.Column('state', sa.String(16), nullable=False, server_default='managed'),
        sa.Column('last_seen_scan', sa.Uuid()),
        sa.CheckConstraint("connector IN ('nethvoice','webtop')"),
        sa.CheckConstraint("state IN ('managed','overridden','excluded','cleanup','removed')"))
    op.create_table('c0_personal_issues',
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('c0_personal_owners.id'), primary_key=True),
        sa.Column('connector', sa.String(16), primary_key=True),
        sa.Column('instance_id', sa.Uuid(), primary_key=True),
        sa.Column('remote_key', sa.String(512), primary_key=True),
        sa.Column('attachment_id', sa.String(128), primary_key=True),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table('c0_personal_checkpoints',
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('c0_personal_owners.id'), primary_key=True),
        sa.Column('connector', sa.String(16), primary_key=True),
        sa.Column('instance_id', sa.Uuid(), primary_key=True),
        sa.Column('generation', sa.BigInteger(), nullable=False),
        sa.Column('cursor', JSONB(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(32), nullable=False, server_default='unverified'),
        sa.Column('last_success', sa.DateTime(timezone=True)),
        sa.Column('last_inventory', sa.DateTime(timezone=True)),
        sa.Column('error_code', sa.String(64)),
        sa.CheckConstraint("connector IN ('nethvoice','webtop')"),
        sa.CheckConstraint("jsonb_typeof(cursor)='object' AND octet_length(cursor::text)<=4096"))


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
