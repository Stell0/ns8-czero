# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Short fenced publication transactions; collection never holds database locks."""
import hashlib
from io import BytesIO
import json
import re

from sqlalchemy import text
from .automatic_sources import UpdateConflict, UpdateNotFound
from .identity import PermissionDenied
from .source_collectors import collect
from .source_http import CollectionError
from .current_content import content_lock
from .spaces import hold_authority


class SourceUpdater:
    def __init__(self, definitions, sources, *, collector=collect):
        self.definitions, self.sources, self.collector = definitions, sources, collector

    def tick(self):
        service=self.definitions
        service._prune_runs()
        row=service.claim()
        if row is None:return 0
        sources=self.sources.in_space(row['space_id'])
        try:
            # Finish extraction from the preceding batch before advancing collection.
            with service.database.engine.begin() as c:
                hold_authority(c);content_lock(c);service.fenced(c,row)
                pending=c.execute(text('''SELECT i.*,v.state,s.revision,s.current_version_id FROM c0_automatic_source_items i
                    LEFT JOIN c0_source_versions v ON v.id=i.version_id AND v.source_id=i.source_id JOIN c0_sources s ON s.id=i.source_id
                    WHERE i.definition_id=:id'''),{'id':row['id']}).mappings().all()
                if any(v['state'] is None for v in pending):raise UpdateConflict('source_changed')
                if any(v['state']=='failed' for v in pending):raise CollectionError('source_extraction_failed')
                if any(v['state']!='ready' for v in pending):
                    service._finish(c,row,'pending',cursor=row['cursor']);return 1
                for old in pending:
                    if old['current_version_id']!=old['version_id']:raise UpdateConflict('source_changed')
                    # Extraction cannot authorize intervening manual changes.
                    if old['revision'] != old['source_revision']:raise UpdateConflict('source_changed')
            if row['cursor'].get('collection_complete'):
                with service.database.engine.begin() as c:
                        hold_authority(c);content_lock(c);service.fenced(c,row);service._finish(c,row,'complete')
                return 1
            items,cursor,complete=self.collector(row['kind'],row['config'],row['cursor'])
            if row['processed']+len(items)>10000:raise CollectionError('source_run_item_limit')
            with service.database.engine.begin() as c:
                hold_authority(c);content_lock(c);service.fenced(c,row)
                for item in items:
                    old=c.execute(text('SELECT * FROM c0_automatic_source_items WHERE definition_id=:id AND external_key=:key'),
                                  {'id':row['id'],'key':item['key']}).mappings().one_or_none()
                    digest=hashlib.sha256(item['body']).hexdigest()
                    if old:
                        saved=sources._source(c,old['source_id'],lock=True)
                        if saved['deleted'] or saved['revision']!=old['source_revision']:
                            raise UpdateConflict('source_changed')
                        if old['content_hash']==digest:continue
                    metadata={**item['metadata'],'automatic_source_id':str(row['id']),'external_key':item['key']}
                    version=sources._ingest(c,BytesIO(item['body']),title=item['title'],
                        filename='source.md' if item['media_type']=='text/markdown' else 'source.txt',
                        media_type=item['media_type'],retain_original=False,encoded=json.dumps(metadata),
                        source_id=old['source_id'] if old else None,expected_revision=old['source_revision'] if old else None)
                    revision=sources._source(c,version['source_id'])['revision']
                    c.execute(text('''INSERT INTO c0_automatic_source_items(definition_id,external_key,source_id,source_revision,version_id,content_hash)
                        VALUES (:id,:key,:source,:revision,:version,:hash) ON CONFLICT(definition_id,external_key) DO UPDATE
                        SET source_revision=EXCLUDED.source_revision,version_id=EXCLUDED.version_id,content_hash=EXCLUDED.content_hash'''),
                        {'id':row['id'],'key':item['key'],'source':version['source_id'],'revision':revision,'version':version['id'],'hash':digest})
                cursor={**cursor,'collection_complete':complete}
                # Bound persisted frontiers independently from downloaded bodies.
                if len(json.dumps(cursor).encode())>2*1024*1024:raise CollectionError('source_cursor_limit')
                service.fenced(c,row)
                c.execute(text('UPDATE c0_source_update_runs SET processed=processed+:count WHERE id=:id'),{'id':row['run_id'],'count':len(items)})
                service._finish(c,row,'pending',cursor=cursor)
            return 1
        except (UpdateConflict,UpdateNotFound):
            self._fail(row,'blocked','source_changed')
        except PermissionDenied:
            self._fail(row,'blocked','authority_changed')
        except CollectionError as error:
            code=str(error) if re.fullmatch('[a-z][a-z0-9_]{0,63}',str(error)) else 'collection_incomplete'
            retry_after=getattr(error,'retry_after','')
            transient=code in {'source_dns_timeout','source_dns_unavailable','source_transport_failed','source_http_408','source_http_429','source_http_500','source_http_502','source_http_503','source_http_504','source_run_item_limit'} or bool(retry_after)
            self._fail(row,'partial' if transient else 'blocked',code,retry_after)
        except Exception:
            self._fail(row,'failed','source_update_failed')
        return 1

    def _fail(self,row,state,code,retry_after=''):
        with self.definitions.database.engine.begin() as c:
            c.execute(text('SELECT id FROM c0_automatic_sources WHERE id=:id FOR UPDATE'), {'id':row['id']})
            current=c.execute(text('SELECT lease,state,lease_until>clock_timestamp() AS lease_current FROM c0_source_update_runs WHERE id=:id FOR UPDATE'),{'id':row['run_id']}).mappings().one_or_none()
            if current and current['state']=='running' and current['lease']==row['lease'] and current['lease_current']:
                self.definitions._finish(c,row,state,code,retry_after=retry_after)
