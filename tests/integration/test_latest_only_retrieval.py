# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real publisher and pgvector: staging/retirement never become candidates."""
import json
from uuid import uuid4

import httpx2
from sqlalchemy import text

from czero_core.embeddings import EmbeddingStore
from czero_core.providers import EmbeddingClient,EmbeddingSettings
from czero_core.retrieval import SearchService
from czero_core.structured import StructuredFilters,StructuredSearchService
from test_full_documents import logical,publish
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_spaces_http import space_http
from test_mcp_http import transport
from test_auth_http import application
from c0_projects.model import Item,sha
from c0_projects.publish import parts,sync_part,save_snapshot


def test_real_publisher_staged_retired_and_unchanged_vectors(logical):
    client,definition,documents,actor,path=logical
    calls=[]
    def embed(request):
        payload=json.loads(request.content);calls.append(payload)
        return httpx2.Response(200,json={'model':payload['model'],'data':[
            {'index':i,'embedding':[1.,0.,0.] if 'alpha' in value else [0.,1.,0.]}
            for i,value in enumerate(payload['input'])]})
    provider=EmbeddingClient(EmbeddingSettings('https://embedding.example.test/'+uuid4().hex,'fixture',dimensions=3),transport=httpx2.MockTransport(embed))
    store=EmbeddingStore(documents.database,provider,documents.access)
    search=SearchService(documents.database,documents.access,embedding_client=provider).in_space(client.space_id)
    filtered=StructuredSearchService(documents.database,documents.access,embedding_client=provider).in_space(client.space_id)
    try:
        first,receipts=publish(client,definition,path,'# alpha\n\nOLD-ONLY-EVIDENCE\n')
        old_version=receipts[0]['version_id']
        old_doc=client.call('documents_get',version_id=old_version)
        old_ids={row['id'] for row in client.call('document_chunks_list',document_id=old_doc['id'])['chunks']}
        with documents.database.engine.begin() as connection:store._index_batch(connection)
        changed=Item('documents','manual.md','Synthetic full manual',b'# beta\n\nNEW-ONLY-EVIDENCE\n','text/markdown')
        pending=sync_part(client,next(parts(changed)),path/'pending.json',definition_hash=sha(definition),attempts=4,seconds=0)
        staged_doc=client.call('documents_get',version_id=pending['version_id'])
        staged_ids={row['id'] for row in client.call('document_chunks_list',document_id=staged_doc['id'])['chunks']}
        with documents.database.engine.begin() as connection:
            # A delayed index tick must ignore a genuinely extracted staged part.
            store._index_batch(connection)
            assert connection.execute(text('SELECT count(*) FROM c0_embeddings WHERE source_chunk_id=ANY(CAST(:ids AS uuid[]))'),{'ids':list(staged_ids)}).scalar_one()==0
        for mode in ('text','semantic','hybrid'):
            hits=search.search(actor,'NEW-ONLY-EVIDENCE',mode=mode,rerank='off')['hits']
            assert staged_ids.isdisjoint(hit['id'] for hit in hits)
            hits=filtered.search(actor,'NEW-ONLY-EVIDENCE',filters=StructuredFilters(categories=['source']),mode=mode,rerank='off')['hits']
            assert staged_ids.isdisjoint(hit['reference']['id'] for hit in hits)
        assert documents.read_document(actor,first['id'])['body']=='# alpha\n\nOLD-ONLY-EVIDENCE\n'
        second=save_snapshot(client,changed,[pending]);assert second['id']==first['id']
        with documents.database.engine.begin() as connection:
            assert connection.execute(text('SELECT count(*) FROM c0_embeddings WHERE source_chunk_id=ANY(CAST(:ids AS uuid[]))'),{'ids':list(old_ids)}).scalar_one()==0
            store._index_batch(connection)
        assert client.call('sources_search',query='OLD-ONLY-EVIDENCE')['citations']==[]
        assert search.search(actor,'OLD-ONLY-EVIDENCE',mode='text')['hits']==[]
        for mode in ('text','semantic','hybrid'):
            hits=search.search(actor,'NEW-ONLY-EVIDENCE',mode=mode,rerank='off')['hits']
            assert hits and old_ids.isdisjoint(hit['id'] for hit in hits)
            typed=filtered.search(actor,'NEW-ONLY-EVIDENCE',filters=StructuredFilters(categories=['source']),mode=mode,rerank='off')['hits']
            assert typed and old_ids.isdisjoint(hit['reference']['id'] for hit in typed)
        before=len(calls)
        again=sync_part(client,next(parts(changed)),path/'pending.json',definition_hash=sha(definition),attempts=4,seconds=0)
        assert again['version_id']==pending['version_id'] and save_snapshot(client,changed,[again])==second
        with documents.database.engine.begin() as connection:assert store._index_batch(connection)['indexed']==0
        assert len(calls)==before
    finally:
        with documents.database.engine.begin() as connection:connection.execute(text('DELETE FROM c0_embedding_profiles WHERE id=:id'),{'id':store.profile_id})
