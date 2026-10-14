# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0007_wiki'
down_revision = '0006_sources'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_wiki_pages',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('slug', sa.String(128), nullable=False, unique=True),
        sa.Column('title', sa.String(256), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('revision >= 1'))
    op.create_index('c0_wiki_pages_updated', 'c0_wiki_pages', ['updated_at', 'id'])
    op.create_table('c0_wiki_revisions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('page_id', sa.Uuid(), sa.ForeignKey('c0_wiki_pages.id'), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(256), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('metadata', JSONB(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('page_id', 'number'),
        sa.CheckConstraint('number >= 1 AND octet_length(body)<=131072'),
        sa.CheckConstraint("jsonb_typeof(metadata)='object' AND octet_length(metadata::text)<=32768"))
    op.create_table('c0_entities',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('kind', sa.String(64), nullable=False),
        sa.Column('label', sa.String(128), nullable=False),
        sa.Column('metadata', JSONB(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('revision >= 1'),
        sa.CheckConstraint("jsonb_typeof(metadata)='object' AND octet_length(metadata::text)<=32768"))
    op.create_index('c0_entities_kind', 'c0_entities', ['kind', 'label', 'id'])
    op.create_table('c0_entity_aliases',
        sa.Column('normalized', sa.String(256), primary_key=True),
        sa.Column('entity_id', sa.Uuid(), sa.ForeignKey('c0_entities.id'), nullable=False),
        sa.Column('label', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('c0_entity_aliases_entity', 'c0_entity_aliases', ['entity_id'])
    op.create_table('c0_knowledge_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('resource_id', sa.Uuid(), nullable=False),
        sa.Column('operation', sa.String(32), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('revision >= 1'))
    op.create_index('c0_knowledge_events_resource', 'c0_knowledge_events', ['kind', 'resource_id', 'id'])
    op.create_table('c0_knowledge_receipts',
        sa.Column('actor_id', sa.Uuid(), primary_key=True),
        sa.Column('key', sa.String(128), primary_key=True),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('result', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("jsonb_typeof(result)='object' AND octet_length(result::text)<=1048576"))


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
