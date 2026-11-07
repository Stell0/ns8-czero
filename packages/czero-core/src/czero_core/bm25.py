# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Document BM25 over the authorized selection, with original evidence chunks."""
import re

from sqlalchemy import text

from .retrieval_filters import StructuredFilters

RANKER_VERSION = 'bm25-v1-en-it-k1-1.2-b-0.75'


def explicit_query(query):
    return bool(re.search(r'["&|!]|(?<!\w)-|\bor\b', query, re.I)
                or re.search(r'\b(?:AND|NOT)\b', query))


def query_groups(connection, query):
    rows = connection.execute(text('SELECT variants FROM c0_lexical_tokens_v1(:query)'), {'query': query})
    groups = []
    for (variants,) in rows:
        merged = set(variants)
        # One contribution for connected literal/stem aliases, independent of
        # query repetition or the order returned by PostgreSQL aggregation.
        remaining = groups
        while True:
            retained = []
            for group in remaining:
                if merged & group:
                    merged |= group
                else:
                    retained.append(group)
            if len(retained) == len(remaining):
                break
            remaining = retained
        groups = retained + [merged]
    return sorted([sorted(group) for group in groups])


def search_documents(connection, query, *, space, limit, kind='all', offset=0, filters=None):
    """Return None for explicit syntax; ordinary queries always use BM25."""
    if explicit_query(query):
        return None
    groups = query_groups(connection, query)
    if not groups:
        return []
    # JIT compilation costs more than executing these bounded indexed reads.
    # This is transaction-local; runtime deadlines and global settings are unchanged.
    connection.execute(text('SET LOCAL jit=off'))
    annotated = filters is not None
    filters = filters or StructuredFilters()
    columns = filters._columns() if annotated else (
        '0 AS applicability_revision,NULL::jsonb AS applicability_value,'
        '0 AS verification_revision,NULL::jsonb AS verification_value')
    source_joins = filters._joins('source_version','v.id','v.number') if annotated else ''
    wiki_joins = filters._joins('wiki_revision','r.id','r.number') if annotated else ''
    parameters = {**filters._parameters(), 'space': space, **{f'terms_{i}':group for i,group in enumerate(groups)},
                  'chunks': kind != 'wiki' and 'source' in filters.categories,
                  'wiki': kind != 'source' and 'wiki' in filters.categories,
                  'limit': limit, 'offset': offset}
    # PostgreSQL 16 otherwise treats source ownership and its current pointer as
    # independent joins, estimates one row, and repeatedly scans the whole corpus.
    # The nullable-pointer CASE preserves the exact predicate and realistic plans.
    eligible = '''SELECT d.id,'chunk' AS kind,v.id AS target_id,v.number AS target_revision,
        ''' + columns + ''' FROM c0_documents d
        JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id
        ''' + source_joins + '''
        WHERE s.space_id=:space AND d.space_id=:space AND CASE WHEN s.current_version_id IS NULL THEN false ELSE s.current_version_id=v.id END
        AND v.state='ready' AND :chunks AND ''' + filters._predicate('v.created_at', 's.deleted') + '''
        UNION ALL
        SELECT r.id,'wiki_revision' AS kind,r.id AS target_id,r.number AS target_revision,
        ''' + columns + ''' FROM c0_wiki_revisions r JOIN c0_wiki_pages p ON p.id=r.page_id
        ''' + wiki_joins + '''
        WHERE p.space_id=:space AND r.space_id=:space AND p.revision=r.number AND :wiki
        AND ''' + filters._predicate('r.created_at', 'p.deleted')
    values = ','.join(f'({i},CAST(:terms_{i} AS text[]))' for i in range(len(groups)))
    sql = '''WITH eligible AS MATERIALIZED (''' + eligible + '''),
      corpus AS MATERIALIZED (
        SELECT e.*,d.length FROM eligible e JOIN c0_lexical_documents d ON d.id=e.id
      ), stats AS (
        SELECT count(*)::double precision AS n,avg(length) AS avgdl FROM corpus
      ), query(qid,variants) AS MATERIALIZED (VALUES ''' + values + '''),
      -- Keep GIN discovery independent of correlated current-pointer row estimates.
      -- Eligibility still precedes document frequencies, scores and every limit.
      matched_terms AS MATERIALIZED (
        SELECT t.document_id,q.qid,t.frequency,t.originals
        FROM query q JOIN c0_lexical_terms t ON t.variants && q.variants
      ), matches AS MATERIALIZED (
        SELECT t.document_id,t.qid,sum(t.frequency) AS tf
        FROM matched_terms t JOIN corpus c ON c.id=t.document_id
        GROUP BY t.document_id,t.qid
      ), weights AS MATERIALIZED (
        SELECT qid,ln(1+(s.n-count(*)+0.5)/(count(*)+0.5)) AS idf
        FROM matches CROSS JOIN stats s GROUP BY qid,s.n
      ), ranked AS MATERIALIZED (
        SELECT m.document_id,sum(w.idf*(m.tf*2.2)/
          (m.tf+1.2*(0.25+0.75*c.length/nullif(s.avgdl,0)))) AS rank
        FROM matches m JOIN weights w USING(qid) JOIN corpus c ON c.id=m.document_id
        CROSS JOIN stats s GROUP BY m.document_id
        ORDER BY rank DESC,m.document_id LIMIT :limit OFFSET :offset
      ), chunk_queries AS MATERIALIZED (
        SELECT t.document_id,t.qid,w.idf,
          to_tsquery('simple',string_agg(DISTINCT plainto_tsquery('simple',v)::text,' | ')) AS expression
        FROM ranked r JOIN corpus c ON c.id=r.document_id
        JOIN matched_terms t ON t.document_id=r.document_id JOIN weights w USING(qid)
        CROSS JOIN LATERAL unnest(t.originals) v WHERE c.kind='chunk'
        GROUP BY t.document_id,t.qid,w.idf
      )
      SELECT CASE WHEN c.kind='chunk' THEN evidence.id ELSE c.id END AS id,
        c.kind,c.target_id,c.target_revision,c.applicability_revision,c.applicability_value,
        c.verification_revision,c.verification_value,r.rank
      FROM ranked r JOIN corpus c ON c.id=r.document_id
      LEFT JOIN LATERAL (
        SELECT ch.id FROM c0_chunks ch
        LEFT JOIN LATERAL (
          SELECT sum(q.idf*ts_rank_cd(ch.search_vector,q.expression)) AS contribution
          FROM chunk_queries q WHERE q.document_id=ch.document_id
        ) contribution ON true
        WHERE c.kind='chunk' AND ch.document_id=c.id
        ORDER BY contribution.contribution DESC NULLS LAST,ch.id LIMIT 1
      ) evidence ON true ORDER BY r.rank DESC,c.id'''
    return connection.execute(text(sql), parameters).mappings().all()
