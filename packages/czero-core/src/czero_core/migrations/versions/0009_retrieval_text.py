# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = '0009_retrieval_text'
down_revision = '0008_knowledge_graph'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('c0_wiki_revisions', sa.Column('search_vector', TSVECTOR(),
        sa.Computed("to_tsvector('simple'::regconfig, title || ' ' || body)", persisted=True)))
    op.create_index('c0_wiki_revisions_search', 'c0_wiki_revisions', ['search_vector'], postgresql_using='gin')


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
