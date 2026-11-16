# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Remember observed directory aliases; reused names cannot prove source ownership."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = '0041_personal_aliases'
down_revision = '0040_personal_data'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('c0_personal_owners', sa.Column('usernames', ARRAY(sa.Text()), nullable=False, server_default='{}'))
    op.add_column('c0_personal_owners', sa.Column('source_identity_ambiguous', sa.Boolean(), nullable=False, server_default=sa.false()))
    connection = op.get_bind()
    rows = connection.execute(sa.text('SELECT id,provider_id,username FROM c0_personal_owners')).mappings().all()
    names = {}
    for row in rows:
        names.setdefault((row['provider_id'], row['username'].casefold()), []).append(row['id'])
    for row in rows:
        # The prototype recorded no creation order: collisions suspend both claimants.
        connection.execute(sa.text('UPDATE c0_personal_owners SET usernames=:names,source_identity_ambiguous=:ambiguous WHERE id=:id'),
            {'names': [row['username'].casefold()], 'ambiguous': len(names[(row['provider_id'], row['username'].casefold())]) > 1, 'id': row['id']})


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
