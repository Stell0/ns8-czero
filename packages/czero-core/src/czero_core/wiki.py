# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned authored knowledge, separate from immutable extracted evidence."""
import hashlib
import json
import re
import unicodedata
from uuid import uuid4

from sqlalchemy import text

from .identity import PermissionDenied, Role
from .object_schema import name
from .objects import page
from .sources import _label, _metadata, _uuid
from .receipts import MUTATION_LOCK as KNOWLEDGE_LOCK, json_value as _json, snapshot as _view, mutate

_SLUG = re.compile(r'[a-z0-9][a-z0-9/-]{0,127}\Z')


class KnowledgeConflict(Exception):
    pass


class KnowledgeNotFound(Exception):
    pass


def page_slug(value):
    if not isinstance(value, str) or not _SLUG.fullmatch(value) or '//' in value or value.endswith('/'):
        raise ValueError('invalid_slug')
    return value


def alias_key(value):
    label = _label(value, 128)
    normalized = unicodedata.normalize('NFKC', label).casefold()
    if len(normalized) > 256:
        raise ValueError('invalid_alias')
    return normalized, label


def markdown(value):
    if not isinstance(value, str) or '\0' in value:
        raise ValueError('invalid_wiki_body')
    try:
        if len(value.encode('utf-8')) > 131072:
            raise ValueError('invalid_wiki_body')
    except UnicodeError:
        raise ValueError('invalid_wiki_body') from None
    return value


class WikiService:
    def __init__(self, database, access):
        self.database, self.access = database, access

    def _authorize(self, connection, actor, role=Role.READER):
        if self.access is None:
            raise PermissionDenied()
        current = self.access._actor(connection, actor.user_id)
        current.require(role)
        return current

    def _mutate(self, actor, operation, payload, key, execute):
        return mutate(self.database, self._authorize, actor, operation, payload,
                      key, execute, conflict=KnowledgeConflict)

    @staticmethod
    def _event(connection, actor, kind, resource_id, revision, operation):
        connection.execute(text('''INSERT INTO c0_knowledge_events(kind,resource_id,operation,revision,actor_id)
            VALUES (:kind,:id,:operation,:revision,:actor)'''),
            {'kind': kind, 'id': resource_id, 'operation': operation, 'revision': revision, 'actor': actor.user_id})

    @staticmethod
    def _page(connection, page_id, *, lock=False):
        row = connection.execute(text('SELECT * FROM c0_wiki_pages WHERE id=:id' + (' FOR UPDATE' if lock else '')),
            {'id': _uuid(page_id)}).mappings().one_or_none()
        if row is None: raise KnowledgeNotFound()
        return dict(row)

    @staticmethod
    def _revision(connection, page_id, number):
        row = connection.execute(text('SELECT * FROM c0_wiki_revisions WHERE page_id=:id AND number=:number'),
            {'id': _uuid(page_id), 'number': number}).mappings().one_or_none()
        if row is None: raise KnowledgeNotFound()
        return dict(row)

    def _write_revision(self, connection, actor, row, title, body, metadata):
        connection.execute(text('''INSERT INTO c0_wiki_revisions(id,page_id,number,title,body,content_hash,metadata,actor_id)
            VALUES (:id,:page,:number,:title,:body,:hash,CAST(:metadata AS jsonb),:actor)'''),
            {'id': uuid4(), 'page': row['id'], 'number': row['revision'], 'title': title, 'body': body,
             'hash': hashlib.sha256(body.encode()).hexdigest(), 'metadata': metadata, 'actor': actor.user_id})
        return {**row, 'content': self._revision(connection, row['id'], row['revision'])}

    def _create_page(self, connection, actor, slug, title, body, encoded):
        row = dict(connection.execute(text('INSERT INTO c0_wiki_pages(id,slug,title) VALUES (:id,:slug,:title) RETURNING *'),
            {'id': uuid4(), 'slug': slug, 'title': title}).mappings().one())
        result = self._write_revision(connection, actor, row, title, body, encoded)
        self._event(connection, actor, 'page', row['id'], 1, 'create')
        return result

    def _update_page(self, connection, actor, row, title, body, encoded, expected_revision):
        if row['deleted'] or row['revision'] != expected_revision: raise KnowledgeConflict()
        row = dict(connection.execute(text('''UPDATE c0_wiki_pages SET title=:title,revision=revision+1,
            updated_at=now() WHERE id=:id RETURNING *'''), {'id': row['id'], 'title': title}).mappings().one())
        result = self._write_revision(connection, actor, row, title, body, encoded)
        self._event(connection, actor, 'page', row['id'], row['revision'], 'update')
        return result

    def create_page(self, actor, slug, title, body, *, metadata=None, idempotency_key):
        slug, title, body = page_slug(slug), _label(title, 256), markdown(body)
        encoded = _metadata({} if metadata is None else metadata)
        def execute(connection, current):
            return self._create_page(connection, current, slug, title, body, encoded)
        return self._mutate(actor, 'page.create', {'slug': slug, 'title': title, 'body': body, 'metadata': json.loads(encoded)}, idempotency_key, execute)

    def update_page(self, actor, page_id, title, body, *, expected_revision, metadata=None, idempotency_key):
        page_id, title, body = _uuid(page_id), _label(title, 256), markdown(body)
        if type(expected_revision) is not int or not 1 <= expected_revision < 2147483647:
            raise ValueError('invalid_revision')
        encoded = _metadata({} if metadata is None else metadata)
        def execute(connection, current):
            return self._update_page(connection, current, self._page(connection, page_id, lock=True),
                                     title, body, encoded, expected_revision)
        return self._mutate(actor, 'page.update', {'id': str(page_id), 'title': title, 'body': body,
            'expected_revision': expected_revision, 'metadata': json.loads(encoded)}, idempotency_key, execute)

    def resolve_page(self, actor, slug, *, include_deleted=False):
        slug = page_slug(slug)
        if type(include_deleted) is not bool: raise ValueError('invalid_filter')
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            row = connection.execute(text('''SELECT * FROM c0_wiki_pages WHERE slug=:slug
                AND (:deleted OR NOT deleted)'''), {'slug': slug, 'deleted': include_deleted}).mappings().one_or_none()
            if row is None: raise KnowledgeNotFound()
            return _view({**row, 'content': self._revision(connection, row['id'], row['revision'])})

    def upsert_page(self, actor, slug, title, body, *, expected_revision=None, metadata=None, idempotency_key):
        """Create-only without a revision; otherwise update-only with that revision."""
        slug, title, body = page_slug(slug), _label(title, 256), markdown(body)
        if expected_revision is not None and (type(expected_revision) is not int or not 1 <= expected_revision < 2147483647):
            raise ValueError('invalid_revision')
        encoded = _metadata({} if metadata is None else metadata)
        def execute(connection, current):
            if expected_revision is None:
                return self._create_page(connection, current, slug, title, body, encoded)
            row = connection.execute(text('SELECT * FROM c0_wiki_pages WHERE slug=:slug FOR UPDATE'),
                                     {'slug': slug}).mappings().one_or_none()
            if row is None: raise KnowledgeNotFound()
            return self._update_page(connection, current, row, title, body, encoded, expected_revision)
        return self._mutate(actor, 'page.upsert', {'slug': slug, 'title': title, 'body': body,
            'expected_revision': expected_revision, 'metadata': json.loads(encoded)}, idempotency_key, execute)

    def get_page(self, actor, page_id, *, revision=None):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            row = self._page(connection, page_id)
            if revision is not None and (type(revision) is not int or revision < 1): raise ValueError('invalid_revision')
            return _view({**row, 'content': self._revision(connection, page_id, row['revision'] if revision is None else revision)})

    def list_pages(self, actor, *, limit=50, offset=0, include_deleted=False):
        page(limit, offset)
        if type(include_deleted) is not bool: raise ValueError('invalid_filter')
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return _view([dict(row) for row in connection.execute(text('''SELECT * FROM c0_wiki_pages
                WHERE :deleted OR NOT deleted ORDER BY updated_at DESC,id LIMIT :limit OFFSET :offset'''),
                {'deleted': include_deleted, 'limit': limit, 'offset': offset}).mappings()])

    def page_history(self, actor, page_id, *, limit=50, offset=0):
        page(limit, offset)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor); self._page(connection, page_id)
            return _view([dict(row) for row in connection.execute(text('''SELECT id,page_id,number,title,content_hash,actor_id,created_at
                FROM c0_wiki_revisions WHERE page_id=:id ORDER BY number DESC LIMIT :limit OFFSET :offset'''),
                {'id': _uuid(page_id), 'limit': limit, 'offset': offset}).mappings()])

    def delete_page(self, actor, page_id, *, expected_revision, idempotency_key):
        page_id = _uuid(page_id)
        if type(expected_revision) is not int or not 1 <= expected_revision < 2147483647: raise ValueError('invalid_revision')
        def execute(connection, current):
            row = self._page(connection, page_id, lock=True)
            if row['revision'] != expected_revision: raise KnowledgeConflict()
            if not row['deleted']:
                # Archive is a new immutable revision, preserving citation targets.
                previous = self._revision(connection, page_id, row['revision'])
                row = dict(connection.execute(text('''UPDATE c0_wiki_pages SET deleted=true,
                    revision=revision+1,updated_at=now() WHERE id=:id RETURNING *'''), {'id': page_id}).mappings().one())
                self._write_revision(connection, current, row, row['title'], previous['body'], _metadata(previous['metadata']))
                self._event(connection, current, 'page', page_id, row['revision'], 'delete')
            return row
        return self._mutate(actor, 'page.delete', {'id': str(page_id), 'expected_revision': expected_revision}, idempotency_key, execute)

    def export_page(self, actor, page_id, *, revision=None, format='json'):
        if format not in ('json', 'markdown'): raise ValueError('invalid_export_format')
        row = self.get_page(actor, page_id, revision=revision)
        return row['content']['body'] if format == 'markdown' else json.loads(json.dumps(row, default=_json))

    @staticmethod
    def _entity(connection, entity_id, *, lock=False):
        row = connection.execute(text('SELECT * FROM c0_entities WHERE id=:id' + (' FOR UPDATE' if lock else '')),
            {'id': _uuid(entity_id)}).mappings().one_or_none()
        if row is None: raise KnowledgeNotFound()
        return dict(row)

    @staticmethod
    def _alias(connection, entity_id, value):
        normalized, label = alias_key(value)
        existing = connection.execute(text('SELECT entity_id FROM c0_entity_aliases WHERE normalized=:key'), {'key': normalized}).scalar_one_or_none()
        if existing is not None:
            if existing != entity_id: raise KnowledgeConflict()
            return False
        if connection.execute(text('SELECT count(*) FROM c0_entity_aliases WHERE entity_id=:id'), {'id': entity_id}).scalar_one() >= 16:
            raise ValueError('alias_limit')
        connection.execute(text('INSERT INTO c0_entity_aliases(normalized,entity_id,label) VALUES (:key,:id,:label)'),
            {'key': normalized, 'id': entity_id, 'label': label})
        return True

    def create_entity(self, actor, kind, label, *, aliases=None, metadata=None, idempotency_key):
        kind, label = name(kind), _label(label, 128)
        aliases = [] if aliases is None else aliases
        if not isinstance(aliases, list) or len(aliases) > 15: raise ValueError('invalid_aliases')
        labels = [alias_key(value)[1] for value in [label, *aliases]]
        encoded = _metadata({} if metadata is None else metadata)
        def execute(connection, current):
            row = dict(connection.execute(text('''INSERT INTO c0_entities(id,kind,label,metadata)
                VALUES (:id,:kind,:label,CAST(:metadata AS jsonb)) RETURNING *'''),
                {'id': uuid4(), 'kind': kind, 'label': label, 'metadata': encoded}).mappings().one())
            for alias in labels: self._alias(connection, row['id'], alias)
            self._event(connection, current, 'entity', row['id'], 1, 'create')
            return row
        return self._mutate(actor, 'entity.create', {'kind': kind, 'label': label, 'aliases': labels, 'metadata': json.loads(encoded)}, idempotency_key, execute)

    def get_entity(self, actor, entity_id):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            row = self._entity(connection, entity_id)
            return _view({**row, 'aliases': [dict(alias) for alias in connection.execute(text('SELECT normalized,label FROM c0_entity_aliases WHERE entity_id=:id ORDER BY normalized'), {'id': row['id']}).mappings()]})

    def resolve_alias(self, actor, value):
        normalized, _ = alias_key(value)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            row = connection.execute(text('''SELECT e.* FROM c0_entity_aliases a JOIN c0_entities e ON e.id=a.entity_id
                WHERE a.normalized=:key AND NOT e.deleted'''), {'key': normalized}).mappings().one_or_none()
            if row is None: raise KnowledgeNotFound()
            return _view(dict(row))

    def list_entities(self, actor, *, kind=None, limit=50, offset=0):
        page(limit, offset)
        if kind is not None: kind = name(kind)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return _view([dict(row) for row in connection.execute(text('''SELECT * FROM c0_entities WHERE NOT deleted
                AND (CAST(:kind AS text) IS NULL OR kind=:kind) ORDER BY label,id LIMIT :limit OFFSET :offset'''),
                {'kind': kind, 'limit': limit, 'offset': offset}).mappings()])

    def update_entity(self, actor, entity_id, label, *, expected_revision, metadata=None, idempotency_key):
        entity_id, label = _uuid(entity_id), _label(label, 128)
        if type(expected_revision) is not int or not 1 <= expected_revision < 2147483647: raise ValueError('invalid_revision')
        encoded = _metadata({} if metadata is None else metadata)
        def execute(connection, current):
            row = self._entity(connection, entity_id, lock=True)
            if row['deleted'] or row['revision'] != expected_revision: raise KnowledgeConflict()
            self._alias(connection, entity_id, label)
            row = dict(connection.execute(text('''UPDATE c0_entities SET label=:label,metadata=CAST(:metadata AS jsonb),
                revision=revision+1,updated_at=now() WHERE id=:id RETURNING *'''),
                {'id': entity_id, 'label': label, 'metadata': encoded}).mappings().one())
            self._event(connection, current, 'entity', entity_id, row['revision'], 'update')
            return row
        return self._mutate(actor, 'entity.update', {'id': str(entity_id), 'label': label, 'metadata': json.loads(encoded),
            'expected_revision': expected_revision}, idempotency_key, execute)

    def add_alias(self, actor, entity_id, value, *, expected_revision, idempotency_key):
        entity_id = _uuid(entity_id); normalized, label = alias_key(value)
        if type(expected_revision) is not int or not 1 <= expected_revision < 2147483647: raise ValueError('invalid_revision')
        def execute(connection, current):
            row = self._entity(connection, entity_id, lock=True)
            if row['deleted'] or row['revision'] != expected_revision: raise KnowledgeConflict()
            if self._alias(connection, entity_id, label):
                row = dict(connection.execute(text('UPDATE c0_entities SET revision=revision+1,updated_at=now() WHERE id=:id RETURNING *'), {'id': entity_id}).mappings().one())
                self._event(connection, current, 'entity', entity_id, row['revision'], 'alias_add')
            return row
        return self._mutate(actor, 'entity.alias_add', {'id': str(entity_id), 'alias': normalized, 'expected_revision': expected_revision}, idempotency_key, execute)

    def delete_entity(self, actor, entity_id, *, expected_revision, idempotency_key):
        entity_id = _uuid(entity_id)
        if type(expected_revision) is not int or not 1 <= expected_revision < 2147483647: raise ValueError('invalid_revision')
        def execute(connection, current):
            row = self._entity(connection, entity_id, lock=True)
            if row['revision'] != expected_revision: raise KnowledgeConflict()
            if not row['deleted']:
                row = dict(connection.execute(text('UPDATE c0_entities SET deleted=true,revision=revision+1,updated_at=now() WHERE id=:id RETURNING *'), {'id': entity_id}).mappings().one())
                self._event(connection, current, 'entity', entity_id, row['revision'], 'delete')
            return row
        return self._mutate(actor, 'entity.delete', {'id': str(entity_id), 'expected_revision': expected_revision}, idempotency_key, execute)

    def changes(self, actor, *, after=0, limit=50):
        page(limit)
        if type(after) is not int or not 0 <= after <= 9223372036854775807: raise ValueError('invalid_cursor')
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return _view([dict(row) for row in connection.execute(text('SELECT * FROM c0_knowledge_events WHERE id>:after ORDER BY id LIMIT :limit'), {'after': after, 'limit': limit}).mappings()])
