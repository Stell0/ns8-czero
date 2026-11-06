# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Metadata-only compilation coordination. Reasoning and publication are external/M2."""
from datetime import datetime, timezone
import json
import unicodedata
from uuid import uuid4

from sqlalchemy import text

from .compilation_schema import (ACTIVE, PROPOSAL, SOURCE_SELECTION, checked,
    defaults, digest, key, policy as normalize_policy)
from .compilation_runs import CompilationRuns
from .current_content import ContentSuperseded
from .documents import DocumentService, SNAPSHOT, RECEIPT
from .identity import PermissionDenied, Role
from .object_schema import bounded_json
from .receipts import mutate, snapshot
from .sources import SourceConflict, SourceNotFound, _uuid
from .spaces import SpaceBound, require_scope
from .wiki import KnowledgeConflict, KnowledgeNotFound


class CompilationConflict(KnowledgeConflict):
    pass


class CompilationNotFound(KnowledgeNotFound):
    pass


class CompilationDisabled(PermissionDenied):
    pass


class CompilationNotReady(Exception):
    pass


_META = """encode(sha256(convert_to(jsonb_build_object(
    'canonical_url',COALESCE(s.metadata->'canonical_url','null'::jsonb),
    'original_url',COALESCE(s.metadata->'original_url','null'::jsonb),
    'provenance',COALESCE(s.metadata->'provenance','{}'::jsonb))::text,'UTF8')),'hex')"""
# Identity-only freshness: body integrity is rechecked by the trusted reader on writes.
_SOURCE_FRESH = """true
    AND ((NOT cs.multipart AND cs.logical_document_id=CAST(cs.parts->0->>'source_id' AS uuid)
        AND cs.observed_revision=CAST(cs.parts->0->>'version_id' AS uuid))
      OR (cs.multipart AND EXISTS(SELECT 1 FROM c0_objects parent WHERE parent.space_id=cs.space_id
        AND parent.id=cs.logical_document_id AND parent.type_name='c0_project_source_snapshot_v1'
        AND parent.revision=cs.source_number)))
    AND NOT EXISTS(SELECT 1 FROM jsonb_to_recordset(cs.parts) AS part(
        source_id uuid,version_id uuid,document_id uuid,content_hash text,text_hash text,receipt_id uuid,receipt_revision integer,metadata_hash text)
      LEFT JOIN c0_sources s ON s.space_id=cs.space_id AND s.id=part.source_id
      LEFT JOIN c0_source_versions v ON v.space_id=cs.space_id AND v.id=part.version_id AND v.source_id=part.source_id
      LEFT JOIN c0_documents d ON d.space_id=cs.space_id AND d.id=part.document_id AND d.version_id=v.id
      LEFT JOIN c0_objects r ON r.space_id=cs.space_id AND r.id=part.receipt_id AND r.type_name='c0_project_source_part_v1'
      WHERE s.id IS NULL OR s.deleted OR s.current_version_id IS DISTINCT FROM part.version_id
        OR part.metadata_hash IS DISTINCT FROM (""" + _META + """)
        OR v.state IS DISTINCT FROM 'ready' OR v.content_hash IS DISTINCT FROM part.content_hash
        OR d.id IS NULL OR d.text_hash IS DISTINCT FROM part.text_hash
        OR (cs.multipart AND (r.id IS NULL OR r.revision IS DISTINCT FROM part.receipt_revision)))"""
_DEP_FRESH = """cs.observed_revision=dep.source_revision AND cs.text_hash=dep.text_hash
    AND cs.metadata_hash=dep.metadata_hash AND cs.parts_hash=dep.parts_hash
    AND cs.profile_version=dep.profile_version AND (""" + _SOURCE_FRESH + """)
    AND EXISTS(SELECT 1 FROM c0_wiki_pages p JOIN c0_wiki_revisions r
      ON r.space_id=p.space_id AND r.page_id=p.id AND r.number=p.revision
      WHERE p.space_id=dep.space_id AND dep.target_kind='page' AND p.id=dep.target_id AND NOT p.deleted
        AND p.revision=dep.target_revision AND r.id=dep.target_content_id AND r.content_hash=dep.target_hash)
    AND (dep.chunk_id IS NULL OR EXISTS(SELECT 1 FROM c0_chunks c
      WHERE c.space_id=dep.space_id AND c.id=dep.chunk_id AND c.document_id=dep.document_id
        AND c.content_hash=dep.chunk_hash AND c.start_offset=dep.start_offset AND c.end_offset=dep.end_offset))"""


def _json(value):
    return json.dumps(snapshot(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _paging(limit, after):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('invalid_compilation_page')
    return _uuid(after) if after is not None else None


class CompilationService(CompilationRuns, SpaceBound):
    """Explicit selected space and current persisted authority on every operation."""
    conflict = CompilationConflict
    notfound = CompilationNotFound
    disabled = CompilationDisabled
    notready = CompilationNotReady
    def __init__(self, database, access, *, clock=None):
        self.database, self.access = database, access
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _authorize(self, connection, actor, minimum=Role.READER):
        if self._space_id is None:
            raise ValueError('explicit_compilation_space_required')
        return self._space_authorize(connection, actor, minimum)

    def _policy(self, connection):
        row = connection.execute(text('SELECT * FROM c0_compilation_policies WHERE space_id=:space'),
            {'space': self._space_id}).mappings().one_or_none()
        return dict(row) if row else {'space_id': self._space_id, 'revision': 0, 'data': defaults()}

    def policy(self, actor):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return snapshot(self._policy(connection))

    def _enabled(self, connection, expected=None):
        result = self._policy(connection)
        if not result['data']['enabled']:
            raise CompilationDisabled()
        if expected is not None and result['revision'] != expected:
            raise CompilationConflict()
        return result

    def _mutate(self, actor, operation, payload, request_key, execute, *, admin=False, lease=None, guard=None):
        bounded_json(payload, maximum=65536)
        request_hash = digest(key(request_key))
        fingerprint = digest([operation, payload])
        def authorize(connection, captured, minimum):
            current = self._authorize(connection, captured, Role.ADMIN if admin else Role.EDITOR)
            if not admin:
                require_scope(current, Role.READER)
                self._enabled(connection, payload.get('policy_revision'))
            if lease is not None:
                self._lease(connection, current, lease, replay_key=request_hash)
            if admin:
                previous_policy = connection.execute(text('''SELECT policy_revision FROM c0_compilation_events
                    WHERE space_id=:space AND actor_id=:actor AND request_key=:key AND operation='policy_set' '''),
                    {'space': self._space_id, 'actor': current.user_id, 'key': request_hash}).scalar_one_or_none()
                if previous_policy is not None and previous_policy != self._policy(connection)['revision']:
                    raise CompilationConflict()
            # A claim receipt cannot revive its expired/transferred fence.
            previous = connection.execute(text('''SELECT run_id,fencing_generation,metrics FROM c0_compilation_events
                WHERE space_id=:space AND actor_id=:actor AND request_key=:key AND operation='run_claim' '''),
                {'space': self._space_id, 'actor': current.user_id, 'key': request_hash}).mappings().one_or_none()
            if operation == 'run_claim' and previous and previous['metrics'].get('lease_issued'):
                self._lease(connection, current, {'run_id': str(previous['run_id']),
                    'lease_owner': payload['lease_owner'], 'fencing_generation': previous['fencing_generation']})
                run = self._run(connection, previous['run_id'])
                for task_id in run['data']['task_ids']:
                    task = self._task(connection, task_id)
                    self._sources(connection, task['source_bindings'])
                    self._target(connection, task['target'])
            if guard:
                guard(connection, current)
            return current
        def checked_execute(connection, current):
            value = execute(connection, current)
            self._event(connection, current, request_hash, fingerprint, operation, value['outcome'],
                run=value.get('run'), task=value.get('task'), metrics={'lease_issued': bool(value.get('lease'))})
            return value
        return mutate(self.database, authorize, actor, 'compilation.' + operation, payload,
            'compilation:' + request_hash, checked_execute, conflict=CompilationConflict, lock_objects=True)

    def _event(self, connection, actor, request_hash, fingerprint, operation, outcome, *,
               run=None, task=None, kind=None, metrics=None, call_id=None):
        metrics = bounded_json(metrics or {}, maximum=16384)
        connection.execute(text('''INSERT INTO c0_compilation_events(
            id,space_id,actor_id,request_key,fingerprint,operation,kind,outcome,run_id,task_id,
            policy_revision,fencing_generation,call_id,day_budget_id,week_budget_id,metrics,created_at)
            VALUES(:id,:space,:actor,:key,:fingerprint,:operation,:kind,:outcome,:run,:task,:policy,:fence,
                :call,:day,:week,CAST(:metrics AS jsonb),:now)'''),
            {'id': uuid4(), 'space': self._space_id, 'actor': actor.user_id, 'key': request_hash,
             'fingerprint': fingerprint, 'operation': operation, 'kind': kind or operation, 'outcome': outcome,
             'run': run['id'] if run else None, 'task': task['id'] if task else None,
             'policy': run['policy_revision'] if run else task['policy_revision'] if task else self._policy(connection)['revision'],
             'fence': run['fencing_generation'] if run else 0, 'call': call_id,
             'day': run.get('day_budget_id') if run else None, 'week': run.get('week_budget_id') if run else None,
             'metrics': _json(metrics), 'now': self.clock()})

    def configure(self, actor, data, *, expected_revision, authorization_ref='', idempotency_key):
        data = normalize_policy(data)
        if type(expected_revision) is not int or not 0 <= expected_revision < 2147483647:
            raise ValueError('invalid_compilation_revision')
        if authorization_ref:
            key(authorization_ref)
        payload = {'data': data, 'expected_revision': expected_revision,
            'authorization_hash': digest(authorization_ref) if authorization_ref else ''}
        def execute(connection, current):
            old = self._policy(connection)
            if old['revision'] != expected_revision:
                raise CompilationConflict()
            wider = (data['enabled'] and not old['data']['enabled'] or
                data['retrieval_feedback'] and not old['data']['retrieval_feedback'] or
                data['publication_mode'] == 'automatic_supported' and old['data']['publication_mode'] != 'automatic_supported')
            if wider and not authorization_ref:
                raise ValueError('compilation_enablement_reference_required')
            if old['revision'] and data == old['data']:
                return {'outcome': 'unchanged', 'policy': snapshot(old)}
            row = connection.execute(text('''INSERT INTO c0_compilation_policies(space_id,revision,data,actor_id,updated_at)
                VALUES(:space,1,CAST(:data AS jsonb),:actor,:now) ON CONFLICT(space_id) DO UPDATE
                SET revision=c0_compilation_policies.revision+1,data=EXCLUDED.data,actor_id=EXCLUDED.actor_id,
                    updated_at=EXCLUDED.updated_at RETURNING *'''),
                {'space': self._space_id, 'data': _json(data), 'actor': current.user_id, 'now': self.clock()}).mappings().one()
            return {'outcome': 'saved', 'policy': snapshot(dict(row))}
        return self._mutate(actor, 'policy_set', payload, idempotency_key, execute, admin=True)

    def _source(self, connection, selection):
        selection = checked(SOURCE_SELECTION, selection)
        reader = DocumentService(self.database, self.access).in_space(self._space_id)
        try:
            doc = reader._read(connection, selection['logical_document_id'], revision_id=selection['revision_id'])
        except SourceNotFound:
            incomplete = connection.execute(text('''SELECT 1 FROM c0_sources s JOIN c0_source_versions v
                ON v.space_id=s.space_id AND v.source_id=s.id WHERE s.space_id=:space
                AND s.id=:logical AND v.id=:revision AND NOT s.deleted AND v.state<>'ready' '''),
                {'space': self._space_id, 'logical': selection['logical_document_id'],
                 'revision': selection['revision_id']}).scalar_one_or_none()
            if incomplete:
                raise CompilationNotReady() from None
            raise CompilationNotFound() from None
        except SourceConflict:
            raise CompilationConflict() from None
        if str(doc['id']) != selection['logical_document_id']:
            raise ValueError('explicit_logical_document_required')
        if doc['state'] != 'ready' or doc['deleted']:
            raise CompilationNotReady()
        parts = snapshot(doc['parts'])
        source_number = doc['number']
        if doc['multipart']:
            parent = connection.execute(text('SELECT revision,data FROM c0_objects WHERE space_id=:space AND id=:id AND type_name=:type'),
                {'space': self._space_id, 'id': doc['id'], 'type': SNAPSHOT}).mappings().one()
            source_number = parent['revision']
            receipts = list(connection.execute(text('''SELECT id,revision,data FROM c0_objects
                WHERE space_id=:space AND type_name=:type AND id=ANY(CAST(:ids AS uuid[]))'''),
                {'space': self._space_id, 'type': RECEIPT, 'ids': parent['data']['part_receipt_ids']}).mappings())
            for index, part in enumerate(parts, 1):
                receipt = next((r for r in receipts if r['data']['part_number'] == index
                    and r['data']['source_id'] == part['source_id'] and r['data']['version_id'] == part['version_id']), None)
                if receipt is None:
                    raise CompilationConflict()
                part.update(receipt_id=str(receipt['id']), receipt_revision=receipt['revision'])
        rows = list(connection.execute(text('''SELECT c.id AS chunk_id,c.document_id,c.content_hash,
            c.start_offset,c.end_offset,d.version_id,v.source_id,v.content_hash AS source_hash
            FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id AND d.space_id=c.space_id
            JOIN c0_source_versions v ON v.id=d.version_id AND v.space_id=d.space_id
            WHERE c.space_id=:space AND c.id=ANY(CAST(:ids AS uuid[]))
              AND c.body=substring(d.body FROM c.start_offset+1 FOR c.end_offset-c.start_offset)
              AND c.content_hash=encode(sha256(convert_to(c.body,'UTF8')),'hex')'''),
            {'space': self._space_id, 'ids': selection['chunk_ids']}).mappings())
        by_id = {str(row['chunk_id']): snapshot(dict(row)) for row in rows}
        if len(by_id) != len(selection['chunk_ids']):
            # Exact retired chunks never acquire new text under the same identity.
            from .current_content import check_retired
            for identifier in selection['chunk_ids']:
                check_retired(connection, self._space_id, 'chunk', _uuid(identifier))
            raise CompilationNotFound()
        chunks = [by_id[value] for value in sorted(selection['chunk_ids'])]
        if any(not any(c['version_id'] == p['version_id'] and c['document_id'] == p['document_id']
                       and c['source_id'] == p['source_id'] for p in parts) for c in chunks):
            raise CompilationNotFound()
        for part in parts:
            part['metadata_hash'] = connection.execute(text('SELECT ' + _META + ' FROM c0_sources s WHERE s.space_id=:space AND s.id=:id'),
                {'space': self._space_id, 'id': part['source_id']}).scalar_one()
        metadata_hash = digest([part['metadata_hash'] for part in parts])
        public = {'logical_document_id': str(doc['id']), 'revision_id': str(doc['revision_id']),
            'text_hash': doc['text_hash'], 'content_hash': doc['content_hash'], 'metadata_hash': metadata_hash,
            'parts_hash': digest(parts), 'chunks': chunks}
        return public, {'parts': parts, 'source_number': source_number, 'multipart': doc['multipart']}, doc

    def source_bindings(self, actor, selections):
        if type(selections) is not list or not 1 <= len(selections) <= 3:
            raise ValueError('invalid_compilation_selection')
        with self.database.engine.begin() as connection:
            connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            self._authorize(connection, actor)
            values = [self._source(connection, s)[0] for s in selections]
            self._check_bindings(values)
            return {'space_id': str(self._space_id), 'source_bindings': values}

    @staticmethod
    def _check_bindings(values):
        if len({s['logical_document_id'] for s in values}) != len(values) or sum(len(s['chunks']) for s in values) > 32:
            raise ValueError('duplicate_or_excess_compilation_support')
        bounded_json(values, maximum=16384, object_root=False)

    def _sources(self, connection, bindings):
        self._check_bindings(bindings)
        actual = []
        for expected in bindings:
            value = self._source(connection, {'logical_document_id': expected['logical_document_id'],
                'revision_id': expected['revision_id'], 'chunk_ids': [c['chunk_id'] for c in expected['chunks']]})
            if value[0] != expected:
                raise CompilationConflict()
            actual.append(value)
        return actual

    def _target(self, connection, target):
        if not target:
            return
        from .current_content import check_retired
        check_retired(connection, self._space_id, 'wiki_revision', _uuid(target['content_id']))
        row = connection.execute(text('''SELECT p.revision,r.id,r.content_hash FROM c0_wiki_pages p
            JOIN c0_wiki_revisions r ON r.space_id=p.space_id AND r.page_id=p.id AND r.number=p.revision
            WHERE p.space_id=:space AND p.id=:id AND NOT p.deleted'''),
            {'space': self._space_id, 'id': _uuid(target['id'])}).mappings().one_or_none()
        if row is None:
            raise CompilationNotFound()
        if row['revision'] != target['revision'] or str(row['id']) != target['content_id'] or row['content_hash'] != target['content_hash']:
            raise CompilationConflict()

    def _observe(self, connection, task, actual):
        for source, private, _ in actual:
            connection.execute(text('''INSERT INTO c0_compilation_sources(space_id,logical_document_id,profile_id,
                profile_version,observed_revision,source_number,multipart,text_hash,content_hash,metadata_hash,parts_hash,
                parts,task_id,state,updated_at) VALUES(:space,:logical,:profile,:version,:revision,:number,:multipart,
                :text,:content,:meta,:hash,CAST(:parts AS jsonb),:task,'observed',:now)
                ON CONFLICT(space_id,logical_document_id,profile_id) DO UPDATE SET
                profile_version=EXCLUDED.profile_version,observed_revision=EXCLUDED.observed_revision,
                source_number=EXCLUDED.source_number,multipart=EXCLUDED.multipart,text_hash=EXCLUDED.text_hash,
                content_hash=EXCLUDED.content_hash,metadata_hash=EXCLUDED.metadata_hash,parts_hash=EXCLUDED.parts_hash,
                parts=EXCLUDED.parts,task_id=EXCLUDED.task_id,state='observed',updated_at=EXCLUDED.updated_at'''),
                {'space': self._space_id, 'logical': source['logical_document_id'], 'profile': task['profile_id'],
                 'version': task['profile_version'], 'revision': source['revision_id'], 'number': private['source_number'],
                 'multipart': private['multipart'], 'text': source['text_hash'], 'content': source['content_hash'],
                 'meta': source['metadata_hash'], 'hash': source['parts_hash'], 'parts': _json(private['parts']),
                 'task': task['id'], 'now': self.clock()})
            if not task['target']:
                continue
            entries = [dict(p, chunk_id=None, chunk_hash=None, source_hash=p['content_hash']) for p in private['parts']]
            entries += [dict(c, chunk_hash=c['content_hash']) for c in source['chunks']]
            for entry in entries:
                target = task['target']
                connection.execute(text('''INSERT INTO c0_compilation_dependencies(id,space_id,target_kind,target_id,
                    target_revision,target_content_id,target_hash,logical_document_id,source_revision,metadata_hash,
                    parts_hash,text_hash,source_id,version_id,document_id,chunk_id,evidence_identity,chunk_hash,source_hash,
                    start_offset,end_offset,profile_id,profile_version,task_id,state,updated_at)
                    VALUES(:id,:space,'page',:target,:target_revision,:target_content,:target_hash,:logical,:revision,
                        :meta,:parts_hash,:text,:source,:version,:document,:chunk,:evidence,:chunk_hash,:source_hash,
                        :start,:end,:profile,:profile_version,:task,'observed',:now)
                    ON CONFLICT(space_id,target_kind,target_id,logical_document_id,evidence_identity) DO UPDATE SET
                        target_revision=EXCLUDED.target_revision,target_content_id=EXCLUDED.target_content_id,
                        target_hash=EXCLUDED.target_hash,source_revision=EXCLUDED.source_revision,
                        metadata_hash=EXCLUDED.metadata_hash,parts_hash=EXCLUDED.parts_hash,text_hash=EXCLUDED.text_hash,
                        profile_version=EXCLUDED.profile_version,task_id=EXCLUDED.task_id,state='observed',updated_at=EXCLUDED.updated_at'''),
                    {'id': uuid4(), 'space': self._space_id, 'target': target['id'], 'target_revision': target['revision'],
                     'target_content': target['content_id'], 'target_hash': target['content_hash'],
                     'logical': source['logical_document_id'], 'revision': source['revision_id'], 'meta': source['metadata_hash'],
                     'parts_hash': source['parts_hash'], 'text': source['text_hash'], 'source': entry['source_id'],
                     'version': entry['version_id'], 'document': entry['document_id'], 'chunk': entry['chunk_id'],
                     'evidence': digest([entry['version_id'], entry['document_id'], entry['chunk_id']]),
                     'chunk_hash': entry['chunk_hash'], 'source_hash': entry['source_hash'],
                     'start': entry.get('start_offset') if entry['chunk_id'] else None,
                     'end': entry.get('end_offset') if entry['chunk_id'] else None,
                     'profile': task['profile_id'], 'profile_version': task['profile_version'], 'task': task['id'], 'now': self.clock()})

    def propose(self, actor, data, *, idempotency_key):
        data = checked(PROPOSAL, data)
        data.setdefault('target', None); data.setdefault('source_label', '')
        for binding in data['source_bindings']:
            binding['chunks'].sort(key=lambda c: c['chunk_id'])
        data['source_bindings'].sort(key=lambda s: s['logical_document_id'])
        self._check_bindings(data['source_bindings'])
        def guard(connection, current):
            config = self._enabled(connection, data['policy_revision'])['data']
            if 'page' not in config['allowed_target_kinds']:
                raise CompilationDisabled()
            if data['origin'] == 'retrieval' and not config['retrieval_feedback']:
                raise CompilationDisabled()
            self._sources(connection, data['source_bindings'])
            self._target(connection, data['target'])
        def execute(connection, current):
            config = self._enabled(connection)['data']
            actual = self._sources(connection, data['source_bindings'])
            label = data['source_label']
            normalize = lambda s: unicodedata.normalize('NFKC', s).casefold()
            if label and (any(ord(c) < 32 for c in label) or not any(
                    normalize(label) in normalize(doc['title']) or normalize(label) in normalize(doc['body']) for _, _, doc in actual)):
                raise ValueError('source_derived_compilation_label_required')
            topic = 'page:' + data['target']['id'] if data['target'] else data['topic_key']
            group = 'review' if data['reason'] in ('contradiction', 'applicability_gap') else 'improvement'
            target_key = 'page:' + data['target']['id'] if data['target'] else 'new:' + topic
            family = digest([str(self._space_id), config['profile_id'], topic, target_key])
            identity = digest([str(self._space_id), config['profile_id'], config['profile_version'], group, topic,
                sorted(data['source_bindings'], key=lambda s: s['logical_document_id']), target_key])
            previous = connection.execute(text('SELECT * FROM c0_compilation_tasks WHERE space_id=:space AND dedup_key=:key'),
                {'space': self._space_id, 'key': identity}).mappings().one_or_none()
            if previous:
                if previous['target'] != (data['target'] or {}):
                    # A new authored revision is a review hold, not another concept or an overwrite.
                    previous = connection.execute(text("""UPDATE c0_compilation_tasks SET target=CAST(:target AS jsonb),
                        state='needs_review',plan_hash=NULL,revision=revision+1,error_code='concurrent_edit',updated_at=:now
                        WHERE space_id=:space AND id=:id RETURNING *"""),
                        {'space': self._space_id, 'id': previous['id'], 'target': _json(data['target'] or {}),
                         'now': self.clock()}).mappings().one()
                    self._observe(connection, dict(previous), actual)
                    return {'outcome': 'needs_review', 'task': snapshot(dict(previous))}
                outcome = 'merged' if previous['state'] in ACTIVE else previous['state']
                return {'outcome': outcome, 'task': snapshot(dict(previous))}
            old = connection.execute(text('''SELECT * FROM c0_compilation_tasks WHERE space_id=:space AND family_key=:family
                ORDER BY created_at DESC,id DESC LIMIT 1'''), {'space': self._space_id, 'family': family}).mappings().one_or_none()
            count = connection.execute(text('SELECT count(*) FROM c0_compilation_tasks WHERE space_id=:space AND state=ANY(:states)'),
                {'space': self._space_id, 'states': list(ACTIVE)}).scalar_one()
            if count >= config['max_outstanding_tasks'] and not (old and old['state'] in ACTIVE):
                return {'outcome': 'deferred_capacity'}
            if old and old['state'] in ACTIVE:
                connection.execute(text("UPDATE c0_compilation_tasks SET state='superseded',revision=revision+1,updated_at=:now WHERE space_id=:space AND id=:id"),
                    {'space': self._space_id, 'id': old['id'], 'now': self.clock()})
            state = 'needs_review' if data['reason'] in ('contradiction', 'applicability_gap') else 'queued'
            row = connection.execute(text('''INSERT INTO c0_compilation_tasks(id,space_id,profile_id,profile_version,
                topic_key,target_key,reason,origin,dedup_key,family_key,source_bindings,target,source_label,state,
                policy_revision,predecessor_id,prior_attempts,not_before,created_at,updated_at)
                VALUES(:id,:space,:profile,:version,:topic,:target_key,:reason,:origin,:dedup,:family,
                    CAST(:sources AS jsonb),CAST(:target AS jsonb),:label,:state,:policy,:previous,:prior,:now,:now,:now)
                RETURNING *'''),
                {'id': uuid4(), 'space': self._space_id, 'profile': config['profile_id'], 'version': config['profile_version'],
                 'topic': topic, 'target_key': target_key, 'reason': data['reason'], 'origin': data['origin'],
                 'dedup': identity, 'family': family, 'sources': _json(sorted(data['source_bindings'], key=lambda s: s['logical_document_id'])),
                 'target': _json(data['target'] or {}), 'label': label, 'state': state, 'policy': data['policy_revision'],
                 'previous': old['id'] if old else None, 'prior': old['attempts'] + old['prior_attempts'] if old else 0,
                 'now': self.clock()}).mappings().one()
            task = dict(row)
            self._observe(connection, task, actual)
            return {'outcome': 'needs_review' if state == 'needs_review' else 'queued', 'task': snapshot(task)}
        return self._mutate(actor, 'propose', data, idempotency_key, execute, guard=guard)

    def _task(self, connection, identifier):
        row = connection.execute(text('SELECT * FROM c0_compilation_tasks WHERE space_id=:space AND id=:id'),
            {'space': self._space_id, 'id': _uuid(identifier)}).mappings().one_or_none()
        if row is None:
            raise CompilationNotFound()
        return dict(row)

    def get_task(self, actor, task_id):
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return snapshot(self._task(connection, task_id))

    def list_tasks(self, actor, *, state=None, topic_key=None, limit=50, after=None):
        from .compilation_schema import STATES
        after = _paging(limit, after)
        if state is not None and state not in STATES:
            raise ValueError('invalid_compilation_state')
        if topic_key is not None and (type(topic_key) is not str or len(topic_key) > 128):
            raise ValueError('invalid_compilation_topic')
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            rows = list(connection.execute(text('''SELECT * FROM c0_compilation_tasks WHERE space_id=:space
                AND (CAST(:state AS text) IS NULL OR state=:state) AND (CAST(:topic AS text) IS NULL OR topic_key=:topic)
                AND (CAST(:after AS uuid) IS NULL OR id>CAST(:after AS uuid)) ORDER BY id LIMIT :limit'''),
                {'space': self._space_id, 'state': state, 'topic': topic_key, 'after': after, 'limit': limit + 1}).mappings())
            return snapshot({'tasks': [dict(r) for r in rows[:limit]],
                'next_cursor': str(rows[limit - 1]['id']) if len(rows) > limit else None})

    def list_dependencies(self, actor, *, logical_document_id=None, target_id=None, limit=50, after=None):
        after = _paging(limit, after)
        logical = _uuid(logical_document_id) if logical_document_id is not None else None
        target = _uuid(target_id) if target_id is not None else None
        if logical is None and target is None:
            raise ValueError('compilation_dependency_filter_required')
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            rows = list(connection.execute(text('''SELECT dep.*,(''' + _DEP_FRESH + ''') AS identities_current
                FROM c0_compilation_dependencies dep JOIN c0_compilation_sources cs
                  ON cs.space_id=dep.space_id AND cs.logical_document_id=dep.logical_document_id AND cs.profile_id=dep.profile_id
                WHERE dep.space_id=:space AND (CAST(:logical AS uuid) IS NULL OR dep.logical_document_id=CAST(:logical AS uuid))
                  AND (CAST(:target AS uuid) IS NULL OR dep.target_id=CAST(:target AS uuid))
                  AND (CAST(:after AS uuid) IS NULL OR dep.id>CAST(:after AS uuid)) ORDER BY dep.id LIMIT :limit'''),
                {'space': self._space_id, 'logical': logical, 'target': target, 'after': after, 'limit': limit + 1}).mappings())
            return snapshot({'dependencies': [dict(r) for r in rows[:limit]],
                'next_cursor': str(rows[limit - 1]['id']) if len(rows) > limit else None})

    def status(self, actor, *, run_id=None, limit=10):
        _paging(limit, None)
        with self.database.engine.connect() as connection:
            self._authorize(connection, actor)
            tasks = connection.execute(text('SELECT state,count(*) FROM c0_compilation_tasks WHERE space_id=:space GROUP BY state'),
                {'space': self._space_id}).all()
            sources = connection.execute(text('''SELECT count(*) AS observed,
                count(*) FILTER(WHERE state='no_change' AND (''' + _SOURCE_FRESH + ''')) AS assessed_no_change,
                count(*) FILTER(WHERE last_compiled_revision IS NOT NULL) AS compiled,
                count(*) FILTER(WHERE NOT (''' + _SOURCE_FRESH + ''')) AS stale
                FROM c0_compilation_sources cs WHERE cs.space_id=:space'''), {'space': self._space_id}).mappings().one()
            dependencies = connection.execute(text('''SELECT count(*) AS observed,
                count(*) FILTER(WHERE NOT (''' + _DEP_FRESH + ''')) AS stale FROM c0_compilation_dependencies dep
                JOIN c0_compilation_sources cs ON cs.space_id=dep.space_id AND cs.logical_document_id=dep.logical_document_id
                  AND cs.profile_id=dep.profile_id WHERE dep.space_id=:space'''), {'space': self._space_id}).mappings().one()
            runs = connection.execute(text('''SELECT * FROM c0_compilation_runs WHERE space_id=:space AND state<>'budget'
                AND (CAST(:id AS uuid) IS NULL OR id=CAST(:id AS uuid)) ORDER BY updated_at DESC,id LIMIT :limit'''),
                {'space': self._space_id, 'id': _uuid(run_id) if run_id is not None else None, 'limit': limit}).mappings().all()
            if run_id is not None and not runs:
                raise CompilationNotFound()
            budgets = connection.execute(text("SELECT * FROM c0_compilation_runs WHERE space_id=:space AND state='budget' ORDER BY window_end DESC LIMIT 4"), {'space': self._space_id}).mappings().all()
            epoch = self._epoch(connection)
            current_policy = self._policy(connection)
            values = []
            for row in runs:
                value = dict(row, lease_valid=self._live(row, current_policy, epoch))
                value['data'] = json.loads(_json(row['data']))
                for call in value['data']['calls'].values():
                    overdue = call['state'] == 'started' and (not value['lease_valid'] or
                        datetime.fromisoformat(call['deadline']) <= self.clock())
                    call['effective_state'] = 'uncertain' if overdue else call['state']
                values.append(value)
            return snapshot({'space_id': self._space_id, 'policy': current_policy, 'tasks': dict(tasks),
                'sources': dict(sources), 'dependencies': dict(dependencies), 'runs': values,
                'budgets': [dict(b) for b in budgets],
                'complete_corpus_coverage': False, 'publication_supported': False})
