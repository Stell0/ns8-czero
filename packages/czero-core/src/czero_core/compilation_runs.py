# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fenced, budgeted metadata observations; no external invocation or publication."""
from datetime import date, timedelta
import json
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .compilation_schema import CLAIM, CHECKPOINT, LEASE, checked, digest
from .project_schema import occurrence_on_day
from .receipts import snapshot
from .sources import _uuid


def _json(value):
    return json.dumps(snapshot(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class CompilationRuns:
    def _epoch(self, connection):
        row = connection.execute(text('''SELECT
            to_char(pg_postmaster_start_time() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US') AS boot,
            (SELECT oid::text FROM pg_database WHERE datname=current_database()) AS database_id''')).mappings().one()
        return digest(dict(row))

    def _run(self, connection, identifier):
        row = connection.execute(text('SELECT * FROM c0_compilation_runs WHERE space_id=:space AND id=:id AND state<>\'budget\''),
            {'space': self._space_id, 'id': _uuid(identifier)}).mappings().one_or_none()
        if row is None:
            raise self.notfound()
        return dict(row)

    def _live(self, run, policy, epoch):
        return bool(run['state'] == 'running' and run['policy_revision'] == policy['revision'] and
            policy['data']['enabled'] and run['database_epoch'] == epoch and
            run['lease_expiry'] is not None and run['lease_expiry'] > self.clock() and
            run['invocation_deadline'] is not None and run['invocation_deadline'] > self.clock())

    def _lease(self, connection, actor, lease, *, replay_key=None):
        lease = checked(LEASE, lease)
        run = self._run(connection, lease['run_id'])
        policy = self._enabled(connection)
        live = self._live(run, policy, self._epoch(connection))
        if not live and replay_key and run['state'] in ('complete', 'partial', 'blocked'):
            # Lost final responses can replay only under their original unexpired fence.
            saved = connection.execute(text('''SELECT outcome FROM c0_compilation_events WHERE space_id=:space
                AND actor_id=:actor AND request_key=:key AND run_id=:run'''),
                {'space': self._space_id, 'actor': actor.user_id, 'key': replay_key, 'run': run['id']}).scalar_one_or_none()
            live = bool(saved and run['policy_revision'] == policy['revision'] and
                run['database_epoch'] == self._epoch(connection) and run['lease_expiry'] > self.clock()
                and run['invocation_deadline'] > self.clock())
        if (not live or str(run['actor_id']) != str(actor.user_id) or run['lease_owner'] != lease['lease_owner']
                or run['fencing_generation'] != lease['fencing_generation']):
            raise self.conflict()
        return run

    def _save_run(self, connection, run):
        row = connection.execute(text('''UPDATE c0_compilation_runs SET revision=revision+1,state=:state,
            policy_revision=:policy,actor_id=:actor,lease_owner=:owner,fencing_generation=:fence,
            lease_expiry=:expiry,invocation_deadline=:deadline,database_epoch=:epoch,attempts=:attempts,
            day_budget_id=:day,week_budget_id=:week,data=CAST(:data AS jsonb),updated_at=:now
            WHERE space_id=:space AND id=:id RETURNING *'''),
            {'space': self._space_id, 'id': run['id'], 'state': run['state'], 'policy': run['policy_revision'],
             'actor': run['actor_id'], 'owner': run['lease_owner'], 'fence': run['fencing_generation'],
             'expiry': run['lease_expiry'], 'deadline': run['invocation_deadline'], 'epoch': run['database_epoch'],
             'attempts': run['attempts'], 'day': run['day_budget_id'], 'week': run['week_budget_id'],
             'data': _json(run['data']), 'now': self.clock()}).mappings().one()
        return dict(row)

    def _window(self, connection, actor, config, period):
        now = self.clock()
        kind = 'budget_' + period
        active = connection.execute(text('''SELECT * FROM c0_compilation_runs WHERE space_id=:space
            AND kind=:kind AND window_start<=:now AND window_end>:now ORDER BY window_end DESC LIMIT 1'''),
            {'space': self._space_id, 'kind': kind, 'now': now}).mappings().one_or_none()
        if active:
            return dict(active)
        local = now.astimezone(ZoneInfo(config['data']['timezone'])).date()
        start_day = local if period == 'day' else local - timedelta(days=local.weekday())
        end_day = start_day + timedelta(days=1 if period == 'day' else 7)
        manifest = {'timezone': config['data']['timezone'], 'schedule': {'daily_local_time': '00:00'}}
        start = occurrence_on_day(manifest, 'daily', start_day.isoformat())
        end = occurrence_on_day(manifest, 'daily', end_day.isoformat())
        previous_end = connection.execute(text('SELECT max(window_end) FROM c0_compilation_runs WHERE space_id=:space AND kind=:kind'),
            {'space': self._space_id, 'kind': kind}).scalar_one_or_none()
        if previous_end is not None:
            start = max(start, previous_end)
        prefix = 'daily_' if period == 'day' else 'weekly_'
        caps = {field: config['data'][prefix + name] for field, name in (
            ('documents', 'documents'), ('pages', 'pages'), ('requests', 'model_requests'), ('tokens', 'model_tokens'))}
        data = {'caps': caps, 'requests': 0, 'charged_tokens': 0, 'observed_tokens': 0, 'usage_unknown': False, 'unknown_requests': 0}
        row = connection.execute(text('''INSERT INTO c0_compilation_runs(id,space_id,kind,cycle_key,state,
            policy_revision,actor_id,fencing_generation,database_epoch,attempts,started_at,updated_at,
            window_start,window_end,data) VALUES(:id,:space,:kind,:cycle,'budget',:policy,:actor,1,:epoch,0,:now,:now,
                :start,:end,CAST(:data AS jsonb)) RETURNING *'''),
            {'id': uuid4(), 'space': self._space_id, 'kind': kind, 'cycle': digest([start.isoformat(), end.isoformat()]),
             'policy': config['revision'], 'actor': actor.user_id, 'epoch': self._epoch(connection),
             'now': now, 'start': start, 'end': end, 'data': _json(data)}).mappings().one()
        return dict(row)

    def _budgets(self, connection, actor, policy, kind):
        day = self._window(connection, actor, policy, 'day')
        week = self._window(connection, actor, policy, 'week') if kind == 'weekly' else None
        return day, week

    def _budget(self, connection, identifier):
        row = connection.execute(text("SELECT * FROM c0_compilation_runs WHERE space_id=:space AND id=:id AND state='budget'"),
            {'space': self._space_id, 'id': identifier}).mappings().one()
        return dict(row)

    def _save_budget(self, connection, budget):
        connection.execute(text('''UPDATE c0_compilation_runs SET data=CAST(:data AS jsonb),revision=revision+1,
            updated_at=:now WHERE space_id=:space AND id=:id AND state='budget' '''),
            {'space': self._space_id, 'id': budget['id'], 'data': _json(budget['data']), 'now': self.clock()})

    def _reservation_fits(self, connection, budget, task, policy):
        column = 'day_budget_id' if budget['kind'] == 'budget_day' else 'week_budget_id'
        rows = connection.execute(text('SELECT metrics FROM c0_compilation_events WHERE space_id=:space AND ' + column + "=:id AND kind='task_reserve'"),
            {'space': self._space_id, 'id': budget['id']}).scalars().all()
        documents = {value for metrics in rows for value in metrics['document_ids']}
        targets = {value for metrics in rows for value in metrics['target_keys']}
        documents.update(s['logical_document_id'] for s in task['source_bindings'])
        targets.add(task['target_key'])
        prefix = 'daily_' if column == 'day_budget_id' else 'weekly_'
        return (len(documents) <= min(budget['data']['caps']['documents'], policy[prefix + 'documents'])
            and len(targets) <= min(budget['data']['caps']['pages'], policy[prefix + 'pages']))

    def _reserve_tasks(self, connection, actor, run, policy, limit):
        # Reattach already reserved work before selecting new tasks; consumed debits survive.
        owned = list(connection.execute(text('''SELECT * FROM c0_compilation_tasks WHERE space_id=:space
            AND run_id=:run AND state IN ('leased','planned','uncertain') ORDER BY created_at,id'''),
            {'space': self._space_id, 'run': run['id']}).mappings())
        candidates = [dict(t) for t in owned]
        candidates += [dict(t) for t in connection.execute(text("SELECT * FROM c0_compilation_tasks WHERE space_id=:space AND id=ANY(CAST(:ids AS uuid[])) AND state='deferred' AND not_before<=:now AND attempts<:attempts ORDER BY not_before,id"), {'space': self._space_id, 'ids': run['data']['task_ids'], 'now': self.clock(), 'attempts': policy['max_attempts']}).mappings()]
        room = min(limit, policy['max_tasks_per_run'] - len(run['data']['task_ids']))
        if room > 0:
            candidates += [dict(t) for t in connection.execute(text('''SELECT * FROM c0_compilation_tasks
                WHERE space_id=:space AND state IN ('queued','deferred') AND not_before<=:now
                  AND attempts<:attempts AND profile_id=:profile AND profile_version=:version
                  AND NOT (id=ANY(CAST(:known AS uuid[])))
                ORDER BY not_before,id LIMIT :limit FOR UPDATE SKIP LOCKED'''),
                {'space': self._space_id, 'now': self.clock(), 'attempts': policy['max_attempts'],
                 'profile': policy['profile_id'], 'version': policy['profile_version'], 'limit': room, 'known': run['data']['task_ids']}).mappings()]
        reserved = []
        retry_at = None
        for task in candidates:
            held = str(task['id']) in run['data']['task_ids']
            if not held and len(reserved) >= limit:
                break
            if 'page' not in policy['allowed_target_kinds']:
                continue
            try:
                self._sources(connection, task['source_bindings']); self._target(connection, task['target'])
            except (self.conflict, self.notfound, self.notready, ValueError):
                connection.execute(text("UPDATE c0_compilation_tasks SET state='conflict',error_code='source_unavailable',revision=revision+1,updated_at=:now WHERE space_id=:space AND id=:id"),
                        {'space': self._space_id, 'id': task['id'], 'now': self.clock()})
                continue
            budgets = [self._budget(connection, run['day_budget_id'])]
            if run['week_budget_id'] is not None:
                budgets.append(self._budget(connection, run['week_budget_id']))
            exhausted = [b for b in budgets if not self._reservation_fits(connection, b, task, policy)]
            if exhausted:
                deadline = max(self.clock(), *(b['window_end'] for b in exhausted))
                retry_at = max(retry_at, deadline) if retry_at else deadline
                continue
            # One task reservation observation per run fence and budget window.
            identity = digest(['task_reserve', str(run['id']), str(task['id']), run['fencing_generation'],
                str(run['day_budget_id']), str(run['week_budget_id'])])
            uncertain = any(c['task_id'] == str(task['id']) and c['state'] == 'uncertain' for c in run['data']['calls'].values())
            changed = (task['fencing_generation'] != run['fencing_generation'] or task['run_id'] != run['id'] or task['state'] == 'deferred' or not held)
            next_state = 'uncertain' if uncertain else task['state'] if held and task['state'] in ('planned','leased') else 'leased'
            if changed:
                if task['attempts'] >= policy['max_attempts']:
                    connection.execute(text("UPDATE c0_compilation_tasks SET state='failed',error_code='retry_exhausted',revision=revision+1 WHERE space_id=:space AND id=:id"),
                        {'space': self._space_id, 'id': task['id']})
                    continue
                task = dict(connection.execute(text('''UPDATE c0_compilation_tasks SET state=:state,run_id=:run,
                    fencing_generation=:fence,policy_revision=:policy,attempts=attempts+1,revision=revision+1,updated_at=:now
                    WHERE space_id=:space AND id=:id RETURNING *'''),
                    {'space': self._space_id, 'id': task['id'], 'state': next_state, 'run': run['id'],
                     'fence': run['fencing_generation'], 'policy': run['policy_revision'], 'now': self.clock()}).mappings().one())
            if not held:
                run['data']['task_ids'].append(str(task['id']))
            recorded = connection.execute(text('SELECT 1 FROM c0_compilation_events WHERE space_id=:space AND actor_id=:actor AND request_key=:key'),
                {'space': self._space_id, 'actor': actor.user_id, 'key': identity}).scalar_one_or_none()
            if not recorded:
                self._event(connection, actor, identity, identity, 'task_reserve', 'reserved', run=run, task=task,
                    kind='task_reserve', metrics={'document_ids': [s['logical_document_id'] for s in task['source_bindings']],
                        'target_keys': [task['target_key']]})
            reserved.append(snapshot(task))
        return reserved, retry_at

    def claim_run(self, actor, data, *, idempotency_key):
        data = checked(CLAIM, data)
        data.setdefault('task_limit', 1)
        def execute(connection, current):
            policy = self._enabled(connection, data['policy_revision']); config = policy['data']; now = self.clock()
            if data['kind'] == 'retrieval' and not config['retrieval_feedback']:
                raise self.disabled()
            today = now.astimezone(ZoneInfo(config['timezone'])).date().isoformat()
            row = connection.execute(text('''SELECT * FROM c0_compilation_runs WHERE space_id=:space
                AND kind=:kind AND cycle_key=:cycle'''),
                {'space': self._space_id, 'kind': data['kind'], 'cycle': data['cycle_key']}).mappings().one_or_none()
            epoch = self._epoch(connection)
            if row:
                run = dict(row)
                if run['state'] == 'complete':
                    return {'outcome': 'completed_bounded', 'run': snapshot(run)}
                live = self._live(run, policy, epoch)
                if live and (run['lease_owner'] != data['lease_owner'] or str(run['actor_id']) != str(current.user_id)):
                    raise self.conflict()
                if not live and run['attempts'] >= config['max_attempts']:
                    return {'outcome': 'retry_exhausted', 'run': snapshot(run)}
            else:
                if data['kind'] in ('daily', 'weekly') and (data['cycle_key'] != today or date.fromisoformat(data['cycle_key']).isoformat() != today):
                    raise ValueError('current_compilation_cycle_required')
                run = None; live = False
            active = connection.execute(text("""SELECT count(*) AS count,
                    min(LEAST(lease_expiry,invocation_deadline)) AS next_eligible_at FROM c0_compilation_runs
                WHERE space_id=:space AND state='running' AND lease_expiry>:now
                  AND invocation_deadline>:now AND policy_revision=:policy AND database_epoch=:epoch
                  AND (CAST(:current AS uuid) IS NULL OR id<>CAST(:current AS uuid))"""),
                {'space': self._space_id, 'now': now, 'policy': policy['revision'], 'epoch': epoch,
                 'current': run['id'] if run else None}).mappings().one()
            if not live and active['count'] >= config['concurrency']:
                return {'outcome': 'deferred_concurrency', 'next_eligible_at': snapshot(active['next_eligible_at']), 'retryable': True}
            day, week = self._budgets(connection, current, policy, data['kind'])
            if run is None:
                run = dict(connection.execute(text('''INSERT INTO c0_compilation_runs(id,space_id,kind,cycle_key,
                    state,policy_revision,actor_id,lease_owner,fencing_generation,lease_expiry,invocation_deadline,
                    database_epoch,attempts,started_at,updated_at,day_budget_id,week_budget_id,data)
                    VALUES(:id,:space,:kind,:cycle,'running',:policy,:actor,:owner,1,:expiry,:deadline,:epoch,1,
                        :now,:now,:day,:week,CAST(:data AS jsonb)) RETURNING *'''),
                    {'id': uuid4(), 'space': self._space_id, 'kind': data['kind'], 'cycle': data['cycle_key'],
                     'policy': policy['revision'], 'actor': current.user_id, 'owner': data['lease_owner'],
                     'expiry': now + timedelta(seconds=min(config['lease_seconds'], config['run_seconds'])),
                     'deadline': now + timedelta(seconds=config['run_seconds']), 'epoch': epoch, 'now': now,
                     'day': day['id'], 'week': week['id'] if week else None,
                     'data': _json({'policy': config, 'task_ids': [], 'calls': {}, 'phase': 'discover'})}).mappings().one())
            else:
                if not live:
                    run['attempts'] += 1; run['fencing_generation'] += 1
                    run['invocation_deadline'] = now + timedelta(seconds=config['run_seconds'])
                    for call in run['data']['calls'].values():
                        if call['state'] == 'started':
                            call['state'] = 'uncertain'
                run.update(state='running', policy_revision=policy['revision'], actor_id=current.user_id,
                    lease_owner=data['lease_owner'], database_epoch=epoch, day_budget_id=day['id'],
                    week_budget_id=week['id'] if week else None,
                    lease_expiry=min(now + timedelta(seconds=config['lease_seconds']), run['invocation_deadline']))
                run['data']['policy'] = config
            tasks, retry_at = self._reserve_tasks(connection, current, run, config, data['task_limit'])
            run = self._save_run(connection, run)
            lease = {'run_id': str(run['id']), 'lease_owner': run['lease_owner'], 'fencing_generation': run['fencing_generation']}
            result = {'outcome': 'deferred_budget' if not tasks and retry_at else 'claimed',
                'run': snapshot(run), 'lease': lease, 'tasks': tasks}
            if retry_at:
                result.update(next_eligible_at=snapshot(retry_at), retryable=True)
            return result
        return self._mutate(actor, 'run_claim', data, idempotency_key, execute)

    def _leased_task(self, connection, run, data, *, support=True):
        if 'task_id' not in data or 'expected_task_revision' not in data:
            raise ValueError('compilation_task_revision_required')
        task = self._task(connection, data['task_id'])
        if (task['run_id'] != run['id'] or task['fencing_generation'] != run['fencing_generation']
                or task['revision'] != data['expected_task_revision'] or task['state'] not in ('leased', 'planned', 'uncertain')):
            raise self.conflict()
        if support:
            if 'page' not in self._enabled(connection)['data']['allowed_target_kinds']:
                raise self.disabled()
            self._sources(connection, task['source_bindings']); self._target(connection, task['target'])
        return task

    def _charge_model(self, connection, run, reserved, *, observed=None):
        policy = self._enabled(connection)['data']
        budgets = [self._budget(connection, run['day_budget_id'])]
        if run['week_budget_id'] is not None:
            budgets.append(self._budget(connection, run['week_budget_id']))
        if observed is None:
            exhausted = []
            for budget in budgets:
                prefix = 'daily_' if budget['kind'] == 'budget_day' else 'weekly_'
                caps = budget['data']['caps']
                if (budget['window_end'] <= self.clock() or budget['data']['requests'] + 1 > min(caps['requests'], policy[prefix + 'model_requests'])
                        or budget['data']['charged_tokens'] + reserved > min(caps['tokens'], policy[prefix + 'model_tokens'])):
                    exhausted.append(budget['window_end'])
            if exhausted:
                return max(self.clock(), *exhausted)
            for budget in budgets:
                budget['data']['requests'] += 1; budget['data']['charged_tokens'] += reserved
                budget['data']['unknown_requests'] += 1
                budget['data']['usage_unknown'] = True
                self._save_budget(connection, budget)
            return True
        for budget in budgets:
            budget['data']['observed_tokens'] += observed
            budget['data']['unknown_requests'] -= 1
            budget['data']['usage_unknown'] = budget['data']['unknown_requests'] > 0
            budget['data']['charged_tokens'] += max(0, observed - reserved)
            self._save_budget(connection, budget)
        return True

    def checkpoint(self, actor, data, *, idempotency_key):
        data = checked(CHECKPOINT, data)
        action = data['action']
        common = {'lease', 'expected_revision', 'action'}
        task_fields = {'task_id', 'expected_task_revision'}
        fields = {'planned': task_fields | {'plan_hash'}, 'no_change': task_fields, 'defer': task_fields | {'error_code'},
            'fail': task_fields | {'error_code'}, 'reserve_model': task_fields | {'request_id', 'reserved_tokens'},
            'start_model': {'request_id'}, 'return_model': {'request_id', 'observed_tokens', 'external_reference_hash'},
            'fail_model': {'request_id'}, 'uncertain_model': {'request_id'},
            'reconcile_returned': {'request_id', 'observed_tokens', 'external_reference_hash'},
            'reconcile_failed': {'request_id'}, 'finish': set(), 'partial': set()}
        if set(data) != common | fields[action]:
            raise ValueError('invalid_compilation_checkpoint')
        def guard(connection, current):
            if action not in ('planned', 'no_change', 'reserve_model', 'start_model', 'finish'):
                return
            run = self._run(connection, data['lease']['run_id'])
            identifiers = run['data']['task_ids'] if action == 'finish' else [data['task_id']] if 'task_id' in data else [run['data']['calls'][data['request_id']]['task_id']] if data['request_id'] in run['data']['calls'] else []
            for identifier in identifiers:
                task = self._task(connection, identifier)
                self._sources(connection, task['source_bindings']); self._target(connection, task['target'])
        def execute(connection, current):
            run = self._lease(connection, current, data['lease'])
            if run['revision'] != data['expected_revision']:
                raise self.conflict()
            task = None
            if action in ('planned', 'no_change', 'defer', 'fail', 'reserve_model'):
                task = self._leased_task(connection, run, data, support=action not in ('defer', 'fail'))
            calls = run['data']['calls']
            if task and action != 'reserve_model' and any(c['task_id'] == str(task['id']) and c['state'] in ('reserved','started','uncertain') for c in calls.values()):
                raise self.conflict()
            if action == 'reserve_model':
                if task['state'] == 'uncertain' or len(calls) >= 100 or data['request_id'] in calls:
                    raise self.conflict()
                if any(c['task_id'] == str(task['id']) and c['state'] in ('reserved','started','uncertain') for c in calls.values()):
                    raise self.conflict()
                if connection.execute(text("SELECT 1 FROM c0_compilation_events WHERE space_id=:space AND call_id=:call AND kind='model_reserve'"),
                        {'space': self._space_id, 'call': _uuid(data['request_id'])}).scalar_one_or_none():
                    raise self.conflict()
                if run['kind'] == 'retrieval' and (len(calls) >= run['data']['policy']['retrieval_model_requests']
                        or data['reserved_tokens'] > run['data']['policy']['retrieval_model_tokens']):
                    return {'outcome': 'deferred_budget', 'run': snapshot(run), 'task': snapshot(task),
                        'next_eligible_at': None, 'retryable': False}
                allowance = self._charge_model(connection, run, data['reserved_tokens'])
                if allowance is not True:
                    return {'outcome': 'deferred_budget', 'run': snapshot(run), 'task': snapshot(task),
                        'next_eligible_at': snapshot(allowance), 'retryable': True}
                calls[data['request_id']] = {'state': 'reserved', 'task_id': str(task['id']),
                    'reserved_tokens': data['reserved_tokens'], 'observed_tokens': None,
                    'day_budget_id': str(run['day_budget_id']),
                    'week_budget_id': str(run['week_budget_id']) if run['week_budget_id'] else None}
                unique = digest([idempotency_key, 'call'])
                self._event(connection, current, unique, unique, 'reserve_model', 'reserved', run=run, task=task,
                    kind='model_reserve', call_id=_uuid(data['request_id']), metrics={'reserved_tokens': data['reserved_tokens']})
            elif action in ('start_model','return_model','fail_model','uncertain_model','reconcile_returned','reconcile_failed'):
                call = calls.get(data['request_id'])
                if call is None:
                    raise self.notfound()
                expected = 'reserved' if action == 'start_model' or action == 'fail_model' and call['state'] == 'reserved' else 'uncertain' if action.startswith('reconcile') else 'started'
                if call['state'] != expected:
                    raise self.conflict()
                if action == 'start_model':
                    if call['day_budget_id'] != str(run['day_budget_id']):
                        raise self.conflict()
                    call.update(state='started', deadline=(self.clock() + timedelta(seconds=run['data']['policy']['request_seconds'])).isoformat())
                elif action == 'uncertain_model':
                    call['state'] = 'uncertain'
                else:
                    unstarted = call['state'] == 'reserved'
                    call['state'] = 'returned' if action in ('return_model','reconcile_returned') else 'failed'
                    if call['state'] == 'returned':
                        call['observed_tokens'] = data['observed_tokens']
                        call['external_reference_hash'] = data['external_reference_hash']
                        if data['observed_tokens'] is not None:
                            original_budgets = run['day_budget_id'], run['week_budget_id']
                            run['day_budget_id'], run['week_budget_id'] = _uuid(call['day_budget_id']), _uuid(call['week_budget_id']) if call['week_budget_id'] else None
                            self._charge_model(connection, run, call['reserved_tokens'], observed=data['observed_tokens'])
                            run['day_budget_id'], run['week_budget_id'] = original_budgets
                    if unstarted:
                        original_budgets = run['day_budget_id'], run['week_budget_id']
                        run['day_budget_id'], run['week_budget_id'] = _uuid(call['day_budget_id']), _uuid(call['week_budget_id']) if call['week_budget_id'] else None
                        self._charge_model(connection, run, call['reserved_tokens'], observed=0)
                        run['day_budget_id'], run['week_budget_id'] = original_budgets
                    # Reconciliation frees only its matching uncertain task, never another run.
                    connection.execute(text("""UPDATE c0_compilation_tasks SET state='leased',revision=revision+1,updated_at=:now
                        WHERE space_id=:space AND id=:id AND run_id=:run AND fencing_generation=:fence AND state='uncertain'"""),
                        {'space': self._space_id, 'id': _uuid(call['task_id']), 'run': run['id'],
                         'fence': run['fencing_generation'], 'now': self.clock()})
            elif action in ('planned','no_change','defer','fail'):
                state = {'planned': 'planned', 'no_change': 'no_change', 'defer': 'deferred', 'fail': 'deferred'}[action]
                if action in ('fail', 'defer') and task['attempts'] >= run['data']['policy']['max_attempts']:
                    state = 'failed'
                if action == 'fail' and data['error_code'] == 'unsupported_evidence':
                    state = 'needs_review'
                delay = min(3600, 30 * 2 ** min(task['attempts'] - 1, 10)) if state == 'deferred' else 0
                task = dict(connection.execute(text('''UPDATE c0_compilation_tasks SET state=:state,revision=revision+1,
                    plan_hash=COALESCE(:plan,plan_hash),error_code=:error,not_before=:not_before,updated_at=:now
                    WHERE space_id=:space AND id=:id RETURNING *'''),
                    {'space': self._space_id, 'id': task['id'], 'state': state, 'plan': data.get('plan_hash'),
                     'error': data.get('error_code', ''), 'not_before': self.clock() + timedelta(seconds=delay),
                     'now': self.clock()}).mappings().one())
                if state == 'no_change':
                    for source in task['source_bindings']:
                        connection.execute(text("""UPDATE c0_compilation_sources SET state='no_change',updated_at=:now
                            WHERE space_id=:space AND logical_document_id=:id AND profile_id=:profile
                              AND observed_revision=:revision AND metadata_hash=:meta AND parts_hash=:parts"""),
                            {'space': self._space_id, 'id': _uuid(source['logical_document_id']), 'profile': task['profile_id'],
                             'revision': _uuid(source['revision_id']), 'meta': source['metadata_hash'], 'parts': source['parts_hash'], 'now': self.clock()})
            elif action in ('finish', 'partial'):
                unfinished = connection.execute(text("SELECT count(*) FROM c0_compilation_tasks WHERE space_id=:space AND run_id=:run AND state<>'no_change'"),
                    {'space': self._space_id, 'run': run['id']}).scalar_one()
                unresolved = any(c['state'] in ('reserved','started','uncertain') for c in calls.values())
                if action == 'finish' and (unfinished or unresolved):
                    raise self.conflict()
                run['state'] = 'complete' if action == 'finish' else 'partial'
            run = self._save_run(connection, run)
            result = {'outcome': 'completed_bounded' if action == 'finish' else action, 'run': snapshot(run)}
            if task:
                result['task'] = snapshot(task)
            return result
        return self._mutate(actor, 'run_checkpoint', data, idempotency_key, execute, lease=data['lease'], guard=guard)
