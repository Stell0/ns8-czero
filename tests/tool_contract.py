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
    assert 'lexical_ranker_version' not in projected.get('required', [])
    version = projected['properties'].pop('lexical_ranker_version')
    assert structural_schema(version) == {'anyOf':[{'type':'string'},{'type':'null'}], 'default':None}
    field = projected['properties'].pop('lexical_strategy')
    assert structural_schema(field) == {'anyOf':[
        {'enum':['websearch','relaxed','bm25'],'type':'string'},{'type':'null'}], 'default':None}
    definitions=projected.get('$defs',{})
    for name in ('SearchHit','StructuredHit'):
        if name not in definitions:continue
        hit=definitions[name]
        assert 'supporting_passages' not in hit.get('required',[])
        support=hit['properties'].pop('supporting_passages')
        assert structural_schema(support)=={'type':'array','maxItems':1,'items':{'$ref':'#/$defs/SearchPassage'}}
    passage=definitions.pop('SearchPassage')
    assert set(passage['required'])=={'id','kind','resource_id','revision','title','content_hash',
        'excerpt','start_offset','end_offset','citation','wiki'}
    assert set(passage['properties'])==set(passage['required'])
    for field in ('citation','wiki','excerpt','start_offset','end_offset'):
        hit=definitions.get('SearchHit',definitions.get('StructuredHit'))
        # Structured primary offsets are nullable for non-evidence records.
        if field not in ('start_offset','end_offset') or 'SearchHit' in definitions:
            assert structural_schema(passage['properties'][field])==structural_schema(hit['properties'][field])
    return projected


def legacy_search_input(schema):
    """Check the deliberate raw bound while retaining all other frozen rules."""
    projected=deepcopy(schema)
    definitions=projected.get('$defs',{})
    for candidate in (projected,definitions.get('SearchOptions',{}),definitions.get('StructuredSearch',{})):
        query=candidate.get('properties',{}).get('query')
        if query is not None:
            assert query['type']=='string' and query['minLength']==1 and query['maxLength']==8192
            query['maxLength']=512
    return projected


def legacy_index_status_output(schema):
    """Check additive optional coverage counts before frozen-schema comparison."""
    projected = deepcopy(schema)
    for name in ('source_indexed', 'wiki_indexed','source_expected','wiki_expected'):
        assert name not in projected.get('required', [])
        field = projected['properties'].pop(name)
        assert structural_schema(field) == {'anyOf':[
            {'type':'integer'}, {'type':'null'}], 'default':None}
    for name,shape in [('input_format',{'enum':['legacy','context-v1'],'type':'string'}),('complete',{'type':'boolean'})]:
        assert name not in projected.get('required',[])
        field=projected['properties'].pop(name)
        assert structural_schema(field)=={'anyOf':[shape,{'type':'null'}],'default':None}
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


def legacy_space_audience(operation):
    """Check the additive Boolean contract before comparing older frozen schemas."""
    projected = deepcopy(operation)
    def strip(schema, creating=False):
        found = 0
        for shape in [schema, *schema.get('$defs', {}).values()]:
            properties = shape.get('properties', {})
            if 'readable_by_all' not in properties:
                continue
            field = properties.pop('readable_by_all')
            assert structural_schema(field) == {'type': 'boolean', 'default': False}
            assert 'readable_by_all' not in shape.get('required', [])
            found += 1
        return found
    assert strip(projected['input_schema'], True) == (1 if operation['name'] == 'spaces_create' else 0)
    assert strip(projected['output_schema']) == 1
    return projected
