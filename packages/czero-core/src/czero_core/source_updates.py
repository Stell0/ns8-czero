# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Short fenced publication transactions; collection never holds database locks."""
import hashlib
from io import BytesIO
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from sqlalchemy import text
from .automatic_sources import UpdateConflict, UpdateNotFound
from .drive_sources import DriveAudienceChanged
from .identity import PermissionDenied
from .source_collectors import attachment_key, collect, strong_etag
from .source_http import CollectionError
from .current_content import content_lock, retire_versions
from .extraction import ExtractionError, MAX_TEXT_BYTES, MAX_PDF_BYTES, chunks, extract_isolated
from .sources import SourceConflict, SourceNotFound, _publish_extracted
from .spaces import hold_authority


DRIVE_FILENAMES = {'text/markdown':'source.md','text/plain':'source.txt','application/pdf':'source.pdf'}
SKIPPED_DRIVE_ERRORS = frozenset({'invalid_text','no_text','too_large','invalid_pdf','encrypted_pdf',
    'unsupported_scan','pdf_too_many_pages'})
DRIVE_PARSER_FAILURES = frozenset({'parser_timeout','resource_limit','parser_failed'})


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


def terminal_failure(item):
    return (item['state'] in (None, 'failed') or item['job_state'] in ('failed', 'cancelled')
            or item['extraction_state'] in ('failed', 'superseded'))


def pdf_validator(sources, rows):
    ready = {row['external_key']: row for row in rows if row['media_type'] == 'application/pdf'
             and row['version_id'] == row['current_version_id'] and row['original_present']
             and not terminal_failure(row)}

    def lookup(url):
        row = ready.get(attachment_key(url))
        if row is None:
            return None
        metadata = row['source_metadata']
        if metadata.get('original_url') != url or metadata.get('canonical_url') != url:
            return None
        etag = strong_etag(metadata.get('http_etag'))
        if etag:
            try:
                sources.originals.check({**row, 'id': row['version_id']})
            except ExtractionError:
                return None
        return etag

    return lookup


def restore_original(connection, sources, row, body, digest):
    """Restore verified identical bytes at their existing current identity."""
    if row['version_content_hash'] != digest or row['version_id'] != row['current_version_id']:
        raise UpdateConflict('source_changed')
    try:
        sources.originals.check({**row, 'id': row['version_id']})
    except ExtractionError:
        sources.originals.write(row['version_id'], BytesIO(body), media_type='application/pdf')
    else:
        if row['original_present']:
            return False
    connection.execute(text('UPDATE c0_source_versions SET original_present=true WHERE id=:id'),
                       {'id': row['version_id']})
    return True


def record(progress, group, name):
    values = progress.setdefault(group, {})
    # Summaries contain codes and counters only. Cap remote HTTP status diversity.
    if group == 'reasons' and name.startswith('source_http_'):
        name = 'source_http_error'
    values[name] = values.get(name, 0) + 1


def save_progress(connection, row, progress):
    connection.execute(text('UPDATE c0_source_update_runs SET diagnostics=CAST(:progress AS jsonb) WHERE id=:id'),
                       {'id': row['run_id'], 'progress': json.dumps(progress)})


class SourceUpdater:
    def __init__(self, definitions, sources, *, collector=collect, drive_collector=None, drive_recheck=None, extraction_queue=None):
        self.definitions, self.sources, self.collector = definitions, sources, collector
        self.drive_collector = drive_collector
        self.drive_recheck = drive_recheck
        self.extraction_queue = extraction_queue

    def tick(self):
        service=self.definitions
        service._prune_runs()
        row=service.claim()
        if row is None:return 0
        sources=self.sources.in_space(row['space_id'])
        drive = None
        collect_attachments = row['kind'] == 'website' and bool(row['config'].get('attachments'))
        page_queue = collect_attachments and row['config']['attachments'].get('page_queue', False)
        progress = row['diagnostics']
        awaiting = row['cursor'].get('awaiting_publication', {})
        try:
            handoff = None
            # Finish extraction from the preceding batch before advancing collection.
            with service.database.engine.begin() as c:
                hold_authority(c);content_lock(c);service.fenced(c,row)
                pending=c.execute(text('''SELECT i.*,v.state,v.media_type,v.error_code,v.original_present,v.size_bytes,v.generation,v.job_id,v.content_hash AS version_content_hash,s.revision,s.current_version_id,s.metadata AS source_metadata,
                        j.state AS job_state,r.state AS extraction_state,r.error_code AS extraction_error
                    FROM c0_automatic_source_items i
                    LEFT JOIN c0_source_versions v ON v.id=i.version_id AND v.source_id=i.source_id
                    JOIN c0_sources s ON s.id=i.source_id
                    LEFT JOIN c0_jobs j ON j.id=v.job_id
                    LEFT JOIN c0_extraction_runs r ON r.version_id=v.id AND r.processing_generation=v.generation
                    WHERE i.definition_id=:id'''),{'id':row['id']}).mappings().all()
                for old in pending:
                    if old['revision'] != old['source_revision']:
                        raise UpdateConflict('source_changed')
                    version_id = str(old['version_id'])
                    if old['version_id'] is None:
                        if old['current_version_id'] is not None:
                            raise UpdateConflict('source_changed')
                        continue
                    if old['state'] is None:
                        if not collect_attachments or old['version_id'] == old['current_version_id']:
                            raise UpdateConflict('source_changed')
                    if collect_attachments and terminal_failure(old):
                        if version_id in awaiting:
                            record(progress, awaiting[version_id], 'failed')
                            reason = old['error_code'] or old['extraction_error'] or (
                                'staging_expired' if old['state'] is None else 'source_extraction_failed')
                            record(progress, 'reasons', reason)
                    elif old['state'] == 'failed':
                        raise CollectionError('source_extraction_failed')
                    elif old['state'] != 'ready':
                        if page_queue and old['job_id'] is None and old['extraction_state'] is None:
                            # Resume a durable queue-only stage even after a worker restart.
                            handoff = old
                            break
                        service._finish(c,row,'pending',cursor=row['cursor'])
                        return 1
                    elif old['current_version_id'] != old['version_id']:
                        raise UpdateConflict('source_changed')
                    elif version_id in awaiting:
                        record(progress, awaiting[version_id], 'published')
                if handoff is None:
                    row['cursor'].pop('awaiting_publication', None)
                    if collect_attachments and awaiting:
                        save_progress(c, row, progress)
                        c.execute(text("UPDATE c0_source_update_runs SET cursor=CAST(:cursor AS jsonb) WHERE id=:id"),
                                  {'id': row['run_id'], 'cursor': json.dumps(row['cursor'])})
                if row['kind'] == 'google_drive':
                    drive = service._drive_worker_binding(c, row)
                if handoff is None and row['cursor'].get('collection_complete'):
                    if collect_attachments:
                        progress['reasons'] = {
                            **progress.get('reasons', {}), **row['cursor'].get('attachment_failures', {})}
                        if row['cursor'].get('depth_limited'):
                            record(progress, 'reasons', 'website_link_depth_or_frontier_limit')
                        progress['pending'] = 0
                        save_progress(c, row, progress)
                        incomplete = bool(progress['reasons'])
                        service._finish(c, row, 'partial' if incomplete else 'complete',
                                        'website_collection_incomplete' if incomplete else None, cursor={},
                                        retry_after=row['cursor'].get('attachment_retry_after', ''))
                    else:
                        service._finish(c,row,'complete')
                    return 1
            if handoff is not None:
                self._handoff(row, handoff)
                return 1
            if drive is not None:
                if self.drive_collector is None or self.drive_recheck is None:
                    raise CollectionError('drive_unavailable')
                fetched, cursor, complete = self.drive_collector(drive['credential'], drive['folder_id'], row['cursor'])
                items, checked, parser_failed = self._prepare_drive_items(row, fetched, pending)
                if parser_failed or row['cursor'].get('parser_incomplete'):
                    cursor = {**cursor, 'parser_incomplete': True}
                self.drive_recheck(drive['credential'],drive['folder_id'],checked)
            else:
                options = {'attachment_validator': pdf_validator(sources, pending)} if collect_attachments else {}
                items,cursor,complete=self.collector(row['kind'],row['config'],row['cursor'],**options)
            if row['processed']+len(items)>10000:raise CollectionError('source_run_item_limit')
            with service.database.engine.begin() as c:
                hold_authority(c);content_lock(c);service.fenced(c,row)
                awaiting = {}
                previous = {old['external_key']: old for old in pending}
                for item in items:
                    kind = 'pdf' if item['media_type'] == 'application/pdf' else 'html'
                    if collect_attachments and not item.get('not_modified'):
                        record(progress, kind, 'fetched')
                    old=c.execute(text('''SELECT i.*,v.media_type FROM c0_automatic_source_items i
                        LEFT JOIN c0_source_versions v ON v.id=i.version_id WHERE definition_id=:id AND external_key=:key'''),
                                  {'id':row['id'],'key':item['key']}).mappings().one_or_none()
                    if item.get('not_modified'):
                        if not collect_attachments or not old:
                            raise UpdateConflict('source_changed')
                        saved = sources._source(c, old['source_id'], lock=True)
                        retained = previous[old['external_key']]
                        if (saved['deleted'] or saved['revision'] != old['source_revision']
                                or saved['current_version_id'] != old['version_id'] or old['version_id'] != retained['version_id']
                                or old['content_hash'] != retained['version_content_hash']):
                            raise UpdateConflict('source_changed')
                        try:
                            sources.originals.check({**retained, 'id': retained['version_id']})
                        except ExtractionError:
                            raise CollectionError('website_retained_original_missing') from None
                        record(progress, 'pdf', 'not_modified')
                        record(progress, 'pdf', 'unchanged')
                        continue
                    digest=item['digest'] if drive is not None else hashlib.sha256(item['body']).hexdigest()
                    reindex = drive is not None and old is not None and old['media_type'] != item['media_type']
                    if old:
                        saved=sources._source(c,old['source_id'],lock=True)
                        if saved['deleted'] or saved['revision']!=old['source_revision']:
                            raise UpdateConflict('source_changed')
                        if old['content_hash'] == digest and not reindex:
                            if collect_attachments:
                                old_status = previous[old['external_key']]
                                if terminal_failure(old_status):
                                    if old_status['state'] is not None and old_status['original_present']:
                                        try:
                                            sources.originals.check({**old_status, 'id': old_status['version_id']})
                                        except ExtractionError:
                                            reindex = True
                                        else:
                                            record(progress, kind, 'failed')
                                            record(progress, 'reasons', old_status['error_code'] or old_status['extraction_error'] or 'source_extraction_failed')
                                            continue
                                    else:
                                        reindex = old_status['state'] is not None
                                else:
                                    if kind == 'pdf' and restore_original(c, sources, old_status, item['body'], digest):
                                        record(progress, kind, 'restored_original')
                                    record(progress, kind, 'unchanged')
                                    continue
                            else:
                                if drive is not None and saved['title'] != item['title']:
                                    revision = sources._update_current_metadata(c, saved['id'], item['title'], json.dumps(saved['metadata']))
                                    c.execute(text('''UPDATE c0_automatic_source_items SET source_revision=:revision
                                        WHERE definition_id=:id AND external_key=:key'''),
                                        {'revision':revision,'id':row['id'],'key':item['key']})
                                continue
                    metadata={**item['metadata'],'automatic_source_id':str(row['id']),'external_key':item['key']}
                    if collect_attachments:
                        record(progress, kind, 'changed' if old else 'new')
                        if kind == 'pdf':
                            metadata['collected_at'] = datetime.now(timezone.utc).isoformat()
                    queue_only = page_queue and kind == 'pdf'
                    version=sources._ingest(c,BytesIO(item['body']),title=item['title'],
                        filename=DRIVE_FILENAMES.get(item['media_type'],'source.txt'),
                        media_type=item['media_type'],retain_original=(collect_attachments and kind == 'pdf') or (drive is not None and bool(metadata.get('pdf_textless_pages'))),
                        encoded=json.dumps(metadata),
                        source_id=old['source_id'] if old else None,expected_revision=old['source_revision'] if old else None,
                        force_reindex=reindex,
                        queue_extraction=drive is None and not queue_only)
                    if version['state'] == 'queued':
                        marker = {'_automatic_source_revision': row['revision']}
                        if queue_only:
                            marker['_automatic_attachment_queue'] = True
                        c.execute(text("UPDATE c0_source_versions SET publication_metadata=CAST(publication_metadata AS jsonb) || CAST(:marker AS jsonb) WHERE id=:id"),
                                  {'id': version['id'], 'marker': json.dumps(marker)})
                        if collect_attachments:
                            awaiting[str(version['id'])] = kind
                    elif collect_attachments and old and terminal_failure(previous[old['external_key']]):
                        # The remote server reverted to the still-current complete bytes.
                        retire_versions(c, [old['version_id']])
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
                if collect_attachments:
                    cursor['awaiting_publication'] = awaiting
                    progress['pending'] = len(awaiting) + sum(len(cursor.get(key, ()))
                        for key in ('attachment_pending','pending','inventories'))
                    pdf = progress.setdefault('pdf', {})
                    if cursor.get('attachment_selected'):
                        pdf['selected'] = cursor['attachment_selected']
                    if cursor.get('attachment_failures'):
                        pdf['skipped'] = sum(cursor['attachment_failures'].values())
                    save_progress(c, row, progress)
                # Bound persisted frontiers independently from downloaded bodies.
                if len(json.dumps(cursor).encode())>2*1024*1024:raise CollectionError('source_cursor_limit')
                service.fenced(c,row)
                c.execute(text('UPDATE c0_source_update_runs SET processed=processed+:count WHERE id=:id'),{'id':row['run_id'],'count':len(items)})
                if drive is not None and complete and cursor.get('parser_incomplete'):
                    # All pages were visited. Retry failures from a fresh traversal.
                    service._finish(c, row, 'partial', 'drive_parser_incomplete', cursor={})
                else:
                    service._finish(c,row,'complete' if drive is not None and complete else 'pending',cursor=cursor)
            return 1
        except (UpdateConflict,UpdateNotFound,SourceConflict,SourceNotFound):
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
            transient=code in {'source_dns_timeout','source_dns_unavailable','source_transport_failed','source_http_408','source_http_429','source_http_500','source_http_502','source_http_503','source_http_504','source_run_item_limit','website_collection_budget_stalled','website_retained_original_missing'} or bool(retry_after)
            self._fail(row,'partial' if transient else 'blocked',code,retry_after)
        except Exception:
            self._fail(row,'failed','source_update_failed')
        return 1

    def _handoff(self, row, version):
        failure = None
        retry = False
        try:
            queue = self.extraction_queue() if callable(self.extraction_queue) else self.extraction_queue
            if queue is None:
                raise ValueError('extraction_units_disabled')
            queue.in_space(row['space_id']).enqueue_automatic_attachment(
                version['version_id'], expected_generation=version['generation'])
        except ExtractionError as error:
            failure = error.code
        except (SourceConflict, SourceNotFound):
            raise UpdateConflict('source_changed') from None
        except ValueError as error:
            code = str(error)
            retry = code == 'extraction_queue_full'
            if not retry:
                failure = code if code in ('extraction_units_disabled','extraction_manifest_exceeds_queue_limit') else 'source_extraction_failed'
        service = self.definitions
        with service.database.engine.begin() as connection:
            content_lock(connection)
            service.fenced(connection, row)
            if failure:
                connection.execute(text("""UPDATE c0_source_versions SET state='failed',error_code=:error
                    WHERE id=:id AND generation=:generation AND state='queued' AND job_id IS NULL"""),
                    {'error': failure, 'id': version['version_id'], 'generation': version['generation']})
            service._finish(connection, row, 'pending', cursor=row['cursor'])
            if retry:
                connection.execute(text("UPDATE c0_source_update_runs SET available_at=now()+interval '30 seconds' WHERE id=:id"),
                                   {'id': row['run_id']})

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
        parser_failed = False
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
                    if failure.code in DRIVE_PARSER_FAILURES:
                        parser_failed = True
                        continue
                    if failure.code in SKIPPED_DRIVE_ERRORS:
                        continue
                    raise CollectionError('source_extraction_failed') from None
            ready.append(item)
            checked.append(raw)
        return ready, checked, parser_failed

    def _fail(self,row,state,code,retry_after=''):
        with self.definitions.database.engine.begin() as c:
            c.execute(text('SELECT id FROM c0_automatic_sources WHERE id=:id FOR UPDATE'), {'id':row['id']})
            current=c.execute(text('SELECT lease,state,lease_until>clock_timestamp() AS lease_current FROM c0_source_update_runs WHERE id=:id FOR UPDATE'),{'id':row['run_id']}).mappings().one_or_none()
            if current and current['state']=='running' and current['lease']==row['lease'] and current['lease_current']:
                self.definitions._finish(c,row,state,code,retry_after=retry_after)
