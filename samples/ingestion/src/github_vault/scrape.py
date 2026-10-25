# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Public-only REST crawler producing immutable local evidence snapshots."""
import base64
import csv
import io
from pathlib import Path
import re
import shutil
from urllib.parse import quote
import uuid
from .config import window
from .discover import seeds, repository, human, person
from .github_client import GitHub, GitHubError, BudgetExceeded
from .metrics import measure, aggregate_people
from .models import validate, KINDS
from .state import atomic, read, digest, encoded, log, now, safe_path


EXCLUDED = {"node_modules", "vendor", "vendors", "dist", "build", "generated", ".git", ".venv", "venv", "third_party", "third-party"}


def selected_path(path, extensions):
    p = Path(path)
    if p.suffix.lower() not in extensions or any(x.lower() in EXCLUDED or x.startswith(".") for x in p.parts):
        return False
    name = p.name.lower()
    return name.startswith(("readme", "agents", "plan", "contribut", "architect", "setup", "install")) or "docs" in [s.lower() for s in p.parts[:-1]]


def documentation(api, repo, work, config, sha):
    name = repo["full_name"]
    actual_readme = None
    try:
        readme, _ = api.get(f"/repos/{name}/readme", {"ref": sha})
        actual_readme = readme["path"]
    except GitHubError as exc:
        if exc.status != 404:
            raise
    tree, _ = api.get(f"/repos/{name}/git/trees/{sha}", {"recursive": 1})
    candidates = [t for t in tree["tree"] if t["type"] == "blob" and selected_path(t["path"], config["extensions"]) and t.get("size", config["max_file_bytes"] + 1) <= config["max_file_bytes"]]
    def priority(t):
        p = t["path"].lower()
        return (0 if t["path"] == actual_readme else 1 if p == "agents.md" else 2 if "architect" in p else 3 if "contribut" in p else 4, len(Path(p).parts), p)
    candidates.sort(key=priority)
    result, skipped = [], []
    for item in candidates[:config["max_documents"]]:
        path = item["path"]
        safe_path(work, path)
        blob_file = Path(work).parent.parent / "blobs" / item["sha"]
        if blob_file.exists():
            content = blob_file.read_bytes()
        else:
            blob, _ = api.get(f"/repos/{name}/git/blobs/{item['sha']}")
            if blob.get("encoding") != "base64":
                raise GitHubError("unsupported documentation encoding")
            content = base64.b64decode(blob["content"])
        if len(content) > config["max_file_bytes"]:
            skipped.append({"path": path, "reason": "size_limit"})
            continue
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append({"path": path, "reason": "not_utf8"})
            continue
        if b"\0" in content or re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}", content):
            skipped.append({"path": path, "reason": "binary_or_potential_secret"})
            continue
        atomic(blob_file, content)
        content_hash = digest(content)
        relative = f"documents/{repo['repo_id']}/{content_hash}.txt"
        atomic(safe_path(work, relative), content)
        url = f"{repo['url']}/blob/{sha}/{quote(path, safe='/')}"
        result.append({"external_key": f"document:{repo['repo_id']}:{digest(path)[:24]}", "repo_id": repo["repo_id"], "path": path, "url": url, "commit_sha": sha, "blob_sha": item["sha"], "sha256": content_hash, "size_bytes": len(content), "content_path": relative, "license": repo["license"], "retrieved_at": now(), "provenance": [url], "coverage": "verified"})
    return result, {"status": "partial" if tree.get("truncated") or len(candidates) > config["max_documents"] or skipped else "verified", "selected_files": len(result), "candidate_files": len(candidates), "tree_truncated": tree.get("truncated", False), "readme_path": next((d["path"] for d in result if Path(d["path"]).name.lower().startswith("readme")), None), "skipped": skipped}


def fork_changes(api, repo, head_sha, commits):
    detail, _ = api.get(f"/repos/{repo['full_name']}")
    parent = detail.get("parent")
    if not parent:
        raise GitHubError("fork parent unavailable; distinct fork authorship unverified")
    base, _ = api.get(f"/repos/{parent['full_name']}/commits/{quote(parent['default_branch'], safe='')}")
    path = f"/repos/{repo['full_name']}/compare/{base['sha']}...{head_sha}"
    comparison, following = api.get(path, {"per_page": 100})
    unique = {c["sha"] for c in comparison["commits"]}
    while following:
        page, following = api.get(following)
        unique.update(c["sha"] for c in page["commits"])
    if len(unique) != comparison["total_commits"]:
        raise GitHubError("fork comparison coverage incomplete")
    return [c for c in commits if c["sha"] in unique], {"parent_head": base["sha"], "fork_head": head_sha, "ahead_by": comparison["ahead_by"], "behind_by": comparison["behind_by"], "url": comparison["html_url"], "status": "verified"}


def process_repo(api, repo, work, config, w, people, discover_people):
    result = dict(repo)
    docs, contributions, unlinked, errors = [], [], [], []
    name = repo["full_name"]
    try:
        if repo["is_fork"] and not repo["parent"]:
            detail, _ = api.get(f"/repos/{name}")
            if detail.get("parent"):
                result["parent"] = {"id": detail["parent"]["id"], "url": detail["parent"]["html_url"]}
        head, _ = api.get(f"/repos/{name}/commits/{quote(repo['default_branch'], safe='')}")
        result["head_sha"] = head["sha"]
        docs, result["documentation"] = documentation(api, repo, work, config, head["sha"])
        result["languages"], _ = api.get(f"/repos/{name}/languages")
    except GitHubError as exc:
        errors.append({"repo": name, "stage": "documentation", "error": str(exc), "retryable": True})
    try:
        if not result.get("head_sha"):
            raise GitHubError("default branch HEAD unavailable")
        commits = list(api.pages(f"/repos/{name}/commits", {"sha": result["head_sha"], "since": w["since"], "until": w["until"]}))
        if repo["is_fork"]:
            commits, result["fork_comparison"] = fork_changes(api, repo, result["head_sha"], commits)
        prs = api.search("issues", f"repo:{name} is:pr is:public", **w)
        issues = api.search("issues", f"repo:{name} is:issue is:public", **w)
        reviews = []
        for pr in prs[:config["max_review_prs"]]:
            reviews.extend(api.pages(f"/repos/{name}/pulls/{pr['number']}/reviews"))
        contributions, bots, unlinked = measure(repo, commits, prs, issues, reviews, w, people, discover_people)
        for contribution in contributions:
            contribution["observed_at"] = now()
            contribution["measurement"]["commits"]["query"] = {"endpoint": f"/repos/{name}/commits", "sha": result["head_sha"], **w}
            contribution["measurement"]["prs"]["query"] = f"repo:{name} is:pr is:public created:{w['since']}..{w['until']}"
            contribution["measurement"]["issues"]["query"] = f"repo:{name} is:issue is:public created:{w['since']}..{w['until']}"
        # Outside repositories cannot add new people to the discovery frontier.
        known_commits = {c["sha"]: c for c in commits if human(c.get("author")) and w["since"] <= c["commit"].get("committer", c["commit"]["author"])["date"] <= w["until"]}
        known_prs = {p["id"]: p for p in prs if human(p.get("user"))}
        result["metrics"] = {"human_commits": len(known_commits), "human_prs": len(known_prs), "unique_human_contributors": len({c["author"]["id"] for c in known_commits.values()} | {p["user"]["id"] for p in known_prs.values()}), "last_human_commit_at": max((c["commit"].get("committer", c["commit"]["author"])["date"] for c in known_commits.values()), default=None), "bot_activity": bots, "unlinked_commits": len(unlinked), "window": w, "commits_status": "partial" if unlinked else "verified", "prs_status": "verified", "method": "linked humans on pinned default branch; committer timestamp; distinct commit SHA and authored PR ID counted separately", "reviews_status": "partial", "review_sample_prs": min(len(prs), config["max_review_prs"])}
        result["coverage"] = "partial"
        result["crawl_status"] = "measured"
        if repo["is_fork"]:
            result["metrics"]["method"] += "; only fork commits absent from pinned parent HEAD"
            for contribution in contributions:
                contribution["measurement"]["commits"]["method"] += "; excludes inherited parent commits"
            if not known_commits and not known_prs and not any(human(i.get("user")) for i in issues + reviews):
                docs = []
                result["documentation"] = {"status": "excluded_pure_fork", "reason": "no verified distinct human fork activity in window", "selected_files": 0}
    except GitHubError as exc:
        errors.append({"repo": name, "stage": "metrics", "error": str(exc), "retryable": True})
        result["crawl_status"] = "partial"
        result["coverage"] = "partial" if docs else "unavailable"
    return {"repo": result, "documents": docs, "contributions": contributions, "unlinked": unlinked, "errors": errors}


def scrape(config, args):
    w = window(config, args)
    settings = dict(config["github"])
    if args.max_requests:
        settings["max_requests"] = args.max_requests
    if args.max_documents:
        settings["max_documents"] = args.max_documents
    seed = seeds(config["root"], settings)
    scope = {"pilot_repositories": settings.get("pilot_repositories", []), "priority_prefix": settings.get("priority_prefix", ""), "window": w, "pilot": args.pilot, "organizations": settings["organizations"], "limit_repos": args.limit_repos, "limit_people": args.limit_people, "max_documents": settings["max_documents"], "max_file_bytes": settings["max_file_bytes"], "extensions": settings["extensions"], "max_review_prs": settings["max_review_prs"], "external_discovery": settings["external_discovery"], "incremental": args.incremental}
    output = Path(args.output or config["paths"]["snapshots"]).resolve()
    if not output.is_relative_to(Path(config["root"]).resolve()):
        raise ValueError("Snapshot outputs must remain inside the private job")
    if args.dry_run:
        return {"status": "dry_run", "writes_c0": 0, "window": w, "scope": scope, "output": str(output)}, 0
    state = Path(config["paths"]["state"])
    anchor_path = state / ("incremental-" + digest({k: v for k, v in scope.items() if k != "window"})[:20] + ".json")
    if args.incremental and args.resume and not args.since and not args.until:
        anchor = read(anchor_path)
        if anchor:
            w = scope["window"] = anchor["window"]
    if args.incremental:
        atomic(anchor_path, {"window": w})
    scope_id = digest(scope)[:20]
    work = state / "crawl" / scope_id
    if not args.resume and work.exists():
        # Keep previous checkpoints rather than delete generated evidence.
        work = state / "crawl" / (scope_id + "-" + uuid.uuid4().hex[:8])
    api = GitHub(work / "pages", settings, resume=args.resume)
    auth, _ = api.get("/user") if api.token else ({"login": None}, None)
    log("github_auth", authenticated=bool(api.token), identity=auth.get("login"))
    errors, repos, people, contributions, documents, unlinked = [], {}, {}, [], [], []
    seed_identities = {}
    root_enumeration = False
    if args.pilot:
        if not settings.get("pilot_repositories"):
            raise ValueError("Configure pilot_repositories before using --pilot")
        for name in settings["pilot_repositories"]:
            try:
                raw, _ = api.get(f"/repos/{name}")
                repos[raw["id"]] = repository(raw, raw["html_url"], settings["organizations"])
            except GitHubError as exc:
                errors.append({"repo": name, "stage": "pilot_lookup", "error": str(exc), "retryable": True})
    else:
        root_enumeration = True
        for org in settings["organizations"]:
            try:
                for raw in api.pages(f"/orgs/{org}/repos", {"type": "public", "sort": "full_name", "direction": "asc"}):
                    repos[raw["id"]] = repository(raw, f"https://github.com/{org}", settings["organizations"])
            except GitHubError as exc:
                root_enumeration = False
                errors.append({"org": org, "stage": "org_enumeration", "error": str(exc), "retryable": True})
        for row in seed["people"]["rows"]:
            try:
                user, _ = api.get(f"/users/{row['github_handle']}")
                if human(user):
                    people[user["id"]] = person(user, user["html_url"])
                    seed_identities[row["github_handle"].lower()] = {"github_id": user["id"], "login": user["login"], "url": user["html_url"]}
            except GitHubError as exc:
                errors.append({"person": row["github_handle"], "stage": "seed_identity", "error": str(exc), "retryable": True})
    seed_status = []
    names = {r["full_name"].lower(): r for r in repos.values()}
    for row in seed["repositories"]["rows"]:
        item = names.get(row["full_name"].lower())
        status = "resolved_by_live_inventory" if item else "unresolved_not_evidence_of_deletion"
        if not item and not args.pilot:
            try:
                raw, _ = api.get(f"/repos/{row['full_name']}")
                item = repository(raw, row["github_url"], settings["organizations"])
                repos[item["repo_id"]] = item
                status = "resolved_live_canonical_name"
            except GitHubError as exc:
                status = "unavailable_not_proof_of_deletion"
                if str(exc) == "private repository excluded":
                    status = "excluded_private"
                errors.append({"repo": row["full_name"], "stage": "seed_reconciliation", "error": str(exc), "retryable": exc.retryable, "http_status": exc.status})
        seed_status.append({"full_name": row["full_name"], "url": row["github_url"], "repo_id": item["repo_id"] if item else None, "canonical_name": item["full_name"] if item else None, "status": status})
    done = 0
    root_ids = {rid for rid, repo in repos.items() if repo["root_org"]}

    def process(ids, expand, ceiling=None):
        nonlocal done
        for rid in ids:
            if args.limit_repos and done >= args.limit_repos:
                break
            if ceiling and done >= ceiling:
                break
            checkpoint = work / "repos" / f"{rid}.json"
            saved = read(checkpoint) if args.resume else None
            measurement_version = 3 if repos[rid]["is_fork"] else 2
            if saved and not saved["errors"] and saved.get("measurement_version") == measurement_version and saved.get("documentation_version") == 2:
                result = saved
                if expand:
                    for p in saved["people"]:
                        people[p["github_id"]] = p
            else:
                result = process_repo(api, repos[rid], work, settings, w, people, expand)
                result["measurement_version"] = measurement_version
                result["documentation_version"] = 2
                result["people"] = list(people.values()) if expand else []
                atomic(checkpoint, result)
            repos[rid] = result["repo"]
            contributions.extend(result["contributions"])
            documents.extend(result["documents"])
            unlinked.extend({"repo_id": rid, **c} for c in result["unlinked"])
            errors.extend(result["errors"])
            done += 1
            log("repository_processed", repo=repos[rid]["full_name"], done=done, people=len(people), documents=len(documents), errors=len(errors))
            if api.requests >= settings["max_requests"]:
                break
    priority = {name.lower(): position for position, name in enumerate(settings.get('pilot_repositories', []))}
    ordered = sorted(root_ids, key=lambda rid: (priority.get(repos[rid]['full_name'].lower(), len(priority)), repos[rid]['full_name'].lower()))
    root_ceiling = max(3, args.limit_repos // 2) if not args.pilot and settings["external_discovery"] and args.limit_repos and args.limit_repos >= 6 else None
    process(ordered, True, root_ceiling)
    if args.limit_people:
        # Retain the most observed root contributors; limits never fabricate zero totals.
        ranked = sorted(people, key=lambda pid: (-sum(c["counts"]["commits"] + c["counts"]["prs"] for c in contributions if c["github_id"] == pid), pid))
        people = {pid: people[pid] for pid in ranked[:args.limit_people]}
        contributions = [c for c in contributions if c["github_id"] in people]
    frontier = list(people.values())
    if not args.pilot and settings["external_discovery"]:
        for p in frontier:
            try:
                login = p["login"]
                for raw in api.pages(f"/users/{login}/repos", {"type": "owner", "sort": "full_name"}):
                    if not raw["private"] and raw["id"] not in repos:
                        repos[raw["id"]] = repository(raw, p["url"], settings["organizations"])
                for kind, query in (("commits", f"author:{login} is:public"), ("issues", f"author:{login} is:pr is:public"), ("issues", f"reviewed-by:{login} is:pr is:public")):
                    for event in api.search(kind, query, **w):
                        if kind == "commits":
                            target = event["repository"]
                            rid, full = target["id"], target["full_name"]
                        else:
                            # repository_url is returned by the API, not a guessed endpoint.
                            repository_url = event["repository_url"]
                            target, _ = api.get(repository_url)
                            rid, full = target["id"], target["full_name"]
                        if rid not in repos:
                            if "default_branch" not in target or "stargazers_count" not in target:
                                target, _ = api.get(f"/repos/{full}")
                            repos[rid] = repository(target, event["html_url"], settings["organizations"])
                        repos[rid]["activity_evidence"] = event["html_url"]
                p["external_discovery"] = {"status": "partial", "method": "owned public repos; commit author search; authored and reviewed PR search; old PR review activity may be omitted"}
            except GitHubError as exc:
                errors.append({"person": p["login"], "stage": "external_discovery", "error": str(exc), "retryable": True})
                p["external_discovery"] = {"status": "partial", "error": str(exc)}
                if isinstance(exc, BudgetExceeded):
                    break
        process(sorted(set(repos) - root_ids, key=lambda rid: (not bool(repos[rid].get("activity_evidence")), not repos[rid]["full_name"].split("/")[-1].startswith(settings.get('priority_prefix', '')), repos[rid]["full_name"].lower())), False)
    aggregate_people(people, contributions)
    snapshot_id = now().replace(":", "").replace("-", "") + "-" + scope_id + "-" + uuid.uuid4().hex[:6]
    root = output / snapshot_id
    records = {"people": list(people.values()), "repositories": list(repos.values()), "contributions": contributions, "documents": documents}
    files = {}
    for kind, items in records.items():
        data = b"".join(encoded(item) + b"\n" for item in sorted(items, key=lambda x: x["external_key"]))
        atomic(root / (kind + ".jsonl"), data)
        files[kind + ".jsonl"] = digest(data)
    for d in documents:
        atomic(safe_path(root, d["content_path"]), safe_path(work, d["content_path"]).read_bytes())
    atomic(root / "unlinked_commits.jsonl", b"".join(encoded(x) + b"\n" for x in unlinked))
    atomic(root / "seed_reconciliation.json", {"repositories": seed_status, "people": [{"seed_login": r["github_handle"], "url": r["github_url"], "resolved_identity": seed_identities.get(r["github_handle"].lower()), "status": "selected_discovered_identity" if any(p["login"].lower() == r["github_handle"].lower() for p in people.values()) else "resolved_outside_bounded_frontier" if r["github_handle"].lower() in seed_identities else "unresolved_seed_only"} for r in seed["people"]["rows"]]})
    summary = io.StringIO()
    writer = csv.DictWriter(summary, fieldnames=["repo_id", "full_name", "url", "coverage", "crawl_status", "human_commits", "human_prs"])
    writer.writeheader()
    for repo in sorted(repos.values(), key=lambda r: r["full_name"].lower()):
        writer.writerow({**{k: repo[k] for k in ["repo_id", "full_name", "url", "coverage", "crawl_status"]}, "human_commits": (repo["metrics"] or {}).get("human_commits"), "human_prs": (repo["metrics"] or {}).get("human_prs")})
    atomic(root / "summary.csv", summary.getvalue().encode())
    atomic(root / "errors.jsonl", b"".join(encoded(e) + b"\n" for e in errors))
    manifest = {"schema_version": 1, "snapshot_id": snapshot_id, "created_at": now(), "window": w, "scope": scope, "counts": {k: len(v) for k, v in records.items()}, "files": files, "sources": {k: {a: b for a, b in v.items() if a != "rows"} for k, v in seed.items()}, "completeness": "partial", "coverage": {"root_inventory": "verified" if root_enumeration else "partial", "root_repositories": sum(r["root_org"] for r in repos.values()), "external_repositories": sum(not r["root_org"] for r in repos.values()), "measured_repositories": sum(r["metrics"] is not None for r in repos.values()), "people_discovery": "partial", "review_discovery": "partial", "window_open_at_retrieval": w["until"] > now(), "aggregate_totals_publishable": False, "reason": "bounded discovery; review sample; external search omits some historical reviews; no exhaustive aggregate claim"}, "errors": errors, "requests": api.requests, "cached_pages": api.cached, "authenticated": bool(api.token)}
    atomic(root / "manifest.json", manifest)
    validate(root)
    atomic(root / "validation_report.json", {"status": "validated", "files": files, "documents_hashed": len(documents)})
    atomic(output / "latest.json", {"snapshot_id": snapshot_id})
    atomic(state / "last_scrape.json", {"snapshot": str(root), "scope_id": scope_id, "checkpoint": str(work)})
    return {"status": "partial", "snapshot": str(root), "counts": manifest["counts"], "coverage": manifest["coverage"], "errors": len(errors), "requests": api.requests, "cached_pages": api.cached}, (1 if any(e.get("retryable", True) for e in errors) else 2)
