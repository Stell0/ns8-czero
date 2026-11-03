# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real staged 0024 results survive the additive PDF publication migration."""
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

from czero_core.database import Database, SCHEMA_REVISION
from czero_core.migrate import migrate_database
import czero_core.migrate

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_0024_staged_results_and_fences_survive_repeated_upgrade():
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL']); name='czero_pdf_upgrade_'+uuid4().hex
    admin=create_engine(url,hide_parameters=True); database=None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE '+name))
        database=Database(url.set(database=name).render_as_string(hide_password=False))
        config=Config(); config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as c:
            config.attributes['connection']=c; command.upgrade(config,'0024_extraction_units')
            source,version,run,unit=(uuid4() for _ in range(4))
            c.execute(text("INSERT INTO c0_sources(id,ingest_key,title,metadata) VALUES(:id,:hash,'Staged predecessor','{}')"),{'id':source,'hash':'b'*64})
            c.execute(text("""INSERT INTO c0_source_versions(id,source_id,number,filename,media_type,content_hash,size_bytes,state,retain_original)
                VALUES(:id,:source,1,'old.txt','text/plain',:hash,8,'queued',true)"""),{'id':version,'source':source,'hash':'a'*64})
            c.execute(text("""INSERT INTO c0_extraction_runs(id,space_id,version_id,processing_generation,original_sha256,
                manifest_sha256,profile,expected_units,state,expires_at,succeeded)
                SELECT :run,space_id,:version,1,:hash,:hash,'{}',1,'assembling',now()+interval '1 hour',1
                FROM c0_source_versions WHERE id=:version"""),{'run':run,'version':version,'hash':'a'*64})
            c.execute(text("""INSERT INTO c0_extraction_units(id,space_id,run_id,ordinal,locator,input_sha256,state,attempts,
                fence,lease_token,body,locations,result_sha256,text_sha256)
                SELECT :unit,space_id,id,1,'{"kind":"document"}',:hash,'succeeded',2,3,:token,
                'Original','[]',:hash,:hash FROM c0_extraction_runs WHERE id=:run"""),
                {'unit':unit,'run':run,'hash':'a'*64,'token':uuid4()})
            before=dict(c.execute(text('SELECT * FROM c0_extraction_units WHERE id=:id'),{'id':unit}).mappings().one())
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as c:
                after=dict(c.execute(text('SELECT * FROM c0_extraction_units WHERE id=:id'),{'id':unit}).mappings().one())
                assert after.pop('lifetime_attempts')==2 and after==before
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()==SCHEMA_REVISION
                assert c.execute(text('SELECT count(*) FROM c0_extraction_units')).scalar_one()==1
    finally:
        if database: database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
