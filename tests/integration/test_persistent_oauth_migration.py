# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""A genuine 0019 native browser/grant retains every original column."""
from datetime import datetime, timezone
import hashlib
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
from czero_core.database import Database
from czero_core.identity import VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_grants import GrantRejected, OAuthGrantService, pkce_challenge
from czero_core.renewal import ConnectionPolicy, NativeAuthorityService, RenewalResult
from czero_core.sessions import SessionService
from legacy_oauth import legacy_pair

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_0019_native_authority_is_preserved_without_persistent_upgrade():
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL']);name='czero_persistent_upgrade_'+uuid4().hex
    admin=create_engine(url,hide_parameters=True);database=None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+name))
        database=Database(url.set(database=name).render_as_string(hide_password=False))
        config=Config();config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as c:
            config.attributes['connection']=c;command.upgrade(config,'0019_client_onboarding')
        key=uuid4();issuer='https://idp.example.test/'+uuid4().hex;current=time.time()
        access=AccessService(database,issuer,key)
        identity=VerifiedIdentity(issuer,'owner',str(key),'owner','Owner',current+300)
        owner=access.resolve(identity)
        authority=NativeAuthorityService(access,'native1','s'*32,
            lambda credential:RenewalResult(identity,'rotated-private-refresh'),connection_policy=ConnectionPolicy())
        native={'id':uuid4(),'account_id':owner.user_id,'issuer':issuer,'native_client':'native1','subject':'owner'}
        cookie,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        callback='https://client.example.test/callback';resource='https://c0.example.test/mcp'
        client=OAuthClientService(access).register(owner,'Preserved persistent predecessor',[callback])
        pair=legacy_pair(database,owner,issuer,'native1',client,resource,{'c0:read'})
        date=lambda value:datetime.fromtimestamp(value,timezone.utc)
        with database.engine.begin() as c:
            c.execute(text('''INSERT INTO c0_native_authority
                (id,account_id,issuer,native_client,subject,credential,verified_until,expires_at,idle_until,idle_seconds)
                VALUES (:id,:account_id,:issuer,:native_client,:subject,:credential,:verified,:expires,:idle,3600)'''),
                {**native,'credential':authority._seal(native,'private-predecessor-refresh'),
                 'verified':date(current+300),'expires':date(current+28800),'idle':date(current+3600)})
            c.execute(text('UPDATE c0_oauth_grants SET native_authority_id=:native WHERE account_id=:account'),
                {'native':native['id'],'account':owner.user_id})
            c.execute(text('''INSERT INTO c0_sessions(token_hash,account_id,csrf_token,issuer,client_id,expires_at,native_authority_id)
                VALUES (:hash,:account,:csrf,:issuer,'native1',:expires,:native)'''),
                {'hash':hashlib.sha256(cookie.encode()).hexdigest(),'account':owner.user_id,'csrf':csrf,
                 'issuer':issuer,'expires':date(current+28800),'native':native['id']})
        with database.engine.connect() as c:
            tables=c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            columns={t:c.execute(text('''SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:name ORDER BY ordinal_position'''),{'name':t}).scalars().all() for t in tables}
            def snapshot(connection):
                return {t:connection.execute(text('SELECT row_to_json(r)::text FROM (SELECT '+
                    ','.join('"'+v+'"' for v in columns[t])+' FROM "'+t+'") r ORDER BY row_to_json(r)::text')).scalars().all() for t in tables}
            before=snapshot(c)
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as c:
                assert snapshot(c)==before
                assert c.execute(text('SELECT authority_kind FROM c0_native_authority')).scalar_one()=='session'
                assert c.execute(text('SELECT browser_idle_until,browser_idle_seconds FROM c0_sessions')).one()==(None,None)
                assert c.execute(text('SELECT persistent,refresh_family,idle_until FROM c0_oauth_grants')).one()==(False,None,None)
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0022_remembered_browsers'
        sessions=SessionService(access,'native1',authority=authority)
        context=sessions.get(cookie);assert context.csrf_token==csrf
        grants=OAuthGrantService(access,'native1',resource,authority=authority)
        assert grants.verify(pair.access_token,resource=resource).actor.user_id==owner.user_id
        with pytest.raises(GrantRejected):
            grants.issue_code(context,client['client_id'],callback=callback,scopes={'c0:read'},
                challenge=pkce_challenge(secrets.token_urlsafe(32)),resource=resource,persistent=True)
    finally:
        if database is not None:database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
