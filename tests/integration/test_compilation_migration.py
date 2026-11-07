# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Additive predecessor migration preserves existing authority and authored rows."""
import os
from pathlib import Path
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
import pytest
import czero_core.migrate
from czero_core.access import AccessService
from czero_core.api_keys import ApiKeyService
from czero_core.database import Database, SCHEMA_REVISION
from czero_core.identity import VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.spaces import SpaceService
from czero_core.wiki import WikiService


@pytest.mark.parametrize('predecessor',['0032_api_key_revisions','0033_compilation_state'])
def test_predecessor_upgrade_twice_preserves_every_existing_table(predecessor,tmp_path):
    url = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    name = 'c0_compiler_migration_' + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    db = None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('CREATE DATABASE ' + name))
        db = Database(url.set(database=name).render_as_string(hide_password=False))
        config = Config()
        config.set_main_option('script_location', str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with db.engine.begin() as c:
            config.attributes['connection'] = c
            command.upgrade(config, predecessor)
        issuer, key = 'https://migration.example.invalid/' + uuid4().hex, uuid4()
        access = AccessService(db, issuer, key)
        owner = access.resolve(VerifiedIdentity(issuer, 'owner', str(key), 'owner', 'Owner', time.time()+300))
        space = SpaceService(db, access).create(owner, 'Migration fixture', idempotency_key='space')['id']
        wiki = WikiService(db, access).in_space(space)
        page = wiki.create_page(owner, 'authored', 'Authored', '# Preserve authored knowledge', idempotency_key='authored')
        keys = ApiKeyService(access, client_id='fixture', client_secret='synthetic', resource='https://example.invalid/mcp')
        token = keys.create(owner, name='Retained key', scopes={'c0:read'}, space_ids=[space])['key']
        from czero_core.sources import OriginalStore, SourceService, register_source_handlers
        from czero_core.jobs import default_registry
        registry=default_registry(); originals=OriginalStore(tmp_path/'originals')
        register_source_handlers(registry,db,originals)
        sources=SourceService(db,access,registry,originals).in_space(space)
        original=sources.ingest_text(owner,title='Retained original',body='Synthetic retained original.',idempotency_key='original')
        with db.engine.begin() as c:
            registry.get('source.extract').execute(c,{'version_id':original['id']})
        original_view=sources.get(owner,original['source_id'])
        if predecessor=='0033_compilation_state':
            from czero_core.compilation import CompilationService
            from czero_core.compilation_schema import defaults
            compiler=CompilationService(db,access).in_space(space)
            compiler.configure(owner,{**defaults(),'enabled':True},expected_revision=0,
                authorization_ref='synthetic:migration',idempotency_key='compiler')
            doc=sources.document(owner,original['id']);chunk=sources.chunks(owner,doc['id'])[0]
            bindings=compiler.source_bindings(owner,[{'logical_document_id':original['source_id'],
                'revision_id':original['id'],'chunk_ids':[str(chunk['id'])]}])['source_bindings']
            compiler.propose(owner,{'policy_revision':1,'origin':'manual','reason':'incomplete_page',
                'topic_key':'retained','source_bindings':bindings,'target':{'kind':'page','id':page['id'],
                'revision':page['revision'],'content_id':page['content']['id'],'content_hash':page['content']['content_hash']}},
                idempotency_key='retained-proposal')
        with db.engine.connect() as c:
            names = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            before = {table: c.execute(text('SELECT to_jsonb(t) FROM '+table+' t ORDER BY to_jsonb(t)::text')).scalars().all() for table in names}
        for _ in range(2):
            migrate_database(db)
            with db.engine.connect() as c:
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == SCHEMA_REVISION
                added={'c0_sources':['compilation_publication'],'c0_objects':['compilation_publication'],
                    'c0_compilation_tasks':['purpose','assessment'],
                    'c0_compilation_sources':['assessment_task_id','seen_sweep_id','publication_marker']}
                after={}
                for table in names:
                    expression='to_jsonb(t)-CAST(:added AS text[])'
                    after[table]=c.execute(text('SELECT '+expression+' FROM '+table+' t ORDER BY ('+expression+')::text'),
                        {'added':added.get(table,[])}).scalars().all()
                assert c.execute(text('SELECT compilation_publication FROM c0_sources WHERE id=:id'),{'id':original['source_id']}).scalar_one()>0
                assert not c.execute(text("SELECT 1 FROM c0_compilation_tasks WHERE purpose<>'knowledge' OR assessment<>'{}'::jsonb LIMIT 1")).scalar_one_or_none()
                assert before == after
                new = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'c0_compilation_%' ORDER BY tablename")).scalars().all()
                assert len(new) == 6
                assert all(c.execute(text('SELECT count(*) FROM '+table)).scalar_one() == 0 for table in new if table not in names)
            assert wiki.get_page(owner, page['id']) == page
            assert sources.get(owner,original['source_id'])==original_view
        assert keys.verify(token, resource=keys.resource).actor.user_id == owner.user_id
    finally:
        if db:
            db.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        admin.dispose()
