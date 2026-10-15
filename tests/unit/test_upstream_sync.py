"""Exercise real independent Git histories, not mocked merge decisions."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

SPEC = importlib.util.spec_from_file_location("upstream_sync", Path(__file__).parents[2] / "scripts/sync-upstream.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)
TRUSTED = "https://github.com/Stell0/ns8-czero.git"


def git(root, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    return subprocess.check_output(["git", "-C", str(root), *args], env=env, stderr=subprocess.DEVNULL).decode().strip()


def commit(root, message):
    git(root, "add", "--all")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def history(tmp_path):
    upstream, fork = tmp_path / "upstream", tmp_path / "fork"
    upstream.mkdir()
    fork.mkdir()
    git(upstream, "init", "-b", "main")
    git(upstream, "remote", "add", "origin", TRUSTED)
    paths = ["managed.txt", "custom.txt", "deleted.txt", "executable.sh", "added.txt"]
    entries = []
    for path in paths[:-1]:
        (upstream / path).write_text("original\n")
        (fork / path).write_text("original\n")
    base = commit(upstream, "baseline")
    for path in paths:
        data = (upstream / path).read_bytes() if (upstream / path).exists() else None
        entries.append({"path": path, "mode": "100644" if data else None,
                        "sha256": hashlib.sha256(data).hexdigest() if data else None})
    manifest = {"format": 1, "upstream": TRUSTED, "revision": base, "files": entries}
    (fork / SYNC.MANIFEST).write_text(json.dumps(manifest))
    (upstream / "managed.txt").write_text("updated\n")
    (upstream / "custom.txt").write_text("upstream behavior\n")
    (upstream / "deleted.txt").unlink()
    (upstream / "executable.sh").chmod(0o755)
    (upstream / "added.txt").write_text("new\n")
    (fork / "custom.txt").write_text("private customization\n")
    target = commit(upstream, "change managed infrastructure")
    return upstream, fork, base, target


def test_apply_preserves_customization_and_is_idempotent(history):
    upstream, fork, base, target = history
    before = (fork / "managed.txt").read_bytes()
    preview = SYNC.synchronize(fork, upstream, target)
    assert preview["changed"] and (fork / "managed.txt").read_bytes() == before
    result = SYNC.synchronize(fork, upstream, target, apply=True)
    assert {c["action"] for c in result["files"]} == {"apply", "review"}
    assert (fork / "managed.txt").read_text() == "updated\n"
    assert (fork / "custom.txt").read_text() == "private customization\n"
    assert not (fork / "deleted.txt").exists()
    assert (fork / "executable.sh").stat().st_mode & 0o111
    assert (fork / "added.txt").read_text() == "new\n"
    report = (fork / SYNC.REPORT).read_text()
    assert "private customization" not in report
    assert f"git diff {base} {target} -- custom.txt" in report
    manifest = json.loads((fork / SYNC.MANIFEST).read_text())
    assert next(e for e in manifest["files"] if e["path"] == "custom.txt")["needs_review"]
    snapshot = {p.relative_to(fork): p.read_bytes() for p in fork.rglob("*") if p.is_file()}
    assert SYNC.synchronize(fork, upstream, target, apply=True) == {"changed": False, "files": []}
    assert snapshot == {p.relative_to(fork): p.read_bytes() for p in fork.rglob("*") if p.is_file()}


def test_already_current_advances_baseline_without_conflict(history):
    upstream, fork, _, target = history
    (fork / "managed.txt").write_bytes((upstream / "managed.txt").read_bytes())
    result = SYNC.synchronize(fork, upstream, target, apply=True)
    assert {e["path"]: e["action"] for e in result["files"]}["managed.txt"] == "already-current"


@pytest.mark.parametrize("bad", ["../escape", "/absolute", ".git/config", "a/../../b", "a//b", "a/./b", ".", "a\nb", SYNC.REPORT, SYNC.MANIFEST])
def test_unsafe_paths_reject_before_any_write(history, bad):
    upstream, fork, _, target = history
    manifest_path = fork / SYNC.MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][-1]["path"] = bad
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        SYNC.synchronize(fork, upstream, target, apply=True)
    assert (fork / "managed.txt").read_text() == "original\n"
    assert not (fork / SYNC.REPORT).exists()


@pytest.mark.parametrize("kind", ["file", "report", "parent", "baseline", "duplicate", "remote", "backward", "upstream-symlink"])
def test_corrupt_or_unsafe_input_fails_atomically(history, kind):
    upstream, fork, base, target = history
    manifest_path = fork / SYNC.MANIFEST
    manifest = json.loads(manifest_path.read_text())
    if kind == "file":
        (fork / "custom.txt").unlink()
        (fork / "custom.txt").symlink_to(upstream / "custom.txt")
    elif kind == "report":
        (fork / ".c0").mkdir()
        (fork / SYNC.REPORT).symlink_to(upstream / "custom.txt")
    elif kind == "parent":
        (fork / ".c0").symlink_to(upstream, target_is_directory=True)
    elif kind == "baseline":
        manifest["files"][-1]["sha256"] = "0" * 64
    elif kind == "duplicate":
        manifest["files"].append(manifest["files"][0])
    elif kind == "remote":
        git(upstream, "remote", "set-url", "origin", "https://github.com/other/untrusted.git")
    elif kind == "backward":
        manifest["revision"] = target
        target = base
    elif kind == "upstream-symlink":
        (upstream / "custom.txt").unlink()
        (upstream / "custom.txt").symlink_to("managed.txt")
        target = commit(upstream, "unsupported symlink")
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        SYNC.synchronize(fork, upstream, target, apply=True)
    assert (fork / "managed.txt").read_text() == "original\n"


def test_unmanaged_change_does_not_churn_manifest(history):
    upstream, fork, _, target = history
    SYNC.synchronize(fork, upstream, target, apply=True)
    manifest = (fork / SYNC.MANIFEST).read_bytes()
    (upstream / "app-only.txt").write_text("outside scope")
    later = commit(upstream, "application customization")
    assert not SYNC.synchronize(fork, upstream, later, apply=True)["changed"]
    assert (fork / SYNC.MANIFEST).read_bytes() == manifest
    assert not (fork / "app-only.txt").exists()


@pytest.mark.parametrize("path", [".c0", ".c0/UPSTREAM_UPDATE.md/child", "c0-upstream.json/child"])
def test_reserved_parent_and_descendant_paths(path):
    with pytest.raises(ValueError):
        SYNC.safe_path(path)


def test_customized_deletion_preserves_local_file(history):
    upstream, fork, _, target = history
    (fork / "deleted.txt").write_text("customized retention\n")
    SYNC.synchronize(fork, upstream, target, apply=True)
    assert (fork / "deleted.txt").read_text() == "customized retention\n"
    assert "`deleted.txt`: review" in (fork / SYNC.REPORT).read_text()


def test_local_mode_customization_is_not_silently_overwritten(history):
    upstream, fork, _, target = history
    (fork / "managed.txt").chmod(0o755)
    SYNC.synchronize(fork, upstream, target, apply=True)
    assert (fork / "managed.txt").read_text() == "original\n"
    assert (fork / "managed.txt").stat().st_mode & 0o111
    assert "`managed.txt`: review" in (fork / SYNC.REPORT).read_text()
