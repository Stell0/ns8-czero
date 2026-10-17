# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent spaces must not share content, cursors or receipt namespaces."""
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.objects import ObjectNotFound
from czero_core.wiki import KnowledgeNotFound
from test_spaces import access, spaces, create, member
from test_wiki import wiki
from test_objects import objects
from test_sources import sources
from test_knowledge import knowledge
from test_embeddings import indexed
from test_retrieval import search
from test_spaces import delegated_space
from test_oauth_grants import grants
from test_auth_http import application

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_private_wiki_names_replays_histories_and_feeds_are_independent(spaces, wiki):
    service, owner, pages, entities, _ = wiki
    private = create(spaces)
    selected = service.in_space(private['id'])
    shared_id = spaces[0].list(owner)['spaces'][0]['id']
    explicit_shared = service.in_space(shared_id)
    before = service.changes(owner)
    slug = 'isolated-' + uuid4().hex
    request = dict(slug=slug, title='Shared title', body='Shared body', idempotency_key='same-key')
    shared = service.create_page(owner, **request); pages.append(shared['id'])
    hidden = selected.create_page(owner, **{**request, 'title': 'Private title', 'body': 'Private body'})
    pages.append(hidden['id'])
    assert service.create_page(owner, **request) == shared
    assert explicit_shared.create_page(owner, **request) == shared
    assert selected.create_page(owner, **{**request, 'title': 'Private title', 'body': 'Private body'}) == hidden
    assert service.resolve_page(owner, slug) == shared
    assert selected.resolve_page(owner, slug) == hidden
    assert [row['id'] for row in selected.list_pages(owner)] == [hidden['id']]
    assert hidden['id'] not in {row['id'] for row in service.list_pages(owner)}
    for target, foreign in ((service, hidden), (selected, shared)):
        for call in (lambda: target.get_page(owner, foreign['id']),
                     lambda: target.page_history(owner, foreign['id']),
                     lambda: target.update_page(owner, foreign['id'], 'No', 'No', expected_revision=1, idempotency_key=uuid4().hex)):
            with pytest.raises(KnowledgeNotFound): call()
    last_shared = service.changes(owner)[-1]['id']
    changed = selected.update_page(owner, hidden['id'], 'Private later', 'Later', expected_revision=1, idempotency_key='later')
    assert selected.page_history(owner, hidden['id'])[0]['number'] == 2
    assert selected.get_page(owner, hidden['id'], revision=1)['content'] == hidden['content']
    assert service.changes(owner, after=last_shared) == []
    another = service.update_page(owner, shared['id'], 'Shared later', 'Later', expected_revision=1, idempotency_key='later')
    assert service.changes(owner)[-1]['id'] == last_shared + 1
    assert selected.changes(owner)[-1]['id'] == 2
    assert changed['revision'] == another['revision'] == 2
    assert service.changes(owner)[:len(before)] == before
    for target in (service, selected):
        row = target.create_entity(owner, 'investigation', 'Same Alias', idempotency_key='alias')
        entities.append(row['id'])
        assert target.resolve_alias(owner, 'same alias')['id'] == row['id']


def test_grants_guard_content_and_forged_actor_space_never_selects_a_space(spaces, wiki):
    service, owner, pages, *_ = wiki
    catalog = spaces[0]; private = create(spaces)
    selected = service.in_space(private['id'])
    hidden = selected.create_page(owner, 'guarded-' + uuid4().hex, 'Secret', 'Secret', idempotency_key=uuid4().hex)
    pages.append(hidden['id'])
    editor = member(spaces, Role.EDITOR)
    for target in (selected, service.in_space(str(uuid4()))):
        with pytest.raises(PermissionDenied): target.list_pages(editor)
    catalog.set_grant(owner, private['id'], editor.user_id, Role.READER, expected_revision=0, idempotency_key=uuid4().hex)
    assert selected.get_page(editor, hidden['id']) == hidden
    with pytest.raises(PermissionDenied): selected.update_page(editor, hidden['id'], 'Denied', '', expected_revision=1, idempotency_key='denied')
    forged = Actor(editor.user_id, Role.ADMIN, True, space_id=UUID(private['id']))
    with pytest.raises(KnowledgeNotFound): service.get_page(forged, hidden['id'])
    catalog.set_grant(owner, private['id'], editor.user_id, None, expected_revision=1, idempotency_key=uuid4().hex)
    with pytest.raises(PermissionDenied): selected.get_page(editor, hidden['id'])


def test_global_types_and_private_object_uniqueness_relations_and_events(spaces, objects):
    service, owner, inventory, projects = objects
    private = create(spaces); selected = service.in_space(private['id'])
    assert selected.get_type(owner, inventory) == service.get_type(owner, inventory)
    shared = service.create(owner, inventory, {'name': 'Same unique value'})
    hidden = selected.create(owner, inventory, {'name': 'Same unique value'})
    assert service.list(owner, inventory) == [shared]
    assert selected.list(owner, inventory) == [hidden]
    for target, foreign in ((service, hidden), (selected, shared)):
        with pytest.raises(ObjectNotFound): target.get(owner, foreign['id'])
        with pytest.raises(ObjectNotFound): target.relations(owner, foreign['id'])
        with pytest.raises(ObjectNotFound): target.update(owner, foreign['id'], {'name': 'Denied'}, expected_revision=1)
    before = service.events(owner)[-1]['id']
    selected.delete(owner, hidden['id'], expected_revision=1)
    assert [e['operation'] for e in selected.events(owner)] == ['create', 'delete']
    assert service.events(owner, after=before) == []
    target = selected.create(owner, projects, {'name': 'Other'})
    with pytest.raises(ObjectNotFound): selected.add_relation(owner, shared['id'], target['id'], 'depends-on', source_type=inventory, target_type=projects)
    with pytest.raises(IntegrityError):
        with service.database.engine.begin() as c:
            c.execute(text('''INSERT INTO c0_object_relations(space_id,id,source_id,target_id,kind)
                VALUES (:space,:id,:source,:target,'cross-space')'''),
                {'space': UUID(private['id']), 'id': uuid4(), 'source': shared['id'], 'target': target['id']})
    own = selected.create(owner, inventory, {'name': 'Private relation'})
    relation = selected.add_relation(owner, own['id'], target['id'], 'depends-on', source_type=inventory, target_type=projects)
    with pytest.raises(ObjectNotFound): service.remove_relation(owner, relation['id'])
    assert len(selected.relations(owner, own['id'])) == 1


def test_sources_originals_citations_replay_and_worker_ownership(spaces, sources):
    from io import BytesIO
    from czero_core.sources import SourceNotFound
    from test_sources import execute
    service, owner, registry, created = sources
    private = create(spaces); selected = service.in_space(private['id'])
    shared = service.ingest(owner, BytesIO(b'Isolated evidence'), title='Same title', filename='proof.txt', media_type='text/plain', retain_original=True)
    hidden = selected.ingest(owner, BytesIO(b'Isolated evidence'), title='Same title', filename='proof.txt', media_type='text/plain', retain_original=True)
    created.extend([shared['source_id'], hidden['source_id']])
    assert shared['source_id'] != hidden['source_id'] and shared['id'] != hidden['id']
    assert selected.ingest(owner, BytesIO(b'Isolated evidence'), title='Same title', filename='proof.txt', media_type='text/plain', retain_original=True) == hidden
    for row in (shared, hidden): execute(sources, 'source.extract', row['id'])
    private_document = selected.document(owner, hidden['id'])
    private_chunk = selected.chunks(owner, private_document['id'])[0]
    assert selected.original(owner, hidden['id'])[0].read_bytes() == b'Isolated evidence'
    for call in (lambda: service.get(owner, hidden['source_id']),
                 lambda: service.versions(owner, hidden['source_id']),
                 lambda: service.original(owner, hidden['id']),
                 lambda: service.document(owner, hidden['id']),
                 lambda: service.citation(owner, private_chunk['id']),
                 lambda: service.retry(owner, hidden['id'], expected_generation=1)):
        with pytest.raises(SourceNotFound): call()
    assert service.chunks(owner, private_document['id']) == []
    assert [r['source_id'] for r in selected.search(owner, 'Isolated')] == [hidden['source_id']]
    assert [r['source_id'] for r in service.search(owner, 'Isolated')] == [shared['source_id']]
    values = {'title': 'Text evidence', 'body': 'Immutable private text', 'idempotency_key': 'text-replay'}
    first = selected.ingest_text(owner, **values); created.append(first['source_id'])
    second = service.ingest_text(owner, **values); created.append(second['source_id'])
    assert first['source_id'] != second['source_id']
    execute(sources, 'source.extract', first['id'])
    assert selected.ingest_text(owner, **values) == first
    assert service.ingest_text(owner, **values) == second
    with service.database.engine.connect() as c:
        for table in ('c0_sources','c0_source_versions','c0_documents','c0_chunks'):
            count = c.execute(text('SELECT count(*) FROM ' + table + ' WHERE space_id=:space'), {'space': UUID(private['id'])}).scalar_one()
            assert count >= 2
        jobs = c.execute(text('''SELECT space_id FROM c0_jobs WHERE payload->>'version_id' IN (:one,:two)'''),
            {'one': str(hidden['id']), 'two': str(first['id'])}).scalars().all()
        assert len(jobs) == 3 and set(jobs) == {UUID(private['id'])}
    with service.database.engine.begin() as c:
        c.execute(text('DELETE FROM c0_knowledge_receipts WHERE actor_id=:id'), {'id': owner.user_id})


def test_claims_graph_and_typed_references_reject_cross_space_targets(spaces, knowledge, objects):
    from io import BytesIO
    from test_sources import execute
    service, wiki_fixture, source_fixture = knowledge
    owner = wiki_fixture[1]; private = create(spaces)
    selected = service.in_space(private['id']); source_service = source_fixture[0].in_space(private['id'])
    version = source_service.ingest(owner, BytesIO(b'Private claim evidence'), title='Private evidence', filename='proof.txt', media_type='text/plain')
    source_fixture[3].append(version['source_id']); execute(source_fixture, 'source.extract', version['id'])
    document = source_service.document(owner, version['id']); chunk = source_service.chunks(owner, document['id'])[0]
    hidden_page = selected.create_page(owner, 'private-' + uuid4().hex, 'Private', 'Private', idempotency_key=uuid4().hex)
    wiki_fixture[2].append(hidden_page['id'])
    private_entity = selected.create_entity(owner, 'investigation', 'Private Entity', idempotency_key=uuid4().hex)
    other_private = selected.create_entity(owner, 'investigation', 'Private Neighbor', idempotency_key=uuid4().hex)
    shared_entity = service.create_entity(owner, 'investigation', 'Shared Entity', idempotency_key=uuid4().hex)
    wiki_fixture[3].extend([private_entity['id'], other_private['id'], shared_entity['id']])
    values = dict(predicate='observed', value={'unknown': True, 'space_id': 'user-value'}, evidence_chunk_ids=[str(chunk['id'])], idempotency_key='private-claim')
    claim = selected.create_claim(owner, private_entity['id'], page_id=hidden_page['id'], **values)
    assert selected.get_claim(owner, claim['id'])['evidence'][0]['body'] == 'Private claim evidence'
    assert selected.get_claim(owner, claim['id'])['value']['space_id'] == 'user-value'
    assert service.list_claims(owner) == []
    with pytest.raises(KnowledgeNotFound): service.get_claim(owner, claim['id'])
    with pytest.raises(KnowledgeNotFound): service.graph(owner, private_entity['id'])
    with pytest.raises(KnowledgeNotFound): selected.create_claim(owner, shared_entity['id'], **{**values, 'idempotency_key': 'cross-entity'})
    with pytest.raises(KnowledgeNotFound): service.create_claim(owner, shared_entity['id'], **{**values, 'idempotency_key': 'cross-evidence'})
    relation = selected.add_relation(owner, private_entity['id'], other_private['id'], 'relates', idempotency_key='relation')
    with pytest.raises(KnowledgeNotFound): service.update_relation(owner, relation['id'], expected_revision=1, metadata={}, idempotency_key='foreign-relation')
    with pytest.raises(KnowledgeNotFound): selected.add_relation(owner, private_entity['id'], shared_entity['id'], 'denied', idempotency_key='cross-relation')
    object_service, _, inventory, _ = objects
    object_service.reference_resolvers = {**service.reference_resolvers(), **source_fixture[0].reference_resolvers()}
    selected_objects = object_service.in_space(private['id'])
    hidden_object = selected_objects.create(owner, inventory, {'name': 'Private object'})
    linked = selected.link_entity(owner, private_entity['id'], 'object', hidden_object['id'], idempotency_key='object-link')
    selected.link_entity(owner, private_entity['id'], 'page', hidden_page['id'], idempotency_key='page-link')
    assert len(selected.graph(owner, private_entity['id'], depth=2)['nodes']) == 2
    for kind, identifier, type_name in (('page', hidden_page['id'], 'page'), ('entity', private_entity['id'], 'entity'),
            ('claim', claim['id'], 'claim'), ('chunk', chunk['id'], 'chunk'), ('document', document['id'], 'document'),
            ('source', version['source_id'], 'source')):
        assert str(selected_objects.resolve_reference(owner, kind, identifier, type_name)['id']) == str(identifier)
        with pytest.raises(ObjectNotFound): object_service.resolve_reference(owner, kind, identifier, type_name)
    selected_objects.delete(owner, hidden_object['id'], expected_revision=1)
    assert next(r for r in selected.entity_links(owner, private_entity['id']) if r['id'] == linked['id'])['missing']
    assert len(selected.graph(owner, private_entity['id'])['nodes']) == 2


def test_search_filters_before_limits_provider_inputs_and_derivative_counts(spaces, indexed):
    from czero_core.retrieval import SearchService, SearchLimits
    store, (_, wiki_fixture, _), embedding_calls = indexed
    private = create(spaces); owner = wiki_fixture[1]
    private_wiki = wiki_fixture[0].in_space(private['id'])
    shared = wiki_fixture[0].create_page(owner, 'public-' + uuid4().hex, 'Public title', 'alpha public evidence', idempotency_key=uuid4().hex)
    wiki_fixture[2].append(shared['id'])
    for number in range(70):
        row = private_wiki.create_page(owner, 'private-' + str(number) + '-' + uuid4().hex,
            'Private title', 'alpha private evidence ' * 10, idempotency_key=uuid4().hex)
        wiki_fixture[2].append(row['id'])
    # Trusted indexing maintains every instance space and derives ownership from
    # each immutable revision. Retrieval and its provider inputs are scoped.
    for _ in range(40):
        with store.database.engine.begin() as c: store._index_batch(c)
    assert store.status(owner)['indexed'] == 1
    assert store.in_space(private['id']).status(owner)['indexed'] == 70
    scored = []
    class Scorer:
        def score(self, query, candidates):
            scored.extend(candidates)
            return {'usage': {}, 'truncated_candidates': 0, 'scores': {c['id']: .9 for c in candidates}}
    search = SearchService(store.database, wiki_fixture[0].access, embedding_client=store.client,
        scorer=Scorer(), scorer_mode='rerank', limits=SearchLimits(max_limit=4, candidates=4))
    embedding_calls.clear()
    result = search.search(owner, 'alpha', mode='hybrid')
    assert result['candidate_count'] == 1 and result['scored_count'] == 1
    assert {r['resource_id'] for r in result['hits']} == {shared['id']}
    assert all('private' not in c['text'] for c in scored)
    assert all('private' not in str(c) for c in embedding_calls)
    selected = search.in_space(private['id'])
    result = selected.search(owner, 'alpha', mode='text', rerank='off')
    assert result['candidate_count'] == 4 and len(result['hits']) == 4
    assert all(r['resource_id'] != shared['id'] for r in result['hits'])
    stranger = member(spaces, Role.READER)
    before = len(scored), len(embedding_calls)
    with pytest.raises(PermissionDenied): selected.search(stranger, 'private', mode='hybrid')
    with pytest.raises(PermissionDenied): store.in_space(private['id']).status(stranger)
    assert (len(scored), len(embedding_calls)) == before
    # Force a real ANN scan's underfilled response to prove the scoped exact
    # fallback, independent of the planner choosing a full exact scan itself.
    with store.database.engine.begin() as c:
        class UnderfilledScan:
            def execute(self, statement, parameters=None):
                if 'WITH nearest AS MATERIALIZED' in str(statement):
                    statement = text('SELECT id,source_chunk_id,wiki_chunk_id,0.0 AS distance FROM c0_embeddings WHERE false')
                    parameters = None
                return c.execute(statement, parameters)
        rows = store.nearest(UnderfilledScan(), [1,0,0], limit=4)
        assert len(rows) == 1
        assert str(rows[0]['wiki_chunk_id']) in {
            str(row[0]) for row in c.execute(text('SELECT id FROM c0_wiki_chunks WHERE revision_id=:id'), {'id': shared['content']['id']})}


@pytest.fixture
def delegated_wiki(delegated_space):
    from czero_core.wiki import WikiService
    from test_oauth_grants import CALLBACK
    catalog, private, *_ = delegated_space
    service = WikiService(catalog.database, catalog.access).in_space(private['id'])
    grant_fixture = delegated_space[5]
    tokens, clients, _, owner_session, *rest = grant_fixture
    client = clients.register(owner_session.actor, 'Space matrix ' + uuid4().hex,
        [CALLBACK], scopes=['c0:read','c0:write','c0:admin'])
    complete = type(grant_fixture)((tokens, clients, client, owner_session, *rest))
    try:
        yield service, (*delegated_space[:5], complete)
    finally:
        with catalog.database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id': UUID(client['client_id'])})
            for table in ('c0_knowledge_receipts', 'c0_knowledge_events', 'c0_wiki_revisions', 'c0_wiki_pages'):
                c.execute(text('DELETE FROM ' + table + ' WHERE space_id=:space'), {'space': UUID(private['id'])})


_SCOPE_SETS = [frozenset(scope for bit, scope in enumerate(('c0:read','c0:write','c0:admin')) if mask & (1 << bit)) for mask in range(1,8)]


@pytest.mark.parametrize('application_role', list(Role))
@pytest.mark.parametrize('grant_role', [None, Role.READER, Role.EDITOR])
@pytest.mark.parametrize('scopes', _SCOPE_SETS, ids=lambda s: '+'.join(sorted(s)))
def test_actual_role_grant_and_oauth_scope_matrix(delegated_wiki, application_role, grant_role, scopes):
    from czero_core.operations import ScopeDenied
    from test_oauth_grants import issue, redeem, RESOURCE
    service, fixture = delegated_wiki
    catalog, private, editor, native, _, grant_fixture = fixture
    tokens, _, client, owner_session, *_ = grant_fixture
    owner = owner_session.actor
    if grant_role is not Role.EDITOR:
        catalog.set_grant(owner, private['id'], editor.user_id, grant_role, expected_revision=1, idempotency_key=uuid4().hex)
    catalog.access.set_role(owner, editor.user_id, application_role)
    role_scopes = {Role.READER: {'c0:read'}, Role.EDITOR: {'c0:read','c0:write'}, Role.ADMIN: {'c0:read','c0:write','c0:admin'}}[application_role]
    if not scopes <= role_scopes:
        with pytest.raises(PermissionDenied): issue(tokens, client, native, scopes=set(scopes))
        return
    pair = redeem(tokens, client, issue(tokens, client, native, scopes=set(scopes)))
    actor = tokens.verify(pair.access_token, resource=RESOURCE).actor
    page = service.create_page(owner, 'matrix', 'Observed', 'Evidence', idempotency_key='owner-page')
    allowed_read = application_role is Role.ADMIN or grant_role is not None
    allowed_write = application_role is Role.ADMIN or (application_role is Role.EDITOR and grant_role is Role.EDITOR)
    for permitted, scope, call in (
        (allowed_read, 'c0:read', lambda: service.get_page(actor, page['id'])),
        (allowed_write, 'c0:write', lambda: service.upsert_page(actor, 'agent-write', 'Observed', 'Evidence', idempotency_key='agent-page'))):
        if not permitted:
            with pytest.raises(PermissionDenied) as denied: call()
            assert not isinstance(denied.value, ScopeDenied)
        elif scope not in scopes:
            with pytest.raises(ScopeDenied) as denied: call()
            assert denied.value.scope == scope
        else:
            assert call()['revision'] == 1


def test_waiting_writer_cannot_use_revoked_token_after_regrant(delegated_wiki, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from test_oauth_grants import issue, redeem, RESOURCE
    service, fixture = delegated_wiki
    catalog, private, editor, native, _, grant_fixture = fixture
    tokens, _, client, owner_session, *_ = grant_fixture
    pair = redeem(tokens, client, issue(tokens, client, native, scopes={'c0:read','c0:write'}))
    actor = tokens.verify(pair.access_token, resource=RESOURCE).actor
    authorized = threading.Event(); original = service._authorize
    def authorize(c, current, role=Role.READER):
        result = original(c, current, role)
        if current.user_id == editor.user_id: authorized.set()
        return result
    monkeypatch.setattr(service, '_authorize', authorize)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with service.database.engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(49376)'))
            future = pool.submit(service.upsert_page, actor, 'waiting', 'Denied', 'Denied', idempotency_key='waiting')
            assert authorized.wait(5)
            catalog.set_grant(owner_session.actor, private['id'], editor.user_id, None, expected_revision=1, idempotency_key='revoke')
            catalog.set_grant(owner_session.actor, private['id'], editor.user_id, Role.EDITOR, expected_revision=2, idempotency_key='regrant')
        with pytest.raises(PermissionDenied): future.result(timeout=10)
    assert service.list_pages(owner_session.actor) == []
    assert service.changes(owner_session.actor) == []
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_knowledge_receipts WHERE space_id=:space'), {'space': UUID(private['id'])}).scalar_one() == 0
