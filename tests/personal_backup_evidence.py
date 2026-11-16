# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Closed, payload-free native Personal Data backup evidence."""
FIELDS=frozenset({'personal_mapping_checkpoint_exclusion_restored','personal_restore_fenced',
    'personal_import_cleanup','personal_authored_retained'})


def validate(value):
    if type(value) is not dict or set(value)!=FIELDS or any(type(v) is not bool or not v for v in value.values()):
        raise AssertionError('Personal backup acceptance measurement invalid')
    return dict(value)


def require_proof(values):
    if len(values)!=1:raise AssertionError('One measured personal backup proof per native distribution required')
    return validate(values[0])
