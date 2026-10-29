# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""AM0 compatibility fixtures use existing services and disposable actors only."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from czero_core.current_content import ContentSuperseded
from czero_core.knowledge import KnowledgeService
from czero_core.retrieval import SearchService
from czero_core.wiki import KnowledgeConflict
from test_access import access
from test_knowledge import knowledge
from test_sources import sources, upload, execute
from test_wiki import wiki, create_entity, create_page
from test_auth_http import application
from project_contract import REMOVED_HISTORY_OPERATIONS

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
FIXTURES = Path(__file__).parents[1] / 'fixtures' / 'agent_memory'


def test_legacy_operation_names_roles_scopes_and_rest_bindings(application):
    app = application[0]
    baseline = json.loads((FIXTURES / 'legacy_contract.json').read_text())
    registry = app.state.operations
    for expected in baseline['operations']:
        if expected['name'] in REMOVED_HISTORY_OPERATIONS:
            assert expected['name'] not in registry._operations
            continue
        actual = registry.definition(expected['name'])
        for key in ('name', 'minimum_role', 'required_scope', 'read_only'):
            assert actual[key] == expected[key]
    schema = app.openapi()
    for binding in baseline['rest_bindings']:
        if binding['operation'] in REMOVED_HISTORY_OPERATIONS:
            assert 'x-c0-operation' not in schema['paths'][binding['path']][binding['method']]
            continue
        assert schema['paths'][binding['path']][binding['method']]['x-c0-operation']['name'] == binding['operation']


def test_synthetic_agent_memory_preserves_evidence_conflicts_and_history(knowledge):
    service, wiki_fixture, source_fixture = knowledge
    actor = wiki_fixture[1]
    scenario = json.loads((FIXTURES / 'investigation.json').read_text())
    namespace = scenario['namespace_prefix'] + uuid4().hex
    source_service = source_fixture[0]
    evidence = scenario['evidence']
    version = upload(source_fixture, evidence['body'].encode('utf-8'),
        title=namespace + ' ' + evidence['title'], media_type=evidence['media_type'])
    assert version['state'] == 'queued'
    execute(source_fixture, 'source.extract', version['id'])
    document = source_service.document(actor, version['id'])
    chunk = source_service.chunks(actor, document['id'])[0]
    assert document['body'] == evidence['body']
    assert document['text_hash'] == hashlib.sha256(evidence['body'].encode()).hexdigest()
    pages = {}
    for record in scenario['records']:
        pages[record['key']] = create_page(wiki_fixture, slug=namespace + '/' + record['key'],
            title=record['title'], body=record['body'], metadata=record['metadata'])
    entity = create_entity(wiki_fixture, label=namespace, kind='system')
    procedure = pages['procedure']
    claim = service.create_claim(actor, entity['id'], 'readiness', {'state': 'healthy'},
        page_id=procedure['id'], evidence_chunk_ids=[str(chunk['id'])], idempotency_key=namespace + ':claim-a')

    # Independent service/connection represents a later caller using stored data.
    later = KnowledgeService(service.database, service.access)
    stored = later.get_page(actor, procedure['id'])
    assert stored == procedure
    results = SearchService(service.database, service.access).search(actor, 'endpoint', mode='text', kind='wiki')
    assert procedure['id'] in {hit['resource_id'] for hit in results['hits']}
    body = stored['content']['body'] + '\n\n' + scenario['later_observation']
    update = dict(expected_revision=1, metadata={**stored['content']['metadata'], 'status': 'unverified'},
        idempotency_key=namespace + ':update-b')
    revised = later.update_page(actor, stored['id'], stored['title'], body, **update)
    assert later.update_page(actor, stored['id'], stored['title'], body, **update) == revised
    with pytest.raises(KnowledgeConflict):
        service.update_page(actor, stored['id'], stored['title'], 'Stale overwrite',
            expected_revision=1, idempotency_key=namespace + ':stale-a')
    conflicting = later.create_claim(actor, entity['id'], 'readiness', {'state': 'unavailable'},
        page_id=procedure['id'], evidence_chunk_ids=[str(chunk['id'])], idempotency_key=namespace + ':claim-b')
    assert conflicting['id'] != claim['id']
    assert {item['value']['state'] for item in later.list_claims(actor, entity_id=entity['id'])} == {'healthy', 'unavailable'}
    with pytest.raises(ContentSuperseded):later.get_page(actor, stored['id'], revision=1)
    assert later.get_page(actor, stored['id'])['content']['metadata']['status'] == 'unverified'
    assert [row['number'] for row in later.page_history(actor, stored['id'])] == [2]
    for row in (claim, conflicting):
        citation = later.get_claim(actor, row['id'])['evidence'][0]
        assert citation['chunk_id'] == str(chunk['id'])
        assert citation['version_id'] == str(version['id'])
        assert citation['source_hash'] == version['content_hash']
    # Normal original cleanup preserves text and evidence identity.
    execute(source_fixture, 'source.cleanup', version['id'])
    assert source_service.document(actor, version['id'])['body'] == evidence['body']
    assert not source_service.originals.path(version['id']).exists()
