# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Changed originals require actual dependent knowledge revalidation."""
import pytest
from czero_core.current_content import ContentSuperseded
from czero_core.compilation import CompilationConflict
from test_compilation_plans import compiler, coordinator_fixture, candidate, apply, verify
from test_compilation import claim, checkpoint
from test_compilation_maintenance import discover, assess
from test_sources import sources, upload, execute
from test_wiki import wiki
from test_access import access


def test_changed_source_cannot_be_acknowledged_over_stale_wiki_dependencies(compiler):
    service,owner,_,source,*_=compiler
    request,original=candidate(compiler)
    published=apply(compiler,request)
    verified=verify(compiler,request,published)
    checkpoint(compiler,{'lease':request['lease'],'run':verified['run']},'finish')
    run=discover(compiler,claim(compiler,kind='bootstrap',cycle_key='initial'))
    run=assess(compiler,run)
    assert run['outcome']=='assessment_verified'
    replacement=upload(source,data=b'Changed original procedure.',source_id=original['source_id'],expected_revision=1)
    execute(source,'source.extract',replacement['id'])
    with pytest.raises(ContentSuperseded):
        source[0].citation(owner,request['plan']['source_bindings'][0]['chunks'][0]['chunk_id'])
    run=discover(compiler,run,limit=20)
    run=discover(compiler,run,limit=20)
    task=next(t for t in run['tasks'] if t['purpose']=='source_assessment')
    assert task['source_bindings'][0]['revision_id']==str(replacement['id'])
    inspected=assess(compiler,run,task)
    assert inspected['outcome']=='assessment_partial' and inspected['task']['state']=='needs_review'
    assert service.status(owner)['sources']['compiled']==0
    dependencies=service.list_dependencies(owner,logical_document_id=original['source_id'])['dependencies']
    assert dependencies and all(not d['identities_current'] and d['state']=='stale' for d in dependencies)
    assert service.get_task(owner,published['task']['id'])['publication']['records']==published['records']
    with pytest.raises(ContentSuperseded):
        checkpoint(compiler,inspected,'finish')
    assert checkpoint(compiler,inspected,'partial')['run']['state']=='partial'


def test_bootstrap_multiple_canonical_children_advance_only_after_actual_verification(compiler):
    from uuid import uuid4
    from test_compilation import enable, support, propose
    from czero_core.compilation_client import navigation_plan
    service,owner,_,source,*_=compiler
    enable(compiler)
    bindings,_=support(compiler,data=b'Cobalt routes require authentication. Copper backups exclude temporary logs.')
    run=discover(compiler,claim(compiler,kind='bootstrap',cycle_key='multiple'))
    children=[propose(compiler,bindings,topic_key=topic)['task'] for topic in ('cobalt-routes','copper-backups')]
    run=assess(compiler,run,child_task_ids=[t['id'] for t in children])
    assert run['outcome']=='assessment_partial' and service.status(owner)['sources']['compiled']==0
    for index in range(2):
        current=claim(compiler,kind='bootstrap',cycle_key='multiple')
        child=next(t for t in current['tasks'] if t['purpose']=='knowledge')
        title={'cobalt-routes':'Cobalt route authentication','copper-backups':'Copper backup exclusions'}[child['topic_key']]
        citation=source[0].citation(owner,child['source_bindings'][0]['chunks'][0]['chunk_id'])
        plan=navigation_plan(str(service._space_id),child,title,title,[(citation,citation['body'])],
            reviewed_source_ids=[s['logical_document_id'] for s in child['source_bindings']])
        request={'lease':current['lease'],'expected_revision':current['run']['revision'],'plan':plan}
        result=apply(compiler,request)
        saved=verify(compiler,request,result)
        assert saved['task']['state']=='succeeded'
        assert service.status(owner)['sources']['compiled']==index
    assert service.status(owner)['sources']['compiled']==1
    assert service.status(owner)['tasks']['succeeded']==2
    assert len(service.list_dependencies(owner,logical_document_id=bindings[0]['logical_document_id'])['dependencies'])>=4


def test_verified_child_with_unresolved_deferred_context_does_not_complete_assessment(compiler):
    service,owner,*_=compiler
    data,original=candidate(compiler)
    data['plan']['deferred']=[{'reason':'unread_source_context','source_ids':[
        data['plan']['source_bindings'][0]['logical_document_id']]}]
    published=apply(compiler,data)
    verified=verify(compiler,data,published)
    checkpoint(compiler,{'lease':data['lease'],'run':verified['run']},'finish')
    run=discover(compiler,claim(compiler,kind='bootstrap',cycle_key='partial-child'))
    result=assess(compiler,run,child_task_ids=[published['task']['id']])
    assert result['outcome']=='assessment_partial' and service.status(owner)['sources']['compiled']==0


def test_new_target_revision_is_new_assessment_input_without_rewriting_authored_content(compiler):
    service,owner,_,source,pages=compiler
    request,original=candidate(compiler)
    published=apply(compiler,request);verified=verify(compiler,request,published)
    checkpoint(compiler,{'lease':request['lease'],'run':verified['run']},'finish')
    run=discover(compiler,claim(compiler,kind='bootstrap',cycle_key='target-change'))
    completed=assess(compiler,run,child_task_ids=[published['task']['id']])
    page=published['records'][0]
    changed=pages[0].update_page(owner,page['id'],'Authored current revision','Preserve this authored explanation.',
        expected_revision=page['revision'],idempotency_key='external-edit')
    run=discover(compiler,completed)
    run=discover(compiler,run)
    task=next(t for t in run['tasks'] if t['purpose']=='source_assessment')
    assert task['id']!=completed['task']['id']
    assert task['source_bindings']==completed['task']['source_bindings']
    assert service.status(owner)['sources']['compiled']==0
    assert pages[0].get_page(owner,page['id'])['content']['body']=='Preserve this authored explanation.'
