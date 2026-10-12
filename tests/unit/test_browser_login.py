# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

from robot.libraries.BuiltIn import BuiltIn


ROOT = Path(__file__).resolve().parents[2]


def test_disposable_login_obeys_core_contract_and_hides_password(monkeypatch):
    commands, levels, fills = [], [], []

    def execute(command, **kwargs):
        commands.append(command)
        return "true", 0

    browser = SimpleNamespace(
        new_page=lambda url: None,
        fill_text=lambda field, value: fills.append((field, value)),
        click=lambda selector: None,
        wait_for_elements_state=lambda *args, **kwargs: None,
    )
    ssh = SimpleNamespace(execute_command=execute)

    def log_level(level):
        levels.append(level)
        return "INFO"

    monkeypatch.setattr(BuiltIn, "get_library_instance", lambda self, name: {
        "SSHLibrary": ssh, "Browser": browser
    }[name])
    monkeypatch.setattr(BuiltIn, "set_log_level", lambda self, level: log_level(level))
    def dispatch(self, name, *args):
        method = name.split(".")[1].lower().replace(" ", "_")
        if method == "wait_for_elements_state":
            assert args[1:] == ("visible", "timeout=30s")
        else:
            return getattr(browser, method)(*args)

    monkeypatch.setattr(BuiltIn, "run_keyword", dispatch)
    library = runpy.run_path(str(ROOT / "tests/CzeroBrowser.py"))["CzeroBrowser"]()
    library.login_to_disposable_cluster("disposable.invalid")
    request = json.loads(commands[0].split("--data '")[1][:-1])
    # Required fields of Core cluster/add-user's input schema.
    assert {"user", "password_hash", "set", "grant"} <= request.keys()
    assert request["grant"] == [{"role": "owner", "on": "*"}]
    password = fills[1][1]
    assert request["password_hash"] == hashlib.sha256(password.encode()).hexdigest()
    assert password not in commands[0]
    assert fills[0][1].startswith("czero-ci-")
    assert levels == ["NONE", "INFO"]
