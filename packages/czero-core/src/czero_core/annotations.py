# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Revisioned descriptions of exact content, never inferred content changes."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from uuid import UUID, uuid4

from sqlalchemy import text

from .identity import Role
from .knowledge import EvidenceNotReady
from .objects import page
from .receipts import json_value, snapshot
from .sources import _metadata, _uuid
from .wiki import KnowledgeConflict, KnowledgeNotFound, WikiService

KINDS = frozenset({'source_version', 'wiki_revision', 'entity', 'object', 'claim'})
NAMESPACES = frozenset({'applicability', 'verification'})


@dataclass(frozen=True)
class ContentTarget:
    kind: str
    id: UUID
    revision: int

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in KINDS or type(self.revision) is not int or not 1 <= self.revision < 2147483647:
            raise ValueError('invalid_annotation_target')
        object.__setattr__(self, 'id', _uuid(self.id))


def _target(value):
    if not isinstance(value, ContentTarget):
        raise ValueError('invalid_annotation_target')
    return value


def _namespace(value):
    if type(value) is not str or value not in NAMESPACES:
        raise ValueError('invalid_annotation_namespace')
    return value


def _literal(value, maximum=128):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(character) < 32 for character in value)):
        raise ValueError('invalid_annotation_value')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise ValueError('invalid_annotation_value') from None
    # Tags are literal, including case and surrounding nonempty whitespace.
    return value


def _utc(value):
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        raise ValueError('invalid_annotation_time') from None


def annotation_value(namespace, value):
    _namespace(namespace)
    if type(value) is not dict:
        raise ValueError('invalid_annotation_value')
    fields = {'status', 'observed_at', 'confidence', 'extensions'}
    fields |= {'products', 'components', 'version_tags'} if namespace == 'applicability' else {'verified_at'}
    if set(value) - fields:
        raise ValueError('invalid_annotation_field')
    result = dict(value)
    if 'status' in result:
        result['status'] = _literal(result['status'], 64)
    for field in ('products', 'components', 'version_tags'):
        if field in result:
            values = result[field]
            if type(values) is not list or len(values) > 32:
                raise ValueError('invalid_annotation_tags')
            result[field] = list(dict.fromkeys(_literal(tag) for tag in values))
    if 'confidence' in result and result['confidence'] is not None:
        value = result['confidence']
        if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
            raise ValueError('invalid_annotation_confidence')
    for field in ('observed_at', 'verified_at'):
        if field in result and result[field] is not None:
            result[field] = _utc(result[field])
    if 'extensions' in result and type(result['extensions']) is not dict:
        raise ValueError('invalid_annotation_extensions')
    return json.loads(_metadata(result))


class AnnotationService(WikiService):
    """Shared receipt/role ordering protects annotation writes and old retries."""

    def _live(self, connection, target, *, lock=False):
        parameters = {'space': self._space(connection), 'id': target.id}
        if target.kind == 'source_version':
            sql = '''SELECT v.*,s.deleted,s.title FROM c0_source_versions v
                JOIN c0_sources s ON s.id=v.source_id AND s.space_id=v.space_id
                WHERE v.space_id=:space AND v.id=:id'''
            if lock: sql += ' FOR SHARE OF v'
        elif target.kind == 'wiki_revision':
            sql = '''SELECT r.*,p.deleted,p.revision AS current_revision FROM c0_wiki_revisions r
                JOIN c0_wiki_pages p ON p.id=r.page_id AND p.space_id=r.space_id
                WHERE r.space_id=:space AND r.id=:id'''
            if lock: sql += ' FOR SHARE OF r'
        else:
            table = {'entity': 'c0_entities', 'object': 'c0_objects', 'claim': 'c0_claims'}[target.kind]
            sql = 'SELECT * FROM ' + table + ' WHERE space_id=:space AND id=:id'
            if lock: sql += ' FOR SHARE'
        row = connection.execute(text(sql), parameters).mappings().one_or_none()
        if row is None:
            return None
        row = dict(row)
        revision = row['number'] if target.kind in ('source_version', 'wiki_revision') else row['revision']
        resource = row['source_id'] if target.kind == 'source_version' else row['page_id'] if target.kind == 'wiki_revision' else row['id']
        digest = row.get('content_hash')
        if digest is None:
            digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                allow_nan=False, default=json_value, separators=(',', ':')).encode()).hexdigest()
        return {'content_revision': revision, 'current_revision': row.get('current_revision', revision),
                'content_hash': digest, 'resource_id': resource,
                'archived': row.get('deleted', False), 'state': row.get('state'), 'row': row}

    def _anchor(self, connection, target):
        return connection.execute(text('''SELECT * FROM c0_annotation_targets
            WHERE space_id=:space AND kind=:kind AND target_id=:id AND content_revision=:revision'''),
            {'space': self._space(connection), 'kind': target.kind, 'id': target.id,
             'revision': target.revision}).mappings().one_or_none()

    def _binding(self, connection, target, *, writing=False):
        anchor = self._anchor(connection, target)
        live = self._live(connection, target, lock=writing)
        if live is None and (writing or anchor is None):
            raise KnowledgeNotFound()
        if (writing or anchor is None) and live['content_revision'] != target.revision:
            raise KnowledgeConflict()
        binding = dict(anchor) if anchor is not None else {
            'id': None, 'space_id': self._space(connection), 'kind': target.kind,
            'target_id': target.id, 'content_revision': target.revision,
            'resource_id': live['resource_id'], 'content_hash': live['content_hash']}
        return binding, live

    @staticmethod
    def _reference(binding):
        return {'kind': binding['kind'], 'id': binding['target_id'],
                'revision': binding['content_revision'], 'space_id': binding['space_id'],
                'resource_id': binding['resource_id'], 'content_hash': binding['content_hash']}

    def _entry(self, connection, target, namespace, *, binding=None, live=None):
        if binding is None:
            binding, live = self._binding(connection, target)
        row = connection.execute(text('''SELECT a.id,a.revision,r.value,r.actor_id,r.created_at
            FROM c0_annotations a JOIN c0_annotation_revisions r
            ON r.space_id=a.space_id AND r.annotation_id=a.id AND r.number=a.revision
            WHERE a.space_id=:space AND a.anchor_id=:anchor AND a.namespace=:namespace'''),
            {'space': self._space(connection), 'anchor': binding['id'], 'namespace': namespace}).mappings().one_or_none() if binding['id'] else None
        value = row['value'] if row else None
        current = live is not None and live['current_revision'] == target.revision
        if live is not None and live['content_revision'] == target.revision:
            current = current and live['content_hash'] == binding['content_hash']
        return {'id': row['id'] if row else None, 'target': self._reference(binding),
                'namespace': namespace, 'revision': row['revision'] if row else 0,
                'value': value, 'status': value.get('status', 'unknown') if value is not None else 'unknown',
                'actor_id': row['actor_id'] if row else None, 'created_at': row['created_at'] if row else None,
                'target_current': current, 'target_archived': live is None or live['archived'],
                'current_content_revision': live['current_revision'] if live else None}

    def get(self, actor, target, namespace):
        target, namespace = _target(target), _namespace(namespace)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return snapshot(self._entry(connection, target, namespace))

    def history(self, actor, target, namespace, *, limit=50, offset=0):
        target, namespace = _target(target), _namespace(namespace)
        page(limit, offset)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            binding, _ = self._binding(connection, target)
            rows = connection.execute(text('''SELECT r.id,r.number,r.value,r.actor_id,r.created_at
                FROM c0_annotations a JOIN c0_annotation_revisions r
                ON r.space_id=a.space_id AND r.annotation_id=a.id
                WHERE a.space_id=:space AND a.anchor_id=:anchor AND a.namespace=:namespace
                ORDER BY r.number DESC LIMIT :limit OFFSET :offset'''),
                {'space': self._space(connection), 'anchor': binding['id'], 'namespace': namespace,
                 'limit': limit, 'offset': offset}).mappings().all() if binding['id'] else []
            return snapshot({'target': self._reference(binding), 'namespace': namespace,
                             'revisions': [dict(row) for row in rows]})

    def update(self, actor, target, namespace, value, *, expected_revision, idempotency_key):
        target, namespace = _target(target), _namespace(namespace)
        value = annotation_value(namespace, value)
        if type(expected_revision) is not int or not 0 <= expected_revision < 2147483646:
            raise ValueError('invalid_annotation_revision')
        payload = {'target': {'kind': target.kind, 'id': str(target.id), 'revision': target.revision},
                   'namespace': namespace, 'value': value, 'expected_revision': expected_revision}
        def execute(connection, current):
            binding, live = self._binding(connection, target, writing=True)
            if namespace == 'verification' and value.get('status') == 'verified' and target.kind == 'source_version' and live['state'] != 'ready':
                raise EvidenceNotReady()
            if binding['id'] is None:
                fields = {kind + '_id': target.id if kind == target.kind else None for kind in KINDS}
                binding = dict(connection.execute(text('''INSERT INTO c0_annotation_targets
                    (id,space_id,kind,target_id,content_revision,resource_id,content_hash,created_by,
                     source_version_id,wiki_revision_id,entity_id,object_id,claim_id)
                    VALUES (:anchor,:space,:kind,:target,:revision,:resource,:hash,:actor,
                     :source_version_id,:wiki_revision_id,:entity_id,:object_id,:claim_id) RETURNING *'''),
                    {**fields, 'anchor': uuid4(), 'space': self._space(connection), 'kind': target.kind,
                     'target': target.id, 'revision': target.revision, 'resource': live['resource_id'],
                     'hash': live['content_hash'], 'actor': current.user_id}).mappings().one())
            old = connection.execute(text('''SELECT id,revision FROM c0_annotations
                WHERE space_id=:space AND anchor_id=:anchor AND namespace=:namespace FOR UPDATE'''),
                {'space': self._space(connection), 'anchor': binding['id'], 'namespace': namespace}).mappings().one_or_none()
            if (old['revision'] if old else 0) != expected_revision:
                raise KnowledgeConflict()
            if old is None:
                identifier = uuid4()
                connection.execute(text('''INSERT INTO c0_annotations(id,space_id,anchor_id,namespace,revision)
                    VALUES (:id,:space,:anchor,:namespace,1)'''),
                    {'id': identifier, 'space': self._space(connection), 'anchor': binding['id'], 'namespace': namespace})
            else:
                identifier = old['id']
                connection.execute(text('UPDATE c0_annotations SET revision=revision+1 WHERE space_id=:space AND id=:id'),
                    {'space': self._space(connection), 'id': identifier})
            number = expected_revision + 1
            connection.execute(text('''INSERT INTO c0_annotation_revisions(id,space_id,annotation_id,number,value,actor_id)
                VALUES (:id,:space,:annotation,:number,CAST(:value AS jsonb),:actor)'''),
                {'id': uuid4(), 'space': self._space(connection), 'annotation': identifier,
                 'number': number, 'value': json.dumps(value, ensure_ascii=False), 'actor': current.user_id})
            self._event(connection, current, 'annotation', identifier, number, namespace)
            return self._entry(connection, target, namespace, binding=binding, live=live)
        return self._mutate(actor, 'annotation.update', payload, idempotency_key, execute)
