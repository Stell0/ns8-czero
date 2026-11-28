"""Regression checks for pairing, non-replay, missing telemetry and blinded scoring."""
import importlib.util
import json
import os
import sys
import types
from collections import Counter
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("web_kb_cli", SCRIPTS / "web-vs-kb.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def smoke(arms=cli.ARMS):
    return {"status": "ok", "episodes": {a: {"catalog_sha256": a} for a in arms}}


def questions(n=25):
    return [{"id": f"{lang}-{source}-{i}", "question": f"question {lang} {source} {i}",
             "language": lang, "source_type": source, "disposition": "answer",
             "required_facts": ["fact"]}
            for lang in ("it", "en") for source in ("documentation", "issue") for i in range(n)]


def test_schedule():
    order = cli.schedule(questions(), 71)
    assert cli.schedule(questions(), 71) == order
    assert len(set(qid for qid, _ in order)) == 100
    assert Counter(arms[0] for _, arms in order) == {arm: 50 for arm in cli.ARMS}
    assert all(set(arms) == set(cli.ARMS) for _, arms in order)


def test_preparation_exposes_only_public_passages_and_balances_clarification():
    from web_kb_prepare import packets
    sources = [{"source_type": k, "url": k, "body": "secret KB addition",
                "public_body": "public original"} for k in ("documentation", "issue")]
    items = list(packets(sources))
    tasks = [t for item in items for t in item["tasks"]]
    assert all(text == ["public original"] for p in items for text in p["originals"].values())
    assert Counter(t["language"] for t in tasks if t["disposition"] == "clarify") == {"en": 5, "it": 5}
    assert Counter((t["language"], t["source_type"]) for t in tasks) == {
        (lang, kind): 25 for lang in ("en", "it") for kind in ("documentation", "issue")}


def test_preparation_preserves_unspecified_version():
    from web_kb_prepare import check_rows
    task = {"id": "q", "language": "en", "source_type": "issue",
            "disposition": "answer", "primary_url": "original"}
    row = dict(task, version="", required_facts=["fact"],
               evidence=[{"url": "original", "first_line": 1, "last_line": 1}])
    check_rows([row], {"tasks": [task], "originals": {"original": ["fact"]}},
               {"original": {"body": "fact"}})
    assert row["version"] == "Version not specified in the selected evidence."


def test_paired_run_and_grade(tmp_path, monkeypatch):
    rows = questions(1)
    pack = tmp_path / "pack.json"
    cli.write(pack, rows)
    calls = []

    def episode(question, arm):
        calls.append((question, arm))
        kb = arm == "web-plus-kb"
        return {"status": "ok" if kb else "timeout", "catalog_sha256": arm, "calls": [{"kind": "kb", "name": "kbnethesis_source_documents_get", "success": True,
                         "evidence": json.dumps({"body":"fact", "metadata":{"url":"example"}})}] if kb else [],
                "answer": "answer" if kb else "", "seconds": 7 if kb else 180,
                "usage": {"total_tokens": 34 if kb else None}, "citations": ["example"] if kb else []}

    monkeypatch.setitem(sys.modules, "web_kb_episode", types.SimpleNamespace(
        run_episode=episode, run_preflight=smoke, settings=lambda: {}))
    results = cli.measured(pack, rows, tmp_path, 173)
    assert len(calls) == len(rows) * 2
    assert cli.measured(pack, rows, tmp_path, 173) == results
    assert len(calls) == len(rows) * 2
    cli.review_material(rows, results, tmp_path)
    cards = cli.read(tmp_path / "blind-review.json")
    for card in cards:
        assert "arm" not in card
        answered = bool(card["answer"])
        card["grade"] = dict(evidence_links=[{"fact":0, "claim":"answer", "citation":0,
                                                   "call":0, "quote":"fact"}] if answered else [], supported_facts=[answered], appropriate_clarification=False,
                             citation_validity=[True] if answered else [], source_changed=False,
                             version_error=False, unsupported_claims=False, rationale="checked")
    reviews = tmp_path / "reviews.json"
    attribution = tmp_path / "faq.json"
    cli.write(reviews, cards)
    cli.write(attribution, {q["id"]: [] for q in rows})
    cli.report(rows, results, tmp_path, reviews, attribution)
    overall = cli.read(tmp_path / "report.json")["groups"]["overall"]
    assert overall["comparisons"]["web-plus-kb"]["gains"] == len(rows)
    assert overall["comparisons"]["web-plus-kb"]["paired_score_95_pp"][0] < 100
    assert overall["arms"]["web-only"]["tokens_per_supported_success"] is None
    assert overall["arms"]["web-plus-kb"]["tokens_per_supported_success"] == 34
    assert overall["comparisons"]["web-plus-kb"]["paired_seconds_difference"]["p50"] == -173
    cli.write(reviews, cards[:-1])
    with pytest.raises(ValueError, match="Every episode"):
        cli.report(rows, results, tmp_path, reviews, attribution)


def test_interrupted_episode_not_replayed(tmp_path, monkeypatch):
    pack = tmp_path / "pack.json"
    cli.write(pack, [])
    count = []

    def interrupted(*args):
        count.append(args)
        raise KeyboardInterrupt()

    runner = types.SimpleNamespace(run_episode=interrupted, run_preflight=smoke,
                                   settings=lambda: {})
    monkeypatch.setitem(sys.modules, "web_kb_episode", runner)
    with pytest.raises(KeyboardInterrupt):
        cli.measured(pack, questions(1), tmp_path, 1)
    runner.run_episode = lambda q, a: {"status": "ok", "catalog_sha256": a, "answer": "", "citations": [], "calls": []}
    results = cli.measured(pack, questions(1), tmp_path, 1)
    assert Counter(r["status"] for r in results.values()) == {"interrupted": 1, "ok": 7}
    assert len(count) == 1


@pytest.mark.parametrize("result", [{"status": "blocked"}, {"status": "ok", "catalog_sha256": "changed"}])
def test_invalid_run_stops_on_resume(tmp_path, monkeypatch, result):
    pack = tmp_path / "pack.json"
    cli.write(pack, [])
    runner = types.SimpleNamespace(run_episode=lambda q, a: dict(result), run_preflight=smoke, settings=lambda: {})
    monkeypatch.setitem(sys.modules, "web_kb_episode", runner)
    for _ in range(2):
        with pytest.raises(ValueError, match="failed|catalog changed"):
            cli.measured(pack, questions(1), tmp_path, 1)


def test_faq_attribution_binds_citation_to_original():
    from web_kb_report import validate_faq
    faq = "https://support.example.com/support/solutions/articles/123"
    row = {"citations": ["https://example.com/public", faq],
           "calls": [{"kind": "kb", "name": "kbnethesis_source_documents_get", "success": True,
                      "evidence": json.dumps({"body": "FAQ evidence", "metadata": {"original_url": faq}})}]}
    marks = {"citation_validity": [True, True], "supported_facts": [True],
             "evidence_links":[{"fact":0,"citation":1,"call":0,"quote":"FAQ evidence"}]}
    with pytest.raises(ValueError, match="cited original"):
        validate_faq([{"citation": 0, "call": 0, "quote": "FAQ evidence"}], row, marks)
    validate_faq([{"citation": 1, "call": 0, "quote": "FAQ evidence"}], row, marks)
    marks["evidence_links"][0]["fact"] = -1
    with pytest.raises(ValueError):
        validate_faq([{"citation":1,"call":0,"quote":"FAQ evidence"}], row, marks)


def test_three_arm_order_is_counterbalanced():
    arms = (*cli.ARMS, cli.CANDIDATE)
    order = cli.schedule(questions(), 11, arms)
    assert all(set(row)==set(arms) for _,row in order)
    for pos in range(3):
        counts = Counter(row[pos] for _,row in order)
        assert max(counts.values()) - min(counts.values()) <= 2


def test_score_interval_keeps_uncertainty_on_zero_and_sparse_discordance():
    from web_kb_report import paired_interval
    lo, hi = paired_interval([0]*100)
    assert -.05 < lo < 0 < hi < .05
    assert hi == pytest.approx(-lo)
    assert paired_interval([0])[1] > .7
    lo, hi = paired_interval([0]*98 + [1, 1])
    assert lo < .02 < hi
    assert paired_interval([-1]*4)[1] < 1


def test_wrong_original_mixed_citations_and_unsupported_clarification():
    from web_kb_report import check_grade, passed
    q = {"disposition":"answer", "required_facts":["fact"]}
    row = {"status":"ok", "citations":["chunk-1", "bad"],
           "calls":[{"success":True, "kind":"kb", "name":"kbnethesis_knowledge_search_compact",
                     "evidence":json.dumps({"hits":[{"citation":{"chunk_id":"chunk-1","body":"first"}},
                                                     {"citation":{"chunk_id":"chunk-2","body":"second"}}]})}]}
    link = {"fact":0, "call":0, "citation":0, "quote":"second", "claim":"the claim"}
    grade = dict(evidence_links=[link], supported_facts=[True], citation_validity=[True,False],
                 version_error=False, appropriate_clarification=True, source_changed=False,
                 unsupported_claims=False, rationale="checked")
    with pytest.raises(ValueError, match="observed original"):
        check_grade(grade, q, row)
    link["quote"] = "first"
    check_grade(grade, q, row)
    assert not passed(q, row, grade)
    q["disposition"] = "clarify"
    grade.update(citation_validity=[True,True], unsupported_claims=True)
    assert not passed(q, row, grade)


def test_fabricated_uri_and_unbound_valid_citation_are_rejected():
    from web_kb_report import check_grade, observed_passages
    version = '5149db45-5633-4ca6-8c81-44bf03ae08da'
    call = {"success":True, "kind":"kb", "name":"kbnethesis_citations_get", "space_id":"correct",
            "evidence":json.dumps({"version_id":version, "chunk_id":"chunk", "body":"quote"})}
    for uri in ("c0://spaces/wrong/source-versions/"+version, "c0://bogus/"+version):
        assert not list(observed_passages(call, uri))
    assert list(observed_passages(call, "c0://spaces/correct/source-versions/"+version)) == ["quote"]
    q = {"required_facts":["fact"]}
    row = {"citations":["chunk", "bogus"], "calls":[call]}
    grade = dict(supported_facts=[True], citation_validity=[True,True], version_error=False,
                 unsupported_claims=False, source_changed=False, appropriate_clarification=False,
                 rationale="mixed", evidence_links=[{"fact":0,"claim":"fact","call":0,"quote":"quote","citation":0}])
    with pytest.raises(ValueError, match="Valid citation"):
        check_grade(grade, q, row)


def test_alternate_evidence_shapes_and_first_observed_support():
    from web_kb_report import observed_passages, first_support_seconds
    calls = []
    for name, payload in [
        ('sources_search', {'citations':[{'chunk_id':'chunk','body':'original'}]}),
        ('knowledge_search_structured', {'hits':[{'supporting_passages':[
            {'citation':{'chunk_id':'chunk','body':'original'}}]}]}),
        ('source_document_sections_get', {'sections':[{'body':'an original passage', 'start_offset':20,
            'citations':[{'chunk_id':'chunk','selected_start':23,'selected_end':31}]}]}),
    ]:
        call = {'name':'kbnethesis_'+name, 'kind':'kb', 'success':True,
                'evidence':json.dumps(payload), 'completed_seconds':len(calls)+1}
        assert list(observed_passages(call,'chunk')) == ['original']
        calls.append(call)
    assert first_support_seconds({'calls':calls,'citations':['chunk']},
        {'evidence_links':[{'quote':'original','call':2,'citation':0}]}) == 1


def test_multipart_version_citation_covers_only_its_part():
    from web_kb_report import observed_passages
    call = {"success":True, "kind":"kb", "name":"kbnethesis_source_version_document_get",
            "space_id":"s", "evidence":json.dumps({"state":"ready","body":"alphaβeta","parts":[
                {"version_id":"first","start_offset":0,"end_offset":5},
                {"version_id":"second","start_offset":5,"end_offset":9}]})}
    assert list(observed_passages(call,"c0://spaces/s/source-versions/second")) == ["βeta"]


def test_sealed_candidate_requires_snapshot_and_blind_adjudication(tmp_path, monkeypatch):
    arms = (*cli.ARMS, cli.CANDIDATE)
    chosen = "selection"
    config = {"candidate_profile":{"changes":["routing","compact","catalog","stopping"], "start_space":chosen}}
    monkeypatch.setenv("WEB_KB_C0_RELEASE","fixture-image")
    monkeypatch.setenv("WEB_KB_C0_CONFIG_SHA256", "f"*64)
    runner = types.SimpleNamespace(
        run_preflight=smoke, settings=lambda: dict(config),
        run_episode=lambda q,arm: {"status":"ok","catalog_sha256":arm,"answer":"Please clarify",
                                   "citations":[],"calls":[],"seconds":1,"usage":{"total_tokens":10}},
    )
    monkeypatch.setitem(sys.modules,"web_kb_episode",runner)

    async def snapshot():
        return {"principal":"reader","spaces":{chosen:{"source_count":1}}}
    monkeypatch.setitem(sys.modules,"web_kb_snapshot",types.SimpleNamespace(snapshot=snapshot))
    rows = [dict(q,disposition="clarify") for q in questions(1)]
    pack = tmp_path/"pack"
    cli.write(pack,rows)
    results = cli.measured(pack,rows,tmp_path,1,arms)
    assert len(results) == 12
    assert cli.read(tmp_path/"corpus-before.json") == cli.read(tmp_path/"corpus-after.json")
    cli.review_material(rows,results,tmp_path,arms)
    cards = cli.read(tmp_path/"blind-review.json")
    for card in cards:
        card["grade"].update(supported_facts=[False], appropriate_clarification=True,
                             unsupported_claims=False, version_error=False,
                             source_changed=False, rationale="Missing discriminator requested.")
    grades,faq = tmp_path/"grades.json", tmp_path/"faq.json"
    cli.write(grades,cards)
    cli.write(faq,{arm:{q["id"]:[] for q in rows} for arm in arms[1:]})
    with pytest.raises(ValueError,match="same operator-verified"):
        cli.report(rows,results,tmp_path,grades,faq,arms,adjudicator="independent")
    cli.report(rows,results,tmp_path,grades,faq,arms,adjudicator="independent",verified_release="fixture-image")
    unverified = cli.read(tmp_path/"report.json")
    assert not unverified["config_verified"]
    assert unverified["groups"]["overall"]["comparisons"][cli.CANDIDATE]["quality_gate"] is None
    with pytest.raises(ValueError,match="configuration differs"):
        cli.report(rows,results,tmp_path,grades,faq,arms,adjudicator="independent",
                   verified_release="fixture-image",verified_config="a"*64)
    cli.report(rows,results,tmp_path,grades,faq,arms,adjudicator="independent",
               verified_release="fixture-image",verified_config="f"*64)
    assert cli.read(tmp_path/"report.json")["config_verified"]
    verdict = (tmp_path/"report.json").read_bytes()
    cli.report(rows,results,tmp_path,grades,faq,arms,provisional=True)
    assert verdict == (tmp_path/"report.json").read_bytes()
    provisional = cli.read(tmp_path/"provisional-report.json")
    assert provisional["groups"]["overall"]["comparisons"][cli.CANDIDATE]["quality_gate"] is None
    monkeypatch.setattr(cli,"protocol_hashes",lambda: {"different":"after measurement"})
    with pytest.raises(ValueError,match="protocol differs"):
        cli.report(rows,results,tmp_path,grades,faq,arms,adjudicator="independent",verified_release="fixture-image")


def test_sealed_candidate_rejects_an_ablation(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_KB_C0_RELEASE","fixture-image")
    monkeypatch.setitem(sys.modules,"web_kb_episode",types.SimpleNamespace(run_preflight=smoke,
        run_episode=None,settings=lambda:{"candidate_profile":{"changes":["catalog"],"start_space":"s"}}))
    with pytest.raises(ValueError,match="all four"):
        cli.measured(tmp_path/"unused",[],tmp_path,1,(*cli.ARMS,cli.CANDIDATE))


def test_real_world_reference_forms_preserve_origin_and_version():
    from web_kb_report import matches_reference
    public = {"https://raw.githubusercontent.com/owner/Repo/main/build.sh"}
    assert matches_reference("https://github.com/owner/repo/blob/main/build.sh#L10-L12",public,None)
    assert not matches_reference("https://github.com/owner/repo/blob/older/build.sh#L10-L12",public,None)
    assert matches_reference("https://example.org/manual#section",{"https://example.org/manual"},None)
    observed = "5149db45-5633-4ca6-8c81-44bf03ae08da"
    foreign = "00b27f22-b905-4e5f-85eb-9814b291d0f4"
    assert matches_reference("Support manual — chunk "+observed,{observed},None)
    assert not matches_reference("wrong space "+foreign+" — chunk "+observed,{observed},None)
    assert not matches_reference("c0://wrong/path/"+observed,{observed},None)


def test_rerun_reuses_legacy_cohort_and_keeps_history_private(tmp_path, monkeypatch):
    import hashlib
    from web_kb_history import baseline
    import web_kb_dataset

    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    pack = root / "pack.json"
    pack.write_text("{}")
    monkeypatch.setattr(web_kb_dataset, "load_pack",
                        lambda path: [{"id": qid, "question": "question " + qid} for qid in ("q1", "q2")])
    legacy = root / "run-recovery"
    (legacy / "episodes").mkdir(parents=True)

    def record(directory, arm, qid, status, seconds, tokens, **fields):
        name = hashlib.sha256(qid.encode()).hexdigest() + "-" + arm + ".json"
        cli.write(directory / "episodes" / name,
                  dict(id=qid, arm=arm, status=status, seconds=seconds,
                       calls=[], citations=[], usage={"total_tokens": tokens}, **fields))

    old = {"pack_sha256": cli.digest(pack), "order": [["q1", list(cli.ARMS)], ["q2", list(cli.ARMS)]],
           "settings": {"instructions": "old"}}
    cli.write(legacy / "manifest.json", old)
    record(legacy, "web-only", "q1", "resource_discovery_attempt", 1, None)
    record(legacy, "web-plus-kb", "q1", "ok", 10, 100)
    record(legacy, "web-plus-kb", "q2", "ok", 8, 90)
    assert baseline(root, cli.digest(pack))[0] == ["q1"]

    filtered = root / "decision-filter-historical"
    (filtered / "episodes").mkdir(parents=True)
    cli.write(filtered / "manifest.json", {**old, "order": ["q1"], "filter": {"rerank": "filter"}})
    record(filtered, "web-plus-kb-filter", "q1", "ok", 11, 105)
    older = root / "runs/z-an-earlier-run"
    (older / "episodes").mkdir(parents=True)
    cli.write(older / "manifest.json", {**old, "order": [["q1", ["web-plus-kb"]]],
                                        "started_utc": "2026-11-28T09:00:00+00:00"})
    record(older, "web-plus-kb", "q1", "ok", 10, 95)

    def measured(path, questions, out, seed, arms, *, development, fixed_order):
        assert questions == [{"id": "q1", "question": "question q1"}]
        assert arms == ("web-plus-kb",) and development and fixed_order == ["q1"]
        assert os.environ["WEB_KB_SEARCH_RERANK"] == "instance"
        (out / "episodes").mkdir()
        cli.write(out / "manifest.json", {**old, "order": [["q1", list(arms)]],
                                         "started_utc": "2026-11-28T10:00:00+00:00"})
        record(out, arms[0], "q1", "ok", 6, 80, wall_seconds=7)

    monkeypatch.setattr(cli, "measured", measured)
    monkeypatch.setenv("WEB_KB_SEARCH_RERANK", "off")
    monkeypatch.setattr(sys, "argv", ["web-vs-kb.py", "rerun", "--history-root", str(root),
                                     "--run-id", "new"])
    old_umask = os.umask(0o077)
    try:
        assert cli.main() == 0
    finally:
        os.umask(old_umask)
    run = cli.read(root / "history.json")["runs"]["runs/new"]
    assert run["vs_original_kb"]["median_seconds_delta"] == -3
    assert run["vs_original_kb"]["token_pairs"] == 1
    assert run["vs_original_web"]["gained"] == 1
    assert run["vs_previous_complete_kb"]["run"] == "runs/z-an-earlier-run"
    assert (root / "runs/new/history.md").stat().st_mode & 0o077 == 0
    assert cli.read(legacy / "manifest.json") == old
    record(legacy, "web-only", "q2", "ok", 9, 125)
    with pytest.raises(ValueError, match="cohort differs"):
        baseline(root, cli.digest(pack))


def test_history_rejects_changed_pack(tmp_path):
    from web_kb_history import read_manifest
    cli.write(tmp_path / "manifest.json", {"pack_sha256": "original"})
    with pytest.raises(ValueError, match="pack hash differs"):
        read_manifest(tmp_path, "changed")


def test_history_rejects_visible_worktree_directory(tmp_path):
    from subprocess import run
    from web_kb_history import private_root
    run(["git", "init", "--quiet", str(tmp_path)], check=True)
    archive = tmp_path / "archive"
    archive.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="ignored and untracked"):
        private_root(archive)
    (tmp_path / ".gitignore").write_text("archive/\n")
    assert private_root(archive) == archive


def test_rerun_records_catalog_drift_as_failure(tmp_path, monkeypatch):
    import hashlib
    pack = tmp_path / "pack.json"
    cli.write(pack, [])
    monkeypatch.setitem(sys.modules, "web_kb_episode", types.SimpleNamespace(
        run_episode=lambda *_: {"status": "ok", "catalog_sha256": "changed", "answer": "answer"},
        run_preflight=smoke, settings=lambda: {}))
    rows = questions(1)
    qid = rows[0]["id"]
    for _ in range(2):
        with pytest.raises(ValueError, match="Tool catalog changed"):
            cli.measured(pack, rows, tmp_path, 173, ("web-plus-kb",), fixed_order=[qid], development=True)
    name = hashlib.sha256(qid.encode()).hexdigest() + "-web-plus-kb.json"
    assert cli.read(tmp_path / "episodes" / name)["status"] == "catalog_drift"
