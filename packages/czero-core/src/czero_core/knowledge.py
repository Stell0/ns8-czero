# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Sourced assertions and a bounded PostgreSQL entity graph, without generation."""
from datetime import datetime, timezone
import json
from uuid import uuid4

from sqlalchemy import bindparam, text

from .object_schema import name
from .objects import page
from .sources import SourceService, SourceNotFound, _metadata, _uuid
from .wiki import WikiService, KnowledgeConflict, KnowledgeNotFound, _view

_LINKS = {'object': ('c0_objects', 'object_id'), 'page': ('c0_wiki_pages', 'page_id'),
          'source': ('c0_sources', 'source_id'), 'document': ('c0_documents', 'document_id'),
          'chunk': ('c0_chunks', 'chunk_id')}


def _time(value):
    if value is None: return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('invalid_claim_time')
    return value.astimezone(timezone.utc)


def _revision(value):
    if type(value) is not int or not 1 <= value < 2147483647: raise ValueError('invalid_revision')
    return value


class KnowledgeService(WikiService):
    def reference_resolvers(self):
        def page_reference(connection, actor, key):
            self._authorize(connection, actor)
            try:
                row = self._page(connection, key)
                revision = self._revision(connection, key, row['revision'])
            except KnowledgeNotFound:
                return None
            return {'type_name': 'page', 'data': {'slug': row['slug'], 'title': row['title'],
                'revision': row['revision'], 'content_hash': revision['content_hash'], 'deleted': row['deleted']}}
        def entity_reference(connection, actor, key):
            self._authorize(connection, actor)
            try: row = self._entity(connection, key)
            except KnowledgeNotFound: return None
            return {'type_name': 'entity', 'data': {'kind': row['kind'], 'label': row['label'],
                'revision': row['revision'], 'deleted': row['deleted']}}
        def claim_reference(connection, actor, key):
            self._authorize(connection, actor)
            try: row = self._claim(connection, key)
            except KnowledgeNotFound: return None
            return {'type_name': 'claim', 'data': {'entity_id': str(row['entity_id']), 'predicate': row['predicate'],
                'revision': row['revision'], 'deleted': row['deleted']}}
        return {'page': page_reference, 'entity': entity_reference, 'claim': claim_reference}

    @staticmethod
    def _claim(connection, claim_id, *, lock=False):
        row = connection.execute(text('SELECT * FROM c0_claims WHERE id=:id' + (' FOR UPDATE' if lock else '')),
            {'id': _uuid(claim_id)}).mappings().one_or_none()
        if row is None: raise KnowledgeNotFound()
        return dict(row)

    @staticmethod
    def _evidence(connection, values):
        if not isinstance(values, list) or not 1 <= len(values) <= 32:
            raise ValueError('invalid_evidence')
        keys = sorted(set(_uuid(value) for value in values), key=str)
        for key in keys:
            try: SourceService._citation(connection, key)
            except SourceNotFound: raise KnowledgeNotFound() from None
        return keys

    def create_claim(self, actor, entity_id, predicate, value, *, evidence_chunk_ids, page_id=None,
                     metadata=None, valid_from=None, valid_to=None, idempotency_key):
        entity_id, predicate = _uuid(entity_id), name(predicate)
        page_id = None if page_id is None else _uuid(page_id)
        encoded_value, encoded_meta = _metadata(value), _metadata({} if metadata is None else metadata)
        valid_from, valid_to = _time(valid_from), _time(valid_to)
        if valid_from is not None and valid_to is not None and valid_to < valid_from:
            raise ValueError('invalid_claim_time')
        if not isinstance(evidence_chunk_ids, list) or not 1 <= len(evidence_chunk_ids) <= 32:
            raise ValueError('invalid_evidence')
        keys = sorted(set(str(_uuid(key)) for key in evidence_chunk_ids))
        def execute(connection, current):
            if self._entity(connection, entity_id)['deleted']: raise KnowledgeConflict()
            if page_id is not None and self._page(connection, page_id)['deleted']: raise KnowledgeConflict()
            evidence = self._evidence(connection, keys)
            row = dict(connection.execute(text('''INSERT INTO c0_claims
                (id,entity_id,page_id,predicate,value,metadata,actor_id,valid_from,valid_to)
                VALUES (:id,:entity,:page,:predicate,CAST(:value AS jsonb),CAST(:metadata AS jsonb),:actor,:start,:end) RETURNING *'''),
                {'id': uuid4(), 'entity': entity_id, 'page': page_id, 'predicate': predicate,
                 'value': encoded_value, 'metadata': encoded_meta, 'actor': current.user_id,
                 'start': valid_from, 'end': valid_to}).mappings().one())
            connection.execute(text('INSERT INTO c0_evidence_links(claim_id,chunk_id) VALUES (:claim,:chunk)'),
                [{'claim': row['id'], 'chunk': key} for key in evidence])
            self._event(connection, current, 'claim', row['id'], 1, 'create')
            return row
        return self._mutate(actor, 'claim.create', {'entity_id': str(entity_id), 'page_id': str(page_id) if page_id else None,
            'predicate': predicate, 'value': json.loads(encoded_value), 'metadata': json.loads(encoded_meta),
            'evidence': keys, 'valid_from': valid_from.isoformat() if valid_from else None,
            'valid_to': valid_to.isoformat() if valid_to else None}, idempotency_key, execute)

    def get_claim(self, actor, claim_id):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            row = self._claim(connection, claim_id)
            keys = connection.execute(text('SELECT chunk_id FROM c0_evidence_links WHERE claim_id=:id ORDER BY chunk_id'), {'id': row['id']}).scalars().all()
            return _view({**row, 'evidence': [SourceService._citation(connection, key) for key in keys]})

    def list_claims(self, actor, *, entity_id=None, page_id=None, predicate=None, limit=50, offset=0, include_deleted=False):
        page(limit, offset)
        entity_id = None if entity_id is None else _uuid(entity_id)
        page_id = None if page_id is None else _uuid(page_id)
        predicate = None if predicate is None else name(predicate)
        if type(include_deleted) is not bool: raise ValueError('invalid_filter')
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return _view([dict(row) for row in connection.execute(text('''SELECT * FROM c0_claims
                WHERE (:deleted OR NOT deleted) AND (CAST(:entity AS uuid) IS NULL OR entity_id=:entity)
                AND (CAST(:page AS uuid) IS NULL OR page_id=:page)
                AND (CAST(:predicate AS text) IS NULL OR predicate=:predicate)
                ORDER BY created_at,id LIMIT :limit OFFSET :offset'''),
                {'deleted': include_deleted, 'entity': entity_id, 'page': page_id, 'predicate': predicate,
                 'limit': limit, 'offset': offset}).mappings()])

    def update_claim(self, actor, claim_id, *, expected_revision, metadata, evidence_chunk_ids=None, idempotency_key):
        """Annotate/add provenance; assertion values stay immutable and coexist."""
        claim_id, expected_revision = _uuid(claim_id), _revision(expected_revision)
        encoded = _metadata(metadata)
        if evidence_chunk_ids is not None and (not isinstance(evidence_chunk_ids, list) or not 1 <= len(evidence_chunk_ids) <= 32):
            raise ValueError('invalid_evidence')
        keys = None if evidence_chunk_ids is None else sorted(set(str(_uuid(key)) for key in evidence_chunk_ids))
        def execute(connection, current):
            row = self._claim(connection, claim_id, lock=True)
            if row['deleted'] or row['revision'] != expected_revision: raise KnowledgeConflict()
            if keys is not None:
                existing = connection.execute(text('SELECT chunk_id FROM c0_evidence_links WHERE claim_id=:id'), {'id': claim_id}).scalars().all()
                combined = sorted(set(existing + self._evidence(connection, keys)), key=str)
                if len(combined) > 32: raise ValueError('invalid_evidence')
                connection.execute(text('INSERT INTO c0_evidence_links(claim_id,chunk_id) VALUES (:claim,:chunk) ON CONFLICT DO NOTHING'),
                    [{'claim': claim_id, 'chunk': key} for key in combined])
            row = dict(connection.execute(text('''UPDATE c0_claims SET metadata=CAST(:metadata AS jsonb),revision=revision+1
                WHERE id=:id RETURNING *'''), {'id': claim_id, 'metadata': encoded}).mappings().one())
            self._event(connection, current, 'claim', claim_id, row['revision'], 'update')
            return row
        return self._mutate(actor, 'claim.update', {'id': str(claim_id), 'expected_revision': expected_revision,
            'metadata': json.loads(encoded), 'evidence': keys}, idempotency_key, execute)

    def delete_claim(self, actor, claim_id, *, expected_revision, idempotency_key):
        claim_id, expected_revision = _uuid(claim_id), _revision(expected_revision)
        def execute(connection, current):
            row = self._claim(connection, claim_id, lock=True)
            if row['revision'] != expected_revision: raise KnowledgeConflict()
            if not row['deleted']:
                row = dict(connection.execute(text('UPDATE c0_claims SET deleted=true,revision=revision+1 WHERE id=:id RETURNING *'), {'id': claim_id}).mappings().one())
                self._event(connection, current, 'claim', claim_id, row['revision'], 'delete')
            return row
        return self._mutate(actor, 'claim.delete', {'id': str(claim_id), 'expected_revision': expected_revision}, idempotency_key, execute)

    @staticmethod
    def _relation(connection, relation_id):
        row = connection.execute(text('SELECT * FROM c0_relations WHERE id=:id FOR UPDATE'), {'id': _uuid(relation_id)}).mappings().one_or_none()
        if row is None: raise KnowledgeNotFound()
        return dict(row)

    @staticmethod
    def _degree(connection, entity_id):
        return connection.execute(text('SELECT count(*) FROM c0_relations WHERE NOT deleted AND (source_id=:id OR target_id=:id)'), {'id': entity_id}).scalar_one()

    def add_relation(self, actor, source_id, target_id, kind, *, metadata=None, idempotency_key):
        source_id, target_id, kind = _uuid(source_id), _uuid(target_id), name(kind)
        if source_id == target_id: raise ValueError('invalid_relation')
        encoded = _metadata({} if metadata is None else metadata)
        def execute(connection, current):
            for key in (source_id, target_id):
                if self._entity(connection, key)['deleted']: raise KnowledgeConflict()
            existing = connection.execute(text('SELECT * FROM c0_relations WHERE source_id=:source AND target_id=:target AND kind=:kind'),
                {'source': source_id, 'target': target_id, 'kind': kind}).mappings().one_or_none()
            if existing:
                if existing['deleted'] or existing['metadata'] != json.loads(encoded): raise KnowledgeConflict()
                return dict(existing)
            if any(self._degree(connection, key) >= 32 for key in (source_id, target_id)):
                raise ValueError('relation_degree_limit')
            row = dict(connection.execute(text('''INSERT INTO c0_relations(id,source_id,target_id,kind,metadata,actor_id)
                VALUES (:id,:source,:target,:kind,CAST(:metadata AS jsonb),:actor) RETURNING *'''),
                {'id': uuid4(), 'source': source_id, 'target': target_id, 'kind': kind,
                 'metadata': encoded, 'actor': current.user_id}).mappings().one())
            self._event(connection, current, 'relation', row['id'], 1, 'create')
            return row
        return self._mutate(actor, 'relation.create', {'source': str(source_id), 'target': str(target_id), 'kind': kind,
            'metadata': json.loads(encoded)}, idempotency_key, execute)

    def update_relation(self, actor, relation_id, *, expected_revision, metadata, deleted=False, idempotency_key):
        relation_id, expected_revision = _uuid(relation_id), _revision(expected_revision)
        encoded = _metadata(metadata)
        if type(deleted) is not bool: raise ValueError('invalid_relation')
        def execute(connection, current):
            row = self._relation(connection, relation_id)
            if row['revision'] != expected_revision: raise KnowledgeConflict()
            if not deleted:
                for key in (row['source_id'], row['target_id']):
                    if self._entity(connection, key)['deleted']: raise KnowledgeConflict()
                    if row['deleted'] and self._degree(connection, key) >= 32: raise ValueError('relation_degree_limit')
            row = dict(connection.execute(text('''UPDATE c0_relations SET metadata=CAST(:metadata AS jsonb),
                deleted=:deleted,revision=revision+1 WHERE id=:id RETURNING *'''),
                {'id': relation_id, 'metadata': encoded, 'deleted': deleted}).mappings().one())
            self._event(connection, current, 'relation', relation_id, row['revision'], 'delete' if deleted else 'update')
            return row
        return self._mutate(actor, 'relation.update', {'id': str(relation_id), 'expected_revision': expected_revision,
            'metadata': json.loads(encoded), 'deleted': deleted}, idempotency_key, execute)

    def list_relations(self, actor, entity_id, *, limit=50, offset=0, include_deleted=False):
        page(limit, offset)
        if type(include_deleted) is not bool: raise ValueError('invalid_filter')
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor); self._entity(connection, entity_id)
            return _view([dict(row) for row in connection.execute(text('''SELECT * FROM c0_relations
                WHERE (:deleted OR NOT deleted) AND (source_id=:id OR target_id=:id)
                ORDER BY created_at,id LIMIT :limit OFFSET :offset'''),
                {'deleted': include_deleted, 'id': _uuid(entity_id), 'limit': limit, 'offset': offset}).mappings()])

    @staticmethod
    def _link_target(connection, kind, resource_id):
        if kind not in _LINKS: raise ValueError('invalid_reference_kind')
        table, column = _LINKS[kind]
        # Identifiers are trusted constants; request data is only bound UUIDs.
        row = connection.execute(text('SELECT * FROM ' + table + ' WHERE id=:id'), {'id': _uuid(resource_id)}).mappings().one_or_none()
        if row is None: raise KnowledgeNotFound()
        if kind == 'object': label = row['type_name']
        elif kind in ('page', 'source'): label = row['title']
        else: label = kind + ' ' + str(row['id'])
        return column, label

    def link_entity(self, actor, entity_id, target_kind, target_id, *, idempotency_key):
        entity_id, target_id = _uuid(entity_id), _uuid(target_id)
        if target_kind not in _LINKS: raise ValueError('invalid_reference_kind')
        def execute(connection, current):
            entity = self._entity(connection, entity_id)
            if entity['deleted']: raise KnowledgeConflict()
            column, label = self._link_target(connection, target_kind, target_id)
            existing = connection.execute(text('SELECT * FROM c0_entity_links WHERE entity_id=:entity AND target_kind=:kind AND target_id=:target'),
                {'entity': entity_id, 'kind': target_kind, 'target': target_id}).mappings().one_or_none()
            if existing: return dict(existing)
            if connection.execute(text('SELECT count(*) FROM c0_entity_links WHERE entity_id=:id'), {'id': entity_id}).scalar_one() >= 32:
                raise ValueError('reference_limit')
            row = dict(connection.execute(text('INSERT INTO c0_entity_links(id,entity_id,target_kind,target_id,label_snapshot,' + column + ',actor_id) '
                'VALUES (:id,:entity,:kind,:target,:label,:target,:actor) RETURNING *'),
                {'id': uuid4(), 'entity': entity_id, 'kind': target_kind, 'target': target_id,
                 'label': label, 'actor': current.user_id}).mappings().one())
            self._event(connection, current, 'entity', entity_id, entity['revision'], 'reference_add')
            return row
        return self._mutate(actor, 'entity.reference_add', {'entity': str(entity_id), 'kind': target_kind,
            'target': str(target_id)}, idempotency_key, execute)

    def entity_links(self, actor, entity_id, *, limit=50, offset=0):
        page(limit, offset)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor); self._entity(connection, entity_id)
            rows = connection.execute(text('SELECT * FROM c0_entity_links WHERE entity_id=:id ORDER BY created_at,id LIMIT :limit OFFSET :offset'),
                {'id': _uuid(entity_id), 'limit': limit, 'offset': offset}).mappings().all()
            return _view([{**dict(row), 'missing': row[_LINKS[row['target_kind']][1]] is None} for row in rows])

    def unlink_entity(self, actor, entity_id, link_id, *, idempotency_key):
        entity_id, link_id = _uuid(entity_id), _uuid(link_id)
        def execute(connection, current):
            row = self._entity(connection, entity_id)
            deleted = connection.execute(text('DELETE FROM c0_entity_links WHERE entity_id=:entity AND id=:id RETURNING id'),
                {'entity': entity_id, 'id': link_id}).scalar_one_or_none()
            if deleted is None: raise KnowledgeNotFound()
            self._event(connection, current, 'entity', entity_id, row['revision'], 'reference_remove')
            return {'id': deleted, 'deleted': True}
        return self._mutate(actor, 'entity.reference_remove', {'entity': str(entity_id), 'id': str(link_id)}, idempotency_key, execute)

    def graph(self, actor, entity_id, *, depth=1, limit=50, direction='both'):
        page(limit)
        if type(depth) is not int or not 1 <= depth <= 3 or direction not in ('out', 'in', 'both'):
            raise ValueError('invalid_graph_limits')
        entity_id = _uuid(entity_id)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            if self._entity(connection, entity_id)['deleted']: raise KnowledgeNotFound()
            rows = connection.execute(text('''WITH RECURSIVE reachable(entity_id,depth) AS (
                SELECT CAST(:root AS uuid),0
                UNION
                SELECT CASE WHEN r.source_id=q.entity_id THEN r.target_id ELSE r.source_id END,q.depth+1
                FROM reachable q JOIN c0_relations r ON NOT r.deleted AND
                    ((:outward AND r.source_id=q.entity_id) OR (:inward AND r.target_id=q.entity_id))
                JOIN c0_entities next ON next.id=CASE WHEN r.source_id=q.entity_id THEN r.target_id ELSE r.source_id END
                WHERE q.depth<:depth AND NOT next.deleted)
                SELECT e.*,min(q.depth) AS depth FROM reachable q JOIN c0_entities e ON e.id=q.entity_id
                GROUP BY e.id ORDER BY min(q.depth),e.id LIMIT :limit'''),
                {'root': entity_id, 'outward': direction != 'in', 'inward': direction != 'out',
                 'depth': depth, 'limit': limit + 1}).mappings().all()
            truncated = len(rows) > limit; nodes = [dict(row) for row in rows[:limit]]
            ids = [row['id'] for row in nodes]
            edges = connection.execute(text('''SELECT * FROM c0_relations WHERE NOT deleted
                AND source_id IN :ids AND target_id IN :ids ORDER BY source_id,target_id,kind''').bindparams(bindparam('ids', expanding=True)), {'ids': ids}).mappings().all()
            # Cross-domain references are leaves; do not invent object/Wiki
            # relationship semantics or traverse arbitrary registered code.
            links = connection.execute(text('SELECT * FROM c0_entity_links WHERE entity_id IN :ids ORDER BY entity_id,id LIMIT 101').bindparams(bindparam('ids', expanding=True)),
                {'ids': [row['id'] for row in nodes if row['depth'] < depth]}).mappings().all()
            truncated = truncated or len(links) > 100
            return _view({'root': entity_id, 'depth': depth, 'direction': direction, 'nodes': nodes,
                'relations': [dict(row) for row in edges], 'references': [{**dict(row),
                    'missing': row[_LINKS[row['target_kind']][1]] is None} for row in links[:100]], 'truncated': truncated})
