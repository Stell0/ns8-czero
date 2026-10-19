# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-secret native lifecycle settings; Core validates runtime policy too."""
import os

ENVIRONMENT = {
    'absolute_seconds': 'CZERO_SESSION_ABSOLUTE_SECONDS',
    'idle_seconds': 'CZERO_SESSION_IDLE_SECONDS',
}
DEFAULTS = {'absolute_seconds': 28800, 'idle_seconds': 3600}


def validate(value):
    if (not isinstance(value, dict) or set(value) != set(DEFAULTS)
            or any(type(item) is not int for item in value.values())
            or not 60 <= value['idle_seconds'] <= value['absolute_seconds'] <= 86400):
        raise ValueError('invalid_session_policy')
    return dict(value)


def read(environment=None):
    environment = os.environ if environment is None else environment
    result = dict(DEFAULTS)
    for field, name in ENVIRONMENT.items():
        if name in environment:
            value = environment[name]
            if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
                raise ValueError('invalid_session_policy')
            result[field] = int(value)
    return validate(result)


def merge(current, patch):
    if not isinstance(patch, dict) or set(patch) - set(DEFAULTS):
        raise ValueError('invalid_session_policy')
    return validate({**current, **patch})


def encode(value):
    return {ENVIRONMENT[field]: str(item) for field, item in validate(value).items()}
