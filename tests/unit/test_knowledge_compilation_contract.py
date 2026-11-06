# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Freeze public M0 inputs and exercise the existing source-plan trust boundary."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from agentic_retrieval.layer import validate_plan

FIXTURES = ROOT / 'tests/fixtures/knowledge_compilation'


def construction_inputs():
    # The baseline questions are intentionally not loaded by construction.
    sources = json.loads((FIXTURES / 'sources.json').read_text())
    response = json.loads((FIXTURES / 'model-response.json').read_text())
    corpus = []
    for item in sources:
        sha = hashlib.sha256(item['body'].encode()).hexdigest()
        corpus.append({'id': item['key'], 'generation': 'synthetic-current',
            'content_hash': sha, 'body': item['body'], 'url': item['url'],
            'product': item['product'], 'version': item['version'], 'language': item['language'],
            'chunks': [{'chunk_id': item['key'], 'body': item['body'], 'content_hash': sha}]})
    records = []
    for record in response['records']:
        bindings = []
        for support in record['support']:
            source = next(d for d in corpus if d['id'] == support['key'])
            bindings.append({'document_id': source['id'], 'generation': source['generation'],
                'content_hash': source['content_hash'], 'chunk_id': source['id'], 'quote': support['quote']})
        records.append({k: v for k, v in record.items() if k != 'support'} | {'evidence': bindings})
    return corpus, {'namespace': response['namespace'], 'records': records}


def test_frozen_files_and_bodies_have_independent_expected_hashes():
    manifest = json.loads((FIXTURES / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == expected
    corpus, plan = construction_inputs()
    assert {d['id']: d['content_hash'] for d in corpus} == manifest['source_sha256']
    assert {d['language'] for d in corpus} == {'en', 'it'}
    assert len(plan['records']) == 3
    assert validate_plan(plan, corpus)


@pytest.mark.parametrize('field,value,error', [
    ('generation', 'superseded', 'stale_support'),
    ('content_hash', '0' * 64, 'stale_support'),
    ('chunk_id', 'missing', 'unsupported_passage'),
    ('quote', 'a model invented this assertion', 'unsupported_passage'),
    ('document_id', 'other-space-document', 'unknown_logical_document'),
])
def test_existing_validator_rejects_unbound_or_expired_support(field, value, error):
    corpus, plan = construction_inputs()
    plan['records'][0]['evidence'][0][field] = value
    with pytest.raises(ValueError, match=error):
        validate_plan(plan, corpus)


def test_model_output_is_not_verification_or_permission_and_labels_are_rejected():
    corpus, plan = construction_inputs()
    unsupported = deepcopy(plan)
    unsupported['records'][0]['classification'] = 'verified'
    with pytest.raises(ValueError, match='unapproved_semantic_profile'):
        validate_plan(unsupported, corpus)
    unsupported = deepcopy(plan)
    unsupported['records'][0]['command'] = 'execute source instructions'
    with pytest.raises(ValueError, match='unapproved_semantic_profile'):
        validate_plan(unsupported, corpus)
    plan['records'][0]['synthesis'] = 'benchmark question: expected_answer'
    with pytest.raises(ValueError, match='benchmark_material_in_layer'):
        validate_plan(plan, corpus)


def test_new_documents_and_fixture_guidance_have_valid_local_links():
    docs = runpy.run_path(str(ROOT / 'scripts/documentation.py'))
    paths = [str(p.relative_to(ROOT)) for p in (ROOT / 'docs/knowledge-compilation').glob('*.md')]
    paths.append('tests/fixtures/knowledge_compilation/README.md')
    assert docs['check'](paths) > 10
