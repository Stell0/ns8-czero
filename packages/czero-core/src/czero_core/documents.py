# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Complete evidence readers over sources and verified immutable part snapshots.

Project snapshots are an existing storage adapter, not an authorization boundary.
Every lookup is restricted to the selected space and current Reader authority.
"""
import hashlib
import json

from sqlalchemy import text

from .sources import SourceConflict, SourceNotFound, SourceService, _uuid
from .spaces import SpaceBound, hold_authority

SNAPSHOT = 'c0_project_source_snapshot_v1'
HISTORY = 'c0_project_source_snapshot_history_v1'
RECEIPT = 'c0_project_source_sync_history_v1'
MAX_DOCUMENT_BYTES = 16777216  # Existing parent-snapshot ceiling, not an extraction-limit increase.


def _hash(body):
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


class DocumentService(SpaceBound):
    """Stable logical identities, bounded discovery and immutable full-body reads."""
    def __init__(self, database, access):
        self.database, self.access = database, access

    def _authorize(self, connection, actor):
        hold_authority(connection)
        return self._space_authorize(connection, actor)

    def _source(self, connection, identifier):
        return connection.execute(text('SELECT * FROM c0_sources WHERE space_id=:space AND id=:id'),
            {'space':self._space(connection),'id':_uuid(identifier)}).mappings().one_or_none()

    def _object(self, connection, identifier, kind):
        return connection.execute(text('SELECT * FROM c0_objects WHERE space_id=:space AND id=:id AND type_name=:type'),
            {'space':self._space(connection),'id':_uuid(identifier),'type':kind}).mappings().one_or_none()

    def browse_documents(self, actor, *, limit=50, offset=0):
        """Summaries only; source parts appear once under their verified parent."""
        # Keep UUID columns indexable; managed receipt IDs are validated UUIDs.
        SourceService._page(limit, offset)
        with self.database.engine.begin() as connection:
            self._authorize(connection, actor)
            rows = connection.execute(text('''WITH parents AS MATERIALIZED (
                SELECT id,data,space_id,updated_at,created_at FROM c0_objects WHERE space_id=:space AND type_name=:snapshot
            ), summaries AS (
                SELECT s.id,s.title,s.metadata,s.updated_at,COALESCE(v.state,'queued') AS state,
                    COALESCE(v.media_type,'text/plain') AS media_type,false AS multipart,s.created_at AS sort_at
                FROM c0_sources s LEFT JOIN LATERAL (
                    SELECT state,media_type FROM c0_source_versions WHERE space_id=s.space_id AND source_id=s.id
                    ORDER BY number DESC LIMIT 1
                ) v ON true WHERE s.space_id=:space AND NOT s.deleted AND NOT EXISTS (
                    SELECT 1 FROM c0_objects receipt WHERE receipt.space_id=s.space_id
                    AND receipt.type_name IN (:receipt,:current_receipt)
                    AND receipt.data->>'source_id'=s.id::text
                )
                UNION ALL
                SELECT p.id,COALESCE(s.title,p.data->>'external_id'),COALESCE(s.metadata,'{}'::jsonb),p.updated_at,
                    CASE WHEN v.state='ready' THEN 'ready' ELSE 'incomplete' END,
                    COALESCE(v.media_type,'text/plain'),true,p.created_at
                FROM parents p LEFT JOIN c0_objects r ON r.space_id=p.space_id AND r.type_name=:receipt
                    AND r.id=CAST(p.data->'part_receipt_ids'->>0 AS uuid)
                LEFT JOIN c0_source_versions v ON v.space_id=p.space_id AND v.id=CAST(r.data->>'version_id' AS uuid)
                    AND v.source_id=CAST(r.data->>'source_id' AS uuid)
                LEFT JOIN c0_sources s ON s.space_id=p.space_id AND s.id=v.source_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(p.data->'part_receipt_ids') part(id)
                    JOIN c0_objects receipt ON receipt.id=CAST(part.id AS uuid) AND receipt.space_id=p.space_id AND receipt.type_name=:receipt
                    JOIN c0_sources original ON original.id=CAST(receipt.data->>'source_id' AS uuid) AND original.space_id=p.space_id
                    WHERE original.deleted
                )
            ) SELECT id,title,metadata,updated_at,state,media_type,multipart FROM summaries ORDER BY sort_at DESC,id LIMIT :limit OFFSET :offset'''),
                {'space':self._space(connection),'snapshot':SNAPSHOT,'receipt':RECEIPT,'current_receipt':'c0_project_source_sync_v1','limit':limit,'offset':offset}).mappings()
            return [dict(row) for row in rows]

    def document_history(self, actor, identifier, *, limit=50, offset=0):
        SourceService._page(limit, offset)
        with self.database.engine.begin() as connection:
            self._authorize(connection, actor)
            source = self._source(connection, identifier)
            if source:
                rows = connection.execute(text('''SELECT id AS revision_id,number,created_at,state,content_hash
                    FROM c0_source_versions WHERE space_id=:space AND source_id=:id
                    ORDER BY number DESC LIMIT :limit OFFSET :offset'''),
                    {'space':self._space(connection),'id':source['id'],'limit':limit,'offset':offset}).mappings()
            else:
                parent = self._object(connection, identifier, SNAPSHOT)
                if not parent:raise SourceNotFound()
                rows = connection.execute(text('''SELECT id AS revision_id,created_at,'ready' AS state,
                    data->>'content_hash' AS content_hash FROM c0_objects
                    WHERE space_id=:space AND type_name=:type AND data @> CAST(:identity AS jsonb)
                    ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset'''),
                    {'space':self._space(connection),'type':HISTORY,'identity':json.dumps({k:parent['data'][k] for k in ('connector_id','external_id')}),
                     'limit':limit,'offset':offset}).mappings()
            return [dict(row) for row in rows]

    def read_document(self, actor, identifier, *, revision_id=None):
        with self.database.engine.begin() as connection:
            self._authorize(connection, actor)
            return self._read(connection, identifier, revision_id=revision_id)

    def _read(self, connection, identifier, *, revision_id=None):
        source = self._source(connection, identifier)
        if source:
            single=self._single(connection,source,revision_id)
            return self._containing(connection,single['revision_id'],single=single)
        parent = self._object(connection, identifier, SNAPSHOT)
        if not parent:raise SourceNotFound()
        selected = self._object(connection, revision_id, HISTORY) if revision_id else parent
        if not selected:raise SourceNotFound()
        for key in ('connector_id','external_id'):
            if selected['data'].get(key)!=parent['data'].get(key):raise SourceNotFound()
        if not revision_id:
            history = connection.execute(text('''SELECT id FROM c0_objects WHERE space_id=:space
                AND type_name=:type AND data @> CAST(:identity AS jsonb) LIMIT 2'''),
                {'space':self._space(connection),'type':HISTORY,'identity':json.dumps({k:selected['data'][k] for k in ('connector_id','external_id','content_hash')})}).scalars().all()
            if len(history)!=1:raise SourceConflict()
            revision_id = history[0]
        return self._composite(connection, parent, selected, _uuid(revision_id))

    def _single(self, connection, source, revision_id):
        version = connection.execute(text('''SELECT v.*,d.id AS document_id,d.text_hash,
            CASE WHEN octet_length(d.body)<=:maximum THEN d.body END AS body
            FROM c0_source_versions v LEFT JOIN c0_documents d ON d.space_id=v.space_id AND d.version_id=v.id
            WHERE v.space_id=:space AND v.source_id=:source AND (CAST(:id AS uuid) IS NULL OR v.id=CAST(:id AS uuid))
            ORDER BY (v.state='ready') DESC,v.number DESC LIMIT 1'''),
            {'space':self._space(connection),'source':source['id'],'id':_uuid(revision_id) if revision_id else None,
             'maximum':MAX_DOCUMENT_BYTES}).mappings().one_or_none()
        if not version:raise SourceNotFound()
        ready=version['state']=='ready' and version['document_id'] is not None
        body=version['body'] if ready else None
        if ready and (body is None or _hash(body)!=version['text_hash']):raise SourceConflict()
        part={'source_id':source['id'],'version_id':version['id'],'document_id':version['document_id'],
            'start_byte':0,'end_byte':len(body.encode()) if body is not None else 0,
            'start_offset':0,'end_offset':len(body) if body is not None else 0,
            'content_hash':version['content_hash'],'text_hash':version['text_hash']}
        return {'id':source['id'],'revision_id':version['id'],'title':source['title'],
            'metadata':source['metadata'],'media_type':version['media_type'],'updated_at':version['created_at'],
            'state':version['state'] if not ready else 'ready','body':body,'text_hash':version['text_hash'],
            'content_hash':version['content_hash'],'parts':[part] if ready else [],'multipart':False,
            'deleted':source['deleted'],'number':version['number'],'error_code':version['error_code'],
            'original_version_ids':[version['id']] if version['original_present'] and (version['retain_original'] or version['state']=='failed') else []}

    def _composite(self, connection, parent, selected, revision_id):
        data=selected['data'];ids=data.get('part_receipt_ids')
        if (not isinstance(ids,list) or not 1<=len(ids)<=100 or len(set(ids))!=len(ids)
                or type(data.get('total_bytes')) is not int or not 1<=data['total_bytes']<=MAX_DOCUMENT_BYTES):
            raise SourceConflict()
        for identifier in ids:_uuid(identifier)
        rows = list(connection.execute(text('''SELECT r.id,r.data,v.id AS version_id,v.source_id,v.state,v.media_type,
            v.content_hash,v.size_bytes,v.original_present,v.retain_original,d.id AS document_id,d.text_hash,
            CASE WHEN sum(octet_length(d.body)) OVER()<=:maximum THEN d.body END AS body,
            s.title,s.metadata,s.deleted
            FROM c0_objects r
            LEFT JOIN c0_source_versions v ON v.space_id=r.space_id AND v.id::text=r.data->>'version_id'
                AND v.source_id::text=r.data->>'source_id'
            LEFT JOIN c0_documents d ON d.space_id=r.space_id AND d.version_id=v.id
            LEFT JOIN c0_sources s ON s.space_id=r.space_id AND s.id=v.source_id
            WHERE r.space_id=:space AND r.type_name=:type AND r.id=ANY(CAST(:ids AS uuid[]))'''),
            {'space':self._space(connection),'type':RECEIPT,'ids':ids,'maximum':MAX_DOCUMENT_BYTES}).mappings())
        result={'id':parent['id'],'revision_id':revision_id,'title':data['external_id'],'metadata':{},
            'media_type':'text/plain','updated_at':selected['updated_at'],'state':'incomplete','body':None,
            'text_hash':None,'content_hash':data['content_hash'],'parts':[],'multipart':True,'deleted':False,
            'number':None,'error_code':'missing_or_unready_part','original_version_ids':[]}
        if len(rows)!=len(ids) or any(row['state']!='ready' or row['document_id'] is None for row in rows):return result
        rows.sort(key=lambda row:row['data'].get('part_number',0))
        bodies=[];parts=[];byte_offset=0;offset=0;media=rows[0]['media_type']
        for number,row in enumerate(rows,1):
            receipt=row['data'];body=row['body']
            legacy=False
            if receipt.get('parent_content_hash')!=data['content_hash']:
                from .projects import logical_key
                identity=receipt.get('connector_id','')+':'+receipt.get('external_id','')+':'+str(row['version_id'])
                legacy=receipt.get('key')==logical_key('source_sync_history_v1',identity)
            if (receipt.get('connector_id')!=data['connector_id'] or receipt.get('parent_external_id')!=data['external_id']
                    or (receipt.get('parent_content_hash')!=data['content_hash'] and not legacy) or receipt.get('sync_status')!='verified'
                    or receipt.get('extraction_status')!='ready' or receipt.get('part_number')!=number
                    or (not legacy and receipt.get('start_byte')!=byte_offset) or row['media_type']!=media
                    or receipt.get('last_content_hash')!=row['content_hash'] or body is None or _hash(body)!=row['text_hash']):
                raise SourceConflict()
            raw_size=len(body.encode()) if media in ('text/plain','text/markdown') else row['size_bytes']
            if receipt.get('end_byte')!=receipt.get('start_byte',0)+raw_size:raise SourceConflict()
            if legacy:
                # Old writers reused immutable receipt versions across parents.
                # Explicit snapshot membership plus the full hash verifies the
                # reconstructed offsets, without borrowing mutable current rows.
                result['metadata']['legacy_receipt_reconstruction']=True
            if media in ('text/plain','text/markdown'):
                if _hash(body)!=row['content_hash']:raise SourceConflict()
            elif len(rows)!=1 or row['content_hash']!=data['content_hash']:raise SourceConflict()
            parts.append({'source_id':row['source_id'],'version_id':row['version_id'],'document_id':row['document_id'],
                'start_byte':byte_offset,'end_byte':byte_offset+raw_size,'start_offset':offset,'end_offset':offset+len(body),
                'content_hash':row['content_hash'],'text_hash':row['text_hash']})
            byte_offset+=raw_size;offset+=len(body);bodies.append(body)
            if row['original_present'] and row['retain_original']:result['original_version_ids'].append(row['version_id'])
        body=''.join(bodies)
        if byte_offset!=data['total_bytes'] or (media in ('text/plain','text/markdown') and _hash(body)!=data['content_hash']):
            raise SourceConflict()
        result.update(title=rows[0]['title'],metadata={**rows[0]['metadata'],**result['metadata']},media_type=media,state='ready',
            body=body,text_hash=_hash(body),parts=parts,deleted=any(row['deleted'] for row in rows),error_code=None)
        # Current source metadata is immutable; immutable receipt provenance describes this snapshot.
        provenance=rows[0]['data'].get('provenance',{})
        if provenance:result['metadata']={**result['metadata'],'snapshot_provenance':provenance}
        return result

    def containing_document(self, actor, version_id):
        """Resolve an old part link to a snapshot containing that exact version."""
        with self.database.engine.begin() as connection:
            self._authorize(connection, actor)
            return self._containing(connection,version_id)

    def _containing(self, connection, version_id, *, single=None):
        version=connection.execute(text('SELECT source_id FROM c0_source_versions WHERE space_id=:space AND id=:id'),
            {'space':self._space(connection),'id':_uuid(version_id)}).mappings().one_or_none()
        if not version:raise SourceNotFound()
        identity=json.dumps({'version_id':str(version_id),'source_id':str(version['source_id'])})
        rows=connection.execute(text('''SELECT p.id,h.id AS revision_id FROM c0_objects r
            JOIN c0_objects h ON h.space_id=r.space_id AND h.type_name=:history
                AND h.data->'part_receipt_ids' @> jsonb_build_array(r.id::text)
                AND h.data->>'connector_id'=r.data->>'connector_id'
                AND h.data->>'external_id'=r.data->>'parent_external_id'
            JOIN c0_objects p ON p.space_id=h.space_id AND p.type_name=:snapshot
                AND p.data->>'connector_id'=h.data->>'connector_id' AND p.data->>'external_id'=h.data->>'external_id'
            WHERE r.space_id=:space AND r.type_name=:receipt AND r.data @> CAST(:identity AS jsonb)
            ORDER BY h.created_at DESC,h.id DESC LIMIT 2'''),
            {'space':self._space(connection),'history':HISTORY,'snapshot':SNAPSHOT,'receipt':RECEIPT,'identity':identity}).mappings().all()
        if rows:return self._read(connection,rows[0]['id'],revision_id=rows[0]['revision_id'])
        result=single or self._single(connection,self._source(connection,version['source_id']),version_id)
        part=connection.execute(text('''SELECT id FROM c0_objects WHERE space_id=:space
            AND type_name IN (:current,:history) AND data @> CAST(:identity AS jsonb) LIMIT 1'''),
            {'space':self._space(connection),'current':'c0_project_source_sync_v1','history':RECEIPT,'identity':identity}).scalar_one_or_none()
        if part is not None:
            result.update(state='incomplete',body=None,parts=[],text_hash=None,error_code='unverified_parent_snapshot')
        return result
