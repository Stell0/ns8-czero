# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2] / 'imageroot'


def test_export_only_emits_known_aggregate_labels(monkeypatch, capsys):
    snapshot = {'inventory': {'sources': 12, 'private account': 999},
                'source_versions': {'failed': 3}, 'source_failures': {'protected_pdf': 1},
                'jobs': {'queued': 7}, 'extraction_runs': None}

    def run(args, **kwargs):
        if args[0] == 'systemctl':
            return SimpleNamespace(returncode=3, stdout='active\nactive\nactive\ninactive\n')
        if args[3] == 'czero-postgres':
            assert 'REPEATABLE READ READ ONLY' in kwargs['input']
            assert 'statement_timeout' in kwargs['input']
            return SimpleNamespace(returncode=0, stdout=json.dumps(snapshot))
        assert args[-1] == '/tmp/czero-mcp-counts.json'
        return SimpleNamespace(returncode=0, stdout='{"success": 2, "error": 1, "private": 33}')

    monkeypatch.setattr(subprocess, 'run', run)
    runpy.run_path(str(ROOT / 'bin/export-metrics'), run_name='__main__')
    output = capsys.readouterr().out
    assert 'czero_inventory{kind="sources"} 12' in output
    assert 'czero_source_failures{reason="protected_pdf"} 1' in output
    assert 'czero_source_versions{state="queued"} 0' in output
    assert 'czero_jobs{state="queued"} 7' in output
    assert 'czero_service_up{service="extraction"} 0' in output
    assert '# TYPE czero_mcp_calls_total counter' in output
    assert 'czero_mcp_calls_total{outcome="error"} 1' in output
    assert 'private' not in output


def test_export_omits_unavailable_counts_instead_of_reporting_zero(monkeypatch, capsys):
    def run(args, **kwargs):
        if args[0] == 'systemctl':
            return SimpleNamespace(returncode=3, stdout='inactive\ninactive\ninactive\ninactive\n')
        return SimpleNamespace(returncode=1, stdout='private database error')
    monkeypatch.setattr(subprocess, 'run', run)
    runpy.run_path(str(ROOT / 'bin/export-metrics'), run_name='__main__')
    out, err = capsys.readouterr()
    assert 'czero_database_metrics_up 0' in out
    assert 'czero_collection_timestamp_seconds' in out
    assert 'czero_inventory' not in out and 'czero_mcp_calls_total' not in out
    assert err == 'C0 database metrics unavailable\n'


class DashboardRegistry:
    def __init__(self):
        self.dashboards = {}
        self.events = []

    def hget(self, key, field):
        return self.dashboards.get((key, field))

    def pipeline(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def hset(self, key, field, value):
        self.dashboards[key, field] = value.encode()

    def publish(self, name, payload):
        self.events.append((name, json.loads(payload)))

    def execute(self):
        pass


def test_dashboard_instances_are_isolated_and_republish_only_on_change(monkeypatch):
    monkeypatch.setitem(sys.modules, 'agent', SimpleNamespace())
    publish = runpy.run_path(str(ROOT / 'bin/czero-publish-dashboard'))['publish']
    registry = DashboardRegistry()
    registry.dashboards['module/czero2/metrics_dashboards', 'custom'] = b'{ }'
    for module_id in ('czero2', 'czero2', 'czero3'):
        publish(registry, module_id)
    assert registry.events == [(f'module/czero{n}/event/metrics-dashboard-changed', {}) for n in (2, 3)]
    assert registry.dashboards['module/czero2/metrics_dashboards', 'custom'] == b'{ }'
    with pytest.raises(ValueError):
        publish(registry, 'czero2"}')
    for module_id in ('czero2', 'czero3'):
        configured = registry.dashboards[f'module/{module_id}/metrics_dashboards', 'czero-overview']
        dashboard = json.loads(configured)
        assert module_id in dashboard['uid'] and module_id in dashboard['title']
        expressions = [target['expr'] for panel in dashboard['panels'] for target in panel.get('targets', ())]
        assert len(expressions) >= 10 and all(module_id in expr for expr in expressions)
        assert b'__MODULE_ID__' not in configured
    for path in ('actions/create-module', 'actions/restore-module', 'update-module.d'):
        assert (ROOT / path / '95grafana-dashboard').resolve().is_file()
