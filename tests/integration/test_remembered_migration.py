# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real 0021 rows retain bytes, ordinary mode and one-use login state."""
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

import czero_core.migrate
from czero_core.database import Database
from czero_core.migrate import migrate_database

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_0021_repeated_upgrade_never_promotes_sessions_or_login_states():
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL']);name='czero_remember_upgrade_'+uuid4().hex
    admin=create_engine(url,hide_parameters=True);database=None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+name))
        database=Database(url.set(database=name).render_as_string(hide_password=False))
        config=Config();config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        account=uuid4()
        with database.engine.begin() as c:
            config.attributes['connection']=c;command.upgrade(config,'0021_workspace_access')
            c.execute(text("INSERT INTO c0_accounts(id,issuer,account_key,subject,username,display_name) VALUES(:id,'https://idp.example.test',:key,'s','reader','Reader')"),{'id':account,'key':uuid4()})
            c.execute(text("INSERT INTO c0_sessions(token_hash,account_id,csrf_token,issuer,client_id,expires_at) VALUES(:hash,:id,:csrf,'https://idp.example.test','native',now()+interval '1 hour')"),{'id':account,'hash':'a'*64,'csrf':'b'*43})
            c.execute(text("INSERT INTO c0_login_states(state_hash,browser_hash,nonce,code_verifier,issuer,client_id,expires_at) VALUES(:hash,:browser,:nonce,:verifier,'https://idp.example.test','native',now()+interval '5 minutes')"),{'hash':'c'*64,'browser':'d'*64,'nonce':'e'*43,'verifier':'f'*43})
            tables=c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            columns={t:c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:name ORDER BY ordinal_position"),{'name':t}).scalars().all() for t in tables}
            def snapshot(c):
                return {t:c.execute(text('SELECT row_to_json(r)::text FROM (SELECT '+','.join('"'+v+'"' for v in columns[t])+' FROM "'+t+'") r ORDER BY row_to_json(r)::text')).scalars().all() for t in tables}
            before=snapshot(c)
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as c:
                assert snapshot(c)==before
                assert c.execute(text('SELECT remembered FROM c0_sessions')).scalar_one() is False
                assert c.execute(text('SELECT remembered FROM c0_login_states')).scalar_one() is False
                assert c.execute(text('SELECT count(*) FROM c0_signin_intents')).scalar_one()==0
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0023_current_content'
    finally:
        if database:database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
