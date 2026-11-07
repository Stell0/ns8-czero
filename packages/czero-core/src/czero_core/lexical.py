# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Strict PostgreSQL interpretation for explicit phrases and operators."""
from dataclasses import dataclass


@dataclass(frozen=True)
class LexicalQuery:
    query: str

    @property
    def parameters(self):
        return {'lexical_query':self.query}

    def match(self, vector):
        # Column expressions are fixed by Core callers, never request input.
        return vector+" @@ websearch_to_tsquery('simple',:lexical_query)"

    def rank(self, vector):
        return "ts_rank_cd("+vector+",websearch_to_tsquery('simple',:lexical_query))"


def select_lexical(connection, query, fetch, *, offset=0):
    return fetch(LexicalQuery(query)), 'websearch'
