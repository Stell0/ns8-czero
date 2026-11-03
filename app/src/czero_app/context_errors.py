# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed, payload-free errors for the four read-only context operations."""
CONTEXT_OPERATIONS=frozenset({'source_document_outline_get','source_document_sections_get',
    'source_document_references_get','context_bundle_get'})
PUBLIC=frozenset({(404,'source_not_found'),(409,'source_conflict'),(410,'content_superseded'),
    (413,'too_large'),(422,'invalid_source_request'),(503,'authentication_not_configured')})


def mcp_context_error(operation,status,detail):
    if operation not in CONTEXT_OPERATIONS: return None
    if type(status) is int and type(detail) is str and (status,detail) in PUBLIC: return detail,status
    return 'service_unavailable',503
