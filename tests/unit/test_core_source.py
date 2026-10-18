import importlib.util
from pathlib import Path
import tomllib
import re

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

SPEC = importlib.util.spec_from_file_location("core_source", Path(__file__).parents[2] / "scripts/select-core-source.py")
SELECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECT)


@pytest.fixture
def project(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    path = app / "pyproject.toml"
    path.write_text('[project]\nname="fixture"\ndependencies=["czero-core>=0.24.1,<0.25"]\n'
                    '[tool.uv.sources]\nczero-core = {git="https://github.com/Stell0/ns8-czero.git", '
                    'tag="core-v0.24.1", subdirectory="packages/czero-core"}\nother = {path="../other"}\n')
    core = tmp_path / "packages/czero-core"
    core.mkdir(parents=True)
    (core / "pyproject.toml").write_text('[project]\nname="czero-core"\nversion="0.24.1"\n')
    return path


def test_released_default_does_not_substitute_existing_local_tree(project):
    original = project.read_bytes()
    assert not SELECT.select(project, "released")
    assert project.read_bytes() == original


def test_local_override_is_explicit_limited_and_repeatable(project):
    before = tomllib.loads(project.read_text())
    assert SELECT.select(project, "local")
    after = tomllib.loads(project.read_text())
    assert after["tool"]["uv"]["sources"]["czero-core"] == {"path": "../packages/czero-core", "editable": False}
    assert after["project"] == before["project"]
    assert after["tool"]["uv"]["sources"]["other"] == before["tool"]["uv"]["sources"]["other"]
    assert not SELECT.select(project, "local")
    with pytest.raises(ValueError):
        SELECT.select(project, "released")


@pytest.mark.parametrize("source", ["url", "branch", "credential", "wrong-tag", "wrong-subdirectory"])
def test_unknown_or_unpinned_sources_fail_without_changes(project, source):
    text = project.read_text()
    if source == "url":
        text = text.replace('git="https://github.com/Stell0/ns8-czero.git"', 'url="https://example.org/core.whl"')
    elif source == "branch":
        text = text.replace('tag="core-v0.24.1"', 'branch="main"')
    elif source == "credential":
        text = text.replace('https://github.com/', 'https://credential@github.com/')
    elif source == "wrong-tag":
        text = text.replace('core-v0.24.1', 'latest')
    else:
        text = text.replace('subdirectory="packages/czero-core"', 'subdirectory="app"')
    project.write_text(text)
    for mode in ("local", "released"):
        with pytest.raises(ValueError):
            SELECT.select(project, mode)
        assert project.read_text() == text


def test_absent_local_checkout_is_not_replaced_by_another_package(project):
    (project.parent / "../packages/czero-core/pyproject.toml").unlink()
    original = project.read_bytes()
    with pytest.raises(ValueError):
        SELECT.select(project, "local")
    assert project.read_bytes() == original


def test_declared_compatibility_supports_both_released_and_explicit_producer_core():
    root = Path(__file__).parents[2]
    app = tomllib.loads((root/'app/pyproject.toml').read_text())
    core = tomllib.loads((root/'packages/czero-core/pyproject.toml').read_text())
    requirement = next(Requirement(value) for value in app['project']['dependencies']
                       if Requirement(value).name == 'czero-core')
    released = app['tool']['uv']['sources']['czero-core']['tag'].removeprefix('core-v')
    assert Version(released) in requirement.specifier
    assert Version(core['project']['version']) in requirement.specifier


def test_native_health_expectations_match_the_declared_producer_versions():
    root = Path(__file__).parents[2]
    robot = (root/'tests/czero.robot').read_text()
    for name, manifest in (('core_version','packages/czero-core/pyproject.toml'),
                           ('app_version','app/pyproject.toml')):
        declared = tomllib.loads((root/manifest).read_text())['project']['version']
        expected = re.findall('"'+name+'":"([^"]+)"',robot)
        assert expected and set(expected)=={declared}
