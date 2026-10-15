# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Inspect the actual independently built wheel's required license bytes."""
import os
from pathlib import Path
import subprocess
import tomllib
import zipfile

ROOT = Path(__file__).parents[2]

def test_built_core_wheel_contains_declared_license(tmp_path):
    environment = {**os.environ, "UV_CACHE_DIR": str(tmp_path / "cache")}
    result = subprocess.run(["uv", "build", "--no-sources", "--wheel", str(ROOT / "packages/czero-core"), "--out-dir", str(tmp_path / "dist")], capture_output=True, timeout=180, env=environment)
    assert result.returncode == 0, "Core wheel build failed"
    version = tomllib.loads((ROOT / "packages/czero-core/pyproject.toml").read_text())["project"]["version"]
    with zipfile.ZipFile(next((tmp_path / "dist").glob("*.whl"))) as archive:
        prefix = f"czero_core-{version}.dist-info/"
        assert archive.read(prefix + "licenses/LICENSE") == (ROOT / "LICENSE").read_bytes()
        assert b"License-Expression: GPL-3.0-or-later" in archive.read(prefix + "METADATA")
