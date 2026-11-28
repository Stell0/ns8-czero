"""Private replay accepts only exact standard-search reconstruction."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from czero_app.retrieval import SearchResult
from web_kb_replay import replay, size


def test_replay_ignores_other_calls_and_rejects_lost_wire_fields():
    full = SearchResult(hits=[], retrieval_method="text", fallback_reason=None, requested_mode="text",
        candidate_count=0, fallback_reasons=[], scored_count=0, scorer_truncated_candidates=0,
        provider_usage={}, graphs=[]).model_dump(mode="json")
    call = {"name": "kbnethesis_knowledge_search", "success": True, "evidence": json.dumps(full)}
    ignored = {"name": "search_service_web_run", "success": True, "evidence": "irrelevant"}
    assert replay([{"calls": [ignored, call]}]) == {
        "searches": 1, "hits": 0, "omitted_excerpts": 0, "full_bytes": size(full), "compact_bytes": size(full)}
    with pytest.raises(ValueError, match="No successful standard searches"):
        replay([{"calls": [ignored, {**call, "success": False}]}])
    with pytest.raises(ValueError, match="reconstruction differs"):
        replay([{"calls": [{**call, "evidence": json.dumps({**full, "future_field": 5})}]}])
