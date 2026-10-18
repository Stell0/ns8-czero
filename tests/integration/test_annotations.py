# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Annotation revisions describe exact content; they never mutate that content."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from czero_core.annotations import AnnotationService, ContentTarget
from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.operations import ScopeDenied
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound
from test_access import access
from test_auth_http import application
from test_oauth_grants import grants, issue, redeem, RESOURCE
from test_wiki import wiki, create_page, create_entity
from test_objects import objects
from test_sources import sources, upload, execute
from test_spaces import spaces, create, member
from test_knowledge import knowledge, evidence, claim

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def annotations(wiki):
    service = AnnotationService(wiki[0].database, wiki[0].access)
    yield service
    with service.database.engine.begin() as connection:
        connection.execute(text('''DELETE FROM c0_annotation_targets WHERE created_by IN
            (SELECT id FROM c0_accounts WHERE issuer=:issuer)'''), {'issuer': service.access.issuer})


def wiki_target(row):
    return ContentTarget('wiki_revision', row['content']['id'], row['revision'])


def write(service, actor, target, namespace, value, revision=0, key=None):
    return service.update(actor, target, namespace, value,
        expected_revision=revision, idempotency_key=key or uuid4().hex)


def test_namespaces_have_separate_history_and_never_rewrite_evidence(annotations, wiki):
    row = create_page(wiki, metadata={'retained': 'original'}); target = wiki_target(row)
    empty = annotations.get(wiki[1], target, 'verification')
    assert empty['revision'] == 0 and empty['value'] is None and empty['status'] == 'unknown'
    assert annotations.history(wiki[1], target, 'verification')['revisions'] == []
    applicability = write(annotations, wiki[1], target, 'applicability',
        {'products': ['NS8'], 'components': ['backup'], 'version_tags': ['8.4', '8.40'],
         'status': 'applicable', 'extensions': {'future-observation': {'state': 'not-understood'}}}, key='applicable')
    verification = write(annotations, wiki[1], target, 'verification',
        {'status': 'verified', 'verified_at': datetime(2026, 10, 18, tzinfo=timezone.utc), 'confidence': 0.8}, key='verified')
    assert applicability['revision'] == verification['revision'] == 1
    second = write(annotations, wiki[1], target, 'verification', {'status': 'contradicted'}, 1)
    assert second['revision'] == 2
    assert annotations.get(wiki[1], target, 'applicability') == applicability
    history = annotations.history(wiki[1], target, 'verification')['revisions']
    assert [value['number'] for value in history] == [2, 1]
    assert history[1]['value'] == verification['value']
    assert wiki[0].get_page(wiki[1], row['id']) == row
    assert annotations.get(wiki[1], target, 'applicability')['value']['version_tags'] == ['8.4', '8.40']


def test_replay_is_original_snapshot_and_independent_writers_have_one_winner(annotations, wiki):
    target = wiki_target(create_page(wiki))
    first = write(annotations, wiki[1], target, 'verification', {'status': 'unverified'}, key='first')
    def edit(index):
        try:
            return write(annotations, wiki[1], target, 'verification', {'status': 'writer-'+str(index)}, 1)
        except KnowledgeConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, range(2)))
    assert sum(value is not None for value in results) == 1
    assert write(annotations, wiki[1], target, 'verification', {'status': 'unverified'}, key='first') == first
    with pytest.raises(KnowledgeConflict):
        write(annotations, wiki[1], target, 'verification', {'status': 'changed'}, key='first')
    with pytest.raises(KnowledgeConflict):
        write(annotations, wiki[1], target, 'verification', {'status': 'stale'}, 0)
    assert len(annotations.history(wiki[1], target, 'verification')['revisions']) == 2


def test_verification_never_transfers_to_changed_content(annotations, wiki):
    original = create_page(wiki); old = wiki_target(original)
    verified = write(annotations, wiki[1], old, 'verification', {'status': 'verified'})
    changed = wiki[0].update_page(wiki[1], original['id'], 'Edited', 'New evidence interpretation',
        expected_revision=1, idempotency_key=uuid4().hex)
    current = annotations.get(wiki[1], wiki_target(changed), 'verification')
    assert current['status'] == 'unknown' and current['revision'] == 0
    assert annotations.get(wiki[1], old, 'verification')['value'] == verified['value']
    entity = create_entity(wiki)
    target = ContentTarget('entity', entity['id'], 1)
    write(annotations, wiki[1], target, 'verification', {'status': 'verified'})
    wiki[0].update_entity(wiki[1], entity['id'], 'Different', expected_revision=1, idempotency_key=uuid4().hex)
    with pytest.raises(KnowledgeConflict):
        write(annotations, wiki[1], target, 'verification', {'status': 'stale'}, 1)
    assert annotations.get(wiki[1], ContentTarget('entity', entity['id'], 2), 'verification')['status'] == 'unknown'


def test_object_annotations_preserve_strict_payload_and_survive_object_removal(annotations, wiki, objects):
    service, owner, inventory, _ = objects
    row = service.create(owner, inventory, {'name': 'Strict original'})
    target = ContentTarget('object', row['id'], row['revision'])
    stored = write(annotations, owner, target, 'applicability', {'products': ['C0'], 'status': 'vendor-new-state'})
    assert service.get(owner, row['id']) == row
    service.delete(owner, row['id'], expected_revision=1)
    retained = annotations.get(owner, target, 'applicability')
    assert retained['value'] == stored['value'] and retained['status'] == 'vendor-new-state'
    assert retained['target_archived']
    assert len(annotations.history(owner, target, 'applicability')['revisions']) == 1


def test_annotation_space_roles_and_uuid_lookups_are_independent(spaces, annotations, wiki):
    private = create(spaces); selected = annotations.in_space(private['id'])
    page = wiki[0].in_space(private['id']).create_page(wiki[1], 'private-'+uuid4().hex, 'Private', 'Private', idempotency_key=uuid4().hex)
    wiki[2].append(page['id']); target = wiki_target(page)
    stored = write(selected, wiki[1], target, 'verification', {'status': 'verified'})
    with pytest.raises(KnowledgeNotFound): annotations.get(wiki[1], target, 'verification')
    editor = member(spaces, Role.EDITOR)
    with pytest.raises(PermissionDenied): selected.get(editor, target, 'verification')
    spaces[0].set_grant(wiki[1], private['id'], editor.user_id, Role.READER, expected_revision=0, idempotency_key=uuid4().hex)
    assert selected.get(editor, target, 'verification')['value'] == stored['value']
    with pytest.raises(PermissionDenied): write(selected, editor, target, 'verification', {'status': 'denied'}, 1)


def test_real_opaque_token_scopes_guard_annotation_mutations(grants):
    from czero_core.wiki import WikiService
    tokens, _, client, session, *_ = grants
    wiki = WikiService(tokens.access.database, tokens.access)
    service = AnnotationService(tokens.access.database, tokens.access)
    row = wiki.create_page(session.actor, 'annotation-'+uuid4().hex, 'Scoped', 'Scoped evidence', idempotency_key=uuid4().hex)
    target = wiki_target(row)
    try:
        pair = redeem(tokens, client, issue(tokens, client, session, scopes={'c0:read'}))
        reader = tokens.verify(pair.access_token, resource=RESOURCE).actor
        assert service.get(reader, target, 'verification')['status'] == 'unknown'
        with pytest.raises(ScopeDenied): write(service, reader, target, 'verification', {'status': 'denied'})
        pair = redeem(tokens, client, issue(tokens, client, session, scopes={'c0:read', 'c0:write'}))
        writer = tokens.verify(pair.access_token, resource=RESOURCE).actor
        result = write(service, writer, target, 'verification', {'status': 'verified'})
        tokens.revoke(pair.access_token, client['client_id'], resource=RESOURCE)
        with pytest.raises(PermissionDenied): service.get(writer, target, 'verification')
    finally:
        with service.database.engine.begin() as connection:
            connection.execute(text('DELETE FROM c0_annotation_targets WHERE space_id=:space AND target_id=:id'),
                {'space': service._space(connection), 'id': target.id})
            connection.execute(text('DELETE FROM c0_knowledge_events WHERE actor_id=:actor'), {'actor': session.actor.user_id})
            connection.execute(text('DELETE FROM c0_knowledge_receipts WHERE actor_id=:actor'), {'actor': session.actor.user_id})
            connection.execute(text('DELETE FROM c0_wiki_revisions WHERE page_id=:id'), {'id': UUID(row['id'])})
            connection.execute(text('DELETE FROM c0_wiki_pages WHERE id=:id'), {'id': UUID(row['id'])})


def test_source_annotations_keep_original_provenance_and_require_ready_verification(sources, annotations, wiki):
    from czero_core.knowledge import EvidenceNotReady
    version = upload(sources, data=b'Exact retained source observation', retain_original=True)
    target = ContentTarget('source_version', version['id'], version['number'])
    write(annotations, wiki[1], target, 'applicability', {'products': ['NS8'], 'version_tags': ['8.4']})
    with pytest.raises(EvidenceNotReady):
        write(annotations, wiki[1], target, 'verification', {'status': 'verified'}, key='before-ready')
    assert annotations.get(wiki[1], target, 'verification')['revision'] == 0
    execute(sources, 'source.extract', version['id'])
    original = sources[0].document(wiki[1], version['id'])
    original_versions = sources[0].versions(wiki[1], version['source_id'])
    result = write(annotations, wiki[1], target, 'verification', {'status': 'verified'}, key='ready')
    assert result['target']['content_hash'] == version['content_hash']
    assert sources[0].document(wiki[1], version['id']) == original
    assert sources[0].versions(wiki[1], version['source_id']) == original_versions
    sources[0].delete(wiki[1], version['source_id'], expected_revision=1)
    assert annotations.get(wiki[1], target, 'verification')['target_archived']
    assert annotations.get(wiki[1], target, 'verification')['value'] == result['value']


def test_claim_annotation_targets_do_not_change_assertions_or_transfer_after_revision(knowledge, annotations, wiki):
    entity = create_entity(wiki)
    _, _, chunk = evidence(knowledge)
    assertion = claim(knowledge, entity, 'Linux', chunk, metadata={'retained': 'claim metadata'})
    target = ContentTarget('claim', assertion['id'], 1)
    before = knowledge[0].get_claim(wiki[1], assertion['id'])
    result = write(annotations, wiki[1], target, 'verification', {'status': 'verified'}, key='claim-verification')
    assert knowledge[0].get_claim(wiki[1], assertion['id']) == before
    updated = knowledge[0].update_claim(wiki[1], assertion['id'], expected_revision=1,
        metadata={'new': 'observation'}, idempotency_key=uuid4().hex)
    assert updated['value'] == assertion['value']
    assert annotations.get(wiki[1], ContentTarget('claim', assertion['id'], 2), 'verification')['status'] == 'unknown'
    old = annotations.get(wiki[1], target, 'verification')
    assert not old['target_current'] and old['current_content_revision'] == 2
    assert write(annotations, wiki[1], target, 'verification', {'status': 'verified'}, key='claim-verification') == result
    with pytest.raises(KnowledgeConflict):
        write(annotations, wiki[1], target, 'verification', {'status': 'stale'}, 1)
    assert knowledge[0].get_claim(wiki[1], assertion['id'])['evidence'] == before['evidence']


def test_annotation_foreign_keys_reject_cross_space_targets_and_histories(spaces, annotations, wiki):
    private = create(spaces); selected = annotations.in_space(private['id'])
    page = wiki[0].in_space(private['id']).create_page(wiki[1], 'constraint-'+uuid4().hex,
        'Private', 'Private content', idempotency_key=uuid4().hex)
    wiki[2].append(page['id'])
    result = write(selected, wiki[1], wiki_target(page), 'verification', {'status': 'verified'})
    with annotations.database.engine.connect() as connection:
        anchor = dict(connection.execute(text('''SELECT t.* FROM c0_annotation_targets t
            JOIN c0_annotations a ON a.anchor_id=t.id WHERE a.id=:id'''),
            {'id': UUID(result['id'])}).mappings().one())
        shared = annotations._space(connection)
    with pytest.raises(IntegrityError):
        with annotations.database.engine.begin() as connection:
            fields = {**anchor, 'id': uuid4(), 'space_id': shared}
            columns = ','.join(fields)
            values = ','.join(':'+name for name in fields)
            connection.execute(text('INSERT INTO c0_annotation_targets('+columns+') VALUES('+values+')'), fields)
    with pytest.raises(IntegrityError):
        with annotations.database.engine.begin() as connection:
            connection.execute(text('''INSERT INTO c0_annotations(id,space_id,anchor_id,namespace,revision)
                VALUES(:id,:space,:anchor,'applicability',1)'''),
                {'id': uuid4(), 'space': shared, 'anchor': anchor['id']})
    with pytest.raises(IntegrityError):
        with annotations.database.engine.begin() as connection:
            connection.execute(text('''INSERT INTO c0_annotation_revisions(id,space_id,annotation_id,number,value,actor_id)
                VALUES(:id,:space,:annotation,2,'{}'::jsonb,:actor)'''),
                {'id': uuid4(), 'space': shared, 'annotation': UUID(result['id']), 'actor': wiki[1].user_id})


@pytest.mark.parametrize('namespace,value', [
    ('wrong', {}), ('applicability', {'version_tags': '8.4'}),
    ('verification', {'confidence': True}), ('verification', {'confidence': float('nan')}),
    ('verification', {'confidence': 10**500}),
    ('verification', {'verified_at': '2026-10-18T00:00:00'}),
    ('applicability', {'products': ['x']*33}), ('applicability', {'extensions': {'big': 'x'*17000}}),
])
def test_invalid_annotation_values_leave_no_revision_event_or_receipt(annotations, wiki, namespace, value):
    target = wiki_target(create_page(wiki)); before = wiki[0].changes(wiki[1])
    with pytest.raises(ValueError): write(annotations, wiki[1], target, namespace, value, key='bad')
    assert wiki[0].changes(wiki[1]) == before
    with annotations.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_knowledge_receipts WHERE actor_id=:id AND key=\'bad\''), {'id': wiki[1].user_id}).scalar_one() == 0
