# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Forward migration preserves prototype owners while quarantining name collisions."""
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


def test_populated_personal_predecessor_retains_spaces_and_suspends_ambiguous_names():
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    name='c0_alias_'+uuid4().hex
    admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
    db=None
    try:
        with admin.connect() as c:c.exec_driver_sql('CREATE DATABASE '+name)
        db=Database(url.set(database=name).render_as_string(hide_password=False))
        config=Config()
        config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        provider=uuid4();owners=[]
        with db.engine.begin() as c:
            config.attributes['connection']=c
            command.upgrade(config,'0040_personal_data')
            c.execute(text("INSERT INTO c0_personal_config(issuer,provider_id) VALUES ('synthetic',:provider)"),{'provider':provider})
            for username in ('Person','PERSON','other'):
                space,owner,directory=uuid4(),uuid4(),uuid4();owners.append((owner,space,directory))
                c.execute(text("INSERT INTO c0_spaces(id,name,personal) VALUES (:id,'Personal Data',true)"),{'id':space})
                c.execute(text('''INSERT INTO c0_personal_owners(id,issuer,provider_id,directory_id,space_id,active,username)
                    VALUES (:id,'synthetic',:provider,:directory,:space,true,:username)'''),
                    {'id':owner,'provider':provider,'directory':directory,'space':space,'username':username})
        for _ in range(2):
            migrate_database(db)
            with db.engine.connect() as c:
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()==SCHEMA_REVISION
                for index,(owner,space,directory) in enumerate(owners):
                    row=c.execute(text('SELECT * FROM c0_personal_owners WHERE id=:id'),{'id':owner}).mappings().one()
                    assert row['space_id']==space and row['directory_id']==directory and row['active']
                    assert row['usernames']==['person' if index<2 else 'other']
                    assert row['source_identity_ambiguous'] is (index<2)
    finally:
        if db:db.close()
        with admin.connect() as c:c.exec_driver_sql('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)')
        admin.dispose()
