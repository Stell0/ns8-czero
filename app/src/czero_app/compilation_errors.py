# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Value-free error allowlist for both MCP protocol modes."""
COMPILATION_OPERATIONS = frozenset({'compilation_policy_get', 'compilation_policy_set',
    'compilation_source_bindings_get', 'compilation_propose', 'compilation_tasks_list',
    'compilation_tasks_get', 'compilation_run_claim', 'compilation_run_checkpoint',
    'compilation_status_get', 'compilation_dependencies_list', 'compilation_target_bindings_get', 'compilation_plan_validate',
    'compilation_apply', 'compilation_verify'})
PUBLIC_ERRORS = frozenset({(409, 'compilation_conflict'), (404, 'compilation_not_found'),
    (403, 'compilation_disabled'), (409, 'compilation_source_not_ready'),
    (422, 'invalid_compilation_request'), (503, 'service_unavailable')})


def mcp_compilation_error(operation, status, detail):
    if operation not in COMPILATION_OPERATIONS:
        return None
    return (detail, status) if type(status) is int and type(detail) is str and (status, detail) in PUBLIC_ERRORS else ('service_unavailable', 503)
