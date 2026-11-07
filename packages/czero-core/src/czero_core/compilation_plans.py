# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Guarded bundle publication; reasoning, semantic review and model calls stay external."""
import json
import unicodedata

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .annotations import AnnotationService, ContentTarget
from .bundles import KnowledgeBundleService, _operations, _references
from .compilation_content import passage, record_binding
from .compilation_plan_schema import VALIDATE, APPLY, VERIFY
from .compilation_schema import checked, digest
from .identity import Role
from .receipts import MUTATION_LOCK, snapshot
from .sources import SourceService, _uuid
from .spaces import hold_authority, require_scope
from .current_content import content_lock, check_retired
from .object_schema import name
from .health import core_version
from .wiki import WikiService, alias_key, page_slug, markdown
from .sources import _label
from datetime import datetime


# Finite profiles; no request-selected callbacks or operation interpreter.
NAVIGATION = {'wiki.upsert', 'annotation.update'}
KNOWLEDGE = NAVIGATION | {'entity.create','entity.update','entity.alias','entity.link',
    'claim.create','claim.update','relation.create','relation.update'}
KINDS = {'wiki': 'page', 'entity': 'entity', 'claim': 'claim', 'relation': 'relation'}


def managed_slug(space_id, profile_id, topic_key):
    return 'c0-' + digest([str(space_id), profile_id, topic_key])[:32]


def plan_hash(plan):
    # Coordination CAS advances on claim/planned checkpoints; content approval does not.
    return digest({k: v for k, v in plan.items() if k != 'expected_task_revision'})


def _json(value):
    return json.dumps(snapshot(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class CompilationPlans:
    def _publication(self, connection, task_id):
        return connection.execute(text("""SELECT metrics FROM c0_compilation_events WHERE space_id=:space
            AND task_id=:task AND operation='apply' ORDER BY created_at DESC,id DESC LIMIT 1"""),
            {'space': self._space_id, 'task': _uuid(task_id)}).scalar_one_or_none()

    def _read_record(self, connection, kind, identifier):
        wiki = WikiService(self.database, self.access).in_space(self._space_id)
        params = {'space': self._space_id, 'id': _uuid(identifier)}
        if kind == 'page':
            row = wiki._page(connection, identifier)
            if row['deleted']:
                raise self.conflict()
            return snapshot({**row, 'content': wiki._revision(connection, identifier, row['revision'])})
        if kind == 'annotation':
            row = connection.execute(text('''SELECT t.kind,t.target_id,t.content_revision,a.namespace
                FROM c0_annotations a JOIN c0_annotation_targets t ON t.space_id=a.space_id AND t.id=a.anchor_id
                WHERE a.space_id=:space AND a.id=:id'''), params).mappings().one_or_none()
            if row is None:
                raise self.notfound()
            value = AnnotationService(self.database, self.access).in_space(self._space_id)._entry(connection,
                ContentTarget(row['kind'], row['target_id'], row['content_revision']), row['namespace'])
            if not value['target_current'] or value['target_archived'] or value['status'] == 'stale':
                raise self.conflict()
            return snapshot(value)
        table = {'entity':'c0_entities', 'claim':'c0_claims', 'relation':'c0_relations', 'link':'c0_entity_links'}[kind]
        row = connection.execute(text('SELECT * FROM ' + table + ' WHERE space_id=:space AND id=:id'), params).mappings().one_or_none()
        if row is None:
            raise self.notfound()
        value = snapshot(dict(row))
        if value.get('deleted'):
            raise self.conflict()
        if kind == 'entity':
            value['aliases'] = [dict(a) for a in connection.execute(text('''SELECT normalized,label
                FROM c0_entity_aliases WHERE space_id=:space AND entity_id=:id ORDER BY normalized'''), params).mappings()]
        elif kind == 'claim':
            if value['evidence_stale'] or wiki._entity(connection,value['entity_id'])['deleted']:
                raise self.conflict()
            if value['page_id'] and wiki._page(connection,value['page_id'])['deleted']:
                raise self.conflict()
            value['evidence'] = [dict(e) for e in connection.execute(text('''SELECT chunk_id,
                CASE WHEN unavailable THEN 'superseded' ELSE 'current' END AS status
                FROM c0_evidence_links WHERE space_id=:space AND claim_id=:id ORDER BY chunk_id'''), params).mappings()]
        elif kind == 'relation':
            if any(wiki._entity(connection,value[k])['deleted'] for k in ('source_id','target_id')):
                raise self.conflict()
        elif kind == 'link':
            # Compiler links are deliberately restricted to a current primary Wiki page.
            if value['target_kind'] != 'page' or value.get('page_id') is None:
                raise self.conflict()
            if wiki._page(connection,value['target_id'])['deleted'] or wiki._entity(connection,value['entity_id'])['deleted']:
                raise self.conflict()
        return snapshot(value)

    def _locators(self, connection, outputs):
        values = []
        for output in outputs:
            kind = output['kind']
            row = self._read_record(connection, kind, output['id'])
            if kind in ('relation','link'):
                arguments = {'entity_id': row['source_id'] if kind == 'relation' else row['entity_id']}
            elif kind == 'annotation':
                arguments = {'kind':row['target']['kind'], 'target_id':row['target']['id'],
                    'content_revision':row['target']['revision'], 'namespace':row['namespace']}
            else:
                arguments = { {'page':'page_id','entity':'entity_id','claim':'claim_id'}[kind]: output['id'] }
            values.append({'kind': kind, 'id': output['id'], 'arguments': arguments})
        return values

    def _read_outputs(self, connection, outputs):
        for output in outputs:
            if output['kind'] == 'page':
                check_retired(connection,self._space_id,'wiki_revision',_uuid(output['content_id']))
        actual = [record_binding(o['kind'], self._read_record(connection, o['kind'], o['id'])) for o in outputs]
        if actual != outputs:
            raise self.conflict()
        return actual

    def _support_task(self, connection, task):
        self._sources(connection, task['source_bindings'])
        if task['state'] in ('applied_pending_verify', 'succeeded'):
            publication = self._publication(connection, task['id'])
            if not publication:
                raise self.conflict()
            self._read_outputs(connection, publication['records'])
        else:
            self._target(connection, task['target'])

    def _owned_target(self, connection, binding):
        return bool(connection.execute(text('''SELECT 1 FROM c0_compilation_dependencies
            WHERE space_id=:space AND target_kind=:kind AND target_id=:id
              AND managed_target_hash=:hash AND state='current' LIMIT 1'''),
            {'space': self._space_id, 'kind': binding['kind'], 'id': _uuid(binding['id']),
             'hash': binding['record_hash']}).scalar_one_or_none())

    def _candidate_decisions(self, connection, plan, index, candidates, target):
        decisions = [d for d in plan['dedup_decisions'] if d['operation_index'] == index]
        supplied = set()
        review = False
        for decision in decisions:
            candidate = decision['candidate']
            actual = record_binding(candidate['kind'], self._read_record(connection, candidate['kind'], candidate['id']))
            if actual != candidate or candidate['kind'] not in ('page','entity'):
                raise self.conflict()
            supplied.add((candidate['kind'], candidate['id']))
            if decision['comparison'] == 'equivalent' and target['id'] != candidate['id']:
                raise ValueError('duplicate_compilation_concept')
            if decision['comparison'] == 'ambiguous' or decision['rationale'] == 'uncertain':
                review = True
        if not {(kind, str(identifier)) for kind, identifier in candidates} <= supplied:
            review = True
        return review

    def _inspect(self, connection, actor, data):
        plan = data['plan']
        if str(self._space_id) != plan['space_id']:
            raise self.conflict()
        policy = self._enabled(connection, plan['policy_revision'])['data']
        run = self._lease(connection, actor, data['lease'])
        task = self._task(connection, plan['task_id'])
        if (run['revision'] != data['expected_revision'] or task['revision'] != plan['expected_task_revision']
                or task['run_id'] != run['id'] or task['fencing_generation'] != run['fencing_generation']
                or task['state'] not in ('leased','planned') or task['profile_id'] != policy['profile_id']
                or plan['profile_id'] != task['profile_id'] or plan['profile_version'] != task['profile_version']
                or plan['source_bindings'] != task['source_bindings']):
            raise self.conflict()
        actual_sources = self._sources(connection, plan['source_bindings'])
        self._target(connection, task['target'])
        for source_id in {s for d in plan['deferred'] for s in d['source_ids']}:
            if source_id not in {s['logical_document_id'] for s in plan['source_bindings']}:
                raise ValueError('invalid_compilation_deferral')
        calls = [c for c in run['data']['calls'].values() if c['task_id'] == str(task['id'])]
        if any(c['state'] in ('reserved','started','uncertain') for c in calls):
            raise self.conflict()
        usage = plan['usage_reservation_id']
        if usage is not None and (usage not in run['data']['calls'] or
                run['data']['calls'][usage]['task_id'] != str(task['id']) or run['data']['calls'][usage]['state'] != 'returned'):
            raise self.conflict()
        if any(c['state'] == 'returned' for c in calls) and usage is None:
            raise ValueError('compilation_usage_identity_required')
        for budget_id in (run['day_budget_id'], run['week_budget_id']):
            if budget_id is not None:
                budget = self._budget(connection, budget_id)
                if budget['window_end'] <= self.clock() or not self._reservation_fits(connection, budget, task, policy):
                    raise self.conflict()
        operations = plan['operations']
        if not operations:
            if plan['target_bindings'] or plan['dedup_decisions']:
                raise ValueError('invalid_empty_compilation_plan')
            return run, task, actual_sources, [], [], ('deferred' if plan['deferred'] or plan['classification'] == 'unsupported'
                else 'needs_review' if plan['classification'] in ('uncertain','contradictory') else 'no_change')
        operations = _operations(operations)
        allowed = NAVIGATION if policy['profile_id'] == 'sourced-navigation-v1' else KNOWLEDGE
        if any(step['operation'] not in allowed for step in operations):
            raise ValueError('unapproved_compilation_operation')
        if sum(step['operation'] == 'wiki.upsert' for step in operations) != 1 or operations[0]['operation'] != 'wiki.upsert':
            raise ValueError('one_primary_compilation_page_required')
        bindings = {b['operation_index']: b for b in plan['target_bindings']}
        content_indices = {i for i,s in enumerate(operations) if s['operation'] not in ('annotation.update','entity.link','entity.alias')}
        if len(bindings) != len(plan['target_bindings']) or set(bindings) != content_indices:
            raise ValueError('compilation_target_bindings_required')
        if any(d['operation_index'] not in bindings for d in plan['dedup_decisions']):
            raise ValueError('invalid_compilation_dedup_decision')
        evidence_ids = {c['chunk_id'] for s in plan['source_bindings'] for c in s['chunks']}
        review = (policy['publication_mode'] == 'queue_only' or policy['profile_id'] == 'sourced-knowledge-v1'
            or plan['classification'] in ('uncertain','contradictory')
            or any(d['reason'] in ('contradiction','unknown_applicability','duplicate_candidate') for d in plan['deferred'])
            or task['reason'] in ('contradiction','applicability_gap')
            or task['error_code'] in ('unsupported_evidence','concurrent_edit'))
        identities = []
        for index, step in enumerate(operations):
            op, args = step['operation'], step['arguments']
            kind = KINDS.get(op.split('.')[0], 'annotation')
            if kind not in policy['allowed_target_kinds']:
                raise self.disabled()
            if op == 'annotation.update':
                # Only exact, source-bound unverified support. Applicability remains unknown.
                value = args['value']
                if (args['namespace'] != 'verification' or type(value) is not dict
                        or set(value) != {'status','source_references'} or value['status'] != 'unverified'
                        or type(value['source_references']) is not list or not value['source_references']
                        or any(type(r) is not dict or set(r) != {'kind','id'} or r['kind'] != 'chunk'
                            or r['id'] not in evidence_ids for r in value['source_references'])):
                    raise ValueError('unverified_compilation_sources_required')
                if args['expected_revision'] != 0:
                    review = True
                continue
            if op == 'entity.link':
                if (not isinstance(args['entity_id'], dict) and not any(b['kind'] == 'entity' and b['id'] == args['entity_id'] for b in bindings.values())
                        or args['target_kind'] != 'page'):
                    raise ValueError('compilation_page_link_required')
                continue
            if op == 'entity.alias':
                # Existing aliases need an observed entity binding in the same plan.
                if not isinstance(args['entity_id'], dict) and not any(b['kind'] == 'entity' and b['id'] == args['entity_id'] for b in bindings.values()):
                    raise ValueError('compilation_entity_binding_required')
                continue
            binding = bindings[index]
            if kind != 'page' and ((binding['id'] is None) != op.endswith('.create')):
                raise ValueError('invalid_compilation_target_operation')
            if binding['kind'] != kind:
                raise ValueError('invalid_compilation_target_kind')
            for support in binding['evidence']:
                if support['chunk_id'] not in evidence_ids:
                    raise ValueError('unbound_compilation_evidence')
                citation = SourceService._citation(connection, _uuid(support['chunk_id']), space_id=self._space_id)
                passage(citation, support['quote'], start_offset=support['start_offset'], end_offset=support['end_offset'])
            candidates = []
            if kind == 'page':
                page_slug(args['slug']); _label(args['title'],256); markdown(args['body'])
                if index != 0 or binding['canonical_key'] != task['topic_key']:
                    raise ValueError('invalid_primary_compilation_key')
                existing = connection.execute(text('SELECT id FROM c0_wiki_pages WHERE space_id=:space AND slug=:slug'),
                    {'space': self._space_id, 'slug': args['slug']}).scalar_one_or_none()
                if binding['id'] is None and args['slug'] != managed_slug(self._space_id, task['profile_id'], task['topic_key']):
                    raise ValueError('stable_compilation_slug_required')
                if existing is not None and str(existing) != binding['id']:
                    raise self.conflict()
                if task['target'] and task['target']['id'] != binding['id']:
                    raise self.conflict()
                candidates = [('page', r[0]) for r in connection.execute(text('''SELECT p.id FROM c0_wiki_pages p
                    JOIN c0_wiki_revisions r ON r.space_id=p.space_id AND r.page_id=p.id AND r.number=p.revision
                    WHERE p.space_id=:space AND NOT p.deleted AND r.search_vector @@ plainto_tsquery('simple',:title)
                      AND (CAST(:id AS uuid) IS NULL OR p.id<>CAST(:id AS uuid)) ORDER BY p.id LIMIT 17'''),
                    {'space': self._space_id, 'title': args['title'], 'id': binding['id']})]
                for _, identifier in candidates:
                    other = self._read_record(connection, 'page', identifier)
                    normalize = lambda s: unicodedata.normalize('NFKC', s).casefold().strip()
                    if normalize(other['title']) == normalize(args['title']):
                        raise ValueError('duplicate_compilation_concept')
            if kind == 'entity':
                if type(args.get('aliases', [])) is not list:
                    raise ValueError('invalid_compilation_aliases')
                labels = [args['label'], *args.get('aliases', [])]
                for label in labels:
                    existing = connection.execute(text('SELECT entity_id FROM c0_entity_aliases WHERE space_id=:space AND normalized=:alias'),
                        {'space': self._space_id, 'alias': alias_key(label)[0]}).scalar_one_or_none()
                    if existing is not None and str(existing) != binding['id']:
                        raise ValueError('duplicate_compilation_concept')
            if binding['id'] is None:
                if (binding['revision'] != 0 or binding['managed'] or any(binding[f] is not None for f in ('content_id','content_hash','record_hash'))
                        or args.get('expected_revision') is not None or op.endswith('.update')):
                    raise ValueError('invalid_compilation_create')
            else:
                current = record_binding(kind, self._read_record(connection, kind, binding['id']))
                expected = {k: binding[k] for k in current}
                if current != expected or args.get('expected_revision') != binding['revision']:
                    raise self.conflict()
                selector = {'entity':'entity_id','claim':'claim_id','relation':'relation_id'}.get(kind)
                if selector and args[selector] != binding['id']:
                    raise self.conflict()
                owned = self._owned_target(connection, current)
                if binding['managed'] != owned:
                    raise self.conflict()
                review = review or not owned
            if kind == 'claim':
                if args.get('evidence_chunk_ids') is not None and type(args['evidence_chunk_ids']) is not list:
                    raise ValueError('invalid_compilation_claim_evidence')
                if not all(type(value) is str for value in args.get('evidence_chunk_ids') or []):
                    raise ValueError('invalid_compilation_claim_evidence')
                if not set(args.get('evidence_chunk_ids') or []) <= {e['chunk_id'] for e in binding['evidence']}:
                    raise ValueError('unbound_compilation_claim')
            if op in ('claim.create','relation.create'):
                def existing_id(value):
                    if type(value) is str:
                        return _uuid(value)
                    prior = bindings.get(value['$result']) if type(value) is dict else None
                    return _uuid(prior['id']) if prior and prior['id'] and value['path'] == 'id' else None
                if op == 'relation.create':
                    name(args['kind'])
                    source_id, target_id = existing_id(args['source_id']), existing_id(args['target_id'])
                    if source_id and target_id and connection.execute(text('''SELECT 1 FROM c0_relations
                        WHERE space_id=:space AND source_id=:source AND target_id=:target AND kind=:kind'''),
                        {'space':self._space_id,'source':source_id,'target':target_id,'kind':args['kind']}).scalar_one_or_none():
                        raise ValueError('duplicate_compilation_relation')
                else:
                    name(args['predicate'])
                    if type(args['value']) is not dict:
                        raise ValueError('invalid_compilation_claim_value')
                    entity = existing_id(args['entity_id'])
                    times = {}
                    for field in ('valid_from','valid_to'):
                        value = args.get(field)
                        try:
                            parsed = datetime.fromisoformat(value) if type(value) is str else None
                        except ValueError:
                            raise ValueError('invalid_compilation_claim_time') from None
                        if value is not None and (parsed is None or parsed.tzinfo is None):
                            raise ValueError('invalid_compilation_claim_time')
                        times[field] = parsed
                    if entity and connection.execute(text('''SELECT 1 FROM c0_claims WHERE space_id=:space
                        AND entity_id=:entity AND predicate=:predicate AND value=CAST(:value AS jsonb)
                        AND valid_from IS NOT DISTINCT FROM CAST(:valid_from AS timestamptz)
                        AND valid_to IS NOT DISTINCT FROM CAST(:valid_to AS timestamptz)
                        AND NOT deleted AND NOT evidence_stale LIMIT 1'''),
                        {'space':self._space_id,'entity':entity,'predicate':args['predicate'],
                         'value':_json(args['value']), **times}).scalar_one_or_none():
                        raise ValueError('duplicate_compilation_claim')
            review = self._candidate_decisions(connection, plan, index, candidates, binding) or review
            identities.append({k: binding[k] for k in ('kind','id','revision','content_id','content_hash','record_hash')})
        outcome = 'deferred' if plan['classification'] == 'unsupported' else 'needs_review' if review else 'eligible'
        return run, task, actual_sources, operations, identities, outcome

    def _bundle_outputs(self, connection, plan, result):
        outputs = []
        claims = set()
        primary = result['results'][0]
        annotated = False
        for index, (step, value) in enumerate(zip(plan['operations'], result['results'], strict=True)):
            operation = step['operation']
            kind = 'annotation' if operation == 'annotation.update' else 'link' if operation == 'entity.link' else KINDS[operation.split('.')[0]]
            if kind == 'annotation':
                args = _references(step['arguments'], index, result['results'])
                if (args['target'] != {'kind':'wiki_revision', 'id':primary['content']['id'], 'revision':primary['revision']}
                        or {r['id'] for r in args['value']['source_references']} !=
                            {e['chunk_id'] for b in plan['target_bindings'] if b['operation_index'] == 0 for e in b['evidence']}):
                    raise ValueError('primary_compilation_annotation_required')
                annotated = True
            elif kind == 'link' and value['target_id'] != primary['id']:
                raise ValueError('primary_compilation_link_required')
            row = self._read_record(connection, kind, value['id'])
            if step['operation'] == 'claim.create':
                identity = digest([row[k] for k in ('entity_id','predicate','value','valid_from','valid_to')])
                if identity in claims:
                    raise ValueError('duplicate_compilation_claim')
                claims.add(identity)
            actual = record_binding(kind, row)
            # Several operations may advance the same entity; retain its final readback only.
            outputs = [o for o in outputs if (o['kind'],o['id']) != (kind,actual['id'])]
            outputs.append(actual)
        if not annotated:
            raise ValueError('primary_compilation_annotation_required')
        body = primary['content']['body']
        for binding in plan['target_bindings']:
            if binding['operation_index'] == 0 and any((e['quote'] not in body and e['quote'].replace('\n','\n> ') not in body) or e['chunk_id'] not in body for e in binding['evidence']):
                raise ValueError('original_compilation_citations_required')
        return outputs

    def _dry_bundle(self, connection, actor, plan, operations):
        savepoint = connection.begin_nested()
        try:
            result = KnowledgeBundleService(self.database, self.access).in_space(self._space_id)._apply(connection, actor, operations)
            self._bundle_outputs(connection, plan, result)
        finally:
            savepoint.rollback()

    def validate_plan(self, actor, data):
        data = checked(VALIDATE, data, maximum=262144)
        try:
            with self.database.engine.begin() as connection:
                self._authorize(connection, actor, Role.EDITOR); require_scope(actor, Role.READER)
                connection.execute(text('SELECT pg_advisory_xact_lock(49375)'))
                connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': MUTATION_LOCK})
                hold_authority(connection); content_lock(connection)
                current = self._authorize(connection, actor, Role.EDITOR); require_scope(current, Role.READER)
                run, task, _, operations, identities, outcome = self._inspect(connection, current, data)
                if operations:
                    self._dry_bundle(connection, current, data['plan'], operations)
                self._lease(connection, current, data['lease'])
                return {'outcome': outcome, 'plan_hash': plan_hash(data['plan']),
                    'identity_digest': digest([data['plan']['source_bindings'], identities]),
                    'task_id': str(task['id']), 'task_revision': task['revision'], 'run_revision': run['revision'],
                    'classification': data['plan']['classification'], 'publication_supported': True}
        except IntegrityError:
            raise self.conflict() from None

    def apply_plan(self, actor, data, *, idempotency_key):
        data = checked(APPLY, data, maximum=262144)
        plan = data['plan']; hashed = plan_hash(plan)
        if data['plan_hash'] != hashed:
            raise self.conflict()
        approval = data.get('approval')
        if approval and approval['plan_hash'] != hashed:
            raise self.conflict()
        payload = {'policy_revision': plan['policy_revision'], 'lease': data['lease'],
            'expected_revision': data['expected_revision'], 'expected_task_revision': plan['expected_task_revision'],
            'task_id': plan['task_id'], 'plan_hash': hashed,
            'approval_hash': digest(approval['reference']) if approval else None}
        def guard(connection, current):
            self._sources(connection, plan['source_bindings'])
            task = self._task(connection, plan['task_id'])
            saved = self._publication(connection, task['id'])
            if saved:
                if saved['plan_hash'] != hashed:
                    raise self.conflict()
                self._read_outputs(connection, saved['records'])
            else:
                self._target(connection, task['target'])
        def execute(connection, current):
            run, task, actual, operations, identities, outcome = self._inspect(connection, current, data)
            if not operations or outcome == 'deferred':
                raise ValueError('compilation_publication_not_eligible')
            if outcome == 'needs_review' and not approval:
                raise self.disabled()
            if task['plan_hash'] is not None and task['plan_hash'] != hashed:
                raise self.conflict()
            result = KnowledgeBundleService(self.database, self.access).in_space(self._space_id)._apply(connection, current, operations)
            outputs = self._bundle_outputs(connection, plan, result)
            self._publish_dependencies(connection, task, actual, outputs)
            task = dict(connection.execute(text("""UPDATE c0_compilation_tasks SET state='applied_pending_verify',
                plan_hash=:hash,revision=revision+1,error_code='',updated_at=:now WHERE space_id=:space AND id=:id RETURNING *"""),
                {'space': self._space_id, 'id': task['id'], 'hash': hashed, 'now': self.clock()}).mappings().one())
            self._lease(connection, current, data['lease'])
            run['data']['phase'] = 'verify'
            run = self._save_run(connection, run)
            metrics = {'plan_hash': hashed, 'identity_digest': digest([plan['source_bindings'], identities]),
                'records': outputs, 'locators': self._locators(connection, outputs), 'approval_hash': payload['approval_hash'],
                'classification': plan['classification'], 'deferred': plan['deferred'], 'usage_reservation_id':plan['usage_reservation_id'],
                'compiler_version':core_version}
            return {'outcome': 'applied_pending_verify', 'run': snapshot(run), 'task': snapshot(task),
                'records': outputs, 'plan_hash': hashed, '_event_metrics': metrics}
        return self._mutate(actor, 'apply', payload, idempotency_key, execute, lease=data['lease'], guard=guard)

    def _publish_dependencies(self, connection, task, actual, outputs):
        # Reuse the exact M1 support writer; only trusted publication can set ownership.
        for output in outputs:
            if output['kind'] in ('annotation','link'):
                continue
            target = {'kind': output['kind'], 'id': output['id'], 'revision': output['revision'],
                'content_id': output['content_id'], 'content_hash': output['content_hash'] or output['record_hash']}
            self._observe(connection, {**task, 'target': target}, actual)
            connection.execute(text("""UPDATE c0_compilation_dependencies SET managed_target_hash=:hash
                WHERE space_id=:space AND task_id=:task AND target_kind=:kind AND target_id=:id AND state='observed'"""),
                {'space': self._space_id, 'task': task['id'], 'kind': output['kind'], 'id': _uuid(output['id']),
                 'hash': output['record_hash']})
        for source, _, _ in actual:
            connection.execute(text("""UPDATE c0_compilation_sources SET state='partial',updated_at=:now
                WHERE space_id=:space AND logical_document_id=:id AND profile_id=:profile"""),
                {'space': self._space_id, 'id': source['logical_document_id'], 'profile': task['profile_id'], 'now': self.clock()})

    def verify_plan(self, actor, data, *, idempotency_key):
        data = checked(VERIFY, data, maximum=65536)
        def guard(connection, current):
            task = self._task(connection, data['task_id'])
            if task['source_bindings'] != data['source_bindings']:
                raise self.conflict()
            self._sources(connection, data['source_bindings'])
            saved = self._publication(connection, task['id'])
            if saved is None or saved['plan_hash'] != data['plan_hash'] or saved['records'] != data['observations']:
                raise self.conflict()
            self._read_outputs(connection, saved['records'])
        def execute(connection, current):
            run = self._lease(connection, current, data['lease'])
            task = self._task(connection, data['task_id'])
            if (run['revision'] != data['expected_revision'] or task['revision'] != data['expected_task_revision']
                    or task['run_id'] != run['id'] or task['fencing_generation'] != run['fencing_generation']
                    or task['state'] != 'applied_pending_verify' or task['plan_hash'] != data['plan_hash']):
                raise self.conflict()
            connection.execute(text("""UPDATE c0_compilation_dependencies SET state='current',last_verified_at=:now,
                updated_at=:now WHERE space_id=:space AND task_id=:task AND state='observed'"""),
                {'space': self._space_id, 'task': task['id'], 'now': self.clock()})
            publication = self._publication(connection, task['id'])
            for source in task['source_bindings'] if not publication['deferred'] else []:
                connection.execute(text("""UPDATE c0_compilation_sources SET last_compiled_revision=:revision,
                    last_compiled_hash=:hash,last_metadata_hash=:meta,last_parts_hash=:parts,last_compiled_at=:now,
                    state='observed',updated_at=:now WHERE space_id=:space AND logical_document_id=:logical
                    AND profile_id=:profile AND observed_revision=:revision AND metadata_hash=:meta AND parts_hash=:parts"""),
                    {'space': self._space_id, 'logical': source['logical_document_id'], 'profile': task['profile_id'],
                     'revision': source['revision_id'], 'hash': source['text_hash'], 'meta': source['metadata_hash'],
                     'parts': source['parts_hash'], 'now': self.clock()})
            task = dict(connection.execute(text("""UPDATE c0_compilation_tasks SET state='succeeded',revision=revision+1,
                updated_at=:now WHERE space_id=:space AND id=:id RETURNING *"""),
                {'space': self._space_id, 'id': task['id'], 'now': self.clock()}).mappings().one())
            self._lease(connection, current, data['lease'])
            run['data']['phase'] = 'verified'
            run = self._save_run(connection, run)
            return {'outcome':'succeeded', 'run':snapshot(run), 'task':snapshot(task),
                'records':data['observations'], 'plan_hash':data['plan_hash'], 'deferred':publication['deferred'],
                '_event_metrics': {'plan_hash':data['plan_hash'], 'records':data['observations'],
                    'deferred':publication['deferred'], 'compiler_version':core_version}}
        return self._mutate(actor, 'verify', data, idempotency_key, execute, lease=data['lease'], guard=guard)
