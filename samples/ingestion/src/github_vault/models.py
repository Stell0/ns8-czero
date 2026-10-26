# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Snapshot trust boundary, validated fully before any C0 mutation."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, quote
from .state import read, digest, safe_path

KINDS = ("people", "repositories", "contributions", "documents")
TYPES = dict(zip(KINDS, ("github_person", "github_repository", "github_contribution_snapshot", "github_document")))


def github_url(value):
    if not isinstance(value, str):
        raise ValueError("GitHub URL required")
    u = urlsplit(value)
    if u.scheme != "https" or u.netloc != "github.com" or u.username or not u.path.strip("/") or u.query or u.fragment:
        # Evidence review URLs have valid anchors; they are checked separately below.
        raise ValueError("invalid canonical GitHub URL")


def validate(snapshot):
    root = Path(snapshot).resolve()
    manifest = read(root / "manifest.json")
    if not manifest or manifest.get("schema_version") != 1:
        raise ValueError("unsupported or missing snapshot schema")
    if root.name != manifest["snapshot_id"]:
        raise ValueError("snapshot ID/path mismatch")
    if manifest.get("completeness") not in ("complete", "partial"):
        raise ValueError("explicit snapshot coverage required")
    from .config import timestamp
    w = manifest["window"]
    if timestamp(w["since"]) > timestamp(w["until"]):
        raise ValueError("invalid window")
    result, all_keys = {}, set()
    for kind in KINDS:
        records = []
        path = safe_path(root, kind + ".jsonl")
        if digest(path.read_bytes()) != manifest["files"][kind + ".jsonl"]:
            raise ValueError("JSONL hash mismatch: " + kind)
        for line in path.read_text().splitlines():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("record is not an object")
            key = item["external_key"]
            if not isinstance(key, str) or len(key) > 128 or key in all_keys:
                raise ValueError("duplicate or invalid external key")
            all_keys.add(key)
            github_url(item["url"])
            if not item.get("provenance") or item.get("coverage") not in ("verified", "partial", "unavailable"):
                raise ValueError("missing provenance/coverage")
            for evidence in item["provenance"]:
                github_url(evidence.split("#")[0])
            id_field = "github_id" if kind in ("people", "contributions") else "repo_id"
            if type(item[id_field]) is not int or item[id_field] < 1:
                raise ValueError("numeric GitHub identity required")
            if kind == "people" and key != f"person:{item['github_id']}":
                raise ValueError("person identity key mismatch")
            if kind == "repositories" and key != f"repo:{item['repo_id']}":
                raise ValueError("repository identity key mismatch")
            if kind == "contributions":
                if item["window"] != w:
                    raise ValueError("contribution window mismatch")
                for name, value in item["counts"].items():
                    if value is not None and (type(value) is not int or value < 0):
                        raise ValueError("invalid metric count")
                    if item["measurement"][name]["status"] not in ("verified", "partial", "unavailable"):
                        raise ValueError("missing metric measurement")
            if kind == "documents":
                sha = item["commit_sha"]
                if not re.fullmatch(r"[0-9a-f]{40}", sha):
                    raise ValueError("invalid commit SHA")
                safe_path(root, item["path"])
                body_path = safe_path(root, item["content_path"])
                if not body_path.is_relative_to(root / "documents"):
                    raise ValueError("document outside documents directory")
                body = body_path.read_bytes()
                body.decode("utf-8")
                if digest(body) != item["sha256"] or len(body) != item["size_bytes"]:
                    raise ValueError("document hash/size mismatch")
                if f"/blob/{sha}/{quote(item['path'], safe='/')}" not in item["url"]:
                    raise ValueError("document permalink does not match SHA/path")
                if key != f"document:{item['repo_id']}:{digest(item['path'])[:24]}":
                    raise ValueError("document key mismatch")
            records.append(item)
        if len(records) != manifest["counts"][kind]:
            raise ValueError("manifest count mismatch")
        result[kind] = records
    repo_ids = {r["repo_id"] for r in result["repositories"]}
    repositories = {r["repo_id"]: r for r in result["repositories"]}
    person_ids = {p["github_id"] for p in result["people"]}
    for c in result["contributions"]:
        if c["repo_id"] not in repo_ids or c["github_id"] not in person_ids:
            raise ValueError("contribution endpoint missing")
    for d in result["documents"]:
        if d["repo_id"] not in repo_ids:
            raise ValueError("document repository missing")
        expected = repositories[d["repo_id"]]["url"] + f"/blob/{d['commit_sha']}/{quote(d['path'], safe='/')}"
        if d["url"] != expected:
            raise ValueError("document permalink repository mismatch")
    return manifest, result


def latest(path):
    root = Path(path).resolve()
    if (root / "manifest.json").exists():
        return root
    pointer = read(root / "latest.json")
    if not pointer:
        raise ValueError("no snapshot found")
    return safe_path(root, pointer["snapshot_id"])
