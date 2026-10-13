# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Check the assembled application filesystem, including dependency wheels."""

import importlib.util
import sys
from pathlib import Path


def audit(root: Path) -> None:
    if not root.is_dir():
        raise SystemExit(f"Runtime directory is missing: {root}")
    forbidden_names = {
        ".agents", ".codex", ".git", ".github", "tests", "testing",
        "AGENTS.md", "PLAN.md", "SKILL.md", "pyproject.toml", "uv.lock",
    }
    unexpected = sorted(str(p) for p in root.rglob("*") if p.name in forbidden_names
                        or (p.name == "templates" and p.parent.name == "alembic")
                        or (p.name == "alembic" and p.parent.name == "bin"))
    tools = [name for name in ("pip", "setuptools", "uv", "pytest", "robot")
             if importlib.util.find_spec(name) is not None]
    if unexpected or tools:
        raise SystemExit(f"Development files: {unexpected}; build/test tools: {tools}")
    print("Application runtime contains no development files or build/test tools")


if __name__ == "__main__":
    audit(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/opt/czero"))
