# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import runpy
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = ROOT / 'imageroot/actions'


def run_step(monkeypatch, name, agent, data=None):
    monkeypatch.setitem(sys.modules, 'agent', agent)
    monkeypatch.setenv('MODULE_ID', 'czero7')
    monkeypatch.setenv('TCP_PORT', '20007')
    monkeypatch.setattr(sys, 'stdin', StringIO(json.dumps(data)))
    return runpy.run_path(str(ACTIONS / name))


@pytest.mark.parametrize('data', [{}, {'host':'localhost'}, {'host':'127.0.0.1'},
    {'host':'https://c0.example.test'}, {'host':'bad-.example.test'},
    {'host':'a'*64+'.test'}, {'host':'c0.test\n'}, {'host':'c0.test','lets_encrypt':'false'},
    {'host':'c0.test','unknown':True}])
def test_invalid_configuration_schema(data):
    schema = json.loads((ACTIONS / 'configure-module/validate-input.json').read_text())
    assert list(Draft7Validator(schema).iter_errors(data))


def test_valid_configuration_schema():
    schema = json.loads((ACTIONS / 'configure-module/validate-input.json').read_text())
    Draft7Validator(schema).validate({'host':'C0.example.test','lets_encrypt':False})


def test_owned_host_can_be_reconfigured(monkeypatch, capsys):
    monkeypatch.setenv('CZERO_HOST', 'c0.example.test')
    run_step(monkeypatch, 'configure-module/10validate', SimpleNamespace(
        set_weight=lambda *a: None, http_route_in_use=lambda **kw: pytest.fail('own route must be exempt')),
        {'host':'C0.example.test'})
    assert capsys.readouterr().out == ''


def test_collision_reports_native_field_error(monkeypatch, capsys):
    monkeypatch.delenv('CZERO_HOST', raising=False)
    statuses = []
    with pytest.raises(SystemExit) as e:
        run_step(monkeypatch, 'configure-module/10validate', SimpleNamespace(
            set_weight=lambda *a: None, http_route_in_use=lambda **kw: True,
            set_status=statuses.append), {'host':'C0.example.test'})
    assert e.value.code == 2
    assert statuses == ['validation-failed']
    assert json.loads(capsys.readouterr().out) == [{'field':'host','parameter':'host',
        'value':'c0.example.test','error':'domain_already_used_in_traefik'}]


def test_route_clears_legacy_path_and_delegates_tls(monkeypatch, capsys):
    routes = []
    run_step(monkeypatch, 'configure-module/20configure-route', SimpleNamespace(set_route=routes.append),
        {'host':'C0.example.test','lets_encrypt':True})
    assert routes == [{'instance':'czero7','url':'http://127.0.0.1:20007',
        'host':'c0.example.test','path':None,'http2https':True,'lets_encrypt':True}]
    assert capsys.readouterr().out == ''


def test_route_failure_is_not_suppressed(monkeypatch):
    def fail(data):
        raise RuntimeError('route rejected')
    with pytest.raises(RuntimeError, match='route rejected'):
        run_step(monkeypatch, 'configure-module/20configure-route', SimpleNamespace(set_route=fail),
            {'host':'c0.example.test'})


def test_settings_round_trip(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv('AGENT_STATE_DIR', str(tmp_path))
    monkeypatch.setenv('AGENT_INSTALL_DIR', str(ROOT / 'imageroot'))
    env = {}
    run_step(monkeypatch, 'configure-module/40persist', SimpleNamespace(mset_env=env.update),
        {'host':'C0.example.test','lets_encrypt':True})
    assert env == {'CZERO_MODULE_ID':'czero7','CZERO_BASE_PATH':'',
                   'CZERO_HOST':'c0.example.test','CZERO_LETS_ENCRYPT':'true',
                   **{key:'' for key in ('CZERO_USER_DOMAIN','CZERO_IDP_UUID','CZERO_OWNER_USERNAME','CZERO_OWNER_LDAP_UUID')}}
    for key, value in env.items():
        monkeypatch.setenv(key,value)
    run_step(monkeypatch, 'get-configuration/20read', SimpleNamespace())
    config = json.loads(capsys.readouterr().out)
    from czero_retrieval_config import public, defaults
    assert config == {'host':'c0.example.test','lets_encrypt':True, 'retrieval':public(defaults()),
        'session_policy':{'absolute_seconds':28800,'idle_seconds':3600}, 'cimd_enabled':False,
        **{key:'' for key in ('user_domain','idp','owner','owner_ldap_uuid')}}
    schema = json.loads((ACTIONS / 'get-configuration/validate-output.json').read_text())
    Draft7Validator(schema).validate(config)


def test_unconfigured_defaults_are_machine_readable(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv('AGENT_STATE_DIR', str(tmp_path))
    monkeypatch.setenv('AGENT_INSTALL_DIR', str(ROOT / 'imageroot'))
    monkeypatch.delenv('CZERO_HOST',raising=False)
    monkeypatch.delenv('CZERO_LETS_ENCRYPT',raising=False)
    run_step(monkeypatch,'get-configuration/20read',SimpleNamespace())
    from czero_retrieval_config import public, defaults
    assert json.loads(capsys.readouterr().out) == {'host':'','lets_encrypt':False, 'retrieval':public(defaults()),
        'session_policy':{'absolute_seconds':28800,'idle_seconds':3600}, 'cimd_enabled':False,
        **{key:'' for key in ('user_domain','idp','owner','owner_ldap_uuid')}}


@pytest.mark.parametrize('base_path', [None, '', '/czero/czero7'])
def test_upgrade_preserves_root_or_initializes_legacy_path(monkeypatch, capsys, base_path):
    env = {}
    monkeypatch.delenv('CZERO_MODULE_ID',raising=False)
    monkeypatch.delenv('CZERO_BASE_PATH',raising=False)
    if base_path is not None:
        monkeypatch.setenv('CZERO_BASE_PATH',base_path)
    monkeypatch.setenv('MODULE_ID','czero7')
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(mset_env=env.update))
    runpy.run_path(str(ROOT / 'imageroot/update-module.d/20instance-id'))
    assert env == {'CZERO_MODULE_ID':'czero7', **({'CZERO_BASE_PATH':'/czero/czero7'} if base_path is None else {})}
    assert capsys.readouterr().out == ''


def test_readiness_retries_then_accepts_only_health_contract(monkeypatch, capsys):
    from contextlib import contextmanager
    import urllib.request
    import time
    responses = [OSError('starting'), {'status':'starting','service':'czero'},
                 {'status':'ok','service':'czero'}]
    progress = []
    @contextmanager
    def open_url(url, timeout):
        assert url == 'http://127.0.0.1:20007/api/v1/health'
        assert timeout == 2
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        yield StringIO(json.dumps(response))
    monkeypatch.setattr(urllib.request,'urlopen',open_url)
    monkeypatch.setattr(time,'sleep',lambda seconds: None)
    run_step(monkeypatch,'configure-module/90wait-ready',SimpleNamespace(set_progress=progress.append))
    assert not responses
    assert progress[-1] == 100
    assert capsys.readouterr().out == ''


def test_unready_service_fails_configuration_without_success_output(monkeypatch, capsys):
    import urllib.request
    import time
    calls = []
    def fail(url, timeout):
        calls.append(timeout)
        raise OSError('unavailable')
    monkeypatch.setattr(urllib.request,'urlopen',fail)
    monkeypatch.setattr(time,'sleep',lambda seconds: None)
    with pytest.raises(SystemExit) as error:
        run_step(monkeypatch,'configure-module/90wait-ready',SimpleNamespace(set_progress=lambda n: None))
    assert error.value.code == 1
    assert len(calls) == 15
    output = capsys.readouterr()
    assert output.out == ''
    assert 'did not become ready' in output.err
