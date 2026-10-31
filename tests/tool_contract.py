# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent structural fingerprints; documentation is not validation.

Property names and literal data are never confused with schema annotations.
"""
from copy import deepcopy
import hashlib
import json

MAP_SCHEMAS = frozenset({'properties', 'patternProperties', '$defs',
    'definitions', 'dependentSchemas'})
ONE_SCHEMA = frozenset({'items', 'additionalProperties', 'unevaluatedProperties',
    'additionalItems', 'unevaluatedItems', 'contains', 'propertyNames',
    'not', 'if', 'then', 'else', 'contentSchema'})
MANY_SCHEMAS = frozenset({'allOf', 'anyOf', 'oneOf', 'prefixItems'})


def structural_schema(schema):
    if not isinstance(schema, dict):
        return deepcopy(schema)
    result = {}
    for key, value in schema.items():
        if key in {'title', 'description'}:
            continue
        if key in MAP_SCHEMAS:
            result[key] = {name: structural_schema(child) for name, child in value.items()}
        elif key in MANY_SCHEMAS or (key == 'items' and isinstance(value, list)):
            result[key] = [structural_schema(child) for child in value]
        elif key in ONE_SCHEMA:
            result[key] = structural_schema(value)
        else:
            # enum, const, default and unknown extension values are literal.
            result[key] = deepcopy(value)
    return result


def schema_hash(schema):
    value = json.dumps(structural_schema(schema), sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(value.encode()).hexdigest()


def legacy_search_output(schema):
    """Validate the one additive field before comparing frozen authority schemas."""
    projected = deepcopy(schema)
    assert 'lexical_strategy' not in projected.get('required', [])
    field = projected['properties'].pop('lexical_strategy')
    assert structural_schema(field) == {'anyOf':[
        {'enum':['websearch','relaxed'],'type':'string'},{'type':'null'}], 'default':None}
    return projected


def operation_contract(operation):
    return {**{key: operation[key] for key in
        ('name', 'minimum_role', 'required_scope', 'read_only')},
        'input_sha256': schema_hash(operation['input_schema']),
        'output_sha256': schema_hash(operation['output_schema'])}


def route_contract(schema):
    return sorted([{'path': path, 'method': method,
        'operation': definition['x-c0-operation']['name']}
        for path, methods in schema['paths'].items()
        for method, definition in methods.items()
        if isinstance(definition, dict) and 'x-c0-operation' in definition],
        key=lambda value: (value['path'], value['method']))
