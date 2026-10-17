# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed space-policy errors contain no private names, identities or details."""
SPACE_OPERATIONS = frozenset({'spaces_list','spaces_create','spaces_get','space_grants_list','space_grants_set'})
_PUBLIC = frozenset({(409,'space_conflict'),(422,'invalid_space_request'),(503,'service_unavailable')})


def mcp_space_error(operation, status, detail):
    if operation not in SPACE_OPERATIONS:return None
    if type(status) is int and isinstance(detail,str) and (status,detail) in _PUBLIC:return detail,status
    return 'service_unavailable',503
