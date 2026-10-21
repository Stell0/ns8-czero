# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Allow only bounded, non-private native CIMD recovery assertions into reports."""
from collections import Counter

COMMON = {'stage', 'approval_preserved', 'policy_enabled', 'core_seeded', 'network_fetch_tested'}
EXTRAS = {'seed': set(), 'update': {'existing_authority_retained', 'refresh_rotated', 'absolute_bound_preserved'},
          'restore': {'old_authority_rejected', 'old_grant_unexpired', 'fresh_consent', 'client_disabled', 'policy_disabled'}}


def validate_measurement(value):
    if not isinstance(value, dict) or type(value.get('stage')) is not str or value['stage'] not in EXTRAS:
        raise AssertionError('CIMD recovery acceptance measurement invalid')
    if (set(value) != COMMON | EXTRAS[value['stage']]
            or any(type(item) is not bool or item is not (key != 'network_fetch_tested')
                   for key, item in value.items() if key != 'stage')):
        raise AssertionError('CIMD recovery acceptance measurement invalid')
    return dict(value)


def require_stages(values):
    validated = [validate_measurement(value) for value in values]
    if Counter(v['stage'] for v in validated) != Counter({'seed': 1, 'update': 1, 'restore': 1}):
        raise AssertionError('All three measured CIMD recovery stages are required')
    return validated
