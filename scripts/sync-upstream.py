#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Review explicit upstream Git blobs; never execute upstream code or merge local edits."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

MANIFEST = "c0-upstream.json"
REPORT = ".c0/UPSTREAM_UPDATE.md"
SHA = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?")


def git(repository: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repository), *args], stderr=subprocess.DEVNULL,
        env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"},
    )


def safe_path(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.\-/]+", value):
        raise ValueError("Invalid managed path")
    parts = PurePosixPath(value).parts
    if not parts or any(p in {".", "..", ".git"} for p in parts) or str(PurePosixPath(value)) != value:
        raise ValueError("Invalid managed path")
    if value.startswith("/") or any(value == reserved or value.startswith(reserved + "/") or reserved.startswith(value + "/") for reserved in (MANIFEST, REPORT)):
        raise ValueError("Reserved managed path")
    return value


def local_blob(root: Path, path: str) -> tuple[str | None, bytes | None]:
    target = root
    parts = PurePosixPath(path).parts
    for index, part in enumerate(parts):
        target /= part
        if target.is_symlink():
            raise ValueError("Symlinks are not managed")
        if index < len(parts) - 1 and target.exists() and not target.is_dir():
            raise ValueError("Managed parent is not a directory")
    if not target.exists():
        return None, None
    if not target.is_file():
        raise ValueError("Managed path is not a file")
    return ("100755" if target.stat().st_mode & 0o111 else "100644", target.read_bytes())


def upstream_blob(repository: Path, revision: str, path: str) -> tuple[str | None, bytes | None]:
    entry = git(repository, "ls-tree", "-z", revision, "--", path)
    if not entry:
        return None, None
    metadata, actual_path = entry.rstrip(b"\0").split(b"\t", 1)
    mode, kind, oid = metadata.decode().split()
    if actual_path.decode() != path or mode not in {"100644", "100755"} or kind != "blob":
        raise ValueError("Upstream managed path is not a regular file")
    return mode, git(repository, "cat-file", "blob", oid)


def identity(blob: tuple[str | None, bytes | None]) -> dict:
    mode, data = blob
    return {"mode": mode, "sha256": hashlib.sha256(data).hexdigest() if data is not None else None}


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".c0-sync-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def synchronize(root: Path, upstream: Path, revision: str, *, apply: bool = False) -> dict:
    root, upstream = root.resolve(), upstream.resolve()
    manifest_path = root / MANIFEST
    local_blob(root, MANIFEST)
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    if set(manifest) != {"format", "upstream", "revision", "files"} or manifest["format"] != 1:
        raise ValueError("Unsupported upstream manifest")
    if not isinstance(manifest["upstream"], str) or not REPOSITORY.fullmatch(manifest["upstream"]):
        raise ValueError("Invalid upstream repository")
    base = manifest["revision"]
    if not isinstance(base, str) or not SHA.fullmatch(base) or not SHA.fullmatch(revision):
        raise ValueError("Use full immutable Git revisions")
    remote = git(upstream, "remote", "get-url", "origin").decode().strip()
    if remote.removesuffix(".git") != manifest["upstream"].removesuffix(".git"):
        raise ValueError("Upstream checkout does not match trusted repository")
    git(upstream, "merge-base", "--is-ancestor", base, revision)
    if not isinstance(manifest["files"], list) or not 1 <= len(manifest["files"]) <= 256:
        raise ValueError("Invalid managed file list")
    # Validate every baseline and destination before allowing any writes.
    paths = [safe_path(entry.get("path")) for entry in manifest["files"] if isinstance(entry, dict)]
    if any(a != b and b.startswith(a + "/") for a in paths for b in paths):
        raise ValueError("Managed paths overlap")
    seen, changes, updated_entries = set(), [], []
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or set(entry) - {"path", "mode", "sha256", "needs_review", "review_from"}:
            raise ValueError("Invalid managed file entry")
        path = safe_path(entry.get("path"))
        if path in seen:
            raise ValueError("Duplicate managed path")
        seen.add(path)
        before = upstream_blob(upstream, base, path)
        if identity(before) != {k: entry.get(k) for k in ("mode", "sha256")}:
            raise ValueError("Managed baseline does not match upstream")
        current, after = local_blob(root, path), upstream_blob(upstream, revision, path)
        updated = {"path": path, **identity(after)}
        if entry.get("needs_review") is True:
            review_from = entry.get("review_from")
            if not isinstance(review_from, str) or not SHA.fullmatch(review_from):
                raise ValueError("Unresolved review requires its original baseline")
            git(upstream, "merge-base", "--is-ancestor", review_from, base)
            updated.update(needs_review=True, review_from=review_from)
        if before != after:
            action = "apply" if current == before else "already-current" if current == after else "review"
            changes.append({"path": path, "action": action, "before": before, "current": current, "after": after})
            if action == "review":
                updated.update(needs_review=True, review_from=updated.get("review_from", base))
            else:
                updated.pop("needs_review", None)
                updated.pop("review_from", None)
        updated_entries.append(updated)
    if not changes:
        return {"changed": False, "files": []}
    # Refuse an existing report symlink or parent symlink even in review-only mode.
    local_blob(root, REPORT)
    lines = ["# Upstream update review", "", f"Upstream: {manifest['upstream']}", "",
             f"Baseline: `{base}`", f"Target: `{revision}`", "",
             "Only registered files are considered. Review tests before merging.", ""]
    report_entries = [{"path": c["path"], "action": c["action"]} for c in changes]
    reported = {c["path"] for c in changes}
    report_entries += [{"path": e["path"], "action": "review"} for e in updated_entries
                       if e.get("needs_review") and e["path"] not in reported]
    identities = {entry["path"]: entry for entry in updated_entries}
    for change in report_entries:
        path, action = change["path"], change["action"]
        comparison_base = identities[path].get("review_from", base)
        lines.extend([f"## `{path}`: {action}", ""])
        if action == "review":
            lines.extend(["Your customized file was preserved. Compare the upstream change and port the relevant behavior manually.",
                          "After testing, remove this file's needs_review and review_from markers; do not replace application customizations blindly.", ""])
        lines.extend(["Inspect the upstream change in a trusted upstream checkout:", "", "```sh",
                      f"git diff {comparison_base} {revision} -- {path}", "```", ""])
    report = "\n".join(lines).encode()
    if apply:
        if manifest_path.read_bytes() != original or any(local_blob(root, c["path"]) != c["current"] for c in changes):
            raise ValueError("Working files changed during preflight")
        for change in changes:
            if change["action"] != "apply":
                continue
            mode, data = change["after"]
            destination = root / change["path"]
            if data is None:
                destination.unlink(missing_ok=True)
            else:
                atomic_write(destination, data, 0o755 if mode == "100755" else 0o644)
        manifest.update(revision=revision, files=updated_entries)
        atomic_write(root / REPORT, report)
        atomic_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode())
    return {"changed": True, "files": [{k: c[k] for k in ("path", "action")} for c in changes]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--upstream-dir", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = synchronize(args.root, args.upstream_dir, args.revision, apply=args.apply)
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError):
        parser.exit(1, "Upstream sync failed preflight; inspect the manifest and trusted checkout.\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
