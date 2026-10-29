# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Whole evidence is read from immutable documents, never overlapping chunks."""
import hashlib
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.documents import DocumentService
from czero_core.current_content import ContentSuperseded
from czero_core.identity import PermissionDenied
from test_sources import sources, upload, execute
from test_access import access


def digest(body):
    return hashlib.sha256(body.encode()).hexdigest()


@pytest.mark.parametrize('body', ['# Firewall configuration\n\nComplete small document.\n', '# Large document\n\n' + 'Full retained paragraph.\n\n' * 8000], ids=['small','large'])
def test_single_full_document_ready_history_archive(sources, body):
    service, owner, _, _ = sources
    version = upload(sources, body.encode(), media_type='text/markdown')
    reader = DocumentService(service.database, service.access)
    queued = reader.read_document(owner, version['source_id'])
    assert queued['state']=='incomplete' and queued['body'] is None
    execute(sources, 'source.extract', version['id'])
    full = reader.read_document(owner, version['source_id'])
    assert full['body'] == body and full['text_hash'] == digest(body)
    assert str(full['revision_id']) == str(version['id']) and len(full['parts']) == 1
    repeated = upload(sources, body.encode(), media_type='text/markdown', source_id=version['source_id'], expected_revision=1)
    assert repeated['id'] == version['id']
    changed = upload(sources, b'# Changed\n\nShort replacement.\n', media_type='text/markdown', source_id=version['source_id'], expected_revision=1)
    # Pending extraction must not hide the last complete version.
    assert reader.read_document(owner, version['source_id'])['body'] == body
    execute(sources, 'source.extract', changed['id'])
    assert reader.read_document(owner, version['source_id'])['body'] == '# Changed\n\nShort replacement.\n'
    with pytest.raises(ContentSuperseded):reader.read_document(owner,version['source_id'],revision_id=version['id'])
    assert len(reader.document_history(owner,version['source_id']))==1
    service.delete(owner, version['source_id'], expected_revision=2)
    assert not reader.browse_documents(owner)
    with pytest.raises(ContentSuperseded):reader.read_document(owner,version['source_id'],revision_id=version['id'])
    with pytest.raises(PermissionDenied):
        reader.in_space(uuid4()).read_document(owner, version['source_id'])

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "samples/ingestion/src"))

from test_project_ingestion_http import setup
from test_ingestion_samples_http import sample_connection
from test_knowledge_http import knowledge_http
from test_spaces_http import space_http
from test_mcp_http import transport
from test_auth_http import application
from c0_projects.model import Item, sha
from c0_projects.publish import parts, sync_part, save_snapshot
from czero_core.sources import SourceConflict, SourceNotFound


def publish(client, definition, tmp_path, body):
    item = Item('documents', 'manual.md', 'Synthetic full manual', body.encode(), 'text/markdown',
        canonical_url='https://example.org/documentation/manual',
        provenance={'product':'Synthetic product','version':'8','path':['Administrator Manual','Configuration']})
    receipts = [sync_part(client, part, tmp_path/'journal.json', definition_hash=sha(definition), attempts=4, seconds=0)
        for part in parts(item, limit=131072)]
    return save_snapshot(client, item, receipts), receipts


@pytest.fixture
def logical(sample_connection, knowledge_http, tmp_path):
    config, _ = sample_connection
    client, definition = setup(config)
    app = knowledge_http[0]
    actor = app.state.auth.access.resolve(app.state.auth.oidc.verify_access_token(knowledge_http[1]))
    service = DocumentService(app.state.sources.database, app.state.auth.access).in_space(client.space_id)
    yield client, definition, service, actor, tmp_path
    client.close()


def test_multipart_exact_order_shrink_repeat_history_and_old_citation(logical):
    client, definition, service, actor, path = logical
    body = '# Beginning\n\n' + ''.join(f'Paragraph {i:05d}: unique original café evidence.\n\n' for i in range(7000)) + '\n## End\n\nEND-MARKER\n'
    first, receipts = publish(client, definition, path, body)
    assert len(receipts) >= 3
    full = service.read_document(actor, first['id'])
    assert full['state'] == 'ready' and full['body'] == body and full['text_hash'] == sha(body.encode())
    assert len(full['parts']) == len(receipts)
    assert [row['id'] for row in service.browse_documents(actor)] == [UUID(first['id'])]
    same, _ = publish(client, definition, path, body)
    assert same == first
    doc = client.call('documents_get', version_id=receipts[-1]['version_id'])
    chunk = client.call('document_chunks_list', document_id=doc['id'], limit=1)['chunks'][0]
    citation = client.call('citations_get', chunk_id=chunk['id'])
    resolved = service.containing_document(actor, receipts[-1]['version_id'])
    assert resolved['body'] == body and resolved['revision_id'] == full['revision_id']
    short = '# Shorter\n\nNo obsolete paragraphs.\n'
    second, _ = publish(client, definition, path, short)
    assert second['id'] == first['id']
    assert service.read_document(actor, first['id'])['body'] == short
    with pytest.raises(ContentSuperseded):service.read_document(actor,first['id'],revision_id=full['revision_id'])
    with pytest.raises(ContentSuperseded):service.containing_document(actor,receipts[-1]['version_id'])
    from c0_ingest.errors import C0Error
    with pytest.raises(C0Error):client.call('citations_get',chunk_id=chunk['id'])
    assert len(service.document_history(actor,first['id']))==1
    assert len(service.browse_documents(actor)) == 1


@pytest.mark.parametrize('fault', ['missing', 'queued', 'hash', 'order', 'parent', 'space', 'offset'])
def test_snapshot_fail_closed_without_partial_body(logical, fault):
    client, definition, service, actor, path = logical
    body = '# Complete\n\n' + 'Fabricated original paragraph.\n\n' * 9500
    saved, receipts = publish(client, definition, path, body)
    full = service.read_document(actor, saved['id'])
    with service.database.engine.begin() as connection:
        if fault == 'missing':
            # A dangling receipt must never return the remaining body as complete.
            connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{part_receipt_ids}', CAST(:ids AS jsonb)) WHERE id=CAST(:id AS uuid)"),
                {'ids':__import__('json').dumps([str(uuid4()), *saved['data']['part_receipt_ids'][1:]]), 'id':saved['id']})
        elif fault == 'queued':
            connection.execute(text("UPDATE c0_source_versions SET state='queued' WHERE id=CAST(:id AS uuid)"), {'id':receipts[1]['version_id']})
        elif fault == 'hash':
            connection.execute(text("UPDATE c0_documents SET body='Corrupt synthetic original' WHERE version_id=CAST(:id AS uuid)"), {'id':receipts[1]['version_id']})
        elif fault == 'offset':
            connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{start_byte}','999') WHERE id=CAST(:id AS uuid)"),{'id':saved['data']['part_receipt_ids'][1]})
        elif fault == 'order':
            connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{part_receipt_ids}', CAST(:ids AS jsonb)) WHERE id=CAST(:id AS uuid)"),
                {'ids':__import__('json').dumps(list(reversed(saved['data']['part_receipt_ids']))), 'id':saved['id']})
        else:
            receipt = saved['data']['part_receipt_ids'][1]
            if fault == 'parent':
                connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{parent_external_id}', '\"different.md\"') WHERE id=CAST(:id AS uuid)"), {'id':receipt})
            else:
                # A receipt from an unrelated space cannot be joined through UUID alone.
                connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{version_id}', to_jsonb(CAST(:version AS text))) WHERE id=CAST(:id AS uuid)"),
                    {'id':receipt,'version':str(uuid4())})
    if fault in ('missing', 'queued', 'space'):
        incomplete = service.read_document(actor, saved['id'])
        assert incomplete['state'] == 'incomplete' and incomplete['body'] is None
    elif fault == 'order':
        # Ordered receipt metadata, rather than the caller's array order, is authoritative.
        assert service.read_document(actor, saved['id'])['body'] == body
    else:
        with pytest.raises(SourceConflict):
            service.read_document(actor, saved['id'])


def test_uncommitted_new_parts_do_not_replace_last_complete_snapshot(logical):
    client, definition, service, actor, path = logical
    first, _ = publish(client, definition, path, '# Verified\n\nLast complete document.\n')
    changed = Item('documents', 'manual.md', 'Synthetic full manual', b'# Pending change\n\nNot yet a complete snapshot.\n', 'text/markdown')
    sync_part(client, next(parts(changed)), path/'pending.json', definition_hash=sha(definition), attempts=4, seconds=0)
    assert service.read_document(actor, first['id'])['body'] == '# Verified\n\nLast complete document.\n'


def test_updated_snapshot_can_reuse_unchanged_part_versions(logical):
    client, definition, service, actor, path = logical
    body = '# Retained opening\n\n' + 'An unchanged paragraph.\n\n' * 14000
    first, receipts = publish(client, definition, path, body)
    before = service.read_document(actor, first['id'])
    changed = body + '\nChanged final paragraph.\n'
    second, later = publish(client, definition, path, changed)
    assert receipts[0]['version_id'] == later[0]['version_id']
    assert service.read_document(actor, second['id'])['body'] == changed
    with pytest.raises(ContentSuperseded):service.read_document(actor,first['id'],revision_id=before['revision_id'])


def test_reader_editor_admin_and_existing_space_boundaries(sources):
    from czero_core.identity import Role
    from czero_core.spaces import SpaceService
    from test_access import identity, record_unadmitted, account_named
    source, owner, _, _ = sources
    version=upload(sources, b'# Shared evidence\n\nRead without Write.', media_type='text/markdown')
    execute(sources,'source.extract',version['id'])
    reader=DocumentService(source.database,source.access)
    key=uuid4();record_unadmitted(source.access,key,'whole-document-reader')
    account=account_named(source.access,owner,'whole-document-reader')
    spaces=SpaceService(source.database,source.access)
    other=spaces.create(owner,'Other document space',idempotency_key=uuid4().hex)
    try:
        for role in (Role.READER,Role.EDITOR,Role.ADMIN):
            source.access.set_role(owner,account['id'],role)
            actor=source.access.resolve(identity(source.access,key,'whole-document-reader'))
            assert reader.read_document(actor,version['source_id'])['body'].startswith('# Shared evidence')
            if role is not Role.ADMIN:
                with pytest.raises(PermissionDenied):reader.in_space(other['id']).read_document(actor,version['source_id'])
            else:
                with pytest.raises(SourceNotFound):reader.in_space(other['id']).read_document(actor,version['source_id'])
        source.access.set_role(owner,account['id'],None)
        with pytest.raises(PermissionDenied):reader.read_document(actor,version['source_id'])
    finally:
        with source.database.engine.begin() as connection:
            connection.execute(text('DELETE FROM c0_space_grants WHERE space_id=CAST(:id AS uuid)'),{'id':other['id']})
            connection.execute(text('DELETE FROM c0_spaces WHERE id=CAST(:id AS uuid)'),{'id':other['id']})


def test_part_identity_resolves_whole_parent_and_pending_parent_has_no_body(logical):
    client, definition, service, actor, path = logical
    body='# Whole parent\n\n'+'Retained original paragraph.\n\n'*10000
    snapshot,receipts=publish(client,definition,path,body)
    assert service.read_document(actor,receipts[-1]['source_id'])['body']==body
    pending=Item('documents','pending-parent.md','Pending parent',b'A ready part is not a verified whole parent.','text/markdown')
    part=sync_part(client,next(parts(pending)),path/'pending-parent.json',definition_hash=sha(definition),attempts=4,seconds=0)
    unresolved=service.containing_document(actor,part['version_id'])
    assert unresolved['state']=='incomplete' and unresolved['body'] is None
    assert UUID(part['source_id']) not in {row['id'] for row in service.browse_documents(actor)}


def test_legacy_snapshot_reuses_its_explicit_old_immutable_receipt(logical):
    import json
    from czero_core.projects import logical_key
    client,definition,service,actor,path=logical
    original='# Legacy beginning\n\n'+'Unchanged legacy paragraph.\n\n'*10000
    first,_=publish(client,definition,path,original)
    changed=original+'\nUpdated legacy ending.\n'
    second,_=publish(client,definition,path,changed)
    full=service.read_document(actor,second['id'])
    old_id=second['data']['part_receipt_ids'][0]
    with service.database.engine.begin() as connection:
        row=connection.execute(text('SELECT data FROM c0_objects WHERE id=CAST(:id AS uuid)'),{'id':old_id}).scalar_one()
        legacy_key=logical_key('source_sync_history_v1',row['connector_id']+':'+row['external_id']+':'+row['version_id'])
        connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{key}',to_jsonb(CAST(:key AS text))) WHERE id=CAST(:id AS uuid)"),{'id':old_id,'key':legacy_key})
        ids=[old_id,*second['data']['part_receipt_ids'][1:]]
        for identifier in (second['id'],):
            connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{part_receipt_ids}',CAST(:ids AS jsonb)) WHERE id=CAST(:id AS uuid)"),{'id':identifier,'ids':json.dumps(ids)})
    assert service.read_document(actor,second['id'])['body']==changed
    assert service.read_document(actor,second['id'],revision_id=full['revision_id'])['body']==changed


def test_thousands_of_document_summaries_remain_bounded_without_bodies(sources,capsys):
    import json
    import time
    source,owner,_,_=sources
    reader=DocumentService(source.database,source.access)
    marker=uuid4().hex
    with source.database.engine.begin() as connection:
        space=reader._space(connection)
        connection.execute(text("""INSERT INTO c0_sources(id,space_id,ingest_key,title,metadata)
            SELECT gen_random_uuid(),:space,md5(:marker||i::text)||md5(i::text||:marker),
                'Synthetic directory '||i::text,jsonb_build_object('fixture',CAST(:marker AS text))
            FROM generate_series(1,5000) i"""),{'space':space,'marker':marker})
    try:
        started=time.perf_counter();first=reader.browse_documents(owner,limit=50);elapsed=(time.perf_counter()-started)*1000
        last=reader.browse_documents(owner,limit=50,offset=4950)
        assert len(first)==len(last)==50 and not {r['id'] for r in first}&{r['id'] for r in last}
        assert all('body' not in row and 'parts' not in row for row in first+last)
        with pytest.raises(ValueError):reader.browse_documents(owner,limit=101)
        print(json.dumps({'source_summaries':5000,'page_size':50,'initial_list_ms':round(elapsed,2)}))
    finally:
        with source.database.engine.begin() as connection:
            connection.execute(text("DELETE FROM c0_sources WHERE space_id=:space AND metadata @> jsonb_build_object('fixture',CAST(:marker AS text))"),{'space':space,'marker':marker})


def test_ten_thousand_logical_parents_use_bounded_summary_pages(logical):
    import json
    import time
    _,_,service,actor,_=logical
    sources=[];versions=[];documents=[];objects=[]
    content_hash=digest('fixture')
    with service.database.engine.begin() as connection:space=service._space(connection)
    for i in range(10000):
        source,version,document,receipt,parent,history=[uuid4() for _ in range(6)]
        sources.append({'id':source,'space':space,'key':digest(str(source)),'title':'Synthetic directory '+str(i)})
        versions.append({'id':version,'space':space,'source':source,'hash':content_hash})
        documents.append({'id':document,'space':space,'version':version,'hash':content_hash})
        part={'key':str(receipt),'connector_id':'documents','external_id':str(i),'parent_external_id':str(i),
            'parent_content_hash':content_hash,'part_number':1,'start_byte':0,'end_byte':7,
            'source_id':str(source),'version_id':str(version),'last_content_hash':content_hash,
            'sync_status':'verified','extraction_status':'ready'}
        snapshot={'key':str(parent),'connector_id':'documents','external_id':str(i),
            'content_hash':content_hash,'part_receipt_ids':[str(receipt)],'total_bytes':7}
        for identifier,kind,data in ((receipt,'source_part_v1',part),(parent,'source_snapshot_v1',snapshot)):
            objects.append({'id':identifier,'space':space,'type':'c0_project_'+kind,'data':json.dumps(data)})
    try:
        with service.database.engine.begin() as connection:
            connection.execute(text("INSERT INTO c0_sources(id,space_id,ingest_key,title,metadata) VALUES(:id,:space,:key,:title,'{}')"),sources)
            connection.execute(text("INSERT INTO c0_source_versions(id,space_id,source_id,number,filename,media_type,content_hash,size_bytes,state,retain_original,original_present) VALUES(:id,:space,:source,1,'fixture.md','text/markdown',:hash,7,'ready',false,false)"),versions)
            connection.execute(text("INSERT INTO c0_documents(id,space_id,version_id,body,text_hash,locations) VALUES(:id,:space,:version,'fixture',:hash,'[]')"),documents)
            connection.execute(text("INSERT INTO c0_objects(id,space_id,type_name,data,tags) VALUES(:id,:space,:type,CAST(:data AS jsonb),'{}')"),objects)
            for table in ('c0_objects','c0_sources','c0_source_versions'):connection.execute(text('ANALYZE '+table))
        for offset in (0,9950):
            started=time.perf_counter();rows=service.browse_documents(actor,limit=50,offset=offset)
            assert len(rows)==50 and all(row['multipart'] for row in rows)
            assert all('body' not in row and 'parts' not in row for row in rows)
            print(json.dumps({'logical_parents':10000,'offset':offset,'summaries':len(rows),
                'elapsed_ms':round((time.perf_counter()-started)*1000,2)}))
    finally:
        # Each statement stays bounded even when the assertion fails. Deleting
        # all versions at once can spend the SQL deadline checking foreign keys.
        for table,rows in (('c0_documents',documents),('c0_source_versions',versions),('c0_sources',sources),('c0_objects',objects)):
            for start in range(0,len(rows),200):
                with service.database.engine.begin() as connection:
                    connection.execute(text('DELETE FROM '+table+' WHERE space_id=:space AND id=ANY(CAST(:ids AS uuid[]))'),
                        {'space':space,'ids':[row['id'] for row in rows[start:start+200]]})
        with service.database.engine.begin() as connection:
            for table in ('c0_objects','c0_sources','c0_source_versions'):connection.execute(text('ANALYZE '+table))


def test_corrupt_staged_replacement_never_displaces_current_generation(logical):
    from c0_ingest.errors import C0Error
    client,definition,service,actor,path=logical
    first,_=publish(client,definition,path,'# Current\n\nCURRENT-BEFORE-CORRUPT-REPLACEMENT\n')
    before=service.read_document(actor,first['id'])
    changed=Item('documents','manual.md','Synthetic full manual',b'# Replacement\n\nVALID-REPLACEMENT-BYTES\n','text/markdown')
    pending=sync_part(client,next(parts(changed)),path/'pending.json',definition_hash=sha(definition),attempts=4,seconds=0)
    with service.database.engine.begin() as connection:
        connection.execute(text("UPDATE c0_documents SET body=body||'CORRUPTED-PART' WHERE version_id=CAST(:id AS uuid)"),{'id':pending['version_id']})
    with pytest.raises(C0Error):save_snapshot(client,changed,[pending])
    assert service.read_document(actor,first['id'])==before
    assert client.call('sources_search',query='CORRUPTED-PART')['citations']==[]
    with service.database.engine.begin() as connection:
        connection.execute(text('UPDATE c0_documents SET body=:body WHERE version_id=CAST(:id AS uuid)'),{'id':pending['version_id'],'body':changed.content.decode()})
    current=save_snapshot(client,changed,[pending])
    assert current['id']==first['id'] and service.read_document(actor,current['id'])['body']==changed.content.decode()
