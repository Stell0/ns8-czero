# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa

revision = '0010_embeddings'
down_revision = '0009_retrieval_text'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('c0_embedding_profiles',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('fingerprint',sa.String(64),nullable=False,unique=True),
        sa.Column('model',sa.String(128),nullable=False),
        sa.Column('dimensions',sa.Integer(),nullable=False),
        sa.Column('generation',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint('dimensions BETWEEN 1 AND 2000 AND generation BETWEEN 1 AND 2147483646'))
    op.create_index('c0_embedding_profile_active','c0_embedding_profiles',['active'],unique=True,postgresql_where=sa.text('active'))
    op.create_table('c0_wiki_chunks',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('revision_id',sa.Uuid(),sa.ForeignKey('c0_wiki_revisions.id',ondelete='CASCADE'),nullable=False),
        sa.Column('ordinal',sa.Integer(),nullable=False),
        sa.Column('start_offset',sa.Integer(),nullable=False),
        sa.Column('end_offset',sa.Integer(),nullable=False),
        sa.Column('body',sa.Text(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.UniqueConstraint('revision_id','ordinal'),
        sa.CheckConstraint('ordinal BETWEEN 0 AND 63 AND start_offset>=0 AND end_offset>=start_offset'),
        sa.CheckConstraint('char_length(body)=end_offset-start_offset AND char_length(body)<=3800'))
    # One fixed full-precision index avoids request-driven DDL. Smaller
    # normalized vectors are zero-padded, preserving same-profile cosine.
    op.execute('''CREATE TABLE c0_embeddings (
        id uuid PRIMARY KEY,
        profile_id uuid NOT NULL REFERENCES c0_embedding_profiles(id) ON DELETE CASCADE,
        generation integer NOT NULL CHECK(generation BETWEEN 1 AND 2147483646),
        source_chunk_id uuid REFERENCES c0_chunks(id) ON DELETE CASCADE,
        wiki_chunk_id uuid REFERENCES c0_wiki_chunks(id) ON DELETE CASCADE,
        input_hash varchar(64) NOT NULL,
        embedding vector(2000) NOT NULL CHECK(vector_norm(embedding)>0),
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(profile_id,source_chunk_id), UNIQUE(profile_id,wiki_chunk_id),
        CHECK((source_chunk_id IS NULL) <> (wiki_chunk_id IS NULL)))''')
    op.execute('CREATE INDEX c0_embeddings_cosine ON c0_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m=16,ef_construction=64)')
    op.create_index('c0_embeddings_profile','c0_embeddings',['profile_id','generation'])
    op.execute("INSERT INTO c0_scheduled_tasks(id,name,handler,payload,enabled,interval_seconds,next_run_at) VALUES ('af8b04ce-b519-4d36-99d5-bcdedff740bd','embedding-refresh','embedding.index','{}',false,600,now())")


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
