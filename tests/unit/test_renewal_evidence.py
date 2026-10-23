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
ADMISSION = 'C0 admission: ' + json.dumps({'fresh_readers': 1, 'blocked_signins': 3, 'shared_only': True})
OFFLINE = 'C0 offline provider: ' + json.dumps(runpy.run_path(str(ROOT/'tests/offline_provider_probe.py'))['EXPECTED'])


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
        value=json.dumps(VALID) if 'renewal_fixture.py' in command else OFFLINE if 'offline_provider_probe.py' in command else ADMISSION if command.endswith('oidc_probe.py') else ''
        return (value,'',0) if kwargs.get('return_stderr') else (value,0)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    monkeypatch.setattr(BuiltIn,'log',lambda self,value,**kwargs:logged.append(value))
    library.verify_disposable_sso('czero901')
    library.verify_disposable_sso('czero901')
    assert sum('renewal_fixture.py' in command for command in commands)==1
    assert sum('offline_provider_probe.py' in command for command in commands)==1
    renewal = [value for value in logged if value.startswith('C0 renewable session: ')]
    assert len(renewal)==1 and json.loads(renewal[0].split(': ',1)[1])==VALID


def test_native_wrapper_rejects_extra_private_output_before_logging(monkeypatch):
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    logged=[]
    def execute(command,**kwargs):
        value=json.dumps({**VALID,'private':'private-provider-value'}) if 'renewal_fixture.py' in command else ADMISSION if command.endswith('oidc_probe.py') else ''
        return (value,'',0) if kwargs.get('return_stderr') else (value,0)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    monkeypatch.setattr(BuiltIn,'log',lambda self,value,**kwargs:logged.append(value))
    with pytest.raises(AssertionError,match='^Renewal acceptance measurement invalid$'):
        library.verify_disposable_sso('czero901')
    assert not any(value.startswith('C0 renewable session: ') or 'private-provider-value' in value for value in logged)


@pytest.mark.parametrize('value', ['', 'C0 admission: private-canary',
    'C0 admission: ' + json.dumps({'fresh_readers': True, 'blocked_signins': 3, 'shared_only': True}),
    'C0 admission: ' + json.dumps({'fresh_readers': 1, 'blocked_signins': 3, 'shared_only': True, 'private': 'canary'})])
def test_native_admission_proof_rejects_missing_or_private_data_before_logging(monkeypatch, value):
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    logged=[]
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda *_:SimpleNamespace(execute_command=lambda *a,**kw:(value,'',0)))
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda *_:'INFO')
    monkeypatch.setattr(BuiltIn,'log',lambda self,value,**kw:logged.append(value))
    with pytest.raises(AssertionError,match='Native default-admission evidence missing or invalid'):
        library.verify_disposable_sso('czero901')
    assert not logged


def test_actual_report_audit_requires_measured_native_evidence(tmp_path):
    audit=runpy.run_path(str(ROOT/'scripts/audit-ci-artifacts.py'))['audit_reports']
    for name in ('debian','rocky'):
        directory=tmp_path/name;directory.mkdir()
        (directory/'output.xml').write_text('<robot/>')
    with pytest.raises(AssertionError,match='One measured renewal proof per native distribution'):
        audit(tmp_path,'a'*40,[],'')


@pytest.mark.parametrize('changes', [
    {'offline_scope_granted': False}, {'owned_provider_logout_completed': False},
    {'initial_offline_access_checked_after_logout': False},
    {'new_adapter_offline_renewal_after_logout': False},
    {'owned_offline_credentials_revoked': False}, {'provider_refresh_expires_in': False},
    {'provider_refresh_expires_in': '0'}, {'passed': 1},
    {'private': 'private-offline-canary'},
])
def test_offline_provider_proof_rejects_failed_or_private_measurements(changes):
    probe = runpy.run_path(str(ROOT/'tests/offline_provider_probe.py'))
    with pytest.raises(AssertionError, match='^Offline provider evidence invalid$'):
        probe['validate']({**probe['EXPECTED'], **changes})


@pytest.mark.parametrize('value', ['', 'C0 offline provider: private-offline-canary',
    'C0 offline provider: ' + json.dumps({'passed': True}),
    OFFLINE + '\nprivate-offline-canary'])
def test_native_wrapper_rejects_offline_output_before_logging(monkeypatch, value):
    library = runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    logged = []
    def execute(command, **kwargs):
        output = (json.dumps(VALID) if 'renewal_fixture.py' in command else
                  value if 'offline_provider_probe.py' in command else
                  ADMISSION if command.endswith('oidc_probe.py') else '')
        return (output, '', 0) if kwargs.get('return_stderr') else (output, 0)
    monkeypatch.setattr(BuiltIn, 'get_library_instance', lambda *_: SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn, 'set_log_level', lambda *_: 'INFO')
    monkeypatch.setattr(BuiltIn, 'log', lambda self, output, **kw: logged.append(output))
    with pytest.raises(AssertionError, match='Offline provider evidence'):
        library.verify_disposable_sso('czero901')
    assert not any('C0 offline provider:' in output or 'private-offline-canary' in output for output in logged)
