# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Whole evidence is read from immutable documents, never overlapping chunks."""
import hashlib
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.documents import DocumentService
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
    assert queued['state'] == 'queued' and queued['body'] is None
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
    assert reader.read_document(owner, version['source_id'], revision_id=version['id'])['body'] == body
    assert len(reader.document_history(owner, version['source_id'])) == 2
    service.delete(owner, version['source_id'], expected_revision=2)
    assert not reader.browse_documents(owner)
    assert reader.read_document(owner, version['source_id'], revision_id=version['id'])['body'] == body
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
    assert service.read_document(actor, first['id'], revision_id=full['revision_id'])['body'] == body
    assert service.containing_document(actor, receipts[-1]['version_id'])['body'] == body
    assert client.call('citations_get', chunk_id=chunk['id']) == citation
    assert len(service.document_history(actor, first['id'])) == 2
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
    assert service.read_document(actor, first['id'], revision_id=before['revision_id'])['body'] == body


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
    old_id=first['data']['part_receipt_ids'][0]
    with service.database.engine.begin() as connection:
        row=connection.execute(text('SELECT data FROM c0_objects WHERE id=CAST(:id AS uuid)'),{'id':old_id}).scalar_one()
        legacy_key=logical_key('source_sync_history_v1',row['connector_id']+':'+row['external_id']+':'+row['version_id'])
        connection.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{key}',to_jsonb(CAST(:key AS text))) WHERE id=CAST(:id AS uuid)"),{'id':old_id,'key':legacy_key})
        ids=[old_id,*second['data']['part_receipt_ids'][1:]]
        for identifier in (second['id'],str(full['revision_id'])):
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
