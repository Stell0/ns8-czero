# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Schema-0015 protected data and real delegated authority survive both migrations."""
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import os
from pathlib import Path
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from czero_core.access import AccessService
from czero_core.annotations import AnnotationService, ContentTarget
from czero_core.database import Database
from czero_core.identity import PermissionDenied, Role, VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.knowledge import KnowledgeService
from czero_core.migrate import migrate_database
import czero_core.migrate
from czero_core.objects import ObjectService
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_grants import OAuthGrantService, pkce_challenge
from legacy_oauth import legacy_pair
from czero_core.sources import OriginalStore, SourceService, register_source_handlers
from czero_core.spaces import SpaceService

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_schema_0015_upgrade_preserves_every_old_column_and_protected_authority(tmp_path):
    parsed = make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    admin = create_engine(parsed, hide_parameters=True)
    name = 'czero_annotation_upgrade_' + uuid4().hex
    database = None
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.execute(text('CREATE DATABASE ' + name))
        database = Database(parsed.set(database=name).render_as_string(hide_password=False))
        config = Config()
        config.set_main_option('script_location', str(Path(czero_core.migrate.__file__).with_name('migrations')))
        with database.engine.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, '0015_content_spaces')
        issuer = 'https://idp.example.test/' + uuid4().hex
        owner_key, editor_key = uuid4(), uuid4()
        access = AccessService(database, issuer, owner_key)
        def identity(key, username):
            return VerifiedIdentity(issuer, username, str(key), username, username.title(), time.time()+600)
        owner = access.resolve(identity(owner_key, 'owner'))
        with pytest.raises(PermissionDenied): access.resolve(identity(editor_key, 'editor'))
        editor_id = next(row['id'] for row in access.list_accounts(owner) if row['account_key'] == editor_key)
        # Seed the old membership schema; current role writers also revoke schema-0017 authority.
        with database.engine.begin() as connection:
            connection.execute(text("INSERT INTO c0_memberships(account_id,role) VALUES (:id,'editor')"), {'id': editor_id})
        editor = access.resolve(identity(editor_key, 'editor'))
        spaces = SpaceService(database, access)
        private = spaces.create(owner, 'Retained protected space', idempotency_key='space')
        grant = spaces.set_grant(owner, private['id'], editor_id, Role.READER,
            expected_revision=0, idempotency_key='grant')
        knowledge = KnowledgeService(database, access).in_space(private['id'])
        request = {'slug': 'retained-procedure', 'title': 'Retained', 'body': 'Original café 東京',
                   'metadata': {'retained': True}, 'idempotency_key': 'first-page'}
        first = knowledge.upsert_page(owner, **request)
        current = knowledge.upsert_page(owner, **{**request, 'body': 'Later retained body',
            'expected_revision': 1, 'idempotency_key': 'later-page'})
        entity = knowledge.create_entity(owner, 'procedure', 'Retained aliases', aliases=['Retained alternate'], idempotency_key='entity')
        registry = default_registry(); originals = OriginalStore(tmp_path / 'originals')
        register_source_handlers(registry, database, originals)
        sources = SourceService(database, access, registry, originals).in_space(private['id'])
        source = sources.ingest(owner, BytesIO('Exact original evidence café 東京'.encode()),
            title='Retained evidence', filename='retained.txt', media_type='text/plain', retain_original=True)
        with database.engine.begin() as connection:
            registry.get('source.extract').execute(connection, {'version_id': source['id']})
        document = sources.document(owner, source['id']); chunk = sources.chunks(owner, document['id'])[0]
        assertion = knowledge.create_claim(owner, entity['id'], 'observed', {'state': 'unknown'},
            page_id=first['id'], evidence_chunk_ids=[chunk['id']], idempotency_key='claim')
        objects = ObjectService(database, access)
        objects.register_type(owner, 'retained-type', 'Retained type', {'type': 'object',
            'properties': {'name': {'type': 'string', 'maxLength': 64}}, 'required': ['name'], 'additionalProperties': False}, ['name'])
        objects.create(owner, 'retained-type', {'name': 'Same key'})
        protected = objects.in_space(private['id'])
        record = protected.create(owner, 'retained-type', {'name': 'Same key'})
        other = protected.create(owner, 'retained-type', {'name': 'Other key'})
        protected.add_relation(owner, record['id'], other['id'], 'related-to', source_type='retained-type', target_type='retained-type')
        callback, resource = 'https://client.example.test/callback', 'https://app.example.test/mcp'
        client = OAuthClientService(access).register(owner, 'Retained client', [callback], scopes=['c0:read', 'c0:write'])
        tokens = OAuthGrantService(access, 'czero900', resource)
        pair = legacy_pair(database, editor, issuer, 'czero900', client, resource, {'c0:read','c0:write'})
        original_bytes = originals.path(source['id']).read_bytes()
        with database.engine.connect() as connection:
            tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            assert len(tables) == 40
            columns = {table: connection.execute(text('''SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:table ORDER BY ordinal_position'''), {'table': table}).scalars().all() for table in tables}
            def snapshot(connection):
                return {table: connection.execute(text('SELECT row_to_json(t)::text FROM (SELECT ' +
                    ','.join('"'+column+'"' for column in columns[table]) + ' FROM "'+table+'") t ORDER BY row_to_json(t)::text')).scalars().all() for table in tables}
            before = snapshot(connection)
            shared = connection.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one()
        for _ in range(2):
            migrate_database(database)
            with database.engine.connect() as connection:
                assert snapshot(connection) == before
                assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0019_client_onboarding'
                assert connection.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one() == shared
            delegated = tokens.verify(pair.access_token, resource=resource).actor
            assert knowledge.get_page(delegated, first['id']) == current
            assert knowledge.upsert_page(owner, **request) == first
            assert sources.document(delegated, source['id']) == document
            assert knowledge.get_claim(delegated, assertion['id'])['evidence'][0]['chunk_id'] == str(chunk['id'])
            assert spaces.list_grants(owner, private['id'])['grants'][0]['revision'] == grant['revision']
            assert originals.path(source['id']).read_bytes() == original_bytes
            assert hashlib.sha256(original_bytes).hexdigest() == source['content_hash']
            with pytest.raises(PermissionDenied):
                knowledge.upsert_page(delegated, **{**request, 'expected_revision': 2, 'idempotency_key': 'denied'})
        annotations = AnnotationService(database, access).in_space(private['id'])
        target = ContentTarget('wiki_revision', current['content']['id'], current['revision'])
        assert annotations.get(owner, target, 'verification')['status'] == 'unknown'
        stored = annotations.update(owner, target, 'verification', {'status': 'verified'}, expected_revision=0, idempotency_key='new-annotation')
        assert annotations.get(delegated, target, 'verification')['value'] == stored['value']
        assert database.health()['status'] == 'ok'
    finally:
        if database is not None: database.close()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.execute(text('DROP DATABASE IF EXISTS ' + name + ' WITH (FORCE)'))
        admin.dispose()
