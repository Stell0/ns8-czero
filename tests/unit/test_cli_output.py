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
