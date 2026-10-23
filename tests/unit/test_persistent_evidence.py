# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest
from robot.libraries.BuiltIn import BuiltIn

ROOT=Path(__file__).resolve().parents[2]
PROBE=runpy.run_path(str(ROOT/'tests/persistent_fixture.py'))
VALID={'browser_absolute_seconds':120,'elapsed_seconds':140,
    **{key:True for key in PROBE['FIELDS']-{'browser_absolute_seconds','elapsed_seconds'}}}


@pytest.mark.parametrize('change',[
    {'elapsed_seconds':119},{'elapsed_seconds':301},{'browser_absolute_seconds':True},
    {'browser_expired':1},{'self_disconnect_revoked':False},{'policy_restored':False},
    {'provider_credential_revoked':False},{'private':'private-persistent-canary'},
])
def test_unmeasured_failed_or_private_background_evidence_is_rejected(change):
    with pytest.raises(AssertionError,match='^Persistent connection evidence invalid$'):
        PROBE['validate']({**VALID,**change})


@pytest.mark.parametrize('value',['','C0 persistent connection: private-persistent-canary',
    'C0 persistent connection: '+json.dumps({**VALID,'private':'private-persistent-canary'}),
    'C0 persistent connection: '+json.dumps(VALID)+'\nprivate-persistent-canary'])
def test_native_wrapper_rejects_private_background_output_before_logging(monkeypatch,value):
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']();logged=[]
    renewal={'elapsed_seconds':330,'browser_reads':17,'native_access_renewals':1,'native_refresh_rotated':1,
        'public_refresh_rotations':2,'idle_elapsed_seconds':80,'absolute_elapsed_seconds':140,
        'absolute_bound_preserved':1,'logout_and_reconnect':1,'client_disabled':1}
    offline=runpy.run_path(str(ROOT/'tests/offline_provider_probe.py'))['EXPECTED']
    admission='C0 admission: '+json.dumps({'fresh_readers':1,'blocked_signins':3,'shared_only':True})
    def execute(command,**kwargs):
        output=(json.dumps(renewal) if 'renewal_fixture.py' in command else
            'C0 offline provider: '+json.dumps(offline) if 'offline_provider_probe.py' in command else
            value if 'persistent_fixture.py' in command else admission if command.endswith('oidc_probe.py') else '')
        return (output,'',0) if kwargs.get('return_stderr') else (output,0)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda *_:SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda *_:'NONE')
    monkeypatch.setattr(BuiltIn,'log',lambda self,output,**kw:logged.append(output))
    monkeypatch.setattr(BuiltIn,'log_to_console',lambda *_:None)
    with pytest.raises(AssertionError,match='Persistent connection evidence'):
        library.verify_disposable_sso('czero901')
    assert not any('private-persistent-canary' in output or output.startswith('C0 persistent connection: ') for output in logged)


def recovery_measurement(stage):
    return {'stage':stage,'inactivity_seconds':7*86400,**{key:True for key in PROBE['RECOVERY_FIELDS'][stage]}}


def test_all_three_background_recovery_stages_are_required():
    values=[recovery_measurement(stage) for stage in PROBE['RECOVERY_FIELDS']]
    assert PROBE['require_recovery'](list(reversed(values)))==values
    for incomplete in ([],values[:1],values[:2],values+[values[0]]):
        with pytest.raises(AssertionError,match='All three measured persistent recovery stages'):
            PROBE['require_recovery'](incomplete)


@pytest.mark.parametrize('change',[{'stage':[]},{'inactivity_seconds':True},{'inactivity_seconds':30*86400},
    {'rows_preserved':False},{'old_authority_rejected':False},{'provider_credential_revoked':False},
    {'private':'private-recovery-canary'}])
def test_failed_or_private_background_recovery_is_rejected(change):
    with pytest.raises(AssertionError,match='^Persistent recovery evidence invalid$'):
        PROBE['validate_recovery']({**recovery_measurement('restore'),**change})


@pytest.mark.parametrize('private',[False,True])
def test_recovery_wrapper_logs_only_strict_public_measurements(monkeypatch,private):
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']();logged=[]
    proof=recovery_measurement('seed')
    if private:proof['private']='private-recovery-canary'
    def execute(command,**kwargs):
        return ('C0 persistent recovery: '+json.dumps(proof),'',0) if 'persistent_fixture.py' in command else ('','',0)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda *_:SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda *_:'NONE')
    monkeypatch.setattr(BuiltIn,'log',lambda self,output,**kw:logged.append(output))
    monkeypatch.setattr(BuiltIn,'log_to_console',lambda *_:None)
    if private:
        with pytest.raises(AssertionError,match='^Persistent recovery evidence invalid$'):
            library._oauth_persistence('czero901','seed')
        assert not logged
    else:
        library._oauth_persistence('czero901','seed')
        assert logged==['C0 persistent recovery: '+json.dumps(proof,sort_keys=True)]
