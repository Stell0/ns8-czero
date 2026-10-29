# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared evidence operations; originals are separate from current extracted text."""
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import stat
from uuid import UUID, uuid4, uuid5

from sqlalchemy import text

from .extraction import MEDIA_TYPES, MAX_UPLOAD, ExtractionError, extract_isolated, chunks
from .identity import PermissionDenied, Role
from .spaces import SpaceBound, SpaceService, content_row, hold_authority
from .jobs import Handler, JobService, bounded_json
from .receipts import mutate

MAX_INGEST_TEXT_BYTES = 131072
TEXT_MEDIA_TYPES = frozenset(('text/plain', 'text/markdown'))


class SourceConflict(ValueError):
    def __init__(self):
        super().__init__('source_conflict')


class SourceNotFound(ValueError):
    def __init__(self):
        super().__init__('source_not_found')


def _uuid(value):
    try:
        return value if isinstance(value, UUID) else UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('invalid_reference') from None


def _label(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError('invalid_label')
    return value.strip()


def _payload(value):
    if not isinstance(value, dict) or set(value) != {'version_id'}:
        raise ValueError('invalid_payload')
    return {'version_id': str(_uuid(value['version_id']))}


def _metadata(value):
    encoded = bounded_json(value)
    pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if any(not isinstance(key, str) for key in node):
                raise ValueError('invalid_metadata')
            pending.extend(node.keys())
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
        elif isinstance(node, str) and '\0' in node:
            raise ValueError('invalid_metadata')
    return encoded


def version_view(row):
    value=content_row(row)
    value.pop('publication_title',None)
    value.pop('publication_metadata',None)
    return value


class OriginalStore:
    """Only generated UUID names; untrusted display filenames never become paths."""
    def __init__(self, root):
        self.root = Path(root)

    def _prepare(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError('invalid_source_directory')
        self.root.chmod(0o700)

    def path(self, version_id):
        self._prepare()
        return self.root / _uuid(version_id).hex

    def write(self, version_id, stream):
        target = self.path(version_id)
        staging = self.root / ('.' + _uuid(version_id).hex)
        digest = hashlib.sha256()
        size = 0
        try:
            with staging.open('xb') as output:
                os.chmod(staging, 0o600)
                while True:
                    part = stream.read(65536)
                    if not part:
                        break
                    if not isinstance(part, bytes):
                        raise ValueError('invalid_upload')
                    size += len(part)
                    if size > MAX_UPLOAD:
                        raise ExtractionError('too_large')
                    digest.update(part)
                    output.write(part)
                if not size:
                    raise ValueError('empty_upload')
                output.flush()
                os.fsync(output.fileno())
            os.replace(staging, target)
            self._sync()
            return digest.hexdigest(), size
        finally:
            staging.unlink(missing_ok=True)

    def _sync(self):
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def check(self, version):
        path = self.path(version['id'])
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size != version['size_bytes']:
                raise ExtractionError('invalid_file')
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != version['content_hash']:
                raise ExtractionError('invalid_file')
        except OSError:
            raise ExtractionError('invalid_file') from None
        return path

    def remove(self, version_id):
        self.path(version_id).unlink(missing_ok=True)
        (self.root / ('.'+_uuid(version_id).hex)).unlink(missing_ok=True)
        self._sync()


class SourceService(SpaceBound):
    def __init__(self, database, access, registry, originals):
        self.database, self.access = database, access
        self.originals = originals
        self.jobs = JobService(database, registry)

    def _authorize(self, connection, actor, role=Role.READER):
        return self._space_authorize(connection, actor, role)

    @staticmethod
    def _page(limit, offset):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 100000:
            raise ValueError('invalid_page')

    def _source(self, connection, source_id, *, lock=False):
        row = connection.execute(text('SELECT * FROM c0_sources WHERE space_id=:space AND id=:id' + (' FOR UPDATE' if lock else '')),
            {'space': self._space(connection), 'id': _uuid(source_id)}).mappings().one_or_none()
        if row is None:
            raise SourceNotFound()
        return content_row(row)

    def ingest(self, actor, stream, *, title, filename, media_type, retain_original=False,
               metadata=None, source_id=None, expected_revision=None):
        title, filename = _label(title, 256), _label(filename, 255)
        if media_type not in MEDIA_TYPES or type(retain_original) is not bool:
            raise ValueError('invalid_upload')
        encoded = _metadata({} if metadata is None else metadata)
        with self.database.engine.begin() as connection:
            hold_authority(connection)
            self._authorize(connection, actor, Role.EDITOR)
            return self._ingest(connection, stream, title=title, filename=filename,
                media_type=media_type, retain_original=retain_original, encoded=encoded,
                source_id=source_id, expected_revision=expected_revision)

    def ingest_text(self, actor, *, idempotency_key, title, body, media_type='text/plain',
                    metadata=None, source_id=None, expected_revision=None):
        """Submit bounded text to the staged current-content evidence pipeline.

        The receipt is the original submission snapshot; poll versions for current
        extraction state. Superseded receipts return an explicit unavailable outcome.
        """
        if not isinstance(body, str) or not body.strip() or '\0' in body or len(body) > MAX_INGEST_TEXT_BYTES:
            raise ValueError('invalid_source_text')
        title = _label(title, 256)
        try:
            content = body.encode('utf-8')
            title.encode('utf-8')
        except UnicodeError:
            raise ValueError('invalid_source_text') from None
        if len(content) > MAX_INGEST_TEXT_BYTES or not isinstance(media_type, str) or media_type not in TEXT_MEDIA_TYPES:
            raise ValueError('invalid_source_text')
        # Normalize JSON containers before the shared NUL/UTF-8/size checks.
        encoded = _metadata(json.loads(bounded_json({} if metadata is None else metadata)))
        source_id = None if source_id is None else _uuid(source_id)
        if ((source_id is None and expected_revision is not None)
                or (source_id is not None and (type(expected_revision) is not int
                    or not 1 <= expected_revision < 2147483647))):
            raise ValueError('invalid_revision')
        payload = {'title': title, 'content_hash': hashlib.sha256(content).hexdigest(),
            'media_type': media_type, 'metadata': json.loads(encoded),
            'source_id': str(source_id) if source_id else None, 'expected_revision': expected_revision}
        def execute(connection, current):
            return self._ingest(connection, BytesIO(content), title=title,
                filename='evidence.md' if media_type == 'text/markdown' else 'evidence.txt',
                media_type=media_type, retain_original=False, encoded=encoded,
                source_id=source_id, expected_revision=expected_revision)
        return mutate(self.database, self._authorize, actor, 'source.ingest_text', payload,
                      idempotency_key, execute, conflict=SourceConflict)

    def _ingest(self, connection, stream, *, title, filename, media_type,
                retain_original, encoded, source_id, expected_revision):
        """Trusted writer; callers own validation, authorization and transaction."""
        from .current_content import content_lock,retire_versions
        content_lock(connection)
        version_id = uuid4()
        if source_id is None:
            if expected_revision is not None:
                raise ValueError('invalid_revision')
        else:
            source = self._source(connection, source_id, lock=True)
            if source['deleted'] or type(expected_revision) is not int or source['revision'] != expected_revision:
                raise SourceConflict()
        # On uncertain database COMMIT failure, keep the original. Do not
        # remove a possibly committed version's only recoverable evidence.
        # A separately committed, delayed deletion intent covers rollback/crash
        # between the file write and version COMMIT. GC takes the writer lock.
        with self.database.engine.begin() as intent:
            intent.execute(text("INSERT INTO c0_original_cleanup(version_id,space_id,available_at) VALUES (:id,:space,now()+interval '1 hour')"),
                {'id':version_id,'space':self._space(connection)})
        digest, size = self.originals.write(version_id, stream)
        if source_id is None:
            # Identical first uploads with the same provenance deduplicate,
            # including concurrent deliveries. Different provenance stays
            # a separate source; changed bytes require explicit versioning.
            ingest_key = hashlib.sha256(json.dumps([title, encoded, media_type, digest], ensure_ascii=False).encode()).hexdigest()
            source = connection.execute(text('''INSERT INTO c0_sources(space_id,id,ingest_key,title,metadata)
                VALUES (:space,:id,:key,:title,CAST(:metadata AS jsonb))
                ON CONFLICT(space_id,ingest_key) DO UPDATE SET ingest_key=EXCLUDED.ingest_key RETURNING *'''),
                {'space': self._space(connection), 'id': uuid4(), 'key': ingest_key, 'title': title, 'metadata': encoded}).mappings().one()
            source_id = source['id']
            if source['deleted']:
                self.originals.remove(version_id)
                raise SourceConflict()
        existing = connection.execute(text('SELECT * FROM c0_source_versions WHERE source_id=:source AND content_hash=:hash ORDER BY number DESC LIMIT 1'),
            {'source': source_id, 'hash': digest}).mappings().one_or_none()
        if existing:
            self.originals.remove(version_id)
            connection.execute(text('DELETE FROM c0_original_cleanup WHERE version_id=:id'),{'id':version_id})
            if existing['media_type'] != media_type or existing['retain_original'] != retain_original:
                raise SourceConflict()
            if existing['id']==source['current_version_id'] and (source['title']!=title or source['metadata']!=json.loads(encoded)):
                connection.execute(text('UPDATE c0_sources SET title=:title,metadata=CAST(:metadata AS jsonb),revision=revision+1,updated_at=now() WHERE id=:id'),
                    {'id':source_id,'title':title,'metadata':encoded})
            elif existing['id']!=source['current_version_id'] and (existing['publication_title']!=title or existing['publication_metadata']!=json.loads(encoded)):
                connection.execute(text('UPDATE c0_source_versions SET publication_title=:title,publication_metadata=CAST(:metadata AS jsonb) WHERE id=:id'),
                    {'id':existing['id'],'title':title,'metadata':encoded})
                connection.execute(text('UPDATE c0_sources SET revision=revision+1,updated_at=now() WHERE id=:id'),{'id':source_id})
            return version_view(existing)
        # Bound abandoned replacements; current publication remains protected.
        pending=connection.execute(text('SELECT id FROM c0_source_versions WHERE source_id=:source AND id IS DISTINCT FROM CAST(:current AS uuid)'),
            {'source':source_id,'current':source['current_version_id']}).scalars().all()
        retire_versions(connection,pending)
        number=connection.execute(text('UPDATE c0_sources SET next_version_number=next_version_number+1 WHERE id=:id RETURNING next_version_number-1'),{'id':source_id}).scalar_one()
        job = self.jobs._enqueue(connection, 'source.extract', {'version_id': str(version_id)},
            'source:' + str(version_id) + ':extract:1', space_id=self._space(connection))
        row = connection.execute(text('''INSERT INTO c0_source_versions
            (space_id,id,source_id,number,filename,media_type,content_hash,size_bytes,retain_original,job_id,publication_title,publication_metadata)
            VALUES (:space,:id,:source,:number,:filename,:media,:hash,:size,:retain,:job,:title,CAST(:metadata AS jsonb)) RETURNING *'''),
            {'space': self._space(connection), 'id': version_id, 'source': source_id, 'number': number, 'filename': filename,
             'media': media_type, 'hash': digest, 'size': size, 'retain': retain_original, 'job': job['id'],'title':title,'metadata':encoded}).mappings().one()
        if number > 1:
            connection.execute(text('UPDATE c0_sources SET revision=revision+1,updated_at=now() WHERE id=:id'), {'id': source_id})
        connection.execute(text('DELETE FROM c0_original_cleanup WHERE version_id=:id'),{'id':version_id})
        return version_view(row)

    def list(self, actor, *, limit=50, offset=0, include_deleted=False, external_key=None):
        self._page(limit, offset)
        if type(include_deleted) is not bool:
            raise ValueError('invalid_filter')
        if external_key is not None:external_key=_label(external_key,128)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return [content_row(row) for row in connection.execute(text('''SELECT * FROM c0_sources
                WHERE space_id=:space AND (:deleted OR NOT deleted) AND (CAST(:external AS text) IS NULL OR metadata->>'external_key'=:external)
                ORDER BY created_at DESC,id LIMIT :limit OFFSET :offset'''),
                {'space': self._space(connection), 'deleted': include_deleted,'external':external_key,'limit': limit, 'offset': offset}).mappings()]

    def get(self, actor, source_id):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return self._source(connection, source_id)

    def versions(self, actor, source_id, *, limit=50, offset=0):
        self._page(limit, offset)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            self._source(connection, source_id)
            return [version_view(row) for row in connection.execute(text('''SELECT v.*,j.state AS job_state
                FROM c0_source_versions v LEFT JOIN c0_jobs j ON j.id=v.job_id
                WHERE v.space_id=:space AND v.source_id=:id ORDER BY v.number DESC LIMIT :limit OFFSET :offset'''),
                {'space': self._space(connection), 'id': _uuid(source_id), 'limit': limit, 'offset': offset}).mappings()]

    def retry(self, actor, version_id, *, expected_generation):
        with self.database.engine.begin() as connection:
            hold_authority(connection)
            self._authorize(connection, actor, Role.EDITOR)
            row = connection.execute(text('''SELECT v.*,j.state AS job_state FROM c0_source_versions v
                LEFT JOIN c0_jobs j ON j.id=v.job_id WHERE v.space_id=:space AND v.id=:id FOR UPDATE OF v'''),
                {'space': self._space(connection), 'id': _uuid(version_id)}).mappings().one_or_none()
            if row is None:
                raise SourceNotFound()
            if (type(expected_generation) is not int or expected_generation != row['generation']
                or row['state'] == 'ready' or (row['state'] == 'queued' and row['job_state'] in ('queued','running'))):
                raise SourceConflict()
            self.originals.check(row)
            generation = row['generation'] + 1
            job = self.jobs._enqueue(connection, 'source.extract', {'version_id': str(row['id'])},
                'source:' + str(row['id']) + ':extract:' + str(generation), space_id=self._space(connection))
            return version_view(connection.execute(text('''UPDATE c0_source_versions SET state='queued',error_code=NULL,
                generation=:generation,job_id=:job WHERE id=:id RETURNING *'''),
                {'id': row['id'], 'generation': generation, 'job': job['id']}).mappings().one())

    def delete(self, actor, source_id, *, expected_revision):
        with self.database.engine.begin() as connection:
            hold_authority(connection)
            self._authorize(connection, actor, Role.EDITOR)
            row = self._source(connection, source_id, lock=True)
            if type(expected_revision) is not int or row['revision'] != expected_revision:
                raise SourceConflict()
            if not row['deleted']:
                row = content_row(connection.execute(text('''UPDATE c0_sources SET deleted=true,
                    revision=revision+1,updated_at=now() WHERE id=:id RETURNING *'''), {'id': row['id']}).mappings().one())
            return row

    def document(self, actor, version_id):
        with self.database.engine.connect() as connection:
            current=self._authorize(connection, actor)
            self._read_version(connection,current,version_id)
            row = connection.execute(text('SELECT * FROM c0_documents WHERE space_id=:space AND version_id=:id'),
                {'space': self._space(connection), 'id': _uuid(version_id)}).mappings().one_or_none()
            if row is None:
                raise SourceNotFound()
            return content_row(row)

    def original(self, actor, version_id):
        with self.database.engine.connect() as connection:
            current=self._authorize(connection, actor)
            self._read_version(connection,current,version_id)
            row = connection.execute(text('SELECT * FROM c0_source_versions WHERE space_id=:space AND id=:id'),
                {'space': self._space(connection), 'id': _uuid(version_id)}).mappings().one_or_none()
            if row is None or not row['original_present'] or not (row['retain_original'] or row['state'] == 'failed'):
                raise SourceNotFound()
            return self.originals.check(row), content_row(row)

    def chunks(self, actor, document_id, *, limit=50, offset=0):
        self._page(limit, offset)
        with self.database.engine.connect() as connection:
            current=self._authorize(connection, actor)
            version=connection.execute(text('SELECT version_id FROM c0_documents WHERE space_id=:space AND id=:id'),
                {'space':self._space(connection),'id':_uuid(document_id)}).scalar_one_or_none()
            if version:self._read_version(connection,current,version)
            else:
                from .current_content import check_retired
                check_retired(connection,self._space(connection),'document',_uuid(document_id))
            return [content_row(row) for row in connection.execute(text('''SELECT id,document_id,ordinal,
                start_offset,end_offset,body,content_hash,locations FROM c0_chunks WHERE space_id=:space AND document_id=:id
                ORDER BY ordinal LIMIT :limit OFFSET :offset'''),
                {'space': self._space(connection), 'id': _uuid(document_id), 'limit': limit, 'offset': offset}).mappings()]

    @staticmethod
    def _citation(connection, chunk_id, *, space_id=None):
        row = connection.execute(text('''SELECT c.id AS chunk_id,c.document_id,c.start_offset,c.end_offset,
            c.body,c.content_hash,c.locations,d.version_id,d.text_hash,v.source_id,v.number AS version,
            v.filename,v.media_type,v.content_hash AS source_hash,s.title,s.deleted FROM c0_chunks c
            JOIN c0_documents d ON d.id=c.document_id JOIN c0_source_versions v ON v.id=d.version_id
            JOIN c0_sources s ON s.id=v.source_id WHERE s.space_id=:space AND s.current_version_id=v.id AND c.id=:id'''), {'space': SpaceService.shared_id(connection) if space_id is None else space_id, 'id': _uuid(chunk_id)}).mappings().one_or_none()
        if row is None:
            from .current_content import check_retired
            check_retired(connection,SpaceService.shared_id(connection) if space_id is None else space_id,'chunk',_uuid(chunk_id))
            raise SourceNotFound()
        return content_row(row)

    def citation(self, actor, chunk_id):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return self._citation(connection, chunk_id, space_id=self._space(connection))

    def search(self, actor, query, *, limit=20, offset=0):
        self._page(limit, offset)
        query = _label(query, 512)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            ids = connection.execute(text('''SELECT c.id FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
                JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id
                WHERE s.space_id=:space AND s.current_version_id=v.id AND NOT s.deleted AND c.search_vector @@ websearch_to_tsquery('simple',:query)
                ORDER BY ts_rank_cd(c.search_vector,websearch_to_tsquery('simple',:query)) DESC,c.id
                LIMIT :limit OFFSET :offset'''), {'space': self._space(connection), 'query': query, 'limit': limit, 'offset': offset}).scalars().all()
            return [self._citation(connection, key, space_id=self._space(connection)) for key in ids]

    def _read_version(self,connection,current,version_id):
        row=connection.execute(text('''SELECT v.id,s.current_version_id FROM c0_source_versions v JOIN c0_sources s ON s.id=v.source_id
            WHERE v.space_id=:space AND v.id=:id'''),{'space':self._space(connection),'id':_uuid(version_id)}).mappings().one_or_none()
        if row is None:
            from .current_content import check_retired
            check_retired(connection,self._space(connection),'source_version',_uuid(version_id))
            raise SourceNotFound()
        # Editors can verify their staged bytes through technical source APIs;
        # ordinary document browsing and every search use current pointers only.
        if row['id']!=row['current_version_id'] and (current.role is Role.READER or
                (current.delegated_scopes is not None and 'c0:write' not in current.delegated_scopes)):raise SourceNotFound()

    def reference_resolvers(self):
        def source(connection, actor, key):
            bound = self.in_space(actor.space_id) if actor.space_id is not None else self
            bound._authorize(connection, actor)
            try:
                row = bound._source(connection, key)
            except SourceNotFound:
                return None
            return {'type_name': 'source', 'data': {'title': row['title'], 'revision': row['revision'], 'deleted': row['deleted']}}

        def chunk(connection, actor, key):
            bound = self.in_space(actor.space_id) if actor.space_id is not None else self
            bound._authorize(connection, actor)
            try:
                row = bound._citation(connection, key, space_id=bound._space(connection))
            except SourceNotFound:
                return None
            # UUIDs must be JSON strings; no paths or retained binary content.
            data = {name: str(row[name]) for name in ('source_id', 'version_id', 'document_id')}
            data.update({name: row[name] for name in ('body', 'source_hash', 'content_hash', 'start_offset', 'end_offset', 'deleted')})
            return {'type_name': 'chunk', 'data': data}
        def document(connection, actor, key):
            bound = self.in_space(actor.space_id) if actor.space_id is not None else self
            bound._authorize(connection, actor)
            row = connection.execute(text('SELECT id,version_id,text_hash,char_length(body) AS characters FROM c0_documents WHERE space_id=:space AND id=:id'),
                {'space': bound._space(connection), 'id': key}).mappings().one_or_none()
            if row is None:
                return None
            return {'type_name': 'document', 'data': {'version_id': str(row['version_id']),
                'text_hash': row['text_hash'], 'characters': row['characters']}}
        return {'source': source, 'document': document, 'chunk': chunk}


def register_source_handlers(registry, database, originals):
    jobs = JobService(database, registry)

    def extract(connection, payload):
        from .current_content import content_lock,publish_versions
        content_lock(connection)
        version_id = _uuid(payload['version_id'])
        row = connection.execute(text('SELECT * FROM c0_source_versions WHERE id=:id FOR UPDATE'),
            {'id': version_id}).mappings().one_or_none()
        if row is None or row['state'] != 'queued':
            return {'state': 'unchanged'}
        try:
            evidence = extract_isolated(originals.check(row), row['media_type'])
            segments = chunks(evidence)
        except ExtractionError as error:
            connection.execute(text("UPDATE c0_source_versions SET state='failed',error_code=:code WHERE id=:id"),
                {'id': version_id, 'code': error.code})
            return {'state': 'failed', 'error_code': error.code}
        source=connection.execute(text('SELECT * FROM c0_sources WHERE id=:id'),{'id':row['source_id']}).mappings().one()
        managed=bool(source['metadata'].get('parent_external_id') or (row['publication_metadata'] or {}).get('parent_external_id')) or connection.execute(text("SELECT 1 FROM c0_objects WHERE type_name IN ('c0_project_source_sync_v1','c0_project_source_part_v1') AND data->>'source_id'=:id LIMIT 1"),{'id':str(row['source_id'])}).scalar_one_or_none()
        if not managed and row['media_type'] in TEXT_MEDIA_TYPES and source['current_version_id']:
            current=connection.execute(text('SELECT * FROM c0_documents WHERE version_id=:id'),{'id':source['current_version_id']}).mappings().one_or_none()
            if current and current['text_hash']==evidence.text_hash and current['body']==evidence.text:
                from .current_content import retire_versions
                connection.execute(text('UPDATE c0_sources SET title=:title,metadata=CAST(:metadata AS jsonb),updated_at=now() WHERE id=:id'),
                    {'id':source['id'],'title':row['publication_title'],'metadata':json.dumps(row['publication_metadata'])})
                retire_versions(connection,[version_id])
                return {'state':'unchanged','current_version_id':str(source['current_version_id'])}
        document_id = uuid5(version_id, 'document')
        connection.execute(text('''INSERT INTO c0_documents(space_id,id,version_id,body,text_hash,locations)
            VALUES (:space,:id,:version,:body,:hash,CAST(:locations AS jsonb))'''),
            {'space': row['space_id'], 'id': document_id, 'version': version_id, 'body': evidence.text, 'hash': evidence.text_hash,
             'locations': json.dumps(evidence.locations)})
        connection.execute(text('''INSERT INTO c0_chunks(space_id,id,document_id,ordinal,start_offset,end_offset,body,content_hash,locations)
            VALUES (:space,:id,:document,:ordinal,:start,:end,:body,:hash,CAST(:locations AS jsonb))'''),
            [{'space': row['space_id'], 'id': uuid5(document_id, str(i)), 'document': document_id, 'ordinal': i,
              'start': chunk['start'], 'end': chunk['end'], 'body': chunk['text'],
              'hash': chunk['text_hash'], 'locations': json.dumps(chunk['locations'])}
             for i, chunk in enumerate(segments)])
        connection.execute(text("UPDATE c0_source_versions SET state='ready',error_code=NULL WHERE id=:id"), {'id': version_id})
        if not managed:publish_versions(connection,[version_id])
        if not row['retain_original']:
            jobs._enqueue(connection, 'source.cleanup', payload, 'source:' + str(version_id) + ':cleanup', space_id=row['space_id'])
        return {'state': 'ready', 'document_id': str(document_id), 'chunks': len(segments)}

    def cleanup(connection, payload):
        from .current_content import content_lock,retire_versions
        content_lock(connection)
        if _uuid(payload['version_id']).int==0:
            abandoned=connection.execute(text("SELECT v.id FROM c0_source_versions v JOIN c0_sources s ON s.id=v.source_id WHERE v.id IS DISTINCT FROM s.current_version_id AND v.created_at<now()-interval '24 hours' ORDER BY v.created_at LIMIT 20")).scalars().all()
            retire_versions(connection,abandoned)
            removed=0
            pending=connection.execute(text('SELECT version_id FROM c0_original_cleanup WHERE available_at<=now() ORDER BY available_at,version_id LIMIT 100 FOR UPDATE')).scalars().all()
            for identifier in pending:
                if connection.execute(text('SELECT 1 FROM c0_source_versions WHERE id=:id'),{'id':identifier}).scalar_one_or_none():continue
                try:originals.remove(identifier)
                except OSError:
                    connection.execute(text("UPDATE c0_original_cleanup SET attempts=attempts+1,available_at=now()+interval '5 minutes' WHERE version_id=:id"),{'id':identifier})
                    continue
                connection.execute(text('DELETE FROM c0_original_cleanup WHERE version_id=:id'),{'id':identifier});removed+=1
            return {'removed':removed}
        row = connection.execute(text('SELECT * FROM c0_source_versions WHERE id=:id FOR UPDATE'),
            {'id': _uuid(payload['version_id'])}).mappings().one_or_none()
        if row is None or row['state'] != 'ready' or row['retain_original']:
            return {'removed': False}
        # A separate job can observe this row only after extraction COMMIT.
        # Unlink is idempotent if cleanup COMMIT is interrupted.
        originals.remove(row['id'])
        connection.execute(text('UPDATE c0_source_versions SET original_present=false WHERE id=:id'), {'id': row['id']})
        return {'removed': True}

    registry.register(Handler('source.extract', extract, _payload, timeout_seconds=30))
    registry.register(Handler('source.cleanup', cleanup, _payload))
