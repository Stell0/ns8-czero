# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest
from robot.libraries.BuiltIn import BuiltIn

ROOT=Path(__file__).resolve().parents[2]
VALID={'elapsed_seconds':330,'browser_reads':17,'native_access_renewals':1,'native_refresh_rotated':1,
    'public_refresh_rotations':2,'idle_elapsed_seconds':80,'absolute_elapsed_seconds':140,
    'absolute_bound_preserved':1,'logout_and_reconnect':1,'client_disabled':1}


@pytest.mark.parametrize('changes', [
    {'elapsed_seconds':300}, {'elapsed_seconds':'330'}, {'browser_reads':0},
    {'native_access_renewals':0}, {'native_refresh_rotated':2}, {'public_refresh_rotations':1},
    {'idle_elapsed_seconds':59}, {'absolute_elapsed_seconds':119},
    {'absolute_bound_preserved':True}, {'client_disabled':0}, {'private':'private-provider-value'}])
def test_unmeasured_or_private_fields_cannot_be_accepted_or_echoed(changes):
    validate=runpy.run_path(str(ROOT/'tests/renewal_evidence.py'))['validate_measurement']
    with pytest.raises(AssertionError,match='^Renewal acceptance measurement invalid$'):
        validate({**VALID,**changes})


def test_native_wrapper_records_only_validated_measurement_once(monkeypatch):
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    commands=[];logged=[]
    def execute(command,**kwargs):
        commands.append(command)
        value=json.dumps(VALID) if 'renewal_fixture.py' in command else ''
        return (value,'',0) if kwargs.get('return_stderr') else (value,0)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    monkeypatch.setattr(BuiltIn,'log',lambda self,value,**kwargs:logged.append(value))
    library.verify_disposable_sso('czero901')
    library.verify_disposable_sso('czero901')
    assert sum('renewal_fixture.py' in command for command in commands)==1
    assert len(logged)==1 and json.loads(logged[0].split(': ',1)[1])==VALID


def test_native_wrapper_rejects_extra_private_output_before_logging(monkeypatch):
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    logged=[]
    def execute(command,**kwargs):
        value=json.dumps({**VALID,'private':'private-provider-value'}) if 'renewal_fixture.py' in command else ''
        return (value,'',0) if kwargs.get('return_stderr') else (value,0)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    monkeypatch.setattr(BuiltIn,'log',lambda self,value,**kwargs:logged.append(value))
    with pytest.raises(AssertionError,match='^Renewal acceptance measurement invalid$'):
        library.verify_disposable_sso('czero901')
    assert logged==[]


def test_actual_report_audit_requires_measured_native_evidence(tmp_path):
    audit=runpy.run_path(str(ROOT/'scripts/audit-ci-artifacts.py'))['audit_reports']
    for name in ('debian','rocky'):
        directory=tmp_path/name;directory.mkdir()
        (directory/'output.xml').write_text('<robot/>')
    with pytest.raises(AssertionError,match='One measured renewal proof per native distribution'):
        audit(tmp_path,'a'*40,[],'')
