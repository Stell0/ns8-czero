# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.current_content import ContentSuperseded
from czero_core.wiki import WikiService, KnowledgeConflict, KnowledgeNotFound
from czero_core.migrate import migrate_database
from test_access import access, owner_actor, identity, record_unadmitted, account_named

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def wiki(access):
    acl, database, _ = access
    service, owner = WikiService(database, acl), owner_actor(access)
    pages, entities, actors = [], [], [owner.user_id]
    yield service, owner, pages, entities, actors
    with database.engine.begin() as c:
        for key in pages:
            c.execute(text('DELETE FROM c0_wiki_revisions WHERE page_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_wiki_pages WHERE id=:id'), {'id': key})
        for key in entities:
            c.execute(text('DELETE FROM c0_entity_aliases WHERE entity_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_entities WHERE id=:id'), {'id': key})
        for key in actors:
            c.execute(text('DELETE FROM c0_knowledge_events WHERE actor_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_knowledge_receipts WHERE actor_id=:id'), {'id': key})


def create_page(fixture, **kwargs):
    service, owner, pages, *_ = fixture
    args = dict(slug='page-' + uuid4().hex, title='Inventory', body='# Evidence\n\ncafé 東京 🔧', idempotency_key=uuid4().hex)
    args.update(kwargs)
    row = service.create_page(owner, **args)
    pages.append(row['id'])
    return row


def create_entity(fixture, **kwargs):
    service, owner, _, entities, _ = fixture
    args = dict(kind='project', label='Project ' + uuid4().hex, aliases=[], idempotency_key=uuid4().hex)
    args.update(kwargs)
    row = service.create_entity(owner, **args)
    entities.append(row['id'])
    return row


def test_page_history_exact_markdown_hash_export_and_archive(wiki):
    service, owner, *_ = wiki
    row = create_page(wiki, metadata={'origin': 'external harness'})
    original = row['content']
    assert original['content_hash'] == hashlib.sha256(original['body'].encode()).hexdigest()
    updated = service.update_page(owner, row['id'], 'Revised inventory', '## Revised\n\nNew claims', expected_revision=1,
        metadata={'review': 'pending'}, idempotency_key='revision-2')
    assert updated['revision'] == 2 and updated['id'] == row['id']
    with pytest.raises(ContentSuperseded):service.get_page(owner,row['id'],revision=1)
    assert [r['number'] for r in service.page_history(owner, row['id'])] == [2]
    assert service.export_page(owner, row['id'], format='markdown') == updated['content']['body']
    with pytest.raises(ContentSuperseded):service.export_page(owner,row['id'],revision=1)
    deleted = service.delete_page(owner, row['id'], expected_revision=2, idempotency_key='archive')
    assert deleted['revision'] == 3 and deleted['deleted']
    assert service.list_pages(owner) == []
    with pytest.raises(ContentSuperseded):service.get_page(owner,row['id'],revision=1)
    assert [e['operation'] for e in service.changes(owner)] == ['create', 'update', 'delete']


def test_idempotent_replays_return_exact_snapshot_and_conflicting_keys_are_atomic(wiki):
    service, owner, *_ = wiki
    row = create_page(wiki, slug='replay-page', idempotency_key='create')
    assert service.create_page(owner, 'replay-page', row['title'], row['content']['body'], idempotency_key='create') == row
    with pytest.raises(KnowledgeConflict): service.create_page(owner, 'other-slug', 'Other', '', idempotency_key='create')
    updated = service.update_page(owner, row['id'], 'Changed', 'Changed', expected_revision=1, idempotency_key='update')
    service.update_page(owner, row['id'], 'Later', 'Later', expected_revision=2, idempotency_key='later')
    with pytest.raises(ContentSuperseded):service.update_page(owner,row['id'],'Changed','Changed',expected_revision=1,idempotency_key='update')
    assert service.get_page(owner, row['id'])['revision'] == 3
    assert len(service.list_pages(owner)) == 1


def test_concurrent_expected_revision_allows_only_one_edit(wiki):
    service, owner, *_ = wiki
    row = create_page(wiki)
    def edit(index):
        try:
            return service.update_page(owner, row['id'], 'Concurrent', str(index), expected_revision=1, idempotency_key='edit-' + str(index))
        except KnowledgeConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, range(2)))
    assert sum(row is not None for row in results) == 1
    assert len(service.page_history(owner,row['id']))==1
    assert len(service.changes(owner)) == 2


def test_maximum_escaped_body_survives_receipt_and_replay(wiki):
    service, owner, *_ = wiki
    body = '\x1f' * 131072  # JSON escapes expand; bounds refer to UTF-8 Markdown.
    row = create_page(wiki, slug='bounded', body=body, idempotency_key='bounded')
    assert service.create_page(owner, 'bounded', 'Inventory', body, idempotency_key='bounded') == row
    assert service.get_page(owner, row['id'])['content']['body'] == body


def test_alias_normalization_rename_conflict_and_entity_tombstone(wiki):
    service, owner, *_ = wiki
    row = create_entity(wiki, label='Inventory', aliases=['ＡＳＳＥＴ', 'Straße'])
    assert service.resolve_alias(owner, 'asset')['id'] == service.get_entity(owner, row['id'])['id']
    assert str(service.resolve_alias(owner, 'STRASSE')['id']) == row['id']
    with pytest.raises(KnowledgeConflict): create_entity(wiki, label='Second inventory', aliases=['asset'])
    renamed = service.update_entity(owner, row['id'], 'Hardware inventory', expected_revision=1, metadata={'review': True}, idempotency_key='rename')
    assert renamed['revision'] == 2
    assert str(service.resolve_alias(owner, 'inventory')['id']) == row['id']
    assert str(service.resolve_alias(owner, 'hardware inventory')['id']) == row['id']
    alias = service.add_alias(owner, row['id'], 'Assets', expected_revision=2, idempotency_key='alias')
    assert alias['revision'] == 3
    assert len(service.list_entities(owner, kind='project')) == 1
    assert len(service.list_entities(owner)) == 1
    service.delete_entity(owner, row['id'], expected_revision=3, idempotency_key='delete')
    with pytest.raises(KnowledgeNotFound): service.resolve_alias(owner, 'asset')
    assert service.get_entity(owner, row['id'])['deleted']
    assert service.list_entities(owner) == []


@pytest.mark.parametrize('role', list(Role))
def test_persisted_roles_and_revocation_protect_wiki_even_with_forged_actor(wiki, role):
    service, owner, _, _, actors = wiki
    row = create_page(wiki)
    key = uuid4(); acl = service.access
    record_unadmitted(acl, key, 'member')
    target = account_named(acl, owner, 'member')['id']; actors.append(target)
    acl.set_role(owner, target, role)
    member = acl.resolve(identity(acl, key, 'member'))
    forged = Actor(member.user_id, Role.ADMIN, True)
    assert service.get_page(forged, row['id'])['id'] == service.get_page(owner, row['id'])['id']
    if role == Role.READER:
        with pytest.raises(PermissionDenied): service.update_page(forged, row['id'], 'Denied', 'Denied', expected_revision=1, idempotency_key='denied')
        with pytest.raises(PermissionDenied): service.create_entity(forged, 'host', 'Denied', idempotency_key='denied')
    else:
        service.update_page(member, row['id'], 'Admitted', 'Admitted', expected_revision=1, idempotency_key='allowed')
    acl.set_role(owner, target, None)
    with pytest.raises(PermissionDenied): service.get_page(member, row['id'])
    with pytest.raises(PermissionDenied): service.changes(member)


def test_repeated_migration_preserves_revision_alias_and_change_cursor(wiki):
    service, owner, *_ = wiki
    row = create_page(wiki); entity = create_entity(wiki, aliases=['Stable entity alias'])
    events = service.changes(owner); migrate_database(service.database)
    assert str(service.get_page(owner, row['id'])['content']['id']) == row['content']['id']
    assert str(service.resolve_alias(owner, 'stable entity alias')['id']) == entity['id']
    assert service.changes(owner, after=events[0]['id']) == events[1:]


@pytest.mark.parametrize('changes', [{'body': '\0'}, {'body': 'x' * 131073}, {'slug': '../unsafe'}, {'metadata': {'value': '\0'}}])
def test_invalid_wiki_inputs_leave_no_page_or_receipt(wiki, changes):
    service, owner, *_ = wiki
    with pytest.raises(ValueError): create_page(wiki, **changes)
    assert service.list_pages(owner) == [] and service.changes(owner) == []


def test_alias_limit_collision_and_stale_updates_do_not_partially_write(wiki):
    service, owner, *_ = wiki
    row = create_entity(wiki, label='Canonical', aliases=['Alias ' + str(i) for i in range(15)])
    before = service.get_entity(owner, row['id'])
    with pytest.raises(ValueError, match='alias_limit'):
        service.add_alias(owner, row['id'], 'Overflow', expected_revision=1, idempotency_key='overflow')
    assert service.get_entity(owner, row['id']) == before
    with pytest.raises(KnowledgeConflict):
        service.update_entity(owner, row['id'], 'Canonical', expected_revision=7, idempotency_key='stale')
    assert service.get_entity(owner, row['id']) == before
    assert len(service.changes(owner)) == 1


def test_uncommitted_changes_are_invisible_and_cursor_follows_commit_order(wiki):
    service, owner, *_ = wiki
    row = create_page(wiki)
    first = service.changes(owner)[0]['id']
    with service.database.engine.connect() as c:
        transaction = c.begin()
        c.execute(text('SELECT pg_advisory_xact_lock(49376)'))
        service._event(c, owner, 'page', row['id'], 1, 'fixture_uncommitted')
        assert service.changes(owner, after=first) == []
        transaction.rollback()
    service.update_page(owner, row['id'], 'Committed', 'Committed', expected_revision=1, idempotency_key='committed')
    changes = service.changes(owner, after=first)
    assert len(changes) == 1 and changes[0]['operation'] == 'update' and changes[0]['id'] > first
