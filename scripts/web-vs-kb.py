# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run and score a private, paired Codex web versus web-plus-KB benchmark."""
import argparse
import asyncio
import fcntl
import hashlib
import json
import itertools
import os
import random
import re
import secrets
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

from web_kb_report import ARMS, CANDIDATE, check_grade, observed_passages, summarize, validate_faq
from web_kb_history import baseline, history_report, private_root


def read(path):
    return json.loads(path.read_text())


def write(path, value, lines=False, *, raw=False):
    if raw:
        payload = value
    elif lines:
        payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in value)
    else:
        payload = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    temp = path.with_suffix(".tmp-" + uuid.uuid4().hex)
    with temp.open("x") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_hashes():
    files = ("web-vs-kb.py", "web_kb_dataset.py", "web_kb_episode.py", "web_kb_report.py",
             "web_kb_grade.py", "web_kb_prepare.py", "web_kb_snapshot.py", "web_kb_history.py")
    return {name: digest(Path(__file__).with_name(name)) for name in files}


def schedule(questions, seed, arms=ARMS):
    groups = defaultdict(list)
    for q in questions:
        groups[q["language"], q["source_type"]].append(q["id"])
    rng = random.Random(seed)
    order = []
    permutations = list(itertools.permutations(arms))
    offset = 0
    for group in (groups[k] for k in sorted(groups)):
        rng.shuffle(group)
        order.extend((qid, list(permutations[(offset + i) % len(permutations)]))
                     for i, qid in enumerate(group))
        offset += len(group)
    rng.shuffle(order)
    return order


def measured(pack, questions, out, seed, arms=ARMS, *, development=False, exclusions=(), fixed_order=None):
    from web_kb_episode import run_episode, run_preflight, settings
    configuration = settings()
    configuration["operator_c0_release"] = os.environ.get("WEB_KB_C0_RELEASE")
    config_digest = os.environ.get("WEB_KB_C0_CONFIG_SHA256")
    if config_digest and not re.fullmatch("[0-9a-f]{64}", config_digest):
        raise ValueError("Expected lowercase SHA-256 of effective retrieval settings")
    configuration["operator_c0_config_sha256"] = config_digest
    if CANDIDATE in arms and not development:
        if not configuration["operator_c0_release"]:
            raise ValueError("Set WEB_KB_C0_RELEASE to the verified deployment version for the sealed study")
        profile = configuration["candidate_profile"]
        if set(profile["changes"]) != {"compact", "routing", "stopping", "catalog"} or not profile["start_space"]:
            raise ValueError("Sealed acceptance requires all four changes and an explicitly selected starting space")
    manifest = {
        "arms": list(arms), "development": development, "excluded_pack_sha256": sorted(exclusions), "pack_sha256": digest(pack), "seed": seed, "settings": configuration,
        "protocol_sha256": protocol_hashes(),
        "order": ([[qid, list(arms)] for qid in fixed_order] if fixed_order is not None
                  else [list(item) for item in schedule(questions, seed, arms)]),
    }
    manifest_path = out / "manifest.json"
    if fixed_order is not None:
        manifest["started_utc"] = (read(manifest_path)["started_utc"] if manifest_path.exists()
                                   else datetime.now(timezone.utc).isoformat())
    if manifest_path.exists():
        if read(manifest_path) != manifest:
            raise ValueError("Pack, seed, code, or settings changed. Preserve the original run.")
    else:
        write(manifest_path, manifest)
    smoke = run_preflight(arms)
    write(out / ("preflight-" + uuid.uuid4().hex + ".json"), smoke)
    if smoke["status"] != "ok":
        raise ValueError("Live preflight blocked. Inspect the private preflight record.")
    catalogs = {arm: smoke["episodes"][arm]["catalog_sha256"] for arm in arms}
    pin = out / "catalogs.json"
    if pin.exists() and read(pin) != catalogs:
        raise ValueError("Live tool catalog changed since the first smoke pair")
    if not pin.exists():
        write(pin, catalogs)
    if CANDIDATE in arms and not development:
        verify_snapshot(out, "before")
    episodes = out / "episodes"
    episodes.mkdir(exist_ok=True)
    by_id = {q["id"]: q for q in questions}
    results = {}
    for qid, episode_order in manifest["order"]:
        for arm in episode_order:
            # Fixed-length filenames independent of externally supplied question IDs.
            name = hashlib.sha256(qid.encode()).hexdigest() + "-" + arm
            record = episodes / (name + ".json")
            completed_before_resume = record.exists()
            if completed_before_resume:
                result = read(record)
            else:
                try:
                    (episodes / (name + ".started")).touch(exist_ok=False)
                except FileExistsError:
                    result = {"status": "interrupted", "answer": "", "calls": [], "citations": [],
                              "usage": {}, "seconds": None}
                else:
                    result = run_episode(by_id[qid]["question"], arm)
                if ((result.get("catalog_sha256") or result["status"] == "ok")
                        and result.get("catalog_sha256") != catalogs[arm]):
                    result["status"] = "catalog_drift"
                result.update(id=qid, arm=arm)
                write(record, result)
            results[qid, arm] = result
            answer_fields = ("id", "arm", "answer", "citations", "seconds", "usage", "status")
            write(out / (arm + ".jsonl"), [
                {field: row.get(field) for field in answer_fields}
                for (_, condition), row in results.items() if condition == arm
            ], lines=True)
            if result["status"] == "catalog_drift":
                raise ValueError(f"Tool catalog changed at {qid}/{arm}. Preserve this run.")
            if result["status"] in ("blocked", "isolation_error", "model_mismatch"):
                raise ValueError(f"Live capability failed at {qid}/{arm}. Inspect private episode.")
            if result["status"] == "quota_unavailable" and not completed_before_resume:
                raise ValueError("Codex inference quota reached. Resume the same run once available.")
            if (result.get("catalog_sha256") or result["status"] == "ok") and result.get("catalog_sha256") != catalogs[arm]:
                raise ValueError(f"Tool catalog changed at {qid}/{arm}. Preserve this run.")
    if CANDIDATE in arms and not development:
        verify_snapshot(out, "after")
    return results


def verify_snapshot(out, phase):
    from web_kb_snapshot import snapshot
    current = asyncio.run(snapshot())
    pin = out / "corpus-before.json"
    if pin.exists() and read(pin) != current:
        write(out / ("corpus-drift-" + uuid.uuid4().hex + ".json"), current)
        raise ValueError("Accessible corpus or provider changed. Preserve this run.")
    write(out / ("corpus-" + phase + ".json"), current)


def observations(row):
    # Keep original call numbering and bodies without revealing tool choices or catalog listings.
    material = []
    for i, call in enumerate(row["calls"]):
        for j, citation in enumerate(row["citations"]):
            for body in dict.fromkeys(observed_passages(call, citation)):
                material.append({"call": i, "citation": j, "original": body})
    return material


def review_material(questions, results, out, arms=ARMS):
    mapping = {}
    cards = []
    for q in questions:
        for arm in arms:
            result = results[q["id"], arm]
            card = secrets.token_hex(12)
            mapping[card] = [q["id"], arm]
            cards.append({"card": card, "label": q, "answer": result.get("answer", ""),
                          "citations": result["citations"], "observations": observations(result), "grade": {
                              "evidence_links": [],
                              "supported_facts": [None] * len(q["required_facts"]),
                              "citation_validity": [None] * len(result["citations"]),
                              "version_error": None, "unsupported_claims": None,
                              "source_changed": None, "appropriate_clarification": None,
                              "rationale": ""}})
    secrets.SystemRandom().shuffle(cards)
    write(out / "review-key.json", mapping)
    write(out / "blind-review.json", cards)


def report(questions, results, out, reviews, faq, arms=ARMS, *, adjudicator=None, provisional=False, verified_release=None, verified_config=None):
    frozen = read(out / "manifest.json")
    if CANDIDATE in arms and not frozen["development"] and adjudicator:
        if not verified_release or verified_release != frozen["settings"]["operator_c0_release"]:
            raise ValueError("Confirm the same operator-verified C0 release after the sealed run")
    pinned_config = frozen["settings"].get("operator_c0_config_sha256")
    config_verified = bool(pinned_config and pinned_config == verified_config)
    if verified_config and not config_verified:
        raise ValueError("Verified retrieval configuration differs from frozen configuration")
    current_protocol = protocol_hashes()
    if not frozen["development"] and current_protocol != frozen["protocol_sha256"]:
        raise ValueError("Grading or measurement protocol differs from frozen study")
    if CANDIDATE in arms and not frozen["development"] and read(out / "corpus-before.json") != read(out / "corpus-after.json"):
        raise ValueError("Corpus verification failed")
    catalogs = read(out / "catalogs.json")
    for (_, arm), row in results.items():
        if (row.get("catalog_sha256") or row["status"] == "ok") and row.get("catalog_sha256") != catalogs[arm]:
            raise ValueError("Tool catalog differs from preflight")
    if any(r["status"] in ("blocked", "isolation_error", "model_mismatch") for r in results.values()):
        raise ValueError("Protocol violation in measured episodes")
    mapping = read(out / "review-key.json")
    by_id = {q["id"]: q for q in questions}
    grades = {}
    for card in read(reviews):
        key = tuple(mapping[card["card"]])
        if key in grades:
            raise ValueError("Duplicate review card")
        original = results[key]
        if card["grade"].get("needs_review"):
            raise ValueError("Resolve the outstanding source check for card " + card["card"])
        if (card["label"] != by_id[key[0]] or card["answer"] != original.get("answer", "")
                or card["observations"] != observations(original) or card["citations"] != original["citations"]):
            raise ValueError("Review card content changed")
        grades[key] = card["grade"]
        check_grade(grades[key], by_id[key[0]], original)
    if grades.keys() != results.keys():
        raise ValueError("Every episode needs a review")
    attributions = read(faq)
    kb_arms = set(arms) - {"web-only"}
    if arms == ARMS and set(attributions) == set(by_id):  # legacy manual attribution file
        attributions = {"web-plus-kb": attributions}
    if set(attributions) != kb_arms:
        raise ValueError("Check FAQ attribution separately for every KB arm")
    faq_ids = set()
    for arm, entries in attributions.items():
        if set(entries) != set(by_id):
            raise ValueError("Check FAQ attribution for every question")
        for qid, matches in entries.items():
            key = qid, arm
            validate_faq(matches, results[key], grades[key])
            if matches:
                faq_ids.add(key)
    groups = {"overall": questions}
    for field in ("language", "source_type"):
        for value in sorted({q[field] for q in questions}):
            groups[value] = [q for q in questions if q[field] == value]
    groups["stable_sources"] = [q for q in questions if not any(
        grades[q["id"], arm]["source_changed"] for arm in arms)]
    development = read(out / "manifest.json")["development"]
    filename = "provisional-report.json" if provisional else "report.json"
    write(out / filename, {
        "config_verified": config_verified, "verified_config_after": verified_config,
        "verified_release_after": verified_release, "report_protocol_sha256": current_protocol, "adjudicator": adjudicator, "provisional": adjudicator is None,
        "manifest_sha256": digest(out / "manifest.json"),
        "reviews_sha256": digest(reviews), "faq_attribution_sha256": digest(faq),
        "development": development,
        "groups": {k: summarize(g, results, grades, faq_ids, arms,
                                acceptance=bool(adjudicator) and config_verified and not development and k=="overall") for k, g in groups.items()},
    })


def historical(args):
    from web_kb_dataset import load_pack

    root = private_root(args.history_root)
    pack = root / "pack.json"
    questions = {q["id"]: q for q in load_pack(pack)}
    pack_hash = digest(pack)
    ids, rows = baseline(root, pack_hash, write)
    if not set(ids) <= questions.keys():
        raise ValueError("Historical episodes do not match the frozen question pack")
    if args.action == "history":
        print(history_report(root, pack_hash, ids, rows, write))
        return 0
    os.environ["WEB_KB_SEARCH_RERANK"] = args.rerank or "instance"
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S-%fZ")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", run_id):
        raise ValueError("Run ID must be a simple directory name")
    out = root / "runs" / run_id
    if not out.resolve().is_relative_to(root):
        raise ValueError("Run directory must remain in private benchmark history")
    out.mkdir(parents=True, exist_ok=True)
    if out.stat().st_mode & 0o077:
        raise ValueError("Use a private run directory (mode 0700)")
    print(f"Measuring {len(ids)} historical questions in {out}", flush=True)
    with (out / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            measured(pack, [questions[qid] for qid in ids], out, args.seed, ("web-plus-kb",),
                     development=True, fixed_order=ids)
        finally:
            print(history_report(root, pack_hash, ids, rows, write, out))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("rerun", "history", "study", "preflight", "run", "report"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--seed", type=int, default=173)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--faq-attribution", type=Path)
    parser.add_argument("--candidate", action="store_true",
                        help="Measure web-only, current C0 and candidate C0 on the same questions")
    parser.add_argument("--dev-per-stratum", type=int, choices=range(1,25), metavar="1..24",
                        help="Exploratory sample per language/source group; excluded from acceptance")
    parser.add_argument("--exclude-pack", type=Path, action="append", default=[],
                        help="Previously exposed question pack, repeat for each development/pilot pack")
    parser.add_argument("--adjudicator", help="Independent reviewer who verified the blinded grades")
    parser.add_argument("--verified-c0-release", help="Operator-verified C0 release after sealed measurement")
    parser.add_argument("--verified-config-sha256", help="Post-run fingerprint of effective C0 retrieval settings")
    parser.add_argument("--history-root", type=Path, help="Existing private folder with the frozen pack and baselines")
    parser.add_argument("--run-id", help="Private run directory name for a new run or an exact resume")
    parser.add_argument("--rerank", choices=("instance", "off", "rerank", "filter"),
                        help="C0 relevance policy for the rerun (instance default if omitted) or preflight")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action in ("rerun", "history"):
        if args.output or args.pack or args.candidate or args.dev_per_stratum:
            parser.error("Historical comparison uses the private root and its frozen cohort")
        return historical(args)
    if not args.output:
        parser.error("--output required")
    if args.rerank:
        if args.action != "preflight":
            parser.error("--rerank applies to rerun or preflight")
        os.environ["WEB_KB_SEARCH_RERANK"] = args.rerank
    arms = (*ARMS, CANDIDATE) if args.candidate else ARMS
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if out.stat().st_mode & 0o077:
        parser.error("Use a private output directory (mode 0700)")
    with (out / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "preflight":
            from web_kb_episode import run_preflight
            smoke = run_preflight(arms)
            write(out / ("preflight-" + uuid.uuid4().hex + ".json"), smoke)
            return 0 if smoke["status"] == "ok" else 2
        if args.action in ("study", "run") and args.candidate and not args.dev_per_stratum:
            if not args.exclude_pack:
                parser.error("For sealed candidate measurement supply --exclude-pack for the exposed pilot/development packs")
        if args.action == "study" and args.candidate and not args.pack:
            # Check the installed candidate before generating and exposing a fresh question set.
            from web_kb_episode import run_preflight
            probe = run_preflight(arms)
            write(out / ("preparation-preflight-" + uuid.uuid4().hex + ".json"), probe)
            if probe["status"] != "ok":
                raise ValueError("Candidate preflight blocked before question generation")
        if args.action == "study" and not args.pack:
            from web_kb_dataset import capture_sources, verify_public
            from web_kb_prepare import prepare
            sources = out / "sources.json"
            args.pack = out / "preparation" / "pack.json"
            if not args.pack.exists():
                if not sources.exists():
                    write(sources, verify_public(asyncio.run(capture_sources())))
                args.pack.parent.mkdir(exist_ok=True)
                asyncio.run(prepare(sources, args.pack.parent))
        if not args.pack:
            parser.error("--pack required")
        from web_kb_dataset import load_pack
        questions = load_pack(args.pack)
        exclusions = []
        if args.action == "report":
            frozen = read(out / "manifest.json")
            selected = {qid for qid, _ in frozen["order"]}
            questions = [q for q in questions if q["id"] in selected]
        elif args.dev_per_stratum:
            strata = defaultdict(list)
            for q in questions:
                strata[q["language"], q["source_type"]].append(q)
            rng = random.Random(args.seed)
            questions = [q for group in sorted(strata) for q in rng.sample(strata[group], args.dev_per_stratum)]
        elif args.candidate:
            normalized = {" ".join(q["question"].casefold().split()) for q in questions}
            for path in args.exclude_pack:
                if any(" ".join(q["question"].casefold().split()) in normalized for q in load_pack(path)):
                    parser.error("Sealed questions overlap an exposed pack")
                exclusions.append(digest(path))
        if args.action in ("study", "run"):
            results = measured(args.pack, questions, out, args.seed, arms,
                               development=bool(args.dev_per_stratum), exclusions=exclusions)
            if not (out / "blind-review.json").exists():
                review_material(questions, results, out, arms)
            if args.action == "run":
                print("Answer files and blind-review.json ready for independent review.")
            else:
                from web_kb_grade import grade, attribute
                cache = out / "grades"
                key = read(out / "review-key.json")
                answers = asyncio.run(grade(read(out / "blind-review.json"), key, results, cache, write, read))
                review_path = out / "model-reviews.json"
                write(review_path, answers)
                faq = asyncio.run(attribute(answers, key, results, cache, write, read))
                faq_path = out / "model-faq.json"
                write(faq_path, faq)
                report(questions, results, out, review_path, faq_path, arms, provisional=True)
                print("Private provisional report written to", out / "provisional-report.json")
        else:
            if args.candidate and not (args.adjudicator or "").strip():
                parser.error("Identify the independent blinded reviewer with --adjudicator")
            if not args.reviews or not args.faq_attribution:
                parser.error("Report requires --reviews and --faq-attribution")
            if digest(args.pack) != read(out / "manifest.json")["pack_sha256"]:
                raise ValueError("Pack differs from the measured pack")
            if list(arms) != read(out / "manifest.json")["arms"]:
                raise ValueError("Report arms differ from the run manifest")
            results = {}
            for q in questions:
                for arm in arms:
                    name = hashlib.sha256(q["id"].encode()).hexdigest() + "-" + arm
                    results[q["id"], arm] = read(out / "episodes" / (name + ".json"))
            report(questions, results, out, args.reviews, args.faq_attribution, arms,
                   adjudicator=args.adjudicator, verified_release=args.verified_c0_release,
                   verified_config=args.verified_config_sha256)
            print("Private paired report written to", out / "report.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        sys.exit(str(exc))
