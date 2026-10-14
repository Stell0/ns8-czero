# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0008_knowledge_graph'
down_revision = '0007_wiki'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_claims',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('entity_id', sa.Uuid(), sa.ForeignKey('c0_entities.id'), nullable=False),
        sa.Column('page_id', sa.Uuid(), sa.ForeignKey('c0_wiki_pages.id')),
        sa.Column('predicate', sa.String(64), nullable=False),
        sa.Column('value', JSONB(), nullable=False),
        sa.Column('metadata', JSONB(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True)),
        sa.Column('valid_to', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('revision >= 1'),
        sa.CheckConstraint('valid_from IS NULL OR valid_to IS NULL OR valid_to >= valid_from'),
        sa.CheckConstraint("jsonb_typeof(value)='object' AND octet_length(value::text)<=32768"),
        sa.CheckConstraint("jsonb_typeof(metadata)='object' AND octet_length(metadata::text)<=32768"))
    op.create_index('c0_claims_entity', 'c0_claims', ['entity_id', 'predicate', 'id'])
    op.create_index('c0_claims_page', 'c0_claims', ['page_id'])
    op.create_table('c0_evidence_links',
        sa.Column('claim_id', sa.Uuid(), sa.ForeignKey('c0_claims.id'), primary_key=True),
        sa.Column('chunk_id', sa.Uuid(), sa.ForeignKey('c0_chunks.id'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('c0_evidence_links_chunk', 'c0_evidence_links', ['chunk_id'])
    op.create_table('c0_relations',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('source_id', sa.Uuid(), sa.ForeignKey('c0_entities.id'), nullable=False),
        sa.Column('target_id', sa.Uuid(), sa.ForeignKey('c0_entities.id'), nullable=False),
        sa.Column('kind', sa.String(64), nullable=False),
        sa.Column('metadata', JSONB(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('source_id', 'target_id', 'kind'),
        sa.CheckConstraint('source_id <> target_id AND revision >= 1'),
        sa.CheckConstraint("jsonb_typeof(metadata)='object' AND octet_length(metadata::text)<=32768"))
    op.create_index('c0_relations_target', 'c0_relations', ['target_id'])
    op.create_table('c0_entity_links',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('entity_id', sa.Uuid(), sa.ForeignKey('c0_entities.id'), nullable=False),
        sa.Column('target_kind', sa.String(24), nullable=False),
        sa.Column('target_id', sa.Uuid(), nullable=False),
        sa.Column('label_snapshot', sa.String(256), nullable=False),
        sa.Column('object_id', sa.Uuid(), sa.ForeignKey('c0_objects.id', ondelete='SET NULL')),
        sa.Column('page_id', sa.Uuid(), sa.ForeignKey('c0_wiki_pages.id')),
        sa.Column('source_id', sa.Uuid(), sa.ForeignKey('c0_sources.id')),
        sa.Column('document_id', sa.Uuid(), sa.ForeignKey('c0_documents.id')),
        sa.Column('chunk_id', sa.Uuid(), sa.ForeignKey('c0_chunks.id')),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('entity_id', 'target_kind', 'target_id'),
        sa.CheckConstraint("target_kind IN ('object','page','source','document','chunk')"),
        # Object deletion remains compatible: its stable target ID/snapshot
        # survives and the cleared FK explicitly represents missing data.
        sa.CheckConstraint("(target_kind='object' AND (object_id IS NULL OR object_id=target_id) AND page_id IS NULL AND source_id IS NULL AND document_id IS NULL AND chunk_id IS NULL) OR "
            "(target_kind='page' AND page_id IS NOT NULL AND page_id=target_id AND object_id IS NULL AND source_id IS NULL AND document_id IS NULL AND chunk_id IS NULL) OR "
            "(target_kind='source' AND source_id IS NOT NULL AND source_id=target_id AND object_id IS NULL AND page_id IS NULL AND document_id IS NULL AND chunk_id IS NULL) OR "
            "(target_kind='document' AND document_id IS NOT NULL AND document_id=target_id AND object_id IS NULL AND page_id IS NULL AND source_id IS NULL AND chunk_id IS NULL) OR "
            "(target_kind='chunk' AND chunk_id IS NOT NULL AND chunk_id=target_id AND object_id IS NULL AND page_id IS NULL AND source_id IS NULL AND document_id IS NULL)"))
    op.create_index('c0_entity_links_target', 'c0_entity_links', ['target_kind', 'target_id'])


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
