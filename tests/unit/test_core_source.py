import importlib.util
import json
from pathlib import Path
import tomllib
import re
import subprocess
import sys

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
    assert after["project"] == {**before["project"],"dependencies":["czero-core==0.24.1"]}
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
        text = text.replace('https://github.com/', 'https://'+'fixture-credential@github.com/')
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


def test_declared_consumer_and_explicit_producer_have_verified_versions(tmp_path):
    root = Path(__file__).parents[2]
    app = tomllib.loads((root/'app/pyproject.toml').read_text())
    core = tomllib.loads((root/'packages/czero-core/pyproject.toml').read_text())
    requirement = next(Requirement(value) for value in app['project']['dependencies']
                       if Requirement(value).name == 'czero-core')
    released = app['tool']['uv']['sources']['czero-core']['tag'].removeprefix('core-v')
    assert Version(released) in requirement.specifier
    import shutil
    shutil.copytree(root/'packages/czero-core',tmp_path/'packages/czero-core',ignore=shutil.ignore_patterns('__pycache__','*.egg-info'))
    (tmp_path/'app').mkdir()
    project=tmp_path/'app/pyproject.toml';project.write_text((root/'app/pyproject.toml').read_text())
    SELECT.select(project,'local')
    producer=tomllib.loads(project.read_text())
    selected=next(Requirement(value) for value in producer['project']['dependencies'] if Requirement(value).name=='czero-core')
    assert str(selected.specifier)=='=='+core['project']['version']
    assert producer['tool']['uv']['sources']['czero-core']['path']=='../packages/czero-core'


def test_native_health_expectations_match_the_declared_producer_versions():
    root = Path(__file__).parents[2]
    robot = (root/'tests/czero.robot').read_text()
    for name, manifest in (('core_version','packages/czero-core/pyproject.toml'),
                           ('app_version','app/pyproject.toml')):
        declared = tomllib.loads((root/manifest).read_text())['project']['version']
        expected = re.findall('"'+name+'":"([^"]+)"',robot)
        assert expected and set(expected)=={declared}


def test_runtime_versions_match_the_installed_package_metadata():
    from importlib.metadata import version
    from czero_app import __version__ as app_version
    from czero_core import core_version
    root = Path(__file__).parents[2]
    for name, runtime, manifest in (
        ('czero-app', app_version, 'app/pyproject.toml'),
        ('czero-core', core_version, 'packages/czero-core/pyproject.toml'),
    ):
        declared = tomllib.loads((root/manifest).read_text())['project']['version']
        assert runtime == version(name) == declared


def test_predecessor_and_current_profile_health_bindings_are_explicit():
    root = Path(__file__).parents[2]
    robot = (root/'tests/czero.robot').read_text()
    predecessor = json.loads((root/'tests/fixtures/upgrade_predecessor.json').read_text())
    current = tomllib.loads((root/'app/pyproject.toml').read_text())['project']['version']
    current_core = tomllib.loads((root/'packages/czero-core/pyproject.toml').read_text())['project']['version']
    calls = re.findall(r'Predecessor Profile\s+\$\{module_id\}\s+changed-\$\{host\}\s+(seed|verify)\s+([0-9.]+)\s+([0-9.]+)',robot)
    assert calls == [('seed',predecessor['app_version'],predecessor['core_version']),
                     ('verify',current,current_core)]
    assert '${expected_app}='+current in robot
    assert '${expected_core}='+current_core in robot
    assert 'Should Be Equal    ${health}[core_version]    ${expected_core}' in robot


def test_native_upgrade_freezes_all_three_accepted_predecessor_images():
    root = Path(__file__).parents[2]
    predecessor = json.loads((root/'tests/fixtures/upgrade_predecessor.json').read_text())
    robot = (root/'tests/czero.robot').read_text()
    assert re.fullmatch(r'[0-9a-f]{40}', predecessor['source'])
    assert predecessor['source'] in predecessor['tag']
    for image in predecessor['images'].values():
        assert re.fullmatch(r'ghcr.io/stell0/czero(?:-app|-postgres)?@sha256:[0-9a-f]{64}', image)
        assert image in robot


@pytest.mark.parametrize('filename', ['test-core-consumer.yml', 'publish-images.yml'])
def test_released_image_workflow_extracts_the_actual_current_lock(tmp_path, filename):
    import subprocess
    import sys
    root = Path(__file__).parents[2]
    workflow = (root/'.github/workflows'/filename).read_text()
    source = workflow.split("python3 - <<'PY' > /tmp/core-expected\n", 1)[1].split('          PY\n', 1)[0]
    import textwrap
    source = textwrap.dedent(source)
    (tmp_path/'app').mkdir()
    (tmp_path/'app/uv.lock').write_bytes((root/'app/uv.lock').read_bytes())
    result = subprocess.run([sys.executable, '-c', source], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0
    core = next(item for item in tomllib.loads((root/'app/uv.lock').read_text())['package'] if item['name'] == 'czero-core')
    assert result.stdout.split() == [core['version'], core['source']['git'].rsplit('#', 1)[1]]


@pytest.fixture
def ci_project(project):
    root = project.parent.parent

    def git(*args):
        return subprocess.check_output([
            'git', '-C', str(root), '-c', 'user.name=Alice',
            '-c', 'user.email=alice@example.org', '-c', 'commit.gpgsign=false',
            *args,
        ], text=True).strip()

    git('init', '-q')
    git('add', '.')
    git('commit', '-qm', 'Released Core fixture')
    commit = git('rev-parse', 'HEAD')
    lock = project.with_name('uv.lock')
    lock.write_text('version=1\n[[package]]\nname="czero-core"\nversion="0.24.1"\n'
        'source={git="https://github.com/Stell0/ns8-czero.git?'
        'subdirectory=packages%2Fczero-core&tag=core-v0.24.1#' + commit + '"}\n')
    git('add', '.')
    git('commit', '-qm', 'Adopt released Core fixture')
    return project, git


@pytest.mark.parametrize('change,expected', [
    ('none', 'released'), ('app', 'released'),
    ('uncommitted-core', 'released'), ('committed-core', 'local'),
])
def test_ci_core_source_compares_committed_package_content(ci_project, change, expected):
    project, git = ci_project
    if change == 'app':
        project.write_text(project.read_text() + '\n# Application-only change\n')
    elif change != 'none':
        (project.parent.parent/'packages/czero-core/new.py').write_text('VALUE = 1\n')
    if change in {'app', 'committed-core'}:
        git('add', '.')
        git('commit', '-qm', 'Changed fixture')
    before = project.read_bytes(), project.with_name('uv.lock').read_bytes()
    assert SELECT.ci_source(project, 'Stell0/ns8-czero') == expected
    assert (project.read_bytes(), project.with_name('uv.lock').read_bytes()) == before


def test_ci_core_fork_never_substitutes_a_local_checkout(ci_project):
    project, git = ci_project
    (project.parent.parent/'packages/czero-core/new.py').write_text('VALUE = 1\n')
    git('add', '.')
    git('commit', '-qm', 'Fork customization fixture')
    project.with_name('uv.lock').unlink()
    assert SELECT.ci_source(project, 'ACME/czero') == 'released'


@pytest.mark.parametrize('problem', [
    'missing', 'unknown-commit', 'wrong-tag', 'duplicate', 'wrong-version',
    'credential', 'path-source', 'unpinned',
])
def test_ci_core_invalid_release_identity_never_selects_local(ci_project, problem):
    project, git = ci_project
    lock = project.with_name('uv.lock')
    text = lock.read_text()
    if problem == 'missing':
        lock.unlink()
    elif problem == 'unknown-commit':
        lock.write_text(re.sub(r'#[a-f0-9]{40}', '#' + 'f'*40, text))
    elif problem == 'wrong-tag':
        lock.write_text(text.replace('tag=core-v0.24.1', 'tag=core-v0.24.2'))
    elif problem == 'duplicate':
        lock.write_text(text + text[text.index('[[package]]'):])
    elif problem == 'wrong-version':
        lock.write_text(text.replace('version="0.24.1"', 'version="0.24.2"'))
    elif problem == 'credential':
        lock.write_text(text.replace('https://github.com/', 'https://' + 'fixture-credential@github.com/'))
    elif problem == 'path-source':
        lock.write_text(text[:text.index('source=')] + 'source={path="../packages/czero-core"}\n')
    else:
        lock.write_text(re.sub(r'#[a-f0-9]{40}', '', text))
    with pytest.raises((ValueError, OSError, subprocess.CalledProcessError)):
        SELECT.ci_source(project, 'Stell0/ns8-czero')


def test_ci_core_cli_is_read_only_and_fails_without_fallback(ci_project):
    project, git = ci_project
    command = [sys.executable, str(Path(SELECT.__file__)), '--project', str(project),
               '--ci-repository', 'Stell0/ns8-czero']
    before = project.read_bytes()
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip() == 'released'
    assert project.read_bytes() == before
    lock = project.with_name('uv.lock')
    lock.write_text(re.sub(r'#[a-f0-9]{40}', '#' + 'f'*40, lock.read_text()))
    failed = subprocess.run(command, capture_output=True, text=True)
    assert failed.returncode != 0 and not failed.stdout.strip()
    assert project.read_bytes() == before
