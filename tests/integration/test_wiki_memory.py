# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent writers use persisted roles and PostgreSQL receipt transactions."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import threading
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.knowledge import EvidenceNotReady
from czero_core.current_content import ContentSuperseded
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound, WikiService
from test_access import access, account_named, identity, record_unadmitted
from test_sources import sources
from test_wiki import wiki, create_page, create_entity
from test_knowledge import knowledge, evidence

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def upsert(fixture, *, actor=None, **changes):
    service, owner, pages, *_ = fixture
    values = dict(slug='memory-'+uuid4().hex, title='Procedure', body='Selected café 東京',
                  metadata={'status':'unverified'}, idempotency_key=uuid4().hex)
    values.update(changes)
    row = service.upsert_page(owner if actor is None else actor, **values)
    if row['id'] not in pages: pages.append(row['id'])
    return row


def member(fixture, role=Role.EDITOR):
    service, owner, _, _, actors = fixture
    key = uuid4(); label = 'writer-'+key.hex
    record_unadmitted(service.access, key, label)
    account = account_named(service.access, owner, label)
    service.access.set_role(owner, account['id'], role)
    actors.append(account['id'])
    return service.access.resolve(identity(service.access, key, label))


def test_exact_resolution_old_create_and_immutable_history(wiki):
    service, owner, *_ = wiki
    first = create_page(wiki, slug='procedures/network', metadata={'verified':False})
    assert service.resolve_page(owner, first['slug']) == first
    with pytest.raises(KnowledgeNotFound): service.resolve_page(owner, 'procedures/net')
    changed = upsert(wiki, slug=first['slug'], expected_revision=1, body='Revised 🔧')
    assert changed['id'] == first['id'] and changed['revision'] == 2
    assert changed['content']['content_hash'] == hashlib.sha256('Revised 🔧'.encode()).hexdigest()
    with pytest.raises(ContentSuperseded):
        service.get_page(owner, first['id'], revision=1)
    old = service.update_page(owner, first['id'], 'Old client', 'Still works', expected_revision=2, idempotency_key='old-update')
    assert service.resolve_page(owner, first['slug']) == old
    service.delete_page(owner, first['id'], expected_revision=3, idempotency_key='archive')
    with pytest.raises(KnowledgeNotFound): service.resolve_page(owner, first['slug'])
    archived = service.resolve_page(owner, first['slug'], include_deleted=True)
    assert archived['deleted'] and archived['revision'] == 4
    assert [r['number'] for r in service.page_history(owner, first['id'])] == [4]
    for revision in (None,4):
        with pytest.raises(KnowledgeConflict): upsert(wiki, slug=first['slug'], expected_revision=revision)
    with pytest.raises(ContentSuperseded):
        service.get_page(owner, first['id'], revision=1)['content']


def test_create_only_missing_update_and_original_replay_after_archive(wiki):
    service, owner, *_ = wiki
    request = dict(slug='retry', idempotency_key='create')
    with pytest.raises(KnowledgeNotFound): upsert(wiki, **request, expected_revision=1)
    first = upsert(wiki, **request)
    assert upsert(wiki, **request) == first
    with pytest.raises(KnowledgeConflict): upsert(wiki, slug='retry')  # even identical content
    with pytest.raises(KnowledgeConflict): upsert(wiki, **request, body='Changed')
    with pytest.raises(KnowledgeConflict): service.create_page(owner, 'other', 'Procedure', 'Selected café 東京', idempotency_key='create')
    update = dict(slug='retry', body='Second', expected_revision=1, idempotency_key='update')
    second = upsert(wiki, **update)
    service.delete_page(owner, first['id'], expected_revision=2, idempotency_key='archive')
    with pytest.raises(ContentSuperseded):upsert(wiki, **request)
    with pytest.raises(ContentSuperseded):upsert(wiki, **update)
    with pytest.raises(KnowledgeConflict): upsert(wiki, **{**update,'idempotency_key':'stale'})


def test_two_editors_race_create_update_then_reload_without_lost_work(wiki):
    service, owner, pages, *_ = wiki
    actors = [member(wiki), member(wiki)]
    slug = 'race-'+uuid4().hex
    def write(index, revision=None):
        try:
            return upsert(wiki, actor=actors[index], slug=slug, body=('Observation ' if revision is None else 'Revision ')+str(index),
                          expected_revision=revision, idempotency_key=f'write-{revision}-{index}')
        except KnowledgeConflict: return None
    with ThreadPoolExecutor(max_workers=2) as pool: created = list(pool.map(write, range(2)))
    assert sum(row is not None for row in created) == 1
    first = next(row for row in created if row is not None)
    assert write(created.index(first)) == first
    with ThreadPoolExecutor(max_workers=2) as pool: updates = list(pool.map(lambda i:write(i,1), range(2)))
    assert sum(row is not None for row in updates) == 1
    winner = next(row for row in updates if row is not None)
    loser = 1-updates.index(winner)
    latest = service.resolve_page(actors[loser], slug)
    final = upsert(wiki, actor=actors[loser], slug=slug, body=latest['content']['body']+'\nAdditional observation '+str(loser),
                   expected_revision=latest['revision'], idempotency_key='reload-retry')
    assert winner['content']['body'] in final['content']['body'] and final['revision'] == 3
    with pytest.raises(ContentSuperseded):
        service.get_page(owner, first['id'], revision=1)['content']
    with pytest.raises(ContentSuperseded):
        service.get_page(owner, first['id'], revision=2)['content']
    assert len(service.page_history(owner, first['id'])) == 1
    # Identical keys for different persisted actors occupy distinct namespaces.
    one = upsert(wiki, actor=actors[0], idempotency_key='same')
    two = upsert(wiki, actor=actors[1], idempotency_key='same')
    assert one['id'] != two['id']


@pytest.mark.parametrize('changes', [
    {'slug':'Upper'}, {'slug':'a//b'}, {'slug':'a/'}, {'slug':'../bad'}, {'slug':'é'}, {'slug':'x'*129},
    {'slug':''}, {'slug':None}, {'body':'bad\ud800'}, {'body':'bad\0'}, {'body':'é'*65537}, {'body':b'bytes'},
    {'metadata':[]}, {'metadata':{'private':'x'*16384}}, {'metadata':{'private':'\0'}}, {'metadata':{'value':float('nan')}},
    {'title':'bad\nlabel'}, {'title':'x'*257}, {'expected_revision':True}, {'expected_revision':0},
    {'expected_revision':2147483647}, {'idempotency_key':'bad key'}, {'idempotency_key':''},
])
def test_invalid_upsert_rolls_back_without_receipt_or_events(wiki, changes):
    service, owner, *_ = wiki
    with pytest.raises(ValueError): upsert(wiki, **changes)
    assert service.list_pages(owner) == [] and service.changes(owner) == []
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_knowledge_receipts WHERE actor_id=:id'), {'id':owner.user_id}).scalar_one() == 0


def test_utf8_metadata_slug_boundaries_and_invalid_resolve(wiki):
    service, owner, *_ = wiki
    row = upsert(wiki, slug='x'*128, body='é'*65536, metadata={'value':'x'*16371})
    assert service.resolve_page(owner, row['slug']) == row
    for slug in ('X'*128, 'x'*129, 'a/', 'a//b', None, '../bad'):
        with pytest.raises(ValueError, match='invalid_slug'): service.resolve_page(owner, slug)
    with pytest.raises(ValueError): service.resolve_page(owner, row['slug'], include_deleted=1)


@pytest.mark.parametrize('role', list(Role))
def test_resolve_upsert_and_receipt_replay_require_current_persisted_roles(wiki, role):
    service, owner, *_ = wiki
    actor = member(wiki, role); forged = Actor(actor.user_id, Role.ADMIN, True)
    original = upsert(wiki, slug='role-check')
    assert service.resolve_page(forged, original['slug']) == original
    request = dict(slug='member-page', idempotency_key='member')
    if role is Role.READER:
        with pytest.raises(PermissionDenied): upsert(wiki, actor=forged, **request)
    else: upsert(wiki, actor=forged, **request)
    service.access.set_role(owner, actor.user_id, None)
    with pytest.raises(PermissionDenied): service.resolve_page(forged, original['slug'])
    with pytest.raises(PermissionDenied): upsert(wiki, actor=forged, **request)


def test_revoke_editor_while_waiting_for_receipt_lock(wiki, monkeypatch):
    service, owner, *_ = wiki
    editor = member(wiki); authorized = threading.Event(); original = service._authorize
    def authorize(c, actor, role=Role.READER):
        result = original(c, actor, role)
        if actor.user_id == editor.user_id: authorized.set()
        return result
    monkeypatch.setattr(service, '_authorize', authorize)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with service.database.engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(49376)'))
            future = pool.submit(upsert, wiki, actor=editor, slug='waiting')
            assert authorized.wait(5)
            service.access.set_role(owner, editor.user_id, None)
        with pytest.raises(PermissionDenied): future.result(timeout=10)
    assert service.list_pages(owner) == []


def test_interruption_rolls_back_page_revision_event_and_receipt(wiki, monkeypatch):
    service, owner, *_ = wiki
    event = service._event
    def interrupted(*args):
        event(*args)
        raise RuntimeError('simulated interruption')
    with monkeypatch.context() as patch:
        patch.setattr(service, '_event', interrupted)
        with pytest.raises(RuntimeError, match='simulated interruption'): upsert(wiki, slug='interrupted', idempotency_key='retry')
    assert service.list_pages(owner) == [] and service.changes(owner) == []
    row = upsert(wiki, slug='interrupted', idempotency_key='retry')
    with monkeypatch.context() as patch:
        patch.setattr(service, '_event', interrupted)
        with pytest.raises(RuntimeError): upsert(wiki, slug='interrupted', body='new', expected_revision=1, idempotency_key='update')
    assert service.resolve_page(owner, row['slug']) == row
    assert len(service.page_history(owner, row['id'])) == 1
    assert upsert(wiki, slug='interrupted', body='new', expected_revision=1, idempotency_key='update')['revision'] == 2


@pytest.mark.parametrize('state', ['queued','failed'])
def test_claim_rejects_real_but_unready_evidence_atomically_then_retries(knowledge, state):
    service, fixture, source_fixture = knowledge; owner = fixture[1]
    entity = create_entity(fixture); version, _, chunk = evidence(knowledge)
    baseline = service.changes(owner)
    values = dict(evidence_chunk_ids=[str(chunk['id'])], idempotency_key='ready-evidence')
    with service.database.engine.begin() as c:
        c.execute(text('UPDATE c0_source_versions SET state=:state WHERE id=:id'), {'state':state, 'id':version['id']})
    with pytest.raises(EvidenceNotReady) as caught:
        service.create_claim(owner, entity['id'], 'observed', {'confirmed':True}, **values)
    assert isinstance(caught.value, KnowledgeConflict)
    assert service.list_claims(owner) == [] and service.changes(owner) == baseline
    with service.database.engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM c0_knowledge_receipts WHERE actor_id=:id AND key='ready-evidence'"), {'id':owner.user_id}).scalar_one() == 0
    with service.database.engine.begin() as c:
        c.execute(text("UPDATE c0_source_versions SET state='ready' WHERE id=:id"), {'id':version['id']})
    source_fixture[0].delete(owner, version['source_id'], expected_revision=1)
    claim = service.create_claim(owner, entity['id'], 'observed', {'confirmed':True}, **values)
    assert service.get_claim(owner, claim['id'])['evidence'][0]['deleted']
    with service.database.engine.begin() as c:
        c.execute(text("UPDATE c0_source_versions SET state=:state WHERE id=:id"), {'state':state, 'id':version['id']})
    with pytest.raises(EvidenceNotReady):
        service.update_claim(owner, claim['id'], expected_revision=1, metadata={'reviewed':True}, evidence_chunk_ids=[str(chunk['id'])], idempotency_key='annotation')
    assert service.get_claim(owner, claim['id'])['revision'] == 1
