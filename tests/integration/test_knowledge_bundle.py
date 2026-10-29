from czero_core.current_content import ContentSuperseded
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""A consolidation is one authorized publication, including its retry receipt."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import text, event

from czero_core.bundles import KnowledgeBundleService
from czero_core.identity import PermissionDenied, Role
from czero_core.operations import ScopeDenied
from czero_core.annotations import ContentTarget
from czero_core.knowledge import EvidenceNotReady
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound
from test_access import access, account_named, identity, record_unadmitted
from test_auth_http import application
from test_annotations import annotations
from test_knowledge import knowledge, evidence
from test_objects import objects
from test_sources import sources
from test_wiki import wiki, create_page
from test_spaces import spaces, create, member
from test_oauth_grants import grants, issue, redeem, RESOURCE

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def bundle(knowledge, annotations, objects):
    service = KnowledgeBundleService(knowledge[0].database, knowledge[0].access)
    yield service
    # The ordinary domain fixtures own disposal; successful bundle writes use
    # the same actor/event identities and must not create a separate lifecycle.
    fixture = knowledge[1]
    with service.database.engine.connect() as connection:
        rows = connection.execute(text("SELECT kind,resource_id FROM c0_knowledge_events WHERE actor_id=:actor AND kind IN ('page','entity')"),
            {'actor': fixture[1].user_id}).mappings().all()
    for row in rows:
        identifiers = fixture[2 if row['kind'] == 'page' else 3]
        if str(row['resource_id']) not in {str(value) for value in identifiers}:
            identifiers.append(row['resource_id'])


def step(operation, **arguments):
    return {'operation': operation, 'arguments': arguments}


def ref(index, path='id'):
    return {'$result': index, 'path': path}


def metadata_state(service, owner):
    with service.database.engine.connect() as connection:
        return {table: connection.execute(text('SELECT count(*) FROM '+table+' WHERE actor_id=:actor'),
            {'actor': owner.user_id}).scalar_one() for table in ('c0_knowledge_events','c0_knowledge_receipts')}


def test_late_conflict_rolls_back_all_domains_events_and_receipt(bundle, wiki, objects):
    owner = wiki[1]
    slug = 'atomic-'+uuid4().hex
    before = metadata_state(bundle, owner)
    operations = [
        step('wiki.upsert', slug=slug, title='Procedure', body='All or nothing'),
        step('entity.create', kind='procedure', label='Atomic '+uuid4().hex),
        step('object.create', type_name=objects[2], data={'name':'atomic-record'}),
        step('wiki.upsert', slug=slug, title='Stale', body='Never committed', expected_revision=999)]
    with pytest.raises(KnowledgeConflict):
        bundle.apply(owner, operations, idempotency_key='all-or-nothing')
    with pytest.raises(KnowledgeNotFound):
        wiki[0].resolve_page(owner, slug)
    assert wiki[0].list_entities(owner) == []
    assert objects[0].list(owner, objects[2]) == []
    assert metadata_state(bundle, owner) == before
    assert objects[0].events(owner) == []


def test_canonical_bundle_resolves_prior_results_and_replays_original_whole_snapshot(bundle, knowledge, annotations, objects):
    _, fixture, _ = knowledge
    owner = fixture[1]
    _, _, chunk = evidence(knowledge)
    operations = [
        step('entity.create', kind='procedure', label='Consolidated '+uuid4().hex),
        step('wiki.upsert', slug='bundle-'+uuid4().hex, title='Procedure', body='Retained procedure'),
        step('object.create', type_name=objects[2], data={'name':'consolidated-record'}),
        step('claim.create', entity_id=ref(0), page_id=ref(1), predicate='observed',
            value={'state':'working'}, evidence_chunk_ids=[str(chunk['id'])]),
        step('entity.link', entity_id=ref(0), target_kind='object', target_id=ref(2)),
        step('annotation.update', target={'kind':'wiki_revision','id':ref(1,'content.id'),'revision':ref(1,'content.number')},
            namespace='verification', value={'status':'unverified'}, expected_revision=0),
        step('annotation.update', target={'kind':'claim','id':ref(3),'revision':ref(3,'revision')},
            namespace='applicability', value={'products':['C0'],'version_tags':['0.43'],'status':'applicable'}, expected_revision=0)]
    result = bundle.apply(owner, operations, idempotency_key='canonical')
    assert len(result['results']) == 7
    assert result['results'][3]['entity_id'] == result['results'][0]['id']
    assert result['results'][3]['page_id'] == result['results'][1]['id']
    assert metadata_state(bundle, owner)['c0_knowledge_receipts'] == 1
    assert bundle.apply(owner, operations, idempotency_key='canonical') == result
    original = result['results'][1]
    fixture[0].update_page(owner, original['id'], 'Later', 'Newer content', expected_revision=1, idempotency_key='later')
    with pytest.raises(ContentSuperseded):bundle.apply(owner, operations, idempotency_key='canonical')
    assert fixture[0].get_page(owner, original['id'])['revision'] == 2
    assert knowledge[0].get_claim(owner, result['results'][3]['id'])['evidence'][0]['body'] == chunk['body']


def test_independent_bundle_writers_have_one_winner_and_no_losing_object(bundle, wiki, objects):
    page = create_page(wiki)
    before = metadata_state(bundle, wiki[1])
    def publish(index):
        operations = [step('object.create', type_name=objects[2], data={'name':'writer-'+str(index)}),
            step('wiki.upsert', slug=page['slug'], title='Winner '+str(index), body='Winner', expected_revision=1)]
        try:
            return bundle.apply(wiki[1], operations, idempotency_key='writer-'+str(index))
        except KnowledgeConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, range(2)))
    assert sum(row is not None for row in results) == 1
    assert len(objects[0].list(wiki[1], objects[2])) == 1
    assert len(objects[0].events(wiki[1])) == 1
    assert wiki[0].get_page(wiki[1], page['id'])['revision'] == 2
    after = metadata_state(bundle, wiki[1])
    assert after == {key:value+1 for key,value in before.items()}


def test_concurrent_same_key_submissions_and_lost_response_retries_are_one_commit(bundle, wiki, objects):
    operations = [step('object.create', type_name=objects[2], data={'name':'same-key'}),
        step('wiki.upsert', slug='same-key-'+uuid4().hex, title='Once', body='Once')]
    def submit(_):
        return bundle.apply(wiki[1], operations, idempotency_key='same-key')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(submit, range(2))
    assert first == second == submit(2)
    assert len(objects[0].list(wiki[1], objects[2])) == len(objects[0].events(wiki[1])) == 1
    assert metadata_state(bundle, wiki[1])['c0_knowledge_receipts'] == 1
    with pytest.raises(KnowledgeConflict):
        bundle.apply(wiki[1], [step('object.create', type_name=objects[2], data={'name':'different'})], idempotency_key='same-key')


def test_injected_database_failure_rolls_back_histories_events_cursors_and_retry_receipt(bundle, wiki, objects):
    operations = [step('wiki.upsert', slug='failure-'+uuid4().hex, title='Rollback', body='Rollback'),
        step('object.create', type_name=objects[2], data={'name':'rollback'}),
        step('annotation.update', target={'kind':'object','id':ref(1),'revision':1}, namespace='verification',
            value={'status':'unverified'}, expected_revision=0)]
    with bundle.database.engine.connect() as connection:
        before = list(connection.execute(text('SELECT * FROM c0_space_cursors ORDER BY space_id,kind')))
    def inject(connection, cursor, statement, parameters, context, executemany):
        if 'INSERT INTO c0_annotation_revisions' in statement:
            raise RuntimeError('injected database failure')
    event.listen(bundle.database.engine, 'before_cursor_execute', inject)
    try:
        with pytest.raises(RuntimeError, match='injected database failure'):
            bundle.apply(wiki[1], operations, idempotency_key='retry-after-rollback')
    finally:
        event.remove(bundle.database.engine, 'before_cursor_execute', inject)
    with bundle.database.engine.connect() as connection:
        assert list(connection.execute(text('SELECT * FROM c0_space_cursors ORDER BY space_id,kind'))) == before
    assert wiki[0].list_pages(wiki[1]) == []
    assert objects[0].list(wiki[1], objects[2]) == []
    assert metadata_state(bundle, wiki[1]) == {'c0_knowledge_events':0,'c0_knowledge_receipts':0}
    assert len(bundle.apply(wiki[1], operations, idempotency_key='retry-after-rollback')['results']) == 3


def test_independent_reader_cannot_observe_a_partial_bundle_before_commit(bundle, wiki, objects):
    slug = 'visibility-'+uuid4().hex
    operations = [step('wiki.upsert', slug=slug, title='Together', body='Together'),
        step('object.create', type_name=objects[2], data={'name':'visible-together'})]
    paused, resume = Event(), Event()
    def pause(connection, cursor, statement, parameters, context, executemany):
        if 'INSERT INTO c0_objects(' in statement:
            paused.set()
            assert resume.wait(timeout=10)
    event.listen(bundle.database.engine, 'before_cursor_execute', pause)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(bundle.apply, wiki[1], operations, idempotency_key='visibility')
            try:
                assert paused.wait(timeout=10)
                with pytest.raises(KnowledgeNotFound):
                    wiki[0].resolve_page(wiki[1], slug)
                assert objects[0].list(wiki[1], objects[2]) == []
                assert metadata_state(bundle, wiki[1]) == {'c0_knowledge_events':0,'c0_knowledge_receipts':0}
            finally:
                resume.set()
            result = future.result(timeout=10)
    finally:
        event.remove(bundle.database.engine, 'before_cursor_execute', pause)
    assert wiki[0].resolve_page(wiki[1], slug) == result['results'][0]
    assert objects[0].get(wiki[1], result['results'][1]['id'])['data'] == {'name':'visible-together'}


def test_revocation_while_waiting_for_mutex_prevents_every_write_and_later_retry(bundle, wiki, objects, monkeypatch):
    owner = wiki[1]
    account_key = uuid4()
    record_unadmitted(bundle.access, account_key, 'bundle-writer')
    account = account_named(bundle.access, owner, 'bundle-writer')
    bundle.access.set_role(owner, account['id'], Role.EDITOR)
    editor = bundle.access.resolve(identity(bundle.access, account_key, 'bundle-writer'))
    wiki[4].append(editor.user_id)
    entered = Event()
    authorize = bundle._authorize
    def observe(connection, actor, role=Role.READER):
        current = authorize(connection, actor, role)
        entered.set()
        return current
    monkeypatch.setattr(bundle, '_authorize', observe)
    operations = [step('object.create', type_name=objects[2], data={'name':'denied'})]
    with ThreadPoolExecutor(max_workers=1) as pool:
        with bundle.database.engine.begin() as blocker:
            blocker.execute(text('SELECT pg_advisory_xact_lock(49375)'))
            future = pool.submit(bundle.apply, editor, operations, idempotency_key='revoked-waiter')
            assert entered.wait(timeout=10)
            bundle.access.set_role(owner, editor.user_id, None)
        with pytest.raises(PermissionDenied):
            future.result(timeout=10)
    assert objects[0].list(owner, objects[2]) == []
    assert metadata_state(bundle, editor) == {'c0_knowledge_events':0,'c0_knowledge_receipts':0}


def test_space_grants_cap_writes_and_references_never_select_another_space(spaces, bundle, wiki, objects):
    private = create(spaces)
    selected = bundle.in_space(private['id'])
    editor = member(spaces, Role.EDITOR)
    wiki[4].append(editor.user_id)
    operations = [step('wiki.upsert', slug='private-'+uuid4().hex, title='Private', body='Private')]
    with pytest.raises(PermissionDenied):
        selected.apply(editor, operations, idempotency_key='private')
    grant = spaces[0].set_grant(wiki[1], private['id'], editor.user_id, Role.READER, expected_revision=0, idempotency_key='reader')
    with pytest.raises(PermissionDenied):
        selected.apply(editor, operations, idempotency_key='private')
    spaces[0].set_grant(wiki[1], private['id'], editor.user_id, Role.EDITOR, expected_revision=grant['revision'], idempotency_key='editor')
    private_result = selected.apply(editor, operations, idempotency_key='private')
    wiki[2].append(private_result['results'][0]['id'])
    assert private_result['space_id'] == private['id']
    with pytest.raises(KnowledgeNotFound):
        bundle.apply(wiki[1], [step('object.create', type_name=objects[2], data={'name':'never-visible'}),
            step('annotation.update', target={'kind':'wiki_revision','id':private_result['results'][0]['content']['id'],'revision':1},
                namespace='verification', value={'status':'unverified'}, expected_revision=0)], idempotency_key='wrong-space')
    assert objects[0].list(wiki[1], objects[2]) == []
    shared_result = bundle.apply(wiki[1], operations, idempotency_key='private')
    assert shared_result['space_id'] != private_result['space_id']
    assert shared_result['results'][0]['id'] != private_result['results'][0]['id']


@pytest.mark.parametrize('scopes,allowed', [({'c0:read'},False),({'c0:write'},True)])
def test_real_opaque_scopes_and_revoked_token_replay(grants, scopes, allowed):
    tokens, _, client, session, *_ = grants
    service = KnowledgeBundleService(tokens.access.database, tokens.access)
    operations = [step('wiki.upsert', slug='scoped-bundle-'+uuid4().hex, title='Scoped', body='Scoped')]
    pair = redeem(tokens, client, issue(tokens, client, session, scopes=scopes))
    actor = tokens.verify(pair.access_token, resource=RESOURCE).actor
    try:
        if not allowed:
            with pytest.raises(ScopeDenied):
                service.apply(actor, operations, idempotency_key='scoped-bundle')
        else:
            original = service.apply(actor, operations, idempotency_key='scoped-bundle')
            assert original['results'][0]['revision'] == 1
        tokens.revoke(pair.access_token, client['client_id'], resource=RESOURCE)
        with pytest.raises(PermissionDenied):
            service.apply(actor, operations, idempotency_key='scoped-bundle')
    finally:
        with service.database.engine.begin() as connection:
            for table in ('c0_knowledge_events','c0_knowledge_receipts'):
                connection.execute(text('DELETE FROM '+table+' WHERE actor_id=:actor'), {'actor':session.actor.user_id})
            connection.execute(text('DELETE FROM c0_wiki_revisions WHERE page_id IN (SELECT id FROM c0_wiki_pages WHERE slug=:slug)'), {'slug':operations[0]['arguments']['slug']})
            connection.execute(text('DELETE FROM c0_wiki_pages WHERE slug=:slug'), {'slug':operations[0]['arguments']['slug']})


@pytest.mark.parametrize('operations', [[], [{}]*26, [step('jobs.enqueue', kind='anything')],
    [step('wiki.upsert', slug='x', title='x', body='x', space_id=str(uuid4()))],
    [step('entity.create', kind='x', label=ref(0))],
    [step('entity.create', kind='x', label={'$result':True,'path':'id'})],
    [step('wiki.upsert', slug='x', title='x', body='x'),step('entity.create', kind='x', label=ref(0,'content.body'))],
    [step('wiki.upsert', slug='x', title='x', body='x'*262144)]])
def test_invalid_steps_references_and_aggregate_budget_have_no_writes(bundle, wiki, operations):
    with pytest.raises(ValueError):
        bundle.apply(wiki[1], operations, idempotency_key='invalid')
    assert wiki[0].list_pages(wiki[1]) == []
    assert metadata_state(bundle, wiki[1]) == {'c0_knowledge_events':0,'c0_knowledge_receipts':0}


def test_twenty_five_steps_are_accepted_and_forward_or_missing_result_fields_roll_back(bundle, wiki):
    operations = [step('wiki.upsert', slug='bounded-'+uuid4().hex, title='Bounded', body='Bounded') for _ in range(25)]
    assert len(bundle.apply(wiki[1], operations, idempotency_key='twenty-five')['results']) == 25
    before = metadata_state(bundle, wiki[1])
    with pytest.raises(ValueError, match='invalid_bundle_reference'):
        bundle.apply(wiki[1], [step('entity.create', kind='procedure', label='No content '+uuid4().hex),
            step('entity.update', entity_id=ref(0,'content.id'), label='Never', expected_revision=1)], idempotency_key='missing-field')
    assert metadata_state(bundle, wiki[1]) == before


def test_allowlisted_maintenance_lifecycle_uses_trusted_helpers_and_retains_prior_evidence(bundle, knowledge, annotations, objects):
    _, fixture, _ = knowledge
    owner = fixture[1]
    version, _, chunk = evidence(knowledge)
    operations = [
        step('object.create', type_name=objects[2], data={'name':'lifecycle'}),
        step('entity.create', kind='procedure', label='First '+uuid4().hex),
        step('entity.create', kind='component', label='Second '+uuid4().hex),
        step('entity.alias', entity_id=ref(1), value='Alias '+uuid4().hex, expected_revision=1),
        step('entity.update', entity_id=ref(1), label='Updated '+uuid4().hex, expected_revision=2),
        step('relation.create', source_id=ref(1), target_id=ref(2), kind='uses'),
        step('relation.update', relation_id=ref(5), expected_revision=1, metadata={'retained':True}, deleted=True),
        step('wiki.upsert', slug='lifecycle-'+uuid4().hex, title='Retained', body='Retained'),
        step('claim.create', entity_id=ref(1), page_id=ref(7), predicate='observed', value={'state':'working'},
            evidence_chunk_ids=[str(chunk['id'])], valid_from='2026-10-18T11:00:00+02:00'),
        step('claim.update', claim_id=ref(8), expected_revision=1, metadata={'review':'retained'}),
        step('entity.link', entity_id=ref(1), target_kind='object', target_id=ref(0)),
        step('entity.unlink', entity_id=ref(1), link_id=ref(10)),
        step('object.update', object_id=ref(0), data={'name':'updated-lifecycle'}, expected_revision=1),
        step('annotation.update', target={'kind':'object','id':ref(0),'revision':ref(12,'revision')},
            namespace='applicability', value={'knowledge_type':'procedure','source_references':[{'kind':'chunk','id':str(chunk['id'])}],
                'supersedes':[{'kind':'wiki_revision','id':ref(7,'content.id'),'revision':1}]}, expected_revision=0),
        step('claim.archive', claim_id=ref(8), expected_revision=2),
        step('wiki.archive', page_id=ref(7), expected_revision=1),
        step('entity.archive', entity_id=ref(2), expected_revision=1),
        step('object.delete', object_id=ref(0), expected_revision=2)]
    result = bundle.apply(owner, operations, idempotency_key='lifecycle')
    rows = result['results']
    assert len(rows) == 18 and rows[3]['revision'] == 2 and rows[4]['revision'] == 3
    assert rows[6]['deleted'] and rows[8]['valid_from'] == '2026-10-18T09:00:00+00:00'
    assert rows[9]['value'] == {'state':'working'} and rows[17]['deleted']
    retained = annotations.get(owner, ContentTarget('object',rows[0]['id'],2), 'applicability')
    assert retained['value'] == rows[13]['value'] and retained['target_archived']
    with pytest.raises(ContentSuperseded):fixture[0].get_page(owner, rows[7]['id'], revision=1)
    assertion = knowledge[0].get_claim(owner, rows[8]['id'])
    assert assertion['deleted'] and assertion['value'] == {'state':'working'}
    assert assertion['evidence'][0]['source_hash'] == version['content_hash']
    with pytest.raises(ContentSuperseded):bundle.apply(owner, operations, idempotency_key='lifecycle')
    assert metadata_state(bundle, owner)['c0_knowledge_receipts'] == 1


def test_unready_real_claim_evidence_rolls_back_earlier_publications(bundle, knowledge):
    _, fixture, _ = knowledge
    version, _, chunk = evidence(knowledge)
    with bundle.database.engine.begin() as connection:
        connection.execute(text("UPDATE c0_source_versions SET state='failed' WHERE id=:id"), {'id':version['id']})
    operations = [step('wiki.upsert', slug='unready-'+uuid4().hex, title='Never', body='Never'),
        step('entity.create', kind='procedure', label='Never '+uuid4().hex),
        step('claim.create', entity_id=ref(1), page_id=ref(0), predicate='unready', value={}, evidence_chunk_ids=[str(chunk['id'])])]
    with pytest.raises(EvidenceNotReady):
        bundle.apply(fixture[1], operations, idempotency_key='unready')
    assert fixture[0].list_pages(fixture[1]) == fixture[0].list_entities(fixture[1]) == []
    assert metadata_state(bundle, fixture[1]) == {'c0_knowledge_events':0,'c0_knowledge_receipts':0}
