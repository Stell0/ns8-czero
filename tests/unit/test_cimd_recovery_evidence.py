# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest
from robot.libraries.BuiltIn import BuiltIn

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = runpy.run_path(str(ROOT/'tests/cimd_recovery_evidence.py'))
validate_measurement, require_stages = EVIDENCE['validate_measurement'], EVIDENCE['require_stages']
COMMON = {'approval_preserved': True, 'policy_enabled': True, 'core_seeded': True, 'network_fetch_tested': False}
SEED = {'stage': 'seed', **COMMON}
UPDATE = {'stage': 'update', **COMMON, 'existing_authority_retained': True, 'refresh_rotated': True, 'absolute_bound_preserved': True}
RESTORE = {'stage': 'restore', **COMMON, 'old_authority_rejected': True, 'old_grant_unexpired': True,
           'fresh_consent': True, 'client_disabled': True, 'policy_disabled': True}


@pytest.mark.parametrize('change', [
    {'stage': 'private-host.example.test'}, {'stage': []}, {'core_seeded': 1}, {'network_fetch_tested': True},
    {'approval_preserved': False}, {'private': 'private-provider-value'}, {'policy_enabled': None}])
def test_private_false_or_unmeasured_recovery_cannot_be_accepted(change):
    with pytest.raises(AssertionError, match='^CIMD recovery acceptance measurement invalid$'):
        validate_measurement({**SEED, **change})


def test_all_three_native_stages_are_required():
    assert require_stages([SEED, UPDATE, RESTORE]) == [SEED, UPDATE, RESTORE]
    for values in ([], [SEED], [SEED, UPDATE], [SEED, UPDATE, UPDATE, RESTORE]):
        with pytest.raises(AssertionError, match='All three measured CIMD recovery stages'):
            require_stages(values)


@pytest.mark.parametrize('value', [SEED, UPDATE, RESTORE, {**RESTORE, 'private': 'private-provider-value'}])
def test_wrapper_only_logs_validated_recovery_measurements(monkeypatch, value):
    logged = []
    library = runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    monkeypatch.setattr(BuiltIn, 'set_log_level', lambda *_: 'NONE')
    monkeypatch.setattr(BuiltIn, 'get_library_instance', lambda *_: SimpleNamespace(
        execute_command=lambda *a, **kw: ('C0 CIMD recovery: ' + json.dumps(value), '', 0)))
    monkeypatch.setattr(BuiltIn, 'log', lambda self, value: logged.append(value))
    monkeypatch.setattr(BuiltIn, 'log_to_console', lambda *_: None)
    if 'private' in value:
        with pytest.raises(AssertionError): library._cimd_persistence('czero7', 'verify')
        assert not logged
    else:
        library._cimd_persistence('czero7', 'verify')
        assert logged == ['C0 CIMD recovery: ' + json.dumps(value, sort_keys=True)]


def test_actual_report_audit_rejects_missing_cimd_recovery(tmp_path):
    valid = {'elapsed_seconds': 330, 'browser_reads': 17, 'native_access_renewals': 1, 'native_refresh_rotated': 1,
        'public_refresh_rotations': 2, 'idle_elapsed_seconds': 80, 'absolute_elapsed_seconds': 140,
        'absolute_bound_preserved': 1, 'logout_and_reconnect': 1, 'client_disabled': 1}
    offline = runpy.run_path(str(ROOT/'tests/offline_provider_probe.py'))['EXPECTED']
    for name in ('debian', 'rocky'):
        p = tmp_path/name;p.mkdir()
        (p/'output.xml').write_text('<robot><msg>C0 renewable session: ' + json.dumps(valid) +
            '</msg><msg>C0 offline provider: ' + json.dumps(offline) + '</msg></robot>')
    audit = runpy.run_path(str(ROOT/'scripts/audit-ci-artifacts.py'))['audit_reports']
    with pytest.raises(AssertionError, match='All three measured CIMD recovery stages'):
        audit(tmp_path, 'a'*40, [], '')
