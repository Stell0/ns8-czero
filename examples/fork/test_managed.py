"""Exercise an original, isolated customized-file upgrade without Core installed."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("sync", Path(__file__).resolve().parents[1] / "scripts/sync-upstream.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class ManagedUpgrade(unittest.TestCase):
    def test_update_preserves_customizations_and_unresolved_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream, fork = root / "upstream", root / "fork"
            upstream.mkdir(); fork.mkdir()
            env = {**os.environ, "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                   "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
            def git(*args):
                return subprocess.check_output(["git", "-C", str(upstream), *args], env=env, stderr=subprocess.DEVNULL).decode().strip()
            def commit(message):
                git("add", "."); git("commit", "-m", message)
                return git("rev-parse", "HEAD")
            git("init", "-b", "main")
            git("remote", "add", "origin", "https://github.com/Stell0/ns8-czero.git")
            for path in (upstream, fork):
                (path / "build.txt").write_text("original build\n")
                (path / "settings.txt").write_text("original settings\n")
            baseline = commit("baseline")
            manifest = {"format": 1, "upstream": "https://github.com/Stell0/ns8-czero.git", "revision": baseline,
                        "files": [{"path": name, "mode": "100644", "sha256": hashlib.sha256((upstream/name).read_bytes()).hexdigest()}
                                  for name in ("build.txt", "settings.txt")]}
            (fork / "c0-upstream.json").write_text(json.dumps(manifest))
            (fork / "settings.txt").write_text("customer settings\n")
            (upstream / "build.txt").write_text("verified build\n")
            (upstream / "settings.txt").write_text("upstream settings\n")
            target = commit("update")
            SYNC.synchronize(fork, upstream, target, apply=True)
            self.assertEqual((fork / "build.txt").read_text(), "verified build\n")
            self.assertEqual((fork / "settings.txt").read_text(), "customer settings\n")
            (upstream / "build.txt").write_text("another build\n")
            later = commit("another update")
            SYNC.synchronize(fork, upstream, later, apply=True)
            self.assertIn(f"git diff {baseline} {later} -- settings.txt", (fork / SYNC.REPORT).read_text())
            self.assertFalse(SYNC.synchronize(fork, upstream, later, apply=True)["changed"])
