# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in deterministic structured retrieval beside filtered evidence retrieval."""
from sqlalchemy import text

from .filtered_retrieval import FilteredEvidenceSearch
from .retrieval import SearchService, excerpt, reciprocal_rank_fusion
from .retrieval_filters import StructuredFilters
from .sources import _label
from .spaces import SpaceBound
from .receipts import snapshot


class StructuredSearchService(SpaceBound):
    _space_children = ('evidence',)

    def __init__(self, database, access, **options):
        self.database, self.access = database, access
        self.evidence = SearchService(database, access, **options)
        self.limits = self.evidence.limits

    def _structured(self, connection, query, filters, space):
        selections = []
        specifications = (
            ('object', 'c0_objects o', 'o', "o.type_name || ' ' || o.data::text", 'o.type_name', 'FALSE'),
            ('entity', 'c0_entities e', 'e', "e.kind || ' ' || e.label || ' ' || e.metadata::text", 'e.label', 'e.deleted'),
            ('claim', 'c0_claims c', 'c', "c.predicate || ' ' || c.value::text || ' ' || c.metadata::text", 'c.predicate', 'c.deleted'))
        for kind, table, alias, body, title, archived in specifications:
            if kind not in filters.categories:
                continue
            vector = "to_tsvector('simple'::regconfig," + body + ')'
            match = vector + " @@ websearch_to_tsquery('simple',:query)"
            rank = "ts_rank_cd(" + vector + ",websearch_to_tsquery('simple',:query))"
            if kind == 'entity':
                aliases = '''SELECT 1 FROM c0_entity_aliases al WHERE al.space_id=:space AND al.entity_id=e.id
                    AND to_tsvector('simple'::regconfig,al.label) @@ websearch_to_tsquery('simple',:query)'''
                match = '(' + match + ' OR EXISTS(' + aliases + '))'
                alias_rank = '''SELECT max(ts_rank_cd(to_tsvector('simple'::regconfig,al.label),websearch_to_tsquery('simple',:query)))
                    FROM c0_entity_aliases al WHERE al.space_id=:space AND al.entity_id=e.id'''
                rank = 'greatest(' + rank + ',coalesce((' + alias_rank + '),0))'
            selections.append('SELECT ' + alias + ".id,'" + kind + "' AS kind," + alias + '.revision,' +
                title + ' AS title,' + body + ' AS body,' + rank + ' AS rank,' + filters._columns() +
                ' FROM ' + table + filters._joins(kind, alias + '.id', alias + '.revision') +
                ' WHERE ' + alias + '.space_id=:space AND ' + filters._predicate(alias + '.created_at', archived) +
                ' AND ' + match)
        if not selections:
            return []
        sql = 'SELECT * FROM (' + ' UNION ALL '.join(selections) + ') candidates ORDER BY rank DESC,kind,id LIMIT :limit'
        rows = connection.execute(text(sql), {**filters._parameters(), 'query': query,
            'space': space, 'limit': self.limits.candidates}).mappings().all()
        hits = []
        for row in rows:
            hit = {'id': row['id'], 'kind': row['kind'], 'category': row['kind'], 'title': row['title'],
                'excerpt': excerpt(row['body'], query)['excerpt'], 'start_offset': None, 'end_offset': None,
                'score': float(row['rank']), 'citation': None, 'wiki': None, 'retrieval_method': 'text',
                'reference': {'kind': row['kind'], 'id': row['id'], 'revision': row['revision'],
                    'space_id': space, 'resource_id': row['id']}, 'evidence_refs': [], **filters._summaries(row)}
            if row['kind'] == 'claim':
                hit['evidence_refs'] = [dict(value) for value in connection.execute(text('''
                    SELECT c.id AS chunk_id,d.version_id,c.content_hash FROM c0_evidence_links l
                    JOIN c0_chunks c ON c.id=l.chunk_id AND c.space_id=l.space_id
                    JOIN c0_documents d ON d.id=c.document_id AND d.space_id=c.space_id
                    WHERE l.space_id=:space AND l.claim_id=:id ORDER BY c.id LIMIT 32'''),
                    {'space': space, 'id': row['id']}).mappings()]
            hits.append(hit)
        return hits

    def search(self, actor, query, *, filters=None, limit=None, mode='auto', rerank=None):
        query = _label(query, 512)
        filters = StructuredFilters() if filters is None else filters
        limit = min(20, self.limits.max_limit) if limit is None else limit
        selected = self.evidence.scorer_mode if rerank is None else rerank
        if (not isinstance(filters, StructuredFilters) or type(limit) is not int or not 1 <= limit <= self.limits.max_limit
                or mode not in ('auto', 'text', 'semantic', 'hybrid') or selected not in ('off', 'rerank', 'filter')
                or (selected != 'off' and self.evidence.scorer_mode == 'off')
                or (selected == 'filter' and self.evidence.scorer_mode != 'filter')):
            raise ValueError('invalid_structured_search')
        with self.database.engine.connect() as connection:
            space = self._space_authorize(connection, actor).space_id
        evidence_categories = set(filters.categories) & {'source', 'wiki'}
        result = {'hits': [], 'retrieval_method': 'text', 'fallback_reason': None, 'fallback_reasons': [],
            'requested_mode': mode, 'candidate_count': 0, 'scored_count': 0,
            'scorer_truncated_candidates': 0, 'provider_usage': {}, 'lexical_strategy':None}
        if evidence_categories:
            evidence = FilteredEvidenceSearch(self.database, self.access, filters=filters,
                embedding_client=self.evidence.embeddings.client, scorer=self.evidence.scorer,
                scorer_mode=self.evidence.scorer_mode, limits=self.limits).in_space(space)
            evidence.configuration_issue = self.evidence.configuration_issue
            kind = 'all' if len(evidence_categories) == 2 else next(iter(evidence_categories))
            found = evidence.search(actor, query, kind=kind, mode=mode, rerank=rerank, limit=self.limits.max_limit)
            result.update({key: found[key] for key in result if key in found})
            result['hits'] = [{**hit, 'retrieval_method': found['retrieval_method']} for hit in found['hits']]
        with self.database.engine.connect() as connection:
            self._space_authorize(connection, actor)
            structured = self._structured(connection, query, filters, space)
        evidence_hits = result['hits']
        result['hits'] = reciprocal_rank_fusion(evidence_hits, structured) if evidence_hits and structured else evidence_hits + structured
        result['candidate_count'] += len(structured)
        if structured and evidence_hits and result['retrieval_method'] != 'text':
            result['retrieval_method'] += '+structured_text'
        with self.database.engine.connect() as connection:
            self._space_authorize(connection, actor)
        result['hits'] = result['hits'][:limit]
        return snapshot(result)
