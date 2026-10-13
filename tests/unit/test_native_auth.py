# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
from io import StringIO
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROVIDER_UUID = "00000000-0000-0000-0000-000000000002"
OWNER_UUID = "00000000-0000-0000-0000-000000000001"


def native(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MODULE_ID", "czero7")
    for key in ("CZERO_IDP_UUID", "CZERO_USER_DOMAIN", "CZERO_OWNER_USERNAME", "CZERO_OWNER_LDAP_UUID"):
        monkeypatch.delenv(key, raising=False)
    @contextmanager
    def safe_open(path, mode="w"):
        with open(path, mode) as output:
            yield output
    calls = []
    def tasks(*args, **kwargs):
        calls.append((args, kwargs))
        return {"exit_code": 0, "output": {"client_id": "czero7", "client_secret": "sensitive-client-value",
            "issuer": "https://idp.example.test/realms/users.example.test", "realm": "users.example.test"}}
    def write_envfile(path, values):
        Path(path).write_text("".join(key + "=" + value + "\n" for key, value in values.items()))
    agent = SimpleNamespace(safe_open=safe_open, write_envfile=write_envfile,
        redis_connect=lambda **kw: object(), set_status=lambda value: None,
        list_service_providers=lambda *args, **kw: [{"module_id": "idp1", "module_uuid": PROVIDER_UUID,
            "host": "idp.example.test", "issuer_url_prefix": "https://idp.example.test/realms/"}],
        tasks=SimpleNamespace(run=tasks))
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "agent.tasks", agent.tasks)
    monkeypatch.setitem(sys.modules, "agent.ldapproxy", SimpleNamespace(Ldapproxy=lambda: SimpleNamespace(
        get_domain=lambda value: {"schema": "rfc2307"} if value == "users.example.test" else None)))
    monkeypatch.setitem(sys.modules, "agent.ldapclient", SimpleNamespace(Ldapclient=SimpleNamespace(
        factory=lambda **kw: SimpleNamespace(get_user_entry=lambda user, lextra_attributes: {
            "attributes": {"entryUUID": [OWNER_UUID]}}))))
    return agent, calls


def prepare(monkeypatch, data):
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(data)))
    runpy.run_path(str(ROOT / "imageroot/actions/configure-module/15validate-auth"))


def test_native_owner_resolution_stages_only_public_config(monkeypatch, tmp_path, capsys):
    native(monkeypatch, tmp_path)
    prepare(monkeypatch, {"host": "c0.example.test", "idp": PROVIDER_UUID,
                         "user_domain": "users.example.test", "owner": "owner"})
    staged = json.loads((tmp_path / "auth-pending.json").read_text())
    assert staged["owner_key"] == OWNER_UUID
    assert staged["provider_id"] == "idp1"
    assert "secret" not in json.dumps(staged)
    assert capsys.readouterr().out == ""


def test_partial_identity_configuration_fails_before_binding(monkeypatch, tmp_path, capsys):
    native(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as error:
        prepare(monkeypatch, {"host": "c0.example.test", "user_domain": "users.example.test"})
    assert error.value.code == 2
    assert not (tmp_path / "auth-pending.json").exists()
    assert json.loads(capsys.readouterr().out)[0]["error"] == "identity_configuration_incomplete"


def test_registered_client_uses_exact_uris_audience_and_private_file(monkeypatch, tmp_path, capsys):
    agent, calls = native(monkeypatch, tmp_path)
    prepare(monkeypatch, {"host": "c0.example.test", "idp": PROVIDER_UUID,
                         "user_domain": "users.example.test", "owner": "owner"})
    runpy.run_path(str(ROOT / "imageroot/actions/configure-module/30register-client"))
    request = calls[0][1]["data"]
    assert request["redirect_uris"] == ["https://c0.example.test/auth/callback"]
    assert request["post_logout_redirect_uris"] == ["https://c0.example.test/"]
    assert request["audience"] == ["czero7"]
    assert "module_id" not in request
    private = tmp_path / "auth.env"
    assert private.stat().st_mode & 0o777 == 0o600
    assert "CZERO_OIDC_CLIENT_SECRET=sensitive-client-value" in private.read_text()
    output = capsys.readouterr()
    assert output.out == "" and "sensitive" not in output.err


def test_registration_failure_does_not_replace_existing_secret(monkeypatch, tmp_path, capsys):
    agent, _ = native(monkeypatch, tmp_path)
    prepare(monkeypatch, {"host": "c0.example.test", "idp": PROVIDER_UUID,
                         "user_domain": "users.example.test", "owner": "owner"})
    private = tmp_path / "auth.env"
    private.write_text("previous-private-file")
    agent.tasks.run = lambda *a, **kw: {"exit_code": 1, "output": "sensitive-failure-result"}
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(ROOT / "imageroot/actions/configure-module/30register-client"))
    assert error.value.code == 1
    assert private.read_text() == "previous-private-file"
    assert "sensitive" not in capsys.readouterr().err


def test_owner_key_is_preserved_for_unchanged_name_and_domain(monkeypatch, tmp_path):
    native(monkeypatch, tmp_path)
    monkeypatch.setenv('CZERO_USER_DOMAIN','users.example.test')
    monkeypatch.setenv('CZERO_OWNER_USERNAME','owner')
    monkeypatch.setenv('CZERO_OWNER_LDAP_UUID',OWNER_UUID)
    monkeypatch.setenv('CZERO_IDP_UUID',PROVIDER_UUID)
    sys.modules['agent.ldapclient'].Ldapclient.factory = lambda **kw: pytest.fail('Do not reassign an unchanged owner name')
    prepare(monkeypatch, {'host':'c0.example.test'})
    assert json.loads((tmp_path/'auth-pending.json').read_text())['owner_key'] == OWNER_UUID


@pytest.mark.parametrize('script', ['actions/restore-module/60register-identity',
                                   'update-module.d/50auth-state'])
def test_identity_reconciliation_uses_sdk_popen_stdin(monkeypatch, tmp_path, script):
    monkeypatch.setenv('AGENT_STATE_DIR', str(tmp_path))
    monkeypatch.setenv('AGENT_INSTALL_DIR', '/test/module')
    monkeypatch.setenv('CZERO_HOST', 'c0.example.test')
    monkeypatch.setenv('CZERO_USER_DOMAIN', 'users.example.test')
    calls = []
    # SDK run_helper forwards keyword arguments to Popen, not subprocess.run.
    def run_helper(path, *, stdin=None, text=False):
        calls.append((path, json.load(stdin) if stdin else None))
        return SimpleNamespace(check_returncode=lambda: None)
    monkeypatch.setitem(sys.modules, 'agent', SimpleNamespace(run_helper=run_helper))
    runpy.run_path(str(ROOT / 'imageroot' / script))
    assert calls[1][1] == {'host': 'c0.example.test'}
    assert [Path(call[0]).name for call in calls] == [
        'czero-create-auth-state', '15validate-auth', '25bind-user-domain', '30register-client']


def test_native_connectivity_action_uses_existing_app_environment(monkeypatch):
    calls=[]
    def run_helper(*command, **options):
        calls.append(command)
        assert options == {"stdout":sys.stdout,"stderr":sys.stderr}
        return SimpleNamespace(check_returncode=lambda:None)
    monkeypatch.setitem(sys.modules,"agent",SimpleNamespace(run_helper=run_helper))
    runpy.run_path(str(ROOT/'imageroot/actions/get-authentication-status/20check'))
    assert calls==[('podman','exec','czero','/opt/czero/.venv/bin/python','-m','czero_app.auth_check')]
