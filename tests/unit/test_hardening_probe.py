# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location('hardening_probe', Path(__file__).parents[1] / 'hardening_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
VALID = ('uid 10001\nNoNewPrivs: 1\nCapEff: 0000000000000000\n'
         'memory 1073741824\nswap 1073741824\npids 256\nrss_kib 65536\n')


def test_accepts_effective_bounds_and_only_returns_safe_measurements():
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert kwargs == {'capture_output': True, 'text': True, 'timeout': 15}
        return SimpleNamespace(returncode=0, stdout=VALID)
    result = probe.probe(run)
    assert set(result) == {'czero', 'czero-postgres'}
    assert all(v['rss_kib'] == 65536 and v['no_new_privileges'] for v in result.values())
    assert all(v['cpu_quota_status'] == 'deferred' and 'cpus' not in v for v in result.values())
    assert all(command[:2] == ['podman', 'exec'] for command in calls)
    assert all('inspect' not in command for command in calls)


@pytest.mark.parametrize('before,after', [
    ('uid 10001', 'uid 0'), ('NoNewPrivs: 1', 'NoNewPrivs: 0'),
    ('CapEff: 0000000000000000', 'CapEff: 0000000000000001'),
    ('memory 1073741824', 'memory max'), ('memory 1073741824', 'memory 2147483648'),
    ('swap 1073741824', 'swap max'), ('pids 256', 'pids max'),
    ('pids 256', 'pids 2048'), ('rss_kib 65536', 'rss_kib 262145'),
    ('rss_kib 65536', 'rss_kib 0'), ('rss_kib 65536', 'rss_kib 1\nuid 10001'),
])
def test_rejects_unhardened_unbounded_or_over_budget_measurements(before, after):
    with pytest.raises(AssertionError):
        probe.validate(VALID.replace(before, after), 256 * 1024)


def test_rejects_missing_and_oversized_measurements_without_echoing_them():
    for value in [VALID + 'private fixture text\n', 'private fixture text' * 4096, '', None]:
        with pytest.raises(AssertionError) as error:
            probe.validate(value, 256 * 1024)
        assert 'private fixture text' not in str(error.value)


@pytest.mark.parametrize('failure', [OSError('private diagnostic'), subprocess.TimeoutExpired('private diagnostic', 15), None])
def test_transport_failure_has_static_diagnostic(failure):
    def run(*args, **kwargs):
        if failure:
            raise failure
        return SimpleNamespace(returncode=1, stdout='private diagnostic')
    with pytest.raises(AssertionError, match='^Runtime measurement unavailable$'):
        probe.probe(run)
