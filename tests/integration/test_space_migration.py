# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Forward upgrade compares every predecessor column, not just row counts."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from czero_core.access import AccessService
from czero_core.database import Database, SCHEMA_REVISION
from czero_core.identity import VerifiedIdentity
from czero_core.migrate import migrate_database
import czero_core.migrate
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_grants import OAuthGrantService, pkce_challenge
from legacy_oauth import legacy_pair
from czero_core.spaces import SpaceService
from czero_core.wiki import WikiService

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_forward_space_upgrade_preserves_all_old_columns_oauth_and_receipt():
    parsed = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    admin = create_engine(parsed, hide_parameters=True)
    name = 'czero_space_upgrade_' + uuid4().hex
    database = None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE ' + name))
        database = Database(parsed.set(database=name).render_as_string(hide_password=False))
        config = Config()
        config.set_main_option('script_location', str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as c:
            config.attributes['connection'] = c
            command.upgrade(config, '0013_oauth_consent')
        owner_key = uuid4(); issuer = 'https://idp.example.test/' + uuid4().hex
        access = AccessService(database, issuer, owner_key)
        owner = access.resolve(VerifiedIdentity(issuer, 'owner', str(owner_key), 'owner', 'Owner', time.time()+600))
        clients = OAuthClientService(access)
        callback, resource = 'https://client.example.test/callback', 'https://app.example.test/mcp'
        client = clients.register(owner, 'Retained client', [callback], scopes=['c0:read','c0:write'])
        tokens = OAuthGrantService(access, 'czero900', resource)
        pair = legacy_pair(database, owner, issuer, 'czero900', client, resource, {'c0:read','c0:write'})
        page, revision, entity, source, version, job = (uuid4() for _ in range(6))
        body = 'Retained original evidence'
        payload = {'slug': 'retained', 'title': 'Retained', 'body': body, 'expected_revision': None, 'metadata': {}}
        fingerprint = hashlib.sha256(('page.upsert\n' + json.dumps(payload,sort_keys=True,separators=(',',':'))).encode()).hexdigest()
        with database.engine.begin() as c:
            c.execute(text('''INSERT INTO c0_wiki_pages(id,slug,title) VALUES (:id,'retained','Retained')'''), {'id': page})
            c.execute(text('''INSERT INTO c0_wiki_revisions(id,page_id,number,title,body,content_hash,metadata,actor_id)
                VALUES (:id,:page,1,'Retained',:body,:hash,'{}',:actor)'''),
                {'id': revision,'page': page,'body':body,'hash':hashlib.sha256(body.encode()).hexdigest(),'actor':owner.user_id})
            c.execute(text('''INSERT INTO c0_entities(id,kind,label,metadata) VALUES (:id,'investigation','Retained','{}')'''), {'id':entity})
            c.execute(text('''INSERT INTO c0_entity_aliases(normalized,entity_id,label) VALUES ('retained',:id,'Retained')'''), {'id':entity})
            c.execute(text('''INSERT INTO c0_knowledge_events(kind,resource_id,operation,revision,actor_id)
                VALUES ('page',:id,'create',1,:actor)'''), {'id':page,'actor':owner.user_id})
            last_allocated = c.execute(text('''INSERT INTO c0_knowledge_events(kind,resource_id,operation,revision,actor_id)
                VALUES ('page',:id,'fixture_removed',1,:actor) RETURNING id'''), {'id':page,'actor':owner.user_id}).scalar_one()
            c.execute(text('DELETE FROM c0_knowledge_events WHERE id=:id'), {'id':last_allocated})
            c.execute(text('''INSERT INTO c0_knowledge_receipts(actor_id,key,fingerprint,result)
                VALUES (:actor,'retained-receipt',:hash,CAST(:result AS jsonb))'''),
                {'actor':owner.user_id,'hash':fingerprint,'result':json.dumps({'retained_snapshot':True})})
            c.execute(text('''INSERT INTO c0_sources(id,ingest_key,title,metadata) VALUES (:id,:key,'Retained evidence','{}')'''), {'id':source,'key':'b'*64})
            c.execute(text('''INSERT INTO c0_jobs(id,idempotency_key,handler,payload,fingerprint,max_attempts,timeout_seconds)
                VALUES (:id,'retained-job','source.extract',CAST(:payload AS jsonb),:hash,1,30)'''),
                {'id':job,'payload':json.dumps({'version_id':str(version)}),'hash':'c'*64})
            c.execute(text('''INSERT INTO c0_source_versions(id,source_id,number,filename,media_type,content_hash,size_bytes,retain_original,job_id)
                VALUES (:id,:source,1,'retained.txt','text/plain',:hash,1,true,:job)'''), {'id':version,'source':source,'hash':'d'*64,'job':job})
            tables = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            columns = {table:c.execute(text('''SELECT column_name FROM information_schema.columns WHERE table_schema='public'
                AND table_name=:table ORDER BY ordinal_position'''), {'table':table}).scalars().all() for table in tables}
            def snapshot(c):
                return {table:c.execute(text('SELECT row_to_json(t)::text FROM (SELECT ' + ','.join('"'+col+'"' for col in columns[table]) +
                    ' FROM "'+table+'") t ORDER BY row_to_json(t)::text')).scalars().all() for table in tables}
            original = snapshot(c)
            shared = c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one()
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as c:
                assert snapshot(c) == original
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == SCHEMA_REVISION
                assert c.execute(text('SELECT id FROM c0_spaces WHERE shared')).scalar_one() == shared
                assert c.execute(text('SELECT space_id FROM c0_jobs WHERE id=:id'), {'id':job}).scalar_one() == shared
                assert c.execute(text('SELECT feed_cursor=id FROM c0_knowledge_events')).scalar_one()
            assert tokens.verify(pair.access_token, resource=resource).actor.user_id == owner.user_id
            assert WikiService(database, access).upsert_page(owner, **payload, idempotency_key='retained-receipt') == {'retained_snapshot':True}
            assert WikiService(database, access).get_page(owner,page)['content']['id'] == str(revision)
        wiki = WikiService(database, access)
        wiki.update_page(owner,page,'Retained','Later',expected_revision=1,idempotency_key='after-upgrade')
        assert wiki.changes(owner)[-1]['id'] > last_allocated
        private = SpaceService(database, access).create(owner,'Other space',idempotency_key='other-space')
        with pytest.raises(IntegrityError):
            with database.engine.begin() as c:
                c.execute(text('UPDATE c0_jobs SET space_id=:space WHERE id=:id'),
                          {'space':private['id'],'id':job})
    finally:
        if database is not None: database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE IF EXISTS ' + name + ' WITH (FORCE)'))
        admin.dispose()
