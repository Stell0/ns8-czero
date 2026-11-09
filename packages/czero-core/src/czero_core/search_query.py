# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Search-only whitespace normalization; never rewrite identifiers or operators."""
import unicodedata

MAX_RAW_QUERY = 8192
MAX_QUERY = 512


def normalize_query(value):
    if (not isinstance(value, str) or len(value) > MAX_RAW_QUERY
            or any(unicodedata.category(c) in ('Cc', 'Cf', 'Cs') and c not in '\r\n\t' for c in value)):
        raise ValueError('invalid_search_query')
    query = ' '.join(value.split())
    if not query or len(query) > MAX_QUERY:
        raise ValueError('invalid_search_query')
    return query
