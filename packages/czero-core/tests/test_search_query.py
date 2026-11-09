# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from czero_core.search_query import normalize_query


@pytest.mark.parametrize('query', ['  BCL-2\n\t"exact phrase" OR NS8 -NS7\r\n',
                                 '\u00a0BCL-2  "exact phrase" OR NS8 -NS7\u2028'])
def test_whitespace_is_normalized_without_rewriting_syntax(query):
    expected='BCL-2 "exact phrase" OR NS8 -NS7'
    assert normalize_query(query)==expected
    assert normalize_query(normalize_query(query))==expected


@pytest.mark.parametrize('query', ['', ' \t\n', 'a'*513, 'a'*8193, 'bad\0query',
                                 'bad\x7fquery','bad\u200bquery', '\ud800', None, 12])
def test_empty_oversized_or_control_queries_fail_without_truncation(query):
    with pytest.raises(ValueError,match='invalid_search_query'):
        normalize_query(query)


def test_raw_whitespace_can_exceed_normalized_bound():
    assert normalize_query(' '*1000+'x\n')=='x'
    assert normalize_query('x'*512)=='x'*512
