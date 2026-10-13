# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace
import pytest

from robot.libraries.BuiltIn import BuiltIn


ROOT = Path(__file__).resolve().parents[2]


def test_disposable_login_obeys_core_contract_and_hides_password(monkeypatch):
    commands, levels, fills, requests, robot_calls = [], [], [], [], []

    def execute(command, **kwargs):
        commands.append(command)
        return "true", 0

    browser = SimpleNamespace(
        new_page=lambda url: None,
        fill_text=lambda field, value: fills.append((field, value)),
        click=lambda selector: None,
        wait_for_elements_state=lambda *args, **kwargs: None,
    )
    def upload(source, destination, **kwargs):
        assert Path(source).stat().st_mode & 0o777 == 0o600
        assert kwargs['mode'] == '0600'
        requests.append(json.loads(Path(source).read_text()))
    ssh = SimpleNamespace(execute_command=execute, put_file=upload)

    def log_level(level):
        levels.append(level)
        return "INFO"

    monkeypatch.setattr(BuiltIn, "get_library_instance", lambda self, name: {
        "SSHLibrary": ssh, "Browser": browser
    }[name])
    monkeypatch.setattr(BuiltIn, "set_log_level", lambda self, level: log_level(level))
    def dispatch(self, name, *args):
        robot_calls.append((name,args))
        method = name.split(".")[1].lower().replace(" ", "_")
        if method == "wait_for_elements_state":
            assert args[1:] == ("visible", "timeout=30s")
        else:
            return getattr(browser, method)(*args)

    monkeypatch.setattr(BuiltIn, "run_keyword", dispatch)
    library = runpy.run_path(str(ROOT / "tests/CzeroBrowser.py"))["CzeroBrowser"]()
    library.login_to_disposable_cluster("disposable.invalid")
    request = requests[0]
    # Required fields of Core cluster/add-user's input schema.
    assert {"user", "password_hash", "set", "grant"} <= request.keys()
    assert request["grant"] == [{"role": "owner", "on": "*"}]
    password = fills[1][1]
    assert request["password_hash"] == hashlib.sha256(password.encode()).hexdigest()
    assert password not in commands[0]
    assert request['password_hash'] not in '\n'.join(commands)
    assert all(password not in args for _, args in robot_calls)
    assert fills[0][1].startswith("czero-ci-")
    assert levels == ["NONE", "INFO"]


@pytest.mark.parametrize('exposed', [False, True])
def test_browser_privacy_assertion_detects_nested_keyword_secrets(monkeypatch, tmp_path, exposed):
    library = runpy.run_path(str(ROOT / 'tests/CzeroBrowser.py'))['CzeroBrowser']()
    library._password = 'synthetic-sensitive-value'
    output = tmp_path / 'output.xml'
    output.write_text('<arg>' + (library._password if exposed else 'public-value') + '</arg>')
    monkeypatch.setattr(BuiltIn, 'get_variable_value', lambda self, name: str(output))
    if exposed:
        with pytest.raises(AssertionError, match='password entered test output'):
            library.assert_disposable_browser_password_is_private()
    else:
        library.assert_disposable_browser_password_is_private()
