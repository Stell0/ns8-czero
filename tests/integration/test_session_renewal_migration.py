# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Genuine schema-0016 rows retain every old column and fixed expiry."""
from datetime import datetime,timezone
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
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

import czero_core.migrate
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_grants import OAuthGrantService,GrantRejected
from czero_core.renewal import NativeAuthorityService
from czero_core.sessions import SessionService,SessionRejected
from legacy_oauth import legacy_pair

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


def test_0016_upgrade_preserves_legacy_browser_grants_and_all_original_columns(monkeypatch):
    parsed=make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    admin=create_engine(parsed,hide_parameters=True)
    name='czero_renewal_upgrade_'+uuid4().hex
    database=None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+name))
        database=Database(parsed.set(database=name).render_as_string(hide_password=False))
        config=Config();config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as c:
            config.attributes['connection']=c;command.upgrade(config,'0016_annotations')
        clock=[time.time()];key=uuid4();issuer='https://idp.example.test/'+uuid4().hex
        access=AccessService(database,issuer,key)
        identity=VerifiedIdentity(issuer,'owner',str(key),'owner','Owner',clock[0]+300)
        owner=access.resolve(identity)
        cookie=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        with database.engine.begin() as c:
            c.execute(text('''INSERT INTO c0_sessions(token_hash,account_id,csrf_token,issuer,client_id,expires_at)
                VALUES (:hash,:account,:csrf,:issuer,'native1',:expires)'''),
                {'hash':hashlib.sha256(cookie.encode()).hexdigest(),'account':owner.user_id,'csrf':csrf,
                 'issuer':issuer,'expires':datetime.fromtimestamp(identity.expires_at,timezone.utc)})
        resource='https://c0.example.test/mcp'
        client=OAuthClientService(access).register(owner,'Retained approved client',['https://client.example.test/callback'])
        pair=legacy_pair(database,owner,issuer,'native1',client,resource,{'c0:read'})
        # Run the exact installed recovery snapshot against both schemas.
        # Native commands are routed only to this disposable database.
        monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
        import oidc_fixture
        import oauth_fixture
        def snapshot_command(arguments):
            with database.engine.connect() as c:
                return json.dumps(c.execute(text(arguments[-1])).scalar_one())
        monkeypatch.setattr(oidc_fixture, 'command', snapshot_command)
        native_before = oauth_fixture.snapshot('czero901', client['client_id'])
        with database.engine.connect() as c:
            tables=c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            columns={table:c.execute(text('''SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:table ORDER BY ordinal_position'''),{'table':table}).scalars().all() for table in tables}
            def snapshot(c):
                return {table:c.execute(text('SELECT row_to_json(t)::text FROM (SELECT '+','.join('"'+column+'"' for column in columns[table])+' FROM "'+table+'") t ORDER BY row_to_json(t)::text')).scalars().all() for table in tables}
            before=snapshot(c)
        def forbidden_provider_call(_):raise AssertionError('Legacy authority must never acquire renewal rights')
        authority=NativeAuthorityService(access,'native1','s'*32,forbidden_provider_call,now=lambda:clock[0])
        sessions=SessionService(access,'native1',authority=authority,now=lambda:clock[0])
        grants=OAuthGrantService(access,'native1',resource,authority=authority,now=lambda:clock[0])
        for _ in range(2):
            migrate_database(database)
            assert oauth_fixture.snapshot('czero901', client['client_id']) == native_before
            with database.engine.connect() as c:
                assert snapshot(c)==before
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0018_cimd_clients'
                assert c.execute(text('SELECT count(*) FROM c0_native_authority')).scalar_one()==0
                assert c.execute(text('SELECT native_authority_id FROM c0_sessions')).scalar_one() is None
                assert c.execute(text('SELECT native_authority_id FROM c0_oauth_grants')).scalar_one() is None
            context=sessions.get(cookie)
            assert context.csrf_token==csrf and context.expires_at.timestamp()==pytest.approx(identity.expires_at)
            assert grants.verify(pair.access_token,resource=resource).actor.user_id==owner.user_id
        clock[0]=identity.expires_at+1
        with pytest.raises(SessionRejected):sessions.get(cookie)
        with pytest.raises(GrantRejected):grants.verify(pair.access_token,resource=resource)
    finally:
        if database is not None:database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
