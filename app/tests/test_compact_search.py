# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from uuid import uuid4

import pytest

from czero_app.retrieval import CompactSearchResult, SearchResult


@pytest.mark.parametrize('start,end,excerpt,elided', [
    (35, 38, 'è字😀', True),
    (31, 34, 'è字😀', True),
    (35, 38, 'different', False),
    (29, 31, '', False),
    (38, 40, '', False),
])
def test_compact_primary_and_support_preserve_exact_unicode_slices(start, end, excerpt, elided):
    # Equal occurrences at different coordinates must retain the exact original range.
    body = 'Aè字😀-è字😀'
    citation = dict(chunk_id=uuid4(), document_id=uuid4(), version_id=uuid4(), source_id=uuid4(),
        version=2, filename='source.txt', media_type='text/plain', title='Source', deleted=False,
        start_offset=30, end_offset=38, body=body, content_hash='chunk', source_hash='source',
        text_hash='text', locations=[])
    passage = dict(id=citation['chunk_id'], kind='chunk', resource_id=citation['source_id'],
        revision=2, title='Source', content_hash='chunk', excerpt=excerpt, start_offset=start,
        end_offset=end, citation=citation, wiki=None)
    support_id = uuid4()
    distinct = {**passage, 'id': support_id, 'citation': {**citation, 'chunk_id': support_id}}
    raw = dict(hits=[{**passage, 'score': 1, 'supporting_passages': [distinct]}],
        retrieval_method='hybrid', fallback_reason=None, requested_mode='hybrid', candidate_count=1,
        fallback_reasons=[], scored_count=0, scorer_truncated_candidates=0, provider_usage={}, graphs=[])
    expected = SearchResult.model_validate(raw).model_dump(mode='json')
    compact = CompactSearchResult.from_search(raw).model_dump(mode='json')
    hit, = compact['hits']
    for actual in (hit, *hit['supporting_passages']):
        assert ('excerpt' not in actual) == elided
        if elided:
            cited = actual['citation']
            origin = cited['start_offset']
            actual['excerpt'] = cited['body'][actual['start_offset'] - origin:actual['end_offset'] - origin]
    assert compact == expected
