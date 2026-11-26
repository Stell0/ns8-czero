# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded metadata views. Private results never enter these queries."""
from collections import Counter
from stat import S_ISREG
from uuid import UUID
from sqlalchemy import text
from .identity import Role
from .sources import SourceNotFound


def page(limit, offset):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError('invalid_page')


def progress(queue, actor, source_id):
    with queue.database.engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        current = queue._space_authorize(c, actor)
        source = c.execute(text('SELECT id,current_version_id FROM c0_sources WHERE id=:id AND space_id=:space AND NOT deleted'),
            {'id':UUID(str(source_id)), 'space':current.space_id}).mappings().one_or_none()
        if source is None: raise SourceNotFound()
        version = c.execute(text('''SELECT id,state,error_code,generation FROM c0_source_versions
            WHERE source_id=:id ORDER BY number DESC LIMIT 1'''), {'id':source['id']}).mappings().one_or_none()
        if version is None: raise SourceNotFound()
        run = c.execute(text('SELECT * FROM c0_extraction_runs WHERE version_id=:id AND processing_generation=:generation'),
            {'id':version['id'],'generation':version['generation']}).mappings().one_or_none()
        result={'source_id':source['id'],'version_id':version['id'],'generation':version['generation'],
            'state':version['state'],'error_code':version['error_code'],'current_available':source['current_version_id'] is not None,'run':None}
        if run:
            result['run']=queue._summary(run,c.execute(text('SELECT clock_timestamp()')).scalar_one())
            counts=c.execute(text('''SELECT count(*) FILTER(WHERE state IN ('succeeded','published')) AS completed,
                count(*) FILTER(WHERE state='retry_wait') AS retrying,
                count(*) FILTER(WHERE state='failed') AS failed FROM c0_extraction_units WHERE run_id=:id'''),{'id':run['id']}).mappings().one()
            result['run'].update(counts)
            state=result['run']['state']
            result['state']=('cancelled' if result['run']['error_code']=='cancelled' else
                'failed' if state in ('failed','superseded') else 'ready' if state=='ready' else
                'retrying' if counts['retrying'] else 'processing' if run['claimed'] else 'queued')
            result['error_code']=result['run']['error_code']
        return result


def reconciliation(queue, actor, *, limit=50, offset=0):
    """Dry-run inspection of current publication and the most recent technical version."""
    page(limit, offset)
    with queue.database.engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        current = queue._space_authorize(c, actor)
        can_recover = current.role is not Role.READER and (
            current.delegated_scopes is None or 'c0:write' in current.delegated_scopes)
        rows = c.execute(text("""WITH selected AS MATERIALIZED (
            SELECT id,title,revision,current_version_id,metadata ? 'parent_external_id' AS managed
            FROM c0_sources WHERE space_id=:space AND NOT deleted
            ORDER BY title,id LIMIT :limit OFFSET :offset
        )
        SELECT s.*, current_doc.id IS NOT NULL AS current_available, v.id AS version_id, v.generation,
            v.state AS version_state, v.error_code AS version_error, v.original_present,
            v.retain_original, v.size_bytes, v.media_type, v.content_hash,
            v.publication_metadata->>'parent_external_id' IS NOT NULL AS managed_stage,
            COALESCE(v.publication_metadata->>'_automatic_attachment_queue' = 'true', false) AS automatic_queue,
            j.state AS job_state, r.id AS run_id, r.revision AS run_revision, r.state AS run_state,
            r.error_code AS run_error, r.expires_at<=clock_timestamp() AS expired,
            EXISTS (SELECT 1 FROM c0_extraction_units u WHERE u.run_id=r.id AND u.state='failed') AS failed_unit
        FROM selected s
        LEFT JOIN c0_documents current_doc ON current_doc.version_id=s.current_version_id
            AND current_doc.space_id=:space
        LEFT JOIN LATERAL (
            SELECT version.* FROM c0_source_versions version
            WHERE version.source_id=s.id AND version.space_id=:space ORDER BY version.number DESC LIMIT 1
        ) v ON true
        LEFT JOIN c0_jobs j ON j.id=v.job_id AND j.space_id=:space
        LEFT JOIN c0_extraction_runs r ON r.version_id=v.id AND r.processing_generation=v.generation
            AND r.space_id=:space
        ORDER BY s.title,s.id"""),
            {'space': current.space_id, 'limit': limit, 'offset': offset}).mappings().all()
        duplicates = Counter(row['content_hash'] for row in rows if row['current_available'] and row['version_id'] == row['current_version_id'])
        return [reconciliation_item(queue, row, can_recover, duplicates) for row in rows]


def reconciliation_item(queue, row, can_recover, duplicates):
    # File stat identifies missing or truncated originals without loading or
    # hashing bodies. The existing recovery operations verify the full hash.
    original = 'not_retained'
    if row['original_present'] or row['retain_original']:
        original = 'missing'
        if row['original_present']:
            try:
                info = (queue.originals.root / row['version_id'].hex).lstat()
                if S_ISREG(info.st_mode) and info.st_size == row['size_bytes']:
                    original = 'present'
            except OSError:
                pass
    error = row['run_error'] or row['version_error']
    state, action = 'ready', 'read_current'
    if row['current_version_id'] and not row['current_available']:
        state, action = 'inconsistent', 'review_inventory'
    elif row['version_id'] is None:
        state, action = 'incomplete', 'reacquire_original'
    elif row['expired'] and row['run_state'] not in ('ready', 'superseded'):
        state, action, error = 'expired', 'reacquire_original', 'staging_expired'
    elif row['run_state'] == 'superseded':
        state = 'cancelled' if error == 'cancelled' else 'stale_dependency'
        action = 'reacquire_original'
    elif row['run_state'] == 'failed' or row['job_state'] in ('failed', 'cancelled') or row['version_state'] == 'failed':
        state, action = 'failed', 'reacquire_original'
        if original == 'present':
            if row['run_state'] == 'failed' and row['failed_unit']:
                action = 'retry_extraction_run'
            elif not row['automatic_queue'] and error not in ('unsupported_scan', 'no_text', 'invalid_pdf', 'too_large'):
                action = 'retry_version'
    elif row['version_state'] == 'queued':
        state = 'running' if row['job_state'] == 'running' or row['run_state'] == 'assembling' else 'queued'
        action = 'wait_for_work'
    elif not row['current_available']:
        state, action = 'incomplete', 'review_inventory'
    elif original == 'missing':
        state, action = 'missing_original', 'reacquire_original'
    if (row['managed'] or row['managed_stage']) and state not in ('ready', 'running', 'queued'):
        action = 'reimport_complete_document'
    if action.startswith('retry_') and not can_recover:
        action = 'ask_editor'
    return {'source_id': row['id'], 'title': row['title'], 'state': state, 'next_step': action,
        'current_version_id': row['current_version_id'], 'current_available': row['current_available'],
        'version_id': row['version_id'] if can_recover or row['version_id'] == row['current_version_id'] else None,
        'processing_generation': row['generation'] if can_recover else None, 'media_type': row['media_type'],
        'error_code': error, 'original': original, 'possible_duplicate': duplicates[row['content_hash']] > 1,
        'extraction_run_id': row['run_id'] if can_recover else None,
        'extraction_run_revision': row['run_revision'] if can_recover else None}


def runs(queue, actor, *, limit=50, offset=0):
    page(limit,offset)
    with queue.database.engine.connect() as c:
        current=queue._space_authorize(c,actor,Role.ADMIN)
        from .extraction_queue import SUMMARY
        rows=c.execute(text('SELECT '+','.join(SUMMARY)+''' FROM c0_extraction_runs
            WHERE space_id=:space ORDER BY created_at DESC,id LIMIT :limit OFFSET :offset'''),
            {'space':current.space_id,'limit':limit,'offset':offset}).mappings()
        now=c.execute(text('SELECT clock_timestamp()')).scalar_one()
        return [queue._summary(row,now) for row in rows]


def units(queue, actor, run_id, *, limit=50, offset=0):
    page(limit,offset)
    with queue.database.engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        current=queue._space_authorize(c,actor,Role.ADMIN)
        run=c.execute(text('SELECT * FROM c0_extraction_runs WHERE space_id=:space AND id=:id'),
            {'space':current.space_id,'id':UUID(str(run_id))}).mappings().one_or_none()
        if run is None: raise SourceNotFound()
        version=c.execute(text('SELECT source_id FROM c0_source_versions WHERE id=:id'),
            {'id':run['version_id']}).scalar_one()
        rows=c.execute(text('''SELECT ordinal,locator,state,attempts,lifetime_attempts,error_code,
            available_at,started_at,finished_at,
            CASE WHEN finished_at IS NOT NULL AND started_at IS NOT NULL THEN
                GREATEST(0,floor(extract(epoch FROM finished_at-started_at)*1000))::bigint
                ELSE NULL END AS duration_ms,reused FROM c0_extraction_units
            WHERE run_id=:id ORDER BY ordinal LIMIT :limit OFFSET :offset'''),
            {'id':run['id'],'limit':limit,'offset':offset}).mappings().all()
        profile=run['profile']
        return {'run':queue._summary(run,c.execute(text('SELECT clock_timestamp()')).scalar_one()),
            'parser':{key:profile[key] for key in ('partitioner','normalization','pypdf','python_docx','chunking') if key in profile},
            'source_id':version,'units':[dict(row) for row in rows],'offset':offset,'limit':limit}
