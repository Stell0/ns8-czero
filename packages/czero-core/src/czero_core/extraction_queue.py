# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in private extraction staging; parsing never owns a DB transaction."""
from dataclasses import dataclass, field
from datetime import timedelta
import hashlib
from importlib.metadata import version
import json
import re
import secrets
import time
from uuid import UUID, uuid4, uuid5

from sqlalchemy import text

from .current_content import check_retired, content_lock
from .extraction import Extracted, ExtractionError, MAX_LOCATIONS, extract_isolated, valid_text
from .identity import Actor, PermissionDenied, Role
from .sources import SourceConflict, SourceNotFound
from .spaces import SpaceBound, hold_authority

TRANSIENT = frozenset({'parser_timeout', 'resource_limit', 'parser_failed', 'lease_expired'})
SUMMARY = ('id','space_id','version_id','processing_generation','state','error_code',
           'expected_units','revision','claimed','succeeded','failed','retried','expires_at')


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _profile():
    return {'partitioner':'whole-document-v1','normalization':1,
            'pypdf':version('pypdf'),'python_docx':version('python-docx')}


def _manifest(source, space, profile):
    return {'space_id':str(space),'version_id':str(source['id']),
            'generation':source['generation'],'original_sha256':source['content_hash'],
            'size_bytes':source['size_bytes'],'media_type':source['media_type'],'profile':profile,
            'units':[{'ordinal':1,'locator':{'kind':'document'}}]}


def _result(result):
    if not isinstance(result, Extracted) or not isinstance(result.text, str):
        raise ExtractionError('parser_failed')
    valid_text(result.text)
    if not result.text.strip():
        raise ExtractionError('no_text')
    if '\r' in result.text or not isinstance(result.locations, list) or len(result.locations)>MAX_LOCATIONS:
        raise ExtractionError('parser_failed')
    for loc in result.locations:
        if (type(loc) is not dict or set(loc)!={'kind','index','start','end'}
            or not isinstance(loc['kind'], str) or not re.fullmatch('[a-z_-]{1,32}', loc['kind'])
            or any(type(loc[key]) is not int for key in ('index','start','end'))
            or loc['index']<1 or not 0<=loc['start']<=loc['end']<=len(result.text)):
            raise ExtractionError('parser_failed')
    return _hash({'text':result.text,'locations':result.locations})


def cancel_versions(connection, version_ids, code='superseded'):
    """Caller holds the content mutex; fence before discarding private results."""
    if not version_ids:
        return 0
    ids = connection.execute(text("""UPDATE c0_extraction_runs SET state='superseded',
        error_code=:code,revision=revision+1,result_bytes=0,result_characters=0
        WHERE version_id=ANY(CAST(:ids AS uuid[])) AND state<>'superseded' RETURNING id"""),
        {'ids':list(version_ids),'code':code}).scalars().all()
    _erase(connection, ids)
    return len(ids)


def _erase(connection, ids):
    if ids:
        connection.execute(text("""UPDATE c0_extraction_units SET state='cancelled',
            lease_token=NULL,lease_deadline=NULL,fence=fence+1,body=NULL,locations=NULL,
            result_sha256=NULL,text_sha256=NULL WHERE run_id=ANY(CAST(:ids AS uuid[]))"""), {'ids':list(ids)})


def cleanup_extractions(connection, *, limit=20):
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError('invalid_limit')
    content_lock(connection)
    ids = connection.execute(text("""SELECT id FROM c0_extraction_runs
        WHERE expires_at<=clock_timestamp() AND error_code IS DISTINCT FROM 'staging_expired'
        ORDER BY expires_at,id LIMIT :limit FOR UPDATE SKIP LOCKED"""), {'limit':limit}).scalars().all()
    if ids:
        _erase(connection, ids)
        connection.execute(text("""UPDATE c0_extraction_runs SET state='failed',error_code='staging_expired',
            revision=revision+1,result_bytes=0,result_characters=0 WHERE id=ANY(CAST(:ids AS uuid[]))"""), {'ids':ids})
    return len(ids)


@dataclass(frozen=True)
class Claim:
    run_id: UUID
    unit_id: UUID
    version_id: UUID
    space_id: UUID
    generation: int
    fence: int
    token: UUID = field(repr=False)
    original: dict = field(repr=False)


class ExtractionQueue(SpaceBound):
    def __init__(self, database, access, originals, *, enabled=False):
        if type(enabled) is not bool:
            raise ValueError('invalid_extraction_flag')
        self.database, self.access, self.originals, self.enabled = database, access, originals, enabled

    def enqueue(self, actor, version_id, *, expected_generation):
        if not self.enabled:
            raise ValueError('extraction_units_disabled')
        if not isinstance(actor, Actor):
            raise PermissionDenied()
        if (actor.delegation is not None or actor.delegated_scopes is not None or actor.session_binding is not None):
            raise ValueError('unsupported_extraction_handoff')
        if type(expected_generation) is not int or expected_generation<1:
            raise ValueError('invalid_generation')
        with self.database.engine.begin() as c:
            content_lock(c); hold_authority(c)
            current = self._space_authorize(c, actor, Role.EDITOR)
            check_retired(c,current.space_id,'source_version',UUID(str(version_id)))
            v = c.execute(text("""SELECT v.* FROM c0_source_versions v JOIN c0_sources s ON s.id=v.source_id
                WHERE v.space_id=:space AND v.id=:id AND NOT s.deleted FOR UPDATE OF v"""),
                {'space':current.space_id,'id':UUID(str(version_id))}).mappings().one_or_none()
            if v is None:
                raise SourceNotFound()
            if v['generation']!=expected_generation or v['state']!='queued':
                raise SourceConflict()
            existing = c.execute(text('SELECT * FROM c0_extraction_runs WHERE version_id=:id AND processing_generation=:generation'),
                {'id':v['id'],'generation':expected_generation}).mappings().one_or_none()
            if existing:
                return self._summary(existing, c.execute(text('SELECT clock_timestamp()')).scalar_one())
            now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
            expiry = v['created_at']+timedelta(hours=24)
            if expiry<=now or not v['original_present']:
                raise ValueError('staging_expired')
            # Only a still-queued legacy attempt can be handed off atomically.
            changed = c.execute(text("""UPDATE c0_jobs SET state='succeeded',finished_at=clock_timestamp(),
                result='{"state":"extraction_staged"}'::jsonb WHERE id=:id AND state='queued'"""), {'id':v['job_id']})
            if changed.rowcount!=1:
                raise SourceConflict()
            profile = _profile()
            manifest = _manifest(v,current.space_id,profile)
            run_id = uuid5(v['id'], 'extraction:'+str(expected_generation))
            row = c.execute(text("""INSERT INTO c0_extraction_runs
                (id,space_id,version_id,actor_id,processing_generation,original_sha256,manifest_sha256,
                 profile,expected_units,state,expires_at) VALUES
                (:id,:space,:version,:actor,:generation,:hash,:manifest,CAST(:profile AS jsonb),1,'extracting',:expiry) RETURNING *"""),
                {'id':run_id,'space':current.space_id,'version':v['id'],'actor':current.user_id,
                 'generation':expected_generation,'hash':v['content_hash'],'manifest':_hash(manifest),
                 'profile':json.dumps(profile),'expiry':min(expiry,now+timedelta(hours=24))}).mappings().one()
            c.execute(text("""INSERT INTO c0_extraction_units(id,space_id,run_id,ordinal,locator,input_sha256)
                VALUES (:id,:space,:run,1,'{"kind":"document"}'::jsonb,:hash)"""),
                {'id':uuid5(run_id,'1'),'space':current.space_id,'run':run_id,'hash':_hash(manifest)})
            return self._summary(row)

    @staticmethod
    def _summary(row, now=None):
        result = {key:row[key] for key in SUMMARY}
        if now is not None and row['expires_at']<=now:
            result.update(state='failed',error_code='staging_expired')
        return result

    def status(self, actor, run_id):
        with self.database.engine.connect() as c:
            current = self._space_authorize(c, actor)
            row = c.execute(text('SELECT '+','.join(SUMMARY)+' FROM c0_extraction_runs WHERE space_id=:space AND id=:id'),
                {'space':current.space_id,'id':UUID(str(run_id))}).mappings().one_or_none()
            if row is None:
                raise SourceNotFound()
            return self._summary(row,c.execute(text('SELECT clock_timestamp()')).scalar_one())

    def cancel(self, actor, run_id):
        with self.database.engine.begin() as c:
            content_lock(c); hold_authority(c)
            current = self._space_authorize(c, actor, Role.EDITOR)
            row = c.execute(text('SELECT * FROM c0_extraction_runs WHERE space_id=:space AND id=:id FOR UPDATE'),
                {'space':current.space_id,'id':UUID(str(run_id))}).mappings().one_or_none()
            if row is None:
                raise SourceNotFound()
            cancel_versions(c, [row['version_id']], 'cancelled')

    def _live(self, c, run, now):
        if run['expires_at']<=now:
            _erase(c, [run['id']])
            c.execute(text("""UPDATE c0_extraction_runs SET state='failed',error_code='staging_expired',
                revision=revision+1,result_bytes=0,result_characters=0 WHERE id=:id"""), {'id':run['id']})
            return False
        source = c.execute(text("""SELECT v.* FROM c0_source_versions v JOIN c0_sources s ON s.id=v.source_id
            WHERE v.id=:id AND v.space_id=:space AND NOT s.deleted"""),
            {'id':run['version_id'],'space':run['space_id']}).mappings().one_or_none()
        if (source is None or source['generation']!=run['processing_generation'] or source['state']!='queued'
            or source['content_hash']!=run['original_sha256']):
            cancel_versions(c, [run['version_id']])
            return False
        if run['profile']!=_profile() or run['manifest_sha256']!=_hash(_manifest(source,run['space_id'],run['profile'])):
            cancel_versions(c,[run['version_id']],'manifest_mismatch')
            return False
        try:
            if run['actor_id'] is None:
                raise PermissionDenied()
            self.in_space(run['space_id'])._space_authorize(c, Actor(run['actor_id'],Role.READER),Role.EDITOR)
        except PermissionDenied:
            cancel_versions(c, [run['version_id']], 'authority_lost')
            return False
        return source

    def claim(self):
        if not self.enabled:
            return None
        with self.database.engine.begin() as c:
            content_lock(c); hold_authority(c)
            now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
            run = c.execute(text("""SELECT r.* FROM c0_extraction_runs r WHERE r.state='extracting'
                AND EXISTS(SELECT 1 FROM c0_extraction_units u WHERE u.run_id=r.id AND
                    ((u.state IN ('queued','retry_wait') AND u.available_at<=:now)
                     OR (u.state='leased' AND u.lease_deadline<=:now)))
                ORDER BY r.created_at,r.id LIMIT 1 FOR UPDATE SKIP LOCKED"""), {'now':now}).mappings().one_or_none()
            if run is None:
                return None
            source = self._live(c, run, now)
            if source is False:
                return None
            unit = c.execute(text("""SELECT * FROM c0_extraction_units WHERE run_id=:id AND
                ((state IN ('queued','retry_wait') AND available_at<=:now) OR (state='leased' AND lease_deadline<=:now))
                ORDER BY ordinal LIMIT 1 FOR UPDATE SKIP LOCKED"""), {'id':run['id'],'now':now}).mappings().one()
            if unit['input_sha256']!=run['manifest_sha256'] or unit['locator']!={'kind':'document'}:
                cancel_versions(c,[run['version_id']],'manifest_mismatch')
                return None
            if unit['state']=='leased':
                self._fail(c, run, unit, 'lease_expired', now)
                return None
            token = uuid4()
            c.execute(text("""UPDATE c0_extraction_units SET state='leased',attempts=attempts+1,fence=fence+1,
                lease_token=:token,lease_deadline=:deadline,started_at=:now,finished_at=NULL,error_code=NULL WHERE id=:id"""),
                {'id':unit['id'],'token':token,'deadline':now+timedelta(seconds=60),'now':now})
            c.execute(text('UPDATE c0_extraction_runs SET claimed=claimed+1,revision=revision+1 WHERE id=:id'), {'id':run['id']})
            return Claim(run['id'],unit['id'],source['id'],run['space_id'],source['generation'],unit['fence']+1,token,dict(source))

    def _attempt(self, c, claim, *, replay=False):
        content_lock(c); hold_authority(c)
        now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
        run = c.execute(text('SELECT * FROM c0_extraction_runs WHERE id=:id AND space_id=:space FOR UPDATE'),
            {'id':claim.run_id,'space':claim.space_id}).mappings().one_or_none()
        if (run is None or run['state'] not in ('extracting','assembling') or run['version_id']!=claim.version_id
            or run['processing_generation']!=claim.generation or self._live(c,run,now) is False):
            return None
        unit = c.execute(text('SELECT * FROM c0_extraction_units WHERE id=:id AND run_id=:run FOR UPDATE'),
            {'id':claim.unit_id,'run':claim.run_id}).mappings().one_or_none()
        if unit is None or unit['lease_token']!=claim.token or unit['fence']!=claim.fence:
            return None
        if unit['input_sha256']!=run['manifest_sha256'] or unit['locator']!={'kind':'document'}:
            cancel_versions(c,[run['version_id']],'manifest_mismatch')
            return None
        if replay and unit['state']=='succeeded':
            return run,unit,now
        if unit['state']!='leased' or unit['lease_deadline']<=now or run['state']!='extracting':
            return None
        return run,unit,now

    def complete(self, claim, result):
        digest = _result(result)
        with self.database.engine.begin() as c:
            attempt = self._attempt(c, claim, replay=True)
            if attempt is None:
                return False
            run,unit,now = attempt
            if unit['state']=='succeeded':
                return unit['result_sha256']==digest==_result(Extracted(unit['body'],unit['locations']))
            if (run['result_bytes']+len(result.text.encode())>2097152
                or run['result_characters']+len(result.text)>1000000):
                self._fail(c,run,unit,'too_large',now)
                return False
            c.execute(text("""UPDATE c0_extraction_units SET state='succeeded',body=:body,locations=CAST(:locations AS jsonb),
                result_sha256=:hash,text_sha256=:text_hash,lease_deadline=NULL,finished_at=:now WHERE id=:id"""),
                {'id':unit['id'],'body':result.text,'locations':json.dumps(result.locations),'hash':digest,'text_hash':result.text_hash,'now':now})
            c.execute(text("""UPDATE c0_extraction_runs SET succeeded=succeeded+1,revision=revision+1,error_code=NULL,
                result_bytes=result_bytes+:bytes,result_characters=result_characters+:characters,
                state=CASE WHEN succeeded+1=expected_units THEN 'assembling' ELSE 'extracting' END WHERE id=:id"""),
                {'id':run['id'],'bytes':len(result.text.encode()),'characters':len(result.text)})
            return True

    @staticmethod
    def _fail(c, run, unit, code, now):
        again = code in TRANSIENT and unit['attempts']<3
        delay = min(300,10*2**max(0,unit['attempts']-1))+secrets.randbelow(3)
        c.execute(text("""UPDATE c0_extraction_units SET state=:state,error_code=:code,lease_token=NULL,
            lease_deadline=NULL,available_at=:due,finished_at=:finished WHERE id=:id"""),
            {'id':unit['id'],'state':'retry_wait' if again else 'failed','code':code,
             'due':now+timedelta(seconds=delay),'finished':None if again else now})
        c.execute(text("""UPDATE c0_extraction_runs SET failed=failed+1,retried=retried+:retry,
            revision=revision+1,state=:state,error_code=:code WHERE id=:id"""),
            {'id':run['id'],'retry':int(again),'state':'extracting' if again else 'failed','code':code})

    def fail(self, claim, code):
        code = ExtractionError(code).code
        with self.database.engine.begin() as c:
            attempt = self._attempt(c,claim)
            if attempt is None:
                return False
            self._fail(c,*attempt[:2],code,attempt[2])
            return True

    def cleanup(self, *, limit=20):
        with self.database.engine.begin() as c:
            return cleanup_extractions(c,limit=limit)


class ExtractionWorker:
    """Bounded one-shot runner. Claim, parse and result commit are separate phases."""
    def __init__(self, queue):
        self.queue = queue

    def tick(self, *, max_units=20, budget_seconds=90):
        if type(max_units) is not int or not 1<=max_units<=20 or type(budget_seconds) is not int or not 1<=budget_seconds<=90:
            raise ValueError('invalid_worker_limit')
        if not self.queue.enabled:
            return 0
        self.queue.cleanup()
        started = time.monotonic(); processed = 0
        while processed<max_units and time.monotonic()-started<budget_seconds:
            claim = self.queue.claim()
            if claim is None:
                break
            try:
                path = self.queue.originals.check(claim.original)
                result = extract_isolated(path,claim.original['media_type'])
                self.queue.originals.check(claim.original)
                self.queue.complete(claim,result)
            except ExtractionError as error:
                self.queue.fail(claim,error.code)
            processed += 1
        return processed
