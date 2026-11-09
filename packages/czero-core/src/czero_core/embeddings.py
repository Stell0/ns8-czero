# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Derivative embeddings retain immutable raw evidence and Wiki revisions."""
import hashlib
import json
from uuid import UUID,uuid4,uuid5,NAMESPACE_URL
from sqlalchemy import text
from .identity import PermissionDenied,Role
from .spaces import SpaceBound
from .jobs import Handler,JobService,empty_payload
from .providers import normalized_vector
from .wiki import KnowledgeConflict,_view
from .embedding_context import contextual_input

PROFILE_LOCK=49377
SCHEDULE_ID=UUID('af8b04ce-b519-4d36-99d5-bcdedff740bd')


def profile_identity(settings):
    identity={'endpoint':settings.endpoint,'model':settings.model,'dimensions':settings.dimensions,
        'send_dimensions':settings.send_dimensions}
    if settings.input_format!='legacy':identity['input_format']=settings.input_format
    encoded=json.dumps(identity,sort_keys=True,separators=(',',':'))
    fingerprint=hashlib.sha256(encoded.encode()).hexdigest()
    return uuid5(NAMESPACE_URL,'czero-embedding/'+fingerprint),fingerprint


def vector_literal(value,dimensions):
    vector=normalized_vector(value,dimensions)+[0.]*(2000-dimensions)
    return '['+','.join(format(v,'.10g') for v in vector)+']'


class EmbeddingStore(SpaceBound):
    def __init__(self,database,client,access=None):
        self.database,self.client,self.access=database,client,access
        self.profile_id,self.fingerprint=profile_identity(client.settings) if client else (None,None)

    def _activate(self,connection):
        """Trusted runtime config transition; ordinary restart preserves pause."""
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':PROFILE_LOCK})
        active=connection.execute(text('SELECT id FROM c0_embedding_profiles WHERE active')).scalar_one_or_none()
        if active==self.profile_id:return
        if self.client:self._profile(connection,create=True)
        connection.execute(text('UPDATE c0_embedding_profiles SET active=false WHERE active'))
        if self.client:connection.execute(text('UPDATE c0_embedding_profiles SET active=true WHERE id=:id'),{'id':self.profile_id})
        connection.execute(text('UPDATE c0_scheduled_tasks SET enabled=:enabled WHERE id=:id'),
                           {'enabled':self.client is not None,'id':SCHEDULE_ID})

    def _profile(self,connection,*,create=False):
        row=connection.execute(text('SELECT * FROM c0_embedding_profiles WHERE id=:id'),{'id':self.profile_id}).mappings().one_or_none()
        if row is None and create:
            connection.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':PROFILE_LOCK})
            row=connection.execute(text('SELECT * FROM c0_embedding_profiles WHERE id=:id'),{'id':self.profile_id}).mappings().one_or_none()
            if row is None:
                if connection.execute(text('SELECT count(*) FROM c0_embedding_profiles')).scalar_one()>=64:
                    raise ValueError('embedding_profile_limit')
                row=connection.execute(text('''INSERT INTO c0_embedding_profiles(id,fingerprint,model,dimensions,input_format)
                    VALUES(:id,:fingerprint,:model,:dimensions,:input_format) RETURNING *'''),
                    {'id':self.profile_id,'fingerprint':self.fingerprint,'model':self.client.settings.model,
                     'dimensions':self.client.settings.dimensions,'input_format':self.client.settings.input_format}).mappings().one()
        return dict(row) if row else None

    @staticmethod
    def _wiki_chunks(connection):
        pages=connection.execute(text('''SELECT r.id,r.body,r.space_id FROM c0_wiki_revisions r JOIN c0_wiki_pages p ON p.id=r.page_id
            WHERE NOT p.deleted AND p.revision=r.number AND NOT EXISTS(SELECT 1 FROM c0_wiki_chunks w WHERE w.revision_id=r.id)
            ORDER BY r.id LIMIT 2''')).mappings().all()
        for row in pages:
            # Wiki accepts blank authored bodies; extraction's no-text guard
            # does not apply. Even a blank page has a title to embed.
            for ordinal,start in enumerate(range(0,max(1,len(row['body'])),3600)):
                end=min(len(row['body']),start+3800);body=row['body'][start:end]
                connection.execute(text('''INSERT INTO c0_wiki_chunks(space_id,id,revision_id,ordinal,start_offset,end_offset,body,content_hash)
                    VALUES(:space,:id,:revision,:ordinal,:start,:end,:body,:hash) ON CONFLICT(revision_id,ordinal) DO NOTHING'''),
                    {'space':row['space_id'],'id':uuid5(row['id'],'wiki-chunk/'+str(ordinal)),'revision':row['id'],'ordinal':ordinal,
                     'start':start,'end':end,'body':body,'hash':hashlib.sha256(body.encode()).hexdigest()})
                if end==len(row['body']):break

    def _index_batch(self,connection):
        if self.client is None:return {'status':'disabled','indexed':0}
        profile=self._profile(connection,create=True);self._wiki_chunks(connection)
        parameters={'profile':self.profile_id,'generation':profile['generation']}
        sources=connection.execute(text('''SELECT c.id,c.body,c.space_id FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
            JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id
            WHERE s.current_version_id=v.id AND v.state='ready' AND NOT s.deleted AND NOT EXISTS(SELECT 1 FROM c0_embeddings e WHERE e.profile_id=:profile
                AND e.generation=:generation AND e.source_chunk_id=c.id) ORDER BY c.id LIMIT 8'''),parameters).mappings().all()
        wiki=connection.execute(text('''SELECT w.id,w.body,w.space_id,r.title FROM c0_wiki_chunks w JOIN c0_wiki_revisions r ON r.id=w.revision_id
            JOIN c0_wiki_pages p ON p.id=r.page_id WHERE NOT p.deleted AND p.revision=r.number
            AND NOT EXISTS(SELECT 1 FROM c0_embeddings e WHERE e.profile_id=:profile AND e.generation=:generation
                AND e.wiki_chunk_id=w.id) ORDER BY w.id LIMIT 8'''),parameters).mappings().all()
        pending=[]
        for i in range(max(len(sources),len(wiki))):
            if i<len(sources):pending.append(('source',sources[i]))
            if i<len(wiki):pending.append(('wiki',wiki[i]))
        pending=pending[:8]
        if not pending:return {'status':'ready','indexed':0,'profile_id':str(self.profile_id),'generation':profile['generation']}
        contextual=self.client.settings.input_format=='context-v1'
        inputs=[self._context_input(connection,kind,row['id']) if contextual else
                row['body'] if kind=='source' else row['title']+'\n'+row['body'] for kind,row in pending]
        available=[(entry,value) for entry,value in zip(pending,inputs,strict=True) if value is not None]
        if not available:return {'status':'indexed','indexed':0,'profile_id':str(self.profile_id),'generation':profile['generation']}
        pending=[entry for entry,_ in available];inputs=[value for _,value in available]
        result=self.client.embed(inputs)
        if contextual:
            # Wiki chunk insertion can already hold FK locks. Never wait for a
            # writer holding the earlier content lock while waiting on those rows.
            from .current_content import CONTENT_LOCK
            if not connection.execute(text('SELECT pg_try_advisory_xact_lock(:key)'),{'key':CONTENT_LOCK}).scalar_one():
                return {'status':'busy','indexed':0,'profile_id':str(self.profile_id),'generation':profile['generation']}
        indexed=0
        for (kind,row),input_text,vector in zip(pending,inputs,result['vectors'],strict=True):
            if contextual and self._context_input(connection,kind,row['id'],lock=True)!=input_text:
                continue
            connection.execute(text('''INSERT INTO c0_embeddings(space_id,id,profile_id,generation,source_chunk_id,wiki_chunk_id,input_hash,embedding)
                VALUES(:space,:id,:profile,:generation,:source,:wiki,:hash,CAST(:vector AS vector))
                ON CONFLICT(id) DO UPDATE SET generation=EXCLUDED.generation,input_hash=EXCLUDED.input_hash,
                    embedding=EXCLUDED.embedding,created_at=now()'''),
                {**parameters,'space':row['space_id'],'id':uuid5(self.profile_id,kind+'/'+str(row['id'])),
                 'source':row['id'] if kind=='source' else None,'wiki':row['id'] if kind=='wiki' else None,
                 'hash':hashlib.sha256(input_text.encode()).hexdigest(),'vector':vector_literal(vector,profile['dimensions'])})
            indexed+=1
        return {'status':'indexed','indexed':indexed,'profile_id':str(self.profile_id),'generation':profile['generation'],'usage':result['usage']}

    def _context_input(self,connection,kind,key,*,lock=False):
        if kind=='source':
            sql='''SELECT c.body,c.start_offset,d.body AS document_body,d.structure,
                s.title,s.metadata,v.media_type FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
                JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id
                WHERE c.id=:id AND s.current_version_id=v.id AND v.state='ready' AND NOT s.deleted'''
            if lock:sql+=' FOR SHARE OF s'
        else:
            sql='''SELECT w.body,w.start_offset,r.body AS document_body,r.title,r.metadata,
                'text/markdown' AS media_type FROM c0_wiki_chunks w
                JOIN c0_wiki_revisions r ON r.id=w.revision_id JOIN c0_wiki_pages p ON p.id=r.page_id
                WHERE w.id=:id AND p.revision=r.number AND NOT p.deleted'''
            if lock:sql+=' FOR SHARE OF r,p'
        row=connection.execute(text(sql),{'id':key}).mappings().one_or_none()
        return contextual_input(dict(row)) if row else None

    def _reindex(self,connection,payload):
        if self.client is None or UUID(payload['profile_id'])!=self.profile_id:raise ValueError('inactive_embedding_profile')
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':PROFILE_LOCK})
        profile=self._profile(connection,create=True)
        if profile['generation']!=payload['expected_generation']:raise KnowledgeConflict()
        if profile['generation']>=2147483646:raise ValueError('embedding_generation_limit')
        generation=connection.execute(text('UPDATE c0_embedding_profiles SET generation=generation+1 WHERE id=:id RETURNING generation'),{'id':self.profile_id}).scalar_one()
        return {'status':'queued','profile_id':str(self.profile_id),'generation':generation}

    def status(self,actor):
        with self.database.engine.connect() as connection:
            self._space_authorize(connection,actor)
            profile=self._profile(connection) if self.client else None
            if profile is None:return {'configured':self.client is not None,'profile_id':None,'generation':None,'indexed':0,'source_indexed':0,'wiki_indexed':0}
            count=connection.execute(text('SELECT count(*) FROM c0_embeddings WHERE space_id=:space AND profile_id=:id AND generation=:generation'),
                {'space':self._space(connection),'id':self.profile_id,'generation':profile['generation']}).scalar_one()
            counts={}
            for kind in ('source','wiki'):
                eligibility,parameters=EmbeddingStore._eligibility(self,connection,profile,kind)
                counts[kind+'_indexed']=connection.execute(text('SELECT count(*) '+eligibility),parameters).scalar_one()
            return _view({**counts,'configured':True,'profile_id':self.profile_id,'generation':profile['generation'],
                          'input_format':profile['input_format'],**self._coverage(connection,profile,counts),
                          'model':profile['model'],'dimensions':profile['dimensions'],'indexed':count})

    def _coverage(self,connection,profile,counts=None):
        space=self._space(connection)
        expected=connection.execute(text('''SELECT
            (SELECT count(*) FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
             JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id
             WHERE s.space_id=:space AND s.current_version_id=v.id AND v.state='ready' AND NOT s.deleted) AS source_expected,
            (SELECT coalesce(sum(greatest(1,ceil(greatest(char_length(r.body)-200,1)/3600.0)::int)),0)
             FROM c0_wiki_revisions r JOIN c0_wiki_pages p ON p.id=r.page_id
             WHERE p.space_id=:space AND p.revision=r.number AND NOT p.deleted) AS wiki_expected'''),{'space':space}).mappings().one()
        if counts is None:
            counts={}
            for kind in ('source','wiki'):
                eligibility,parameters=EmbeddingStore._eligibility(self,connection,profile,kind)
                counts[kind+'_indexed']=connection.execute(text('SELECT count(*) '+eligibility),parameters).scalar_one()
        expected=dict(expected)
        return {**expected,'complete':all(counts[k+'_indexed']==expected[k+'_expected'] for k in ('source','wiki'))}

    def _ready(self,connection,profile):
        if self.client.settings.input_format=='context-v1':
            coverage=self._coverage(connection,profile)
            return coverage['complete'] and coverage['source_expected']+coverage['wiki_expected']>0
        return connection.execute(text('SELECT 1 FROM c0_embeddings WHERE space_id=:space AND profile_id=:id AND generation=:generation LIMIT 1'),
            {'space':self._space(connection),'id':self.profile_id,'generation':profile['generation']}).scalar_one_or_none() is not None

    def _eligibility(self,connection,profile,kind):
        eligibility='''FROM c0_embeddings e
            WHERE e.space_id=:space AND e.profile_id=:profile AND e.generation=:generation AND (
                (:sources AND e.source_chunk_id IS NOT NULL AND EXISTS(SELECT 1 FROM c0_chunks c
                    JOIN c0_documents d ON d.id=c.document_id JOIN c0_source_versions v ON v.id=d.version_id
                    JOIN c0_sources s ON s.id=v.source_id WHERE c.id=e.source_chunk_id AND s.current_version_id=v.id AND v.state='ready' AND NOT s.deleted))
                OR (:wiki AND e.wiki_chunk_id IS NOT NULL AND EXISTS(SELECT 1 FROM c0_wiki_chunks w
                    JOIN c0_wiki_revisions r ON r.id=w.revision_id JOIN c0_wiki_pages p ON p.id=r.page_id
                    WHERE w.id=e.wiki_chunk_id AND NOT p.deleted AND p.revision=r.number)))'''
        return eligibility,{'space':self._space(connection),'profile':self.profile_id,'generation':profile['generation'],
            'sources':kind!='wiki','wiki':kind!='source'}

    def nearest(self,connection,vector,*,limit=64,kind='all'):
        if type(limit) is not int or not 1<=limit<=64 or kind not in ('all','source','wiki'):raise ValueError('invalid_embedding_query')
        profile=self._profile(connection)
        if profile is None:return []
        encoded=vector_literal(vector,profile['dimensions'])
        eligibility,parameters=self._eligibility(connection,profile,kind)
        parameters={**parameters,'vector':encoded,'limit':limit}
        connection.execute(text("SET LOCAL hnsw.iterative_scan='strict_order'"))
        connection.execute(text('SET LOCAL hnsw.ef_search=64'))
        connection.execute(text('SET LOCAL hnsw.max_scan_tuples=1000'))
        query=text('''WITH nearest AS MATERIALIZED (
            SELECT e.id,e.source_chunk_id,e.wiki_chunk_id,e.embedding <=> CAST(:vector AS vector) AS distance
            '''+eligibility+''' ORDER BY e.embedding <=> CAST(:vector AS vector) LIMIT :limit)
            SELECT * FROM nearest ORDER BY distance,id''')
        rows=[dict(row) for row in connection.execute(query,parameters).mappings()]
        if len(rows)<limit:
            # Global ANN pruning can starve a small authorized space. Materialize
            # its eligible rows before exact ordering when the scan underfills.
            exact=text('''WITH candidates AS MATERIALIZED (
                SELECT e.id,e.source_chunk_id,e.wiki_chunk_id,e.embedding '''+eligibility+''')
                SELECT id,source_chunk_id,wiki_chunk_id,embedding <=> CAST(:vector AS vector) AS distance
                FROM candidates ORDER BY distance,id LIMIT :limit''')
            rows=[dict(row) for row in connection.execute(exact,parameters).mappings()]
        return rows


def reindex_payload(value):
    if not isinstance(value,dict) or set(value)!={'profile_id','expected_generation'}:
        raise ValueError('invalid_embedding_reindex')
    try:key=UUID(value['profile_id'])
    except (ValueError,TypeError,AttributeError):raise ValueError('invalid_embedding_reindex') from None
    generation=value['expected_generation']
    if type(generation) is not int or not 1<=generation<2147483646:raise ValueError('invalid_embedding_reindex')
    return {'profile_id':str(key),'expected_generation':generation}


def register_embedding_handlers(registry,store):
    def index(connection,payload):
        result=store._index_batch(connection)
        # Continue only enabled automatic indexing, with at most one successor.
        enabled=connection.execute(text('SELECT enabled FROM c0_scheduled_tasks WHERE id=:id'),
                                   {'id':SCHEDULE_ID}).scalar_one_or_none()
        if result['indexed'] and enabled:
            pending=connection.execute(text("SELECT 1 FROM c0_jobs WHERE handler='embedding.index' AND state='queued' LIMIT 1")).scalar_one_or_none()
            if pending is None:
                JobService(store.database,registry)._enqueue(connection,'embedding.index',{},
                    'embedding-continuation:'+str(store.profile_id)+':'+uuid4().hex)
        return result
    registry.register(Handler('embedding.index',index,empty_payload,timeout_seconds=15))
    registry.register(Handler('embedding.reindex',store._reindex,reindex_payload,timeout_seconds=10))
