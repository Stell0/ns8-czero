# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translate only known, value-free Core object errors into public codes."""
import re

VALIDATION_CODES = frozenset({
    'invalid_schema', 'unsupported_schema', 'invalid_unique_fields',
    'unique_string_too_long', 'unique_value_too_large', 'invalid_name',
    'invalid_label', 'invalid_json_object', 'invalid_json_key',
    'invalid_json_value', 'json_too_complex', 'json_too_large',
    'invalid_tags', 'invalid_filter', 'invalid_paging', 'invalid_revision',
    'invalid_batch', 'invalid_operation', 'invalid_cursor',
    'reference_type_mismatch', 'unknown_reference_kind',
    'invalid_object_request',
})
_COMPONENT = r'(?:[A-Za-z_][A-Za-z0-9_]{0,63}|[0-9]+)'
_RECORD_ERROR = re.compile(r'record_invalid:(?:' + _COMPONENT + r'(?:\.' + _COMPONENT + r')*)?:'
    r'(?:type|required|additionalProperties|minLength|maxLength|minItems|maxItems|'
    r'minimum|maximum|exclusiveMinimum|exclusiveMaximum|enum|const)')


def object_validation_code(detail):
    if not isinstance(detail, str):
        return None
    if detail in VALIDATION_CODES:
        return detail
    # Core returns a path and keyword, never record values or library messages.
    if len(detail) <= 1024 and _RECORD_ERROR.fullmatch(detail):
        return detail
    return None


def mcp_object_error(operation, status, detail):
    if not (operation.startswith(('object_types_', 'objects_', 'object_relations_'))
            or operation == 'references_get'):
        return None
    if status == 422:
        return object_validation_code(detail)
    if (status, detail) in ((404, 'object_not_found'), (409, 'object_conflict')):
        return detail
    return None
