# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Reusable original-text ingestion and bounded independent readback."""
from time import sleep,perf_counter
from .errors import C0Error
from .state import digest


def submit_text(client, *, body, title, metadata, external_key, media_type='text/plain', source=None):
    raw = body.encode('utf-8')
    if not raw or len(raw) > 131072:
        raise C0Error('Original text must contain 1–131072 UTF-8 bytes; split it with provenance before ingestion')
    request = {'body': body, 'title': title, 'metadata': metadata, 'media_type': media_type,
               'idempotency_key': digest([client.space_id, external_key, digest(raw)])}
    if source:
        current = client.call('sources_get', source_id=source['id'])
        request.update(source_id=source['id'], expected_revision=current['revision'])
        request['idempotency_key']=digest([client.space_id,external_key,digest(raw),source['id'],current['revision'],title,metadata])
    return client.call('sources_ingest_text', data=request)


def verify_document(client, version, body, *, attempts=20, seconds=3, timings=None):
    if type(attempts) is not int or not 1 <= attempts <= 100 or not 0 <= seconds <= 30:
        raise C0Error('Invalid bounded extraction wait')
    started=perf_counter()
    for attempt in range(attempts):
        if attempt == 0 and version['state'] == 'ready':
            current = version
        else:
            rows = client.listing('source_versions_list', 'versions', source_id=version['source_id'])
            current = next((v for v in rows if v['id'] == version['id']), None)
        if not current:
            raise C0Error('Source version missing on readback')
        if current['source_id'] != version['source_id'] or current['content_hash'] != version['content_hash']:
            raise C0Error('Source version identity/hash changed on readback')
        if current['state'] == 'failed':
            raise C0Error('Source extraction failed; inspect source status before retrying')
        if current['state'] == 'ready':
            break
        if attempt + 1 < attempts:
            sleep(seconds)
    else:
        raise C0Error('Source indexing not ready within bounded wait; resume')
    if timings is not None:timings['extraction_seconds']=timings.get('extraction_seconds',0.)+perf_counter()-started
    started=perf_counter()
    document = client.call('documents_get', version_id=version['id'])
    if document['body'] != body or digest(document['body'].encode()) != version['content_hash']:
        raise C0Error('Verbatim source body/hash readback mismatch')
    if timings is not None:timings['readback_seconds']=timings.get('readback_seconds',0.)+perf_counter()-started
    return document
