# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
from uuid import uuid4
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
import czero_core.migrate
from czero_core.database import Database,SCHEMA_REVISION
from czero_core.migrate import migrate_database


def test_first_producer_keys_are_revoked_without_changing_account_state():
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL']);name='c0_key_migration_'+uuid4().hex
    admin=create_engine(url,hide_parameters=True);db=None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+name))
        db=Database(url.set(database=name).render_as_string(hide_password=False))
        config=Config();config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        account,key=uuid4(),uuid4()
        with db.engine.begin() as c:
            config.attributes['connection']=c;command.upgrade(config,'0031_api_keys')
            c.execute(text("INSERT INTO c0_accounts(id,issuer,account_key,subject,username,display_name) VALUES(:id,'https://idp.example.test',:key,'s','member','Member')"),{'id':account,'key':key})
            c.execute(text("INSERT INTO c0_memberships(account_id,role) VALUES(:id,'editor')"),{'id':account})
            c.execute(text("""INSERT INTO c0_api_keys(id,account_id,digest,configuration,name,scopes,space_ids,created_at)
                SELECT :id,:account,'synthetic-hash','synthetic-configuration','Prototype',ARRAY['c0:read'],ARRAY[knowledge_space_id],now() FROM instance_metadata"""),{'id':uuid4(),'account':account})
            before=c.execute(text('SELECT row_to_json(a) FROM c0_accounts a WHERE id=:id'),{'id':account}).scalar_one()
        for _ in range(2):
            migrate_database(db)
            with db.engine.connect() as c:
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()==SCHEMA_REVISION
                assert c.execute(text('SELECT revoked_at IS NOT NULL FROM c0_api_keys')).scalar_one()
                assert c.execute(text('SELECT account_revision FROM c0_api_keys')).scalar_one()==0
                assert c.execute(text('SELECT row_to_json(a) FROM c0_accounts a WHERE id=:id'),{'id':account}).scalar_one()==before
                assert c.execute(text('SELECT role FROM c0_memberships')).scalar_one()=='editor'
    finally:
        if db:db.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
