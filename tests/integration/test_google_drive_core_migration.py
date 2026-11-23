# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Upgrade actual populated Core 0.51.1 to the independently installed Drive producer."""
import os
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_current_content_migration import current_core_python

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')

PREDECESSOR = '9ccb159fa0c6e4a99e32130b424b97f06516f402'

SEED = """
import time
from uuid import uuid4
from czero_core import Database
from czero_core.access import AccessService
from czero_core.automatic_sources import AutomaticSourceService
from czero_core.identity import VerifiedIdentity
from czero_core.health import core_version
from czero_core.migrate import migrate_database
assert core_version == '0.51.1'
db=Database()
migrate_database(db)
key=uuid4()
access=AccessService(db,'https://drive.fixture.test',key)
owner=access.resolve(VerifiedIdentity(access.issuer,'test',str(key),'owner','Owner',time.time()+300))
service=AutomaticSourceService(db,access)
draft=dict(name='Existing public repository',kind='github',config={'repositories':['fixture/docs']},
           interval_seconds=3600,enabled=True,idempotency_key='retained')
saved=service.save(owner,**draft)
service.command(owner,saved['id'],expected_revision=1,action='run',idempotency_key='run')
service.command(owner,saved['id'],expected_revision=1,action='pause',idempotency_key='pause')
service.save(owner,name='Existing website',kind='website',config={'website':{
    'seeds':['https://example.org/docs/'],'allowed_roots':['https://example.org/docs/']}},
    interval_seconds=None,enabled=False,idempotency_key='site')
db.close()
"""


def test_drive_schema_retains_public_definitions_runs_and_receipts(current_core_python, tmp_path):
    prior = tmp_path/'predecessor'/'bin'/'python'
    env = {**os.environ, 'UV_CACHE_DIR':str(tmp_path/'cache')}
    def run(args, *, runtime=env):
        result = subprocess.run(args, env=runtime, capture_output=True, timeout=240)
        (tmp_path/'migration.log').write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0, 'See private migration.log for command output'
    run(['uv','venv','--python',sys.executable,str(prior.parent.parent)])
    run(['uv','pip','install','--python',str(prior),'czero-core @ git+https://github.com/Stell0/ns8-czero.git@'
         + PREDECESSOR + '#subdirectory=packages/czero-core'])
    url = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    database_name = 'c0_drive_upgrade_' + uuid4().hex
    admin = create_engine(url, isolation_level='AUTOCOMMIT')
    target = url.set(database=database_name)
    with admin.connect() as c:
        c.exec_driver_sql('CREATE DATABASE ' + database_name)
    db = create_engine(target)
    try:
        runtime = {**env, 'CZERO_DATABASE_URL':target.render_as_string(hide_password=False)}
        run([str(prior),'-I','-c',SEED], runtime=runtime)
        def public_state():
            queries = ('SELECT * FROM c0_automatic_sources WHERE kind<>\'google_drive\'',
                       'SELECT r.* FROM c0_source_update_runs r JOIN c0_automatic_sources d ON d.id=r.definition_id WHERE d.kind<>\'google_drive\'',
                       'SELECT * FROM c0_knowledge_receipts')
            with db.connect() as c:
                return tuple(c.exec_driver_sql('SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) FROM ('+query+') t').scalar_one()
                             for query in queries)
        before = public_state()
        assert len(before[0]) == 2 and before[1][0]['state'] == 'cancelled'
        run([str(current_core_python),'-I','-c',"""
from pathlib import Path
from alembic import command
from alembic.config import Config
from czero_core import migrate
from czero_core.database import Database
db=Database()
config=Config()
config.set_main_option('script_location',str(Path(migrate.__file__).with_name('migrations')))
with db.engine.begin() as c:
    config.attributes['connection']=c
    command.upgrade(config,'0044_pdf_limits')
db.close()
"""], runtime=runtime)
        legacy = uuid4()
        with db.begin() as c:
            c.execute(text("""INSERT INTO c0_automatic_sources(id,space_id,name,kind,config,enabled,owner_id,
                authority_revision,space_revision,grant_revision) SELECT :id,space_id,'Legacy folder',
                'google_drive','{}',true,owner_id,authority_revision,space_revision,grant_revision
                FROM c0_automatic_sources WHERE kind='github'"""),{'id':legacy})
            c.execute(text("""INSERT INTO c0_drive_connections(account_id,space_id,subject_hash,credential,offline)
                SELECT owner_id,space_id,repeat('0',64),'sealed-fixture',true FROM c0_automatic_sources WHERE id=:id"""),
                {'id':legacy})
            c.execute(text("""INSERT INTO c0_drive_bindings(definition_id,account_id,space_id,generation,folder_id)
                SELECT id,owner_id,space_id,1,'fixture-folder' FROM c0_automatic_sources WHERE id=:id"""),{'id':legacy})
            c.execute(text("""INSERT INTO c0_source_update_runs(id,definition_id,number,revision,state)
                VALUES (:run,:id,1,1,'pending')"""),{'run':uuid4(),'id':legacy})
        for _ in range(2):
            run([str(current_core_python),'-I','-m','czero_core.migrate'], runtime=runtime)
            assert public_state() == before
            with db.connect() as c:
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0045_drive_audience'
                assert c.execute(text('SELECT enabled,revision,next_run_at FROM c0_automatic_sources WHERE id=:id'),
                                 {'id':legacy}).one()==(False,2,None)
                assert c.execute(text('SELECT state,error_code FROM c0_source_update_runs WHERE definition_id=:id'),
                                 {'id':legacy}).one()==('blocked','drive_audience_changed')
                assert c.execute(text('SELECT approved_audience FROM c0_drive_bindings WHERE definition_id=:id'),
                                 {'id':legacy}).scalar_one() is None
    finally:
        db.dispose()
        with admin.connect() as c:
            c.exec_driver_sql('DROP DATABASE ' + database_name + ' WITH (FORCE)')
        admin.dispose()
