# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Installed Core/disposable native backup fixture; never run against real knowledge."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import UUID, uuid4

from sqlalchemy import text
from czero_core import Database
from czero_core.access import AccessService
from czero_core.compilation import CompilationService, CompilationConflict
from czero_core.compilation_schema import defaults, digest
from czero_core.compilation_client import navigation_plan
from czero_core.compilation_content import record_binding
from czero_core.annotations import AnnotationService, ContentTarget
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.sources import OriginalStore, SourceService, register_source_handlers
from czero_core.spaces import SpaceService
from czero_core.wiki import WikiService

assert os.environ.get('CZERO_DISPOSABLE_TEST') == '1', 'Disposable fixture marker required'
mode = os.environ.get('CZERO_COMPILATION_STAGE', 'exercise')
assert mode in ('seed', 'verify', 'exercise')
state_path = Path(os.environ.get('CZERO_COMPILATION_STATE', '/var/lib/czero/sources/compilation-fixture.json'))
root = state_path.parent / 'compilation-fixture-originals'
database = Database()
tables = ['c0_compilation_' + suffix for suffix in ('policies','runs','tasks','sources','dependencies','events')]


def observed(space):
    with database.engine.connect() as c:
        return {table: digest(c.execute(text('SELECT to_jsonb(t) FROM '+table+' t WHERE space_id=:space ORDER BY to_jsonb(t)::text'),
            {'space': space}).scalars().all()) for table in tables}


def owner_for(state):
    access = AccessService(database, state['issuer'], UUID(state['owner_key']))
    owner = access.resolve(VerifiedIdentity(state['issuer'], 'fixture-owner', state['owner_key'],
        'compiler-fixture', 'Compiler fixture', time.time()+300))
    return access, owner


try:
    if mode in ('seed', 'exercise'):
        assert not state_path.exists(), 'Preserve existing fixture rather than overwriting it'
        state = {'issuer': 'https://compiler-fixture.example.invalid/'+uuid4().hex, 'owner_key': str(uuid4())}
        access, owner = owner_for(state)
        space = SpaceService(database, access).create(owner, 'Disposable compiler fixture '+uuid4().hex, idempotency_key='space')['id']
        state['space'] = space
        registry = default_registry()
        originals = OriginalStore(root)
        register_source_handlers(registry, database, originals)
        sources = SourceService(database, access, registry, originals).in_space(space)
        version = sources.ingest_text(owner, title='Synthetic source', body='Synthetic source-backed inventory.', idempotency_key='source')
        with database.engine.begin() as c:
            registry.get('source.extract').execute(c, {'version_id': version['id']})
        document = sources.document(owner, version['id'])
        chunk = sources.chunks(owner, document['id'])[0]
        page = WikiService(database, access).in_space(space).create_page(owner, 'synthetic', 'Synthetic', '# Authored inventory', idempotency_key='page')
        state['authored_page_id'] = page['id']
        service = CompilationService(database, access).in_space(space)
        assert service.policy(owner)['revision'] == 0
        assert service.status(owner)['sources']['compiled'] == 0
        service.configure(owner, {**defaults(), 'enabled': True}, expected_revision=0,
            authorization_ref='synthetic:disposable-native', idempotency_key='enable-fixture')
        bindings = service.source_bindings(owner, [{'logical_document_id': str(version['source_id']),
            'revision_id': str(version['id']), 'chunk_ids': [str(chunk['id'])]}])['source_bindings']
        # A real atomic publication stays pending across the native clean restore.
        publication_task = service.propose(owner, {'policy_revision':1,'origin':'manual',
            'reason':'missing_concept','topic_key':'native/compiled','source_bindings':bindings},
            idempotency_key='compile-proposal')['task']
        compilation = service.claim_run(owner, {'kind':'manual','cycle_key':'native-compiled',
            'lease_owner':'compiler-fixture','policy_revision':1}, idempotency_key='compile-claim')
        plan = navigation_plan(space, compilation['tasks'][0], 'Compiled synthetic inventory',
            'Read the original inventory evidence.', [(sources.citation(owner,chunk['id']),chunk['body'])],
            reviewed_source_ids=[str(version['source_id'])])
        request = {'lease':compilation['lease'],'expected_revision':compilation['run']['revision'],'plan':plan}
        preview = service.validate_plan(owner, request)
        published = service.apply_plan(owner, {**request,'plan_hash':preview['plan_hash'],
            'approval':{'plan_hash':preview['plan_hash'],'reference':'synthetic:exact-plan-review'}}, idempotency_key='compile-apply')
        assert published['outcome'] == 'applied_pending_verify'
        state['publication_task_id'] = published['task']['id']
        state['publication_records'] = published['records']
        service.checkpoint(owner, {'lease':compilation['lease'],'expected_revision':published['run']['revision'],
            'action':'partial'}, idempotency_key='compile-pending')
        proposal = {'policy_revision': 1, 'origin': 'manual', 'reason': 'incomplete_page', 'topic_key': 'synthetic',
            'source_bindings': bindings, 'target': {'kind': 'page', 'id': page['id'], 'revision': page['revision'],
                'content_id': page['content']['id'], 'content_hash': page['content']['content_hash']}}
        task = service.propose(owner, proposal, idempotency_key='proposal')['task']
        assert service.propose(owner, proposal, idempotency_key='duplicate')['task']['id'] == task['id']
        run = service.claim_run(owner, {'kind': 'manual', 'cycle_key': 'native-fixture', 'lease_owner': 'fixture', 'policy_revision': 1}, idempotency_key='claim')
        state['lease'] = run['lease']
        call = str(uuid4())
        for action in ('reserve_model', 'start_model'):
            data = {'lease': run['lease'], 'expected_revision': run['run']['revision'], 'action': action, 'request_id': call}
            if action == 'reserve_model':
                data.update(task_id=task['id'], expected_task_revision=run['tasks'][0]['revision'], reserved_tokens=100)
            run = {**service.checkpoint(owner, data, idempotency_key=action), 'lease': state['lease']}
        state['run_revision'] = run['run']['revision']
        with database.engine.begin() as c:
            registry.get('source.cleanup').execute(c, {'version_id': version['id']})
        state['observed'] = observed(space)
        with database.engine.connect() as c:
            state['epoch'] = service._epoch(c)
        state_path.write_text(json.dumps(state))
        state_path.chmod(0o600)
    else:
        state = json.loads(state_path.read_text())
        access, owner = owner_for(state)
        service = CompilationService(database, access).in_space(state['space'])
    assert observed(state['space']) == state['observed']
    current = service.status(owner, run_id=state['lease']['run_id'])
    assert current['sources']['compiled'] == 0 and current['dependencies']['stale'] == 0
    assert current['budgets'][0]['data']['requests'] == 1
    assert current['budgets'][0]['data']['usage_unknown']
    if mode == 'verify':
        with database.engine.connect() as c:
            assert service._epoch(c) != state['epoch'], 'Restore must invalidate captured database incarnation'
        assert not current['runs'][0]['lease_valid']
        try:
            service.checkpoint(owner, {'lease': state['lease'], 'expected_revision': state['run_revision'],
                'action': 'partial'}, idempotency_key='obsolete-native-fence')
        except CompilationConflict:
            pass
        else:
            raise AssertionError('Restored old fence remained writable')
        recovered = service.claim_run(owner, {'kind': 'manual', 'cycle_key': 'native-fixture',
            'lease_owner': 'restored-fixture', 'policy_revision': 1}, idempotency_key='recovery')
        assert recovered['lease']['fencing_generation'] == 2
        assert recovered['tasks'][0]['state'] == 'uncertain'
    if mode != 'seed':
        # Free the metadata-only run; its uncertain external call is never replayed.
        active = recovered if mode == 'verify' else {'lease':state['lease'],'run':current['runs'][0]}
        service.checkpoint(owner, {'lease':active['lease'],'expected_revision':active['run']['revision'],
            'action':'partial'}, idempotency_key='metadata-partial')
        compilation = service.claim_run(owner, {'kind':'manual','cycle_key':'native-compiled',
            'lease_owner':'verification-fixture','policy_revision':1}, idempotency_key='compile-recover')
        task = service.get_task(owner,state['publication_task_id'])
        assert task['state'] == 'applied_pending_verify'
        assert task['publication']['records'] == state['publication_records']
        wiki_reader = WikiService(database,access).in_space(state['space'])
        annotations = AnnotationService(database,access).in_space(state['space'])
        proofs = []
        for saved in state['publication_records']:
            if saved['kind'] == 'page':
                value = wiki_reader.get_page(owner,saved['id'])
            else:
                primary = state['publication_records'][0]
                value = annotations.get(owner, ContentTarget('wiki_revision',primary['content_id'],primary['revision']), 'verification')
                assert value['status'] == 'unverified'
            proofs.append(record_binding(saved['kind'],value))
        assert proofs == state['publication_records']
        selections = [{'logical_document_id':s['logical_document_id'],'revision_id':s['revision_id'],
            'chunk_ids':[chunk['chunk_id'] for chunk in s['chunks']]} for s in task['source_bindings']]
        assert service.source_bindings(owner,selections)['source_bindings'] == task['source_bindings']
        verified = service.verify_plan(owner, {'lease':compilation['lease'],'expected_revision':compilation['run']['revision'],
            'task_id':task['id'],'expected_task_revision':task['revision'],'policy_revision':1,
            'plan_hash':task['plan_hash'],'observations':proofs,'source_bindings':task['source_bindings']}, idempotency_key='compile-verify')
        assert verified['task']['state'] == 'succeeded' and service.status(owner)['sources']['compiled'] == 1
        assert wiki_reader.get_page(owner,state['authored_page_id'])['content']['body'] == '# Authored inventory'
        with database.engine.begin() as c:
            for table in ('c0_compilation_events','c0_compilation_dependencies','c0_compilation_sources',
                'c0_compilation_tasks','c0_compilation_runs','c0_compilation_policies',
                'c0_annotation_targets','c0_knowledge_receipts','c0_knowledge_events','c0_wiki_revisions','c0_wiki_pages',
                'c0_chunks','c0_documents','c0_source_versions','c0_sources','c0_jobs','c0_space_grants'):
                c.execute(text('DELETE FROM '+table+' WHERE space_id=:space'), {'space': state['space']})
            c.execute(text('DELETE FROM c0_spaces WHERE id=:space'), {'space': state['space']})
            c.execute(text('DELETE FROM c0_accounts WHERE issuer=:issuer'), {'issuer': state['issuer']})
        state_path.unlink()
    print(json.dumps({'compilation_state': True, 'six_tables': True, 'publication_disabled': True,
        'guarded_compilation': True, 'pending_compilation_verified': mode != 'seed',
        'restored_fence_invalidated': mode == 'verify', 'stage': mode}))
finally:
    database.close()
