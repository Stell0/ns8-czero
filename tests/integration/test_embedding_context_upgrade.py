# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
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
from czero_core.embeddings import EmbeddingStore,profile_identity,vector_literal
from czero_core.migrate import migrate_database
from czero_core.providers import EmbeddingSettings,EmbeddingClient

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='isolated PostgreSQL required')


def test_populated_predecessor_profile_and_vector_survive_upgrade_and_restart():
    parsed=make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    admin=create_engine(parsed,hide_parameters=True)
    name='c0_context_migration_'+uuid4().hex
    database=None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+name))
        database=Database(parsed.set(database=name).render_as_string(hide_password=False))
        config=Config();config.set_main_option('script_location',str(Path(czero_core.migrate.__file__).with_name('migrations')))
        settings=EmbeddingSettings('https://embedding.example.test/v1','legacy',dimensions=3)
        profile,fingerprint=profile_identity(settings)
        with database.engine.begin() as c:
            config.attributes['connection']=c;command.upgrade(config,'0036_document_bm25')
            c.execute(text('''INSERT INTO c0_embedding_profiles(id,fingerprint,model,dimensions,generation,active)
                VALUES(:id,:fingerprint,'legacy',3,7,true)'''),{'id':profile,'fingerprint':fingerprint})
            # A real predecessor chunk/vector pair, independent of current app/Core adapters.
            space=c.execute(text('SELECT id FROM c0_spaces ORDER BY id LIMIT 1')).scalar_one()
            page,revision,chunk=uuid4(),uuid4(),uuid4()
            # Source chunks require a full source/version owner chain; Wiki is
            # the smaller predecessor fixture and uses the same profile/vector FK.
            account=uuid4()
            c.execute(text("INSERT INTO c0_accounts(id,issuer,account_key,subject,username,display_name) VALUES(:id,'https://idp.example.test',:external,'owner','owner','Owner')"),{'id':account,'external':uuid4()})
            c.execute(text("INSERT INTO c0_wiki_pages(space_id,id,slug,title,revision) VALUES(:space,:id,'retained','Retained',1)"),{'space':space,'id':page})
            c.execute(text("INSERT INTO c0_wiki_revisions(space_id,id,page_id,number,title,body,content_hash,metadata,actor_id) VALUES(:space,:id,:page,1,'Retained','alpha',:hash,'{}',:actor)"),{'space':space,'id':revision,'page':page,'hash':'a'*64,'actor':account})
            c.execute(text("INSERT INTO c0_wiki_chunks(space_id,id,revision_id,ordinal,start_offset,end_offset,body,content_hash) VALUES(:space,:id,:revision,0,0,5,'alpha',:hash)"),{'space':space,'id':chunk,'revision':revision,'hash':'a'*64})
            c.execute(text('''INSERT INTO c0_embeddings(space_id,id,profile_id,generation,wiki_chunk_id,input_hash,embedding)
                VALUES(:space,:id,:profile,7,:chunk,:hash,CAST(:vector AS vector))'''),
                {'space':space,'id':uuid4(),'profile':profile,'chunk':chunk,'hash':'b'*64,'vector':vector_literal([1,0,0],3)})
            before=c.execute(text('SELECT row_to_json(e)::text FROM c0_embeddings e')).scalars().all()
        migrate_database(database);migrate_database(database);database.engine.dispose()
        with database.engine.connect() as c:
            row=c.execute(text('SELECT * FROM c0_embedding_profiles WHERE id=:id'),{'id':profile}).mappings().one()
            assert row['generation']==7 and row['active'] and row['input_format']=='legacy'
            assert row['fingerprint']==fingerprint
            assert c.execute(text('SELECT row_to_json(e)::text FROM c0_embeddings e')).scalars().all()==before
            assert EmbeddingStore(database,EmbeddingClient(settings))._ready(c,dict(row))
        assert database.health()['status']=='ok'
    finally:
        if database is not None:database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
        admin.dispose()
