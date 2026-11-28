# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Losslessly replay private standard search results. Output contains only totals."""
import argparse
import json
from pathlib import Path

from czero_app.retrieval import CompactSearchResult


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def replay(episodes):
    counts = dict(searches=0, hits=0, omitted_excerpts=0, full_bytes=0, compact_bytes=0)
    for episode in episodes:
        for call in episode["calls"]:
            if call["name"] != "kbnethesis_knowledge_search" or not call["success"]:
                continue
            original = json.loads(call["evidence"])
            compact = CompactSearchResult.from_search(original).model_dump(mode="json")
            counts["full_bytes"] += size(original)
            counts["compact_bytes"] += size(compact)
            for hit in compact["hits"]:
                for passage in (hit, *hit["supporting_passages"]):
                    if "excerpt" not in passage:
                        citation = passage["citation"]
                        start = passage["start_offset"] - citation["start_offset"]
                        end = passage["end_offset"] - citation["start_offset"]
                        passage["excerpt"] = citation["body"][start:end]
                        counts["omitted_excerpts"] += 1
            if compact != original:
                raise ValueError("Compact reconstruction differs from the recorded result")
            counts["hits"] += len(compact["hits"])
            counts["searches"] += 1
    if not counts["searches"]:
        raise ValueError("No successful standard searches in these episodes")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_directory", type=Path, help="private run's episodes directory")
    args = parser.parse_args()
    episodes = (json.loads(p.read_text()) for p in sorted(args.episode_directory.glob("*.json")))
    try:
        counts = replay(episodes)
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(1, "Replay failed during decoding, validation or evidence comparison (" +
                    type(error).__name__ + "). Inspect the run privately.\n")
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
