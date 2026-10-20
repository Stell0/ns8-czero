# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from czero_app.tool_guidance import annotations_for

spec = importlib.util.spec_from_file_location('tool_contract', Path(__file__).parents[1] / 'tool_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def test_documentation_fingerprint_keeps_named_properties_and_literal_values():
    schema = {'type':'object', 'title':'Presentation', 'description':'Help',
        'properties':{'title':{'type':'string', 'description':'Actual field'},
            'description':{'const':{'title':'literal', 'description':'literal data'}},
            'values':{'type':'array', 'items':{'$ref':'#/$defs/Entry'}}},
        '$defs':{'Entry':{'type':'string', 'title':'Entry title',
            'enum':['a','b'], 'default':'a'}},
        'required':['title'], 'additionalProperties':False}
    changed = deepcopy(schema)
    changed['description'] = 'Different help'
    changed['properties']['title']['description'] = 'Different field help'
    changed['$defs']['Entry']['title'] = 'Another label'
    assert contract.schema_hash(schema) == contract.schema_hash(changed)
    result = contract.structural_schema(schema)
    assert set(result['properties']) == {'title','description','values'}
    assert result['properties']['description']['const'] == {'title':'literal','description':'literal data'}
    assert schema['title'] == 'Presentation'  # Never mutate trusted schemas.


@pytest.mark.parametrize('change', ['property', 'literal', 'required', 'default', 'reference', 'extra'])
def test_validation_changes_cannot_hide_behind_documentation(change):
    original = {'type':'object', 'properties':{'title':{'type':'string', 'maxLength':8},
        'description':{'const':{'description':'original'}},
        'value':{'$ref':'#/$defs/Value'}}, '$defs':{'Value':{'type':'integer','default':1}},
        'required':['title'], 'additionalProperties':False}
    changed = deepcopy(original)
    if change == 'property': changed['properties']['title']['maxLength'] = 9
    elif change == 'literal': changed['properties']['description']['const']['description'] = 'other'
    elif change == 'required': changed['required'] = []
    elif change == 'default': changed['$defs']['Value']['default'] = 2
    elif change == 'reference': changed['properties']['value']['$ref'] = '#/$defs/Other'
    elif change == 'extra': changed['additionalProperties'] = True
    assert contract.schema_hash(original) != contract.schema_hash(changed)


def test_unreviewed_tools_keep_conservative_hints_and_fresh_metadata():
    operation = {'name':'future_operation', 'read_only':False}
    assert annotations_for(operation) == {'readOnlyHint':False,
        'destructiveHint':True, 'idempotentHint':False, 'openWorldHint':True}
    first = annotations_for({'name':'get_profile', 'read_only':True})
    first['destructiveHint'] = True
    assert annotations_for({'name':'get_profile', 'read_only':True})['destructiveHint'] is False
    assert operation == {'name':'future_operation','read_only':False}
