# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PARSER = runpy.run_path(str(ROOT / "tests/CzeroActions.py"))["CzeroActions"]()


@pytest.mark.parametrize("output", ["{'module_id': 'czero1'}", '{"module_id": "czero1"}'])
def test_native_and_json_installation_results(output):
    assert PARSER.installed_module_id(output) == "czero1"


@pytest.mark.parametrize("output", ["{}", "[]", "{'module_id': 'traefik1'}", "{'module_id': 1}"])
def test_missing_or_unrelated_module_id_is_rejected(output):
    with pytest.raises(AssertionError):
        PARSER.installed_module_id(output)


def test_cli_output_is_not_executable():
    with pytest.raises((ValueError, SyntaxError)):
        PARSER.installed_module_id("__import__('os').getcwd()")


def test_installed_candidates_use_explicit_source_without_runner_git(monkeypatch):
    import json
    import subprocess
    from robot.libraries.BuiltIn import BuiltIn
    source = 'a' * 40
    class Ssh:
        def execute_command(self, command, **kwargs):
            assert command.startswith('runagent -m czero1 python3 -c ')
            return json.dumps({'digest': 'sha256:'+'b'*64, 'revision': source}), 0
    monkeypatch.setattr(BuiltIn, 'get_library_instance', lambda *args: Ssh())
    logged = []
    monkeypatch.setattr(BuiltIn, 'log_to_console', lambda self, value: logged.append(value))
    monkeypatch.setattr(subprocess, 'check_output', lambda *args, **kwargs: pytest.fail('Git is unavailable in Robot'))
    PARSER.verify_installed_candidate_images('czero1', source)
    assert json.loads(logged[0].split(': ', 1)[1])['source'] == source
    with pytest.raises(AssertionError, match='source mismatch'):
        PARSER.verify_installed_candidate_images('czero1', 'c'*40)


@pytest.mark.parametrize('source', ['', 'main', 'a'*39, 'a'*40+';echo bad'])
def test_installed_candidate_source_must_be_an_immutable_commit(source):
    with pytest.raises(AssertionError, match='Invalid expected source'):
        PARSER.verify_installed_candidate_images('czero1', source)
