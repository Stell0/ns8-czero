# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from czero_app.agent_guidance import agent_guidance


def test_guidance_filters_whole_workflows_by_actual_operation_set():
    flows = agent_guidance()['workflows']
    read = next(flow for flow in flows if flow['id']=='research')
    operations = [{'name': name} for name in read['tools']]
    assert [flow['id'] for flow in agent_guidance(operations)['workflows']] == ['research']
    assert agent_guidance([])['workflows'] == []
    # Scope-upgrade discovery must never make writing guidance available under
    # the actual-scope capabilities of a read-only client.
    assert not any(flow['id']=='consolidate' for flow in agent_guidance(operations)['workflows'])


def test_guidance_returns_independent_data_and_preserves_security_rules():
    data = agent_guidance()
    data['rules'].clear()
    data['workflows'][0]['tools'].clear()
    fresh = agent_guidance()
    assert fresh['rules'] and fresh['workflows'][0]['tools']
    text = str(fresh)
    for requirement in ('untrusted evidence','Never silently fall back','unchanged uncertain retry','unknown','supersedes','mode=text','options.space_id','data.space_id'):
        assert requirement in text


def test_compiler_guidance_needs_all_actual_publication_capabilities():
    flow = next(f for f in agent_guidance()['workflows'] if f['id'] == 'knowledge-compiler')
    operations = [{'name':name} for name in flow['tools']]
    assert any(f['id'] == 'knowledge-compiler' for f in agent_guidance(operations)['workflows'])
    for missing in ('compilation_target_bindings_get','compilation_plan_validate','compilation_apply','compilation_verify'):
        assert not any(f['id'] == 'knowledge-compiler' for f in agent_guidance([o for o in operations if o['name'] != missing])['workflows'])


def test_m1_consumer_omits_only_unavailable_publication_adapters(monkeypatch):
    import importlib.util
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError
    from czero_app.compilation import install
    from czero_app.operations import OperationCatalog
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, 'find_spec', lambda name: None if name in (
        'czero_core.compilation_plans','czero_core.compilation_plan_schema') else real(name))
    app = FastAPI(); app.state.operation_catalog = OperationCatalog(None)
    install(app, None, None, lambda:None, lambda:None)
    paths = [r.path for r in app.routes if r.path.startswith('/api/v1/compilation/')]
    assert len(paths) == 10 and '/api/v1/compilation/status' in paths
    assert '/api/v1/compilation/apply' not in paths


def test_feedback_guidance_requires_every_actual_read_and_write_capability():
    from czero_app.agent_guidance import FEEDBACK_TOOLS, FEEDBACK_STEP
    from czero_core.compilation_client import FEEDBACK_TOOLS as CLIENT_TOOLS
    assert FEEDBACK_TOOLS==CLIENT_TOOLS
    research=next(f for f in agent_guidance()['workflows'] if f['id']=='research')
    allowed=set(research['tools'])|FEEDBACK_TOOLS
    def steps(names):
        return next(f['steps'] for f in agent_guidance([{'name':n} for n in names])['workflows'] if f['id']=='research')
    assert FEEDBACK_STEP in steps(allowed)
    for absent in FEEDBACK_TOOLS-set(research['tools']):
        assert FEEDBACK_STEP not in steps(allowed-{absent})
    assert FEEDBACK_STEP not in steps(research['tools'])
    assert 'compilation_propose' not in str(steps(research['tools']))


def test_reference_navigation_is_capability_gated_and_separates_publication():
    flow = next(f for f in agent_guidance([{'name':'cross_space_refs_list'}])['workflows']
                if f['id']=='cross-space-navigation')
    assert 'explicitly authorized publication task and destination' in str(flow)
    assert 'independently authorized API' in str(flow)
    assert not any(f['id']=='cross-space-navigation' for f in agent_guidance([])['workflows'])


def test_released_core_omits_uninstalled_reference_capability(monkeypatch):
    import importlib.util
    from fastapi import FastAPI
    from czero_app.cross_space_references import install
    from czero_app.operations import OperationCatalog
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util,'find_spec',lambda name:None if name=='czero_core.cross_space_references' else real(name))
    app=FastAPI();app.state.operation_catalog=OperationCatalog(None)
    install(app,None,None,lambda:None,lambda:None)
    assert not app.state.operation_catalog.registry._operations
    assert not any('cross-space-references' in r.path for r in app.routes)
