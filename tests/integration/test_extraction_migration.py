# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real 0023 rows stay unchanged; unit queues start empty on repeated upgrade."""
import hashlib
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

from czero_core.database import Database, SCHEMA_REVISION
import czero_core.migrate
from czero_core.migrate import migrate_database

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='disposable PostgreSQL required')


def test_0023_repeat_upgrade_preserves_all_existing_rows_and_no_backfill():
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL']); name='czero_units_upgrade_'+uuid4().hex
    admin=create_engine(url,hide_parameters=True); database=None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE '+name))
        database=Database(url.set(database=name).render_as_string(hide_password=False))
        config=Config(); config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as c:
            config.attributes['connection']=c; command.upgrade(config,'0023_current_content')
            tables=c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            columns={table:c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:table ORDER BY ordinal_position"),{'table':table}).scalars().all() for table in tables}
            def snapshot(c):
                return {table:c.execute(text('SELECT row_to_json(r)::text FROM (SELECT '+
                    ','.join('"'+column+'"' for column in columns[table])+' FROM "'+table+'") r ORDER BY row_to_json(r)::text')).scalars().all() for table in tables}
            # Seed coherent predecessor source/document/chunk rows directly;
            # the current service requires the new guard tables.
            source=uuid4(); version=uuid4(); document=uuid4(); chunk=uuid4()
            digest=hashlib.sha256(b'Original').hexdigest()
            c.execute(text("INSERT INTO c0_sources(id,ingest_key,title,metadata) VALUES(:id,:hash,'Existing evidence','{}')"),{'id':source,'hash':'a'*64})
            c.execute(text("""INSERT INTO c0_source_versions(id,source_id,number,filename,media_type,content_hash,size_bytes,state,retain_original)
                VALUES(:id,:source,1,'old.txt','text/plain',:hash,8,'ready',false)"""),{'id':version,'source':source,'hash':digest})
            c.execute(text("UPDATE c0_sources SET current_version_id=:version,next_version_number=2 WHERE id=:id"),{'version':version,'id':source})
            c.execute(text("INSERT INTO c0_documents(id,version_id,body,text_hash,locations) VALUES(:id,:version,'Original',:hash,'[]')"),{'id':document,'version':version,'hash':digest})
            c.execute(text("INSERT INTO c0_chunks(id,document_id,ordinal,start_offset,end_offset,body,content_hash,locations) VALUES(:id,:document,0,0,8,'Original',:hash,'[]')"),{'id':chunk,'document':document,'hash':digest})
            before=snapshot(c)
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as c:
                assert snapshot(c)==before
                assert c.execute(text("SELECT count(*) FROM c0_documents WHERE structure IS NOT NULL OR chunking_profile<>'fixed-v1'")).scalar_one()==0
                assert c.execute(text("SELECT count(*) FROM c0_chunks WHERE section_context<>'[]'::jsonb")).scalar_one()==0
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()==SCHEMA_REVISION
                assert c.execute(text('SELECT count(*) FROM c0_extraction_runs')).scalar_one()==0
                assert c.execute(text('SELECT count(*) FROM c0_extraction_units')).scalar_one()==0
    finally:
        if database: database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
