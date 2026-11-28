"""The study's private corpus pin covers every evidence surface it admits."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from web_kb_episode import Blocked
from web_kb_snapshot import inventory, metadata_result


class Metadata:
    def __init__(self):
        self.store = {
            "get_profile": {"id": "account", "nickname": "private account name"},
            "spaces_list": {"spaces": [{"id": "space", "role": "reader", "revision": 1}]},
            "sources_list": {"sources": [{"id": "s", "revision": 5, "deleted": True, "title": "secret title"}]},
            "source_versions_list": {"versions": [{"id": "v", "source_id": "s", "number": 3, "generation": 2,
                                                   "content_hash": "hash", "state": "ready"}]},
            "wiki_pages_list": {"pages": [{"id": "page", "revision": 1, "title": "secret article"}]},
            "objects_changes": {"events": [{"id": 2}]},
            "knowledge_changes": {"changes": [{"id": 1}]},
            "knowledge_index_status": {"configured": False, "indexed": 0},
        }

    async def __call__(self, name, **args):
        response = deepcopy(self.store[name])
        if name not in ("get_profile", "spaces_list"):
            assert args["space_id"] == "space"
        if name in ("sources_list", "wiki_pages_list"):
            assert args["include_deleted"] is True
        if name == "source_versions_list":
            assert args["source_id"] == "s"
        if name in ("knowledge_changes", "objects_changes"):
            key, = response
            response[key] = [p for p in response[key] if p["id"] > args["after"]][:args["limit"]]
        elif "offset" in args:
            key, = response
            response[key] = response[key][args["offset"]:args["offset"] + args["limit"]]
        return response


@pytest.mark.parametrize(("name", "key", "field", "value"), [
    ("get_profile", None, "id", "other-account"),
    ("spaces_list", "spaces", "role", "editor"),
    ("sources_list", "sources", "deleted", False),
    ("source_versions_list", "versions", "generation", 3),
    ("source_versions_list", "versions", "content_hash", "replacement"),
    ("wiki_pages_list", "pages", "revision", 2),
    ("objects_changes", "events", "id", 3),
    ("knowledge_changes", "changes", "id", 3),
    ("knowledge_index_status", None, "configured", True),
])
def test_relevant_change_invalidates_compact_metadata_manifest(name, key, field, value):
    api = Metadata()
    baseline = asyncio.run(inventory(api))
    assert "secret" not in json.dumps(baseline) and "private account name" not in json.dumps(baseline)
    row = api.store[name] if key is None else api.store[name][key][0]
    row[field] = value
    assert asyncio.run(inventory(api)) != baseline


def test_state_change_during_scan_is_rejected():
    api = Metadata()

    async def racing(name, **args):
        if name == "sources_list" and len(api.store["knowledge_changes"]["changes"]) == 1:
            api.store["knowledge_changes"]["changes"].append({"id": 2})
        return await api(name, **args)

    with pytest.raises(ValueError, match="changed during corpus verification"):
        asyncio.run(inventory(racing))


def test_pagination_cannot_repeat_or_associate_a_foreign_source():
    api = Metadata()
    api.store["spaces_list"]["spaces"] *= 2
    with pytest.raises(ValueError, match="pagination"):
        asyncio.run(inventory(api))
    api = Metadata()
    api.store["source_versions_list"]["versions"][0]["source_id"] = "other"
    with pytest.raises(ValueError, match="Invalid source version"):
        asyncio.run(inventory(api))


def test_broker_metadata_decode_is_private_and_fails_closed():
    assert metadata_result("spaces_list", {"structuredContent": {"spaces": []}}) == {"spaces": []}
    assert metadata_result("get_profile", {"content": [{"type": "text", "text": '{"id":"valid"}'}]}) == {"id": "valid"}
    with pytest.raises(Blocked, match="^Corpus verification failed at sources_list$"):
        metadata_result("sources_list", {"content": [{"type": "text", "text": "private failure detail"}]})
    with pytest.raises(Blocked):
        metadata_result("sources_list", {"isError": True, "structuredContent": {"sources": []}})


def test_snapshot_reads_only_selected_spaces():
    api = Metadata()
    first = api.store["spaces_list"]["spaces"][0]["id"]
    api.store["spaces_list"]["spaces"].append({"id":"unrelated","revision":1,"role":"reader"})
    async def restricted(name, **args):
        assert args.get("space_id") != "unrelated"
        return await api(name, **args)
    result = asyncio.run(inventory(restricted, {first}))
    assert set(result["spaces"]) == {first}
    with pytest.raises(ValueError,match="unavailable"):
        asyncio.run(inventory(restricted, {"unavailable"}))
