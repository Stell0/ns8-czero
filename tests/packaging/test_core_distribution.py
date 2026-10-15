# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the actual distributed package, never an editable checkout import."""
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import shutil
import tarfile
import tomllib
from uuid import uuid4
import zipfile

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]


def command(arguments, *, cwd, env=None):
    result = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True, timeout=240, umask=0o022)
    (cwd / 'last-package-command.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, 'Package command failed; inspect the isolated command log'
    return result.stdout


@pytest.fixture(scope='module')
def distributions(tmp_path_factory):
    directory=tmp_path_factory.mktemp('core-distribution')
    env={**os.environ,'SOURCE_DATE_EPOCH':os.getenv('SOURCE_DATE_EPOCH','1767225600'),'UV_CACHE_DIR':str(directory/'cache')}
    supplied=os.getenv('CZERO_CORE_DISTRIBUTION_DIR')
    if supplied:
        shutil.copytree(Path(supplied).resolve(),directory/'dist')
        return directory,env
    command(['uv','build','--no-sources',str(ROOT/'packages/czero-core'),'--out-dir',str(directory/'dist')],cwd=directory,env=env)
    command([sys.executable,str(ROOT/'scripts/normalize-core-sdist.py'),str(next((directory/'dist').glob('*.tar.gz')))],cwd=directory,env=env)
    command(['uv','build','--no-sources','--wheel',str(next((directory/'dist').glob('*.tar.gz'))),'--out-dir',str(directory/'dist')],cwd=directory,env=env)
    return directory, env


def test_distributions_have_license_runtime_metadata_and_complete_migrations(distributions):
    directory,_=distributions
    version=tomllib.loads((ROOT/'packages/czero-core/pyproject.toml').read_text())['project']['version']
    wheel=directory/'dist'/f'czero_core-{version}-py3-none-any.whl'
    source=directory/'dist'/f'czero_core-{version}.tar.gz'
    with zipfile.ZipFile(wheel) as archive:
        names=archive.namelist()
        metadata=archive.read(f'czero_core-{version}.dist-info/METADATA').decode()
        assert f'Version: {version}\n' in metadata
        assert 'License-Expression: GPL-3.0-or-later' in metadata
        assert archive.read(f'czero_core-{version}.dist-info/licenses/LICENSE')==(ROOT/'LICENSE').read_bytes()
        expected={str(p.relative_to(ROOT/'packages/czero-core/src')) for p in (ROOT/'packages/czero-core/src/czero_core/migrations').rglob('*.py')}
        assert expected <= set(names)
        assert not any(part in name.split('/') for name in names for part in ('tests','.agents','.github','app'))
        assert not any(name.endswith(('.pyc','.h','.pxd','.pyx')) for name in names)
    with tarfile.open(source) as archive:
        names=set(archive.getnames())
        assert f'czero_core-{version}/LICENSE' in names
        assert f'czero_core-{version}/README.md' in names


def test_wheel_and_source_rebuild_have_identical_hashes(distributions):
    directory,env=distributions
    command(['uv','build','--no-sources',str(ROOT/'packages/czero-core'),'--out-dir',str(directory/'repeat')],cwd=directory,env=env)
    command([sys.executable,str(ROOT/'scripts/normalize-core-sdist.py'),str(next((directory/'repeat').glob('*.tar.gz')))],cwd=directory,env=env)
    command(['uv','build','--no-sources','--wheel',str(next((directory/'repeat').glob('*.tar.gz'))),'--out-dir',str(directory/'repeat')],cwd=directory,env=env)
    for first in (directory/'dist').iterdir():
        if first.name.endswith(('.whl','.tar.gz')):
            second=directory/'repeat'/first.name
            assert hashlib.sha256(first.read_bytes()).digest()==hashlib.sha256(second.read_bytes()).digest()


@pytest.fixture(scope='module',params=['wheel','source'])
def installed(distributions,request):
    directory,env=distributions
    environment=directory/('venv-'+request.param)
    artifact=next((directory/'dist').glob('*.whl' if request.param=='wheel' else '*.tar.gz'))
    command(['uv','venv','--python','3.12',str(environment)],cwd=directory,env=env)
    command(['uv','pip','install','--python',str(environment/'bin/python'),str(artifact)],cwd=directory,env=env)
    return directory,env,environment/'bin/python'


def test_clean_install_is_independent_of_checkout_and_ns8_sdk(installed):
    directory,env,python=installed
    value=command([str(python),'-I','-c',
        "import sys,json,importlib.util,importlib.metadata;from pathlib import Path;import czero_core;"
        "from czero_core.jobs import default_registry;from czero_core.objects import ObjectService;"
        "from czero_core.wiki import WikiService;from czero_core.sources import SourceService;"
        "assert importlib.util.find_spec('agent') is None;assert importlib.util.find_spec('czero_app') is None;"
        "assert Path(czero_core.__file__).is_relative_to(Path(sys.prefix).resolve());"
        "assert default_registry().get('health').name=='health';"
        "assert czero_core.core_version==importlib.metadata.version('czero-core');"
        "print(json.dumps(czero_core.core_health()))"],cwd=directory,env=env)
    assert json.loads(value)['status']=='ok'


def test_installed_package_migrates_fresh_database_and_preserves_identity(installed):
    url=os.getenv('CZERO_TEST_DATABASE_URL')
    if not url:pytest.skip('Requires an isolated PostgreSQL/pgvector test database')
    directory,env,python=installed
    name='czero_distribution_'+uuid4().hex
    parsed=make_url(url)
    engine=create_engine(parsed,hide_parameters=True)
    target=parsed.set(database=name).render_as_string(hide_password=False)
    try:
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.execute(text('CREATE DATABASE '+name))
        results=[]
        for _ in range(2):
            command([str(python),'-I','-m','czero_core.migrate'],cwd=directory,env={**env,'CZERO_DATABASE_URL':target})
            output=command([str(python),'-I','-c',
                "import json;from sqlalchemy import text;from czero_core import Database;d=Database();"
                "c=d.engine.connect();print(json.dumps([str(c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one()),"
                "c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()]));c.close();d.close()"],cwd=directory,env={**env,'CZERO_DATABASE_URL':target})
            results.append(json.loads(output))
        assert results[0]==results[1] and results[0][1]=='0013_oauth_consent'
    finally:
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        engine.dispose()
