# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timezone, timedelta
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.knowledge import KnowledgeService
from czero_core.objects import ObjectService
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound
from test_wiki import wiki, create_entity, create_page
from test_sources import sources, upload, execute
from test_access import access, identity, record_unadmitted, account_named

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def knowledge(wiki, sources):
    service = KnowledgeService(wiki[0].database, wiki[0].access)
    yield service, wiki, sources
    entities = wiki[3]
    with service.database.engine.begin() as c:
        for key in entities:
            c.execute(text('DELETE FROM c0_evidence_links WHERE claim_id IN (SELECT id FROM c0_claims WHERE entity_id=:id)'), {'id': key})
            c.execute(text('DELETE FROM c0_claims WHERE entity_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_relations WHERE source_id=:id OR target_id=:id'), {'id': key})
            c.execute(text('DELETE FROM c0_entity_links WHERE entity_id=:id'), {'id': key})


def evidence(fixture):
    service, _, source_fixture = fixture
    version = upload(source_fixture)
    execute(source_fixture, 'source.extract', version['id'])
    source_service, owner, *_ = source_fixture
    document = source_service.document(owner, version['id'])
    chunk = source_service.chunks(owner, document['id'])[0]
    return version, document, chunk


def claim(fixture, entity, value, chunk, **kwargs):
    service, wiki_fixture, _ = fixture
    return service.create_claim(wiki_fixture[1], entity['id'], 'operating-system', {'name': value},
        evidence_chunk_ids=[str(chunk['id'])], idempotency_key=uuid4().hex, **kwargs)


def test_conflicting_claims_coexist_with_durable_citations_after_source_archive(knowledge):
    service, wiki_fixture, source_fixture = knowledge
    entity = create_entity(wiki_fixture)
    version, _, chunk = evidence(knowledge)
    first = claim(knowledge, entity, 'Linux', chunk)
    second = claim(knowledge, entity, 'BSD', chunk)
    assert first['id'] != second['id']
    assert len(service.list_claims(wiki_fixture[1], entity_id=entity['id'])) == 2
    actual = service.get_claim(wiki_fixture[1], first['id'])
    assert actual['value'] == {'name': 'Linux'} and actual['evidence'][0]['source_hash'] == version['content_hash']
    source_fixture[0].delete(source_fixture[1], version['source_id'], expected_revision=1)
    assert service.get_claim(wiki_fixture[1], second['id'])['evidence'][0]['deleted']
    assert service.get_claim(wiki_fixture[1], first['id'])['evidence'][0]['body'] == chunk['body']


def test_claim_annotation_replay_revision_and_retraction_preserve_assertion_and_evidence(knowledge):
    service, wiki_fixture, _ = knowledge
    entity = create_entity(wiki_fixture); page_row = create_page(wiki_fixture)
    _, _, chunk = evidence(knowledge)
    now = datetime.now(timezone.utc)
    row = claim(knowledge, entity, 'Linux', chunk, page_id=page_row['id'], valid_from=now, valid_to=now + timedelta(days=1))
    changed = service.update_claim(wiki_fixture[1], row['id'], expected_revision=1,
        metadata={'reviewed': True}, evidence_chunk_ids=[str(chunk['id'])], idempotency_key='review')
    assert changed['revision'] == 2 and changed['value'] == row['value']
    assert service.update_claim(wiki_fixture[1], row['id'], expected_revision=1,
        metadata={'reviewed': True}, evidence_chunk_ids=[str(chunk['id'])], idempotency_key='review') == changed
    with pytest.raises(KnowledgeConflict): service.update_claim(wiki_fixture[1], row['id'], expected_revision=1, metadata={}, idempotency_key='stale')
    deleted = service.delete_claim(wiki_fixture[1], row['id'], expected_revision=2, idempotency_key='retract')
    assert deleted['revision'] == 3 and deleted['deleted']
    assert service.list_claims(wiki_fixture[1]) == []
    assert service.get_claim(wiki_fixture[1], row['id'])['evidence']


def test_claim_requires_real_provenance_and_bounded_utc_times(knowledge):
    service, wiki_fixture, _ = knowledge; entity = create_entity(wiki_fixture)
    with pytest.raises(ValueError): service.create_claim(wiki_fixture[1], entity['id'], 'fact', {}, evidence_chunk_ids=[], idempotency_key='empty')
    with pytest.raises(KnowledgeNotFound): service.create_claim(wiki_fixture[1], entity['id'], 'fact', {}, evidence_chunk_ids=[str(uuid4())], idempotency_key='missing')
    _, _, chunk = evidence(knowledge)
    with pytest.raises(ValueError): claim(knowledge, entity, 'Linux', chunk, valid_from=datetime.now())
    start = datetime.now(timezone.utc)
    with pytest.raises(ValueError): claim(knowledge, entity, 'Linux', chunk, valid_from=start, valid_to=start - timedelta(seconds=1))
    assert service.list_claims(wiki_fixture[1]) == []


def test_one_to_three_hops_cycles_direction_and_truncation_are_deterministic(knowledge):
    service, wiki_fixture, _ = knowledge; owner = wiki_fixture[1]
    entities = [create_entity(wiki_fixture) for _ in range(4)]
    for i in range(3):
        service.add_relation(owner, entities[i]['id'], entities[i+1]['id'], 'depends-on', idempotency_key=f'edge-{i}')
    service.add_relation(owner, entities[2]['id'], entities[0]['id'], 'cycle', idempotency_key='cycle')
    for depth, count in [(1, 2), (2, 3), (3, 4)]:
        graph = service.graph(owner, entities[0]['id'], depth=depth, direction='out')
        assert len(graph['nodes']) == count and graph == service.graph(owner, entities[0]['id'], depth=depth, direction='out')
        assert graph['nodes'][0]['depth'] == 0 and graph['nodes'][0]['id'] == entities[0]['id']
    assert len(service.graph(owner, entities[3]['id'], depth=3, direction='in')['nodes']) == 4
    assert service.graph(owner, entities[0]['id'], depth=3, limit=2)['truncated']
    for depth in (True, 0, 4):
        with pytest.raises(ValueError): service.graph(owner, entities[0]['id'], depth=depth)
    with pytest.raises(ValueError): service.graph(owner, entities[0]['id'], direction='sql')


def test_relation_metadata_revision_archive_and_revival(knowledge):
    service, wiki_fixture, _ = knowledge; owner = wiki_fixture[1]
    first, second = create_entity(wiki_fixture), create_entity(wiki_fixture)
    row = service.add_relation(owner, first['id'], second['id'], 'uses', metadata={'source': 'harness'}, idempotency_key='edge')
    assert service.add_relation(owner, first['id'], second['id'], 'uses', metadata={'source': 'harness'}, idempotency_key='duplicate')['id'] == row['id']
    with pytest.raises(KnowledgeConflict): service.add_relation(owner, first['id'], second['id'], 'uses', metadata={}, idempotency_key='different')
    changed = service.update_relation(owner, row['id'], expected_revision=1, metadata={}, deleted=True, idempotency_key='archive')
    assert changed['revision'] == 2 and service.list_relations(owner, first['id']) == []
    with pytest.raises(KnowledgeConflict): service.update_relation(owner, row['id'], expected_revision=1, metadata={}, idempotency_key='stale')
    revived = service.update_relation(owner, row['id'], expected_revision=2, metadata={}, idempotency_key='revive')
    assert revived['id'] == row['id'] and not revived['deleted'] and revived['revision'] == 3


def test_degree_bound_prevents_unbounded_graph_work(knowledge):
    service, wiki_fixture, _ = knowledge; owner = wiki_fixture[1]
    root = create_entity(wiki_fixture)
    for i in range(32):
        leaf = create_entity(wiki_fixture)
        service.add_relation(owner, root['id'], leaf['id'], 'connected', idempotency_key='degree-' + str(i))
    extra = create_entity(wiki_fixture)
    with pytest.raises(ValueError, match='relation_degree_limit'):
        service.add_relation(owner, extra['id'], root['id'], 'overflow', idempotency_key='overflow')
    assert len(service.graph(owner, root['id'], depth=3, limit=100)['nodes']) == 33


def test_source_page_document_chunk_and_deleted_object_references_are_explicit(knowledge):
    service, wiki_fixture, _ = knowledge; owner = wiki_fixture[1]
    entity = create_entity(wiki_fixture); wiki_page = create_page(wiki_fixture)
    version, document, chunk = evidence(knowledge)
    for kind, key in [('page', wiki_page['id']), ('source', version['source_id']), ('document', document['id']), ('chunk', chunk['id'])]:
        row = service.link_entity(owner, entity['id'], kind, key, idempotency_key='link-' + kind)
        assert row['target_id'] == str(key)
    objects = ObjectService(service.database, service.access); type_name = 'knowledge-' + uuid4().hex
    objects.register_type(owner, type_name, 'Linked object', {'type': 'object', 'properties': {'label': {'type': 'string'}}})
    obj = objects.create(owner, type_name, {'label': 'original'})
    try:
        linked = service.link_entity(owner, entity['id'], 'object', obj['id'], idempotency_key='object-link')
        objects.delete(owner, obj['id'], expected_revision=1)
        actual = next(row for row in service.entity_links(owner, entity['id']) if row['target_kind'] == 'object')
        assert actual['missing'] and actual['target_id'] == str(obj['id']) and actual['label_snapshot'] == type_name
        graph = service.graph(owner, entity['id'], depth=1)
        assert len(graph['references']) == 5 and any(ref['missing'] for ref in graph['references'])
        assert service.unlink_entity(owner, entity['id'], linked['id'], idempotency_key='unlink')['deleted']
    finally:
        with service.database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_objects WHERE type_name=:name'), {'name': type_name})
            c.execute(text('DELETE FROM c0_object_events WHERE type_name=:name'), {'name': type_name})
            c.execute(text('DELETE FROM c0_object_types WHERE name=:name'), {'name': type_name})


@pytest.mark.parametrize('role', list(Role))
def test_claim_relation_and_reference_roles_rechecked(knowledge, role):
    service, wiki_fixture, _ = knowledge; owner = wiki_fixture[1]
    entity, other = create_entity(wiki_fixture), create_entity(wiki_fixture)
    version, _, chunk = evidence(knowledge)
    key = uuid4(); acl = service.access
    record_unadmitted(acl, key, 'member'); target = account_named(acl, owner, 'member')['id']; wiki_fixture[4].append(target)
    acl.set_role(owner, target, role); member = acl.resolve(identity(acl, key, 'member')); forged = Actor(member.user_id, Role.ADMIN, True)
    assert service.graph(forged, entity['id'])['nodes']
    if role == Role.READER:
        with pytest.raises(PermissionDenied): service.create_claim(forged, entity['id'], 'fact', {}, evidence_chunk_ids=[str(chunk['id'])], idempotency_key='denied')
        with pytest.raises(PermissionDenied): service.add_relation(forged, entity['id'], other['id'], 'uses', idempotency_key='denied')
        with pytest.raises(PermissionDenied): service.link_entity(forged, entity['id'], 'source', version['source_id'], idempotency_key='denied')
    else:
        service.create_claim(member, entity['id'], 'fact', {}, evidence_chunk_ids=[str(chunk['id'])], idempotency_key='allowed')
    acl.set_role(owner, target, None)
    with pytest.raises(PermissionDenied): service.graph(member, entity['id'])
    with pytest.raises(PermissionDenied): service.list_claims(member)
