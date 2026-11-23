# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Short fenced publication transactions; collection never holds database locks."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from sqlalchemy import text
from .automatic_sources import UpdateConflict, UpdateNotFound
from .drive_sources import DriveAudienceChanged
from .identity import PermissionDenied
from .source_collectors import collect
from .source_http import CollectionError
from .current_content import content_lock
from .extraction import ExtractionError, MAX_TEXT_BYTES, MAX_PDF_BYTES, chunks, extract_isolated
from .sources import _publish_extracted
from .spaces import hold_authority


DRIVE_FILENAMES = {'text/markdown':'source.md','text/plain':'source.txt','application/pdf':'source.pdf'}
SKIPPED_DRIVE_ERRORS = frozenset({'invalid_text','no_text','too_large','invalid_pdf','encrypted_pdf',
    'unsupported_scan','pdf_too_many_pages','parser_timeout','resource_limit','parser_failed'})


def prepare_drive_document(body, media_type):
    """Parse complete bytes with the normal isolated parser before confirming remote access."""
    limit = MAX_PDF_BYTES if media_type == 'application/pdf' else MAX_TEXT_BYTES
    if not isinstance(body, bytes) or len(body)>limit:
        raise ExtractionError('too_large')
    if media_type == 'application/pdf':
        from .drive_pdf import prepare_pdf
        return prepare_pdf(body)
    if media_type not in DRIVE_FILENAMES:
        raise ExtractionError('unsupported_format')
    with NamedTemporaryFile() as temporary:
        temporary.write(body)
        temporary.flush()
        evidence = extract_isolated(Path(temporary.name), media_type)
    return evidence, chunks(evidence)


class SourceUpdater:
    def __init__(self, definitions, sources, *, collector=collect, drive_collector=None, drive_recheck=None):
        self.definitions, self.sources, self.collector = definitions, sources, collector
        self.drive_collector = drive_collector
        self.drive_recheck = drive_recheck

    def tick(self):
        service=self.definitions
        service._prune_runs()
        row=service.claim()
        if row is None:return 0
        sources=self.sources.in_space(row['space_id'])
        drive = None
        try:
            # Finish extraction from the preceding batch before advancing collection.
            with service.database.engine.begin() as c:
                hold_authority(c);content_lock(c);service.fenced(c,row)
                pending=c.execute(text('''SELECT i.*,v.state,v.media_type,s.revision,s.current_version_id FROM c0_automatic_source_items i
                    LEFT JOIN c0_source_versions v ON v.id=i.version_id AND v.source_id=i.source_id JOIN c0_sources s ON s.id=i.source_id
                    WHERE i.definition_id=:id'''),{'id':row['id']}).mappings().all()
                if any(v['state'] is None and v['version_id'] is not None for v in pending):raise UpdateConflict('source_changed')
                if any(v['state']=='failed' for v in pending):raise CollectionError('source_extraction_failed')
                if any(v['state']!='ready' and v['version_id'] is not None for v in pending):
                    service._finish(c,row,'pending',cursor=row['cursor']);return 1
                for old in pending:
                    if old['current_version_id']!=old['version_id']:raise UpdateConflict('source_changed')
                    # Extraction cannot authorize intervening manual changes.
                    if old['revision'] != old['source_revision']:raise UpdateConflict('source_changed')
                if row['kind'] == 'google_drive':
                    drive = service._drive_worker_binding(c, row)
            if row['cursor'].get('collection_complete'):
                with service.database.engine.begin() as c:
                        hold_authority(c);content_lock(c);service.fenced(c,row);service._finish(c,row,'complete')
                return 1
            if drive is not None:
                if self.drive_collector is None or self.drive_recheck is None:
                    raise CollectionError('drive_unavailable')
                fetched, cursor, complete = self.drive_collector(drive['credential'], drive['folder_id'], row['cursor'])
                items, checked = self._prepare_drive_items(row, fetched, pending)
                self.drive_recheck(drive['credential'],drive['folder_id'],checked)
            else:
                items,cursor,complete=self.collector(row['kind'],row['config'],row['cursor'])
            if row['processed']+len(items)>10000:raise CollectionError('source_run_item_limit')
            with service.database.engine.begin() as c:
                hold_authority(c);content_lock(c);service.fenced(c,row)
                for item in items:
                    old=c.execute(text('''SELECT i.*,v.media_type FROM c0_automatic_source_items i
                        LEFT JOIN c0_source_versions v ON v.id=i.version_id WHERE definition_id=:id AND external_key=:key'''),
                                  {'id':row['id'],'key':item['key']}).mappings().one_or_none()
                    digest=item['digest'] if drive is not None else hashlib.sha256(item['body']).hexdigest()
                    reindex = drive is not None and old is not None and old['media_type'] != item['media_type']
                    if old:
                        saved=sources._source(c,old['source_id'],lock=True)
                        if saved['deleted'] or saved['revision']!=old['source_revision']:
                            raise UpdateConflict('source_changed')
                        if old['content_hash'] == digest and not reindex:
                            if drive is not None and saved['title'] != item['title']:
                                revision = sources._update_current_metadata(c, saved['id'], item['title'], json.dumps(saved['metadata']))
                                c.execute(text('''UPDATE c0_automatic_source_items SET source_revision=:revision
                                    WHERE definition_id=:id AND external_key=:key'''),
                                    {'revision':revision,'id':row['id'],'key':item['key']})
                            continue
                    metadata={**item['metadata'],'automatic_source_id':str(row['id']),'external_key':item['key']}
                    version=sources._ingest(c,BytesIO(item['body']),title=item['title'],
                        filename=DRIVE_FILENAMES.get(item['media_type'],'source.txt'),
                        media_type=item['media_type'],retain_original=drive is not None and bool(metadata.get('pdf_textless_pages')),
                        encoded=json.dumps(metadata),
                        source_id=old['source_id'] if old else None,expected_revision=old['source_revision'] if old else None,
                        force_reindex=reindex,queue_extraction=drive is None)
                    c.execute(text("UPDATE c0_source_versions SET publication_metadata=CAST(publication_metadata AS jsonb) || jsonb_build_object('_automatic_source_revision',CAST(:revision AS bigint)) WHERE id=:id"),{'id':version['id'],'revision':row['revision']})
                    revision=sources._source(c,version['source_id'])['revision']
                    c.execute(text('''INSERT INTO c0_automatic_source_items(definition_id,external_key,source_id,source_revision,version_id,content_hash)
                        VALUES (:id,:key,:source,:revision,:version,:hash) ON CONFLICT(definition_id,external_key) DO UPDATE
                        SET source_revision=EXCLUDED.source_revision,version_id=EXCLUDED.version_id,content_hash=EXCLUDED.content_hash'''),
                        {'id':row['id'],'key':item['key'],'source':version['source_id'],'revision':revision,'version':version['id'],'hash':digest})
                    if drive is not None:
                        staged = c.execute(text('SELECT * FROM c0_source_versions WHERE id=:id FOR UPDATE'),
                                           {'id':version['id']}).mappings().one()
                        evidence,segments = item['extracted']
                        result = _publish_extracted(c, staged, evidence, segments, sources.jobs,
                                                    access=service.access,reuse_identical=False)
                        if result['state'] != 'ready':
                            raise UpdateConflict('source_changed')
                cursor={**cursor,'collection_complete':complete}
                # Bound persisted frontiers independently from downloaded bodies.
                if len(json.dumps(cursor).encode())>2*1024*1024:raise CollectionError('source_cursor_limit')
                service.fenced(c,row)
                c.execute(text('UPDATE c0_source_update_runs SET processed=processed+:count WHERE id=:id'),{'id':row['run_id'],'count':len(items)})
                service._finish(c,row,'complete' if drive is not None and complete else 'pending',cursor=cursor)
            return 1
        except (UpdateConflict,UpdateNotFound):
            self._fail(row,'blocked','source_changed')
        except DriveAudienceChanged:
            self._fail(row,'blocked','drive_audience_changed')
        except PermissionDenied:
            self._fail(row,'blocked','authority_changed')
        except CollectionError as error:
            if drive is not None and str(error) == 'drive_reconnect_required':
                service._expired_drive({'space':row['space_id'],'account':row['owner_id']}, drive['generation'])
                return 1
            code=str(error) if re.fullmatch('[a-z][a-z0-9_]{0,63}',str(error)) else 'collection_incomplete'
            retry_after=getattr(error,'retry_after','')
            transient=code in {'source_dns_timeout','source_dns_unavailable','source_transport_failed','source_http_408','source_http_429','source_http_500','source_http_502','source_http_503','source_http_504','source_run_item_limit'} or bool(retry_after)
            self._fail(row,'partial' if transient else 'blocked',code,retry_after)
        except Exception:
            self._fail(row,'failed','source_update_failed')
        return 1

    @staticmethod
    def _drive_item(row, item):
        # A definition-scoped identity is enough for replay and rename. Private
        # provider metadata, links and original file IDs never enter source reads.
        identifier = item['key']
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', identifier):
            raise CollectionError('invalid_drive_item')
        if item['media_type'] not in DRIVE_FILENAMES:
            raise CollectionError('invalid_drive_item')
        title = item['title']
        if not isinstance(title, str) or not title.strip() or len(title)>256 or any(ord(ch)<32 for ch in title):
            raise CollectionError('invalid_drive_item')
        opaque = hashlib.sha256(f"{row['id']}/{identifier}".encode()).hexdigest()
        return {'key':opaque, 'title':title, 'body':item['body'], 'media_type':item['media_type'], 'metadata':{}}

    def _prepare_drive_items(self, row, fetched, pending):
        previous = {old['external_key']:(old['content_hash'],old['media_type']) for old in pending}
        ready, checked = [], []
        for raw in fetched:
            item = self._drive_item(row,raw)
            item['digest'] = hashlib.sha256(item['body']).hexdigest()
            if previous.get(item['key']) != (item['digest'],item['media_type']):
                try:
                    item['extracted'] = prepare_drive_document(item['body'],item['media_type'])
                    missing = getattr(item['extracted'][0], 'textless_pages', ())
                    if missing:
                        item['metadata']['pdf_textless_pages'] = list(missing)
                        item['metadata']['pdf_textless_page_count'] = len(missing)
                except ExtractionError as failure:
                    if failure.code in SKIPPED_DRIVE_ERRORS:
                        continue
                    raise CollectionError('source_extraction_failed') from None
            ready.append(item)
            checked.append(raw)
        return ready,checked

    def _fail(self,row,state,code,retry_after=''):
        with self.definitions.database.engine.begin() as c:
            c.execute(text('SELECT id FROM c0_automatic_sources WHERE id=:id FOR UPDATE'), {'id':row['id']})
            current=c.execute(text('SELECT lease,state,lease_until>clock_timestamp() AS lease_current FROM c0_source_update_runs WHERE id=:id FOR UPDATE'),{'id':row['run_id']}).mappings().one_or_none()
            if current and current['state']=='running' and current['lease']==row['lease'] and current['lease_current']:
                self.definitions._finish(c,row,state,code,retry_after=retry_after)
