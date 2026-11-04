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
from .extraction import Extracted, ExtractionError, MAX_LOCATIONS, extract_isolated, valid_text, chunks
from .pdf_units import inventory_isolated, extract_page_isolated, validate_page, assemble_pdf
from .document_units import (DOCX,inventory_isolated as document_inventory,
    extract_unit_isolated,validate_spec,validate_fragment,locators as document_locators,assemble as assemble_document)
from .local_ocr import preflight as ocr_preflight,validate_profile as validate_ocr,validate_provenance,extract_unit as ocr_extract
from .structure import PROFILES,build as build_structure,section_chunks
from .extraction_cache import ReusedUnit,owners as cache_owners,live as cache_live,output as cache_output
from .identity import Actor, PermissionDenied, Role
from .sources import SourceConflict, SourceNotFound
from .spaces import SpaceBound, hold_authority

TRANSIENT = frozenset({'parser_timeout', 'resource_limit', 'parser_failed', 'lease_expired'})
SUMMARY = ('id','space_id','version_id','processing_generation','state','error_code',
           'expected_units','revision','claimed','succeeded','failed','retried','expires_at',
           'wait_ms','run_ms','retry_wait_ms','timeout_count','cache_hits','cache_misses','reused_bytes')


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


FORMATS={'docx-block-v1':DOCX,'markdown-block-v1':'text/markdown','text-block-v1':'text/plain'}


def _profile(partitioner='whole-document-v1',pages=None,*,spec=None,chunking=None,ocr=None):
    result={'partitioner':partitioner,'normalization':1,
            'pypdf':version('pypdf'),'python_docx':version('python-docx')}
    if chunking is not None:
        if chunking not in PROFILES: raise ValueError('invalid_chunking_profile')
        result['chunking']=chunking
    if ocr is not None:
        if partitioner!='pdf-page-v1': raise ValueError('invalid_ocr_profile')
        result['ocr']=validate_ocr(ocr)
    if partitioner=='pdf-page-v1':
        if type(pages) is not int or not 1<=pages<=200: raise ValueError('invalid_manifest')
        result['pages']=pages
    elif partitioner in FORMATS:
        result['spec']=validate_spec(FORMATS[partitioner],spec)
    elif partitioner!='whole-document-v1': raise ValueError('invalid_manifest')
    return result


def _locators(profile):
    kind=profile['partitioner']
    if kind=='pdf-page-v1': return [{'kind':'page','first':page,'last':page} for page in range(1,profile['pages']+1)]
    if kind in FORMATS: return document_locators(FORMATS[kind],profile['spec'])
    return [{'kind':'document'}]


def _manifest(source, space, profile):
    return {'space_id':str(space),'version_id':str(source['id']),
            'generation':source['generation'],'original_sha256':source['content_hash'],
            'size_bytes':source['size_bytes'],'media_type':source['media_type'],'profile':profile,
            'units':[{'ordinal':ordinal,'locator':locator} for ordinal,locator in enumerate(_locators(profile),1)]}


def _locator(profile,ordinal):
    values=_locators(profile)
    return values[ordinal-1] if 1<=ordinal<=len(values) else {}


def _fingerprint(manifest,profile,ordinal,locator):
    if profile['partitioner']=='whole-document-v1': return manifest
    return _hash({'manifest':manifest,'ordinal':ordinal,'locator':locator})


def _result(result,*,allow_blank=False):
    if not isinstance(result, Extracted) or not isinstance(result.text, str):
        raise ExtractionError('parser_failed')
    valid_text(result.text)
    if not result.text.strip() and not allow_blank:
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
            result_sha256=NULL,text_sha256=NULL,provenance=NULL,provenance_sha256=NULL WHERE run_id=ANY(CAST(:ids AS uuid[]))"""), {'ids':list(ids)})


def cleanup_extractions(connection, *, limit=20):
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError('invalid_limit')
    content_lock(connection)
    ids = connection.execute(text("""SELECT id FROM c0_extraction_runs
        WHERE expires_at<=clock_timestamp() AND error_code IS DISTINCT FROM 'staging_expired'
        AND state NOT IN ('ready','superseded')
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
    ordinal: int = 1
    locator: dict = field(default_factory=lambda:{'kind':'document'})
    profile: dict = field(default_factory=dict,repr=False)


class ExtractionQueue(SpaceBound):
    def __init__(self, database, access, originals, *, enabled=False,
                 instance_workers=2,document_workers=2,space_workers=2,max_queued_units=2000,max_staging_bytes=33554432,chunking_profile='sections-v1',ocr_language=None,cache_enabled=True):
        if type(enabled) is not bool:
            raise ValueError('invalid_extraction_flag')
        self.database, self.access, self.originals, self.enabled = database, access, originals, enabled
        if chunking_profile not in PROFILES: raise ValueError('invalid_chunking_profile')
        self.chunking_profile=chunking_profile
        if type(cache_enabled) is not bool: raise ValueError('invalid_cache_flag')
        self.cache_enabled=cache_enabled
        self.ocr_profile=ocr_preflight(ocr_language) if ocr_language is not None else None
        for limit in (instance_workers,document_workers,space_workers):
            if type(limit) is not int or not 1<=limit<=4: raise ValueError('invalid_worker_limit')
        if type(max_queued_units) is not int or not 200<=max_queued_units<=4000: raise ValueError('invalid_queue_limit')
        if type(max_staging_bytes) is not int or not 2097152<=max_staging_bytes<=67108864: raise ValueError('invalid_staging_limit')
        self.document_workers,self.space_workers=document_workers,space_workers
        self.instance_workers=instance_workers
        self.max_queued_units,self.max_staging_bytes=max_queued_units,max_staging_bytes

    def enqueue(self, actor, version_id, *, expected_generation):
        if not self.enabled:
            raise ValueError('extraction_units_disabled')
        if not isinstance(actor, Actor):
            raise PermissionDenied()
        if (actor.api_key_binding is not None or actor.delegation is not None or actor.delegated_scopes is not None or actor.session_binding is not None):
            raise ValueError('unsupported_extraction_handoff')
        if type(expected_generation) is not int or expected_generation<1:
            raise ValueError('invalid_generation')
        # Read/preflight without holding any work connection or content lock.
        with self.database.engine.connect() as c:
            current=self._space_authorize(c,actor,Role.EDITOR)
            check_retired(c,current.space_id,'source_version',UUID(str(version_id)))
            original=c.execute(text('''SELECT v.* FROM c0_source_versions v JOIN c0_sources s ON s.id=v.source_id
                WHERE v.space_id=:space AND v.id=:id AND NOT s.deleted'''),
                {'space':current.space_id,'id':UUID(str(version_id))}).mappings().one_or_none()
            if original is None: raise SourceNotFound()
            if original['generation']!=expected_generation or original['state']!='queued': raise SourceConflict()
            existing=c.execute(text('SELECT * FROM c0_extraction_runs WHERE version_id=:id AND processing_generation=:generation'),
                {'id':original['id'],'generation':expected_generation}).mappings().one_or_none()
            if existing: return self._summary(existing,c.execute(text('SELECT clock_timestamp()')).scalar_one())
            original=dict(original)
        profile=_profile()
        if original['media_type']=='application/pdf':
            profile=_profile('pdf-page-v1',inventory_isolated(self.originals.check(original)),ocr=self.ocr_profile)
            self.originals.check(original)
        elif original['media_type']==DOCX or original['size_bytes']>65536:
            spec=document_inventory(self.originals.check(original),original['media_type'])
            self.originals.check(original)
            if original['media_type']==DOCX:
                if spec['blocks']>64 or spec['characters']>65536: profile=_profile('docx-block-v1',spec=spec)
            else:
                profile=_profile('markdown-block-v1' if original['media_type']=='text/markdown' else 'text-block-v1',spec=spec)
        profile['chunking']=self.chunking_profile
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
            if any(v[key]!=original[key] for key in ('content_hash','size_bytes','media_type','original_present')):
                raise SourceConflict()
            existing = c.execute(text('SELECT * FROM c0_extraction_runs WHERE version_id=:id AND processing_generation=:generation'),
                {'id':v['id'],'generation':expected_generation}).mappings().one_or_none()
            if existing:
                return self._summary(existing, c.execute(text('SELECT clock_timestamp()')).scalar_one())
            counts=c.execute(text("""SELECT count(*) AS total,
                count(*) FILTER(WHERE u.space_id=:space) AS selected FROM c0_extraction_units u
                JOIN c0_extraction_runs r ON r.id=u.run_id
                WHERE r.state IN ('extracting','assembling','failed') AND r.expires_at>clock_timestamp()
                AND u.state IN ('queued','leased','retry_wait')"""),{'space':current.space_id}).mappings().one()
            count=len(_locators(profile))
            if counts['total']+count>self.max_queued_units or counts['selected']+count>max(200,self.max_queued_units//2):
                raise ValueError('extraction_queue_full')
            now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
            expiry = now+timedelta(hours=24)
            if not v['original_present']:
                raise ValueError('staging_expired')
            # Only a still-queued legacy attempt can be handed off atomically.
            changed = c.execute(text("""UPDATE c0_jobs SET state='succeeded',finished_at=clock_timestamp(),
                result='{"state":"extraction_staged"}'::jsonb WHERE id=:id AND state='queued'"""), {'id':v['job_id']})
            if changed.rowcount!=1:
                raise SourceConflict()
            manifest = _manifest(v,current.space_id,profile)
            run_id = uuid5(v['id'], 'extraction:'+str(expected_generation))
            row = c.execute(text("""INSERT INTO c0_extraction_runs
                (id,space_id,version_id,actor_id,processing_generation,original_sha256,manifest_sha256,
                 profile,expected_units,state,expires_at) VALUES
                (:id,:space,:version,:actor,:generation,:hash,:manifest,CAST(:profile AS jsonb),:count,'extracting',:expiry) RETURNING *"""),
                {'id':run_id,'space':current.space_id,'version':v['id'],'actor':current.user_id,
                 'generation':expected_generation,'hash':v['content_hash'],'manifest':_hash(manifest),
                 'profile':json.dumps(profile),'count':len(manifest['units']),'expiry':expiry}).mappings().one()
            c.execute(text("""INSERT INTO c0_extraction_units(id,space_id,run_id,ordinal,locator,input_sha256)
                VALUES (:id,:space,:run,:ordinal,CAST(:locator AS jsonb),:hash)"""),
                [{'id':uuid5(run_id,str(unit['ordinal'])),'space':current.space_id,'run':run_id,
                  'ordinal':unit['ordinal'],'locator':json.dumps(unit['locator']),
                  'hash':_fingerprint(_hash(manifest),profile,unit['ordinal'],unit['locator'])} for unit in manifest['units']])
            return self._summary(row)

    @staticmethod
    def _summary(row, now=None):
        result = {key:row[key] for key in SUMMARY}
        if now is not None and row['state'] not in ('ready','superseded') and row['expires_at']<=now:
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

    def progress(self, actor, source_id):
        from .extraction_status import progress
        return progress(self,actor,source_id)

    def runs(self, actor, *, limit=50, offset=0):
        from .extraction_status import runs
        return runs(self,actor,limit=limit,offset=offset)

    def units(self, actor, run_id, *, limit=50, offset=0):
        from .extraction_status import units
        return units(self,actor,run_id,limit=limit,offset=offset)

    def cancel(self, actor, run_id, *, expected_revision=None):
        with self.database.engine.begin() as c:
            content_lock(c); hold_authority(c)
            current = self._space_authorize(c, actor, Role.EDITOR)
            row = c.execute(text('SELECT * FROM c0_extraction_runs WHERE space_id=:space AND id=:id FOR UPDATE'),
                {'space':current.space_id,'id':UUID(str(run_id))}).mappings().one_or_none()
            if row is None:
                raise SourceNotFound()
            if row['state']=='superseded' and row['error_code']=='cancelled':
                return self._summary(row)
            if row['state'] in ('ready','superseded') or (expected_revision is not None
                    and (type(expected_revision) is not int or expected_revision!=row['revision'])):
                raise SourceConflict()
            cancel_versions(c, [row['version_id']], 'cancelled')
            return self._summary(c.execute(text('SELECT * FROM c0_extraction_runs WHERE id=:id'),
                {'id':row['id']}).mappings().one())

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
        try:
            profile=run['profile']
            valid=(profile==_profile(profile.get('partitioner'),profile.get('pages'),spec=profile.get('spec'),chunking=profile.get('chunking'),ocr=profile.get('ocr'))
                and run['expected_units']==len(_locators(profile))
                and (profile['partitioner']!='pdf-page-v1' or source['media_type']=='application/pdf')
                and (profile['partitioner'] not in FORMATS or source['media_type']==FORMATS[profile['partitioner']])
                and run['manifest_sha256']==_hash(_manifest(source,run['space_id'],profile)))
        except (ValueError,TypeError,KeyError): valid=False
        if not valid:
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
                AND (SELECT count(*) FROM c0_extraction_units a
                    WHERE a.state='leased' AND a.lease_deadline>:now)<:instance_limit
                AND (SELECT count(*) FROM c0_extraction_units a WHERE a.run_id=r.id
                    AND a.state='leased' AND a.lease_deadline>:now)<:document_limit
                AND (SELECT count(*) FROM c0_extraction_units a WHERE a.space_id=r.space_id
                    AND a.state='leased' AND a.lease_deadline>:now)<:space_limit
                AND EXISTS(SELECT 1 FROM c0_extraction_units u WHERE u.run_id=r.id AND
                    ((u.state IN ('queued','retry_wait') AND u.available_at<=:now)
                     OR (u.state='leased' AND u.lease_deadline<=:now)))
                ORDER BY COALESCE(r.last_claimed_at,r.created_at),r.created_at,r.id LIMIT 1 FOR UPDATE SKIP LOCKED"""),
                {'now':now,'instance_limit':self.instance_workers,'document_limit':self.document_workers,'space_limit':self.space_workers}).mappings().one_or_none()
            if run is None:
                return None
            source = self._live(c, run, now)
            if source is False:
                return None
            unit = c.execute(text("""SELECT * FROM c0_extraction_units WHERE run_id=:id AND
                ((state IN ('queued','retry_wait') AND available_at<=:now) OR (state='leased' AND lease_deadline<=:now))
                ORDER BY ordinal LIMIT 1 FOR UPDATE SKIP LOCKED"""), {'id':run['id'],'now':now}).mappings().one()
            locator=_locator(run['profile'],unit['ordinal'])
            if (unit['ordinal']>run['expected_units'] or _hash(unit['locator'])!=_hash(locator)
                or unit['input_sha256']!=_fingerprint(run['manifest_sha256'],run['profile'],unit['ordinal'],locator)):
                cancel_versions(c,[run['version_id']],'manifest_mismatch')
                return None
            if unit['state']=='leased':
                self._fail(c, run, unit, 'lease_expired', now)
                return None
            token = uuid4()
            c.execute(text("""UPDATE c0_extraction_units SET state='leased',attempts=attempts+1,lifetime_attempts=lifetime_attempts+1,fence=fence+1,
                lease_token=:token,lease_deadline=:deadline,started_at=:now,finished_at=NULL,error_code=NULL WHERE id=:id"""),
                {'id':unit['id'],'token':token,'deadline':now+timedelta(seconds=60),'now':now})
            wait=max(0,int((now-unit['available_at']).total_seconds()*1000))
            retry_wait=(max(0,int((now-unit['finished_at']).total_seconds()*1000))
                if unit['state']=='retry_wait' and unit['finished_at'] else 0)
            c.execute(text('''UPDATE c0_extraction_runs SET claimed=claimed+1,revision=revision+1,
                last_claimed_at=:now,wait_ms=wait_ms+:wait,retry_wait_ms=retry_wait_ms+:retry_wait WHERE id=:id'''),
                {'id':run['id'],'now':now,'wait':wait,'retry_wait':retry_wait})
            return Claim(run['id'],unit['id'],source['id'],run['space_id'],source['generation'],unit['fence']+1,token,dict(source),unit['ordinal'],locator,dict(run['profile']))

    def _attempt(self, c, claim, *, replay=False):
        content_lock(c); hold_authority(c)
        now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
        run = c.execute(text('SELECT * FROM c0_extraction_runs WHERE id=:id AND space_id=:space FOR UPDATE'),
            {'id':claim.run_id,'space':claim.space_id}).mappings().one_or_none()
        if run is not None and _hash(claim.profile)!=_hash(run['profile']): return None
        if replay and run is not None and run['state']=='ready':
            try:
                if run['actor_id'] is None: raise PermissionDenied()
                self.in_space(run['space_id'])._space_authorize(c,Actor(run['actor_id'],Role.READER),Role.EDITOR)
            except PermissionDenied: return None
            unit=c.execute(text('SELECT * FROM c0_extraction_units WHERE id=:id AND run_id=:run'),
                {'id':claim.unit_id,'run':claim.run_id}).mappings().one_or_none()
            if (unit is not None and unit['state']=='published' and unit['lease_token']==claim.token
                and unit['fence']==claim.fence and unit['ordinal']==claim.ordinal
                and run['version_id']==claim.version_id and run['processing_generation']==claim.generation
                and _hash(unit['locator'])==_hash(claim.locator)):
                return run,unit,now
            return None
        if (run is None or run['state'] not in ('extracting','assembling') or run['version_id']!=claim.version_id
            or run['processing_generation']!=claim.generation or self._live(c,run,now) is False):
            return None
        unit = c.execute(text('SELECT * FROM c0_extraction_units WHERE id=:id AND run_id=:run FOR UPDATE'),
            {'id':claim.unit_id,'run':claim.run_id}).mappings().one_or_none()
        if unit is None or unit['lease_token']!=claim.token or unit['fence']!=claim.fence:
            return None
        locator=_locator(run['profile'],unit['ordinal'])
        if (unit['ordinal']>run['expected_units'] or _hash(unit['locator'])!=_hash(locator)
            or claim.ordinal!=unit['ordinal'] or _hash(claim.locator)!=_hash(locator)
            or unit['input_sha256']!=_fingerprint(run['manifest_sha256'],run['profile'],unit['ordinal'],locator)):
            cancel_versions(c,[run['version_id']],'manifest_mismatch')
            return None
        if replay and unit['state']=='succeeded':
            return run,unit,now
        if unit['state']!='leased' or unit['lease_deadline']<=now or run['state']!='extracting':
            return None
        return run,unit,now

    @staticmethod
    def _cache_manifest(owner):
        try:
            source={'id':owner['version_id'],'generation':owner['processing_generation'],
                'content_hash':owner['original_sha256'],'size_bytes':owner['size_bytes'],'media_type':owner['media_type']}
            profile=owner['profile']
            digest=_hash(_manifest(source,owner['space_id'],profile))
            return (digest==owner['manifest_sha256'] and owner['expected_units']==len(_locators(profile))
                and owner['input_sha256']==_fingerprint(digest,profile,owner['ordinal'],owner['locator']))
        except (ValueError,TypeError,KeyError): return False

    def cached(self,claim):
        if not self.cache_enabled: return None
        with self.database.engine.begin() as c:
            attempt=self._attempt(c,claim)
            if attempt is None: return None
            run,_,now=attempt
            eligible=('ocr' not in claim.profile or self.ocr_profile==claim.profile['ocr'])
            if eligible:
                for owner in cache_owners(c,claim):
                    if not self._cache_manifest(owner) or not cache_live(self,c,owner,now): continue
                    try:
                        evidence,metadata=cache_output(c,owner)
                        digest=_result(evidence,allow_blank=claim.locator['kind']!='document')
                        if (digest!=owner['result_sha256'] or evidence.text_hash!=owner['text_sha256']
                            or (_hash(metadata) if metadata is not None else None)!=owner['provenance_sha256']): continue
                        return ReusedUnit(owner['id'],digest,owner['provenance_sha256'],evidence,metadata)
                    except (ExtractionError,ValueError,TypeError,KeyError,IndexError): continue
            c.execute(text('UPDATE c0_extraction_runs SET cache_misses=cache_misses+1 WHERE id=:id'),{'id':run['id']})
            return None

    def complete(self, claim, result,*,provenance=None,reused=None):
        page=claim.locator.get('kind')=='page'
        fragment=claim.locator.get('kind') in ('blocks','characters')
        if page: validate_page(result,claim.ordinal)
        if fragment: validate_fragment(result,claim.locator)
        digest = _result(result,allow_blank=page or fragment)
        with self.database.engine.begin() as c:
            attempt = self._attempt(c, claim, replay=True)
            if attempt is None:
                return False
            run,unit,now = attempt
            if provenance is not None:
                if not page or 'ocr' not in run['profile']: raise ExtractionError('parser_failed')
                validate_provenance(provenance,run['profile']['ocr'],claim.ordinal)
            metadata_hash=_hash(provenance) if provenance is not None else None
            if unit['state'] in ('published','succeeded') and unit['provenance_sha256']!=metadata_hash: return False
            if unit['state']=='published': return unit['result_sha256']==digest
            if unit['state']=='succeeded':
                return unit['result_sha256']==digest==_result(Extracted(unit['body'],unit['locations']),allow_blank=page or fragment)
            if reused is not None:
                if not isinstance(reused,ReusedUnit): raise ValueError('invalid_cache_proof')
                owners=cache_owners(c,claim,owner_id=reused.owner_id)
                valid=(self.cache_enabled and len(owners)==1 and self._cache_manifest(owners[0]) and cache_live(self,c,owners[0],now)
                    and owners[0]['result_sha256']==reused.result_sha256==digest
                    and owners[0]['provenance_sha256']==reused.provenance_sha256==metadata_hash)
                if not valid:
                    c.execute(text('UPDATE c0_extraction_runs SET cache_misses=cache_misses+1 WHERE id=:id'),{'id':run['id']})
                    return False
            if (run['result_bytes']+len(result.text.encode())>2097152
                or run['result_characters']+len(result.text)>1000000):
                self._fail(c,run,unit,'too_large',now)
                return False
            staged=c.execute(text("""SELECT COALESCE(sum(result_bytes),0) FROM c0_extraction_runs
                WHERE state IN ('extracting','assembling','failed') AND expires_at>clock_timestamp()""")).scalar_one()
            if staged+len(result.text.encode())>self.max_staging_bytes:
                self._fail(c,run,unit,'resource_limit',now)
                return False
            c.execute(text("""UPDATE c0_extraction_units SET state='succeeded',body=:body,locations=CAST(:locations AS jsonb),
                reused=:reused,result_sha256=:hash,text_sha256=:text_hash,provenance=CAST(:provenance AS jsonb),provenance_sha256=:provenance_hash,lease_deadline=NULL,finished_at=:now WHERE id=:id"""),
                {'id':unit['id'],'body':result.text,'locations':json.dumps(result.locations),'hash':digest,'text_hash':result.text_hash,'now':now,'provenance':json.dumps(provenance) if provenance is not None else None,'provenance_hash':metadata_hash,'reused':reused is not None})
            c.execute(text("""UPDATE c0_extraction_runs SET succeeded=succeeded+1,revision=revision+1,error_code=NULL,
                result_bytes=result_bytes+:bytes,result_characters=result_characters+:characters,run_ms=run_ms+:duration,
                cache_hits=cache_hits+:hit,reused_bytes=reused_bytes+:reused,
                state=CASE WHEN succeeded+1=expected_units THEN 'assembling' ELSE 'extracting' END WHERE id=:id"""),
                {'id':run['id'],'bytes':len(result.text.encode()),'characters':len(result.text),
                 'duration':max(0,min(86400000,int((now-unit['started_at']).total_seconds()*1000))),
                 'hit':int(reused is not None),'reused':len(result.text.encode()) if reused is not None else 0})
            return True

    @staticmethod
    def _fail(c, run, unit, code, now):
        again = code in TRANSIENT and unit['attempts']<3
        delay = min(300,10*2**max(0,unit['attempts']-1))+secrets.randbelow(3)
        c.execute(text("""UPDATE c0_extraction_units SET state=:state,error_code=:code,lease_token=NULL,
            lease_deadline=NULL,available_at=:due,finished_at=:finished WHERE id=:id"""),
            {'id':unit['id'],'state':'retry_wait' if again else 'failed','code':code,
             'due':now+timedelta(seconds=delay),'finished':now})
        c.execute(text("""UPDATE c0_extraction_runs SET failed=failed+1,retried=retried+:retry,
            revision=revision+1,state=:state,error_code=:code,run_ms=run_ms+:duration,
            timeout_count=timeout_count+:timeout WHERE id=:id"""),
            {'id':run['id'],'retry':int(again),'state':'extracting' if again else 'failed','code':code,
             'duration':max(0,min(86400000,int((now-unit['started_at']).total_seconds()*1000))) if unit['started_at'] else 0,
             'timeout':int(code in ('parser_timeout','lease_expired'))})

    def fail(self, claim, code):
        code = ExtractionError(code).code
        with self.database.engine.begin() as c:
            attempt = self._attempt(c,claim)
            if attempt is None:
                return False
            self._fail(c,*attempt[:2],code,attempt[2])
            return True

    def retry_failed(self,actor,run_id,*,expected_revision,idempotency_key):
        from .receipts import _KEY
        from .current_content import ContentSuperseded
        if not isinstance(actor,Actor): raise PermissionDenied()
        # This authorizes an operator action, not a new durable handoff. _live
        # still checks the original submitting account and selected space.
        if type(expected_revision) is not int or expected_revision<1: raise ValueError('invalid_revision')
        if not isinstance(idempotency_key,str) or not _KEY.fullmatch(idempotency_key):
            raise ValueError('invalid_idempotency_key')
        identifier=UUID(str(run_id))
        fingerprint=_hash({'operation':'extraction.retry','run':str(identifier),'revision':expected_revision})
        receipt_key='extraction.retry:'+hashlib.sha256(idempotency_key.encode()).hexdigest()
        with self.database.engine.connect() as c:
            current=self._space_authorize(c,actor,Role.EDITOR)
            run=c.execute(text('SELECT * FROM c0_extraction_runs WHERE space_id=:space AND id=:id'),
                {'space':current.space_id,'id':identifier}).mappings().one_or_none()
            if run is None: raise SourceNotFound()
            if run['state'] not in ('ready','superseded') and run['expires_at']<=c.execute(text('SELECT clock_timestamp()')).scalar_one():
                raise ValueError('staging_expired')
            original=c.execute(text('SELECT * FROM c0_source_versions WHERE id=:id'),{'id':run['version_id']}).mappings().one_or_none()
            original=dict(original) if original is not None else None
            needs_original=run['state'] not in ('ready','superseded')
        if needs_original:
            if original is None: raise SourceNotFound()
            self.originals.check(original)
        with self.database.engine.begin() as c:
            content_lock(c); hold_authority(c)
            current=self._space_authorize(c,actor,Role.EDITOR)
            run=c.execute(text('SELECT * FROM c0_extraction_runs WHERE space_id=:space AND id=:id FOR UPDATE'),
                {'space':current.space_id,'id':identifier}).mappings().one_or_none()
            if run is None: raise SourceNotFound()
            check_retired(c,current.space_id,'source_version',run['version_id'])
            now=c.execute(text('SELECT clock_timestamp()')).scalar_one()
            if run['state']=='superseded': raise ContentSuperseded()
            if run['state']!='ready' and run['expires_at']<=now: raise ValueError('staging_expired')
            receipt=c.execute(text('''SELECT fingerprint,result FROM c0_knowledge_receipts
                WHERE space_id=:space AND actor_id=:actor AND key=:key'''),
                {'space':current.space_id,'actor':current.user_id,'key':receipt_key}).mappings().one_or_none()
            if receipt:
                if receipt['fingerprint']!=fingerprint: raise SourceConflict()
                return receipt['result']
            if run['state']!='failed' or run['revision']!=expected_revision: raise SourceConflict()
            if self._live(c,run,now) is False: raise SourceConflict()
            changed=c.execute(text("""UPDATE c0_extraction_units SET state='queued',attempts=0,
                lease_token=NULL,lease_deadline=NULL,available_at=clock_timestamp(),error_code=NULL,
                started_at=NULL,finished_at=NULL WHERE run_id=:id AND state='failed' RETURNING id"""),
                {'id':identifier}).scalars().all()
            if not changed: raise SourceConflict()
            row=c.execute(text("""UPDATE c0_extraction_runs SET state='extracting',error_code=NULL,
                revision=revision+1 WHERE id=:id RETURNING revision"""),{'id':identifier}).scalar_one()
            result={'id':str(identifier),'revision':row,'retried_units':len(changed)}
            c.execute(text('''INSERT INTO c0_knowledge_receipts(space_id,actor_id,key,fingerprint,result)
                VALUES(:space,:actor,:key,:fingerprint,CAST(:result AS jsonb))'''),
                {'space':current.space_id,'actor':current.user_id,'key':receipt_key,
                 'fingerprint':fingerprint,'result':json.dumps(result)})
            return result

    def publish(self,run_id):
        """Assemble without a connection, then atomically publish a fenced snapshot."""
        if not self.enabled: return False
        identifier=UUID(str(run_id))
        with self.database.engine.connect() as c:
            run=c.execute(text('SELECT * FROM c0_extraction_runs WHERE id=:id'),{'id':identifier}).mappings().one_or_none()
            if run is None: return False
            if run['state']=='ready': return True
            if run['state']!='assembling': return False
            units=[dict(row) for row in c.execute(text('SELECT * FROM c0_extraction_units WHERE run_id=:id ORDER BY ordinal LIMIT 201'),
                {'id':identifier}).mappings()]
            source=c.execute(text('SELECT * FROM c0_source_versions WHERE id=:id'),{'id':run['version_id']}).mappings().one_or_none()
            if source is None: return False
            run=dict(run); source=dict(source)
        error=None
        try:
            self.originals.check(source)
            kind=run['profile']['partitioner']
            if kind=='pdf-page-v1': evidence=assemble_pdf(units,run['expected_units'])
            elif kind in FORMATS: evidence=assemble_document(units,source['media_type'],run['profile']['spec'])
            else:
                if len(units)!=1 or units[0]['state']!='succeeded': raise ExtractionError('parser_failed')
                unit=units[0]; evidence=Extracted(unit['body'],unit['locations'])
                if _result(evidence)!=unit['result_sha256'] or evidence.text_hash!=unit['text_sha256']:
                    raise ExtractionError('parser_failed')
            chunking=run['profile'].get('chunking','fixed-v1')
            try: structure=build_structure(evidence,source['media_type'],self.originals.check(source))
            except ExtractionError as failure:
                # Optional metadata bounds cannot reject an otherwise valid body.
                if failure.code!='too_large': raise
                structure=None; chunking='fixed-v1'
            metadata=[]
            for unit in units:
                if unit['provenance'] is not None:
                    validate_provenance(unit['provenance'],run['profile']['ocr'],unit['ordinal'])
                    if _hash(unit['provenance'])!=unit['provenance_sha256']: raise ExtractionError('parser_failed')
                    metadata.append(unit['provenance'])
                elif unit['provenance_sha256'] is not None: raise ExtractionError('parser_failed')
            if metadata:
                if structure is None: raise ExtractionError('parser_failed')
                structure['ocr']={'profile':run['profile']['ocr'],'pages':metadata}
            segments=section_chunks(evidence,structure,profile=chunking)
            self.originals.check(source)
        except ExtractionError as failure: error=failure.code
        except (ValueError,TypeError,KeyError,IndexError): error='parser_failed'
        from .sources import _publish_extracted, register_source_handlers
        from .jobs import default_registry, JobService
        registry=default_registry(); register_source_handlers(registry,self.database,self.originals)
        with self.database.engine.begin() as c:
            content_lock(c); hold_authority(c)
            current=c.execute(text('SELECT * FROM c0_extraction_runs WHERE id=:id FOR UPDATE'),{'id':identifier}).mappings().one_or_none()
            if current is None: return False
            if current['state']=='ready': return True
            if current['state']!='assembling' or self._live(c,current,c.execute(text('SELECT clock_timestamp()')).scalar_one()) is False:
                return False
            if current['revision']!=run['revision'] or current['manifest_sha256']!=run['manifest_sha256']: return False
            stored=c.execute(text('''SELECT id,ordinal,locator,input_sha256,state,result_sha256,text_sha256,provenance,provenance_sha256
                FROM c0_extraction_units WHERE run_id=:id ORDER BY ordinal FOR UPDATE'''),{'id':identifier}).mappings().all()
            keys=('id','ordinal','locator','input_sha256','state','result_sha256','text_sha256','provenance','provenance_sha256')
            same=(len(stored)==len(units) and all(all(a[key]==b[key] for key in keys) for a,b in zip(stored,units)))
            if not same: return False
            manifest_ok=all(_hash(row['locator'])==_hash(_locator(current['profile'],row['ordinal']))
                and row['input_sha256']==_fingerprint(current['manifest_sha256'],current['profile'],row['ordinal'],row['locator'])
                for row in stored)
            if error is not None or not manifest_ok:
                c.execute(text("UPDATE c0_extraction_runs SET state='failed',error_code=:code,revision=revision+1 WHERE id=:id"),
                    {'id':identifier,'code':error or 'manifest_mismatch'})
                return False
            version=c.execute(text('SELECT * FROM c0_source_versions WHERE id=:id FOR UPDATE'),{'id':current['version_id']}).mappings().one()
            _publish_extracted(c,version,evidence,segments,JobService(self.database,registry),reuse_identical=False,structure=structure,chunking_profile=chunking)
            c.execute(text("""UPDATE c0_extraction_units SET state='published',body=NULL,locations=NULL,provenance=NULL,
                lease_deadline=NULL WHERE run_id=:id"""),{'id':identifier})
            c.execute(text("""UPDATE c0_extraction_runs SET state='ready',error_code=NULL,
                result_bytes=0,result_characters=0,revision=revision+1 WHERE id=:id"""),{'id':identifier})
            return True

    def publish_pending(self):
        with self.database.engine.connect() as c:
            identifiers=c.execute(text("""SELECT id FROM c0_extraction_runs WHERE state='assembling'
                ORDER BY created_at,id LIMIT 20""")).scalars().all()
        for identifier in identifiers: self.publish(identifier)

    def cleanup(self, *, limit=20):
        with self.database.engine.begin() as c:
            return cleanup_extractions(c,limit=limit)

    def metrics(self):
        """Trusted worker aggregates; never an unauthorised reader status route."""
        with self.database.engine.connect() as c:
            row=c.execute(text("""SELECT count(*) FILTER(WHERE u.state IN ('queued','retry_wait')) AS queue_depth,
                count(*) FILTER(WHERE u.state='leased' AND u.lease_deadline>clock_timestamp()) AS active_units,
                count(*) FILTER(WHERE (u.state IN ('queued','retry_wait') AND u.available_at<=clock_timestamp())
                    OR (u.state='leased' AND u.lease_deadline<=clock_timestamp())) AS due_units
                FROM c0_extraction_units u JOIN c0_extraction_runs r ON r.id=u.run_id
                WHERE r.state='extracting' AND r.expires_at>clock_timestamp()""")).mappings().one()
            return dict(row)


class ExtractionWorker:
    """Bounded one-shot runner. Claim, parse and result commit are separate phases."""
    def __init__(self, queue):
        self.queue = queue

    def tick(self, *, max_units=20, budget_seconds=90,stop=None):
        if type(max_units) is not int or not 1<=max_units<=20 or type(budget_seconds) is not int or not 1<=budget_seconds<=90:
            raise ValueError('invalid_worker_limit')
        if not self.queue.enabled:
            return 0
        self.queue.cleanup()
        started = time.monotonic(); processed = 0; idle=0
        while processed<max_units and time.monotonic()-started<budget_seconds and not (stop is not None and stop.is_set()):
            claim = self.queue.claim()
            if claim is None:
                idle+=1
                if idle<20 and self.queue.metrics()['due_units'] and not self.queue.metrics()['active_units']: continue
                break
            idle=0
            try:
                path = self.queue.originals.check(claim.original)
                reused=self.queue.cached(claim)
                if reused is not None:
                    self.queue.originals.check(claim.original)
                    if self.queue.complete(claim,reused.evidence,provenance=reused.provenance,reused=reused):
                        processed+=1
                        continue
                provenance=None
                if claim.locator['kind']=='page':
                    try: result=extract_page_isolated(path,claim.ordinal)
                    except ExtractionError as error:
                        if error.code!='unsupported_scan' or 'ocr' not in claim.profile: raise
                        if self.queue.ocr_profile is None: raise
                        if self.queue.ocr_profile!=claim.profile['ocr']: raise ExtractionError('ocr_unavailable')
                        parsed=ocr_extract(path,claim.ordinal,claim.profile['ocr'])
                        result,provenance=parsed.evidence,parsed.provenance
                elif claim.locator['kind'] in ('blocks','characters'):
                    result=extract_unit_isolated(path,claim.original['media_type'],claim.locator)
                else: result=extract_isolated(path,claim.original['media_type'])
                self.queue.originals.check(claim.original)
                self.queue.complete(claim,result,provenance=provenance)
            except ExtractionError as error:
                self.queue.fail(claim,error.code)
            processed += 1
        self.queue.publish_pending()
        return processed


class ExtractionPool:
    """Bounded threads coordinate independent isolated parser processes."""
    def __init__(self,queue,*,workers=2):
        if type(workers) is not int or not 1<=workers<=4: raise ValueError('invalid_worker_limit')
        if workers>queue.instance_workers: raise ValueError('invalid_worker_limit')
        self.queue,self.workers=queue,workers

    def tick(self,*,max_units=20,budget_seconds=90,stop=None):
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from threading import Event
        import resource
        if not self.queue.enabled: return {'processed':0,'workers':0}
        stop=stop if stop is not None else Event()
        started=time.monotonic()
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures=[pool.submit(ExtractionWorker(self.queue).tick,max_units=max_units,
                budget_seconds=budget_seconds,stop=stop) for _ in range(self.workers)]
            processed=sum(future.result() for future in futures)
        def measurement(name):
            try:
                value=(Path('/sys/fs/cgroup')/name).read_text().strip()
                if value.isdecimal() and len(value)<=20: return int(value)
            except OSError: pass
            return None
        return {'processed':processed,'workers':self.workers,'seconds':round(time.monotonic()-started,6),
            'cgroup_peak_bytes':measurement('memory.peak'),'cgroup_limit_bytes':measurement('memory.max'),
            'cgroup_swap_limit_bytes':measurement('memory.swap.max'),'cgroup_pids_limit':measurement('pids.max'),
            'parser_peak_rss_bytes':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
            **self.queue.metrics()}
