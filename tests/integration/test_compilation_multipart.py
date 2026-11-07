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


def test_bootstrap_multipart_shrink_and_project_tracking_scope(logical):
    from datetime import datetime, timezone
    from uuid import uuid4
    from czero_core.projects import ProjectService
    client,definition,reader,owner,path=logical
    initial,receipts=publish(client,definition,path,'# Multipart original\n\n'+'A source-backed procedure.\n'*6500)
    assert len(receipts)>=2
    service=CompilationService(reader.database,reader.access).in_space(client.space_id)
    try:
        service.configure(owner,{**defaults(),'enabled':True},expected_revision=0,
            authorization_ref='synthetic:bootstrap',idempotency_key='enable-maintenance')
        run=service.claim_run(owner,{'kind':'bootstrap','cycle_key':'multipart','lease_owner':'worker','policy_revision':1},idempotency_key='bootstrap')
        discovered=service.discover(owner,{'lease':run['lease'],'expected_revision':run['run']['revision'],'limit':20},idempotency_key='inventory')
        tasks=discovered['tasks']
        assert len(tasks)==1 and tasks[0]['source_bindings'][0]['logical_document_id']==initial['id']
        source=tasks[0]['source_bindings'][0]
        assessed=service.assess(owner,{'lease':run['lease'],'expected_revision':discovered['run']['revision'],
            'task_id':tasks[0]['id'],'expected_task_revision':tasks[0]['revision'],
            'reviewed_source_ids':[initial['id']],'child_task_ids':[],'status':'reviewed','findings':[]},idempotency_key='assess')
        service.checkpoint(owner,{'lease':run['lease'],'expected_revision':assessed['run']['revision'],'action':'finish'},idempotency_key='finish-bootstrap')
        changed,parts=publish(client,definition,path,'# Smaller current original\n\nChanged procedure.\n')
        assert changed['id']==initial['id'] and len(parts)==1
        projects=ProjectService(reader.database,reader.access).in_space(client.space_id)
        host=projects.claim_run(owner,'daily','daily-host',projects.get(owner)['data']['version'],idempotency_key='host')['records'][0]['data']
        host_lease={k:host[k] for k in ('run_id','lease_owner','fencing_generation')}
        run=service.claim_run(owner,{'kind':'daily','cycle_key':datetime.now(timezone.utc).date().isoformat(),
            'lease_owner':'compiler','policy_revision':1,'project_lease':host_lease},idempotency_key='daily')
        # Finish the old pinned sweep, then catch up to the new publication.
        for index in range(3):
            discovered=service.discover(owner,{'lease':run['lease'],'expected_revision':run['run']['revision'],'limit':20},idempotency_key='step-'+str(index))
            run={**discovered,'lease':run['lease']}
            if run['tasks']:break
        assert len(run['tasks'])==1
        replacement=run['tasks'][0]
        assert replacement['source_bindings'][0]['logical_document_id']==initial['id']
        assert replacement['source_bindings'][0]['revision_id']!=source['revision_id']
        assert replacement['source_bindings'][0]['parts_hash']!=source['parts_hash']
        with service.database.engine.connect() as c:
            physical={str(r['source_id']) for r in receipts}
            assessed_ids={str(v) for v in c.execute(text('SELECT logical_document_id FROM c0_compilation_sources WHERE space_id=:space'),{'space':client.space_id}).scalars()}
            assert not assessed_ids & physical
    finally:
        with service.database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_compilation_policies WHERE space_id=:space'),{'space':client.space_id})
