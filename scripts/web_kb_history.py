# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reuse the local Nethesis baseline cohort and compare it with later runs."""
import fcntl
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median
from subprocess import check_output, run

from web_kb_report import SEARCH_READS, observed_passages, percentiles, usage

LEGACY = "run-recovery"
PROTOCOL_STOPS = {"blocked", "isolation_error", "model_mismatch", "quota_unavailable", "interrupted", "catalog_drift"}


def private_root(override):
    if override is None:
        common = Path(check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                   text=True).strip())
        if common.name != ".git":
            raise ValueError("Set --history-root to your private benchmark directory")
        override = common.parent / ".local" / "benchmark" / "web-vs-kb"
    root = override.resolve()
    if not root.is_dir() or root.stat().st_mode & 0o077:
        raise ValueError("Use an existing private history directory (mode 0700)")
    git = ["git", "-C", str(root)]
    location = run([*git, "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if location.stdout.strip() == "true":
        ignored = run([*git, "check-ignore", "-q", "--", "."], capture_output=True).returncode == 0
        if not ignored or check_output([*git, "ls-files", "--", "."], text=True).strip():
            raise ValueError("The history directory must be ignored and untracked inside a Git worktree")
    return root


def attempt(directory, qid, arm):
    name = hashlib.sha256(qid.encode()).hexdigest() + "-" + arm + ".json"
    path = directory / "episodes" / name
    if not path.is_file():
        return None
    row = json.loads(path.read_text())
    if (row["id"], row["arm"]) != (qid, arm):
        raise ValueError("Episode identity does not match its frozen question and arm")
    return row


def read_manifest(directory, pack_hash):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["pack_sha256"] != pack_hash:
        raise ValueError(f"Question pack hash differs for {directory.name}")
    return manifest


def baseline(root, pack_hash, write=None):
    order = read_manifest(root / LEGACY, pack_hash)["order"]
    records = {arm: {} for arm in ("web-only", "web-plus-kb")}
    for qid, _ in order:
        for arm, ledger in records.items():
            if row := attempt(root / LEGACY, qid, arm):
                ledger[qid] = row
    ids = [qid for qid, _ in order if all(qid in rows for rows in records.values())]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("The historical web and KB runs need a unique shared cohort")
    cohort = root / "cohort.json"
    pinned = {"pack_sha256": pack_hash, "order": ids}
    if cohort.exists():
        if json.loads(cohort.read_text()) != pinned:
            raise ValueError("The shared historical cohort differs from the archive's frozen order")
    elif write:
        write(cohort, pinned)
    return ids, {arm: {qid: rows[qid] for qid in ids} for arm, rows in records.items()}


def load_runs(root, pack_hash, ids, reference):
    settings = read_manifest(root / LEGACY, pack_hash)["settings"]
    entries = [(f"{LEGACY}/{arm}", rows, {"legacy": True, "batch_width": 1,
                                         "model": settings.get("model"), "cli": settings.get("cli_version")})
               for arm, rows in reference.items()]
    skipped = []
    prior_filters = [(path, "web-plus-kb-filter") for path in sorted(root.glob("decision-filter-*"))
                     if (path / "manifest.json").is_file()]
    new_runs = [(path, "web-plus-kb") for path in sorted((root / "runs").glob("*"))
                if (path / "manifest.json").is_file()]
    dated = []
    for directory, arm in prior_filters + new_runs:
        name = directory.relative_to(root).as_posix()
        try:
            manifest = read_manifest(directory, pack_hash)
        except ValueError:
            skipped.append(name)
            continue
        selected = [item if isinstance(item, str) else item[0] for item in manifest["order"]]
        if len(selected) != len(ids) or set(selected) != set(ids):
            skipped.append(name)
            continue
        rows = {qid: row for qid in ids if (row := attempt(directory, qid, arm))}
        config = manifest.get("settings", {})
        profile = {
            "legacy": arm == "web-plus-kb-filter",
            "batch_width": manifest.get("parallel_workers", 1),
            "rerank": manifest.get("filter", config.get("search_controls", {})).get("rerank"),
            "model": config.get("model"),
            "cli": config.get("cli_version"),
            "instructions_match_baseline": config.get("instructions") == settings["instructions"],
            "started_utc": manifest.get("started_utc"),
        }
        dated.append((name, rows, profile))
    entries.extend(sorted(dated, key=lambda entry: (entry[2]["started_utc"] or "", entry[0])))
    return entries, skipped


def citation_coverage(row):
    found = set()
    for call in row["calls"]:
        data = call["arguments"]
        scoped = data.get("options", data.get("data", data))
        if not call.get("space_id") and isinstance(scoped, dict):
            call = {**call, "space_id": scoped.get("space_id")}
        found.update(j for j, ref in enumerate(row["citations"]) if any(observed_passages(call, ref)))
    return len(found)


def search_metrics(rows):
    methods, providers, scoring_episodes = Counter(), Counter(), 0
    for row in rows:
        scored = False
        for call in row["calls"]:
            if not call["success"] or call["name"].removeprefix("kbnethesis_") not in SEARCH_READS:
                continue
            try:
                payload = json.loads(call.get("evidence", ""))
            except ValueError:
                continue
            if not isinstance(payload, dict):
                continue
            if method := payload.get("retrieval_method"):
                methods[method] += 1
            scored |= bool(payload.get("scored_count"))
            for provider, counters in payload.get("provider_usage", {}).items():
                if counters.get("total_tokens") is not None:
                    providers[provider] += counters["total_tokens"]
        scoring_episodes += scored
    return {"retrieval_methods": dict(methods), "episodes_with_scoring": scoring_episodes,
            "provider_tokens_reported": dict(providers)}


def summary(rows):
    answers = [row for row in rows.values() if row["status"] == "ok"]
    tokens = [usage(row).get("total_tokens") for row in answers]
    return {"attempted": len(rows), "answers": len(answers),
            "outcomes": dict(Counter(r["status"] for r in rows.values())),
            "latency": distribution(wall_seconds(r) for r in answers),
            "tokens": distribution(tokens),
            "answers_with_observed_citation": sum(citation_coverage(row) > 0 for row in answers),
            **search_metrics(rows.values())}


def distribution(values):
    observed = [value for value in values if value is not None]
    return {**percentiles(observed), "p50": median(observed) if observed else None}


def wall_seconds(row):
    return row.get("wall_seconds", row.get("seconds"))


def paired(reference, current):
    pairs = [(reference[qid], row) for qid, row in current.items() if qid in reference]
    answered = [(old, new) for old, new in pairs if old["status"] == new["status"] == "ok"]
    elapsed = [b - a for old, new in answered
               if (a := wall_seconds(old)) is not None and (b := wall_seconds(new)) is not None]
    tokens = [(a, b) for old, new in answered
              if (a := usage(old).get("total_tokens")) is not None
              and (b := usage(new).get("total_tokens")) is not None]
    return {"common_attempts": len(pairs), "joint_answers": len(answered),
            "gained": sum(a["status"] != "ok" and b["status"] == "ok" for a, b in pairs),
            "lost": sum(a["status"] == "ok" and b["status"] != "ok" for a, b in pairs),
            "elapsed_pairs": len(elapsed), "median_seconds_delta": median(elapsed) if elapsed else None,
            "token_pairs": len(tokens), "codex_token_change_pct":
                (sum(b for a, b in tokens) / sum(a for a, b in tokens) - 1) * 100
                if tokens and sum(a for a, b in tokens) else None}


def history_report(root, pack_hash, ids, baseline_rows, write, out=None):
    with (root / ".history.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return build_report(root, pack_hash, ids, baseline_rows, write, out)


def build_report(root, pack_hash, ids, baseline_rows, write, out):
    runs, skipped = load_runs(root, pack_hash, ids, baseline_rows)
    baseline_name = f"{LEGACY}/web-plus-kb"
    web_name = f"{LEGACY}/web-only"
    comparisons = {}
    for name, rows, profile in runs:
        comparisons[name] = {"profile": profile, **summary(rows),
                             "complete": (len(rows) == len(ids)
                                          and not any(r["status"] in PROTOCOL_STOPS for r in rows.values())),
                             "vs_original_web": paired(baseline_rows["web-only"], rows) if name != web_name else None,
                             "vs_original_kb": paired(baseline_rows["web-plus-kb"], rows) if name != baseline_name else None}
    previous = None
    for name, rows, _ in runs:
        if name != web_name and previous is not None:
            previous_name, previous_rows = previous
            comparisons[name]["vs_previous_complete_kb"] = {"run": previous_name, **paired(previous_rows, rows)}
        if name != web_name and comparisons[name]["complete"]:
            previous = (name, rows)
    payload = {"pack_sha256": pack_hash, "cohort_size": len(ids), "runs": comparisons, "skipped": skipped,
               "factual_accuracy": "ungraded"}

    def fmt(value, spec):
        return format(value, spec) if value is not None else "Unknown"

    lines = ["# kbnethesis benchmark history", "", f"Frozen historical cohort of **{len(ids)} questions**.", "",
             "| Run | Responses / attempted | Median s | P95 s | Median Codex tokens | Observed citations | Scoring episodes |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, row in comparisons.items():
        lines.append(f"| {name} | {row['answers']}/{row['attempted']} | {fmt(row['latency']['p50'], '.2f')} | "
                     f"{fmt(row['latency']['p95'], '.2f')} | {fmt(row['tokens']['p50'], ',')} | "
                     f"{row['answers_with_observed_citation']}/{row['answers']} | {row['episodes_with_scoring']} |")
    lines += ["", "## Paired changes against original web + kbnethesis", "",
              "| Run | Joint responses | Gains / losses | Median time change (s) | Total Codex token change |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for name, row in comparisons.items():
        pair = row["vs_original_kb"]
        if pair is not None and name != web_name:
            lines.append(f"| {name} | {pair['joint_answers']} | +{pair['gained']} / −{pair['lost']} | "
                         f"{fmt(pair['median_seconds_delta'], '+.2f')} | "
                         f"{fmt(pair['codex_token_change_pct'], '+.1f')}% |")
    lines += ["", "Latency uses elapsed worker time including cleanup to match the original timer. "
              "Latency and token columns use responses with telemetry. Paired time and tokens use the same "
              "questions answered by both arms and the JSON gives exact coverage. Decision-model usage is reported "
              "separately in JSON. A response can be a clarification. Citation coverage checks for an observed original. "
              "Factual accuracy is ungraded.", "",
              "Historical and recent runs can differ in discovery handling, instructions, concurrency, live web results "
              "and C0 contents. The original web runner stopped on empty discovery. Check manifests and outcomes before "
              "attributing differences to a retrieval setting."]
    if skipped:
        lines += ["", "Skipped runs with a different frozen pack or cohort: " + ", ".join(skipped)]
    report = "\n".join(lines) + "\n"
    for directory in (root,) if out is None else (root, out):
        write(directory / "history.json", payload)
        write(directory / "history.md", report, raw=True)
    return root / "history.md"
