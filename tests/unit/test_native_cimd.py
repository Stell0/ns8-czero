# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy

from jsonschema import Draft7Validator, ValidationError
import pytest

from czero_app.cimd_config import configured
from test_native_session_policy import native, step

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cimd_native(native, monkeypatch):
    monkeypatch.delenv('CZERO_CIMD_ENABLED', raising=False)
    return native


def test_old_install_defaults_off_and_repeat_keeps_the_configured_value(cimd_native, monkeypatch):
    updates, _ = cimd_native
    step(monkeypatch, 'bin/czero-create-cimd-config')
    assert updates == [{'CZERO_CIMD_ENABLED': 'false'}]
    monkeypatch.setenv('CZERO_CIMD_ENABLED', 'true')
    step(monkeypatch, 'bin/czero-create-cimd-config')
    assert len(updates) == 1 and configured()


def test_omitted_patch_preserves_switch_and_old_backups_default_off(cimd_native, monkeypatch):
    updates, _ = cimd_native
    monkeypatch.setenv('CZERO_CIMD_ENABLED', 'true')
    step(monkeypatch, 'actions/configure-module/14validate-cimd', {'host': 'c0.example.test'})
    step(monkeypatch, 'actions/configure-module/39persist-cimd', {'host': 'c0.example.test'})
    assert updates == [{'CZERO_CIMD_ENABLED': 'true'}]
    for original, expected in [({}, 'false'), ({'CZERO_CIMD_ENABLED': 'true'}, 'true')]:
        step(monkeypatch, 'actions/restore-module/20persist-settings', {'environment': original})
        assert updates[-1]['CZERO_CIMD_ENABLED'] == expected


@pytest.mark.parametrize('value', [None, 1, 0, 'true', 'false', [], {}])
def test_configure_rejects_non_boolean_before_mutation(cimd_native, monkeypatch, capsys, value):
    updates, statuses = cimd_native
    with pytest.raises(SystemExit) as result:
        step(monkeypatch, 'actions/configure-module/14validate-cimd', {'cimd_enabled': value})
    assert result.value.code == 2 and not updates and statuses == ['validation-failed']
    assert json.loads(capsys.readouterr().out) == [{'field': 'cimd_enabled', 'parameter': 'cimd_enabled', 'error': 'invalid_cimd_policy'}]


@pytest.mark.parametrize('value', ['', 'TRUE', 'False', '1', '0', ' true', True, None])
def test_runtime_and_native_environment_both_fail_closed(value, cimd_native):
    native_read = runpy.run_path(str(ROOT/'imageroot/bin/czero_cimd_config.py'))['read']
    for reader in (native_read, configured):
        with pytest.raises(ValueError, match='invalid_cimd_policy'):
            reader({'CZERO_CIMD_ENABLED': value})
        assert reader({}) is False
        assert reader({'CZERO_CIMD_ENABLED': 'true'}) is True
        assert reader({'CZERO_CIMD_ENABLED': 'false'}) is False


def test_native_schemas_boolean_configuration_and_application_environment(cimd_native, monkeypatch):
    schema = json.loads((ROOT/'imageroot/actions/configure-module/validate-input.json').read_text())
    for value in (True, False):
        Draft7Validator(schema).validate({'host': 'c0.example.test', 'cimd_enabled': value})
    with pytest.raises(ValidationError):
        Draft7Validator(schema).validate({'host': 'c0.example.test', 'cimd_enabled': 'true'})
    output = json.loads((ROOT/'imageroot/actions/get-configuration/validate-output.json').read_text())
    assert 'cimd_enabled' in output['required'] and output['properties']['cimd_enabled']['type'] == 'boolean'
    unit = (ROOT/'imageroot/systemd/user/czero.service').read_text()
    assert '--env=CZERO_CIMD_ENABLED=${CZERO_CIMD_ENABLED}' in unit
