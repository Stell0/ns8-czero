# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only predecessor preflight and transactional latest-only conversion."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID

from sqlalchemy import text

from .documents import DocumentService, SNAPSHOT

LEGACY_PART='c0_project_source_sync_history_v1'
LEGACY_SNAPSHOT='c0_project_source_snapshot_history_v1'


def preflight(connection):
    """Never choose an incomplete or corrupt parent by version-number ordering."""
    current={};members=set();part_sources=set();diagnostics=[];parents=0;owners={};published=set()
    latest=connection.execute(text("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='c0_sources' AND column_name='current_version_id')")).scalar_one()
    from .current_content import PART
    for parent in connection.execute(text('SELECT * FROM c0_objects WHERE type_name=:type ORDER BY space_id,id'),{'type':SNAPSHOT}).mappings():
        parents+=1
        try:
            reader=DocumentService(None,None).in_space(parent['space_id'])
            document=reader._composite(connection,parent,parent,parent['id'],receipt_kind=PART if latest else LEGACY_PART)
            if document['state']!='ready':raise ValueError('incomplete_current_parent')
            for part in document['parts']:
                source=part['source_id'];version=part['version_id']
                if source in owners:raise ValueError('ambiguous_parent_membership')
                owners[source]=parent['id'];current[source]=version;part_sources.add(source)
            members.update(UUID(value) for value in parent['data']['part_receipt_ids'])
        except (ValueError,TypeError,KeyError) as error:
            diagnostics.append({'document_id':str(parent['id']),'reason':'current_parent_cannot_be_verified_repair_before_upgrade',
                'diagnostic':'ambiguous_parent_membership' if str(error)=='ambiguous_parent_membership' else 'incomplete_or_corrupt_membership',
                'next_step':'repair current bodies/membership and give repeated part sources distinct identities before retrying'})
    if not latest:
        # A shrunken parent's retired last part is a past publication, never a
        # pending replacement merely because its extraction state remains ready.
        for history in connection.execute(text('SELECT data FROM c0_objects WHERE type_name=:type'),{'type':LEGACY_SNAPSHOT}).mappings():
            values=history['data'].get('part_receipt_ids',[])
            if not isinstance(values,list):continue
            try:ids=[UUID(value) for value in values]
            except (ValueError,TypeError,AttributeError):continue
            for part in connection.execute(text('SELECT data FROM c0_objects WHERE type_name=:type AND id=ANY(CAST(:ids AS uuid[]))'),{'type':LEGACY_PART,'ids':ids}).mappings():
                try:published.add(UUID(part['data']['version_id']))
                except (ValueError,TypeError,KeyError):continue
    # Includes incomplete first imports and legacy sources lacking metadata hints.
    for row in connection.execute(text('SELECT data FROM c0_objects WHERE type_name IN (:current,:history)'),
            {'current':'c0_project_source_sync_v1','history':LEGACY_PART}).mappings():
        try:part_sources.add(UUID(row['data']['source_id']))
        except (ValueError,KeyError,TypeError):
            diagnostics.append({'reason':'invalid_importer_source_identity'})
    counts={'sources':0,'current_documents':0,'current_multipart_parents':parents,'archived_sources':0,'pending_sources':0}
    keep=set(current.values())
    for source in connection.execute(text('SELECT * FROM c0_sources ORDER BY id')).mappings():
        counts['sources']+=1;counts['archived_sources']+=int(source['deleted'])
        versions=connection.execute(text('SELECT v.*,d.body,d.text_hash FROM c0_source_versions v LEFT JOIN c0_documents d ON d.version_id=v.id WHERE v.source_id=:id ORDER BY v.number DESC'),{'id':source['id']}).mappings().all()
        selected=current.get(source['id']) or (source.get('current_version_id') if latest else None)
        if selected:current[source['id']]=selected;keep.add(selected)
        is_part=source['id'] in part_sources or bool(source['metadata'].get('parent_external_id'))
        if not selected and not is_part and not latest:
            ready=next((v for v in versions if v['state']=='ready'),None)
            if ready:
                if ready['body'] is None or hashlib.sha256(ready['body'].encode()).hexdigest()!=ready['text_hash']:
                    diagnostics.append({'source_id':str(source['id']),'reason':'current_source_body_missing_or_corrupt'})
                else:selected=ready['id'];current[source['id']]=selected;keep.add(selected)
        if selected:
            retained=next((v for v in versions if v['id']==selected),None)
            if not retained or retained['state']!='ready' or retained['body'] is None or hashlib.sha256(retained['body'].encode()).hexdigest()!=retained['text_hash']:
                diagnostics.append({'source_id':str(source['id']),'reason':'current_source_body_missing_or_corrupt'})
            counts['current_documents']+=1
        # One bounded pending replacement is allowed. Its authority never comes
        # from a failed/queued version displacing the last complete publication.
        pending=next((v for v in versions if v['id']!=selected and v['id'] not in published and (is_part or v['state']!='ready')
            and (selected is None or v['number']>next(x['number'] for x in versions if x['id']==selected))),None)
        if pending:keep.add(pending['id']);counts['pending_sources']+=1
    ids=list(keep)
    estimate=connection.execute(text('''SELECT count(*) AS versions,COALESCE(sum(size_bytes),0) AS original_bytes,
        count(*) FILTER(WHERE original_present) AS originals FROM c0_source_versions
        WHERE NOT(id=ANY(CAST(:keep AS uuid[])))'''),{'keep':ids}).mappings().one()
    affected=connection.execute(text('''SELECT count(*) FROM c0_evidence_links e JOIN c0_chunks c ON c.id=e.chunk_id
        JOIN c0_documents d ON d.id=c.document_id WHERE NOT(d.version_id=ANY(CAST(:keep AS uuid[])))'''),{'keep':ids}).scalar_one()
    wiki=connection.execute(text('SELECT count(*) FROM c0_wiki_revisions r JOIN c0_wiki_pages p ON p.id=r.page_id WHERE r.number<>p.revision')).scalar_one()
    for row in connection.execute(text('SELECT p.id FROM c0_wiki_pages p WHERE NOT EXISTS(SELECT 1 FROM c0_wiki_revisions r WHERE r.page_id=p.id AND r.number=p.revision)')).mappings():
        diagnostics.append({'page_id':str(row['id']),'reason':'current_wiki_body_missing'})
    for row in connection.execute(text('SELECT p.id,r.body,r.content_hash FROM c0_wiki_pages p JOIN c0_wiki_revisions r ON r.page_id=p.id AND r.number=p.revision')).mappings():
        if hashlib.sha256(row['body'].encode()).hexdigest()!=row['content_hash']:
            diagnostics.append({'page_id':str(row['id']),'reason':'current_wiki_body_corrupt'})
    derivative=connection.execute(text('''SELECT count(DISTINCT d.id) AS documents,count(c.id) AS chunks,
        COALESCE(sum(octet_length(c.body)),0) AS chunk_bytes FROM c0_documents d LEFT JOIN c0_chunks c ON c.document_id=d.id
        WHERE NOT(d.version_id=ANY(CAST(:keep AS uuid[])))'''),{'keep':ids}).mappings().one()
    # Managed connector schema compatibility must be visible in read-only preflight.
    from copy import deepcopy
    from .project_schema import SCHEMAS
    for type_name,kind in ((LEGACY_PART,'source_part_v1'),(LEGACY_SNAPSHOT,'source_snapshot_v1'),(PART,'source_part_v1')):
        row=connection.execute(text('SELECT schema,unique_fields FROM c0_object_types WHERE name=:name'),{'name':type_name}).mappings().one_or_none()
        if row and (row['schema']!=SCHEMAS[kind] or row['unique_fields']!=['key']):
            diagnostics.append({'type_name':type_name,'reason':'customized_source_membership_schema_requires_review'})
    for kind in ('connector_v1','connector_config_v1'):
        schema=connection.execute(text('SELECT schema FROM c0_object_types WHERE name=:name'),{'name':'c0_project_'+kind}).scalar_one_or_none()
        if schema is None:continue
        old=deepcopy(SCHEMAS[kind]);old['properties']['definition']['properties'].pop('website')
        old['properties']['definition']['properties']['adapter']['enum'].remove('website')
        if schema not in (old,SCHEMAS[kind]):diagnostics.append({'type_name':'c0_project_'+kind,'reason':'customized_connector_schema_requires_review'})
    report={**counts,'superseded_extracted_documents':derivative['documents'],'superseded_chunks':derivative['chunks'],
        'chunk_bytes_to_remove':derivative['chunk_bytes'],'superseded_source_versions':estimate['versions'],'original_files_to_remove':estimate['originals'],
        'original_bytes_upper_bound':estimate['original_bytes'],'affected_evidence_links':affected,
        'superseded_wiki_bodies':wiki,'blocked':bool(diagnostics),'diagnostics':diagnostics[:100]}
    return report,{'current':current,'keep':keep,'members':members}


def convert(connection,plan):
    from .current_content import PART, retire_versions, retire_wiki, thin_receipt
    # Preserve exact verified memberships before removing reconstructable history.
    connection.execute(text('''INSERT INTO c0_object_types(name,label,schema,unique_fields)
        SELECT :part,'Current source parts',schema,unique_fields FROM c0_object_types WHERE name=:old
        ON CONFLICT(name) DO NOTHING'''),{'part':PART,'old':LEGACY_PART})
    if plan['members']:
        connection.execute(text('UPDATE c0_objects SET type_name=:part WHERE id=ANY(CAST(:ids AS uuid[]))'),{'part':PART,'ids':list(plan['members'])})
        connection.execute(text('UPDATE c0_object_keys SET type_name=:part WHERE object_id=ANY(CAST(:ids AS uuid[]))'),{'part':PART,'ids':list(plan['members'])})
    # Object keys/relations are CASCADE-owned. Project events are payload-free.
    connection.execute(text('DELETE FROM c0_objects WHERE type_name IN (:parts,:snapshots)'),{'parts':LEGACY_PART,'snapshots':LEGACY_SNAPSHOT})
    connection.execute(text('DELETE FROM c0_object_types WHERE name IN (:parts,:snapshots)'),{'parts':LEGACY_PART,'snapshots':LEGACY_SNAPSHOT})
    for source,version in plan['current'].items():
        connection.execute(text('UPDATE c0_sources SET current_version_id=:version WHERE id=:id'),{'id':source,'version':version})
    connection.execute(text('''UPDATE c0_sources s SET next_version_number=COALESCE(
        (SELECT max(number)+1 FROM c0_source_versions v WHERE v.source_id=s.id),1)'''))
    ids=connection.execute(text('SELECT id FROM c0_source_versions WHERE NOT(id=ANY(CAST(:keep AS uuid[])))'),{'keep':list(plan['keep'])}).scalars().all()
    retire_versions(connection,ids)
    for page in connection.execute(text('SELECT id,revision FROM c0_wiki_pages')).mappings():retire_wiki(connection,page['id'],page['revision'])
    for receipt in connection.execute(text('SELECT space_id,actor_id,key,result FROM c0_knowledge_receipts')).mappings():
        reduced=thin_receipt(receipt['result'])
        if reduced!=receipt['result']:
            connection.execute(text('UPDATE c0_knowledge_receipts SET result=CAST(:result AS jsonb) WHERE space_id=:space AND actor_id=:actor AND key=:key'),
                {'result':json.dumps(reduced),'space':receipt['space_id'],'actor':receipt['actor_id'],'key':receipt['key']})
    # Annotation revisions can contain quoted content. Keep only their current
    # authored value; retired anchors explicitly report target_current=false.
    connection.execute(text('DELETE FROM c0_annotation_revisions r USING c0_annotations a WHERE a.id=r.annotation_id AND r.number<>a.revision'))
    # The connector schema extension is an explicit managed-type migration.
    # Refuse unknown customized schemas rather than silently overwriting them.
    from copy import deepcopy
    from .project_schema import SCHEMAS
    for kind in ('connector_v1','connector_config_v1'):
        row=connection.execute(text('SELECT schema FROM c0_object_types WHERE name=:name'),{'name':'c0_project_'+kind}).mappings().one_or_none()
        if not row:continue
        old=deepcopy(SCHEMAS[kind]);definition=old['properties']['definition']
        definition['properties'].pop('website')
        definition['properties']['adapter']['enum'].remove('website')
        if row['schema'] not in (old,SCHEMAS[kind]):raise RuntimeError('customized_project_connector_schema_requires_review')
        connection.execute(text('UPDATE c0_object_types SET schema=CAST(:schema AS jsonb) WHERE name=:name'),{'name':'c0_project_'+kind,'schema':json.dumps(SCHEMAS[kind])})


def preflight_originals(connection,root,*,current_ids=None,max_files=100000,max_bytes=1073741824):
    """Audit the explicit managed store without modifying files or guessing ownership."""
    root=Path(root);diagnostics=[];files=0;hashed=0;orphans=0
    if root.is_symlink():return {'blocked':True,'diagnostics':[{'reason':'original_store_is_symlink'}]}
    rows={row['id']:row for row in connection.execute(text('SELECT id,retain_original,original_present,size_bytes,content_hash FROM c0_source_versions')).mappings()}
    has_cleanup=connection.execute(text("SELECT to_regclass('c0_original_cleanup') IS NOT NULL")).scalar_one()
    cleanup=set(connection.execute(text('SELECT version_id FROM c0_original_cleanup')).scalars()) if has_cleanup else set()
    found=set()
    if root.exists():
        with os.scandir(root) as entries:
            for entry in entries:
                files+=1
                if files>max_files:
                    diagnostics.append({'reason':'original_file_audit_limit_partial'});break
                if not re.fullmatch(r'\.?[0-9a-f]{32}',entry.name):continue # operator files/backups are never deleted
                identifier=UUID(entry.name.lstrip('.'));info=entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    diagnostics.append({'file_id':str(identifier),'reason':'unsafe_generated_original_entry'});continue
                row=rows.get(identifier)
                if row is None and identifier not in cleanup:
                    orphans+=1
                    diagnostics.append({'file_id':str(identifier),'reason':'unidentified_generated_file_reconcile_outside_managed_store'})
                if row and not entry.name.startswith('.'):
                    found.add(identifier)
                    if row['retain_original'] and row['original_present'] and (current_ids is None or identifier in current_ids):
                        if hashed+info.st_size>max_bytes:
                            diagnostics.append({'reason':'original_hash_audit_limit_partial'});break
                        hashed+=info.st_size
                        with open(entry.path,'rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                        if info.st_size!=row['size_bytes'] or digest!=row['content_hash']:
                            diagnostics.append({'file_id':str(identifier),'reason':'retained_original_corrupt'})
    for identifier,row in rows.items():
        if row['retain_original'] and row['original_present'] and (current_ids is None or identifier in current_ids) and identifier not in found:
            diagnostics.append({'file_id':str(identifier),'reason':'retained_original_missing_or_audit_incomplete'})
    return {'original_entries_examined':files,'original_bytes_hashed':hashed,'unidentified_generated_files':orphans,
        'blocked':bool(diagnostics),'diagnostics':diagnostics[:100]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',required=True)
    parser.add_argument('--originals',type=Path,required=True,help='Explicit managed source-originals directory, never an operator backup')
    args=parser.parse_args(argv)
    from .database import Database
    database=Database()
    try:
        with database.engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            connection.execute(text('SET TRANSACTION READ ONLY'))
            report,plan=preflight(connection)
            report['filesystem']=preflight_originals(connection,args.originals,current_ids=set(plan['current'].values()))
            report['blocked']|=report['filesystem']['blocked']
        print(json.dumps(report,sort_keys=True));return 1 if report['blocked'] else 0
    finally:database.close()


if __name__=='__main__':raise SystemExit(main())
