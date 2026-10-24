# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from io import StringIO
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

from jsonschema import Draft7Validator
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def lifecycle(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'imageroot/bin'))
    monkeypatch.setenv('AGENT_INSTALL_DIR',str(ROOT/'imageroot'))
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path))
    monkeypatch.setenv('MODULE_ID','czero901')
    monkeypatch.delenv('CZERO_CONNECTION_IDLE_SECONDS',raising=False)
    updates,statuses = [],[]
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(mset_env=lambda value:updates.append(dict(value)),
        set_status=statuses.append,read_envfile=lambda _: {},safe_open=lambda name:open(name,'w')))
    def step(name,data=None):
        monkeypatch.setattr(sys,'stdin',StringIO(json.dumps(data)))
        return runpy.run_path(str(ROOT/'imageroot'/name))
    return updates,statuses,step


def test_old_install_default_and_repeat_preserve_operator_setting(lifecycle,monkeypatch):
    updates,_,step = lifecycle
    step('bin/czero-create-connection-policy')
    assert updates == [{'CZERO_CONNECTION_IDLE_SECONDS':'2592000'}]
    monkeypatch.setenv('CZERO_CONNECTION_IDLE_SECONDS',str(42*86400))
    step('bin/czero-create-connection-policy')
    assert len(updates) == 1


def test_partial_configuration_and_restore_preserve_connection_inactivity(lifecycle,monkeypatch):
    updates,_,step = lifecycle
    monkeypatch.setenv('CZERO_CONNECTION_IDLE_SECONDS',str(42*86400))
    step('actions/configure-module/39persist-connection-policy',{'host':'c0.example.test'})
    assert updates[-1] == {'CZERO_CONNECTION_IDLE_SECONDS':str(42*86400)}
    step('actions/configure-module/39persist-connection-policy',{'connection_idle_seconds':14*86400})
    assert updates[-1] == {'CZERO_CONNECTION_IDLE_SECONDS':str(14*86400)}
    step('actions/restore-module/20persist-settings',{'environment':{'CZERO_HOST':'c0.example.test',
        'CZERO_CONNECTION_IDLE_SECONDS':str(45*86400)}})
    assert updates[-1]['CZERO_CONNECTION_IDLE_SECONDS'] == str(45*86400)
    assert updates[-1]['CZERO_MODULE_ID'] == 'czero901'


@pytest.mark.parametrize('value',[None,False,'2592000',0,86399,86401,31622400,[],{}])
def test_invalid_policy_is_rejected_before_any_settings_mutation(lifecycle,capsys,value):
    updates,statuses,step = lifecycle
    with pytest.raises(SystemExit):
        step('actions/configure-module/14validate-connection-policy',{'connection_idle_seconds':value})
    assert not updates and statuses == ['validation-failed']
    assert json.loads(capsys.readouterr().out) == [{'field':'connection_idle_seconds',
        'parameter':'connection_idle_seconds','error':'invalid_connection_policy'}]
    schema = json.loads((ROOT/'imageroot/actions/configure-module/validate-input.json').read_text())
    assert list(Draft7Validator(schema).iter_errors({'host':'c0.example.test','connection_idle_seconds':value}))


@pytest.mark.parametrize('value',['+2592000','2592000.0','Infinity','٢٥٩٢٠٠٠',''])
def test_malformed_saved_policy_cannot_be_silently_replaced(lifecycle,monkeypatch,value):
    updates,_,step = lifecycle
    monkeypatch.setenv('CZERO_CONNECTION_IDLE_SECONDS',value)
    with pytest.raises(ValueError,match='^invalid_connection_policy$'):
        step('bin/czero-create-connection-policy')
    assert not updates
