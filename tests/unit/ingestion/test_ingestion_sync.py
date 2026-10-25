# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "samples/ingestion/src"))
from github_vault.models import validate, KINDS, TYPES
from github_vault.state import atomic, digest, encoded
from github_vault.sync import Updater, sync
from github_vault.c0_client import C0Error

W = {"since": "2024-10-25T00:00:00Z", "until": "2026-10-25T23:59:59Z"}


def fixture(root):
    doc_path = "README.md"
    body = b"# Example\r\nDistinctive original documentation phrase.\r\n"
    sha = "a" * 40
    repo = {"external_key": "repo:7", "repo_id": 7, "url": "https://github.com/org/project", "provenance": ["https://github.com/org/project"], "coverage": "partial"}
    doc = {"external_key": f"document:7:{digest(doc_path)[:24]}", "repo_id": 7, "url": f"https://github.com/org/project/blob/{sha}/{doc_path}", "provenance": ["https://github.com/org/project"], "coverage": "verified", "path": doc_path, "commit_sha": sha, "sha256": digest(body), "size_bytes": len(body), "content_path": "documents/7/readme.txt", "license": None, "retrieved_at": "2026-10-25T00:00:00Z"}
    records = {"people": [], "repositories": [repo], "contributions": [], "documents": [doc]}
    atomic(root / doc["content_path"], body)
    files = {}
    for kind in KINDS:
        data = b"".join(encoded(r) + b"\n" for r in records[kind])
        atomic(root / (kind + ".jsonl"), data)
        files[kind + ".jsonl"] = digest(data)
    manifest = {"schema_version": 1, "snapshot_id": root.name, "completeness": "partial", "window": W, "files": files, "counts": {k: len(v) for k, v in records.items()}, "scope": {"incremental": False}}
    atomic(root / "manifest.json", manifest)
    return manifest, records


class FakeC0:
    def __init__(self):
        self.space_id = "space"
        self.objects = {}
        self.relations = []
        self.writes = 0
        self.bad_readback = False

    def call(self, name, **args):
        if name == "objects_batch":
            rows = []
            for op in args["data"]["operations"]:
                if op["operation"] == "create":
                    rows.append(self.call("objects_create", data={"type_name": op["type_name"], "data": op["data"]}))
                else:
                    rows.append(self.call("objects_update", object_id=op["id"], data={"data": op["data"], "expected_revision": op["expected_revision"]}))
            return {"results": rows}
        if name == "objects_create":
            self.writes += 1
            row = {"id": str(len(self.objects) + 1), "revision": 1, **args["data"]}
            self.objects[row["id"]] = row
            return copy.deepcopy(row)
        if name == "objects_update":
            self.writes += 1
            row = self.objects[args["object_id"]]
            if row["revision"] != args["data"]["expected_revision"]:
                raise C0Error("conflict")
            row.update(data=args["data"]["data"], revision=row["revision"] + 1)
            return copy.deepcopy(row)
        if name == "objects_get":
            row = copy.deepcopy(self.objects[args["object_id"]])
            if self.bad_readback:
                row["data"] = {}
            return row
        if name == "object_relations_create":
            self.writes += 1
            row = {"id": str(len(self.relations) + 1), **args["data"]}
            self.relations.append(row)
            return row
        raise C0Error("mock C0 failure: " + name)

    def read_many(self, calls):
        return [self.call(name, **arguments) for name, arguments in calls]

    def listing(self, name, field, **args):
        if name == "objects_list":
            return [copy.deepcopy(v) for v in self.objects.values() if v["type_name"] == args["type_name"]]
        if name == "object_relations_list":
            return [r for r in self.relations if args["object_id"] in (r["source_id"], r["target_id"])]
        raise C0Error("mock C0 failure")


class SnapshotTests(unittest.TestCase):
    def test_valid_partial_and_verbatim_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "snapshot"
            fixture(root)
            m, r = validate(root)
            self.assertEqual(m["completeness"], "partial")
            self.assertEqual(len(r["documents"]), 1)

    def test_hash_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "snapshot"
            _, r = fixture(root)
            (root / r["documents"][0]["content_path"]).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash/size"):
                validate(root)

    def mutate_jsonl(self, kind, transform, error=Exception):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "snapshot"
            m, _ = fixture(root)
            path = root / (kind + ".jsonl")
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            data = transform(rows)
            atomic(path, data)
            m["files"][kind + ".jsonl"] = digest(data)
            atomic(root / "manifest.json", m)
            with self.assertRaises(error):
                validate(root)

    def test_malformed_jsonl(self):
        self.mutate_jsonl("repositories", lambda _: b"{invalid\n", ValueError)

    def test_duplicate_identity(self):
        self.mutate_jsonl("repositories", lambda rows: encoded(rows[0]) + b"\n" + encoded(rows[0]) + b"\n", ValueError)

    def test_absent_provenance(self):
        def change(rows):
            rows[0]["provenance"] = []
            return encoded(rows[0]) + b"\n"
        self.mutate_jsonl("repositories", change, ValueError)

    def test_path_traversal(self):
        def change(rows):
            rows[0]["content_path"] = "../../outside"
            return encoded(rows[0]) + b"\n"
        self.mutate_jsonl("documents", change, ValueError)

    def test_document_cannot_claim_another_repository(self):
        def change(rows):
            rows[0]["url"] = rows[0]["url"].replace("org/project", "unrelated/project")
            return encoded(rows[0]) + b"\n"
        self.mutate_jsonl("documents", change, ValueError)

    def test_invalid_input_before_connect(self):
        with tempfile.TemporaryDirectory() as d, patch("github_vault.sync.C0") as client:
            args = SimpleNamespace(space_name="Github projects", input=d)
            with self.assertRaises(ValueError):
                sync({"c0": {"space_name": "Github projects"}}, args)
            client.assert_not_called()


class UpdaterTests(unittest.TestCase):
    def test_native_batch_readback_and_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            c = FakeC0()
            records = {"repositories": [{"external_key": "repo:7", "repo_id": 7, "url": "https://github.com/org/project", "coverage": "partial"}]}
            for _ in range(2):
                u = Updater(c, Path(d) / "journal.json", "snapshot", {})
                u.load_objects()
                u.upsert_records(records)
            self.assertEqual(c.writes, 1)
            self.assertEqual(u.stats["objects_unchanged"], 1)
            self.assertEqual(len(u.journal), 1)

    def test_idempotent_objects_relations_and_journal(self):
        with tempfile.TemporaryDirectory() as d:
            c = FakeC0()
            r = {"external_key": "repo:7", "repo_id": 7, "url": "https://github.com/org/project", "coverage": "partial"}
            p = {"external_key": "person:8", "github_id": 8, "url": "https://github.com/alice", "coverage": "partial"}
            for _ in range(2):
                u = Updater(c, Path(d) / "journal.json", "snapshot", {})
                u.load_objects()
                u.object("repositories", r)
                u.object("people", p)
                u.relation("contributed_to", p["external_key"], r["external_key"])
            self.assertEqual(c.writes, 3)
            self.assertEqual(len(c.objects), 2)
            self.assertEqual(len(c.relations), 1)
            self.assertEqual(u.stats["objects_unchanged"], 2)
            self.assertEqual(len(u.journal), 3)
            self.assertTrue(all(x["space_id"] == "space" for x in u.journal.values()))

    def test_failed_readback_never_verified(self):
        with tempfile.TemporaryDirectory() as d:
            c = FakeC0()
            c.bad_readback = True
            u = Updater(c, Path(d) / "journal.json", "snapshot", {})
            with self.assertRaisesRegex(C0Error, "readback"):
                u.object("repositories", {"external_key": "repo:7", "repo_id": 7, "url": "https://github.com/org/project", "coverage": "partial"})
            self.assertEqual(u.stats["objects_verified"], 0)
            self.assertFalse(u.journal)

    def test_source_hash_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "snapshot"
            _, records = fixture(root)
            doc = records["documents"][0]
            c = FakeC0()
            source = {"id": "source", "metadata": {"external_key": doc["external_key"]}}
            version = {"id": "version", "source_id": "source", "state": "ready", "number": 1, "content_hash": doc["sha256"]}
            c.listing = lambda *a, **k: [version]
            c.call = lambda name, **args: {"body": "wrong", "id": "document"}
            u = Updater(c, Path(d) / "journal.json", "snapshot", {"poll_attempts": 1})
            u.sources[doc["external_key"]] = source
            with self.assertRaisesRegex(C0Error, "body/hash"):
                u.document(root, doc)
            self.assertEqual(u.stats["documents_verified"], 0)

    def test_immutable_source_receipt_avoids_new_version(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "snapshot"
            _, records = fixture(root)
            doc = records["documents"][0]
            c = FakeC0()
            version = {"id": "version", "source_id": "source", "state": "ready", "number": 1, "content_hash": doc["sha256"]}
            c.listing = lambda *a, **k: [version]
            u = Updater(c, Path(d) / "journal.json", "snapshot", {})
            u.sources[doc["external_key"]] = {"id": "source"}
            u.save(doc["external_key"], doc["sha256"], {"version_id": "version", "source_id": "source", "body_verified": True})
            result = u.document(root, doc)
            self.assertTrue(result["body_verified"])
            self.assertEqual(c.writes, 0)
            self.assertEqual(u.stats["sources_unchanged"], 1)

    def test_submit_then_verify_never_duplicates_or_verifies_queued_text(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "snapshot"
            _, records = fixture(root)
            doc = records["documents"][0]
            c = FakeC0()
            version = {"id": "version", "source_id": "source", "state": "queued", "number": 1, "content_hash": doc["sha256"]}
            source = {"id": "source", "metadata": {"external_key": doc["external_key"], "repo_id": 7, "path": doc["path"]}}
            submitted = []
            def call(name, **arguments):
                if name == "sources_ingest_text":
                    submitted.append(arguments)
                    return version
                if name == "sources_get":
                    return source
                if name == "documents_get":
                    return {"id": "document", "body": (root / doc["content_path"]).read_bytes().decode()}
                raise C0Error("unexpected test operation")
            c.call = call
            c.listing = lambda *a, **k: [{**version, "state": "ready"}]
            u = Updater(c, Path(d) / "journal.json", "snapshot", {"poll_attempts": 1})
            u.document(root, doc, submit_only=True)
            u.document(root, doc, submit_only=True)
            self.assertEqual(len(submitted), 1)
            self.assertEqual(u.stats["documents_verified"], 0)
            self.assertFalse(u.journal)
            u.document(root, doc)
            self.assertEqual(u.stats["documents_verified"], 1)
            self.assertEqual(u.stats["source_versions_created"], 1)
            self.assertEqual(u.stats["sources_unchanged"], 0)


if __name__ == "__main__":
    unittest.main()
