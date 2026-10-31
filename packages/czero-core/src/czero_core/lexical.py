# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded lexical recovery after an eligible selection has no strict matches."""
from dataclasses import dataclass
import re

from sqlalchemy import text


# The same declared product/version context is frozen by document snapshots.
# Keep the chunk predicate separate and GIN-indexable.
SOURCE_CONTEXT = "(c.search_vector || to_tsvector('simple',coalesce(s.metadata#>>'{provenance,product}','') || ' ' || coalesce(s.metadata#>>'{provenance,product_version}','')))"


@dataclass(frozen=True)
class LexicalQuery:
    query: str
    terms: tuple[str, ...] = ()
    required: str = ''

    @property
    def strategy(self):
        return 'relaxed' if self.terms else 'websearch'

    @property
    def parameters(self):
        return {'lexical_query':self.query,'lexical_terms':list(self.terms),
                'lexical_minimum':max(2,(len(self.terms)+1)//2),'lexical_required':self.required}

    @staticmethod
    def coverage(vector):
        # Column expressions are fixed by Core callers, never request input.
        return "(SELECT count(*) FROM unnest(tsvector_to_array(" + vector + ")) term WHERE term=ANY(CAST(:lexical_terms AS text[])))"

    def match(self, vector, *, context=None):
        predicate=vector+" @@ websearch_to_tsquery('simple',:lexical_query)"
        if self.terms:
            vector=context or vector
            predicate+=' AND '+self.coverage(vector)+' >= :lexical_minimum'
            if self.required:
                predicate+=' AND '+vector+" @@ plainto_tsquery('simple',:lexical_required)"
        return predicate

    def rank(self, vector, *, context=None):
        if self.terms:vector=context or vector
        base="ts_rank_cd("+vector+",websearch_to_tsquery('simple',:lexical_query)"
        return self.coverage(vector)+' + '+base+',32)' if self.terms else base+')'


def relaxed_query(connection, query):
    # Explicit web-search syntax keeps its original PostgreSQL interpretation.
    if (re.search(r'["&|!]|(?<!\w)-|\bor\b',query,re.I)
            or re.search(r'\b(?:AND|NOT)\b',query)):
        return None
    rows=connection.execute(text("""SELECT word,
        coalesce(cardinality(ts_lexize('english_stem',word)),1)>0
        AND coalesce(cardinality(ts_lexize('italian_stem',word)),1)>0 AS content
        FROM unnest(tsvector_to_array(to_tsvector('simple',:query))) word"""),{'query':query}).all()
    terms=tuple(word for word,content in rows if content)
    if len(rows)<4 or not 2<=len(terms)<=32 or any('"' in word for word in terms):
        return None
    # Versions and punctuated technical names must survive any relaxation.
    required=' '.join(word for word in query.split()
        if any(c.isdigit() for c in word) or re.search(r'\w[-._/@()]\w',word)
        or len(word)>1 and word.isupper())
    return LexicalQuery(' OR '.join('"'+word+'"' for word in terms),terms,required)


def select_lexical(connection, query, fetch, *, offset=0):
    strict=LexicalQuery(query)
    rows=fetch(strict)
    # Later source pages must use the same strategy as their first page.
    if rows or offset and fetch(strict, first=True):
        return rows,strict.strategy
    relaxed=relaxed_query(connection,query)
    return (fetch(relaxed),relaxed.strategy) if relaxed else (rows,strict.strategy)
