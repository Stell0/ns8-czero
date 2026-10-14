# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision='0005_objects'
down_revision='0004_jobs'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('c0_object_types',
        sa.Column('name',sa.String(64),primary_key=True),
        sa.Column('label',sa.String(128),nullable=False),
        sa.Column('schema',JSONB(),nullable=False),
        sa.Column('unique_fields',ARRAY(sa.String(64)),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint("jsonb_typeof(schema)='object' AND octet_length(schema::text)<=32768"))
    op.create_table('c0_objects',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('type_name',sa.String(64),sa.ForeignKey('c0_object_types.name'),nullable=False),
        sa.Column('data',JSONB(),nullable=False),
        sa.Column('tags',ARRAY(sa.String(64)),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint('revision>=1'),
        sa.CheckConstraint("jsonb_typeof(data)='object' AND octet_length(data::text)<=131072"),
        sa.CheckConstraint('cardinality(tags)<=32'))
    op.create_index('c0_objects_type','c0_objects',['type_name','created_at','id'])
    op.create_index('c0_objects_data','c0_objects',['data'],postgresql_using='gin')
    op.create_index('c0_objects_tags','c0_objects',['tags'],postgresql_using='gin')
    op.create_table('c0_object_keys',
        sa.Column('object_id',sa.Uuid(),sa.ForeignKey('c0_objects.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('field',sa.String(64),primary_key=True),
        sa.Column('type_name',sa.String(64),sa.ForeignKey('c0_object_types.name'),nullable=False),
        sa.Column('value',JSONB(),nullable=False),
        sa.UniqueConstraint('type_name','field','value'),
        sa.CheckConstraint("jsonb_typeof(value) IN ('string','number','boolean') AND octet_length(value::text)<=1024"))
    op.create_table('c0_object_relations',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('source_id',sa.Uuid(),sa.ForeignKey('c0_objects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('target_id',sa.Uuid(),sa.ForeignKey('c0_objects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('kind',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('source_id','target_id','kind'))
    op.create_index('c0_object_relations_target','c0_object_relations',['target_id'])
    op.create_table('c0_object_events',
        sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),
        sa.Column('object_id',sa.Uuid(),nullable=False),
        sa.Column('type_name',sa.String(64),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('operation',sa.String(24),nullable=False),
        sa.Column('actor_id',sa.Uuid(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint("operation IN ('create','update','delete','relation_add','relation_remove')"))
    op.create_index('c0_object_events_object','c0_object_events',['object_id','id'])


def downgrade():
    raise RuntimeError('C0 schema downgrades are not supported')
