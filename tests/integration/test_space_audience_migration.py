# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""A populated genuine predecessor remains restricted after repeat migration."""
import os
from pathlib import Path
from uuid import uuid4
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
import czero_core.migrate
from czero_core.database import Database, SCHEMA_REVISION
from czero_core.migrate import migrate_database


def test_existing_spaces_keep_identity_content_and_restricted_audience():
    url = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    name = 'c0_audience_' + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    db = None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE ' + name))
        db = Database(url.set(database=name).render_as_string(hide_password=False))
        config = Config()
        config.set_main_option('script_location', str(Path(czero_core.migrate.__file__).with_name('migrations')))
        identifier = uuid4()
        with db.engine.begin() as c:
            config.attributes['connection'] = c
            command.upgrade(config, '0038_cross_space_references')
            c.execute(text("INSERT INTO c0_spaces(id,name) VALUES(:id,'Existing research')"), {'id': identifier})
            before = c.execute(text('SELECT id,name,revision FROM c0_spaces ORDER BY id')).all()
        for _ in range(2):
            migrate_database(db)
            with db.engine.connect() as c:
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == SCHEMA_REVISION
                assert c.execute(text('SELECT id,name,revision FROM c0_spaces ORDER BY id')).all() == before
                assert c.execute(text('SELECT bool_and(readable_by_all=shared) FROM c0_spaces')).scalar_one()
    finally:
        if db:
            db.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE IF EXISTS ' + name + ' WITH (FORCE)'))
        admin.dispose()
