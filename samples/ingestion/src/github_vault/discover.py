# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, one-hop discovery. Seeds never establish affiliation or activity."""
import csv
from pathlib import Path
from .state import digest

def seeds(root, settings):
    result = {}
    for kind, key, field in [("people", "github_handle", "people_seed"),
                             ("repositories", "full_name", "repository_seed")]:
        name = settings.get(field)
        if not name:
            result[kind] = {"rows": [], "headers": [], "sha256": digest(b""), "path": None}
            continue
        from .state import safe_path
        path = safe_path(root, name)
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or key not in reader.fieldnames or "github_url" not in reader.fieldnames:
                raise ValueError("unexpected seed CSV headers")
            rows = list(reader)
        result[kind] = {"rows": rows, "headers": reader.fieldnames, "sha256": digest(path.read_bytes()), "path": name}
    return result


def human(user):
    return bool(user and user.get("id") and user.get("type") == "User" and not user.get("login", "").lower().endswith("[bot]"))


def person(user, evidence):
    return {"external_key": f"person:{user['id']}", "github_id": user["id"], "login": user["login"], "url": user["html_url"], "user_type": "User", "affiliation": "unknown", "provenance": [evidence], "coverage": "partial"}


def repository(raw, provenance, roots):
    return {"external_key": f"repo:{raw['id']}", "repo_id": raw["id"], "full_name": raw["full_name"], "url": raw["html_url"], "owner": {"id": raw["owner"]["id"], "login": raw["owner"]["login"], "type": raw["owner"]["type"]}, "description": (raw.get("description") or "")[:500], "is_fork": raw["fork"], "parent": ({"id": raw["parent"]["id"], "url": raw["parent"]["html_url"]} if raw.get("parent") else None), "archived": raw["archived"], "default_branch": raw["default_branch"], "stars": raw["stargazers_count"], "language": raw.get("language"), "license": raw.get("license"), "root_org": raw["owner"]["login"].lower() in {s.lower() for s in roots}, "provenance": [provenance], "coverage": "unavailable", "crawl_status": "pending", "metrics": None, "documentation": {"status": "unavailable"}}


def group(repo):
    return repo["owner"]["login"].lower() if repo.get("root_org") else "other"
