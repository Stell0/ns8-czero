# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real PostgreSQL navigation, privacy, retries, constraints and revocation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from czero_core.cross_space_references import (CrossSpaceReferenceService, ReferenceConflict,
    ReferenceNotFound, ReferenceTargetUnavailable, _ENDPOINTS)
from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.operations import ScopeDenied
from czero_core.spaces import SpaceService
from test_access import access, owner_actor, identity, record_unadmitted, account_named
from test_spaces_http import dispose_spaces
from test_api_keys import setup

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def resources(db, space, type_name):
    """Minimal persisted identities; bodies are deliberately absent from this fixture."""
    result = {kind: {'kind': kind, 'id': str(uuid4())} for kind in _ENDPOINTS}
    result['object']['type_name'] = type_name
    with db.engine.begin() as c:
        params = {'space': UUID(str(space)), 'type': type_name, 'entity': result['entity']['id']}
        for kind, resource in result.items():
            values = {'id': resource['id'], 'key': resource['id'], **params}
            if kind == 'object':
                c.execute(text("INSERT INTO c0_objects(space_id,id,type_name,data,tags) VALUES (:space,:id,:type,'{\"secret\":\"never returned\"}','{}')"), values)
            elif kind in ('page', 'source'):
                c.execute(text('INSERT INTO '+_ENDPOINTS[kind]+'(space_id,id,'+('slug' if kind == 'page' else 'ingest_key')+",title"+(',metadata' if kind == 'source' else '')+") VALUES (:space,:id,:key,'Current guide'"+(",'{}'" if kind == 'source' else '')+')'), values)
            elif kind == 'entity':
                c.execute(text("INSERT INTO c0_entities(space_id,id,kind,label,metadata) VALUES (:space,:id,'concept','Current entity','{}')"), values)
            else:
                c.execute(text("INSERT INTO c0_claims(space_id,id,entity_id,predicate,value,metadata,actor_id,evidence_stale) VALUES (:space,:id,:entity,'supports','{\"secret\":\"never returned\"}','{}',:id,true)"), values)
    return result


@pytest.fixture
def references(access):
    acl, db, _ = access
    owner = owner_actor(access)
    spaces = SpaceService(db, acl)
    ids = [spaces.create(owner, 'Reference '+uuid4().hex, idempotency_key=uuid4().hex)['id'] for _ in range(3)]
    type_name = 'reference-'+uuid4().hex
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO c0_object_types(name,label,schema,unique_fields) VALUES (:type,'Ticket','{\"type\":\"object\"}','{}')"), {'type': type_name})
    endpoints = [resources(db, space, type_name) for space in ids]
    service = CrossSpaceReferenceService(db, acl)
    yield service, owner, ids, endpoints, spaces
    dispose_spaces(db, ids, [type_name])


def grant(fixture, roles):
    service, owner, ids, _, spaces = fixture
    key = uuid4(); username = 'reference-'+key.hex
    record_unadmitted(service.access, key, username)
    account = account_named(service.access, owner, username)
    service.access.set_role(owner, account['id'], Role.EDITOR)
    actor = service.access.resolve(identity(service.access, key, username))
    for space, role in zip(ids, roles):
        if role:
            spaces.set_grant(owner, space, actor.user_id, role,
                             expected_revision=0, idempotency_key=uuid4().hex)
    return actor


def request(fixture, source_kind='object', target_kind='page', *, target_index=1):
    _, _, ids, endpoints, _ = fixture
    return {'space_id': ids[0], 'source': endpoints[0][source_kind],
            'target': {'space_id': ids[target_index], **endpoints[target_index][target_kind]},
            'idempotency_key': uuid4().hex}


def listing(fixture, actor=None, **changes):
    service, owner, ids, endpoints, _ = fixture
    return service.list(actor or owner, space_id=ids[0], source=endpoints[0]['object'],
                        target_space_ids=ids[1:], **changes)


@pytest.mark.parametrize('source_kind', list(_ENDPOINTS))
@pytest.mark.parametrize('target_kind', list(_ENDPOINTS))
def test_all_endpoint_pairs_current_metadata_only(references, source_kind, target_kind):
    service, owner, ids, endpoints, _ = references
    args = request(references, source_kind, target_kind)
    first = service.create(owner, **args)
    assert set(first) == {'reference_id'}
    assert service.create(owner, **args) == first
    assert service.create(owner, **{**args, 'idempotency_key': uuid4().hex}) == first
    result = service.list(owner, space_id=ids[0], source=endpoints[0][source_kind], target_space_ids=[ids[1]])
    assert result['next_after'] is None and len(result['references']) == 1
    summary = result['references'][0]['target']
    assert summary['kind'] == target_kind and summary['revision'] == 1
    assert set(summary) == {'kind','id','space_id','revision', *({'type_name'} if target_kind=='object' else {'predicate','evidence_stale'} if target_kind=='claim' else {'label'})}
    assert 'never returned' not in str(result)
    if target_kind == 'claim': assert summary['evidence_stale'] is True
    with service.database.engine.connect() as c:
        receipt = c.execute(text('SELECT result FROM c0_knowledge_receipts WHERE actor_id=:actor AND key=:key'),
                            {'actor': owner.user_id, 'key': args['idempotency_key']}).scalar_one()
        assert receipt == first


def test_roles_visibility_regrant_and_blind_delete(references):
    service, owner, ids, endpoints, spaces = references
    both = grant(references, [Role.EDITOR, Role.READER, None])
    source_only = grant(references, [Role.EDITOR, None, None])
    target_only = grant(references, [None, Role.EDITOR, None])
    neither = grant(references, [None, None, None])
    reader = grant(references, [Role.READER, Role.READER, None])
    args = request(references)
    ack = service.create(both, **args)
    assert listing(references, reader)['references'][0]['id'] == ack['reference_id']
    assert listing(references, source_only) == {'references': [], 'next_after': None}
    for actor in (target_only, neither):
        with pytest.raises(PermissionDenied): listing(references, actor)
    for actor in (reader, target_only, neither):
        with pytest.raises(PermissionDenied): service.create(actor, **{**args, 'idempotency_key': uuid4().hex})
        with pytest.raises(PermissionDenied): service.delete(actor, space_id=ids[0], source=endpoints[0]['object'],
            reference_id=ack['reference_id'], idempotency_key=uuid4().hex)
    with pytest.raises(ReferenceTargetUnavailable): service.create(source_only, **args)
    spaces.set_grant(owner, ids[1], both.user_id, None, expected_revision=1, idempotency_key=uuid4().hex)
    assert listing(references, both)['references'] == []
    with pytest.raises(ReferenceTargetUnavailable): service.create(both, **args)
    spaces.set_grant(owner, ids[1], both.user_id, Role.READER, expected_revision=2, idempotency_key=uuid4().hex)
    assert listing(references, both)['references']
    spaces.set_grant(owner, ids[1], both.user_id, None, expected_revision=3, idempotency_key=uuid4().hex)
    assert service.delete(both, space_id=ids[0], source=endpoints[0]['object'], reference_id=ack['reference_id'],
                          idempotency_key='blind-delete') is None
    spaces.set_grant(owner, ids[1], both.user_id, Role.READER, expected_revision=4, idempotency_key=uuid4().hex)
    assert listing(references, both)['references'] == []
    assert service.create(both, **args) == ack
    assert listing(references, both)['references'] == []  # replay cannot resurrect
    assert service.create(both, **{**args, 'idempotency_key': uuid4().hex}) != ack


def test_target_unavailable_and_wrong_source_are_indistinguishable(references):
    service, owner, ids, endpoints, _ = references
    source_only = grant(references, [Role.EDITOR, None, None])
    args = request(references)
    for actor, target in [(source_only, args['target']), (owner, {**args['target'], 'id': str(uuid4())}),
                           (owner, {**args['target'], 'space_id': ids[2]}),
                           (owner, {**args['target'], 'kind': 'entity'})]:
        with pytest.raises(ReferenceTargetUnavailable) as error:
            service.create(actor, **{**args, 'target': target})
        assert str(error.value) == 'reference_target_unavailable'
    with pytest.raises(ReferenceNotFound):
        service.create(owner, **{**args, 'source': {**args['source'], 'id': str(uuid4())}})
    object_args = request(references, target_kind='object')
    with pytest.raises(ReferenceTargetUnavailable):
        service.create(owner, **{**object_args, 'target': {**object_args['target'], 'type_name': 'wrong'}})


def test_hidden_edges_do_not_affect_visible_pagination_or_cursors(references):
    service, owner, ids, endpoints, _ = references
    actor = grant(references, [Role.READER, Role.READER, None])
    for kind in _ENDPOINTS:
        for target_index in (1, 2):
            service.create(owner, **request(references, target_kind=kind, target_index=target_index))
    expected = listing(references, actor)['references']
    actual, cursor = [], None
    while True:
        result = listing(references, actor, limit=2, after=cursor)
        actual.extend(result['references'])
        cursor = result['next_after']
        if cursor is None: break
    assert actual == expected and len(actual) == 5
    # An arbitrary UUID is just a boundary. Hidden target space remains hidden.
    assert all(row['target']['space_id'] == ids[1] for row in listing(references, actor, after=uuid4())['references'])
    with service.database.engine.begin() as c:
        c.execute(text('DELETE FROM c0_cross_space_references WHERE target_space_id=:space'), {'space': UUID(ids[2])})
    assert listing(references, actor)['references'] == expected


@pytest.mark.parametrize('kind', list(_ENDPOINTS))
def test_delete_archive_restore_and_updates(references, kind):
    service, owner, ids, endpoints, _ = references
    ack = service.create(owner, **request(references, target_kind=kind))
    table, target = _ENDPOINTS[kind], endpoints[1][kind]['id']
    with service.database.engine.begin() as c:
        c.execute(text('UPDATE '+table+' SET revision=revision+1 WHERE id=:id'), {'id': target})
    assert listing(references)['references'][0]['target']['revision'] == 2
    if kind != 'object':
        with service.database.engine.begin() as c:
            c.execute(text('UPDATE '+table+' SET deleted=true WHERE id=:id'), {'id': target})
        assert listing(references)['references'] == []
        with service.database.engine.begin() as c:
            c.execute(text('UPDATE '+table+' SET deleted=false WHERE id=:id'), {'id': target})
        assert listing(references)['references']
    with service.database.engine.begin() as c:
        if kind == 'entity': c.execute(text('DELETE FROM c0_claims WHERE entity_id=:id'), {'id': target})
        c.execute(text('DELETE FROM '+table+' WHERE id=:id'), {'id': target})
    assert listing(references)['references'] == []
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT 1 FROM c0_cross_space_references WHERE id=:id'), {'id': ack['reference_id']}).first() is None


def test_blind_delete_source_tuple_and_retry_conflicts(references):
    service, owner, ids, endpoints, _ = references
    args = request(references); ack = service.create(owner, **args)
    for source, identifier in [(endpoints[0]['page'], ack['reference_id']), (endpoints[0]['object'], str(uuid4()))]:
        assert service.delete(owner, space_id=ids[0], source=source, reference_id=identifier, idempotency_key=uuid4().hex) is None
    assert listing(references)['references']
    with pytest.raises(ReferenceConflict): service.create(owner, **{**args, 'target': {**endpoints[2]['page'], 'space_id': ids[2]}})
    with ThreadPoolExecutor(max_workers=5) as pool:
        acks = list(pool.map(lambda _: service.create(owner, **{**args, 'idempotency_key': uuid4().hex}), range(10)))
    assert acks == [ack] * 10
    with service.database.engine.connect() as c:
        for table in ('c0_object_events','c0_knowledge_events'):
            assert not c.execute(text('SELECT 1 FROM '+table+' WHERE actor_id=:id'), {'id': owner.user_id}).first()


def test_db_enforces_typed_identity_and_ownership(references):
    service, owner, ids, endpoints, _ = references
    ack = service.create(owner, **request(references))
    for assignment, value in [('target_space_id', ids[2]), ('target_id', str(uuid4())),
                               ('target_entity_id', endpoints[1]['entity']['id']), ('target_page_id', None),
                               ('relation_kind', 'supports')]:
        with pytest.raises(IntegrityError), service.database.engine.begin() as c:
            c.execute(text('UPDATE c0_cross_space_references SET '+assignment+'=:value WHERE id=:id'),
                      {'value': value, 'id': ack['reference_id']})


def test_key_ceiling_write_only_delete_and_revoked_actor(references):
    from czero_core.api_keys import ApiKeyService
    service, owner, ids, endpoints, _ = references
    keys = ApiKeyService(service.access, client_id='fixture', client_secret='synthetic', resource='https://c0.example.test/mcp')
    def issue(scopes, spaces):
        created = keys.create(owner, name='References', scopes=set(scopes), space_ids=spaces)
        return created, keys.verify(created['key'], resource=keys.resource).actor
    ack = service.create(owner, **request(references))
    _, reader = issue(['c0:read'], ids)
    _, source_only = issue(['c0:read','c0:write'], ids[:1])
    created, both = issue(['c0:read','c0:write'], ids)
    _, writer = issue(['c0:write'], ids[:1])
    assert listing(references, source_only)['references'] == []
    with pytest.raises(ReferenceTargetUnavailable): service.create(source_only, **request(references))
    with pytest.raises(ScopeDenied): service.create(reader, **request(references))
    with pytest.raises(ScopeDenied): service.create(writer, **request(references))
    assert service.delete(writer, space_id=ids[0], source=endpoints[0]['object'], reference_id=ack['reference_id'],
                          idempotency_key=uuid4().hex) is None
    keys.revoke(owner, created['id'])
    with pytest.raises(PermissionDenied): listing(references, both)


def test_sql_count_is_independent_of_reference_count(references):
    service, owner, _, _, _ = references
    counts = []
    for n in range(1, 6):
        service.create(owner, **request(references, target_kind=list(_ENDPOINTS)[n-1]))
        statements = []
        def track(*args): statements.append(args[2])
        event.listen(service.database.engine, 'before_cursor_execute', track)
        try: listing(references)
        finally: event.remove(service.database.engine, 'before_cursor_execute', track)
        counts.append(len(statements))
    assert len(set(counts)) == 1 and counts[0] <= 13


def test_revocation_waits_for_admitted_read_and_later_read_is_denied(references):
    service, owner, ids, _, spaces = references
    actor = grant(references, [Role.READER, Role.READER, None])
    service.create(owner, **request(references))
    admitted, release, revoking = Event(), Event(), Event()
    original = service._available
    def pause(c, space, resource, **kwargs):
        admitted.set()
        assert release.wait(3)
        return original(c, space, resource, **kwargs)
    service._available = pause
    def revoke():
        revoking.set()
        return spaces.set_grant(owner, ids[1], actor.user_id, None, expected_revision=1, idempotency_key=uuid4().hex)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            read = pool.submit(listing, references, actor)
            assert admitted.wait(3)
            revoked = pool.submit(revoke)
            assert revoking.wait(3)
            # Inspect PostgreSQL's actual lock wait instead of trusting thread timing.
            with service.database.engine.connect() as c:
                for _ in range(100):
                    waiting = c.execute(text("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted")).scalar_one()
                    if waiting: break
                assert waiting and not revoked.done()
            release.set()
            assert read.result(4)['references']
            assert revoked.result(4)['role'] is None
    finally:
        release.set(); service._available = original
    assert listing(references, actor)['references'] == []


def test_hard_delete_during_create_serializes_and_cascades(references):
    from czero_core.objects import ObjectService
    service, owner, ids, endpoints, _ = references
    admitted, release = Event(), Event()
    original = service._available
    def pause(c, space, resource, **kwargs):
        result = original(c, space, resource, **kwargs)
        if str(space) == ids[1]:
            admitted.set()
            assert release.wait(3)
        return result
    service._available = pause
    target = endpoints[1]['object']
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            created = pool.submit(service.create, owner, **request(references, target_kind='object'))
            assert admitted.wait(3)
            deleted = pool.submit(ObjectService(service.database, service.access).in_space(ids[1]).delete,
                                  owner, target['id'], expected_revision=1)
            release.set()
            ack = created.result(4)
            deleted.result(4)
    finally:
        release.set(); service._available = original
    assert listing(references)['references'] == []
    with service.database.engine.connect() as c:
        assert not c.execute(text('SELECT 1 FROM c0_cross_space_references WHERE id=:id'), {'id': ack['reference_id']}).first()
    with pytest.raises(ReferenceTargetUnavailable): service.create(owner, **request(references, target_kind='object'))


def test_blind_delete_object_type_cannot_be_substituted(references):
    service, owner, ids, endpoints, _ = references
    ack = service.create(owner, **request(references))
    assert service.delete(owner, space_id=ids[0], source={**endpoints[0]['object'],'type_name':'wrong'},
                          reference_id=ack['reference_id'], idempotency_key=uuid4().hex) is None
    assert listing(references)['references']


def test_upgrade_from_schema0037_preserves_existing_constraints_and_rows():
    import asyncio
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from czero_core.database import Database
    from czero_core import migrate
    from evaluation.fixture import disposable_database
    async def check():
        async with disposable_database(os.environ['CZERO_TEST_DATABASE_URL']) as url:
            db = Database(url)
            try:
                config = Config()
                config.set_main_option('script_location', str(Path(migrate.__file__).with_name('migrations')))
                with db.engine.begin() as c:
                    config.attributes['connection'] = c
                    command.upgrade(config, '0037_embedding_context')
                    before = c.execute(text("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conname")).all()
                    identity_before = c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one()
                    c.execute(text("INSERT INTO c0_sources(id,ingest_key,title,metadata) VALUES (:id,:key,'Preserved','{}')"), {'id': uuid4(), 'key': uuid4().hex})
                    rows_before = c.execute(text('SELECT * FROM c0_sources')).all()
                migrate.migrate_database(db)
                migrate.migrate_database(db)
                with db.engine.connect() as c:
                    after = c.execute(text("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conname")).all()
                    assert set(before) <= set(after)
                    assert c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one() == identity_before
                    assert c.execute(text('SELECT * FROM c0_sources')).all() == rows_before
                    assert c.execute(text('SELECT count(*) FROM c0_cross_space_references')).scalar_one() == 0
                assert db.health()['status'] == 'ok'
            finally: db.close()
    asyncio.run(check())
