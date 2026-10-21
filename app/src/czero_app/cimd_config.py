# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict trusted installation switch; absent configuration is disabled."""
import os


def configured(environment=None):
    environment = os.environ if environment is None else environment
    value = environment.get('CZERO_CIMD_ENABLED', 'false')
    if value not in ('true', 'false'):
        raise ValueError('invalid_cimd_policy')
    return value == 'true'
