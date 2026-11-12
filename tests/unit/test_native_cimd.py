# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import sys
from test_native_session_policy import native, step

ROOT = Path(__file__).resolve().parents[2]


def test_upgrade_removes_retired_discovery_setting(native, monkeypatch):
    removed = []
    monkeypatch.setattr(sys.modules['agent'], 'unset_env', removed.append)
    monkeypatch.setenv('CZERO_CIMD_ENABLED', 'false')
    step(monkeypatch, 'update-module.d/53cimd')
    assert removed == ['CZERO_CIMD_ENABLED']


def test_restore_ignores_old_disabled_setting(native, monkeypatch):
    updates, _ = native
    step(monkeypatch, 'actions/restore-module/20persist-settings',
         {'environment': {'CZERO_CIMD_ENABLED': 'false'}})
    assert 'CZERO_CIMD_ENABLED' not in updates[-1]
    assert updates[-1]['CZERO_MODULE_ID'] == 'czero901'


def test_setting_is_absent_from_native_contracts():
    for action, direction in [('configure-module','input'), ('get-configuration','output')]:
        schema = json.loads((ROOT/f'imageroot/actions/{action}/validate-{direction}.json').read_text())
        assert 'cimd_enabled' not in schema['properties']
        assert 'cimd_enabled' not in schema.get('required', [])
    assert 'CZERO_CIMD_ENABLED' not in (ROOT/'imageroot/systemd/user/czero.service').read_text()
