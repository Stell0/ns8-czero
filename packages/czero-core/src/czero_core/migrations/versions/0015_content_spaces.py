# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Backfill ownership without rewriting any predecessor content or identity."""
from alembic import op
import sqlalchemy as sa

revision = '0015_content_spaces'
down_revision = '0014_spaces'
branch_labels = None
depends_on = None

# Trusted identifiers only. Types and provider profiles remain instance-wide.
TABLES = ('c0_objects', 'c0_object_keys', 'c0_object_relations', 'c0_object_events',
          'c0_sources', 'c0_source_versions', 'c0_documents', 'c0_chunks',
          'c0_wiki_pages', 'c0_wiki_revisions', 'c0_entities', 'c0_entity_aliases',
          'c0_claims', 'c0_evidence_links', 'c0_relations', 'c0_entity_links',
          'c0_knowledge_events', 'c0_knowledge_receipts', 'c0_wiki_chunks', 'c0_embeddings')


def upgrade():
    op.execute('''CREATE FUNCTION c0_shared_space() RETURNS uuid LANGUAGE sql STABLE AS
        'SELECT knowledge_space_id FROM instance_metadata' ''')
    for table in TABLES:
        op.add_column(table, sa.Column('space_id', sa.Uuid(), nullable=False,
                                      server_default=sa.text('c0_shared_space()')))
        op.create_foreign_key(table + '_space_fk', table, 'c0_spaces', ['space_id'], ['id'])
        op.create_index(table + '_space', table, ['space_id'])
    # Old shared callers and direct maintenance inserts keep their original
    # namespace. Protected writers must explicitly provide their trusted space.
    for table, columns, old_name in (
        ('c0_sources', ['ingest_key'], 'c0_sources_ingest_key_key'),
        ('c0_wiki_pages', ['slug'], 'c0_wiki_pages_slug_key'),
        ('c0_object_keys', ['type_name', 'field', 'value'], 'c0_object_keys_type_name_field_value_key')):
        op.drop_constraint(old_name, table, type_='unique')
        op.create_unique_constraint(table + '_space_unique', table, ['space_id', *columns])
    for table, columns in (('c0_entity_aliases', ['normalized']),
                           ('c0_knowledge_receipts', ['actor_id', 'key'])):
        op.drop_constraint(table + '_pkey', table, type_='primary')
        op.create_primary_key(table + '_pkey', table, ['space_id', *columns])
    roots = ('c0_objects', 'c0_sources', 'c0_source_versions', 'c0_documents', 'c0_chunks',
             'c0_wiki_pages', 'c0_wiki_revisions', 'c0_entities', 'c0_claims', 'c0_wiki_chunks')
    for table in roots:
        op.create_unique_constraint(table + '_space_id_unique', table, ['space_id', 'id'])
    # Composite references make same-space ownership an invariant even for an
    # Admin permitted to read both spaces. Retain existing deletion behavior.
    references = (
        ('c0_object_keys', 'object_id', 'c0_objects', 'CASCADE'),
        ('c0_object_relations', 'source_id', 'c0_objects', 'CASCADE'),
        ('c0_object_relations', 'target_id', 'c0_objects', 'CASCADE'),
        ('c0_source_versions', 'source_id', 'c0_sources', None),
        ('c0_documents', 'version_id', 'c0_source_versions', None),
        ('c0_chunks', 'document_id', 'c0_documents', None),
        ('c0_wiki_revisions', 'page_id', 'c0_wiki_pages', None),
        ('c0_entity_aliases', 'entity_id', 'c0_entities', None),
        ('c0_claims', 'entity_id', 'c0_entities', None),
        ('c0_claims', 'page_id', 'c0_wiki_pages', None),
        ('c0_evidence_links', 'claim_id', 'c0_claims', None),
        ('c0_evidence_links', 'chunk_id', 'c0_chunks', None),
        ('c0_relations', 'source_id', 'c0_entities', None),
        ('c0_relations', 'target_id', 'c0_entities', None),
        ('c0_entity_links', 'entity_id', 'c0_entities', None),
        ('c0_entity_links', 'page_id', 'c0_wiki_pages', None),
        ('c0_entity_links', 'source_id', 'c0_sources', None),
        ('c0_entity_links', 'document_id', 'c0_documents', None),
        ('c0_entity_links', 'chunk_id', 'c0_chunks', None),
        ('c0_wiki_chunks', 'revision_id', 'c0_wiki_revisions', 'CASCADE'),
        ('c0_embeddings', 'source_chunk_id', 'c0_chunks', 'CASCADE'),
        ('c0_embeddings', 'wiki_chunk_id', 'c0_wiki_chunks', 'CASCADE'))
    for table, column, target, delete in references:
        op.create_foreign_key(table + '_' + column + '_space_fk', table, target,
            ['space_id', column], ['space_id', 'id'], ondelete=delete)
    # PG17 supports a column list for SET NULL. Clearing a deleted object's FK
    # must retain the link's own space and immutable target/snapshot identity.
    op.execute('''ALTER TABLE c0_entity_links ADD CONSTRAINT c0_entity_links_object_space_fk
        FOREIGN KEY(space_id,object_id) REFERENCES c0_objects(space_id,id)
        ON DELETE SET NULL (object_id)''')
    op.create_table('c0_space_cursors',
        sa.Column('space_id', sa.Uuid(), sa.ForeignKey('c0_spaces.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('kind', sa.String(16), primary_key=True),
        sa.Column('value', sa.BigInteger(), nullable=False),
        sa.CheckConstraint("kind IN ('object','knowledge') AND value>=0"))
    for table, kind in (('c0_object_events', 'object'), ('c0_knowledge_events', 'knowledge')):
        op.add_column(table, sa.Column('feed_cursor', sa.BigInteger()))
        op.execute('UPDATE ' + table + ' SET feed_cursor=id')
        op.alter_column(table, 'feed_cursor', nullable=False)
        op.create_unique_constraint(table + '_space_cursor', table, ['space_id', 'feed_cursor'])
        # A predecessor sequence may be ahead of retained rows (rolled-back or
        # removed fixture events). Never move an already issued legacy cursor
        # backwards, even when no old event row remains.
        op.execute("INSERT INTO c0_space_cursors(space_id,kind,value) SELECT c0_shared_space(),'" +
                   kind + "',GREATEST(COALESCE(max(feed_cursor),0),(SELECT CASE WHEN is_called "
                   "THEN last_value ELSE 0 END FROM " + table + "_id_seq)) FROM " + table)
    op.add_column('c0_jobs', sa.Column('space_id', sa.Uuid(), sa.ForeignKey('c0_spaces.id')))
    op.execute('''UPDATE c0_jobs j SET space_id=v.space_id FROM c0_source_versions v
        WHERE j.id=v.job_id''')
    # Retained cleanup jobs no longer appear in the version's current job_id;
    # derive their ownership from the existing, validated parent UUID payload.
    op.execute('''UPDATE c0_jobs j SET space_id=v.space_id FROM c0_source_versions v
        WHERE j.handler IN ('source.extract','source.cleanup')
        AND j.payload->>'version_id'=v.id::text''')
    op.create_index('c0_jobs_space', 'c0_jobs', ['space_id'])
    op.create_unique_constraint('c0_jobs_space_id_unique', 'c0_jobs', ['space_id', 'id'])
    op.execute('''ALTER TABLE c0_source_versions ADD CONSTRAINT c0_source_versions_job_space_fk
        FOREIGN KEY(space_id,job_id) REFERENCES c0_jobs(space_id,id)
        ON DELETE SET NULL (job_id)''')


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
