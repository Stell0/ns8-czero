# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Outgoing current-resource navigation; never evidence or publication authority."""
import hashlib
import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .current_content import content_lock
from .identity import PermissionDenied, Role
from .object_schema import name
from .receipts import _KEY, snapshot
from .spaces import SpaceService, hold_authority, require_scope, space_uuid

_ENDPOINTS = {'object': 'c0_objects', 'page': 'c0_wiki_pages', 'source': 'c0_sources',
              'entity': 'c0_entities', 'claim': 'c0_claims'}
_TABLE = 'c0_cross_space_references'


class ReferenceNotFound(ValueError):
    def __init__(self):
        super().__init__('reference_source_unavailable')


class ReferenceTargetUnavailable(ValueError):
    def __init__(self):
        super().__init__('reference_target_unavailable')


class ReferenceConflict(ValueError):
    def __init__(self):
        super().__init__('reference_conflict')


def endpoint(value):
    if not isinstance(value, dict) or not isinstance(value.get('kind'), str) or value['kind'] not in _ENDPOINTS:
        raise ValueError('invalid_reference_endpoint')
    kind = value['kind']
    if set(value) != ({'kind', 'id', 'type_name'} if kind == 'object' else {'kind', 'id'}):
        raise ValueError('invalid_reference_endpoint')
    result = {'kind': kind, 'id': str(space_uuid(value['id']))}
    if kind == 'object':
        result['type_name'] = name(value['type_name'])
    return result


def _active(kind, alias):
    return 'TRUE' if kind == 'object' else 'NOT '+alias+'.deleted'


def _summary_query():
    branches = []
    for kind, table in _ENDPOINTS.items():
        fields = {'object': "'type_name',t.type_name", 'page': "'label',t.title",
                  'source': "'label',t.title", 'entity': "'label',t.label",
                  'claim': "'predicate',t.predicate,'evidence_stale',t.evidence_stale"}[kind]
        branches.append("""SELECT r.id,r.relation_kind,jsonb_build_object(
            'space_id',r.target_space_id,'kind',r.target_kind,'id',r.target_id,
            'revision',t.revision,"""+fields+""") AS target
            FROM c0_cross_space_references r JOIN """+table+""" t
              ON t.space_id=r.target_space_id AND t.id=r.target_"""+kind+"""_id
            WHERE r.source_space_id=:space AND r.source_kind=:kind AND r.source_id=:source
              AND r.target_space_id=ANY(CAST(:targets AS uuid[]))
              AND r.target_kind='"""+kind+"' AND "+_active(kind, 't')+"""
              AND (CAST(:after AS uuid) IS NULL OR r.id>CAST(:after AS uuid))""")
    return text('SELECT * FROM ('+' UNION ALL '.join(branches)+') visible ORDER BY id LIMIT :limit')


_LIST = _summary_query()


class CrossSpaceReferenceService:
    def __init__(self, database, access):
        self.database, self.access = database, access
        self.spaces = SpaceService(database, access)

    def _source_actor(self, c, actor, space, targets, role, *, read):
        selected = self.spaces.authorize_many(c, actor, list(dict.fromkeys([space, *targets])),
                                              check_scopes=False)
        current = selected.get(space)
        if current is None:
            raise PermissionDenied()
        current.require(role)
        require_scope(current, role)
        if read:
            require_scope(current, Role.READER)
        return current, selected

    @staticmethod
    def _available(c, space, resource, *, lock=False):
        kind = resource['kind']
        # SQL identifiers are closed, trusted constants; request values are bound.
        row = c.execute(text('SELECT t.id FROM '+_ENDPOINTS[kind]+' t WHERE '
            't.space_id=:space AND t.id=:id AND '+_active(kind, 't')+
            (' AND t.type_name=:type_name' if kind == 'object' else '')+
            (' FOR KEY SHARE' if lock else '')),
            {'space': space, 'id': resource['id'], 'type_name': resource.get('type_name')}).first()
        return row is not None

    def _mutate(self, actor, space, source, operation, payload, key, target=None):
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise ValueError('invalid_idempotency_key')
        fingerprint = hashlib.sha256(json.dumps({'space': str(space), 'operation': operation,
            **payload}, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        try:
            with self.database.engine.begin() as c:
                # Match mixed-domain bundles before reading any caller authority.
                for lock in (49375, 49376):
                    c.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
                hold_authority(c)
                content_lock(c)
                targets = [space_uuid(target['space_id'])] if target else []
                current, selected = self._source_actor(c, actor, space, targets, Role.EDITOR,
                                                       read=target is not None)
                if target:
                    if not self._available(c, space, source, lock=True):
                        raise ReferenceNotFound()
                    target_space = targets[0]
                    target_resource = {k: v for k, v in target.items() if k != 'space_id'}
                    if target_space not in selected or not self._available(c, target_space, target_resource, lock=True):
                        raise ReferenceTargetUnavailable()
                receipt = c.execute(text('''SELECT fingerprint,result FROM c0_knowledge_receipts
                    WHERE space_id=:space AND actor_id=:actor AND key=:key'''),
                    {'space': space, 'actor': current.user_id, 'key': key}).mappings().one_or_none()
                if receipt:
                    if receipt['fingerprint'] != fingerprint:
                        raise ReferenceConflict()
                    result = receipt['result']
                else:
                    if target:
                        source_column, target_column = 'source_'+source['kind']+'_id', 'target_'+target['kind']+'_id'
                        identifier = c.execute(text('INSERT INTO '+_TABLE+'''
                            (id,source_space_id,source_kind,source_id,target_space_id,target_kind,target_id,
                             relation_kind,created_by,'''+source_column+','+target_column+''')
                            VALUES (:id,:space,:kind,:source,:target_space,:target_kind,:target,
                                    'references',:actor,:source,:target)
                            ON CONFLICT (source_space_id,source_kind,source_id,target_space_id,
                                         target_kind,target_id,relation_kind)
                            DO UPDATE SET id=c0_cross_space_references.id RETURNING id'''),
                            {'id': uuid4(), 'space': space, 'kind': source['kind'], 'source': source['id'],
                             'target_space': target_space, 'target_kind': target['kind'],
                             'target': target['id'], 'actor': current.user_id}).scalar_one()
                        result = {'reference_id': str(identifier)}
                    else:
                        # Blind deletion never fetches target identity or affected-row count.
                        c.execute(text('''DELETE FROM c0_cross_space_references WHERE
                            source_space_id=:space AND source_kind=:kind AND source_id=:source AND id=:id''' +
                            (''' AND EXISTS(SELECT 1 FROM c0_objects o WHERE o.space_id=:space
                                AND o.id=:source AND o.type_name=:type_name)''' if source['kind']=='object' else '')),
                            {'space': space, 'kind': source['kind'], 'source': source['id'],
                             'id': payload['reference_id'], 'type_name': source.get('type_name')})
                        result = {}
                    c.execute(text('''INSERT INTO c0_knowledge_receipts(space_id,actor_id,key,fingerprint,result)
                        VALUES (:space,:actor,:key,:fingerprint,CAST(:result AS jsonb))'''),
                        {'space': space, 'actor': current.user_id, 'key': key,
                         'fingerprint': fingerprint, 'result': json.dumps(result)})
                self.access.checked_actor(c, actor).require(Role.EDITOR)
                return snapshot(result) if target else None
        except IntegrityError:
            raise ReferenceConflict() from None

    def create(self, actor, *, space_id, source, target, relation_kind='references', idempotency_key):
        space, source = space_uuid(space_id), endpoint(source)
        if not isinstance(target, dict) or 'space_id' not in target:
            raise ValueError('invalid_reference_endpoint')
        target_space = space_uuid(target['space_id'])
        target = {**endpoint({k: v for k, v in target.items() if k != 'space_id'}), 'space_id': str(target_space)}
        if space == target_space or relation_kind != 'references':
            raise ValueError('invalid_reference_request')
        return self._mutate(actor, space, source, 'cross_space_ref.create',
            {'source': source, 'target': target, 'relation_kind': relation_kind}, idempotency_key, target)

    def delete(self, actor, *, space_id, source, reference_id, idempotency_key):
        space, source = space_uuid(space_id), endpoint(source)
        return self._mutate(actor, space, source, 'cross_space_ref.delete',
            {'source': source, 'reference_id': str(space_uuid(reference_id))}, idempotency_key)

    def list(self, actor, *, space_id, source, target_space_ids, limit=50, after=None):
        space, source = space_uuid(space_id), endpoint(source)
        if not isinstance(target_space_ids, list) or not 1 <= len(target_space_ids) <= 10:
            raise ValueError('invalid_space_selection')
        targets = [space_uuid(value) for value in target_space_ids]
        if len(set(targets)) != len(targets):
            raise ValueError('invalid_space_selection')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('invalid_paging')
        after = None if after is None else space_uuid(after)
        with self.database.engine.begin() as c:
            hold_authority(c)
            _, selected = self._source_actor(c, actor, space, targets, Role.READER, read=True)
            if not self._available(c, space, source):
                raise ReferenceNotFound()
            rows = c.execute(_LIST, {'space': space, 'kind': source['kind'], 'source': source['id'],
                'targets': [identifier for identifier in targets if identifier in selected],
                'after': after, 'limit': limit+1}).mappings().all()
            self.access.checked_actor(c, actor).require(Role.READER)
            result = snapshot({'references': [dict(row) for row in rows[:limit]],
                'next_after': rows[limit-1]['id'] if len(rows) > limit else None})
            if len(json.dumps(result, ensure_ascii=True).encode()) > 256 * 1024:
                raise ValueError('reference_response_too_large')
            return result
