# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Paired, question-level scoring of frozen blind reviews."""
import json
import math
import random
import re
from collections import Counter
from statistics import mean, median, NormalDist
from urllib.parse import urlsplit, urlunsplit


ARMS = ("web-only", "web-plus-kb")
CANDIDATE = "web-plus-kb-candidate"
SEARCH_READS = {"knowledge_search", "knowledge_search_compact", "knowledge_search_structured"}
ORIGINAL_READS = {"source_documents_get", "source_document_sections_get", "documents_get",
                  "source_version_document_get", "document_chunks_list", "citations_get", "sources_search", "context_bundle_get"}


def faq_passages(result):
    """Accept a FAQ identity only on original records carrying source provenance."""
    def originals(value):
        if isinstance(value, dict):
            if isinstance(value.get("body"), str) and isinstance(value.get("metadata"), dict):
                yield value
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from originals(child)
        elif isinstance(value, list):
            for child in value:
                yield from originals(child)

    for index, call in enumerate(result["calls"]):
        if (call["kind"] != "kb" or not call.get("success")
                or call.get("name", "").removeprefix("kbnethesis_") not in ORIGINAL_READS):
            continue
        try:
            payload = json.loads(call.get("evidence", ""))
        except ValueError:
            continue
        for doc in originals(payload):
            meta = doc["metadata"]
            url = meta.get("original_url") or meta.get("url")
            if not isinstance(url, str):
                continue
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not re.search(r"/solutions/articles/\d+", parsed.path):
                continue
            yield {"call": index, "url": url, "body": doc["body"]}


def validate_faq(matches, result, grade):
    if not isinstance(matches, list):
        raise ValueError("FAQ attribution must be a list of exact citation and passage matches")
    choices = list(faq_passages(result))
    for match in matches:
        i, j, quote = match["citation"], match["call"], match["quote"]
        if (type(i) is not int or not 0 <= i < len(result["citations"])
                or not grade["citation_validity"][i] or not any(grade["supported_facts"])
                or not isinstance(quote, str) or not quote.strip()
                or not any(link["fact"] >= 0 and link["citation"] == i and link["call"] == j
                           and link["quote"] == quote for link in grade["evidence_links"])
                or not any(p["call"] == j and p["url"] == result["citations"][i]
                           and quote in p["body"] for p in choices)):
            raise ValueError("FAQ attribution must resolve to the cited original and an observed passage")


def percentiles(values):
    ordered = sorted(v for v in values if v is not None)
    return {"n": len(ordered), **{
        label: ordered[math.ceil(len(ordered) * p) - 1] if ordered else None
        for label, p in (("p50", .5), ("p95", .95))
    }}


def fraction(a, b):
    return a / b if b else None


def paired_interval(deltas):
    """Invert the matched multinomial score test for P(gain) - P(loss)."""
    n = len(deltas)
    if not n:
        return None
    gains, losses = deltas.count(1), deltas.count(-1)
    estimate = (gains - losses) / n
    limit = NormalDist().inv_cdf(.975) ** 2

    def accepted(delta):
        # Restricted likelihood estimate of P(gain) + P(loss).
        b = (gains + losses + (gains - losses) * delta) / n
        c = ((losses - gains) * delta + (n - gains - losses) * delta ** 2) / n
        discordance = min(1, max(abs(delta), (b + math.sqrt(max(0, b*b + 4*c))) / 2))
        return n * (estimate - delta) ** 2 <= limit * (discordance - delta ** 2)

    def bound(outside):
        inside = estimate
        if accepted(outside):
            return outside
        for _ in range(55):
            mid = (inside + outside) / 2
            if accepted(mid):
                inside = mid
            else:
                outside = mid
        return inside

    return [bound(-1), bound(1)]


def source_references(obj, space):
    meta = obj.get("metadata") or {}
    ids = {obj.get(key) for key in ("chunk_id", "document_id", "version_id", "revision_id", "id")}
    ids.update((meta.get("original_url"), meta.get("url")))
    if space and obj.get("version_id"):
        ids.add(f"c0://spaces/{space}/source-versions/{obj['version_id']}")
    return {value for value in ids if isinstance(value, str) and value}


UUID_PATTERN = re.compile(r"(?<![a-z0-9-])[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}(?![a-z0-9-])", re.I)


def page_identity(url):
    """Compare observed page identities, keeping the revision, path and query."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    parts = parsed.path.split("/")
    if parsed.netloc == "raw.githubusercontent.com" and len(parts) >= 5:
        parts = ["", parts[1].lower(), parts[2].lower(), "blob", *parts[3:]]
        return ("github.com", "/".join(parts), parsed.query)
    if parsed.netloc == "github.com" and len(parts) >= 5 and parts[3] == "blob":
        parts[1:3] = [v.lower() for v in parts[1:3]]
        return ("github.com", "/".join(parts), parsed.query)
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, parsed.query, ""))


def matches_reference(citation, identifiers, space):
    if citation in identifiers:
        return True
    # A URI claims a precise route. Never accept an unrelated URI merely because
    # it contains a familiar UUID. A page fragment remains visible to the reviewer.
    if "://" in citation:
        if not citation.startswith(("https://", "http://")) or any(c.isspace() for c in citation):
            return False
        identity = page_identity(citation)
        return identity is not None and any(identity == page_identity(value) for value in identifiers
                   if value.startswith(("https://", "http://")))
    ids = set(UUID_PATTERN.findall(citation))
    return (bool(ids & identifiers) and ids <= identifiers | {space}
            and bool(re.search(r"\b(chunk|version(?:e)?|revision(?:e)?|document(?:o)?)(?:_id)?\b",
                               citation, re.I)))


def observed_passages(call, citation):
    """Yield only original passages bound to the submitted reference."""
    if not call.get("success"):
        return
    evidence = call.get("evidence", "")
    space = call.get("space_id")
    if call["kind"] == "web":
        if set(call["arguments"]) & {"open", "click", "find"}:
            # The broker permits one public page action. Its leading title line identifies
            # the resolved original; links mentioned later are not its identity.
            header = evidence.splitlines()[:2]
            if not header:
                return
            urls = re.findall(r"\((https?://[^\s]+)\)", header[0])
            refs = re.findall(r"【(turn[0-9]+(?:view|fetch)[0-9]+)】", " ".join(header))
            if matches_reference(citation, set(urls + refs), None):
                yield evidence
        return
    name = call["name"].removeprefix("kbnethesis_")
    if name not in ORIGINAL_READS | SEARCH_READS:
        return
    try:
        payload = json.loads(evidence)
    except ValueError:
        return
    if name in SEARCH_READS:
        for hit in payload.get("hits", []):
            for passage in [hit, *hit.get("supporting_passages", [])]:
                ref = passage.get("citation") or {}
                if ref.get("body") and matches_reference(citation, source_references(ref, space), space):
                    yield ref["body"]
        return

    if name in {"source_documents_get", "source_version_document_get"}:
        text = payload.get("body")
        if not isinstance(text, str) or payload.get("state", "ready") != "ready":
            return
        if matches_reference(citation, source_references(payload, space), space):
            yield text
        for part in payload.get("parts", []):
            if matches_reference(citation, source_references(part, space), space):
                start, end = part["start_offset"], part["end_offset"]
                if 0 <= start < end <= len(text):
                    yield text[start:end]
        return
    if name in {"context_bundle_get", "source_document_sections_get"}:
        for section in payload.get("sections", []):
            text = section.get("body", "")
            if matches_reference(citation, source_references(section, space), space):
                yield text
            for handle in section.get("citations", []):
                if matches_reference(citation, source_references(handle, space), space):
                    start = handle["selected_start"] - section["start_offset"]
                    end = handle["selected_end"] - section["start_offset"]
                    if 0 <= start < end <= len(text):
                        yield text[start:end]
        return

    def bodies(obj, inherited=()):
        if isinstance(obj, dict):
            ids = {*inherited, *source_references(obj, space)}
            for key, value in obj.items():
                if key in {"body", "text"} and isinstance(value, str) and matches_reference(citation, ids, space):
                    yield value
                elif key != "metadata":
                    yield from bodies(value, ids)
        elif isinstance(obj, list):
            for item in obj:
                yield from bodies(item, inherited)
    yield from bodies(payload)


def check_grade(grade, question, result):
    facts = grade.get("supported_facts")
    if not isinstance(facts, list) or len(facts) != len(question["required_facts"]):
        raise ValueError("Review every required fact in order")
    flags = [*facts, *(grade.get(k) for k in (
        "version_error", "appropriate_clarification", "unsupported_claims", "source_changed"
    ))]
    if any(type(v) is not bool for v in flags):
        raise ValueError("Review flags must be true or false")
    validity = grade.get("citation_validity")
    if (not isinstance(validity, list) or len(validity) != len(result["citations"])
            or any(type(v) is not bool for v in validity)):
        raise ValueError("Check each submitted citation in order")
    for citation, valid in zip(result["citations"], validity):
        if valid and not any(body for call in result["calls"] for body in observed_passages(call, citation)):
            raise ValueError("Valid citation must resolve to an observed original")
    if any(facts) and not any(validity):
        raise ValueError("Supported facts require at least one valid citation")
    if not isinstance(grade.get("rationale"), str) or not grade["rationale"].strip():
        raise ValueError("Provide a source-based grading rationale")


    bindings = grade.get("evidence_links")
    if not isinstance(bindings, list):
        raise ValueError("Map material claims to cited original passages")
    supported = set()
    for link in bindings:
        fact, citation, call = (link[k] for k in ("fact", "citation", "call"))
        if (any(type(i) is not int for i in (fact, citation, call)) or not -1 <= fact < len(facts)
                or not 0 <= citation < len(validity) or not validity[citation]
                or not 0 <= call < len(result["calls"])
                or not isinstance(link["claim"], str) or not link["claim"].strip()
                or not isinstance(link["quote"], str) or not link["quote"].strip()
                or not any(link["quote"] in body for body in observed_passages(result["calls"][call], result["citations"][citation]))):
            raise ValueError("Evidence link must resolve to an observed original and valid citation")
        if fact >= 0:
            supported.add(fact)
    if supported != {i for i, flag in enumerate(facts) if flag}:
        raise ValueError("Each credited fact needs its own observed evidence link")


def passed(question, row, grade):
    if (row["status"] != "ok" or grade["version_error"] or grade["unsupported_claims"]
            or not all(grade["citation_validity"])):
        return False
    if question["disposition"] == "clarify":
        return grade["appropriate_clarification"]
    return all(grade["supported_facts"])


def first_support_seconds(row, grade):
    """Also recognize the same cited evidence observed before a later verification read."""
    links = grade["evidence_links"]
    for index, call in enumerate(row["calls"]):
        for link in links:
            reference = row["citations"][link["citation"]]
            if index <= link["call"] and any(link["quote"] in body for body in observed_passages(call, reference)):
                return call.get("completed_seconds")
    return None


def usage(row):
    values = dict(row.get("usage") or {})
    if row.get("usage_complete") is False or row["status"] != "ok":
        if row.get("usage_complete") is not True:
            return {}
    if values.get("input_tokens") is not None and values.get("cached_input_tokens") is not None:
        values["uncached_input_tokens"] = values["input_tokens"] - values["cached_input_tokens"]
    return values


def bootstrap_ratio(rows, statistic):
    if not rows:
        return {"ratio": None, "paired_95": None}
    point = statistic(rows)
    rng = random.Random(7713)
    values = []
    for _ in range(2000):
        value = statistic(rng.choices(rows, k=len(rows)))
        if value is None:
            return {"ratio": point, "paired_95": None}
        values.append(value)
    values.sort()
    return {"ratio": point, "paired_95": [values[49], values[1949]]}


def summarize(rows, episodes, grades, faq_ids, arms=ARMS, *, acceptance=False):
    arm_stats, successes = {}, {}
    token_names = ("input_tokens", "cached_input_tokens", "uncached_input_tokens", "output_tokens",
                   "reasoning_tokens", "total_tokens")
    for arm in arms:
        keys = [(q["id"], arm) for q in rows]
        results = [episodes[k] for k in keys]
        for q, k in zip(rows, keys):
            successes[k] = passed(q, episodes[k], grades[k])
        answerable = [k for q,k in zip(rows, keys) if q["disposition"] == "answer"]
        supported = sum(successes[k] for k in answerable)
        totals = [usage(r).get("total_tokens") for r in results]
        times = [r.get("seconds") for r in results]
        calls = [c for r in results for c in r["calls"]]
        first = []
        for k in keys:
            first.append(first_support_seconds(episodes[k], grades[k]))
        arm_stats[arm] = {
            "episode_status": dict(Counter(r["status"] for r in results)),
            "supported_answers": supported, "answerable": len(answerable),
            "required_fact_coverage": mean(sum(grades[k]["supported_facts"])/len(grades[k]["supported_facts"])
                                           for k in answerable) if answerable else None,
            "clarifications_correct": sum(successes[k] for k in keys) - supported,
            "clarification_questions": len(keys) - len(answerable),
            "version_errors": sum(grades[k]["version_error"] for k in keys),
            "answers_with_unsupported_claims": sum(grades[k]["unsupported_claims"] for k in keys),
            "citations_valid": sum(sum(grades[k]["citation_validity"]) for k in keys),
            "citations_submitted": sum(len(grades[k]["citation_validity"]) for k in keys),
            "retrieval_calls": dict(Counter(c["kind"] for c in calls)),
            "calls_by_tool": dict(Counter(c["name"] for c in calls)),
            "episodes_using_connector": sum(any(c["kind"] == "kb" for c in r["calls"]) for r in results),
            "calls_by_space": dict(Counter(c.get("space_id") or "legacy_shared" for c in calls
                                           if c["kind"] == "kb" and c["name"] != "kbnethesis_spaces_list")),
            "host": {field: percentiles([r.get(field) for r in results]) for field in
                     ("setup_seconds", "catalog_seconds", "catalog_schema_bytes", "eager_schema_bytes")},
            "tool_measurements": {name: {field: percentiles([c.get(field) for c in calls if c["name"]==name])
                                         for field in ("seconds", "argument_bytes", "result_bytes")}
                                  for name in sorted({c["name"] for c in calls})},
            "seconds": percentiles(times), "first_cited_support_seconds": percentiles(first),
            "seconds_per_supported_success": fraction(sum(times), supported) if None not in times else None,
            "tokens": {name: percentiles([usage(r).get(name) for r in results]) for name in token_names},
            "tokens_per_supported_success": fraction(sum(totals), supported) if None not in totals else None,
            "faq_supported_questions": sum((k in faq_ids or k[0] in faq_ids and arm == ARMS[1]) for k in keys),
        }
    comparisons = {}
    for baseline, candidate in zip(arms, arms[1:]):
        comparison = []
        time_pairs, token_rows, time_deltas = [], [], []
        for q in rows:
            a, b = [(q["id"], arm) for arm in (baseline, candidate)]
            x,y = successes[a], successes[b]
            comparison.append(int(y)-int(x))
            t,u = [episodes[k].get("seconds") for k in (a,b)]
            if None not in (t,u):
                time_deltas.append(u-t)
                if x and y:
                    time_pairs.append((t,u))
            tx,ty = [usage(episodes[k]).get("total_tokens") for k in (a,b)]
            if None not in (tx,ty):
                token_rows.append((tx,ty, int(x and q["disposition"]=="answer"),
                                   int(y and q["disposition"]=="answer")))

        def token_ratio(sample):
            a,b,x,y = map(sum, zip(*sample))
            return fraction(b*x, a*y) if x and y else None

        latency = bootstrap_ratio(time_pairs, lambda sample: fraction(
            median(pair[1] for pair in sample), median(pair[0] for pair in sample)))
        tokens = bootstrap_ratio(token_rows if len(token_rows)==len(rows) else [], token_ratio)
        interval = paired_interval(comparison)
        comparisons[candidate] = {
            "baseline": baseline, "success_difference_pp": 100*mean(comparison) if comparison else None,
            "paired_score_95_pp": [100*v for v in interval] if interval else None,
            "gains": comparison.count(1), "losses": comparison.count(-1),
            "paired_seconds_difference": percentiles(time_deltas),
            "joint_success_pairs": len(time_pairs), "joint_success_latency": latency,
            "tokens_per_supported_answer": tokens,
            "quality_gate": interval[0] > -.05 if acceptance and interval else None,
            "latency_target": latency["ratio"] <= .85 if acceptance and latency["ratio"] is not None else None,
            "token_target": tokens["ratio"] <= .8 if acceptance and tokens["ratio"] is not None else None,
        }
    return {"questions": len(rows), "arms": arm_stats, "comparisons": comparisons,
            "source_changed_question_ids": [q["id"] for q in rows if
                                           any(grades[q["id"], arm]["source_changed"] for arm in arms)]}
