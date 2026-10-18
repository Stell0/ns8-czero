# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Separate exact-content applicability and verification histories."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0016_annotations'
down_revision = '0015_content_spaces'
branch_labels = None
depends_on = None


def upgrade():
    links = {'source_version': 'c0_source_versions', 'wiki_revision': 'c0_wiki_revisions',
             'entity': 'c0_entities', 'object': 'c0_objects', 'claim': 'c0_claims'}
    op.create_table('c0_annotation_targets',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('space_id', sa.Uuid(), sa.ForeignKey('c0_spaces.id'), nullable=False),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('target_id', sa.Uuid(), nullable=False),
        sa.Column('content_revision', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Uuid(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        *(sa.Column(kind + '_id', sa.Uuid()) for kind in links),
        sa.UniqueConstraint('space_id', 'kind', 'target_id', 'content_revision'),
        sa.UniqueConstraint('space_id', 'id'),
        sa.CheckConstraint('content_revision>=1'),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'"))
    choices = []
    for kind, table in links.items():
        column = kind + '_id'
        same_id = f'({column}=target_id OR {column} IS NULL)' if kind == 'object' else f'{column}=target_id AND {column} IS NOT NULL'
        choices.append('(' + "kind='" + kind + "' AND " + same_id + ' AND ' +
                       ' AND '.join(other + '_id IS NULL' for other in links if other != kind) + ')')
        if kind == 'object':
            # Retain the space and observed identity after physical record removal.
            op.execute('''ALTER TABLE c0_annotation_targets ADD CONSTRAINT c0_annotation_targets_object_space_fk
                FOREIGN KEY(space_id,object_id) REFERENCES c0_objects(space_id,id)
                ON DELETE SET NULL (object_id)''')
        else:
            op.create_foreign_key('c0_annotation_targets_' + kind + '_space_fk',
                'c0_annotation_targets', table, ['space_id', column], ['space_id', 'id'])
    op.create_check_constraint('c0_annotation_targets_kind', 'c0_annotation_targets', ' OR '.join(choices))
    op.create_table('c0_annotations',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('space_id', sa.Uuid(), nullable=False),
        sa.Column('anchor_id', sa.Uuid(), nullable=False),
        sa.Column('namespace', sa.String(16), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['space_id', 'anchor_id'],
            ['c0_annotation_targets.space_id', 'c0_annotation_targets.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('space_id', 'anchor_id', 'namespace'),
        sa.UniqueConstraint('space_id', 'id'),
        sa.CheckConstraint("namespace IN ('applicability','verification') AND revision>=1"))
    op.create_table('c0_annotation_revisions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('space_id', sa.Uuid(), nullable=False),
        sa.Column('annotation_id', sa.Uuid(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('value', JSONB(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['space_id', 'annotation_id'],
            ['c0_annotations.space_id', 'c0_annotations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('annotation_id', 'number'),
        sa.CheckConstraint('number>=1'),
        sa.CheckConstraint("jsonb_typeof(value)='object' AND octet_length(value::text)<=32768"))
    op.create_index('c0_annotation_revisions_values', 'c0_annotation_revisions', ['value'], postgresql_using='gin')
    # Expression indexes add no fields to existing strict record/service views.
    for table, expression in (
        ('c0_objects', "type_name || ' ' || data::text"),
        ('c0_entities', "kind || ' ' || label || ' ' || metadata::text"),
        ('c0_claims', "predicate || ' ' || value::text || ' ' || metadata::text"),
        ('c0_entity_aliases', 'label')):
        op.execute('CREATE INDEX ' + table + '_structured_search ON ' + table +
                   " USING gin(to_tsvector('simple'::regconfig," + expression + '))')


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
