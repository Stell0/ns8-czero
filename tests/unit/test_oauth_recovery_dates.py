# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the native recovery fixture's date checks on host Python too."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


class RecoveryDates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'tests'))
        try:
            spec = importlib.util.spec_from_file_location(
                'recovery_date_fixture', ROOT / 'tests/oauth_fixture.py')
            cls.fixture = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.fixture)
        finally:
            sys.path.pop(0)

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='c0-recovery-dates-')
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        state = patch.object(self.fixture, 'STATE', self.state)
        state.start()
        self.addCleanup(state.stop)

    def recovery(self, expires_at):
        pair = {'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh'}
        rotated = {**pair, 'refresh_token': 'synthetic-rotated-refresh'}
        rows = {'grants': [{'expires_at': expires_at}], 'tokens': [], 'codes': []}
        expected = {'module_id': 'czero1', 'client': {'client_id': 'synthetic-client'},
                    'pair': pair, 'rows': rows}
        (self.state / 'expected-oauth-grant.json').write_text(json.dumps(expected))
        calls = []
        self.calls = calls

        class Browser:
            origin = 'https://c0.example.test'

            def request(self, path, *args):
                calls.append(path)
                return 200, json.dumps(rotated).encode(), self.origin + path

        self.fixture.verify_persistence('czero1', Browser(), {},
            snapshot_fn=lambda *args: rows,
            sdk_fn=lambda *args: calls.append('sdk'))
        return calls, rotated

    def test_native_recovery_accepts_trimmed_fraction(self):
        calls, pair = self.recovery('2099-01-02T03:04:05.12345+00:00')
        self.assertEqual(calls, ['/oauth/token', 'sdk'])
        path = self.state / 'expected-oauth-grant.json'
        self.assertEqual(json.loads(path.read_text())['pair'], pair)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_expired_trimmed_fraction_cannot_reach_refresh(self):
        with self.assertRaisesRegex(AssertionError, 'Recovery grant expired before binding assertion'):
            self.recovery('2000-01-02T03:04:05.12345+00:00')
        self.assertEqual(self.calls, [])

    def test_postgresql_precision_and_offsets_preserve_instant(self):
        for precision in range(7):
            fraction = '123456'[:precision]
            for minutes, offset in ((0, '+00:00'), (330, '+05:30'), (-240, '-04:00')):
                with self.subTest(precision=precision, offset=offset):
                    value = '2030-01-02T03:04:05' + ('.' + fraction if fraction else '') + offset
                    expected = datetime(2030, 1, 2, 3, 4, 5,
                        int(fraction.ljust(6, '0') or '0'),
                        tzinfo=timezone(timedelta(minutes=minutes)))
                    self.assertEqual(self.fixture.parse_grant_expiry(value), expected)

    def test_invalid_or_timezone_less_values_are_rejected(self):
        for value in (None, '', '2030-01-02T03:04:05', '2030-01-02T03:04:05.12345',
                      '2030-13-02T03:04:05+00:00', '2030-01-02T03:04:05.1234567+00:00'):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                self.fixture.parse_grant_expiry(value)


if __name__ == '__main__':
    unittest.main()
