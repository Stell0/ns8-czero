# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real PostgreSQL/vector acceptance; CI supplies an isolated database URL."""
import os

import pytest
from sqlalchemy import text

from czero_core.database import Database, SCHEMA_REVISION
from czero_core.migrate import migrate_database

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL URL required')


@pytest.fixture(scope='module')
def database():
    database = Database(os.environ['CZERO_TEST_DATABASE_URL'])
    migrate_database(database)
    yield database
    database.close()


def test_migrations_are_repeatable_and_identity_survives(database):
    with database.engine.connect() as connection:
        before = connection.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one()
    migrate_database(database)
    with database.engine.connect() as connection:
        assert connection.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one() == before
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == SCHEMA_REVISION
    assert database.health()['status'] == 'ok'


def test_real_vector_index_query_and_transaction_rollback(database):
    with database.engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text('CREATE TABLE czero_vector_test (id int PRIMARY KEY, embedding vector(3))'))
        connection.execute(text("INSERT INTO czero_vector_test VALUES (1,'[1,0,0]'),(2,'[0,1,0]'),(3,'[0,0,1]')"))
        connection.execute(text('CREATE INDEX czero_vector_test_hnsw ON czero_vector_test USING hnsw (embedding vector_l2_ops)'))
        connection.execute(text('SET LOCAL enable_seqscan = off'))
        assert connection.execute(text("SELECT id FROM czero_vector_test ORDER BY embedding <-> '[1,0,0]' LIMIT 1")).scalar_one() == 1
        plan = connection.execute(text("EXPLAIN SELECT id FROM czero_vector_test ORDER BY embedding <-> '[1,0,0]' LIMIT 1")).scalars().all()
        assert any('czero_vector_test_hnsw' in row for row in plan)
        transaction.rollback()
        assert connection.execute(text("SELECT to_regclass('czero_vector_test')")).scalar_one() is None


def test_incompatible_schema_is_reported_without_connection_details(database):
    try:
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = 'future_schema'"))
        assert database.health() == {'status':'unavailable','reason':'schema_incompatible'}
    finally:
        with database.engine.begin() as connection:
            connection.execute(text('UPDATE alembic_version SET version_num = :revision'), {'revision':SCHEMA_REVISION})
