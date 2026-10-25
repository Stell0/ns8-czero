# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "samples/ingestion/src"))
from github_vault.github_client import GitHub, GitHubError, BudgetExceeded
from github_vault.state import atomic, digest, safe_path
from github_vault.discover import human, repository
from github_vault.metrics import measure
from github_vault.c0_client import C0, C0Error
from github_vault.models import validate
from github_vault.scrape import fork_changes

F = json.loads((Path(__file__).parent / "fixtures/events.json").read_text())


class Response(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(json.dumps(data).encode())
        self.headers = headers or {}


class CoreTests(unittest.TestCase):
    def test_pages_resume(self):
        with tempfile.TemporaryDirectory() as directory, patch("github_vault.github_client.token", return_value=None):
            responses = [Response([{"id": 1}], {"Link": '<https://api.github.com/example?page=2>; rel="next"'}), Response([{"id": 2}])]
            api = GitHub(directory, {"max_requests": 10, "max_retries": 1, "max_wait_seconds": 1}, opener=lambda *a, **k: responses.pop(0))
            self.assertEqual([v["id"] for v in api.pages("/example")], [1, 2])
            self.assertEqual([v["id"] for v in api.pages("/example")], [1, 2])
            self.assertEqual(api.requests, 2)
            self.assertEqual(api.cached, 2)

    def test_retry_failure_budget(self):
        with tempfile.TemporaryDirectory() as directory, patch("github_vault.github_client.token", return_value=None):
            calls = []
            def opener(*a, **k):
                calls.append(1)
                if len(calls) == 1:
                    raise urllib.error.HTTPError("https://api.github.com/x", 503, "", {}, None)
                return Response({"ok": True})
            api = GitHub(directory, {"max_requests": 2, "max_retries": 1, "max_wait_seconds": 2}, opener=opener, sleeper=lambda _: None)
            self.assertTrue(api.get("/x")[0]["ok"])
            with self.assertRaises(BudgetExceeded):
                api.get("/different")

    def test_bots_sha_duplicates_and_unknown(self):
        date = "2025-01-01T00:00:00Z"
        def commit(sha, author):
            return {"sha": sha, "author": author, "html_url": f"https://github.com/org/repo/commit/{sha}", "commit": {"author": {"date": date}}}
        commits = [commit("a", F["human"]), commit("a", F["human"]), commit("b", F["bot"]), commit("c", None)]
        repo = {"repo_id": 100, "url": "https://github.com/org/repo", "owner": {"login": "org"}}
        people = {}
        rows, bots, unlinked = measure(repo, commits, [], [], [], F["window"], people)
        self.assertEqual(rows[0]["counts"]["commits"], 1)
        self.assertEqual(bots["commits"], 1)
        self.assertEqual(len(unlinked), 1)
        self.assertEqual(rows[0]["measurement"]["reviews"]["status"], "partial")
        self.assertIsNone(rows[0]["counts"]["reviews"])
        self.assertFalse(human(F["bot"]))

    def test_no_external_recursion(self):
        repo = {"repo_id": 100, "url": "https://github.com/org/repo", "owner": {"login": "org"}}
        people = {}
        rows, _, _ = measure(repo, [], [{"id": 3, "user": F["human"], "created_at": "2025-01-01T00:00:00Z", "html_url": "https://github.com/org/repo/pull/1"}], [], [], F["window"], people, False)
        self.assertEqual(people, {})
        self.assertEqual(rows, [])

    def test_rename_numeric_key(self):
        raw = {"id": 7, "full_name": "org/new", "html_url": "https://github.com/org/new", "owner": {"id": 8, "login": "org", "type": "Organization"}, "fork": False, "archived": True, "default_branch": "main", "stargazers_count": 0}
        first = repository(raw, raw["html_url"], ["org"])
        raw["full_name"] = "org/renamed"
        self.assertEqual(first["external_key"], repository(raw, raw["html_url"], ["org"])["external_key"])

    def test_safe_paths_hashes_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in ["../x", "/etc/passwd", "documents/../../x", "a\\b"]:
                with self.assertRaises(ValueError):
                    safe_path(directory, path)
            atomic(Path(directory) / "bytes", b"literal\r\n")
            self.assertEqual((Path(directory) / "bytes").read_bytes(), b"literal\r\n")
            self.assertEqual(digest(b"x"), digest(b"x"))
            with self.assertRaises(ValueError):
                validate(directory)

    def test_wrong_space_fails_before_transport(self):
        c = object.__new__(C0)
        c.space_id = "correct"
        c.operations = {"objects_create": {"read_only": False, "input_schema": {"properties": {"space_id": {}}}}}
        c.writes = 0
        with self.assertRaises(C0Error):
            c.call("objects_create", space_id="wrong", data={})
        self.assertEqual(c.writes, 0)

    def test_search_incomplete_is_failure(self):
        c = object.__new__(GitHub)
        c.get = lambda *args: ({"incomplete_results": True, "total_count": 0, "items": []}, None)
        with self.assertRaises(GitHubError):
            c.search("issues", "repo:a/b", **F["window"])

    def test_search_splits_ceiling(self):
        c = object.__new__(GitHub)
        queries = []
        def get(path, params=None):
            queries.append(params["q"])
            if len(queries) == 1:
                return {"total_count": 1001, "items": [], "incomplete_results": False}, None
            return {"total_count": 1, "items": [{"id": len(queries)}], "incomplete_results": False}, None
        c.get = get
        self.assertEqual(len(c.search("issues", "repo:a/b", **F["window"])), 2)
        self.assertEqual(len(queries), 3)

    def test_incomplete_search_is_not_a_completed_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory, patch("github_vault.github_client.token", return_value=None):
            responses = [Response({"incomplete_results": True, "total_count": 1, "items": []}), Response({"incomplete_results": False, "total_count": 0, "items": []})]
            api = GitHub(directory, {"max_requests": 5, "max_retries": 0, "max_wait_seconds": 1}, opener=lambda *a, **k: responses.pop(0))
            self.assertTrue(api.get("/search/issues", {"q": "repo:a/b"})[0]["incomplete_results"])
            self.assertFalse(api.get("/search/issues", {"q": "repo:a/b"})[0]["incomplete_results"])
            self.assertEqual(api.requests, 2)

    def test_committer_window_with_author_attribution(self):
        repo = {"repo_id": 1, "url": "https://github.com/a/b", "owner": {"login": "a"}}
        commit = {"sha": "a", "author": F["human"], "html_url": "https://github.com/a/b/commit/a", "commit": {"author": {"date": "2020-01-01T00:00:00Z"}, "committer": {"date": "2025-01-01T00:00:00Z"}}}
        rows, _, _ = measure(repo, [commit], [], [], [], F["window"], {})
        self.assertEqual(rows[0]["counts"]["commits"], 1)

    def test_fork_does_not_count_inherited_parent_commits(self):
        class API:
            def __init__(self):
                self.responses = [({"parent": {"full_name": "upstream/project", "default_branch": "main"}}, None), ({"sha": "a" * 40}, None), ({"commits": [{"sha": "unique"}], "total_commits": 1, "ahead_by": 1, "behind_by": 2, "html_url": "https://github.com/fork/project/compare/base...head"}, None)]
            def get(self, *args, **kwargs):
                return self.responses.pop(0)
        commits, proof = fork_changes(API(), {"full_name": "fork/project"}, "b" * 40, [{"sha": "inherited"}, {"sha": "unique"}])
        self.assertEqual(commits, [{"sha": "unique"}])
        self.assertEqual(proof["status"], "verified")

    def test_private_metadata_is_not_exported(self):
        with tempfile.TemporaryDirectory() as directory, patch("github_vault.github_client.token", return_value=None):
            api = GitHub(directory, {"max_requests": 5, "max_retries": 0, "max_wait_seconds": 1}, opener=lambda *a, **k: Response({"private": True, "secret_metadata": "must-not-be-exported"}))
            for _ in range(2):
                with self.assertRaises(GitHubError) as exc:
                    api.get("/repos/org/private")
                self.assertFalse(exc.exception.retryable)
            self.assertEqual(api.requests, 1)
            self.assertNotIn("must-not-be-exported", "".join(p.read_text() for p in Path(directory).glob('*.json')))


if __name__ == "__main__":
    unittest.main()
