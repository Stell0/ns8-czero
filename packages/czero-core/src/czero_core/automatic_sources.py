# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Space-owned definitions and explicitly authorized deterministic background work."""
from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

from sqlalchemy import text

from .identity import Actor, Role, PermissionDenied
from .receipts import mutate
from .drive_sources import DriveAudienceChanged, DriveSources
from .spaces import SpaceBound, hold_authority, _paging
from .jobs import bounded_json


class UpdateConflict(ValueError):
    pass


class UpdateNotFound(ValueError):
    pass


def configuration(kind, value):
    from .source_collectors import validate
    return validate(kind, value)


class AutomaticSourceService(DriveSources, SpaceBound):
    def __init__(self, database, access):
        self.database, self.access = database, access

    def _authorize(self, c, actor, role=Role.READER):
        return self._space_authorize(c, actor, role)

    def _row(self, c, identifier, *, lock=False):
        row = c.execute(text('SELECT * FROM c0_automatic_sources WHERE id=:id AND space_id=:space' +
                             (' FOR UPDATE' if lock else '')),
                        {'id': UUID(str(identifier)), 'space': self._space(c)}).mappings().one_or_none()
        if row is None:
            raise UpdateNotFound('automatic_source_not_found')
        return dict(row)

    @staticmethod
    def _view(row):
        return {k: v for k, v in row.items() if k not in ('authority_revision', 'space_revision', 'grant_revision', 'retry_count', 'run_number')}

    def list(self, actor, *, limit=50, offset=0):
        _paging(limit, offset)
        with self.database.engine.connect() as c:
            self._authorize(c, actor)
            rows = c.execute(text("SELECT d.*, (SELECT r.state FROM c0_source_update_runs r WHERE r.definition_id=d.id ORDER BY r.number DESC LIMIT 1) AS status FROM c0_automatic_sources d WHERE d.space_id=:space ORDER BY d.name,d.id LIMIT :limit OFFSET :offset"),
                             {'space': self._space(c), 'limit': limit, 'offset': offset}).mappings()
            return [self._view(dict(row)) for row in rows]

    def runs(self, actor, identifier, *, limit=50, offset=0):
        _paging(limit, offset)
        with self.database.engine.connect() as c:
            self._authorize(c, actor)
            self._row(c, identifier)
            return [dict(row) for row in c.execute(text('''SELECT id,definition_id,revision,state,error_code,processed,created_at,finished_at,
                    diagnostics,CASE WHEN state IN ('queued','pending') THEN available_at END AS available_at,
                    cursor<>'{}' AS checkpoint_available
                FROM c0_source_update_runs WHERE definition_id=:id ORDER BY number DESC LIMIT :limit OFFSET :offset'''),
                {'id': identifier, 'limit': limit, 'offset': offset}).mappings()]

    def documents(self, actor, identifier, *, limit=50, offset=0):
        _paging(limit, offset)
        with self.database.engine.connect() as c:
            self._authorize(c, actor)
            self._row(c, identifier)
            return [dict(row) for row in c.execute(text("""SELECT s.id,s.title,s.revision,s.deleted FROM c0_automatic_source_items i
                JOIN c0_sources s ON s.id=i.source_id WHERE i.definition_id=:id AND s.space_id=:space
                ORDER BY s.title,s.id LIMIT :limit OFFSET :offset"""),
                {'id': identifier, 'space': self._space(c), 'limit': limit, 'offset': offset}).mappings()]

    def preview(self, actor, *, kind, config):
        from .source_collectors import collect
        with self.database.engine.connect() as c:
            self._authorize(c, actor, Role.EDITOR)
        checked = configuration(kind, config)
        sample = 5 if checked.get('attachments') else 1
        checked.update(max_items=sample, max_requests=4, timeout=3)
        items, cursor, complete = collect(kind, checked, {}, preview=True)
        with self.database.engine.connect() as c:
            self._authorize(c, actor, Role.EDITOR)
        return {'items': [{'title': item['title'], 'url': item['metadata']['original_url'],
                           **{key: item[key] for key in ('kind', 'selection', 'reason') if key in item}}
                          for item in items],
                'complete': complete and not cursor.get('attachment_failures') and not cursor.get('depth_limited')}

    def save(self, actor, *, name, kind, config, enabled, interval_seconds, idempotency_key,
             identifier=None, expected_revision=None):
        return self._save(actor, name=name, kind=kind, config=config,
                          enabled=enabled, interval_seconds=interval_seconds, idempotency_key=idempotency_key,
                          identifier=identifier, expected_revision=expected_revision)

    def _save(self, actor, *, name, kind, config, enabled, interval_seconds, idempotency_key,
              identifier=None, expected_revision=None, proof_hash=None):
        if (type(name) is not str or not name.strip() or len(name)>256 or not name.isprintable()
                or type(enabled) is not bool or (interval_seconds is not None and
                (type(interval_seconds) is not int or not 300<=interval_seconds<=2678400))):
            raise ValueError('invalid_automatic_source')
        if expected_revision is not None and (type(expected_revision) is not int or not 1<=expected_revision<9223372036854775807):
            raise ValueError('invalid_revision')
        if (identifier is None) != (expected_revision is None):
            raise ValueError('invalid_revision')
        if proof_hash is None:
            config = configuration(kind, config)
        payload = dict(name=name, kind=kind, config=config, enabled=enabled, interval_seconds=interval_seconds,
                       identifier=str(identifier) if identifier else None, expected_revision=expected_revision)
        if proof_hash is not None:
            payload['preview_hash'] = proof_hash

        def execute(c, current):
            binding = None
            if proof_hash is not None:
                binding = self._use_drive_preview(c, actor, proof_hash, identifier, expected_revision, enabled)
            authority = c.execute(text('SELECT access_revision FROM c0_accounts WHERE id=:id'), {'id': current.user_id}).scalar_one()
            space_revision = c.execute(text('SELECT revision FROM c0_spaces WHERE id=:id'), {'id': self._space(c)}).scalar_one()
            grant_revision = c.execute(text('SELECT revision FROM c0_space_grants WHERE space_id=:space AND account_id=:id'), {'space': self._space(c), 'id': current.user_id}).scalar_one_or_none() or 0
            if identifier:
                old = self._row(c, identifier, lock=True)
                if old['kind'] == 'google_drive' or binding is not None:
                    if old['kind'] != 'google_drive' or binding is None or old['owner_id'] != current.user_id:
                        raise PermissionDenied()
                if old['revision'] != expected_revision:
                    raise UpdateConflict('automatic_source_conflict')
                cancel_staged(c, identifier)
                c.execute(text("UPDATE c0_source_update_runs SET state='cancelled',finished_at=now(),lease=NULL,cursor='{}' WHERE definition_id=:id AND state IN ('queued','running','pending')"), {'id': identifier})
                c.execute(text('''UPDATE c0_automatic_sources SET retry_count=0,name=:name,kind=:kind,config=CAST(:config AS jsonb),enabled=:enabled,
                    interval_seconds=:interval,revision=revision+1,owner_id=:owner,authority_revision=:authority,space_revision=:sr,grant_revision=:gr,
                    next_run_at=CASE WHEN :enabled THEN now() ELSE NULL END,updated_at=now() WHERE id=:id'''),
                    {'id': identifier, 'name': name, 'kind': kind, 'config': json.dumps(config), 'enabled': enabled,
                     'interval': interval_seconds, 'owner': current.user_id, 'authority': authority, 'sr': space_revision, 'gr': grant_revision})
                c.execute(text("UPDATE c0_source_update_runs SET cursor='{}' WHERE definition_id=:id AND cursor<>'{}'"), {'id':identifier})
                result_id = identifier
            else:
                result_id = uuid4()
                c.execute(text('''INSERT INTO c0_automatic_sources(id,space_id,name,kind,config,enabled,interval_seconds,owner_id,authority_revision,space_revision,grant_revision,next_run_at)
                    VALUES (:id,:space,:name,:kind,CAST(:config AS jsonb),:enabled,:interval,:owner,:authority,:sr,:gr,CASE WHEN :enabled THEN now() END)'''),
                    {'id': result_id, 'space': self._space(c), 'name': name, 'kind': kind, 'config': json.dumps(config),
                     'enabled': enabled, 'interval': interval_seconds, 'owner': current.user_id, 'authority': authority, 'sr': space_revision, 'gr': grant_revision})
            if binding is not None:
                c.execute(text("""INSERT INTO c0_drive_bindings(definition_id,account_id,space_id,generation,folder_id,approved_audience)
                    VALUES (:id,:account,:space,:generation,:folder_id,:audience) ON CONFLICT(definition_id) DO UPDATE SET
                    generation=excluded.generation,folder_id=excluded.folder_id,approved_audience=excluded.approved_audience"""),
                    {**binding, 'id': result_id})
            return {'id': str(result_id), 'revision': self._row(c, result_id)['revision']}
        authorize = self._authorize_drive_mutation if proof_hash is not None else self._authorize
        return mutate(self.database, authorize, actor, 'automatic_source.save', payload, idempotency_key, execute, conflict=UpdateConflict)

    def command(self, actor, identifier, *, expected_revision, idempotency_key, action):
        return self._command(actor, identifier, expected_revision=expected_revision,
                             idempotency_key=idempotency_key, action=action, private_run=False)

    def _command(self, actor, identifier, *, expected_revision, idempotency_key, action, private_run):
        if type(expected_revision) is not int or not 1<=expected_revision<9223372036854775807:
            raise ValueError('invalid_revision')
        if action not in ('run','pause','remove'):
            raise ValueError('invalid_source_action')
        def execute(c, current):
            row = self._row(c, identifier, lock=True)
            if row['revision'] != expected_revision:
                raise UpdateConflict('automatic_source_conflict')
            if action == 'run':
                if private_run != (row['kind'] == 'google_drive') or (private_run and row['owner_id'] != current.user_id):
                    raise PermissionDenied()
                # Manual work also requires a deliberately enabled background authority.
                try:
                    self._background_actor(c, row)
                except DriveAudienceChanged:
                    run_id = self._enqueue(c,row)
                    self._finish(c,{**row,'run_id':run_id},'blocked','drive_audience_changed')
                    return {'id':str(run_id)}
                return {'id': str(self._enqueue(c, row))}
            cancel_staged(c, identifier)
            c.execute(text("UPDATE c0_source_update_runs SET state='cancelled',finished_at=now(),lease=NULL,cursor='{}' WHERE definition_id=:id AND state IN ('queued','running','pending')"), {'id': identifier})
            c.execute(text("UPDATE c0_source_update_runs SET cursor='{}' WHERE definition_id=:id AND cursor<>'{}'"), {'id':identifier})
            if action == 'pause':
                c.execute(text('UPDATE c0_automatic_sources SET enabled=false,revision=revision+1,next_run_at=NULL,updated_at=now() WHERE id=:id'), {'id': identifier})
            else:
                c.execute(text('DELETE FROM c0_automatic_sources WHERE id=:id'), {'id': identifier})
            return {'id': str(identifier)}
        authorize = self._authorize_drive_mutation if private_run else self._authorize
        operation = 'automatic_source.drive_run' if private_run else 'automatic_source.' + action
        return mutate(self.database, authorize, actor, operation,
                      {'id': str(identifier), 'revision': expected_revision}, idempotency_key, execute, conflict=UpdateConflict)

    def _background_actor(self, c, definition):
        if not definition['enabled']:
            raise PermissionDenied()
        if definition['kind'] == 'google_drive':
            self._drive_worker_binding(c, definition)
        current = self.access.checked_actor(c, Actor(definition['owner_id'], Role.READER))
        revision = c.execute(text('SELECT access_revision FROM c0_accounts WHERE id=:id'), {'id': current.user_id}).scalar_one()
        sr = c.execute(text('SELECT revision FROM c0_spaces WHERE id=:id'), {'id': definition['space_id']}).scalar_one()
        gr = c.execute(text('SELECT revision FROM c0_space_grants WHERE space_id=:space AND account_id=:id'), {'space': definition['space_id'], 'id': current.user_id}).scalar_one_or_none() or 0
        if revision != definition['authority_revision'] or sr != definition['space_revision'] or gr != definition['grant_revision']:
            raise PermissionDenied()
        return self.in_space(definition['space_id'])._authorize(c, current, Role.EDITOR)

    @staticmethod
    def _enqueue(c, row):
        existing = c.execute(text("SELECT id FROM c0_source_update_runs WHERE definition_id=:id AND state IN ('queued','running','pending')"), {'id': row['id']}).scalar_one_or_none()
        if existing:
            return existing
        identifier = uuid4()
        number = c.execute(text('UPDATE c0_automatic_sources SET run_number=run_number+1 WHERE id=:id AND run_number<9223372036854775807 RETURNING run_number'), {'id':row['id']}).scalar_one_or_none()
        if number is None:raise UpdateConflict('source_run_limit')
        previous = c.execute(text("SELECT id,state,cursor FROM c0_source_update_runs WHERE definition_id=:id AND revision=:revision ORDER BY number DESC LIMIT 1"), {'id':row['id'],'revision':row['revision']}).mappings().one_or_none()
        cursor = previous['cursor'] if previous and previous['state'] in ('partial','failed') else {}
        c.execute(text('INSERT INTO c0_source_update_runs(id,definition_id,number,revision,cursor) VALUES (:id,:definition,:number,:revision,CAST(:cursor AS jsonb))'),
                  {'id': identifier, 'definition': row['id'], 'number': number, 'revision': row['revision'], 'cursor': json.dumps(cursor)})
        if previous:
            c.execute(text("UPDATE c0_source_update_runs SET cursor='{}' WHERE id=:id"), {'id':previous['id']})
        return identifier

    def _prune_runs(self):
        # Keep the latest summary and active checkpoints; retire bounded old metadata.
        with self.database.engine.begin() as c:
            c.execute(text("""WITH retired AS MATERIALIZED (
                SELECT r.id FROM c0_source_update_runs r JOIN c0_automatic_sources d ON d.id=r.definition_id
                WHERE r.state NOT IN ('queued','running','pending') AND r.created_at<now()-interval '30 days'
                    AND r.number<d.run_number ORDER BY r.created_at,r.id LIMIT 100 FOR UPDATE OF r SKIP LOCKED)
                DELETE FROM c0_source_update_runs USING retired WHERE c0_source_update_runs.id=retired.id"""))

    def claim(self):
        with self.database.engine.begin() as c:
            hold_authority(c)
            # Serialize scheduling and recovery independently of ordinary extraction.
            c.execute(text('SELECT pg_advisory_xact_lock(49410)'))
            c.execute(text("""WITH expired AS MATERIALIZED (SELECT r.id FROM c0_automatic_sources d
                JOIN c0_source_update_runs r ON r.definition_id=d.id
                WHERE r.state='running' AND r.lease_until<clock_timestamp()
                ORDER BY r.lease_until,r.id LIMIT 100 FOR UPDATE OF d,r SKIP LOCKED)
                UPDATE c0_source_update_runs r SET state='queued',lease=NULL FROM expired WHERE r.id=expired.id"""))
            due = c.execute(text('''SELECT d.* FROM c0_automatic_sources d WHERE enabled AND next_run_at<=now() AND NOT EXISTS (SELECT 1 FROM c0_source_update_runs r WHERE r.definition_id=d.id AND r.state IN ('queued','running','pending'))
                ORDER BY next_run_at,id LIMIT 100 FOR UPDATE SKIP LOCKED''')).mappings().all()
            for row in due:
                self._enqueue(c, row)
            row = c.execute(text('''SELECT d.*,r.id AS run_id,r.cursor,r.processed,r.diagnostics FROM c0_automatic_sources d
                JOIN c0_source_update_runs r ON r.definition_id=d.id
                WHERE r.state IN ('queued','pending') AND r.available_at<=now() ORDER BY r.available_at,r.id LIMIT 1 FOR UPDATE OF d,r SKIP LOCKED''')).mappings().one_or_none()
            if row is None:
                return None
            row = dict(row)
            try:
                self._background_actor(c, row)
            except DriveAudienceChanged:
                self._finish(c, row, 'blocked', 'drive_audience_changed')
                return None
            except PermissionDenied:
                self._finish(c, row, 'blocked', 'authority_changed')
                return None
            lease = uuid4()
            c.execute(text("UPDATE c0_source_update_runs SET state='running',lease=:lease,lease_until=now()+interval '2 minutes' WHERE id=:id"), {'id': row['run_id'], 'lease': lease})
            row['lease'] = lease
            return row

    @staticmethod
    def _finish(c, row, state, error=None, cursor=None, retry_after=''):
        retry_at = None
        if retry_after:
            try:
                requested = datetime.fromisoformat(retry_after)
                if requested.tzinfo is not None:
                    now = datetime.now(timezone.utc)
                    retry_at = min(max(requested, now), now+timedelta(days=1))
            except (ValueError, TypeError):
                pass
        c.execute(text('''UPDATE c0_source_update_runs SET state=CAST(:state AS varchar),error_code=:error,lease=NULL,available_at=now(),cursor=CAST(:cursor AS jsonb),
            finished_at=CASE WHEN :state='pending' THEN NULL ELSE now() END WHERE id=:id'''),
            {'id': row['run_id'], 'state': state, 'error': error, 'cursor': json.dumps({} if state in ('complete','blocked','cancelled') else (cursor if cursor is not None else row.get('cursor',{})))})
        if error == 'drive_audience_changed':
            c.execute(text('''UPDATE c0_automatic_sources SET enabled=false,revision=revision+1,
                next_run_at=NULL,updated_at=now() WHERE id=:id'''),{'id':row['id']})
            return
        if state != 'pending':
            c.execute(text('''UPDATE c0_automatic_sources SET next_run_at=CASE WHEN interval_seconds IS NOT NULL
                AND :state<>'blocked' THEN GREATEST(now()+make_interval(secs=>CASE WHEN CAST(:error AS text) IS NULL OR retry_count>=4 THEN interval_seconds ELSE 30*CAST(power(2,retry_count) AS integer) END),COALESCE(CAST(:retry_at AS timestamptz),now())) END,
                retry_count=CASE WHEN CAST(:error AS text) IS NULL OR retry_count>=4 THEN 0 ELSE retry_count+1 END,
                last_success_at=CASE WHEN :state='complete' THEN now() ELSE last_success_at END WHERE id=:id'''),
                {'id': row['id'], 'state': state, 'error': error, 'retry_at': retry_at})

    def fenced(self, c, row):
        hold_authority(c)
        current = self.in_space(row['space_id'])._row(c, row['id'], lock=True)
        run = c.execute(text('SELECT *,lease_until>clock_timestamp() AS lease_current FROM c0_source_update_runs WHERE id=:id FOR UPDATE'), {'id': row['run_id']}).mappings().one_or_none()
        if (current['revision'] != row['revision'] or run is None or run['state'] != 'running'
                or run['lease'] != row['lease'] or not run['lease_current']):
            raise UpdateConflict('source_run_superseded')
        return self._background_actor(c, current)


def cancel_staged(c, identifier):
    """Retire owned pending bytes while retaining complete documents and logical IDs."""
    from .current_content import retire_versions
    rows=c.execute(text('''SELECT i.version_id FROM c0_automatic_source_items i
        JOIN c0_sources s ON s.id=i.source_id JOIN c0_source_versions v ON v.id=i.version_id
        WHERE i.definition_id=:id AND i.version_id IS DISTINCT FROM s.current_version_id
        AND CAST(v.publication_metadata AS jsonb) ? '_automatic_source_revision' '''), {'id':identifier}).scalars().all()
    c.execute(text('''UPDATE c0_automatic_source_items i SET version_id=s.current_version_id,
        content_hash=COALESCE(v.content_hash,''),source_revision=s.revision FROM c0_sources s
        LEFT JOIN c0_source_versions v ON v.id=s.current_version_id
        WHERE i.definition_id=:id AND i.source_id=s.id AND i.version_id=ANY(CAST(:versions AS uuid[]))
        AND i.source_revision=s.revision'''), {'id':identifier,'versions':rows})
    retire_versions(c,rows)


def queued_attachment_actor(c, version, access):
    """Resolve only a queue-only native website stage bound to a saved definition."""
    metadata = version['publication_metadata'] or {}
    if (access is None or metadata.get('_automatic_attachment_queue') is not True
            or version['media_type'] != 'application/pdf' or version['job_id'] is not None):
        raise PermissionDenied()
    try:
        identifier = UUID(metadata['automatic_source_id'])
    except (ValueError, TypeError, KeyError, AttributeError):
        raise PermissionDenied() from None
    service = AutomaticSourceService(None, access).in_space(version['space_id'])
    try:
        definition = service._row(c, identifier)
    except UpdateNotFound:
        raise PermissionDenied() from None
    if (definition['kind'] != 'website' or definition['revision'] != metadata.get('_automatic_source_revision')
            or not definition['config'].get('attachments', {}).get('page_queue')):
        raise PermissionDenied()
    owned = c.execute(text("""SELECT 1 FROM c0_automatic_source_items i
        JOIN c0_sources s ON s.id=i.source_id
        WHERE i.definition_id=:id AND i.source_id=:source AND i.version_id=:version
        AND s.space_id=:space AND NOT s.deleted AND i.source_revision=s.revision"""),
        {'id': identifier, 'source': version['source_id'], 'version': version['id'],
         'space': version['space_id']}).scalar_one_or_none()
    if not owned:
        raise PermissionDenied()
    return service._background_actor(c, definition)


def guard_publication(c, version, access):
    """Recheck native authority at extraction's final atomic publication boundary."""
    metadata=version['publication_metadata'] or {}
    if '_automatic_source_revision' not in metadata:return None
    try:identifier=UUID(metadata['automatic_source_id'])
    except (ValueError,TypeError,KeyError,AttributeError):return None
    managed=c.execute(text('''SELECT i.source_revision=s.revision AS unchanged
        FROM c0_automatic_source_items i JOIN c0_sources s ON s.id=i.source_id
        WHERE i.definition_id=:id AND i.source_id=:source AND i.version_id=:version'''),
        {'id':identifier,'source':version['source_id'],'version':version['id']}).mappings().one_or_none()
    if managed is None:
        # Ordinary user metadata never becomes a native authorization marker.
        return None
    hold_authority(c)
    service=AutomaticSourceService(None,access).in_space(version['space_id'])
    try:
        definition=service._row(c,identifier,lock=True)
        if not managed['unchanged']:raise UpdateConflict('source_changed')
        if access is None or definition['revision']!=metadata['_automatic_source_revision']:
            raise PermissionDenied()
        service._background_actor(c,definition)
    except (PermissionDenied,UpdateNotFound,UpdateConflict) as failure:
        cancel_staged(c,identifier)
        from .current_content import retire_versions
        retire_versions(c,[version['id']])
        c.execute(text("UPDATE c0_source_update_runs SET state='blocked',error_code=:code,lease=NULL,cursor='{}',finished_at=now() WHERE definition_id=:id AND state IN ('queued','running','pending')"),{'id':identifier,'code':'source_changed' if isinstance(failure,UpdateConflict) else 'authority_changed'})
        c.execute(text('UPDATE c0_automatic_sources SET next_run_at=NULL WHERE id=:id'),{'id':identifier})
        return False
    # The private stage marker must not become editable current-source metadata.
    c.execute(text("UPDATE c0_source_versions SET publication_metadata=CAST(publication_metadata AS jsonb)-'_automatic_source_revision'-'_automatic_attachment_queue' WHERE id=:id"),{'id':version['id']})
    return True
