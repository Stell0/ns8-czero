# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""The configured project host remains authoritative; no second scheduler."""
from uuid import uuid4
import pytest
from sqlalchemy import text
from czero_core.compilation import CompilationService, CompilationConflict
from czero_core.compilation_schema import defaults
from test_access import access
from test_projects import project, initialize


@pytest.fixture
def project_compiler(project):
    initialize(project)
    projects,manifest,owner,_=project
    compiler=CompilationService(projects.database,projects.access,clock=projects.clock).in_space(manifest['space_id'])
    compiler.configure(owner,{**defaults(),'enabled':True,'daily_model_requests':100,'weekly_pages':100},
        expected_revision=0,authorization_ref='synthetic:maintenance',idempotency_key='compiler')
    yield projects,compiler,owner
    with projects.database.engine.begin() as c:
        c.execute(text('DELETE FROM c0_compilation_policies WHERE space_id=:space'),{'space':compiler._space_id})


def test_daily_requires_actual_project_host_lease_and_intersects_caps(project_compiler):
    projects,compiler,owner=project_compiler
    data={'kind':'daily','cycle_key':projects.clock().date().isoformat(),'lease_owner':'compiler','policy_revision':1}
    with pytest.raises(ValueError,match='compilation_project_lease_required'):
        compiler.claim_run(owner,data,idempotency_key='unbound')
    host=projects.claim_run(owner,'daily','host',1,idempotency_key='host')['records'][0]['data']
    lease={k:host[k] for k in ('run_id','lease_owner','fencing_generation')}
    result=compiler.claim_run(owner,{**data,'project_lease':lease},idempotency_key='bound')
    assert result['run']['data']['project_lease']==lease
    assert result['run']['data']['project_config_version']==1
    assert result['run']['data']['policy']['daily_model_requests']==5
    assert result['run']['data']['policy']['weekly_pages']==30
    discovered=compiler.discover(owner,{'lease':result['lease'],'expected_revision':result['run']['revision'],'limit':1},idempotency_key='discover')
    assert discovered['tasks']==[]
    with projects.database.engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM c0_objects WHERE space_id=:space AND type_name='c0_project_run_v1'"),{'space':compiler._space_id}).scalar_one()==1
    assert projects.get(owner)['data']['manifest']['schedule']['enabled'] is False


def test_project_lease_expiry_fences_compiler_and_project_review_is_reused(project_compiler):
    from datetime import timedelta
    projects,compiler,owner=project_compiler
    host=projects.claim_run(owner,'weekly','host',1,idempotency_key='host')['records'][0]['data']
    lease={k:host[k] for k in ('run_id','lease_owner','fencing_generation')}
    run=compiler.claim_run(owner,{'kind':'weekly','cycle_key':projects.clock().date().isoformat(),
        'lease_owner':'compiler','policy_revision':1,'project_lease':lease},idempotency_key='bound')
    with pytest.raises(ValueError,match='use_project_semantic_select'):
        compiler.semantic_select(owner,{'lease':run['lease'],'expected_revision':run['run']['revision']},idempotency_key='no-duplicate')
    assert compiler.discovery(owner)['cursors']==[]
    with projects.database.engine.begin() as c:
        c.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{lease_expiry}',to_jsonb(CAST(:expired AS text))) WHERE space_id=:space AND type_name='c0_project_run_v1'"),
            {'space':compiler._space_id,'expired':(projects.clock()-timedelta(seconds=1)).isoformat()})
    with pytest.raises(CompilationConflict):
        compiler.discover(owner,{'lease':run['lease'],'expected_revision':run['run']['revision'],'limit':1},idempotency_key='expired-host')


def test_recovered_project_host_updates_binding_and_fences_old_compiler(project_compiler):
    from datetime import timedelta
    projects,compiler,owner=project_compiler
    host=projects.claim_run(owner,'daily','host',1,idempotency_key='host')['records'][0]['data']
    lease={k:host[k] for k in ('run_id','lease_owner','fencing_generation')}
    data={'kind':'daily','cycle_key':projects.clock().date().isoformat(),'lease_owner':'compiler','policy_revision':1,'project_lease':lease}
    original=compiler.claim_run(owner,data,idempotency_key='first')
    with projects.database.engine.begin() as c:
        c.execute(text("UPDATE c0_objects SET data=jsonb_set(data,'{lease_expiry}',to_jsonb(CAST(:expired AS text))) WHERE space_id=:space AND type_name='c0_project_run_v1'"),
            {'space':compiler._space_id,'expired':(projects.clock()-timedelta(seconds=1)).isoformat()})
    recovered=projects.claim_run(owner,'daily','next-host',1,idempotency_key='recover-host')['records'][0]['data']
    newlease={k:recovered[k] for k in ('run_id','lease_owner','fencing_generation')}
    run=compiler.claim_run(owner,{**data,'project_lease':newlease},idempotency_key='compiler-recovery')
    assert run['lease']['fencing_generation']>original['lease']['fencing_generation']
    assert run['run']['data']['project_lease']==newlease
    with pytest.raises(CompilationConflict):
        compiler.discover(owner,{'lease':original['lease'],'expected_revision':run['run']['revision'],'limit':1},idempotency_key='old-compiler')


def test_project_inventory_limit_and_untracked_sources_do_not_expand_scope(project_compiler):
    projects,compiler,owner=project_compiler
    stored=projects.get(owner);manifest=stored['data']['manifest']
    manifest['maintenance']['max_inventory']=1
    projects.configure(owner,manifest,expected_revision=stored['revision'],authorization_ref='synthetic:inventory-bound',idempotency_key='inventory-limit')
    host=projects.claim_run(owner,'daily','host',2,idempotency_key='host')['records'][0]['data']
    lease={k:host[k] for k in ('run_id','lease_owner','fencing_generation')}
    source_ids=[]
    try:
        with projects.database.engine.begin() as c:
            source_ids=c.execute(text('''INSERT INTO c0_sources(id,space_id,ingest_key,title,metadata)
                SELECT gen_random_uuid(),:space,encode(sha256(convert_to(:seed||i::text,'UTF8')),'hex'),
                    'Synthetic untracked original','{}'::jsonb FROM generate_series(1,2) i RETURNING id'''),
                {'space':compiler._space_id,'seed':uuid4().hex}).scalars().all()
        run=compiler.claim_run(owner,{'kind':'daily','cycle_key':projects.clock().date().isoformat(),
            'lease_owner':'compiler','policy_revision':1,'project_lease':lease},idempotency_key='bound')
        selected=compiler.discover(owner,{'lease':run['lease'],'expected_revision':run['run']['revision'],'limit':20},idempotency_key='discover')
        assert selected['run']['data']['inventory_scanned']==1 and selected['tasks']==[]
        assert selected['cursor']['data']['counts']=={'out_of_scope':1}
        limited=compiler.discover(owner,{'lease':run['lease'],'expected_revision':selected['run']['revision'],'limit':20},idempotency_key='limited')
        assert limited['outcome']=='deferred_project_inventory' and not limited['complete_corpus_coverage']
        assert compiler.list_tasks(owner)['tasks']==[]
        assert projects.get(owner)['data']['manifest']['connector_ids']==[]
    finally:
        with projects.database.engine.begin() as c:
            c.execute(text('DELETE FROM c0_sources WHERE id=ANY(CAST(:ids AS uuid[]))'),{'ids':source_ids})
