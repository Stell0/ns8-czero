# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Reuse only output still owned by current content or unexpired private work."""
from dataclasses import dataclass,field
import json
from uuid import UUID
from sqlalchemy import text

from .extraction import Extracted,ExtractionError
from .local_ocr import validate_provenance


@dataclass(frozen=True)
class ReusedUnit:
    owner_id: UUID
    result_sha256: str
    provenance_sha256: str | None
    evidence: Extracted = field(repr=False)
    provenance: dict | None = field(repr=False)


def owners(connection,claim,*,owner_id=None):
    return connection.execute(text('''SELECT u.*,r.state AS run_state,r.version_id,r.actor_id,
        r.processing_generation,r.original_sha256,r.manifest_sha256,r.profile,r.expected_units,
        r.expires_at,r.id AS owner_run_id,d.id AS document_id,v.size_bytes,v.media_type
        FROM c0_extraction_units u JOIN c0_extraction_runs r ON r.id=u.run_id
        JOIN c0_source_versions v ON v.id=r.version_id AND v.space_id=r.space_id
        JOIN c0_sources s ON s.id=v.source_id AND s.space_id=v.space_id
        LEFT JOIN c0_documents d ON d.version_id=v.id AND d.space_id=v.space_id
        WHERE r.space_id=:space AND r.original_sha256=:original AND r.profile=CAST(:profile AS jsonb)
        AND v.content_hash=r.original_sha256 AND v.generation=r.processing_generation
        AND v.media_type=:media AND NOT s.deleted AND r.id<>:run
        AND u.ordinal=:ordinal AND u.locator=CAST(:locator AS jsonb)
        AND (CAST(:owner AS uuid) IS NULL OR u.id=CAST(:owner AS uuid))
        AND ((u.state='succeeded' AND v.state='queued' AND r.state IN ('extracting','assembling','failed')
                AND r.expires_at>clock_timestamp())
            OR (u.state='published' AND r.state='ready' AND v.state='ready' AND s.current_version_id=v.id AND d.id IS NOT NULL))
        ORDER BY (u.state='published') DESC,r.created_at,u.id LIMIT 4'''),
        {'space':claim.space_id,'original':claim.original['content_hash'],'media':claim.original['media_type'],
         'profile':json.dumps(claim.profile),'locator':json.dumps(claim.locator),
         'run':claim.run_id,'ordinal':claim.ordinal,'owner':owner_id}).mappings().all()


def live(queue,connection,row,now):
    if row['state']=='published': return True
    # Reuse the same authority/manifest fencing as an ordinary attempt.
    run={**dict(row),'id':row['owner_run_id'],'state':row['run_state']}
    return queue._live(connection,run,now) is not False


def output(connection,row):
    if row['state']=='succeeded':
        return Extracted(row['body'],row['locations']),row['provenance']
    document=connection.execute(text('SELECT body,locations,structure FROM c0_documents WHERE id=:id AND space_id=:space'),
        {'id':row['document_id'],'space':row['space_id']}).mappings().one_or_none()
    if document is None: raise ExtractionError('parser_failed')
    body=document['body']; locator=row['locator']; kind=locator['kind']
    if kind=='document': evidence=Extracted(body,document['locations'])
    elif kind=='characters':
        value=body[locator['start']:locator['end']]
        evidence=Extracted(value,[{'kind':'body','index':1,'start':0,'end':len(value)}])
    else:
        selected=[loc for loc in document['locations'] if
            (kind=='page' and loc['kind']=='page' and loc['index']==row['ordinal']) or
            (kind=='blocks' and locator['first']<=loc['index']<=locator['last'])]
        first=selected[0]['start'] if selected else 0; last=selected[-1]['end'] if selected else 0
        evidence=Extracted(body[first:last],[{**loc,'start':loc['start']-first,'end':loc['end']-first} for loc in selected])
    metadata=None
    if row['provenance_sha256'] is not None:
        choices=(document['structure'] or {}).get('ocr',{}).get('pages',[])
        matching=[item for item in choices if item.get('page')==row['ordinal']]
        if len(matching)!=1: raise ExtractionError('parser_failed')
        metadata=validate_provenance(matching[0],row['profile']['ocr'],row['ordinal'])
    return evidence,metadata
