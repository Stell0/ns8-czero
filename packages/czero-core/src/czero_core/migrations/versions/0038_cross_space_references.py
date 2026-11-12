# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Outgoing navigation identities, without stored target metadata or authority."""
from alembic import op
import sqlalchemy as sa

revision = '0038_cross_space_references'
down_revision = '0037_embedding_context'
branch_labels = None
depends_on = None

_ENDPOINTS = {'object': 'c0_objects', 'page': 'c0_wiki_pages', 'source': 'c0_sources',
              'entity': 'c0_entities', 'claim': 'c0_claims'}
_TABLE = 'c0_cross_space_references'


def upgrade():
    columns = [sa.Column('id', sa.Uuid(), primary_key=True),
               sa.Column('relation_kind', sa.String(16), nullable=False),
               sa.Column('created_by', sa.Uuid(), nullable=False),
               sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
               sa.CheckConstraint("relation_kind='references'"),
               sa.CheckConstraint('source_space_id<>target_space_id')]
    for side in ('source', 'target'):
        columns.extend([sa.Column(side+'_space_id', sa.Uuid(), sa.ForeignKey('c0_spaces.id'), nullable=False),
                        sa.Column(side+'_kind', sa.String(16), nullable=False),
                        sa.Column(side+'_id', sa.Uuid(), nullable=False)])
        choices = []
        for kind, table in _ENDPOINTS.items():
            column = side+'_'+kind+'_id'
            columns.extend([sa.Column(column, sa.Uuid()), sa.ForeignKeyConstraint(
                [side+'_space_id', column], [table+'.space_id', table+'.id'], ondelete='CASCADE')])
            choices.append('(' + ' AND '.join([
                side+"_kind='"+kind+"'", column+' IS NOT NULL', column+'='+side+'_id',
                *[side+'_'+other+'_id IS NULL' for other in _ENDPOINTS if other != kind]]) + ')')
        columns.append(sa.CheckConstraint(' OR '.join(choices)))
    columns.append(sa.UniqueConstraint('source_space_id','source_kind','source_id',
        'target_space_id','target_kind','target_id','relation_kind'))
    op.create_table(_TABLE, *columns)
    op.create_index('c0_cross_refs_outgoing', _TABLE, ['source_space_id','source_kind','source_id','id'])
    op.create_index('c0_cross_refs_selected', _TABLE,
                    ['source_space_id','source_kind','source_id','target_space_id','id'])
    for side in ('source', 'target'):
        for kind in _ENDPOINTS:
            column = side+'_'+kind+'_id'
            op.create_index('c0_cross_refs_'+side+'_'+kind, _TABLE, [side+'_space_id', column],
                            postgresql_where=sa.text(column+' IS NOT NULL'))


def downgrade():
    raise RuntimeError('Restore an external backup; C0 schema downgrades are not supported')
