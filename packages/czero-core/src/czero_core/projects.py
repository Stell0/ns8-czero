# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Protected research projects using existing typed storage and transaction receipts."""
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import text

from .identity import PermissionDenied, Role
from .objects import ObjectService, ObjectConflict, ObjectNotFound, page
from .object_schema import bounded_json, validate_record
from .project_schema import PREFIX, SCHEMAS, normalize_manifest, identifier, next_occurrence
from .receipts import mutate, snapshot
from .spaces import SpaceBound


class ProjectConflict(ObjectConflict):
    pass


class ProjectNotFound(ObjectNotFound):
    pass


def logical_key(kind, identity):
    return hashlib.sha256((kind + '\n' + identity).encode()).hexdigest()


class ProjectService(SpaceBound):
    def __init__(self, database, access, *, clock=None):
        self.database, self.access = database, access
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _authorize(self, connection, actor, role=Role.READER):
        if self._space_id is None:
            raise ValueError('explicit_project_space_required')
        current = self._space_authorize(connection, actor, role)
        if connection.execute(text('SELECT shared FROM c0_spaces WHERE id=:space'),
                              {'space': self._space_id}).scalar_one():
            raise PermissionDenied()
        return current

    def _admin(self, connection, actor, role=Role.ADMIN):
        return self._authorize(connection, actor, Role.ADMIN)

    def _objects(self):
        # This flag is trusted Python wiring, never a request field.
        return ObjectService(self.database, self.access, managed_projects=True).in_space(self._space_id)

    def _bootstrap(self, connection, actor):
        for kind, schema in SCHEMAS.items():
            type_name = PREFIX + kind
            row = connection.execute(text('SELECT schema,unique_fields FROM c0_object_types WHERE name=:name'),
                                     {'name': type_name}).mappings().one_or_none()
            if row is not None:
                if row['schema'] != schema or row['unique_fields'] != ['key']:
                    raise ProjectConflict()
                continue
            self._admin(connection, actor)
            connection.execute(text('''INSERT INTO c0_object_types(name,label,schema,unique_fields)
                VALUES(:name,:label,CAST(:schema AS jsonb),ARRAY['key'])'''),
                {'name': type_name, 'label': 'Research project ' + kind, 'schema': json.dumps(schema)})

    def _find(self, connection, kind, identity, *, required=True):
        row = connection.execute(text('''SELECT o.* FROM c0_object_keys k JOIN c0_objects o ON o.id=k.object_id AND o.space_id=k.space_id
            WHERE k.space_id=:space AND k.type_name=:type AND k.field='key' AND k.value=CAST(:key AS jsonb)'''),
            {'space': self._space_id, 'type': PREFIX + kind, 'key': json.dumps(logical_key(kind, identity))}).mappings().one_or_none()
        if row is None and required:
            raise ProjectNotFound()
        return dict(row) if row else None

    def _save(self, connection, actor, kind, identity, data, *, previous=None):
        values = {'key': logical_key(kind, identity), **data}
        if previous is None:
            operation = {'operation': 'create', 'type_name': PREFIX + kind, 'data': values}
        else:
            operation = {'operation': 'update', 'id': str(previous['id']),
                'expected_revision': previous['revision'], 'data': values}
        return self._objects()._write(connection, actor, operation)

    def _mutate(self, actor, operation, data, key, execute, *, admin=False):
        bounded_json(data, maximum=262144)
        return mutate(self.database, self._admin if admin else self._authorize, actor,
            'project.' + operation, data, key, execute, conflict=ProjectConflict, lock_objects=True)

    def _manifest(self, connection):
        return self._find(connection, 'manifest_v1', 'manifest')

    def get(self, actor):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return snapshot(self._manifest(connection))

    def list_records(self, actor, kind, *, limit=50, offset=0):
        if kind not in SCHEMAS:
            raise ValueError('invalid_project_record_kind')
        page(limit, offset)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            rows = connection.execute(text('''SELECT * FROM c0_objects
                WHERE space_id=:space AND type_name=:type ORDER BY created_at,id LIMIT :limit OFFSET :offset'''),
                {'space': self._space_id, 'type': PREFIX + kind, 'limit': limit, 'offset': offset}).mappings()
            return snapshot([dict(row) for row in rows])

    def _primary_topics(self, connection, manifest):
        for topic_id in manifest['primary_topic_ids']:
            topic = self._find(connection, 'topic_v1', topic_id)['data']
            if topic['classification'] != 'user' or topic['lifecycle'] != 'active' or not topic['authorized_by']:
                raise ValueError('primary_topic_requires_active_user_authorization')

    def initialize(self, actor, manifest, *, authorization_ref, idempotency_key):
        manifest = normalize_manifest(manifest)
        if manifest['space_id'] != str(self._space_id):
            raise ValueError('project_space_mismatch')
        if not isinstance(authorization_ref, str) or not 1 <= len(authorization_ref) <= 512:
            raise ValueError('project_authorization_reference_required')
        def execute(connection, current):
            self._bootstrap(connection, current)
            if self._find(connection, 'manifest_v1', 'manifest', required=False):
                raise ProjectConflict()
            self._primary_topics(connection, manifest)
            result = self._save(connection, current, 'manifest_v1', 'manifest', {'version': 1, 'manifest': manifest})
            self._save(connection, current, 'config_v1', '1', {'version': 1, 'manifest': manifest,
                'actor_id': str(current.user_id), 'authorization_ref': authorization_ref,
                'recorded_at': self.clock().isoformat()})
            return result
        return self._mutate(actor, 'initialize', {'manifest': manifest, 'authorization_ref': authorization_ref},
                            idempotency_key, execute, admin=True)

    def configure(self, actor, manifest, *, expected_revision, authorization_ref, idempotency_key):
        manifest = normalize_manifest(manifest)
        if manifest['space_id'] != str(self._space_id):
            raise ValueError('project_space_mismatch')
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('invalid_revision')
        if not isinstance(authorization_ref, str) or not 1 <= len(authorization_ref) <= 512:
            raise ValueError('project_authorization_reference_required')
        def execute(connection, current):
            previous = self._manifest(connection)
            if previous['revision'] != expected_revision:
                raise ProjectConflict()
            old = previous['data']['manifest']
            if manifest['project_id'] != old['project_id']:
                raise ProjectConflict()
            self._primary_topics(connection, manifest)
            version = previous['data']['version'] + 1
            self._save(connection, current, 'config_v1', str(version), {'version': version, 'manifest': manifest,
                'actor_id': str(current.user_id), 'authorization_ref': authorization_ref,
                'recorded_at': self.clock().isoformat()})
            return self._save(connection, current, 'manifest_v1', 'manifest', {'version': version, 'manifest': manifest}, previous=previous)
        return self._mutate(actor, 'configure', {'manifest': manifest, 'expected_revision': expected_revision,
            'authorization_ref': authorization_ref}, idempotency_key, execute, admin=True)

    def set_topic(self, actor, topic, *, expected_revision=0, idempotency_key):
        topic = bounded_json(topic)
        allowed = set(SCHEMAS['topic_v1']['properties']) - {'key', 'schema_version', 'authorized_by', 'created_at', 'expires_at'}
        if set(topic) - allowed:
            raise ValueError('invalid_project_topic')
        identifier(topic.get('topic_id'))
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('invalid_revision')
        def execute(connection, current):
            self._bootstrap(connection, current)
            previous = self._find(connection, 'topic_v1', topic['topic_id'], required=False)
            if (previous['revision'] if previous else 0) != expected_revision:
                raise ProjectConflict()
            values = {'schema_version': 1, 'aliases': [], 'parent_ids': [], 'anchor_ids': [],
                'originating_question': '', 'direct_contribution': '', 'assessment_ref': '', 'authorization_ref': '',
                'authorized_by': '', 'lifecycle': 'active', **topic,
                'created_at': previous['data']['created_at'] if previous else self.clock().isoformat(), 'expires_at': ''}
            kind = values['classification']
            manifest_row = self._find(connection, 'manifest_v1', 'manifest', required=False)
            if (manifest_row and values['topic_id'] in manifest_row['data']['manifest']['primary_topic_ids']
                    and (kind != 'user' or values['lifecycle'] != 'active')):
                raise ValueError('primary_topic_requires_active_user_authorization')
            if kind == 'user' or (previous and previous['data']['classification'] == 'user'):
                current = self._admin(connection, actor)
                if not values['authorization_ref'].strip():
                    raise ValueError('project_authorization_reference_required')
                values['authorized_by'] = str(current.user_id)
                if kind == 'user':
                    values['anchor_ids'] = [values['topic_id']]
            elif previous and previous['data']['authorized_by']:
                values['authorized_by'] = previous['data']['authorized_by']
            if previous and previous['data']['lifecycle'] in ('archived', 'retired') and values['lifecycle'] == 'active':
                raise ValueError('archived_topic_requires_new_explicit_authorization')
            if len(set(values['parent_ids'])) != len(values['parent_ids']) or values['topic_id'] in values['parent_ids']:
                raise ValueError('invalid_topic_parents')
            for parent_id in values['parent_ids']:
                parent = self._find(connection, 'topic_v1', parent_id)['data']
                if parent['classification'] == 'peripheral':
                    raise ValueError('peripheral_topic_is_terminal')
                ancestors = connection.execute(text('''WITH RECURSIVE ancestors AS (
                    SELECT data FROM c0_objects WHERE space_id=:space AND type_name=:type AND data->>'topic_id'=:parent
                    UNION SELECT o.data FROM c0_objects o JOIN ancestors a
                    ON a.data->'parent_ids' ? (o.data->>'topic_id')
                    WHERE o.space_id=:space AND o.type_name=:type)
                    SELECT data->>'topic_id' FROM ancestors LIMIT 1001'''),
                    {'space': self._space_id, 'type': PREFIX + 'topic_v1', 'parent': parent_id}).scalars().all()
                if len(ancestors) > 1000 or values['topic_id'] in ancestors:
                    raise ValueError('invalid_topic_ancestry')
            if kind in ('adjacent', 'peripheral'):
                if not values['anchor_ids'] or len(set(values['anchor_ids'])) != len(values['anchor_ids']):
                    raise ValueError('topic_requires_direct_user_anchor')
                for anchor_id in values['anchor_ids']:
                    anchor = self._find(connection, 'topic_v1', anchor_id)['data']
                    if anchor['classification'] != 'user' or anchor['lifecycle'] != 'active':
                        raise ValueError('topic_requires_direct_user_anchor')
                if not values['direct_contribution'].strip() or not values['assessment_ref'].strip():
                    raise ValueError('topic_requires_recorded_assessment')
            if kind == 'peripheral':
                manifest = self._manifest(connection)['data']['manifest']
                values['expires_at'] = (previous['data']['expires_at'] if previous and previous['data']['expires_at']
                    else next_occurrence(manifest, 'weekly', self.clock()).isoformat())
            values = validate_record(SCHEMAS['topic_v1'], {'key': logical_key('topic_v1', topic['topic_id']), **values})
            return self._save(connection, current, 'topic_v1', topic['topic_id'], {k: v for k, v in values.items() if k != 'key'}, previous=previous)
        # Initial schema bootstrap is Admin-only. Thereafter Editors can assess adjacent topics.
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor, Role.EDITOR)
            bootstrapped = connection.execute(text('SELECT 1 FROM c0_object_types WHERE name=:name'),
                {'name': PREFIX + 'topic_v1'}).scalar_one_or_none()
        return self._mutate(actor, 'topic', {'topic': topic, 'expected_revision': expected_revision}, idempotency_key,
            execute, admin=not bootstrapped)
