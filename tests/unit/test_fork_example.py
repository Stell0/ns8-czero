"""Fixture generation never reads application/private data or changes its source."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location("fork_example", ROOT / "examples/fork/create.py")
EXAMPLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXAMPLE)


def test_original_example_has_only_explicit_infrastructure_and_consumer(tmp_path):
    destination = tmp_path / "consumer"
    EXAMPLE.create(destination, ROOT)
    manifest = json.loads((destination / "c0-upstream.json").read_text())
    for entry in manifest["files"]:
        if entry["path"].startswith(".github/workflows/"):
            continue  # The consumer has focused CI, not an unconfigured module publisher.
        assert (destination / entry["path"]).read_bytes() == (ROOT / entry["path"]).read_bytes()
    assert (destination / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
    assert not (destination / "app").exists()
    assert not (destination / "packages").exists()
    assert not (destination / ".git").exists()
    assert (destination / "tests/test_consumer.py").is_file()
    assert (destination / ".github/workflows/check.yml").is_file()
    assert not (destination / ".github/workflows/publish-images.yml").exists()
    assert "git =" in (destination / "pyproject.toml").read_text()


def test_generator_does_not_overwrite_existing_destination(tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "keep").write_text("draft")
    with pytest.raises(ValueError):
        EXAMPLE.create(destination, ROOT)
    assert (destination / "keep").read_text() == "draft"


@pytest.mark.parametrize("kind", ["unsafe", "missing", "symlink"])
def test_generator_preflights_paths_before_creating_destination(tmp_path, kind):
    repository = tmp_path / "repository"
    (repository / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/sync-upstream.py", repository / "scripts/sync-upstream.py")
    (repository / "safe.txt").write_text("safe")
    bad = {"unsafe": "../outside", "missing": "absent", "symlink": "link"}[kind]
    if kind == "symlink":
        (repository / "link").symlink_to(repository / "safe.txt")
    (repository / "c0-upstream.json").write_text(json.dumps({"files": [{"path": "safe.txt"}, {"path": bad}]}))
    destination = tmp_path / "result"
    with pytest.raises(ValueError):
        EXAMPLE.create(destination, repository)
    assert not destination.exists()


def test_generated_fork_has_complete_native_cimd_dependencies(tmp_path):
    import runpy
    destination = tmp_path / 'consumer'
    EXAMPLE.create(destination, ROOT)
    helper = destination / 'imageroot/bin/czero_cimd_config.py'
    assert helper.is_file(), 'Generated native configuration imports an unregistered CIMD helper'
    assert runpy.run_path(str(helper))['read']({}) is False
    for name in ('imageroot/bin/czero-create-cimd-config',
                 'imageroot/actions/create-module/33cimd',
                 'imageroot/update-module.d/53cimd',
                 'imageroot/actions/configure-module/14validate-cimd',
                 'imageroot/actions/configure-module/39persist-cimd'):
        assert (destination / name).is_file() and (destination / name).stat().st_mode & 0o111
