# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Closed errors never expose target identities or database diagnostics."""
REFERENCE_OPERATIONS = frozenset({'cross_space_ref_create','cross_space_refs_list','cross_space_ref_delete'})
_PUBLIC = frozenset({(404,'reference_source_unavailable'),(404,'reference_target_unavailable'),
                     (409,'reference_conflict'),(422,'invalid_reference_request'),(503,'service_unavailable')})


def mcp_reference_error(operation, status, detail):
    if operation not in REFERENCE_OPERATIONS: return None
    if isinstance(detail, str) and type(status) is int and (status, detail) in _PUBLIC: return detail, status
    return 'service_unavailable', 503
