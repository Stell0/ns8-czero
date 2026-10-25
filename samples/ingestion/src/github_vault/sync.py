# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Snapshot-only C0 writes, with fresh readback and durable retry receipts."""
import json
from pathlib import Path
import re
import time
from .c0_client import C0, C0Error
from c0_ingest.sources import submit_text, verify_document
from .models import TYPES, validate, latest
from .state import atomic, read, digest, encoded, log, now, safe_path


def payload(record):
    text = encoded(record).decode()
    if len(text) > 4096:
        raise ValueError(f"record exceeds inspected C0 schema bound: {record['external_key']}")
    return {"external_key": record["external_key"], "github_id": record.get("github_id", record.get("repo_id")), "url": record["url"], "coverage": record["coverage"], "record_json": text}


class Updater:
    def __init__(self, client, state_path, snapshot_id, settings):
        self.client = client
        self.path = Path(state_path)
        self.snapshot_id = snapshot_id
        self.settings = settings
        self.journal = read(self.path, {})
        self.objects = {}
        self.sources = {}
        self.stats = {"objects_created": 0, "objects_updated": 0, "objects_unchanged": 0, "objects_verified": 0, "sources_created": 0, "source_versions_created": 0, "sources_unchanged": 0, "documents_verified": 0, "relations_created": 0, "relations_unchanged": 0, "relations_verified": 0, "wiki_written": 0, "wiki_unchanged": 0, "wiki_verified": 0, "search_verified": 0}
        self.document_results = []
        self.relations = {}
        self.version_cache = {}
        self.pages = None
        self.submitted_versions = set()

    def save(self, key, content_hash, result):
        identity = digest([self.client.space_id, self.snapshot_id, key, content_hash])
        self.journal[identity] = {"space_id": self.client.space_id, "snapshot_id": self.snapshot_id, "external_key": key, "content_sha256": content_hash, "result": result, "verified_at": now()}
        atomic(self.path, self.journal)

    def load_objects(self):
        for type_name in TYPES.values():
            rows = self.client.listing("objects_list", "objects", type_name=type_name)
            for row in rows:
                key = row["data"].get("external_key")
                if key in self.objects:
                    raise C0Error("duplicate external key already exists in C0")
                self.objects[key] = row

    def upsert_records(self, records):
        pending = []
        for kind, rows in records.items():
            for record in rows:
                data = payload(record)
                existing = self.objects.get(record["external_key"])
                if existing and existing["type_name"] != TYPES[kind]:
                    raise C0Error("existing object type mismatch")
                if existing and existing["data"] == data:
                    self.object(kind, record)
                    continue
                operation = {"operation": "update", "id": existing["id"], "expected_revision": existing["revision"], "data": data} if existing else {"operation": "create", "type_name": TYPES[kind], "data": data}
                pending.append((record, operation, existing is not None))
        for offset in range(0, len(pending), 25):
            batch = pending[offset:offset + 25]
            saved = self.client.call("objects_batch", data={"operations": [v[1] for v in batch]})["results"]
            if len(saved) != len(batch):
                raise C0Error("object batch receipt count mismatch")
            fetched = self.client.read_many([("objects_get", {"object_id": v["id"]}) for v in saved])
            for (record, operation, updated), actual in zip(batch, fetched, strict=True):
                if actual["data"] != operation["data"]:
                    raise C0Error("object batch independent readback mismatch")
                self.objects[record["external_key"]] = actual
                self.stats["objects_updated" if updated else "objects_created"] += 1
                self.stats["objects_verified"] += 1
                self.save(record["external_key"], digest(actual["data"]), {"kind": "object", "id": actual["id"], "revision": actual["revision"]})

    def object(self, kind, record):
        data = payload(record)
        key = record["external_key"]
        existing = self.objects.get(key)
        if existing and existing["type_name"] != TYPES[kind]:
            raise C0Error("existing object type mismatch")
        if existing and existing["data"] == data:
            saved = existing
            self.stats["objects_unchanged"] += 1
        elif existing:
            saved = self.client.call("objects_update", object_id=existing["id"], data={"data": data, "expected_revision": existing["revision"]})
            self.stats["objects_updated"] += 1
        else:
            # Unique external_key + fresh listing reconcile uncertain creates on rerun.
            saved = self.client.call("objects_create", data={"type_name": TYPES[kind], "data": data})
            self.stats["objects_created"] += 1
        # An unchanged record already came from this run's fresh scoped listing.
        verified = existing if existing and existing["data"] == data else self.client.call("objects_get", object_id=saved["id"])
        if verified["data"] != data or verified["type_name"] != TYPES[kind]:
            raise C0Error("object readback mismatch: " + key)
        self.stats["objects_verified"] += 1
        self.objects[key] = verified
        self.save(key, digest(data), {"kind": "object", "id": verified["id"], "revision": verified["revision"]})
        return verified

    def load_sources(self):
        for source in self.client.listing("sources_list", "sources"):
            key = source["metadata"].get("external_key")
            if key:
                if key in self.sources:
                    raise C0Error("duplicate source key already exists")
                self.sources[key] = source
        sources = list(self.sources.values())
        if hasattr(self.client, "read_many"):
            responses = self.client.read_many([("source_versions_list", {"source_id": s["id"], "limit": 100}) for s in sources])
            for source, response in zip(sources, responses):
                if len(response["versions"]) < 100:
                    self.version_cache[source["id"]] = response["versions"]

    def document(self, root, document, submit_only=False):
        key = document["external_key"]
        body = safe_path(root, document["content_path"]).read_bytes().decode("utf-8")
        source = self.sources.get(key)
        version = None
        if source:
            versions = self.version_cache.get(source["id"])
            if versions is None:
                versions = self.client.listing("source_versions_list", "versions", source_id=source["id"])
            version = next((v for v in versions if v["content_hash"] == document["sha256"]), None)
        if version:
            if submit_only:
                return
            if version["id"] not in self.submitted_versions:
                self.stats["sources_unchanged"] += 1
            previous = next((j["result"] for j in self.journal.values() if j["space_id"] == self.client.space_id and j["external_key"] == key and j["content_sha256"] == document["sha256"] and j["result"].get("version_id") == version["id"] and j["result"].get("body_verified")), None)
            if previous and version["state"] == "ready":
                result = {**previous, "verification_method": "fresh immutable version hash/state plus prior exact body readback"}
                self.stats["documents_verified"] += 1
                self.document_results.append(result)
                self.save(key, document["sha256"], result)
                return result
        else:
            version = submit_text(self.client, body=body,
                title=f"{document['url'].split('/blob/')[0].removeprefix('https://github.com/')} — {document['path']}",
                media_type="text/markdown" if Path(document["path"]).suffix.lower() in (".md", ".markdown") else "text/plain",
                external_key=key, source=source,
                metadata={"external_key": key, "github_url": document["url"], "repo_id": document["repo_id"],
                          "path": document["path"], "commit_sha": document["commit_sha"], "sha256": document["sha256"],
                          "license": document["license"], "retrieved_at": document["retrieved_at"]})
            self.submitted_versions.add(version["id"])
            self.stats["source_versions_created"] += 1
            if not source:
                self.stats["sources_created"] += 1
            source = self.client.call("sources_get", source_id=version["source_id"])
            self.sources[key] = source
            self.version_cache[source["id"]] = [version]
        if submit_only:
            return
        fetched = verify_document(self.client, version, body,
                                  attempts=self.settings["poll_attempts"], seconds=self.settings.get("poll_seconds", 0))
        provenance = source
        if provenance["metadata"].get("external_key") != key:
            raise C0Error("source provenance readback mismatch")
        if provenance["metadata"].get("repo_id") != document["repo_id"] or provenance["metadata"].get("path") != document["path"]:
            raise C0Error("source repository/path attribution mismatch")
        result = {"external_key": key, "source_id": version["source_id"], "version_id": version["id"], "version": version["number"], "document_id": fetched["id"], "sha256": document["sha256"], "github_url": document["url"], "state": "ready", "body_verified": True}
        result["verification_method"] = "exact document body/hash and source attribution readback"
        self.stats["documents_verified"] += 1
        self.save(key, document["sha256"], result)
        self.document_results.append(result)
        return result

    def relation(self, kind, source_key, target_key):
        source, target = self.objects.get(source_key), self.objects.get(target_key)
        if not source or not target:
            return
        identity = (kind, source["id"], target["id"])
        if source["id"] not in self.relations:
            self.relations[source["id"]] = self.client.listing("object_relations_list", "relations", object_id=source["id"])
        existing = next((r for r in self.relations[source["id"]] if (r["kind"], r["source_id"], r["target_id"]) == identity), None)
        if existing:
            self.stats["relations_unchanged"] += 1
            fresh = self.relations[source["id"]]
        else:
            self.client.call("object_relations_create", data={"kind": kind, "source_id": source["id"], "source_type": source["type_name"], "target_id": target["id"], "target_type": target["type_name"]})
            self.stats["relations_created"] += 1
            fresh = self.client.listing("object_relations_list", "relations", object_id=source["id"])
        matches = [r for r in fresh if (r["kind"], r["source_id"], r["target_id"]) == identity]
        if len(matches) != 1:
            raise C0Error("relation readback missing or duplicated")
        self.relations[source["id"]] = fresh
        self.stats["relations_verified"] += 1
        self.save("relation:" + digest(identity)[:40], digest(identity), {"id": matches[0]["id"]})

    def prefetch_relations(self, keys):
        ids = sorted({self.objects[k]["id"] for k in keys if k in self.objects})
        replies = self.client.read_many([("object_relations_list", {"object_id": identity, "limit": 100}) for identity in ids])
        for identity, reply in zip(ids, replies):
            if len(reply["relations"]) < 100:
                self.relations[identity] = reply["relations"]

    def search_readmes(self, root, documents):
        for doc in documents:
            if not Path(doc["path"]).name.lower().startswith("readme"):
                continue
            result = next(v for v in self.document_results if v["external_key"] == doc["external_key"])
            body = safe_path(root, doc["content_path"]).read_text()
            # Test several real text spans; search still must attribute the exact version.
            lines = [" ".join(re.findall(r"[A-Za-z0-9]+", line)) for line in body.splitlines() if len(re.findall(r"[A-Za-z0-9]+", line)) >= 4]
            verified = False
            for line in lines[:5]:
                query = " ".join(line.split()[:8])
                response = self.client.call("knowledge_search", options={"query": query[:512], "mode": "text", "rerank": "off", "kind": "source", "limit": 50})
                for hit in response["hits"]:
                    citation = hit.get("citation")
                    if citation and citation["version_id"] == result["version_id"] and citation["source_id"] == result["source_id"]:
                        passage = self.client.call("citations_get", chunk_id=citation["chunk_id"])
                        if passage["version_id"] != result["version_id"] or passage["body"] not in body:
                            raise C0Error("immutable search citation does not match original body")
                        result["chunk_id"] = passage["chunk_id"]
                        result["search"] = {"query": query, "chunk_id": citation["chunk_id"], "verified": True}
                        self.stats["search_verified"] += 1
                        verified = True
                        break
                if verified:
                    break
            if not verified:
                raise C0Error("README phrase search did not return exact source/version: " + doc["url"])
            self.save(doc["external_key"], doc["sha256"], result)

    def wiki(self, slug, title, body):
        if self.pages is None:
            pages = self.client.listing("wiki_pages_list", "pages")
            reads = self.client.read_many([("wiki_pages_get", {"page_id": p["id"]}) for p in pages])
            self.pages = {p["slug"]: p for p in reads}
        current = self.pages.get(slug)
        if current and current["content"]["body"] == body:
            saved = current
            self.stats["wiki_unchanged"] += 1
        else:
            data = {"slug": slug, "title": title, "body": body, "metadata": {"derived": True, "coverage": "partial", "snapshot_id": self.snapshot_id}, "idempotency_key": digest([self.client.space_id, slug, digest(body.encode()), current["revision"] if current else None])}
            if current:
                data["expected_revision"] = current["revision"]
            saved = self.client.call("wiki_pages_upsert", data=data)
            self.stats["wiki_written"] += 1
        fetched = current if current and current["content"]["body"] == body else self.client.call("wiki_pages_get", page_id=saved["id"])
        if fetched["content"]["body"] != body:
            raise C0Error("wiki readback mismatch")
        self.stats["wiki_verified"] += 1
        self.pages[slug] = fetched
        self.save("wiki:" + slug, digest(body.encode()), {"id": saved["id"], "revision": fetched["revision"]})


def selected(records, args):
    result = {k: list(v) for k, v in records.items()}
    if args.limit_repos:
        result["repositories"] = sorted(result["repositories"], key=lambda r: (r["metrics"] is None, r["full_name"].lower()))[:args.limit_repos]
    if args.limit_people:
        result["people"] = sorted(result["people"], key=lambda p: p["github_id"])[:args.limit_people]
    repos = {r["repo_id"] for r in result["repositories"]}
    people = {p["github_id"] for p in result["people"]}
    result["documents"] = [d for d in result["documents"] if d["repo_id"] in repos]
    result["contributions"] = [c for c in result["contributions"] if c["repo_id"] in repos and c["github_id"] in people]
    return result


def sync(config, args):
    if args.space_name and args.space_name != config["c0"]["space_name"]:
        raise C0Error("Space name selector differs from configured target")
    root = latest(args.input or config["paths"]["snapshots"])
    manifest, records = validate(root)
    if args.since and args.since != manifest["window"]["since"] or args.until and args.until != manifest["window"]["until"]:
        raise ValueError("sync window selectors do not match snapshot; updater never recrawls")
    if args.incremental and not manifest["scope"]["incremental"]:
        raise ValueError("incremental updater requires an incremental snapshot")
    records = selected(records, args)
    for items in records.values():
        for record in items:
            payload(record)
    if args.validate_only:
        return {"status": "validated", "snapshot": str(root), "counts": {k: len(v) for k, v in records.items()}, "writes": 0}, 0
    if not args.dry_run and not getattr(args, 'apply', False):
        raise C0Error('Explicit --apply is required before C0 writes')
    client = C0(config["c0"])
    try:
        required = ["sources_ingest_text", "sources_get", "source_versions_list", "documents_get", "objects_create", "objects_get", "objects_list"]
        for name in required:
            if name not in client.operations or "space_id" not in client.operations[name]["input_schema"]["properties"]:
                raise C0Error("bulk writes blocked: source ingestion or space isolation unavailable: " + name)
        space_id = client.resolve_space(Path(config["paths"]["state"]) / "c0_space.json", dry_run=args.dry_run)
        types = {t["name"]: t for t in client.listing("object_types_list", "types")}
        for name in TYPES.values():
            if name not in types:
                raise C0Error("required compatible unique type missing; admin bootstrap required: " + name)
            from .bootstrap import check_type
            check_type(types[name])
        summary = {"snapshot_id": manifest["snapshot_id"], "space_id": space_id, "snapshot_completeness": manifest["completeness"], "aggregate_totals_published": False, "counts": {k: len(v) for k, v in records.items()}}
        if args.dry_run:
            if client.writes != 0:
                raise C0Error("dry-run performed writes")
            return {**summary, "status": "dry_run", "writes": 0}, 0
        if not space_id:
            raise C0Error("target space unresolved")
        updater = Updater(client, Path(config["paths"]["state"]) / "sync_journal.json", manifest["snapshot_id"], config["c0"])
        reports = Path(config["paths"]["reports"])
        error = None
        try:
            updater.load_objects()
            updater.load_sources()
            updater.upsert_records(records)
            log("objects_verified", count=updater.stats["objects_verified"])
            for document in records["documents"]:
                updater.document(root, document, submit_only=True)
            for document in records["documents"]:
                updater.document(root, document)
                log("source_verified", key=document["external_key"], count=updater.stats["documents_verified"])
            updater.prefetch_relations([f"person:{c['github_id']}" for c in records["contributions"]] + [d["external_key"] for d in records["documents"]] + [r["external_key"] for r in records["repositories"]] + [f"person:{r['owner']['id']}" for r in records["repositories"]])
            for c in records["contributions"]:
                updater.relation("contributed_to", f"person:{c['github_id']}", f"repo:{c['repo_id']}")
            for r in records["repositories"]:
                updater.relation("owns", f"person:{r['owner']['id']}", r["external_key"])
                if r["parent"]:
                    updater.relation("fork_of", r["external_key"], f"repo:{r['parent']['id']}")
            for d in records["documents"]:
                updater.relation("documents", d["external_key"], f"repo:{d['repo_id']}")
            updater.search_readmes(root, records["documents"])
            index = ["# " + config['c0']['space_name'], "", f"Evidence snapshot `{manifest['snapshot_id']}`. UTC window: {manifest['window']['since']} through {manifest['window']['until']}.", "", "Coverage is partial. Counts are observed records, not exhaustive organization or person totals. Employment and maintainership are unknown.", ""]
            for repo in records["repositories"]:
                evidence = [d for d in updater.document_results if next(x for x in records["documents"] if x["external_key"] == d["external_key"])["repo_id"] == repo["repo_id"]]
                if not evidence:
                    continue
                lines = [f"# {repo['full_name']}", "", f"Repository: {repo['url']}", "", "Original documentation evidence:", ""]
                lines += [f"- {d['github_url']} — source `{d['source_id']}`, immutable version `{d['version_id']}`." for d in evidence]
                # c0:// URIs are advertised by c0://capabilities; no guessed web routes.
                lines += ["", f"[Original evidence](c0://spaces/{space_id}/source-versions/{evidence[0]['version_id']})", "", "This overview provides source navigation only; no undocumented product claims."]
                slug = f"github-repository-{repo['repo_id']}"
                updater.wiki(slug, repo["full_name"], "\n".join(lines))
                index.append(f"- [{repo['full_name']}]({repo['url']}) — original source version `{evidence[0]['version_id']}`.")
            # Developer activity stays in structured API evidence; README indexing alone
            # does not substantiate developer summaries, employment or maintainership.
            updater.wiki("github-projects-index", config["c0"]["space_name"], "\n".join(index))
        except Exception as exc:
            error = str(exc)
            log("sync_incomplete", error=error)
        result = {**summary, "status": "failed" if error else "verified_partial", "stats": updater.stats, "writes": client.writes, "documents": updater.document_results, "error": error, "finished_at": now()}
        atomic(reports / "last_sync.json", result)
        atomic(reports / f"sync-{manifest['snapshot_id']}-{digest(result)[:8]}.json", result)
        for filename, title in (("ingestion_report.md", "Ingestion"), ("verification_report.md", "Verification")):
            atomic(reports / filename, (f"# {title}\n\nTarget space `{space_id}`. Snapshot `{manifest['snapshot_id']}`.\n\n" + "```json\n" + json.dumps(result, indent=2) + "\n```\n").encode())
        return result, 1 if error else 2
    finally:
        client.close()
