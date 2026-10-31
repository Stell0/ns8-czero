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


def corpus_snapshot(client):
    corpus=[]
    for summary in client.listing('source_documents_list','documents'):
        doc=client.call('source_documents_get',logical_document_id=summary['id'])
        if doc['state']!='ready' or doc['multipart']:raise ValueError('selected_profile_requires_single_complete_documents')
        physical=client.call('documents_get',version_id=doc['revision_id'])
        chunks=client.call('document_chunks_list',document_id=physical['id'])['chunks']
        citations=[client.call('citations_get',chunk_id=c['id']) for c in chunks]
        meta=doc['metadata'];p=meta.get('provenance',{})
        corpus.append({'id':doc['id'],'url':meta['canonical_url'],'generation':doc['revision_id'],
            'content_hash':body_hash(doc['body']),'body':doc['body'],'title':doc.get('title',''),
            'product':p.get('product',''),'version':p.get('product_version',''),'language':p.get('language',''),
            'chunks':citations})
    corpus.sort(key=lambda d:d['id']);validate_corpus(corpus);return corpus
