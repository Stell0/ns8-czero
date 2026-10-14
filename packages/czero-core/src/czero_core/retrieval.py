# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded knowledge retrieval; immutable evidence stays in domain services."""
import re
from sqlalchemy import text
from .identity import PermissionDenied, Role
from .sources import SourceService, _label
from .wiki import _view


def excerpt(body, query, *, origin=0):
    # The window is an exact substring, unlike a formatted ts_headline.
    words = re.findall(r'\w+', query, flags=re.UNICODE)[:32]
    matches = [match.start() for word in words if (match := re.search(re.escape(word), body, flags=re.IGNORECASE))]
    start = max(0, min(matches, default=0) - 160)
    end = min(len(body), start + 1200)
    return {'excerpt': body[start:end], 'start_offset': origin + start, 'end_offset': origin + end}


class SearchService:
    def __init__(self, database, access):
        self.database, self.access = database, access

    def _authorize(self, connection, actor):
        if self.access is None: raise PermissionDenied()
        current = self.access._actor(connection, actor.user_id)
        current.require(Role.READER)
        return current

    def search(self, actor, query, *, limit=20, mode='auto', kind='all'):
        query = _label(query, 512)
        if type(limit) is not int or not 1 <= limit <= 50 or mode not in ('auto','text','semantic','hybrid') or kind not in ('all','source','wiki'):
            raise ValueError('invalid_retrieval_options')
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            rows = connection.execute(text('''SELECT * FROM (
                SELECT c.id,'chunk' AS kind,ts_rank_cd(c.search_vector,websearch_to_tsquery('simple',:query)) AS rank
                FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
                JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id
                WHERE :chunks AND NOT s.deleted AND c.search_vector @@ websearch_to_tsquery('simple',:query)
                UNION ALL
                SELECT r.id,'wiki_revision' AS kind,ts_rank_cd(r.search_vector,websearch_to_tsquery('simple',:query)) AS rank
                FROM c0_wiki_revisions r JOIN c0_wiki_pages p ON p.id=r.page_id
                WHERE :wiki AND NOT p.deleted AND p.revision=r.number
                    AND r.search_vector @@ websearch_to_tsquery('simple',:query)
                ) matches ORDER BY rank DESC,kind,id LIMIT :limit'''),
                {'query':query,'chunks':kind!='wiki','wiki':kind!='source','limit':limit}).mappings().all()
            hits = []
            for row in rows:
                if row['kind'] == 'chunk':
                    citation = SourceService._citation(connection, row['id'])
                    hit = {'id':row['id'],'kind':'chunk','resource_id':citation['source_id'],
                        'revision':citation['version'],'title':citation['title'],'content_hash':citation['content_hash'],
                        **excerpt(citation['body'],query,origin=citation['start_offset']), 'citation':citation,'wiki':None}
                else:
                    revision = connection.execute(text('''SELECT r.*,p.slug FROM c0_wiki_revisions r
                        JOIN c0_wiki_pages p ON p.id=r.page_id WHERE r.id=:id'''), {'id':row['id']}).mappings().one()
                    hit = {'id':row['id'],'kind':'wiki_revision','resource_id':revision['page_id'],
                        'revision':revision['number'],'title':revision['title'],'content_hash':revision['content_hash'],
                        **excerpt(revision['body'],query),'citation':None,'wiki':{'page_id':revision['page_id'],
                            'revision_id':revision['id'],'revision':revision['number'],'slug':revision['slug'],
                            'content_hash':revision['content_hash']}}
                hits.append({**hit,'score':float(row['rank'])})
            # Provider-free FTS never depends on a derivative indexing job.
            return _view({'hits':hits,'retrieval_method':'text','fallback_reason':
                'embeddings_not_configured' if mode in ('semantic','hybrid') else None,
                'requested_mode':mode,'candidate_count':len(hits)})
