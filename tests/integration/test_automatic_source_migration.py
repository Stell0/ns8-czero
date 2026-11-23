# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Upgrade the independently installed immutable personal-data Core release."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_current_content_migration import current_core_python


@pytest.fixture(scope='module')
def published_personal_python(tmp_path_factory):
    directory=tmp_path_factory.mktemp('published-personal-core')
    python=directory/'venv/bin/python'
    environment={**os.environ,'UV_CACHE_DIR':str(directory/'cache')}
    for command in (
        ['uv','venv','--python',sys.executable,str(directory/'venv')],
        ['uv','pip','install','--python',str(python),
         'czero-core @ git+https://github.com/Stell0/ns8-czero.git@280ca06639bf6df55082aca397c2a6a585d988e0#subdirectory=packages/czero-core'],
    ):
        result=subprocess.run(command,capture_output=True,timeout=240,env=environment)
        (directory/'install.log').write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,'Published Core install failed; inspect private install.log'
    probe=subprocess.run([str(python),'-I','-c',
        "import importlib.metadata,czero_core;print(importlib.metadata.version('czero-core'));print(czero_core.__file__)"],
        capture_output=True,text=True,timeout=20)
    assert probe.returncode==0 and probe.stdout.splitlines()[0]=='0.50.0'
    assert '/packages/czero-core/src/' not in probe.stdout
    # Released migrations stay byte-identical through subsequent producer work.
    import czero_core.migrate
    migrations=Path(czero_core.migrate.__file__).with_name('migrations')/'versions'
    for name in ('0040_personal_data.py','0041_personal_aliases.py'):
        result=subprocess.run([str(python),'-I','-c',
            "import hashlib;from pathlib import Path;import czero_core.migrate;"
            "print(hashlib.sha256((Path(czero_core.migrate.__file__).with_name('migrations')/'versions'/"+repr(name)+").read_bytes()).hexdigest())"],
            capture_output=True,text=True,timeout=20)
        assert result.returncode==0
        assert result.stdout.strip()==hashlib.sha256((migrations/name).read_bytes()).hexdigest()
    return python


def test_published_personal_upgrade_preserves_all_rows_and_import_fences(
    published_personal_python,current_core_python,tmp_path,
):
    url=make_url(os.environ['CZERO_TEST_DATABASE_URL'])
    name='c0_automatic_upgrade_'+uuid4().hex
    admin=create_engine(url,isolation_level='AUTOCOMMIT')
    target=url.set(database=name).render_as_string(hide_password=False)
    database=create_engine(target)
    environment={**os.environ,'CZERO_DATABASE_URL':target,'CZERO_DISPOSABLE_TEST':'1',
                 'CZERO_PERSONAL_STATE':str(tmp_path/'state.json')}
    probe=Path(__file__).parents[1]/'packaging/core_personal_backup_probe.py'
    def run(python,*arguments,**extra):
        result=subprocess.run([str(python),'-I',*map(str,arguments)],capture_output=True,timeout=120,
                              env={**environment,**extra})
        (tmp_path/'migration.log').write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,'Installed migration/probe failed; inspect private migration.log'
    try:
        with admin.connect() as c:c.exec_driver_sql('CREATE DATABASE '+name)
        run(published_personal_python,'-m','czero_core.migrate')
        run(published_personal_python,probe,CZERO_PERSONAL_STAGE='seed')
        with database.connect() as c:
            assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0041_personal_aliases'
            names=c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename")).scalars().all()
            def snapshot():
                return {table:c.exec_driver_sql('SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\'::jsonb) FROM "'+table+'" t').scalar_one() for table in names}
            before=snapshot()
            for _ in range(2):
                run(current_core_python,'-m','czero_core.migrate')
                assert snapshot()==before
                assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0044_pdf_limits'
                assert c.execute(text('SELECT count(*) FROM c0_automatic_sources')).scalar_one()==0
        with database.begin() as c:c.execute(text('UPDATE c0_personal_config SET validated=false'))
        run(current_core_python,probe,CZERO_PERSONAL_STAGE='verify')
        assert not (tmp_path/'state.json').exists()
    finally:
        database.dispose()
        with admin.connect() as c:c.exec_driver_sql('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)')
        admin.dispose()
