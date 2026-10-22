# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real 0018 predecessor: preserve rows and make earlier denials sticky."""
import os
from pathlib import Path
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

import czero_core.migrate
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import PermissionDenied, Role, VerifiedIdentity
from czero_core.migrate import migrate_database

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_0018_upgrade_preserves_rows_and_old_denials_through_repeat_migration():
    parsed = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    admin = create_engine(parsed, hide_parameters=True)
    name = 'czero_onboarding_upgrade_' + uuid4().hex
    database = None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE ' + name))
        database = Database(parsed.set(database=name).render_as_string(hide_password=False))
        config = Config()
        config.set_main_option('script_location', str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as c:
            config.attributes['connection'] = c
            command.upgrade(config, '0018_cimd_clients')
        issuer, owner_key = 'https://idp.example.test/' + uuid4().hex, uuid4()
        old = AccessService(database, issuer, owner_key)
        def identity(key, username):
            return VerifiedIdentity(issuer, username, str(key), username, username.title(), time.time() + 600)
        owner = old.resolve(identity(owner_key, 'owner'))
        denied_key, editor_key = uuid4(), uuid4()
        for key, username in [(denied_key, 'denied'), (editor_key, 'editor')]:
            with pytest.raises(PermissionDenied): old.resolve(identity(key, username))
        with database.engine.begin() as c:
            editor_id = c.execute(text("SELECT id FROM c0_accounts WHERE issuer=:issuer AND username='editor'"), {'issuer': issuer}).scalar_one()
            c.execute(text("INSERT INTO c0_memberships(account_id,role) VALUES (:id,'editor')"), {'id': editor_id})
        with database.engine.connect() as c:
            tables = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            def snapshot(connection):
                return {t: connection.execute(text('SELECT row_to_json(r)::text FROM "' + t + '" r ORDER BY row_to_json(r)::text')).scalars().all() for t in tables}
            before = snapshot(c)
        service = AccessService(database, issuer, owner_key, admit_readers=True)
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as c:
                assert snapshot(c) == before
                assert c.execute(text('SELECT count(*) FROM c0_client_onboarding')).scalar_one() == 0
            with pytest.raises(PermissionDenied): service.resolve(identity(denied_key, 'denied'))
            assert service.authorize(owner, Role.ADMIN).is_owner
            assert service.resolve(identity(editor_key, 'editor')).role is Role.EDITOR
            # resolve updates last_seen; snapshot the established old-row state
            # again only after proving the migration itself changed no values.
            with database.engine.connect() as c: before = snapshot(c)
        new = service.resolve(identity(uuid4(), 'new-reader'))
        assert new.role is Role.READER
    finally:
        if database is not None: database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE IF EXISTS ' + name + ' WITH (FORCE)'))
        admin.dispose()
