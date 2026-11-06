# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from uuid import UUID
import pytest
from sqlalchemy import text
from czero_core.compilation import CompilationService, CompilationConflict
from czero_core.compilation_schema import defaults
from test_full_documents import (logical, publish, sample_connection, knowledge_http,
    space_http, transport, application)


def test_nonfirst_part_provenance_and_receipt_revision_invalidate_support(logical):
    client, definition, reader, owner, path = logical
    saved, receipts = publish(client, definition, path,
        '# Synthetic original\n\n' + 'Distinct supporting evidence.\n'*6500)
    assert len(receipts) >= 2
    service = CompilationService(reader.database, reader.access).in_space(client.space_id)
    try:
        service.configure(owner, {**defaults(), 'enabled': True}, expected_revision=0,
            authorization_ref='synthetic:multipart', idempotency_key='enable')
        doc = client.call('documents_get', version_id=receipts[-1]['version_id'])
        chunk = client.call('document_chunks_list', document_id=doc['id'], limit=1)['chunks'][0]
        complete = reader.read_document(owner, saved['id'])
        selection = {'logical_document_id': saved['id'], 'revision_id': str(complete['revision_id']), 'chunk_ids': [chunk['id']]}
        bindings = service.source_bindings(owner, [selection])['source_bindings']
        proposal = {'policy_revision': 1, 'origin': 'manual', 'reason': 'distributed_evidence',
            'topic_key': 'multipart', 'source_bindings': bindings}
        service.propose(owner, proposal, idempotency_key='proposal')
        assert service.status(owner)['sources']['stale'] == 0
        with service.database.engine.begin() as c:
            c.execute(text("UPDATE c0_sources SET metadata=metadata||jsonb_build_object('provenance',jsonb_build_object('version','changed')) WHERE id=:id"),
                {'id': receipts[-1]['source_id']})
        assert service.status(owner)['sources']['stale'] == 1
        with pytest.raises(CompilationConflict):
            service.propose(owner, proposal, idempotency_key='stale-replay')
        rebound = service.source_bindings(owner, [selection])['source_bindings']
        assert rebound[0]['metadata_hash'] != bindings[0]['metadata_hash']
        service.propose(owner, {**proposal, 'source_bindings': rebound}, idempotency_key='current-provenance')
        with service.database.engine.begin() as c:
            c.execute(text("UPDATE c0_objects SET revision=revision+1 WHERE id=(SELECT (data->'part_receipt_ids'->>1)::uuid FROM c0_objects WHERE id=:id)"), {'id': saved['id']})
        assert service.status(owner)['sources']['stale'] == 1
    finally:
        with service.database.engine.begin() as c:
            for table in ('events','dependencies','sources'):
                c.execute(text('DELETE FROM c0_compilation_'+table+' WHERE space_id=:space'), {'space': client.space_id})
            c.execute(text('UPDATE c0_compilation_tasks SET predecessor_id=NULL WHERE space_id=:space'), {'space': client.space_id})
            for table in ('tasks','runs','policies'):
                c.execute(text('DELETE FROM c0_compilation_'+table+' WHERE space_id=:space'), {'space': client.space_id})
