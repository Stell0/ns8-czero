# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded metadata views. Private results never enter these queries."""
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
