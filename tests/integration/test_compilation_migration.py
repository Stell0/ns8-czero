# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Additive predecessor migration preserves existing authority and authored rows."""
import os
from pathlib import Path
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
import czero_core.migrate
from czero_core.access import AccessService
from czero_core.api_keys import ApiKeyService
from czero_core.database import Database, SCHEMA_REVISION
from czero_core.identity import VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.spaces import SpaceService
from czero_core.wiki import WikiService


def test_predecessor_upgrade_twice_preserves_every_existing_table():
    url = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    name = 'c0_compiler_migration_' + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    db = None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE ' + name))
        db = Database(url.set(database=name).render_as_string(hide_password=False))
        config = Config()
        config.set_main_option('script_location', str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with db.engine.begin() as c:
            config.attributes['connection'] = c
            command.upgrade(config, '0032_api_key_revisions')
        issuer, key = 'https://migration.example.invalid/' + uuid4().hex, uuid4()
        access = AccessService(db, issuer, key)
        owner = access.resolve(VerifiedIdentity(issuer, 'owner', str(key), 'owner', 'Owner', time.time()+300))
        space = SpaceService(db, access).create(owner, 'Migration fixture', idempotency_key='space')['id']
        wiki = WikiService(db, access).in_space(space)
        page = wiki.create_page(owner, 'authored', 'Authored', '# Preserve authored knowledge', idempotency_key='authored')
        keys = ApiKeyService(access, client_id='fixture', client_secret='synthetic', resource='https://example.invalid/mcp')
        token = keys.create(owner, name='Retained key', scopes={'c0:read'}, space_ids=[space])['key']
        with db.engine.connect() as c:
            names = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            before = {table: c.execute(text('SELECT to_jsonb(t) FROM '+table+' t ORDER BY to_jsonb(t)::text')).scalars().all() for table in names}
        for _ in range(2):
            migrate_database(db)
            with db.engine.connect() as c:
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == SCHEMA_REVISION
                after = {table: c.execute(text('SELECT to_jsonb(t) FROM '+table+' t ORDER BY to_jsonb(t)::text')).scalars().all() for table in names}
                assert before == after
                new = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'c0_compilation_%' ORDER BY tablename")).scalars().all()
                assert len(new) == 6
                assert all(c.execute(text('SELECT count(*) FROM '+table)).scalar_one() == 0 for table in new)
            assert wiki.get_page(owner, page['id']) == page
        assert keys.verify(token, resource=keys.resource).actor.user_id == owner.user_id
    finally:
        if db:
            db.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
