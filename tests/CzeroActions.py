# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parse the native add-module command's output without evaluating code."""
import ast
import json

from robot.api.deco import keyword


class CzeroActions:
    @keyword
    def installed_module_id(self, output):
        # Core add-module prints result['output'] as a Python dict. api-cli
        # emits JSON; accept either representation for runner compatibility.
        try:
            result = json.loads(output)
        except json.JSONDecodeError:
            result = ast.literal_eval(output)
        if not isinstance(result, dict):
            raise AssertionError("Installation result must be a dictionary")
        module_id = result.get("module_id")
        if not isinstance(module_id, str) or not module_id.startswith("czero"):
            raise AssertionError("Installation did not return a Czero module id")
        return module_id
