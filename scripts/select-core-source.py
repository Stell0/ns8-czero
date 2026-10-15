#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit build-only local Core override; released consumption is the default."""
import argparse
from pathlib import Path
import re
import tomllib


def select(project: Path, source: str) -> bool:
    if source not in {"released", "local"}:
        raise ValueError("Unknown Core source")
    original = project.read_text()
    config = tomllib.loads(original)
    core = config["tool"]["uv"]["sources"]["czero-core"]
    local = {"path": "../packages/czero-core", "editable": False}
    if source == "local" and core == local:
        return False
    if (not isinstance(core, dict) or set(core) != {"git", "tag", "subdirectory"}
            or not isinstance(core["git"], str)
            or not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", core["git"])
            or not isinstance(core["tag"], str)
            or not re.fullmatch(r"core-v[0-9]+\.[0-9]+\.[0-9]+", core["tag"])
            or core["subdirectory"] != "packages/czero-core"):
        raise ValueError("Released Core requires a pinned Git tag/subdirectory")
    if source == "released":
        return False
    if not (project.parent / "../packages/czero-core/pyproject.toml").is_file():
        raise ValueError("Local Core checkout is absent")
    lines = original.splitlines(keepends=True)
    section, positions = "", []
    for index, line in enumerate(lines):
        if line.strip().startswith("["):
            section = line.strip()
        if section == "[tool.uv.sources]" and re.match(r"^czero-core\s*=", line):
            positions.append(index)
    if len(positions) != 1:
        raise ValueError("Use one inline Core source declaration")
    lines[positions[0]] = 'czero-core = { path = "../packages/czero-core", editable = false }\n'
    updated = "".join(lines)
    if tomllib.loads(updated)["tool"]["uv"]["sources"]["czero-core"] != local:
        raise ValueError("Local source selection failed")
    project.write_text(updated)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source", choices=("released", "local"), default="released")
    args = parser.parse_args()
    try:
        changed = select(args.project, args.source)
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, "Core source selection failed; no automatic fallback is permitted.\n")
    print("Explicit local Core selected" if changed else "Declared Core source verified")
