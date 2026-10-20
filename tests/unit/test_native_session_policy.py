# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from io import StringIO
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest
from jsonschema import Draft7Validator
from czero_core.renewal import SessionPolicy

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def native(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'imageroot/bin'))
    monkeypatch.setenv('AGENT_INSTALL_DIR', str(ROOT/'imageroot'))
    monkeypatch.setenv('AGENT_STATE_DIR', str(tmp_path))
    monkeypatch.setenv('MODULE_ID', 'czero901')
    for name in ('CZERO_SESSION_ABSOLUTE_SECONDS', 'CZERO_SESSION_IDLE_SECONDS'):
        monkeypatch.delenv(name, raising=False)
    updates, statuses = [], []
    monkeypatch.setitem(sys.modules, 'agent', SimpleNamespace(
        mset_env=lambda values: updates.append(dict(values)), set_status=statuses.append,
        read_envfile=lambda _: {}, safe_open=lambda name: open(name, 'w')))
    return updates, statuses


def step(monkeypatch, name, data=None):
    monkeypatch.setattr(sys, 'stdin', StringIO(json.dumps(data)))
    runpy.run_path(str(ROOT/'imageroot'/name))


def test_old_install_defaults_match_core_and_repeat_preserves_policy(native, monkeypatch):
    updates, _ = native
    step(monkeypatch, 'bin/czero-create-session-policy')
    assert updates == [{'CZERO_SESSION_ABSOLUTE_SECONDS':'28800','CZERO_SESSION_IDLE_SECONDS':'3600'}]
    policy = SessionPolicy()
    assert int(updates[0]['CZERO_SESSION_ABSOLUTE_SECONDS']) == policy.absolute_seconds
    assert int(updates[0]['CZERO_SESSION_IDLE_SECONDS']) == policy.idle_seconds
    monkeypatch.setenv('CZERO_SESSION_ABSOLUTE_SECONDS', '7200')
    monkeypatch.setenv('CZERO_SESSION_IDLE_SECONDS', '600')
    step(monkeypatch, 'bin/czero-create-session-policy')
    assert len(updates) == 1


def test_partial_configuration_preserves_other_bound_and_old_restore_defaults(native, monkeypatch):
    updates, _ = native
    monkeypatch.setenv('CZERO_SESSION_ABSOLUTE_SECONDS', '7200')
    monkeypatch.setenv('CZERO_SESSION_IDLE_SECONDS', '600')
    request = {'host':'c0.example.test','session_policy':{'absolute_seconds':1200}}
    step(monkeypatch, 'actions/configure-module/13validate-session-policy', request)
    assert updates == []
    step(monkeypatch, 'actions/configure-module/38persist-session-policy', request)
    assert updates == [{'CZERO_SESSION_ABSOLUTE_SECONDS':'1200','CZERO_SESSION_IDLE_SECONDS':'600'}]
    step(monkeypatch, 'actions/restore-module/20persist-settings', {'environment':{
        'CZERO_HOST':'c0.example.test', 'CZERO_MODULE_ID':'czero1',
        'CZERO_SESSION_ABSOLUTE_SECONDS':'4500','CZERO_SESSION_IDLE_SECONDS':'900'}})
    assert updates[-1]['CZERO_MODULE_ID'] == 'czero901'
    assert updates[-1]['CZERO_SESSION_ABSOLUTE_SECONDS'] == '4500'
    assert updates[-1]['CZERO_SESSION_IDLE_SECONDS'] == '900'


@pytest.mark.parametrize('patch', [None, [], {'unknown':60}, {'idle_seconds':True},
    {'absolute_seconds':59}, {'absolute_seconds':86401}, {'idle_seconds':28801},
    {'idle_seconds':'60'}, {'absolute_seconds':60,'idle_seconds':61}])
def test_invalid_policy_is_rejected_before_any_settings_mutation(native, monkeypatch, capsys, patch):
    updates, statuses = native
    with pytest.raises(SystemExit) as caught:
        step(monkeypatch, 'actions/configure-module/13validate-session-policy', {'session_policy':patch})
    assert caught.value.code == 2 and updates == [] and statuses == ['validation-failed']
    assert json.loads(capsys.readouterr().out) == [{'field':'session_policy','parameter':'session_policy','error':'invalid_session_policy'}]


def test_schema_and_persistence_preserve_exact_second_values(native, monkeypatch):
    updates, _ = native
    request = {'host':'c0.example.test','session_policy':{'absolute_seconds':121,'idle_seconds':61}}
    schema = json.loads((ROOT/'imageroot/actions/configure-module/validate-input.json').read_text())
    Draft7Validator(schema).validate(request)
    step(monkeypatch, 'actions/configure-module/13validate-session-policy', request)
    step(monkeypatch, 'actions/configure-module/38persist-session-policy', request)
    assert updates == [{'CZERO_SESSION_ABSOLUTE_SECONDS':'121','CZERO_SESSION_IDLE_SECONDS':'61'}]
