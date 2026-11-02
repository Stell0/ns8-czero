# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reuse the private ingestion connection, lock and target binding for maintenance."""
import asyncio
from contextlib import contextmanager

from c0_ingest.auth import locked
from c0_ingest.client import C0
from c0_ingest.config import connection_settings
from c0_ingest.jobs import check_job
from .protocol import body_hash,validate_corpus


@contextmanager
def job_client(job,writable=False):
    check_job(job)
    with locked(job/'job.lock'):
        client=C0(connection_settings(job))
        try:
            space=client.select_space(client.config['space_id'],writable=writable)
            if space['name']!=client.config['space_name']:raise ValueError('exact_space_name_changed')
            yield client
        finally:client.close()


async def read_corpus(call, *, max_sources=1000, max_source_bytes=134217728):
    async def listing(name, field, *, maximum=100000, **arguments):
        rows=[]
        for offset in range(0,100000,100):
            page=(await call(name,limit=100,offset=offset,**arguments))[field]
            rows.extend(page)
            if len(rows)>maximum:raise ValueError('source_selection_budget')
            if len(page)<100:return rows
        raise ValueError('corpus_inventory_incomplete')

    corpus=[];total_bytes=0
    summaries=await listing('source_documents_list','documents',maximum=max_sources)
    if len(summaries)>max_sources:raise ValueError('source_selection_budget')
    for summary in summaries:
        doc=await call('source_documents_get',logical_document_id=summary['id'])
        if doc['state']!='ready' or doc.get('body') is None:raise ValueError('corpus_document_not_ready')
        total_bytes+=len(doc['body'].encode())
        if total_bytes>max_source_bytes:raise ValueError('source_total_bytes_budget')
        if body_hash(doc['body'])!=doc['text_hash']:raise ValueError('corpus_document_hash_mismatch')
        parts=doc['parts'] if doc['multipart'] else [{'version_id':doc['revision_id']}]
        citations=[]
        for part in parts:
            physical=await call('documents_get',version_id=part['version_id'])
            if 'document_id' in part and physical['id']!=part['document_id']:raise ValueError('corpus_part_identity_mismatch')
            if 'text_hash' in part and physical['text_hash']!=part['text_hash']:raise ValueError('corpus_part_hash_mismatch')
            chunks=await listing('document_chunks_list','chunks',document_id=physical['id'])
            for chunk in chunks:
                citation=await call('citations_get',chunk_id=chunk['id'])
                if (citation['version_id']!=part['version_id'] or citation['document_id']!=physical['id']
                        or ('source_id' in part and citation['source_id']!=part['source_id'])):
                    raise ValueError('corpus_citation_identity_mismatch')
                citations.append(citation)
        meta=doc['metadata'];p=meta.get('provenance',{})
        corpus.append({'id':doc['id'],'url':meta['canonical_url'],'generation':doc['revision_id'],
            'content_hash':body_hash(doc['body']),'body':doc['body'],'title':doc.get('title',''),
            'product':p.get('product',''),'version':p.get('product_version',''),'language':p.get('language',''),
            'chunks':citations})
        if doc['multipart']:corpus[-1]['parts']=doc['parts']
    corpus.sort(key=lambda d:d['id']);validate_corpus(corpus);return corpus


def corpus_snapshot(client, *, max_sources=1000, max_source_bytes=134217728):
    async def call(name, **arguments):return client.call(name,**arguments)
    return asyncio.run(read_corpus(call,max_sources=max_sources,max_source_bytes=max_source_bytes))
