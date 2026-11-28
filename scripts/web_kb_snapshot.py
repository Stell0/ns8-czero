# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fingerprint authorized evidence and read settings outside measured turns."""
import asyncio
import json

from web_kb_dataset import digest

PAGE_SIZE = 100


async def pages(call, name, key, **arguments):
    rows = {}
    while True:
        page = (await call(name, limit=PAGE_SIZE, offset=len(rows), **arguments))[key]
        if not isinstance(page, list) or len(page) > PAGE_SIZE:
            raise ValueError("Invalid inventory page at " + name)
        for item in page:
            if item["id"] in rows:
                raise ValueError("Inventory changed during pagination at " + name)
            rows[item["id"]] = item
        if len(page) < PAGE_SIZE:
            return [rows[key] for key in sorted(rows)]


async def feed_cursor(call, name, key, space, after=0):
    # Commit-order cursors capture updates to entities, claims, annotations,
    # references, objects and relations, including updates later reverted.
    cursor = after
    while True:
        rows = (await call(name, after=cursor, limit=PAGE_SIZE, space_id=space))[key]
        if not isinstance(rows, list) or len(rows) > PAGE_SIZE:
            raise ValueError("Invalid change feed at " + name)
        for row in rows:
            current = row["id"]
            if type(current) is not int or current <= cursor:
                raise ValueError("Invalid change cursor at " + name)
            cursor = current
        if len(rows) < PAGE_SIZE:
            return cursor


async def inventory(call, eligible=None):
    async def selected_spaces():
        rows = await pages(call, "spaces_list", "spaces")
        if eligible is None:
            return rows
        selected = [row for row in rows if row["id"] in eligible]
        if {row["id"] for row in selected} != eligible:
            raise ValueError("An explicitly selected C0 space is unavailable")
        return selected

    principal = (await call("get_profile"))["id"]
    if not isinstance(principal, str) or not principal:
        raise ValueError("Missing authenticated corpus principal")
    spaces = await selected_spaces()
    if not spaces:
        raise ValueError("No readable C0 space for corpus verification")
    result = {"format": 2, "principal": principal, "spaces": {}}
    for space in spaces:
        ident = space["id"]
        selector = {"space_id": ident}
        cursors = {}
        for name, key in (("knowledge_changes", "changes"), ("objects_changes", "events")):
            cursors[name] = await feed_cursor(call, name, key, ident)
        sources = await pages(call, "sources_list", "sources", include_deleted=True, **selector)
        versions = []
        for source in sources:
            selected = await pages(call, "source_versions_list", "versions", source_id=source["id"], **selector)
            for version in selected:
                if version["source_id"] != source["id"] or not version["content_hash"]:
                    raise ValueError("Invalid source version in corpus verification")
                versions.append([source["id"], version["id"], version["number"], version["generation"],
                                 version["content_hash"], version["state"]])
        wiki = await pages(call, "wiki_pages_list", "pages", include_deleted=True, **selector)
        index = await call("knowledge_index_status", **selector)
        if type(index.get("configured")) is not bool or type(index.get("indexed")) is not int:
            raise ValueError("Invalid C0 index status")
        # Source versions are latest-only. Recheck the metadata after the per-source
        # traversal so changing the source list mid-pagination cannot freeze a mixed set.
        if sources != await pages(call, "sources_list", "sources", include_deleted=True, **selector):
            raise ValueError("Sources changed during corpus verification")
        for name, key in (("knowledge_changes", "changes"), ("objects_changes", "events")):
            if await feed_cursor(call, name, key, ident, cursors[name]) != cursors[name]:
                raise ValueError("Knowledge or objects changed during corpus verification")
        result["spaces"][ident] = {
            "role": space["role"], "revision": space["revision"], "space_sha256": digest(space),
            "source_count": len(sources), "sources_sha256": digest(sources),
            "source_versions_sha256": digest(versions), "wiki_pages_sha256": digest(wiki),
            "feed_cursors": cursors, "index_status": index,
        }
    if (await call("get_profile"))["id"] != principal or await selected_spaces() != spaces:
        raise ValueError("Authenticated principal or accessible spaces changed during corpus verification")
    return result


def metadata_result(name, response):
    from web_kb_episode import Blocked
    if not response.get("isError"):
        if isinstance(response.get("structuredContent"), dict):
            return response["structuredContent"]
        content = response.get("content", [])
        if len(content) == 1 and content[0].get("type") == "text":
            try:
                value = json.loads(content[0]["text"])
            except (TypeError, ValueError, KeyError):
                pass
            else:
                if isinstance(value, dict):
                    return value
    # Keep native connector errors, account info and private source data out of logs.
    raise Blocked("Corpus verification failed at " + name)


async def snapshot():
    from web_kb_episode import candidate_profile, server, start_thread
    async with asyncio.timeout(7200), server(True) as broker:
        thread = await start_thread(broker)

        async def call(name, **arguments):
            result = await broker.request("mcpServer/tool/call", {
                "threadId": thread, "server": "codex_apps", "tool": "kbnethesis." + name,
                "arguments": arguments})
            return metadata_result(name, result)

        profile = candidate_profile()
        if not profile["start_space"]:
            raise ValueError("Select a starting space before taking a sealed corpus snapshot")
        return await inventory(call, {profile["start_space"], *profile["fallback_spaces"]})
