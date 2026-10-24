# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-secret inactivity setting for newly consented background connections."""
import os

ENVIRONMENT = 'CZERO_CONNECTION_IDLE_SECONDS'
DEFAULT = 30 * 86400


def validate(value):
    if type(value) is not int or not 86400 <= value <= 365 * 86400 or value % 86400:
        raise ValueError('invalid_connection_policy')
    return value


def read(environment=None):
    environment = os.environ if environment is None else environment
    value = environment.get(ENVIRONMENT, str(DEFAULT))
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError('invalid_connection_policy')
    return validate(int(value))


def encode(value):
    return {ENVIRONMENT: str(validate(value))}
