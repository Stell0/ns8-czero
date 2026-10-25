# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Commit and PR authorship are counted separately; unknowns stay unknown."""
from collections import defaultdict
from .discover import human, person, group
from .state import digest


def measure(repo, commits, prs, issues, reviews, window, people, allow_discovery=True):
    by_person = defaultdict(lambda: {"commits": set(), "prs": set(), "issues": set(), "reviews": set(), "dates": [], "evidence": []})
    bots = {"commits": 0, "prs": 0}
    unlinked = []
    seen = set()
    def event(user, metric, identity, date, url):
        if not human(user):
            return
        if user["id"] not in people and allow_discovery:
            people[user["id"]] = person(user, url)
        if user["id"] not in people:
            return
        row = by_person[user["id"]]
        row[metric].add(identity)
        row["dates"].append(date)
        if url not in row["evidence"] and len(row["evidence"]) < 5:
            row["evidence"].append(url)
    for commit in commits:
        if commit["sha"] in seen:
            continue
        seen.add(commit["sha"])
        date = commit["commit"].get("committer", commit["commit"]["author"])["date"]
        if not window["since"] <= date <= window["until"]:
            continue
        user = commit.get("author")
        if human(user):
            event(user, "commits", commit["sha"], date, commit["html_url"])
        elif user and (user.get("type") == "Bot" or user.get("login", "").endswith("[bot]")):
            bots["commits"] += 1
        else:
            unlinked.append({"sha": commit["sha"], "url": commit["html_url"], "date": date, "identity": "unlinked_or_uncertain"})
    for pr in prs:
        if human(pr.get("user")):
            event(pr["user"], "prs", pr["id"], pr["created_at"], pr["html_url"])
        else:
            bots["prs"] += 1
    for issue in issues:
        event(issue.get("user"), "issues", issue["id"], issue["created_at"], issue["html_url"])
    for review in reviews:
        date = review.get("submitted_at")
        if date and window["since"] <= date <= window["until"]:
            event(review.get("user"), "reviews", review["id"], date, review["html_url"])
    records = []
    for pid, row in sorted(by_person.items()):
        key = f"contribution:{pid}:{repo['repo_id']}:{digest(window)[:16]}"
        records.append({"external_key": key, "github_id": pid, "repo_id": repo["repo_id"], "url": repo["url"], "owner_group": group(repo), "window": window, "counts": {**{k: len(row[k]) for k in ("commits", "prs", "issues")}, "reviews": None}, "observed_reviews": len(row["reviews"]), "last_activity": max(row["dates"]), "provenance": row["evidence"], "coverage": "partial", "measurement": {"commits": {"status": "verified", "method": "distinct SHA; linked human author; pinned default branch; committer date in window; merges included; cherry-picks with different SHAs distinct"}, "prs": {"status": "verified", "method": "distinct authored PR ID; created in UTC window; all states; paginated partitioned GitHub issues search"}, "issues": {"status": "verified", "method": "distinct authored issue ID; created in window"}, "reviews": {"status": "partial", "method": "submitted reviews on bounded PR sample; excludes pending; old PRs may be missing; observed_reviews is a lower bound"}}})
    return records, bots, unlinked


def aggregate_people(people, contributions):
    for pid, p in people.items():
        mine = [c for c in contributions if c["github_id"] == pid]
        p["metrics"] = {}
        for owner in sorted({c["owner_group"] for c in contributions} | {"other"}):
            rows = [c for c in mine if c["owner_group"] == owner]
            p["metrics"][owner] = {"commits": None, "prs": None, "observed_commits": sum(c["counts"]["commits"] for c in rows), "observed_prs": sum(c["counts"]["prs"] for c in rows), "observed_distinct_repos": len({c["repo_id"] for c in rows}), "status": "partial", "method": "observed lower bounds across processed repositories; exhaustive totals unavailable"}
        p["last_human_activity_at"] = max((c["last_activity"] for c in mine), default=None)
        p["coverage"] = "partial"
