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
