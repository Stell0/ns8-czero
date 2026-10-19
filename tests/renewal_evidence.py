# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Strict public numeric proof; raw native output must never reach artifacts."""
FIELDS = {'elapsed_seconds', 'browser_reads', 'native_access_renewals', 'native_refresh_rotated',
          'public_refresh_rotations', 'idle_elapsed_seconds', 'absolute_elapsed_seconds',
          'absolute_bound_preserved', 'logout_and_reconnect', 'client_disabled'}


def validate_measurement(value):
    if (not isinstance(value, dict) or set(value) != FIELDS
            or any(type(item) is not int for item in value.values())
            or not 330 <= value['elapsed_seconds'] <= 600
            or not 2 <= value['browser_reads'] <= 64
            or not 1 <= value['native_access_renewals'] <= 32
            or value['native_refresh_rotated'] not in (0, 1)
            or not 2 <= value['public_refresh_rotations'] <= 64
            or not 60 <= value['idle_elapsed_seconds'] <= 180
            or not 120 <= value['absolute_elapsed_seconds'] <= 240
            or any(value[name] != 1 for name in ('absolute_bound_preserved', 'logout_and_reconnect', 'client_disabled'))):
        raise AssertionError('Renewal acceptance measurement invalid')
    return dict(value)
