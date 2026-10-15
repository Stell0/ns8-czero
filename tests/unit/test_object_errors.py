# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from czero_app.object_errors import object_validation_code, mcp_object_error


@pytest.mark.parametrize('code', ['unique_string_too_long', 'invalid_schema', 'unsupported_schema',
    'record_invalid::required', 'record_invalid:name:type', 'record_invalid:parts.0.name:maxLength'])
def test_known_value_free_validation_codes_are_public(code):
    assert object_validation_code(code) == code
    assert mcp_object_error('object_types_create', 422, code) == code


@pytest.mark.parametrize('detail', [None, {'secret':'synthetic-private'}, ['synthetic-private'],
    'database connection failed: synthetic-private', 'record_invalid:name:type:synthetic-private',
    'record_invalid:name:type\nsynthetic-private', 'record_invalid:private value:type',
    'record_invalid:name:private_validator', 'record_invalid:' + 'a' * 1025 + ':type'])
def test_unexpected_messages_and_values_never_become_public_codes(detail):
    assert object_validation_code(detail) is None
    assert mcp_object_error('objects_create', 422, detail) is None


def test_mcp_public_errors_are_limited_to_object_operations_and_expected_statuses():
    assert mcp_object_error('objects_get', 404, 'object_not_found') == 'object_not_found'
    assert mcp_object_error('objects_update', 409, 'object_conflict') == 'object_conflict'
    assert mcp_object_error('wiki_pages_get', 422, 'invalid_schema') is None
    assert mcp_object_error('objects_create', 403, 'unique_string_too_long') is None
    assert mcp_object_error('objects_create', 500, 'invalid_schema') is None
    assert mcp_object_error('objects_get', 404, {'secret':'synthetic-private'}) is None
