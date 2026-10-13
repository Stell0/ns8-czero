# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def agent_fixture(monkeypatch):
    @contextmanager
    def safe_open(path, mode='w'):
        with open(path,mode) as f:
            yield f
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(safe_open=safe_open))


@pytest.mark.parametrize('fail',[False,True])
def test_dump_failure_and_cold_database_leave_service_state_intact(monkeypatch,tmp_path,capsys,fail):
    import subprocess
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        if 'is-active' in command or 'is-enabled' in command:
            return SimpleNamespace(returncode=1)
        if command[:3] == ['podman','exec','czero-postgres']:
            if fail:
                raise subprocess.CalledProcessError(1,command)
            kwargs['stdout'].write(b'PGDMP fixture')
        return SimpleNamespace(returncode=0)
    agent_fixture(monkeypatch)
    monkeypatch.setattr(subprocess,'run',run)
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path))
    script=str(ROOT / 'imageroot/bin/module-dump-state')
    if fail:
        with pytest.raises(subprocess.CalledProcessError): runpy.run_path(script)
        assert not (tmp_path/'czero.pg_dump').exists()
        assert not (tmp_path/'backup-metadata.json').exists()
    else:
        runpy.run_path(script)
        assert (tmp_path/'czero.pg_dump').read_bytes().startswith(b'PGDMP')
        assert json.loads((tmp_path/'backup-metadata.json').read_text()) == {'format':1,'app_active':False,'app_enabled':False}
    assert ['systemctl','--user','start','czero-postgres.service'] in calls
    assert ['systemctl','--user','stop','czero-postgres.service'] in calls
    assert ['systemctl','--user','stop','czero-pod.service'] in calls
    assert not any(c[:3]==['systemctl','--user','start'] and c[-1]=='czero.service' for c in calls)
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('metadata,archive',[(None,b'PGDMP'),({'format':2,'app_active':True,'app_enabled':True},b'PGDMP'),({'format':True,'app_active':True,'app_enabled':True},b'PGDMP'),({'format':1,'app_active':True,'app_enabled':True},b'not an archive')])
def test_invalid_backup_stops_before_database_restore(monkeypatch,tmp_path,capsys,metadata,archive):
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path))
    if metadata is not None: (tmp_path/'backup-metadata.json').write_text(json.dumps(metadata))
    (tmp_path/'czero.pg_dump').write_bytes(archive)
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(ROOT/'imageroot/actions/restore-module/30validate-backup'))
    assert error.value.code == 1
    assert capsys.readouterr().out == ''


def test_backup_inputs_include_logical_dump_not_live_database():
    lines=set((ROOT/'imageroot/etc/state-include.conf').read_text().splitlines())
    assert {'state/czero.pg_dump','state/passwords.env','state/backup-metadata.json','volumes/czero-sources'} <= lines
    assert 'volumes/czero-db-data' not in lines


def test_backup_destination_helper_sanitizes_generated_password(monkeypatch):
    from robot.libraries.BuiltIn import BuiltIn
    calls=[]
    levels=[]
    outputs=[('10.5.4.1',0),(json.dumps({'id':'destination-id','password':'sensitive-generated-value'}),0),('3',0),('czero/space-id',0)]
    def execute(command,**kwargs):
        calls.append(command)
        assert levels[-1] == 'NONE'
        return outputs.pop(0)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:SimpleNamespace(execute_command=execute))
    def set_level(self,level):
        previous=levels[-1] if levels else 'INFO'
        levels.append(level)
        return previous
    monkeypatch.setattr(BuiltIn,'set_log_level',set_level)
    library=runpy.run_path(str(ROOT/'tests/CzeroBackup.py'))['CzeroBackup']()
    result=library.create_disposable_backup('czero1')
    assert result == {'repository':'destination-id','backup_id':3,'path':'czero/space-id'}
    assert 'sensitive-generated-value' not in json.dumps(result)
    assert not any('sensitive-generated-value' in c for c in calls)
    assert levels == ['NONE','INFO']


@pytest.mark.parametrize('fail',[False,True])
def test_offline_restore_is_transactional_and_failure_has_no_receipt(monkeypatch,tmp_path,fail):
    import subprocess
    agent_fixture(monkeypatch)
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path))
    monkeypatch.setenv('CZERO_POSTGRES_IMAGE','database-image')
    (tmp_path/'czero.pg_dump').write_bytes(b'PGDMP fixture')
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        if '--entrypoint=sh' in command: return SimpleNamespace(returncode=1)
        if '--interactive' in command:
            script=(tmp_path/'restore-database/10restore.sh').read_text()
            assert '--single-transaction' in script and '--exit-on-error' in script
            assert '--no-owner' in script and '--no-privileges' in script
            assert '--network=none' in command
            if fail: raise subprocess.CalledProcessError(1,command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess,'run',run)
    script=str(ROOT/'imageroot/actions/restore-module/40restore-database')
    if fail:
        with pytest.raises(subprocess.CalledProcessError): runpy.run_path(script)
        assert not (tmp_path/'restore-receipt.json').exists()
    else:
        runpy.run_path(script)
        assert json.loads((tmp_path/'restore-receipt.json').read_text())['format'] == 1
    assert not (tmp_path/'restore-database').exists()
    assert any('--interactive' in c for c in calls)


def test_initialized_restore_target_cannot_be_overwritten(monkeypatch,tmp_path,capsys):
    import subprocess
    agent_fixture(monkeypatch)
    calls=[]
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path))
    monkeypatch.setenv('CZERO_POSTGRES_IMAGE','database-image')
    (tmp_path/'czero.pg_dump').write_bytes(b'PGDMP fixture')
    monkeypatch.setattr(subprocess,'run',lambda command,**kwargs: calls.append(command) or SimpleNamespace(returncode=0))
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(ROOT/'imageroot/actions/restore-module/40restore-database'))
    assert error.value.code == 1
    assert not any('--interactive' in c for c in calls)
    assert capsys.readouterr().out == ''


def test_restore_settings_keep_new_platform_port_and_identity(monkeypatch,tmp_path):
    from io import StringIO
    values={}
    agent_fixture(monkeypatch)
    agent=sys.modules['agent']
    agent.read_envfile=lambda path:{'CZERO_HOST':''}
    agent.mset_env=values.update
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path))
    monkeypatch.setenv('MODULE_ID','czero9')
    monkeypatch.setenv('TCP_PORT','22222')
    original={'CZERO_HOST':'Old.Test','CZERO_MODULE_ID':'czero1','TCP_PORT':'11111','NODE_ID':'1','IMAGE_URL':'old-image','CZERO_LETS_ENCRYPT':'false'}
    monkeypatch.setattr(sys,'stdin',StringIO(json.dumps({'environment':original})))
    runpy.run_path(str(ROOT/'imageroot/actions/restore-module/20persist-settings'))
    assert values == {'CZERO_MODULE_ID':'czero9','CZERO_HOST':'old.test','CZERO_LETS_ENCRYPT':'false','CZERO_BASE_PATH':''}
    assert not {'TCP_PORT','NODE_ID','IMAGE_URL'} & values.keys()
