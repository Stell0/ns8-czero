# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded retrieval; evidence and roles remain in shared domain services."""
from dataclasses import dataclass
import re
from uuid import UUID
from sqlalchemy import Uuid,bindparam,text
from sqlalchemy.exc import SQLAlchemyError
from .identity import PermissionDenied,Role
from .spaces import require_scope
from .sources import SourceService,_label
from .wiki import _view,KnowledgeNotFound
from .embeddings import EmbeddingStore
from .knowledge import KnowledgeService
from .providers import ProviderUnavailable


def excerpt(body,query,*,origin=0):
    # Exact substrings preserve offsets; formatted highlights do not.
    words=re.findall(r'\w+',query,flags=re.UNICODE)[:32]
    matches=[match.start() for word in words if (match:=re.search(re.escape(word),body,flags=re.IGNORECASE))]
    start=max(0,min(matches,default=0)-160);end=min(len(body),start+1200)
    return {'excerpt':body[start:end],'start_offset':origin+start,'end_offset':origin+end}


@dataclass(frozen=True)
class SearchLimits:
    max_limit: int = 50
    candidates: int = 64
    graph_depth: int = 3
    scorer_candidates: int = 16

    def __post_init__(self):
        if (type(self.max_limit) is not int or not 1<=self.max_limit<=50
                or type(self.candidates) is not int or not self.max_limit<=self.candidates<=64
                or type(self.graph_depth) is not int or not 0<=self.graph_depth<=3
                or type(self.scorer_candidates) is not int or not 1<=self.scorer_candidates<=16):
            raise ValueError('invalid_retrieval_limits')


def hit_key(hit):
    return hit['kind']+':'+str(hit['id'])


def reciprocal_rank_fusion(*rankings):
    hits={};scores={}
    for ranking in rankings:
        seen=set();rank=0
        for hit in ranking:
            key=hit_key(hit)
            if key in seen:continue
            seen.add(key);rank+=1;hits.setdefault(key,hit);scores[key]=scores.get(key,0.)+1./(60+rank)
    return [{**hits[key],'score':scores[key]} for key in sorted(hits,key=lambda k:(-scores[k],k))]


class SearchService:
    def __init__(self,database,access,*,embedding_client=None,scorer=None,scorer_mode='off',limits=None):
        if scorer_mode not in ('off','rerank','filter'):raise ValueError('invalid_scorer_mode')
        self.database,self.access=database,access
        self.embeddings=EmbeddingStore(database,embedding_client,access)
        self.scorer,self.scorer_mode=scorer,scorer_mode
        self.limits=limits or SearchLimits()
        self.knowledge=KnowledgeService(database,access)
        self.configuration_issue=None

    def _authorize(self,connection,actor):
        if self.access is None:raise PermissionDenied()
        current=self.access.checked_actor(connection,actor);current.require(Role.READER)
        require_scope(current,Role.READER)
        return current

    @staticmethod
    def _source_hit(connection,key,query):
        citation=SourceService._citation(connection,key)
        return {'id':citation['chunk_id'],'kind':'chunk','resource_id':citation['source_id'],
            'revision':citation['version'],'title':citation['title'],'content_hash':citation['content_hash'],
            **excerpt(citation['body'],query,origin=citation['start_offset']),'citation':citation,'wiki':None}

    @staticmethod
    def _wiki_hit(connection,key,query,*,chunk_id=None):
        data=connection.execute(text('''SELECT r.*,p.slug FROM c0_wiki_revisions r
            JOIN c0_wiki_pages p ON p.id=r.page_id WHERE r.id=:id'''),{'id':key}).mappings().one()
        window=excerpt(data['body'],query)
        if chunk_id is not None:
            piece=connection.execute(text('SELECT body,start_offset FROM c0_wiki_chunks WHERE id=:id'),{'id':chunk_id}).mappings().one()
            window=excerpt(piece['body'],query,origin=piece['start_offset'])
        return {'id':data['id'],'kind':'wiki_revision','resource_id':data['page_id'],
            'revision':data['number'],'title':data['title'],'content_hash':data['content_hash'],
            **window,'citation':None,'wiki':{'page_id':data['page_id'],'revision_id':data['id'],
                'revision':data['number'],'slug':data['slug'],'content_hash':data['content_hash']}}

    def _text(self,connection,query,*,limit,kind):
        rows=connection.execute(text('''SELECT * FROM (
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
        return [{**(self._source_hit(connection,row['id'],query) if row['kind']=='chunk'
                    else self._wiki_hit(connection,row['id'],query)),'score':float(row['rank'])} for row in rows]

    def _semantic(self,connection,vector,query,kind):
        rows=self.embeddings.nearest(connection,vector,limit=self.limits.candidates,kind=kind)
        result=[];seen=set()
        for row in rows:
            if row['source_chunk_id'] is not None:
                hit=self._source_hit(connection,row['source_chunk_id'],query)
            else:
                revision=connection.execute(text('SELECT revision_id FROM c0_wiki_chunks WHERE id=:id'),
                    {'id':row['wiki_chunk_id']}).scalar_one()
                hit=self._wiki_hit(connection,revision,query,chunk_id=row['wiki_chunk_id'])
            key=hit_key(hit)
            if key in seen:continue
            seen.add(key);result.append({**hit,'score':1.-float(row['distance'])})
        return result

    def _graphs(self,actor,query,hits,depth):
        targets=set();chunks=[]
        for hit in hits[:self.limits.candidates]:
            targets.add(str(hit['resource_id']));targets.add(str(hit['id']))
            if hit['citation']:
                targets.add(str(hit['citation']['document_id']));chunks.append(str(hit['id']))
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor)
            roots=connection.execute(text('''SELECT id FROM c0_entities e WHERE NOT deleted AND (
                to_tsvector('simple',label) @@ websearch_to_tsquery('simple',:query)
                OR EXISTS(SELECT 1 FROM c0_entity_links l WHERE l.entity_id=e.id AND l.target_id IN :targets)
                OR EXISTS(SELECT 1 FROM c0_claims c JOIN c0_evidence_links l ON l.claim_id=c.id
                    WHERE c.entity_id=e.id AND NOT c.deleted AND l.chunk_id IN :chunks))
                ORDER BY id LIMIT 3''').bindparams(bindparam('targets',expanding=True,type_=Uuid()),bindparam('chunks',expanding=True,type_=Uuid())),
                {'query':query,'targets':[UUID(k) for k in targets],'chunks':[UUID(k) for k in chunks]}).scalars().all()
        return [self.knowledge.graph(actor,key,depth=depth,limit=16) for key in roots]

    def search(self,actor,query,*,limit=None,mode='auto',kind='all',graph_depth=0,rerank=None):
        query=_label(query,512);limit=min(20,self.limits.max_limit) if limit is None else limit
        selected=self.scorer_mode if rerank is None else rerank
        if (type(limit) is not int or not 1<=limit<=self.limits.max_limit
                or mode not in ('auto','text','semantic','hybrid') or kind not in ('all','source','wiki')
                or type(graph_depth) is not int or not 0<=graph_depth<=self.limits.graph_depth
                or selected not in ('off','rerank','filter')
                or (selected!='off' and self.scorer_mode=='off')
                or (selected=='filter' and self.scorer_mode!='filter')):
            raise ValueError('invalid_retrieval_options')
        failures=[self.configuration_issue] if self.configuration_issue else []
        usage={};scored_count=0;truncated=0;method='text';graphs=[]
        desired=('hybrid' if self.embeddings.client else 'text') if mode=='auto' else mode
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor)
            ordinary=self._text(connection,query,limit=self.limits.candidates,kind=kind)
            profile=self.embeddings._profile(connection) if self.embeddings.client else None
            ready=profile is not None and connection.execute(text('SELECT 1 FROM c0_embeddings WHERE profile_id=:id AND generation=:generation LIMIT 1'),
                {'id':self.embeddings.profile_id,'generation':profile['generation']}).scalar_one_or_none() is not None
        hits=ordinary
        if desired in ('semantic','hybrid'):
            if self.embeddings.client is None:failures.append('embeddings_not_configured')
            elif not ready:failures.append('embedding_index_not_ready')
            else:
                try:
                    # Release DB connections before optional outbound I/O.
                    embedded=self.embeddings.client.embed([query]);usage['embedding']=embedded['usage']
                    with self.database.engine.connect() as connection:
                        self._authorize(connection,actor)
                        semantic=self._semantic(connection,embedded['vectors'][0],query,kind)
                    if semantic:
                        hits=semantic if desired=='semantic' else reciprocal_rank_fusion(ordinary,semantic)
                        method=desired
                    else:failures.append('embedding_no_candidates')
                except ProviderUnavailable as error:failures.append('embedding_'+error.reason)
                except SQLAlchemyError:failures.append('embedding_storage_unavailable')
        candidate_count=len(hits)
        if selected!='off' and hits:
            if self.scorer is None:failures.append('systemone_not_configured')
            else:
                candidates=hits[:self.limits.scorer_candidates]
                try:
                    scored=self.scorer.score(query,[{'id':hit_key(hit),'text':hit['title']+'\n'+hit['excerpt']} for hit in candidates])
                    usage['systemone']=scored['usage'];truncated=scored['truncated_candidates'];scored_count=len(candidates)
                    ranked=[{**hit,'relevance_score':scored['scores'][hit_key(hit)]} for hit in candidates]
                    ranked.sort(key=lambda h:(-h['relevance_score'],hit_key(h)))
                    hits=([h for h in ranked if h['relevance_score']>=self.scorer.settings.threshold]
                          if selected=='filter' else ranked+hits[len(candidates):])
                    method+='+'+selected
                except ProviderUnavailable as error:failures.append('systemone_'+error.reason)
        if graph_depth:
            try:
                graphs=self._graphs(actor,query,hits,graph_depth)
                if graphs:method+='+graph'
            except PermissionDenied:raise
            except (KnowledgeNotFound,SQLAlchemyError):failures.append('graph_unavailable')
        # Revocation during provider calls cannot return an admitted result.
        with self.database.engine.connect() as connection:self._authorize(connection,actor)
        return _view({'hits':hits[:limit],'retrieval_method':method,'fallback_reason':failures[0] if failures else None,
            'fallback_reasons':failures,'requested_mode':mode,'candidate_count':candidate_count,'scored_count':scored_count,
            'scorer_truncated_candidates':truncated,'provider_usage':usage,'graphs':graphs})
