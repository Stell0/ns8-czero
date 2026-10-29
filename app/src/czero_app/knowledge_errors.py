# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed, value-free MCP errors for explicitly registered knowledge operations."""
KNOWLEDGE_OPERATIONS = frozenset({
    'wiki_pages_list', 'wiki_pages_create', 'wiki_pages_get', 'wiki_pages_update',
    'wiki_pages_archive', 'wiki_revisions_list', 'wiki_pages_resolve', 'wiki_pages_upsert',
    'entities_list', 'entities_create', 'entities_resolve', 'entities_get',
    'entities_update', 'entities_archive', 'entity_aliases_create',
    'claims_list', 'claims_create', 'claims_get', 'claims_annotate', 'claims_retract',
    'entity_relations_create', 'entity_relations_update', 'entity_relations_list',
    'entity_references_create', 'entity_references_list', 'entity_references_remove',
    'knowledge_annotations_get', 'knowledge_annotations_history', 'knowledge_annotations_update',
    'knowledge_search_structured',
    'knowledge_bundle_apply',
    'knowledge_graph', 'knowledge_changes', 'knowledge_search', 'knowledge_index_status',
})
_PUBLIC_HTTP_ERRORS = frozenset({
    (410, 'content_superseded'),
    (404, 'knowledge_not_found'), (409, 'knowledge_conflict'),
    (409, 'evidence_not_ready'), (422, 'invalid_knowledge_request'),
    (503, 'service_unavailable'),
})


def mcp_knowledge_error(operation, status, detail):
    if operation not in KNOWLEDGE_OPERATIONS:
        return None
    if type(status) is int and isinstance(detail, str) and (status, detail) in _PUBLIC_HTTP_ERRORS:
        return detail, status
    return 'service_unavailable', 503
