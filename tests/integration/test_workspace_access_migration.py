# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real schema0020 upgrade preserves every old column and explicit blocks."""
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


def test_real_0020_repeated_upgrade_preserves_old_rows_and_adds_safe_ids():
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL']);name='czero_access_upgrade_'+uuid4().hex
    admin=create_engine(url,hide_parameters=True);database=None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+name))
        database=Database(url.set(database=name).render_as_string(hide_password=False))
        config=Config();config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        account=uuid4()
        with database.engine.begin() as c:
            config.attributes['connection']=c;command.upgrade(config,'0020_persistent_oauth')
            c.execute(text("INSERT INTO c0_accounts(id,issuer,account_key,subject,username,display_name) VALUES(:id,'https://idp.example.test',:key,'s','blocked','Blocked')"),{'id':account,'key':uuid4()})
            c.execute(text('INSERT INTO c0_account_blocks(account_id) VALUES(:id)'),{'id':account})
            c.execute(text("""INSERT INTO c0_client_onboarding(hash,browser_hash,metadata_url,account_id,issuer,native_client,resource,policy_revision,parameters,expires_at)
                VALUES(:hash,:browser,'https://client.example.test/client.json',:id,'https://idp.example.test','native','https://c0.example.test/mcp',1,'{}',now()+interval '5 minutes')"""),{'id':account,'hash':'a'*64,'browser':'b'*64})
            tables=c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            columns={t:c.execute(text('SELECT column_name FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=:name ORDER BY ordinal_position'),{'name':t}).scalars().all() for t in tables}
            def snapshot(c):
                return {t:c.execute(text('SELECT row_to_json(r)::text FROM (SELECT '+','.join('"'+v+'"' for v in columns[t])+' FROM "'+t+'") r ORDER BY row_to_json(r)::text')).scalars().all() for t in tables}
            before=snapshot(c)
        identifier=None
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as c:
                assert snapshot(c)==before
                assert c.execute(text('SELECT access_revision FROM c0_accounts')).scalar_one()==1
                current=c.execute(text('SELECT id FROM c0_client_onboarding')).scalar_one()
                assert current and (identifier is None or current==identifier);identifier=current
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0021_workspace_access'
    finally:
        if database:database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
