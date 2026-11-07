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
    for missing in ('compilation_plan_validate','compilation_apply','compilation_verify'):
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
