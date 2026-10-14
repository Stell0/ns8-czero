# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

revision = '0006_sources'
down_revision = '0005_objects'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_sources',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('ingest_key', sa.String(64), nullable=False, unique=True),
        sa.Column('title', sa.String(256), nullable=False),
        sa.Column('metadata', JSONB(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('revision >= 1'),
        sa.CheckConstraint("jsonb_typeof(metadata)='object' AND octet_length(metadata::text)<=32768"))
    op.create_index('c0_sources_created', 'c0_sources', ['created_at', 'id'])
    op.create_table('c0_source_versions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('source_id', sa.Uuid(), sa.ForeignKey('c0_sources.id'), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('media_type', sa.String(128), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(16), nullable=False, server_default='queued'),
        sa.Column('error_code', sa.String(32)),
        sa.Column('retain_original', sa.Boolean(), nullable=False),
        sa.Column('original_present', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('generation', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('c0_jobs.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('source_id', 'number'),
        sa.UniqueConstraint('source_id', 'content_hash'),
        sa.CheckConstraint("state IN ('queued','ready','failed')"),
        sa.CheckConstraint('number >= 1 AND generation >= 1'),
        sa.CheckConstraint('size_bytes BETWEEN 1 AND 10485760'))
    op.create_table('c0_documents',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('version_id', sa.Uuid(), sa.ForeignKey('c0_source_versions.id'), nullable=False, unique=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('text_hash', sa.String(64), nullable=False),
        sa.Column('locations', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('char_length(body) BETWEEN 1 AND 1000000 AND octet_length(body)<=2097152'),
        sa.CheckConstraint("jsonb_typeof(locations)='array' AND jsonb_array_length(locations)<=4000"))
    op.create_table('c0_chunks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('document_id', sa.Uuid(), sa.ForeignKey('c0_documents.id'), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('start_offset', sa.Integer(), nullable=False),
        sa.Column('end_offset', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('locations', JSONB(), nullable=False),
        sa.Column('search_vector', TSVECTOR(), sa.Computed("to_tsvector('simple'::regconfig, body)", persisted=True)),
        sa.UniqueConstraint('document_id', 'ordinal'),
        sa.CheckConstraint('ordinal >= 0 AND start_offset >= 0 AND end_offset > start_offset'),
        sa.CheckConstraint('char_length(body)=end_offset-start_offset AND char_length(body)<=4096'))
    op.create_index('c0_chunks_search', 'c0_chunks', ['search_vector'], postgresql_using='gin')


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
