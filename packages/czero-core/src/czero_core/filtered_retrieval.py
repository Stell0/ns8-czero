# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in evidence predicates reuse the established provider and ANN pipeline."""
from sqlalchemy import text

from .embeddings import EmbeddingStore
from .retrieval import SearchService, hit_key


class FilteredEmbeddingStore(EmbeddingStore):
    def __init__(self, database, client, access, filters):
        super().__init__(database, client, access)
        self.filters = filters

    def _eligibility(self, connection, profile, kind):
        filters = self.filters
        source = '''SELECT 1 FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
            JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id '''
        source += filters._joins('source_version', 'v.id', 'v.number')
        source += ''' WHERE c.id=e.source_chunk_id AND c.space_id=:space AND s.space_id=:space
            AND v.state='ready' AND ''' + filters._predicate('v.created_at', 's.deleted')
        wiki = '''SELECT 1 FROM c0_wiki_chunks w JOIN c0_wiki_revisions r ON r.id=w.revision_id
            JOIN c0_wiki_pages p ON p.id=r.page_id '''
        wiki += filters._joins('wiki_revision', 'r.id', 'r.number')
        wiki += ''' WHERE w.id=e.wiki_chunk_id AND w.space_id=:space AND p.space_id=:space
            AND p.revision=r.number AND ''' + filters._predicate('r.created_at', 'p.deleted')
        eligibility = ''' FROM c0_embeddings e WHERE e.space_id=:space AND e.profile_id=:profile
            AND e.generation=:generation AND (
                (:sources AND e.source_chunk_id IS NOT NULL AND EXISTS(''' + source + '''))
                OR (:wiki AND e.wiki_chunk_id IS NOT NULL AND EXISTS(''' + wiki + ')))'
        return eligibility, {**filters._parameters(), 'space': self._space(connection),
            'profile': self.profile_id, 'generation': profile['generation'],
            'sources': kind != 'wiki' and 'source' in filters.categories,
            'wiki': kind != 'source' and 'wiki' in filters.categories}

    def _ready(self, connection, profile):
        eligibility, parameters = self._eligibility(connection, profile, 'all')
        return connection.execute(text('SELECT 1' + eligibility + ' LIMIT 1'), parameters).scalar_one_or_none() is not None


class FilteredEvidenceSearch(SearchService):
    def __init__(self, database, access, *, filters, **options):
        super().__init__(database, access, **options)
        self.filters = filters
        self.embeddings = FilteredEmbeddingStore(database, self.embeddings.client, access, filters)

    def _decorate(self, connection, hit, row):
        return {**hit, **self.filters._summaries(row), 'category': 'source' if hit['kind'] == 'chunk' else 'wiki',
                'reference': {'space_id': self._space(connection),
                    'kind': 'source_version' if hit['kind'] == 'chunk' else 'wiki_revision',
                    'id': row['target_id'], 'revision': row['target_revision'], 'resource_id': hit['resource_id']},
                'evidence_refs': []}

    def _source_candidate(self):
        filters = self.filters
        return '''SELECT c.id,'chunk' AS kind,v.id AS target_id,v.number AS target_revision,
            ts_rank_cd(c.search_vector,websearch_to_tsquery('simple',:query)) AS rank,
            ''' + filters._columns() + ''' FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
            JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id
            ''' + filters._joins('source_version', 'v.id', 'v.number') + '''
            WHERE c.space_id=:space AND s.space_id=:space AND v.state='ready' AND :chunks
            AND c.search_vector @@ websearch_to_tsquery('simple',:query)
            AND ''' + filters._predicate('v.created_at', 's.deleted')

    def _wiki_candidate(self):
        filters = self.filters
        return '''SELECT r.id,'wiki_revision' AS kind,r.id AS target_id,r.number AS target_revision,
            ts_rank_cd(r.search_vector,websearch_to_tsquery('simple',:query)) AS rank,
            ''' + filters._columns() + ''' FROM c0_wiki_revisions r JOIN c0_wiki_pages p ON p.id=r.page_id
            ''' + filters._joins('wiki_revision', 'r.id', 'r.number') + '''
            WHERE r.space_id=:space AND p.space_id=:space AND :wiki AND p.revision=r.number
            AND r.search_vector @@ websearch_to_tsquery('simple',:query)
            AND ''' + filters._predicate('r.created_at', 'p.deleted')

    def _text(self, connection, query, *, limit, kind):
        sql = 'SELECT * FROM (' + self._source_candidate() + ' UNION ALL ' + self._wiki_candidate()
        sql += ') matches ORDER BY rank DESC,kind,id LIMIT :limit'
        parameters = {**self.filters._parameters(), 'space': self._space(connection), 'query': query,
            'chunks': kind != 'wiki' and 'source' in self.filters.categories,
            'wiki': kind != 'source' and 'wiki' in self.filters.categories, 'limit': limit}
        rows = connection.execute(text(sql), parameters).mappings().all()
        return [self._decorate(connection,
            {**(self._source_hit(connection, row['id'], query) if row['kind'] == 'chunk'
                else self._wiki_hit(connection, row['id'], query)), 'score': float(row['rank'])}, row) for row in rows]

    def _semantic_row(self, connection, row):
        filters = self.filters
        if row['source_chunk_id'] is not None:
            sql = '''SELECT c.id,v.id AS target_id,v.number AS target_revision,'''
            sql += filters._columns() + ''' FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
                JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id '''
            sql += filters._joins('source_version', 'v.id', 'v.number')
            sql += ''' WHERE c.space_id=:space AND s.space_id=:space AND c.id=:id AND v.state='ready'
                AND ''' + filters._predicate('v.created_at', 's.deleted')
            identifier = row['source_chunk_id']
        else:
            sql = '''SELECT r.id,w.id AS wiki_chunk_id,r.id AS target_id,r.number AS target_revision,'''
            sql += filters._columns() + ''' FROM c0_wiki_chunks w JOIN c0_wiki_revisions r ON r.id=w.revision_id
                JOIN c0_wiki_pages p ON p.id=r.page_id '''
            sql += filters._joins('wiki_revision', 'r.id', 'r.number')
            sql += ''' WHERE w.space_id=:space AND p.space_id=:space AND w.id=:id AND p.revision=r.number
                AND ''' + filters._predicate('r.created_at', 'p.deleted')
            identifier = row['wiki_chunk_id']
        return connection.execute(text(sql), {**filters._parameters(), 'space': self._space(connection),
            'id': identifier}).mappings().one_or_none()

    def _semantic(self, connection, vector, query, kind):
        rows = self.embeddings.nearest(connection, vector, limit=self.limits.candidates, kind=kind)
        hits, seen = [], set()
        for row in rows:
            candidate = self._semantic_row(connection, row)
            if candidate is None:
                continue
            if row['source_chunk_id'] is not None:
                hit = self._source_hit(connection, candidate['id'], query)
            else:
                hit = self._wiki_hit(connection, candidate['id'], query, chunk_id=candidate['wiki_chunk_id'])
            key = hit_key(hit)
            if key in seen:
                continue
            seen.add(key)
            hits.append(self._decorate(connection, {**hit, 'score': 1. - float(row['distance'])}, candidate))
        return hits
