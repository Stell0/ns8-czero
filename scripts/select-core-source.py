#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit build-only local Core override; released consumption is the default."""
import argparse
from pathlib import Path
import re
import subprocess
import tomllib
from urllib.parse import parse_qs, urlsplit, urlunsplit


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
    producer=tomllib.loads((project.parent/'../packages/czero-core/pyproject.toml').read_text())['project']['version']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',producer):raise ValueError('Invalid producer Core version')
    # The generated producer manifest uses an exact local version. The declared
    # released consumer range and frozen lock in Git remain untouched.
    updated,count=re.subn(r'([\"\'])czero-core[^\"\']*\1',lambda match:match[1]+'czero-core=='+producer+match[1],updated)
    if count!=1:raise ValueError('Use one Core dependency')
    if tomllib.loads(updated)["tool"]["uv"]["sources"]["czero-core"] != local:
        raise ValueError("Local source selection failed")
    project.write_text(updated)
    return True


def ci_source(project: Path, repository: str) -> str:
    """Use producer CI only for committed upstream Core development."""
    select(project, "released")
    if repository != "Stell0/ns8-czero":
        return "released"
    declared = tomllib.loads(project.read_text())["tool"]["uv"]["sources"]["czero-core"]
    packages = tomllib.loads(project.with_name("uv.lock").read_text()).get("package")
    if not isinstance(packages, list) or not all(isinstance(p, dict) for p in packages):
        raise ValueError("Invalid dependency lock")
    matches = [p for p in packages if p.get("name") == "czero-core"]
    if len(matches) != 1:
        raise ValueError("Use one locked Core package")
    package = matches[0]
    source = package.get("source")
    if not isinstance(source, dict) or set(source) != {"git"}:
        raise ValueError("Core lock requires one Git source")
    locked = source["git"]
    if not isinstance(locked, str):
        raise ValueError("Core lock requires an immutable Git source")
    uri = urlsplit(locked)
    repository_url = urlunsplit((uri.scheme, uri.netloc, uri.path, "", ""))
    if (repository_url.removesuffix(".git") != declared["git"].removesuffix(".git")
            or parse_qs(uri.query, keep_blank_values=True) != {
                "tag": [declared["tag"]], "subdirectory": [declared["subdirectory"]]}
            or declared["tag"] != "core-v" + str(package.get("version"))
            or not re.fullmatch(r"[0-9a-f]{40}", uri.fragment)):
        raise ValueError("Core lock does not match its declared release")
    # Compare package content, not versions: same-version edits are still producer work.
    trees = subprocess.check_output([
        "git", "-C", str(project.resolve().parent.parent), "rev-parse",
        "HEAD:packages/czero-core", uri.fragment + ":packages/czero-core",
    ], text=True).splitlines()
    if len(trees) != 2 or not all(re.fullmatch(r"[0-9a-f]{40}", tree) for tree in trees):
        raise ValueError("Core package tree is unavailable")
    return "released" if trees[0] == trees[1] else "local"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--source", choices=("released", "local"), default="released")
    mode.add_argument("--ci-repository", help="Select the reference CI build policy without editing files")
    args = parser.parse_args()
    try:
        if args.ci_repository is not None:
            print(ci_source(args.project, args.ci_repository))
            parser.exit()
        changed = select(args.project, args.source)
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError):
        parser.exit(1, "Core source selection failed; no automatic fallback is permitted.\n")
    print("Explicit local Core selected" if changed else "Declared Core source verified")
