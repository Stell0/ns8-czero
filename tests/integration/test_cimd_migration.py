# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""A genuine 0017 database retains every preexisting value through 0018."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

import czero_core.migrate
from czero_core.access import AccessService
from czero_core.cimd import CimdService
from czero_core.identity import VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_grants import OAuthGrantService
from czero_core.sessions import SessionService
from legacy_oauth import legacy_pair

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_0017_upgrade_preserves_all_old_rows_and_new_policy_defaults_off():
    parsed = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    admin = create_engine(parsed, hide_parameters=True)
    name = 'czero_cimd_upgrade_' + uuid4().hex
    database = None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE ' + name))
        database = czero_core.migrate.Database(parsed.set(database=name).render_as_string(hide_password=False))
        config = Config()
        config.set_main_option('script_location', str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as c:
            config.attributes['connection'] = c
            command.upgrade(config, '0017_session_renewal')
        now, key = time.time(), uuid4()
        issuer = 'https://idp.example.test/' + uuid4().hex
        access = AccessService(database, issuer, key)
        owner = access.resolve(VerifiedIdentity(issuer, 'owner', str(key), 'owner', 'Owner', now + 600))
        callback, resource = 'https://client.example.test/callback', 'https://c0.example.test/mcp'
        client = OAuthClientService(access).register(owner, 'Retained manual client', [callback])
        pair = legacy_pair(database, owner, issuer, 'native1', client, resource, {'c0:read'})
        cookie, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        authority_id, code = uuid4(), secrets.token_urlsafe(32)
        with database.engine.begin() as c:
            c.execute(text('''INSERT INTO c0_native_authority
                (id,account_id,issuer,native_client,subject,credential,verified_until,expires_at,idle_until,idle_seconds)
                VALUES (:id,:account,:issuer,'native1','owner','opaque-encrypted-test-value',:until,:until,:until,600)'''),
                {'id': authority_id, 'account': owner.user_id, 'issuer': issuer,
                 'until': datetime.fromtimestamp(now + 600, timezone.utc)})
            c.execute(text('''INSERT INTO c0_sessions(token_hash,account_id,csrf_token,issuer,client_id,expires_at)
                VALUES (:hash,:account,:csrf,:issuer,'native1',:until)'''),
                {'hash': hashlib.sha256(cookie.encode()).hexdigest(), 'account': owner.user_id,
                 'csrf': binding, 'issuer': issuer, 'until': datetime.fromtimestamp(now + 600, timezone.utc)})
            c.execute(text('''INSERT INTO c0_oauth_consent
                (hash,browser_hash,client_id,client_revision,issuer,native_client,resource,callback,scopes,challenge,state,expires_at)
                VALUES (:hash,:browser,:client,1,:issuer,'native1',:resource,:callback,CAST(:scopes AS jsonb),:challenge,'old-state',:until)'''),
                {'hash': hashlib.sha256(code.encode()).hexdigest(), 'browser': hashlib.sha256(binding.encode()).hexdigest(),
                 'client': client['client_id'], 'issuer': issuer, 'resource': resource, 'callback': callback,
                 'scopes': json.dumps(['c0:read']), 'challenge': 'x' * 43,
                 'until': datetime.fromtimestamp(now + 300, timezone.utc)})
        with database.engine.connect() as c:
            tables = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            columns = {t:c.execute(text('''SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:table ORDER BY ordinal_position'''),
                {'table':t}).scalars().all() for t in tables}
            def snapshot(connection):
                return {t:connection.execute(text('SELECT row_to_json(r)::text FROM (SELECT '+
                    ','.join('"'+v+'"' for v in columns[t])+' FROM "'+t+'") r ORDER BY row_to_json(r)::text')).scalars().all() for t in tables}
            before = snapshot(c)
        registry = CimdService(access)
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as c:
                assert snapshot(c) == before
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0020_persistent_oauth'
                assert c.execute(text('SELECT count(*) FROM c0_cimd_clients')).scalar_one() == 0
                assert tuple(c.execute(text('SELECT id,enabled,revision FROM c0_cimd_policy')).one()) == (1, False, 1)
            registry.sync_policy(False)
            assert SessionService(access, 'native1').get(cookie).actor.user_id == owner.user_id
            assert OAuthGrantService(access, 'native1', resource).verify(pair.access_token, resource=resource).actor.user_id == owner.user_id
    finally:
        if database is not None:
            database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE IF EXISTS ' + name + ' WITH (FORCE)'))
        admin.dispose()
