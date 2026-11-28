# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import web_kb_dataset as dataset


def test_public_provenance_precedes_any_network_access(monkeypatch):
    monkeypatch.setattr(dataset, 'public_selection', lambda: ('space', {'collection': ('owner/repo', {'documentation'})}))
    invalid = {'definition_id': 'collection', 'space_id': 'space',
               'source_type': 'documentation', 'url': 'https://example.org/private/faq'}
    with pytest.raises(ValueError, match='provenance'):
        dataset.public_source(invalid)


def test_freeze_and_detect_changed_evidence(tmp_path):
    sources = [{'source_type': kind, 'url': 'https://example.org/' + kind, 'id': kind,
                'revision': 'rev', 'body': 'original', 'public_body': 'original',
                'title': kind, 'sha256': 'hash', 'public_checked_at': 'time'}
               for kind in ('documentation', 'issue')]
    questions = []
    for index in range(100):
        source = sources[index // 50]
        questions.append({'id': str(index), 'question': f'Question {index}',
                          'language': ('en', 'it')[index % 2], 'source_type': source['source_type'],
                          'disposition': 'clarify' if index < 10 else 'answer',
                          'required_facts': ['fact'], 'expected_answer': 'answer',
                          'product': 'example', 'version': 'unknown',
                          'evidence': [{'url': source['url'], 'quote': 'original'}]})
    proposal = {'generator': 'author', 'questions': questions}
    audit = {'reviewer': 'independent reviewer', 'approved_ids': [q['id'] for q in questions],
             'proposal_sha256': dataset.digest(proposal), 'sources_sha256': dataset.digest(sources)}
    pack = dataset.freeze(proposal, sources, audit)
    dataset.save(tmp_path / 'pack.json', pack)
    assert dataset.load_pack(tmp_path / 'pack.json') == questions

    sources[0]['public_body'] = 'changed'
    with pytest.raises(ValueError, match='source-bound'):
        dataset.freeze(proposal, sources, audit)
    audit['sources_sha256'] = dataset.digest(sources)
    with pytest.raises(ValueError, match='passage missing'):
        dataset.freeze(proposal, sources, audit)

    pack['questions'][0]['question'] += 'modified'
    dataset.save(tmp_path / 'tampered.json', pack)
    with pytest.raises(ValueError, match='modified'):
        dataset.load_pack(tmp_path / 'tampered.json')
