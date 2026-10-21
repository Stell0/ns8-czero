# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-secret native CIMD switch; omitted old configuration defaults off."""
import os


def validate(value):
    if type(value) is not bool:
        raise ValueError('invalid_cimd_policy')
    return value


def read(environment=None):
    environment = os.environ if environment is None else environment
    value = environment.get('CZERO_CIMD_ENABLED', 'false')
    if value not in ('true', 'false'):
        raise ValueError('invalid_cimd_policy')
    return value == 'true'


def encode(value):
    return {'CZERO_CIMD_ENABLED': 'true' if validate(value) else 'false'}
