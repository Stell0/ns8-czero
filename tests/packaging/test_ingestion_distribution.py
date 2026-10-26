# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Install both actual sample distributions outside the checkout and Core/app."""
import json
import os
from pathlib import Path
import subprocess
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'samples/ingestion'


def command(args, *, cwd, env):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.fixture(scope='module')
def artifacts(tmp_path_factory):
    path = tmp_path_factory.mktemp('ingestion-distribution')
    env = {**os.environ, 'UV_CACHE_DIR': str(path / 'cache')}
    command(['uv', 'build', '--project', str(PROJECT), '--out-dir', str(path / 'dist')], cwd=path, env=env)
    wheel = next((path / 'dist').glob('*.whl'))
    archive = next((path / 'dist').glob('*.tar.gz'))
    with zipfile.ZipFile(wheel) as zipped:
        names = zipped.namelist()
        assert any(n.endswith('/c0_ingest/client.py') or n == 'c0_ingest/client.py' for n in names)
        assert 'github_vault/scrape.py' in names and 'github_vault/sync.py' in names
        licenses = [n for n in names if '.dist-info/licenses/' in n]
        assert len(licenses) == 1 and zipped.read(licenses[0]) == (PROJECT / 'LICENSE').read_bytes()
    with tarfile.open(archive) as tar:
        names = tar.getnames()
        assert any(n.endswith('/scripts/run_pipeline.py') for n in names)
        assert any(n.endswith('/uv.lock') for n in names)
        assert not any('/.local/' in n or n.endswith(('/oauth.json', '/.env')) for n in names)
    return path, env, wheel, archive


@pytest.mark.parametrize('kind', ['wheel', 'archive'])
def test_sample_installs_and_initializes_without_core_or_checkout(artifacts, kind):
    path, env, wheel, archive = artifacts
    work = path / kind
    work.mkdir()
    venv = work / 'venv'
    command(['uv', 'venv', str(venv)], cwd=work, env=env)
    python = venv / 'bin/python'
    command(['uv', 'pip', 'install', '--python', str(python), str(wheel if kind == 'wheel' else archive)], cwd=work, env=env)
    command([str(python), '-I', '-c',
        "import importlib.util,sys;from pathlib import Path;import c0_ingest.client,github_vault.sync;"
        "assert Path(c0_ingest.client.__file__).is_relative_to(Path(sys.prefix));"
        "assert importlib.util.find_spec('czero_core') is None;"
        "assert importlib.util.find_spec('czero_app') is None"], cwd=work, env=env)
    result = command([str(venv / 'bin/c0-ingest'), 'init', str(work / 'job')], cwd=work, env=env)
    assert json.loads(result)['writes_c0'] == 0
    assert (work / 'job/.env').stat().st_mode & 0o777 == 0o600
    help_text = command([str(python), str(work / 'job/run.py'), '--help'], cwd=work, env=env)
    assert 'sync' in help_text and 'login' in help_text
