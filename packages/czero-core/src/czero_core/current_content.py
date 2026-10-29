# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Current publication ownership, payload-free evidence tombstones and retirement."""
from uuid import UUID
from sqlalchemy import text

PART = 'c0_project_source_part_v1'
SNAPSHOT = 'c0_project_source_snapshot_v1'
CONTENT_LOCK = 49384


class ContentSuperseded(ValueError):
    def __init__(self):
        super().__init__('content_superseded')


def content_lock(connection):
    connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': CONTENT_LOCK})


def tombstone(connection, *, space, kind, identifier, resource, generation, digest):
    connection.execute(text('''INSERT INTO c0_content_tombstones
        (space_id,kind,id,resource_id,generation,content_hash)
        VALUES (:space,:kind,:id,:resource,:generation,:hash) ON CONFLICT DO NOTHING'''),
        {'space':space,'kind':kind,'id':identifier,'resource':resource,'generation':generation,'hash':digest})


def check_retired(connection, space, kind, identifier):
    # Call only after current selected-space authorization. No global ID probe.
    if connection.execute(text('SELECT 1 FROM c0_content_tombstones WHERE space_id=:space AND kind=:kind AND id=:id'),
            {'space':space,'kind':kind,'id':identifier}).scalar_one_or_none():
        raise ContentSuperseded()


def _invalidate(connection, kind, ids):
    if not ids:return
    connection.execute(text('''UPDATE c0_annotations a SET evidence_stale=true FROM c0_annotation_targets t
        WHERE a.anchor_id=t.id AND a.space_id=t.space_id AND t.kind=:kind AND t.target_id=ANY(CAST(:ids AS uuid[]))'''),{'kind':kind,'ids':ids})


def retire_versions(connection, ids):
    """Retire only versions no longer owned by any current publication."""
    if not ids:return
    values={'ids':list(ids),'part':PART}
    rows=connection.execute(text('''SELECT v.* FROM c0_source_versions v
        WHERE v.id=ANY(CAST(:ids AS uuid[]))
        AND NOT EXISTS(SELECT 1 FROM c0_sources s WHERE s.current_version_id=v.id)
        AND NOT EXISTS(SELECT 1 FROM c0_objects p WHERE p.type_name=:part AND p.space_id=v.space_id AND p.data->>'version_id'=v.id::text)
        FOR UPDATE'''),values).mappings().all()
    for row in rows:
        identifier=row['id'];space=row['space_id'];parameters={'id':identifier,'space':space}
        tombstone(connection,space=space,kind='source_version',identifier=identifier,
            resource=row['source_id'],generation=row['number'],digest=row['content_hash'])
        connection.execute(text('''INSERT INTO c0_content_tombstones(space_id,kind,id,resource_id,generation,content_hash)
            SELECT c.space_id,'chunk',c.id,:source,:number,c.content_hash FROM c0_chunks c
            JOIN c0_documents d ON d.id=c.document_id WHERE d.version_id=:id ON CONFLICT DO NOTHING'''),
            {**parameters,'source':row['source_id'],'number':row['number']})
        connection.execute(text('''INSERT INTO c0_content_tombstones(space_id,kind,id,resource_id,generation,content_hash)
            SELECT space_id,'document',id,:source,:number,text_hash FROM c0_documents WHERE version_id=:id ON CONFLICT DO NOTHING'''),
            {**parameters,'source':row['source_id'],'number':row['number']})
        # Evidence links retain exact IDs but have no FK into removed content.
        connection.execute(text('''UPDATE c0_evidence_links SET unavailable=true WHERE chunk_id IN (
            SELECT c.id FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id WHERE d.version_id=:id)'''),parameters)
        connection.execute(text('UPDATE c0_claims SET evidence_stale=true WHERE id IN (SELECT claim_id FROM c0_evidence_links WHERE unavailable)'))
        connection.execute(text('''UPDATE c0_annotations a SET evidence_stale=true FROM c0_annotation_revisions r
            WHERE r.annotation_id=a.id AND r.number=a.revision AND EXISTS (
                SELECT 1 FROM jsonb_array_elements(COALESCE(r.value->'source_references','[]'::jsonb)) ref
                JOIN c0_chunks c ON c.id::text=ref->>'id' JOIN c0_documents d ON d.id=c.document_id WHERE d.version_id=:id)'''),parameters)
        connection.execute(text('''UPDATE c0_entity_links SET chunk_id=NULL,document_id=NULL WHERE
            chunk_id IN (SELECT c.id FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id WHERE d.version_id=:id)
            OR document_id IN (SELECT id FROM c0_documents WHERE version_id=:id)'''),parameters)
        _invalidate(connection,'source_version',[identifier])
        connection.execute(text('DELETE FROM c0_chunks WHERE document_id IN (SELECT id FROM c0_documents WHERE version_id=:id)'),parameters)
        connection.execute(text('DELETE FROM c0_documents WHERE version_id=:id'),parameters)
        # Intent survives the version DELETE and COMMIT. The worker unlinks only
        # these UUID paths after checking that no current/staged version owns it.
        connection.execute(text('INSERT INTO c0_original_cleanup(version_id,space_id) VALUES (:id,:space) ON CONFLICT DO NOTHING'),parameters)
        connection.execute(text('DELETE FROM c0_source_versions WHERE id=:id'),parameters)
    return len(rows)


def publish_versions(connection, ids):
    content_lock(connection)
    for identifier in ids:
        row=connection.execute(text("SELECT * FROM c0_source_versions WHERE id=:id AND state='ready' FOR UPDATE"),{'id':identifier}).mappings().one_or_none()
        if row is None:raise ValueError('publication_part_not_ready')
        source=connection.execute(text('SELECT * FROM c0_sources WHERE id=:id FOR UPDATE'),{'id':row['source_id']}).mappings().one()
        if source['current_version_id']==identifier:continue
        if source['current_version_id'] is not None:
            current_number=connection.execute(text('SELECT number FROM c0_source_versions WHERE id=:id'),{'id':source['current_version_id']}).scalar_one()
            if current_number>=row['number']:raise ContentSuperseded()
        connection.execute(text('''UPDATE c0_sources SET current_version_id=:version,
            title=COALESCE(:title,title),metadata=COALESCE(CAST(:metadata AS jsonb),metadata),updated_at=now() WHERE id=:id'''),
            {'version':identifier,'id':source['id'],'title':row['publication_title'],
             'metadata':__import__('json').dumps(row['publication_metadata']) if row['publication_metadata'] is not None else None})
        obsolete=connection.execute(text('SELECT id FROM c0_source_versions WHERE source_id=:source AND number<:number'),
            {'source':source['id'],'number':row['number']}).scalars().all()
        retire_versions(connection,obsolete)


def retire_wiki(connection, page_id, number):
    rows=connection.execute(text('SELECT * FROM c0_wiki_revisions WHERE page_id=:id AND number<>:number'),
        {'id':page_id,'number':number}).mappings().all()
    for row in rows:
        tombstone(connection,space=row['space_id'],kind='wiki_revision',identifier=row['id'],
            resource=page_id,generation=row['number'],digest=row['content_hash'])
    _invalidate(connection,'wiki_revision',[r['id'] for r in rows])
    connection.execute(text('DELETE FROM c0_wiki_revisions WHERE page_id=:id AND number<>:number'),{'id':page_id,'number':number})


def thin_receipt(value):
    """Wiki bodies/metadata are read afresh on replay, never copied to receipts."""
    if isinstance(value,list):return [thin_receipt(v) for v in value]
    if not isinstance(value,dict):return value
    if {'source_id','number','content_hash'}<=value.keys():
        return {key:thin_receipt(item) for key,item in value.items() if key not in ('publication_title','publication_metadata')}
    if isinstance(value.get('content'),dict) and 'body' in value['content'] and 'page_id' in value['content']:
        return {'$current_wiki':str(value['id']),'revision':value['revision']}
    if value.get('type_name') in (PART,SNAPSHOT,'c0_project_source_sync_v1'):
        return {'$current_source_record':str(value['id']),'revision':value['revision']}
    if {'predicate','entity_id','value','revision','id'}<=value.keys():
        return {'$current_claim':str(value['id']),'revision':value['revision']}
    if {'target','namespace','value','revision','id'}<=value.keys() and value['id']:
        return {'$current_annotation':str(value['id']),'revision':value['revision']}
    return {key:thin_receipt(item) for key,item in value.items()}


def replay_receipt(connection, space, value):
    if isinstance(value,list):return [replay_receipt(connection,space,v) for v in value]
    if not isinstance(value,dict):return value
    if '$current_wiki' in value:
        from .spaces import content_row
        from .receipts import snapshot
        page=connection.execute(text('SELECT * FROM c0_wiki_pages WHERE space_id=:space AND id=:id'),
            {'space':space,'id':UUID(value['$current_wiki'])}).mappings().one_or_none()
        if not page or page['revision']!=value['revision']:raise ContentSuperseded()
        revision=connection.execute(text('SELECT * FROM c0_wiki_revisions WHERE space_id=:space AND page_id=:id AND number=:number'),
            {'space':space,'id':page['id'],'number':page['revision']}).mappings().one()
        return snapshot({**content_row(page),'content':content_row(revision)})
    if '$current_annotation' in value or '$annotation_value' in value:
        from .annotations import AnnotationService,ContentTarget
        from .receipts import snapshot
        row=connection.execute(text('''SELECT a.revision,a.namespace,t.kind,t.target_id,t.content_revision
            FROM c0_annotations a JOIN c0_annotation_targets t ON t.id=a.anchor_id AND t.space_id=a.space_id
            WHERE a.space_id=:space AND a.id=:id'''),
            {'space':space,'id':UUID(value.get('$current_annotation',value.get('$annotation_value')))}).mappings().one_or_none()
        if not row or row['revision']!=value['revision']:raise ContentSuperseded()
        service=AnnotationService(None,None).in_space(space)
        return snapshot(service._entry(connection,ContentTarget(row['kind'],row['target_id'],row['content_revision']),row['namespace']))
    if '$current_source_record' in value:
        from .receipts import snapshot
        from .spaces import content_row
        row=connection.execute(text('SELECT * FROM c0_objects WHERE space_id=:space AND id=:id'),
            {'space':space,'id':UUID(value['$current_source_record'])}).mappings().one_or_none()
        if not row or row['revision']!=value['revision']:raise ContentSuperseded()
        return snapshot(content_row(row))
    if '$current_claim' in value:
        from .receipts import snapshot
        from .spaces import content_row
        row=connection.execute(text('SELECT * FROM c0_claims WHERE space_id=:space AND id=:id'),
            {'space':space,'id':UUID(value['$current_claim'])}).mappings().one_or_none()
        if not row or row['revision']!=value['revision']:raise ContentSuperseded()
        return snapshot(content_row(row))
    return {key:replay_receipt(connection,space,item) for key,item in value.items()}
