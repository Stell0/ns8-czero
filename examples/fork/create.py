#!/usr/bin/env python3
"""Create original, isolated acceptance material, with no Git or network effects."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil


def create(destination: Path, repository: Path) -> None:
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Choose a new, empty destination")
    manifest = json.loads((repository / "c0-upstream.json").read_text())
    spec = importlib.util.spec_from_file_location("c0_sync", repository / "scripts/sync-upstream.py")
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    for entry in manifest["files"]:
        path = sync.safe_path(entry["path"])
        if sync.local_blob(repository, path)[1] is None:
            raise ValueError("Missing registered infrastructure file")
    destination.mkdir(parents=True)
    for entry in manifest["files"]:
        source, target = repository / entry["path"], destination / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(repository / "c0-upstream.json", destination / "c0-upstream.json")
    example = repository / "examples/fork"
    for name in ("AGENTS.md", "PLAN.md", "README.md", ".gitignore", "pyproject.toml", "renovate.json"):
        shutil.copy2(example / name, destination / name)
    if (example / "uv.lock").exists():
        shutil.copy2(example / "uv.lock", destination / "uv.lock")
    (destination / "tests").mkdir()
    shutil.copy2(example / "test_consumer.py", destination / "tests/test_consumer.py")
    # This fixture is a Core consumer, not a newly configured NS8 runtime module.
    shutil.rmtree(destination / ".github/workflows")
    shutil.copytree(example / "workflows", destination / ".github/workflows")
    shutil.copy2(repository / ".github/workflows/sync-upstream.yml", destination / ".github/workflows/sync-upstream.yml")
    print("Isolated example created; no Git repository or remote changes made")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    create(args.destination, Path(__file__).resolve().parents[2])
