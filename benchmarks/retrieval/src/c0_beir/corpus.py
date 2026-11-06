# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Resumable source ingestion and read-only whole-corpus verification."""
import time

from c0_ingest.errors import C0Error
from c0_ingest.sources import submit_text, verify_document
from c0_ingest.state import atomic, digest, read


def binding(client, dataset):
    return {'format': 1, 'url': client.config['url'], 'account_id': client.config['account_id'],
            'space_id': client.space_id, 'dataset': dataset.name, 'split': dataset.split,
            'fingerprint': dataset.fingerprint}


def metadata(dataset, key):
    return {'benchmark': 'beir-v1', 'dataset': dataset.name, 'beir_id': key,
            'dataset_fingerprint': dataset.fingerprint, 'content_sha256': digest(dataset.body(key).encode())}


def title(dataset, key):
    # Original titles remain complete in the searchable body and local dataset.
    return 'BEIR ' + dataset.name + ' ' + digest(key)[:32]


def inventory(client, dataset):
    if client.listing('wiki_pages_list', 'pages'):
        raise C0Error('Benchmark space contains unrelated Wiki content; use a dedicated empty protected space')
    found = {}
    for source in client.listing('sources_list', 'sources'):
        key = source.get('metadata', {}).get('beir_id')
        if (key not in dataset.corpus or key in found or source.get('deleted')
                or source['metadata'] != metadata(dataset, key) or source['title'] != title(dataset, key)):
            raise C0Error('Unrelated, duplicate or changed remote source; corpus is unsuitable for evaluation')
        found[key] = source
    return found


def verify_source(client, dataset, key, source, *, attempts=1, seconds=0, timings=None):
    versions = client.listing('source_versions_list', 'versions', source_id=source['id'])
    if len(versions) != 1 or versions[0]['content_hash'] != metadata(dataset, key)['content_sha256']:
        raise C0Error('Changed or ambiguous source generation in benchmark space')
    version = versions[0]
    document = verify_document(client, version, dataset.body(key), attempts=attempts, seconds=seconds, timings=timings)
    if document['version_id'] != version['id'] or document['text_hash'] != digest(dataset.body(key).encode()):
        raise C0Error('Changed extracted document identity/hash')
    chunks = client.listing('document_chunks_list', 'chunks', document_id=document['id'])
    if not chunks:
        raise C0Error('Ready source has no searchable chunks')
    identities = []
    for chunk in chunks:
        if (chunk['document_id'] != document['id'] or digest(chunk['body'].encode()) != chunk['content_hash']
                or document['body'][chunk['start_offset']:chunk['end_offset']] != chunk['body']):
            raise C0Error('Invalid chunk identity/hash/offset readback')
        identities.append({k: chunk[k] for k in ('id', 'content_hash', 'start_offset', 'end_offset')})
    current = client.call('sources_get', source_id=source['id'])
    if current['metadata'] != metadata(dataset, key) or current['title'] != title(dataset, key):
        raise C0Error('Source metadata changed during readback')
    return {'id': source['id'], 'version_id': version['id'], 'revision': current['revision'],
            'document_id': document['id'], 'content_hash': version['content_hash'], 'chunks': identities}


def load_manifest(path, client, dataset):
    manifest = read(path)
    if not isinstance(manifest, dict) or manifest.get('binding') != binding(client, dataset):
        raise C0Error('Missing manifest or dataset/instance/account/space fingerprint mismatch; run ingest in the original configuration')
    return manifest


def check(client, dataset, manifest, *, full=True):
    if (manifest.get('binding') != binding(client, dataset) or not manifest.get('complete')
            or set(manifest['documents']) != set(dataset.corpus) or manifest.get('pending') or manifest.get('submitted')):
        raise C0Error('Incomplete or incompatible ingestion manifest; run benchmark ingest')
    found = inventory(client, dataset)
    if set(found) != set(dataset.corpus):
        raise C0Error('Missing/additional corpus documents; benchmark invalid')
    for number, key in enumerate(sorted(dataset.corpus), 1):
        expected = manifest['documents'][key]
        if (found[key]['id'] != expected['id'] or found[key]['revision'] != expected['revision']
                or (full and verify_source(client, dataset, key, found[key]) != expected)):
            raise C0Error('Corpus drift: source/version/revision/chunks changed')
        if full and number % 100 == 0:
            print(f'Verified {number}/{len(found)} corpus documents', flush=True)
    return digest(manifest['documents'])


def index_status(client, manifest):
    status = client.call('knowledge_index_status')
    expected = sum(len(row['chunks']) for row in manifest['documents'].values())
    # Current public API exposes counts, not per-chunk embedding receipts. In an
    # exclusively verified source space, require matching complete coverage.
    return {**status, 'expected_chunks': expected,
            'coverage_ready': bool(status.get('configured') and status.get('profile_id')
                                   and expected and status.get('indexed') == expected),
            'readiness_basis': 'space/profile generation count equals verified current chunk count; connectivity checked by searches'}


def ingest(client, dataset, path, *, attempts=20, seconds=3, index_attempts=20):
    dataset.validate_ingestion()  # Fail oversized items before the first write.
    manifest = read(path)
    expected = binding(client, dataset)
    if manifest is None:
        manifest = {'binding': expected, 'documents': {}, 'submitted': {}, 'pending': None, 'complete': False,
                    'timings': {'ingestion_seconds': 0., 'indexing_seconds': 0.}}
    elif not isinstance(manifest, dict) or manifest.get('binding') != expected:
        raise C0Error('Dataset fingerprint or target changed; refusing incompatible state')
    # Older single-document manifests resume through the same pending intent.
    submitted = manifest.setdefault('submitted', {})
    if (not isinstance(submitted, dict) or set(submitted) - set(dataset.corpus)
            or set(submitted) & set(manifest['documents'])
            or manifest.get('pending') in set(submitted) | set(manifest['documents'])):
        raise C0Error('Invalid submission journal; inspect manifest')
    found = inventory(client, dataset)
    for key, record in manifest['documents'].items():
        if key not in found or verify_source(client, dataset, key, found[key]) != record:
            raise C0Error('Completed ingestion has drifted; refusing to overwrite content')
    for key, receipt in submitted.items():
        if key not in found or found[key]['id'] != receipt['id']:
            raise C0Error('Acknowledged submission missing or changed; refusing to overwrite content')
        versions = client.listing('source_versions_list', 'versions', source_id=found[key]['id'])
        if (len(versions) != 1 or versions[0]['id'] != receipt['version_id']
                or versions[0]['content_hash'] != receipt['content_hash']
                or receipt['content_hash'] != metadata(dataset, key)['content_sha256']):
            raise C0Error('Acknowledged source generation changed; refusing to overwrite content')
        if versions[0]['state'] == 'failed':
            raise C0Error('Source extraction failed; inspect source status before retrying')
    # Acknowledged submissions and the one uncertain intent are the only
    # unverified remote items which this manifest can legitimately own.
    if set(found) - set(manifest['documents']) - set(submitted) - {manifest.get('pending')}:
        raise C0Error('Remote documents have no local receipt; refusing to adopt unrelated content')
    started = time.perf_counter()
    atomic(path, manifest)
    try:
        for number, key in enumerate(sorted(dataset.corpus), 1):
            if key in manifest['documents'] or key in submitted:
                continue
            if manifest.get('pending') not in (None, key):
                raise C0Error('Pending ingestion order differs; inspect manifest')
            manifest['pending'] = key
            manifest['complete'] = False
            atomic(path, manifest)  # Commit intent before I/O; same deterministic request on recovery.
            if key not in found:
                # On resume the complete inventory was read first. Replaying the
                # identical idempotency key cannot duplicate a late committed write.
                receipt = submit_text(client, body=dataset.body(key), title=title(dataset, key), metadata=metadata(dataset, key),
                            external_key=['beir-v1', dataset.fingerprint, key])
                found[key] = {'id': receipt['source_id']}
            else:
                # An uncertain submission may have committed before interruption.
                versions = client.listing('source_versions_list', 'versions', source_id=found[key]['id'])
                if len(versions) != 1:
                    raise C0Error('Ambiguous pending source generation')
                receipt = versions[0]
            if (receipt['source_id'] != found[key]['id']
                    or receipt['content_hash'] != metadata(dataset, key)['content_sha256']):
                raise C0Error('Submission identity/hash differs from the original dataset')
            submitted[key] = {'id': receipt['source_id'], 'version_id': receipt['id'],
                              'content_hash': receipt['content_hash']}
            manifest['pending'] = None
            atomic(path, manifest)  # Save acknowledgement before submitting the next document.
            if number % 25 == 0 or number == len(dataset.corpus):
                print(f'Submitted {number}/{len(dataset.corpus)} documents; extraction continues in the background', flush=True)
        # Submission never waits for extraction. Only verified originals earn
        # document receipts, and evaluation still requires the complete corpus.
        for key in sorted(list(submitted)):
            record = verify_source(client, dataset, key, found[key], attempts=attempts, seconds=seconds)
            if any(record[field] != submitted[key][field] for field in ('id', 'version_id', 'content_hash')):
                raise C0Error('Acknowledged source generation changed before verification')
            manifest['documents'][key] = record
            del submitted[key]
            atomic(path, manifest)
            number = len(manifest['documents'])
            if number % 25 == 0 or number == len(dataset.corpus):
                print(f'Ingested and verified {number}/{len(dataset.corpus)} documents', flush=True)
        manifest['complete'] = True
    finally:
        manifest['timings']['ingestion_seconds'] += time.perf_counter() - started
        atomic(path, manifest)
    check(client, dataset, manifest)
    started = time.perf_counter()
    try:
        for attempt in range(index_attempts):
            status = index_status(client, manifest)
            if not status['configured'] or status['coverage_ready']:
                break
            if attempt + 1 < index_attempts:
                time.sleep(seconds)
        manifest['index'] = status
    finally:
        manifest['timings']['indexing_seconds'] += time.perf_counter() - started
        atomic(path, manifest)
    print(f"Corpus ready; semantic coverage ready: {manifest['index']['coverage_ready']}; "
          f"ingestion {manifest['timings']['ingestion_seconds']:.1f}s, index wait {manifest['timings']['indexing_seconds']:.1f}s", flush=True)
    return manifest
