# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure existing publication boundaries before deciding to add a bundle."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.annotations import ContentTarget
from czero_core.identity import PermissionDenied, Role
from czero_core.objects import ObjectConflict
from czero_core.wiki import KnowledgeConflict
from test_access import access, account_named, identity, record_unadmitted
from test_annotations import annotations, wiki_target
from test_knowledge import knowledge, evidence
from test_objects import objects
from test_sources import sources
from test_wiki import wiki, create_entity, create_page

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_individual_receipts_recover_lost_replies_but_object_creation_has_no_receipt(knowledge, annotations, objects):
    service, fixture, _ = knowledge
    owner = fixture[1]
    page_args = dict(slug='consolidate-'+uuid4().hex, title='Procedure', body='Observed procedure', idempotency_key=uuid4().hex)
    page = fixture[0].create_page(owner, **page_args)
    fixture[2].append(page['id'])
    # The harness lost the reply and resubmits exactly the same request.
    assert fixture[0].create_page(owner, **page_args) == page
    entity_args = dict(kind='procedure', label='Procedure '+uuid4().hex, idempotency_key=uuid4().hex)
    entity = service.create_entity(owner, **entity_args)
    fixture[3].append(entity['id'])
    assert service.create_entity(owner, **entity_args) == entity
    _, _, chunk = evidence(knowledge)
    claim_args = dict(entity_id=entity['id'], page_id=page['id'], predicate='observed',
        value={'state': 'working'}, evidence_chunk_ids=[str(chunk['id'])], idempotency_key=uuid4().hex)
    claim = service.create_claim(owner, **claim_args)
    assert service.create_claim(owner, **claim_args) == claim
    annotation_args = dict(target=ContentTarget('claim', claim['id'], 1), namespace='verification',
        value={'status': 'unverified'}, expected_revision=0, idempotency_key=uuid4().hex)
    annotation = annotations.update(owner, **annotation_args)
    assert annotations.update(owner, **annotation_args) == annotation
    records, _, type_name, _ = objects
    record = records.create(owner, type_name, {'name': 'lost-response'})
    with pytest.raises(ObjectConflict):
        records.create(owner, type_name, {'name': 'lost-response'})
    assert records.get(owner, record['id'])['revision'] == 1
    assert len(records.list(owner, type_name)) == 1
    assert service.get_claim(owner, claim['id'])['evidence'][0]['body'] == chunk['body']
    with service.database.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM c0_knowledge_receipts WHERE actor_id=:actor'),
            {'actor': owner.user_id}).scalar_one() == 4


def test_independent_writers_can_publish_a_page_before_losing_the_shared_entity_revision(wiki):
    service, owner, pages, *_ = wiki
    entity = create_entity(wiki)
    ready = Barrier(2)
    def publish(index):
        page = service.create_page(owner, 'race-'+uuid4().hex, 'Writer '+str(index),
            'Candidate '+str(index), idempotency_key='candidate-'+str(index))
        pages.append(page['id'])
        ready.wait(timeout=10)
        try:
            service.update_entity(owner, entity['id'], 'Winner '+str(index), expected_revision=1,
                idempotency_key='entity-'+str(index))
            return True
        except KnowledgeConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, range(2)))
    assert sum(results) == 1
    assert service.get_entity(owner, entity['id'])['revision'] == 2
    # The losing writer's page, event and receipt have already committed.
    assert len(service.list_pages(owner)) == 2
    with service.database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM c0_knowledge_receipts WHERE actor_id=:actor AND key LIKE 'candidate-%'"),
            {'actor': owner.user_id}).scalar_one() == 2


def test_revocation_between_individual_steps_leaves_the_first_publication(wiki):
    service, owner, pages, _, actors = wiki
    account_key = uuid4()
    record_unadmitted(service.access, account_key, 'consolidator')
    account = account_named(service.access, owner, 'consolidator')
    service.access.set_role(owner, account['id'], Role.EDITOR)
    editor = service.access.resolve(identity(service.access, account_key, 'consolidator'))
    actors.append(editor.user_id)
    args = dict(slug='revoked-'+uuid4().hex, title='Partial procedure', body='Published first', idempotency_key=uuid4().hex)
    page = service.create_page(editor, **args)
    pages.append(page['id'])
    service.access.set_role(owner, editor.user_id, None)
    with pytest.raises(PermissionDenied):
        service.create_entity(editor, 'procedure', 'Never published', idempotency_key=uuid4().hex)
    with pytest.raises(PermissionDenied):
        service.create_page(editor, **args)
    assert service.get_page(owner, page['id']) == page
    assert service.list_entities(owner) == []


@pytest.mark.parametrize('completed_steps', [1, 2])
def test_harness_failure_cannot_roll_back_previously_committed_publications(wiki, annotations, completed_steps):
    service, owner, *_ = wiki
    page = None
    def consolidate():
        nonlocal page
        page = create_page(wiki, body='Individually committed procedure')
        if completed_steps == 2:
            annotations.update(owner, wiki_target(page), 'applicability', {'status': 'applicable'},
                expected_revision=0, idempotency_key='partial-annotation')
        raise RuntimeError('injected harness failure before the next publication')
    with pytest.raises(RuntimeError, match='injected harness failure'):
        consolidate()
    assert service.get_page(owner, page['id']) == page
    assert len(service.page_history(owner, page['id'])) == 1
    assert annotations.get(owner, wiki_target(page), 'applicability')['revision'] == completed_steps-1
    with service.database.engine.connect() as connection:
        for table in ('c0_knowledge_receipts', 'c0_knowledge_events'):
            assert connection.execute(text('SELECT count(*) FROM '+table+' WHERE actor_id=:actor'),
                {'actor': owner.user_id}).scalar_one() == completed_steps
