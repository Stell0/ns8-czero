# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import runpy
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_route_is_owned_by_instance(monkeypatch):
    routes = []
    env = []
    monkeypatch.setitem(sys.modules, "agent", SimpleNamespace(set_route=routes.append, set_env=lambda *args: env.append(args)))
    monkeypatch.setenv("MODULE_ID", "czero7")
    monkeypatch.setenv("TCP_PORT", "20007")
    monkeypatch.setattr(sys, "stdin", StringIO("{}"))
    runpy.run_path(str(ROOT / "imageroot/actions/configure-module/20configure"))
    assert env == [("CZERO_MODULE_ID", "czero7")]
    assert routes == [{"instance": "czero7", "url": "http://127.0.0.1:20007",
                       "http2https": False, "lets_encrypt": False, "path": "/czero/czero7"}]


def test_malformed_input_cannot_configure_route(monkeypatch):
    routes = []
    monkeypatch.setitem(sys.modules, "agent", SimpleNamespace(set_route=routes.append))
    monkeypatch.setattr(sys, "stdin", StringIO("not JSON"))
    with pytest.raises(json.JSONDecodeError):
        runpy.run_path(str(ROOT / "imageroot/actions/configure-module/20configure"))
    assert routes == []


def test_configuration_is_machine_readable(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "agent", SimpleNamespace())
    runpy.run_path(str(ROOT / "imageroot/actions/get-configuration/20read"))
    assert json.loads(capsys.readouterr().out) == {}


def test_upgrade_from_missing_identity_keeps_stdout_clean(monkeypatch, capsys):
    env = []
    monkeypatch.delenv("CZERO_MODULE_ID", raising=False)
    monkeypatch.setenv("MODULE_ID", "czero7")
    monkeypatch.setitem(sys.modules, "agent", SimpleNamespace(set_env=lambda *args: env.append(args)))
    runpy.run_path(str(ROOT / "imageroot/update-module.d/20instance-id"))
    assert env == [("CZERO_MODULE_ID", "czero7")]
    assert capsys.readouterr().out == ""
