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
from test_auth_http import ORIGIN, application
from c0_projects.model import Item, sha
from c0_projects.publish import parts, sync_part, save_snapshot
from czero_core.sources import SourceConflict, SourceNotFound


def publish(client, definition, tmp_path, body, *, external_id='manual.md'):
    item = Item('documents', external_id, 'Synthetic full manual', body.encode(), 'text/markdown',
        canonical_url='https://example.org/documentation/manual',
        provenance={'product':'Synthetic product','version':'8','path':['Administrator Manual','Configuration']})
    receipts = [sync_part(client, part, tmp_path/'journal.json', definition_hash=sha(definition), attempts=4, seconds=0)
        for part in parts(item, limit=131072)]
    return save_snapshot(client, item, receipts), receipts


def test_ingestion_pipeline_m0_external_parts_are_not_extraction_units(logical, record_property):
    import time
    client, definition, service, actor, path = logical
    body = (Path(__file__).resolve().parents[1] /
            'fixtures/evidence/pipeline/multipart.md').read_text(encoding='utf-8')
    started = time.perf_counter()
    saved, receipts = publish(client, definition, path, body)
    publication_seconds = time.perf_counter() - started
    assert len(receipts) >= 2
    started = time.perf_counter()
    full = service.read_document(actor, saved['id'])
    assert full['state'] == 'ready' and full['body'] == body
    assert full['text_hash'] == sha(body.encode())
    assert len(full['parts']) == len(receipts)
    assert [row['id'] for row in service.browse_documents(actor)] == [UUID(saved['id'])]
    record_property('m0_multipart_timings', __import__('json').dumps({
        'publish_seconds': publication_seconds,
        'full_read_seconds': time.perf_counter() - started,
        'parts': len(receipts)}))


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


@pytest.mark.parametrize('fault', ['missing', 'malformed', 'queued', 'missing_document', 'hash', 'order', 'parent', 'space', 'offset', 'range_size', 'total_size'])
def test_snapshot_fail_closed_without_partial_body(logical, knowledge_http, fault):
    client, definition, service, actor, path = logical
    body = '# Complete\n\n' + 'Fabricated original paragraph.\n\n' * 9500
    saved, receipts = publish(client, definition, path, body)
    initial = service.browse_documents(actor)
    assert len(initial) == 1 and initial[0]['id'] == UUID(saved['id']) and initial[0]['state'] == 'ready'
    with service.database.engine.begin() as connection:
        if fault in ('missing', 'malformed'):
            # A missing later receipt is invisible to a first-part-only check.
            ids = list(saved['data']['part_receipt_ids'])
            ids[1] = str(uuid4()) if fault == 'missing' else 'invalid stored receipt ID'
            connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{part_receipt_ids}', CAST(:ids AS jsonb)) WHERE id=CAST(:id AS uuid)"),
                {'ids':__import__('json').dumps(ids), 'id':saved['id']})
        elif fault == 'queued':
            connection.execute(text("UPDATE c0_source_versions SET state='queued' WHERE id=CAST(:id AS uuid)"), {'id':receipts[1]['version_id']})
        elif fault == 'missing_document':
            parameters = {'id':receipts[1]['version_id']}
            connection.execute(text("DELETE FROM c0_chunks WHERE document_id IN (SELECT id FROM c0_documents WHERE version_id=CAST(:id AS uuid))"), parameters)
            connection.execute(text("DELETE FROM c0_documents WHERE version_id=CAST(:id AS uuid)"), parameters)
        elif fault == 'hash':
            connection.execute(text("UPDATE c0_documents SET body='Corrupt synthetic original' WHERE version_id=CAST(:id AS uuid)"), {'id':receipts[1]['version_id']})
        elif fault in ('offset', 'range_size'):
            # A displaced range can have the correct length while starting at the wrong offset.
            connection.execute(text('''UPDATE c0_objects SET data=data || jsonb_build_object(
                'start_byte', (data->>'start_byte')::int + :start_delta, 'end_byte', (data->>'end_byte')::int + 1)
                WHERE id=CAST(:id AS uuid)'''), {'id':saved['data']['part_receipt_ids'][1],
                'start_delta':1 if fault == 'offset' else 0})
        elif fault == 'total_size':
            connection.execute(text('''UPDATE c0_objects SET data=jsonb_set(data,'{total_bytes}',to_jsonb((data->>'total_bytes')::int+1))
                WHERE id=CAST(:id AS uuid)'''), {'id':saved['id']})
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
    summary = service.browse_documents(actor)[0]
    assert summary['id'] == UUID(saved['id'])
    if fault in ('missing', 'queued', 'missing_document', 'space'):
        assert summary['state'] == 'incomplete' and summary['error_code'] == 'missing_or_unready_part'
        if fault == 'missing':
            listed = client.call('source_documents_list')['documents'][0]
            assert listed['id'] == saved['id'] and listed['error_code'] == summary['error_code']
        incomplete = service.read_document(actor, saved['id'])
        assert incomplete['state'] == 'incomplete' and incomplete['body'] is None
    elif fault == 'order':
        # Ordered receipt metadata, rather than the caller's array order, is authoritative.
        assert summary['state'] == 'ready' and summary['error_code'] is None
        assert service.read_document(actor, saved['id'])['body'] == body
    else:
        if fault in ('malformed', 'parent', 'offset', 'range_size', 'total_size'):
            assert summary['state'] == 'incomplete' and summary['error_code'] == 'invalid_part_membership'
        with pytest.raises(SourceConflict):
            service.read_document(actor, saved['id'])
        if fault == 'malformed':
            from fastapi.testclient import TestClient
            api = TestClient(knowledge_http[0], base_url=ORIGIN)
            rest = api.get('/api/v1/source-documents/' + saved['id'],
                params={'space_id':client.space_id}, headers={'Authorization':'Bearer ' + knowledge_http[1]})
            assert rest.status_code == 409 and rest.json() == {'detail':'source_conflict'}
            mcp = client.transport.call('source_documents_get', {
                'logical_document_id':saved['id'],'space_id':client.space_id})
            assert mcp['isError'] and mcp['_meta']['c0/error'] == {'code':'source_conflict','status':409}


def test_snapshot_repair_proves_membership_keeps_versions_and_fences_writes(logical):
    from czero_core.identity import Role
    from czero_core.projects import ProjectConflict, ProjectService
    from czero_core.spaces import SpaceService
    from test_access import account_named, identity, record_unadmitted

    client, definition, documents, owner, path = logical
    space_id = UUID(client.space_id)
    projects = ProjectService(documents.database, documents.access).in_space(space_id)
    spaces = SpaceService(documents.database, documents.access)
    body = '# Complete\n\n' + 'Synthetic independently acquired original.\n\n' * 4100
    previous, receipts = publish(client, definition, path, body)
    intact = documents.read_document(owner, previous['id'])
    chunk = client.call('document_chunks_list', document_id=str(intact['parts'][-1]['document_id']), limit=1)['chunks'][0]
    citation = client.call('citations_get', chunk_id=chunk['id'])
    unrelated, _ = publish(client, definition, path, 'Independent evidence.\n', external_id='other.md')
    independent = documents.read_document(owner, unrelated['id'])
    request = {'connector_id':'documents','external_id':'manual.md',
        'content_hash':sha(body.encode()),'part_receipt_ids':[row['receipt_id'] for row in receipts],
        'expected_revision':previous['revision']}
    assert client.call('project_source_snapshot_set', data={**request,'idempotency_key':uuid4().hex}) == previous
    with documents.database.engine.begin() as connection:
        # This reference cannot become deletion authority over a different parent.
        connection.execute(text('''UPDATE c0_objects SET data=jsonb_set(data,'{part_receipt_ids,1}',
            to_jsonb(CAST(:foreign_part AS text))) WHERE id=CAST(:id AS uuid)'''),
            {'id':previous['id'],'foreign_part':unrelated['data']['part_receipt_ids'][0]})
    with pytest.raises(SourceConflict):
        documents.read_document(owner, previous['id'])
    with pytest.raises(ProjectConflict):
        projects.save_source_snapshot(owner, **{**request,'expected_revision':0}, idempotency_key=uuid4().hex)

    editor_key = uuid4()
    record_unadmitted(documents.access, editor_key, 'repair-editor')
    account = account_named(documents.access, owner, 'repair-editor')
    documents.access.set_role(owner, account['id'], Role.EDITOR)
    spaces.set_grant(owner, space_id, account['id'], Role.EDITOR, expected_revision=0, idempotency_key=uuid4().hex)
    editor = documents.access.resolve(identity(documents.access, editor_key, 'repair-editor'))
    assert spaces.get(editor, space_id)['role'] == 'editor'
    spaces.set_grant(owner, space_id, account['id'], None, expected_revision=1, idempotency_key=uuid4().hex)
    with pytest.raises(PermissionDenied):
        projects.save_source_snapshot(editor, **request, idempotency_key=uuid4().hex)

    # Execute and replay the supported operation with the exact verified receipt IDs.
    data = {**request,'idempotency_key':uuid4().hex}
    saved = client.call('project_source_snapshot_set', data=data)
    assert saved['id'] == previous['id'] and saved['revision'] == previous['revision'] + 1
    assert saved['data']['content_hash'] == previous['data']['content_hash']
    assert client.call('project_source_snapshot_set', data=data) == saved
    recovered = documents.read_document(owner, previous['id'])
    assert recovered['body'] == body and recovered['parts'] == intact['parts']
    assert client.call('citations_get', chunk_id=chunk['id']) == citation
    assert documents.read_document(owner, unrelated['id']) == independent
    with pytest.raises(ContentSuperseded):
        documents.read_document(owner, previous['id'], revision_id=intact['revision_id'])
    with documents.database.engine.connect() as connection:
        assert connection.execute(text('''SELECT count(*) FROM c0_objects WHERE space_id=:space
            AND id=ANY(CAST(:ids AS uuid[]))'''),{'space':space_id,'ids':previous['data']['part_receipt_ids']}).scalar_one() == 0
    assert client.call('project_source_snapshot_set', data={**request,'expected_revision':saved['revision'],
        'idempotency_key':uuid4().hex}) == saved


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
    rows=service.browse_documents(actor)
    queued=next(row for row in rows if row['id']==UUID(part['source_id']))
    assert queued['state']=='incomplete' and queued['title']=='Pending parent'
    assert service.read_document(actor,part['source_id'])['body'] is None
    saved=save_snapshot(client,pending,[part])
    ids={row['id'] for row in service.browse_documents(actor)}
    assert UUID(saved['id']) in ids and UUID(part['source_id']) not in ids
    assert service.read_document(actor,part['source_id'])['body']==pending.content.decode()


def test_legacy_snapshot_reuses_its_explicit_old_immutable_receipt(logical):
    from czero_core.projects import logical_key
    client,definition,service,actor,path=logical
    original='# Legacy beginning\n\n'+'Unchanged legacy paragraph.\n\n'*10000
    publish(client,definition,path,original)
    changed=original+'\nUpdated legacy ending.\n'
    second,_=publish(client,definition,path,changed)
    full=service.read_document(actor,second['id'])
    old_id=second['data']['part_receipt_ids'][1]
    with service.database.engine.begin() as connection:
        row=connection.execute(text('SELECT data FROM c0_objects WHERE id=CAST(:id AS uuid)'),{'id':old_id}).scalar_one()
        legacy_key=logical_key('source_sync_history_v1',row['connector_id']+':'+row['external_id']+':'+row['version_id'])
        connection.execute(text('''UPDATE c0_objects SET data=data || jsonb_build_object('key',CAST(:key AS text),
            'parent_content_hash',CAST(:previous_hash AS text),'start_byte',(data->>'start_byte')::int+1,
            'end_byte',(data->>'end_byte')::int+1) WHERE id=CAST(:id AS uuid)'''),
            {'id':old_id,'key':legacy_key,'previous_hash':sha(original.encode())})
        connection.execute(text('''UPDATE c0_object_keys SET value=to_jsonb(CAST(:key AS text))
            WHERE object_id=CAST(:id AS uuid) AND field='key' '''),
            {'id':old_id,'key':legacy_key})
    summary=service.browse_documents(actor)[0]
    assert summary['id']==UUID(second['id']) and summary['state']=='ready' and summary['error_code'] is None
    assert service.read_document(actor,second['id'])['body']==changed
    assert service.read_document(actor,second['id'],revision_id=full['revision_id'])['body']==changed
    replacement, _ = publish(client, definition, path, '# Updated successor\n')
    assert replacement['id'] == second['id']
    assert service.read_document(actor,replacement['id'])['body'] == '# Updated successor\n'
    with service.database.engine.connect() as connection:
        assert connection.execute(text('SELECT id FROM c0_objects WHERE id=CAST(:id AS uuid)'),
            {'id':old_id}).scalar_one_or_none() is None


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
    assert client.call('sources_search',query='"CORRUPTED-PART"')['citations']==[]
    with service.database.engine.begin() as connection:
        connection.execute(text('UPDATE c0_documents SET body=:body WHERE version_id=CAST(:id AS uuid)'),{'id':pending['version_id'],'body':changed.content.decode()})
    current=save_snapshot(client,changed,[pending])
    assert current['id']==first['id'] and service.read_document(actor,current['id'])['body']==changed.content.decode()


@pytest.mark.parametrize('lost_at',['prepared','submitted'])
@pytest.mark.parametrize('return_to_same_bytes',[False,True])
def test_uncertain_publisher_retry_never_rebases_onto_newer_content(logical,monkeypatch,lost_at,return_to_same_bytes):
    from c0_ingest.errors import C0Error
    client,definition,service,actor,path=logical
    initial,_=publish(client,definition,path,'# Initial\n\nA\n')
    pending_item=Item('documents','manual.md','Synthetic full manual',b'# Uncertain\n\nB\n','text/markdown')
    journal=path/'uncertain.json';original=client.call;lost=[]
    def lose_reply(name,**arguments):
        result=original(name,**arguments)
        if not lost and (name=='sources_ingest_text' if lost_at=='prepared' else name=='project_source_status_set'):
            lost.append(True);raise C0Error('synthetic_publication_reply_lost')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(client,'call',lose_reply)
        with pytest.raises(C0Error,match='synthetic_publication_reply_lost'):
            sync_part(client,next(parts(pending_item)),journal,definition_hash=sha(definition),attempts=4,seconds=0)
    assert service.read_document(actor,initial['id'])['body']=='# Initial\n\nA\n'
    latest,_=publish(client,definition,path,'# Newest\n\nC\n')
    if return_to_same_bytes:latest,_=publish(client,definition,path,pending_item.content.decode())
    before=service.read_document(actor,latest['id'])
    with pytest.raises(C0Error,match='reconciliation|superseded'):
        sync_part(client,next(parts(pending_item)),journal,definition_hash=sha(definition),attempts=4,seconds=0)
    assert service.read_document(actor,latest['id'])==before
    versions=client.call('source_versions_list',source_id=str(before['parts'][0]['source_id']))['versions']
    assert len(versions)==1 and versions[0]['id']==str(before['parts'][0]['version_id'])


def test_legacy_publisher_journal_requires_reconciliation_after_change(logical):
    from c0_ingest.errors import C0Error
    from c0_ingest.state import read,atomic
    client,definition,service,actor,path=logical
    old_body='# Legacy original\n\nA\n'
    initial,_=publish(client,definition,path,old_body)
    newer,_=publish(client,definition,path,'# Current\n\nB\n')
    journal=path/'journal.json';saved=read(journal)
    for entry in saved.values():
        entry.pop('observations',None);entry['intent'].pop('source_revision',None)
    atomic(journal,saved);before=journal.read_bytes()
    old=Item('documents','manual.md','Synthetic full manual',old_body.encode(),'text/markdown')
    with pytest.raises(C0Error,match='legacy_source_journal_requires_current_reconciliation'):
        sync_part(client,next(parts(old)),journal,definition_hash=sha(definition),attempts=4,seconds=0)
    assert journal.read_bytes()==before
    assert service.read_document(actor,newer['id'])['body']=='# Current\n\nB\n'
    assert newer['id']==initial['id']
