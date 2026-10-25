# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import base64
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "samples/ingestion/src"))
from github_vault.scrape import documentation


class DocumentationTests(unittest.TestCase):
    def run_documentation(self, body):
        class API:
            def get(self, path, params=None):
                if path.endswith("/readme"):
                    return {"path": "README.md"}, None
                if "/git/trees/" in path:
                    return {"tree": [{"type": "blob", "path": "README.administrator.md", "sha": "b" * 40, "size": 10}, {"type": "blob", "path": "README.md", "sha": "c" * 40, "size": len(body)}]}, None
                return {"encoding": "base64", "content": base64.b64encode(body).decode()}, None
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        work = Path(self.temp.name) / "crawl/scope"
        config = {"extensions": [".md"], "max_documents": 1, "max_file_bytes": 131072}
        repo = {"repo_id": 7, "full_name": "org/project", "url": "https://github.com/org/project", "license": None}
        docs, coverage = documentation(API(), repo, work, config, "a" * 40)
        return docs, coverage, work

    def test_actual_readme_precedes_other_readme_named_files(self):
        docs, _, work = self.run_documentation(b"Original README\r\n")
        self.assertEqual(docs[0]["path"], "README.md")
        self.assertEqual((work / docs[0]["content_path"]).read_bytes(), b"Original README\r\n")

    def test_rejected_secret_is_not_materialized(self):
        docs, coverage, work = self.run_documentation(b"-----BEGIN " + b"PRIVATE KEY-----\nexample\n")
        self.assertEqual(docs, [])
        self.assertEqual(coverage["skipped"][0]["reason"], "binary_or_potential_secret")
        self.assertFalse(any((work.parent.parent / "blobs").glob("*")))


if __name__ == "__main__":
    unittest.main()
