# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from czero_core.object_schema import bounded_json, schema_validator, validate_record, tags

SCHEMA={'type':'object','properties':{'name':{'type':'string','maxLength':64}},'required':['name']}


def test_schema_normalization_and_unknown_field_validation():
    v=schema_validator(SCHEMA)
    assert v.schema['additionalProperties'] is False
    assert validate_record(v.schema,{'name':'safe <script>'})=={'name':'safe <script>'}
    assert 'additionalProperties' not in SCHEMA
    for value in ({},{'name':42},{'name':'x','extra':True}):
        with pytest.raises(ValueError,match='record_invalid'): validate_record(SCHEMA,value)


@pytest.mark.parametrize('schema',[
    {'type':'object','$ref':'https://untrusted.invalid/schema'},
    {'type':'object','$defs':{'loop':{'$ref':'#/$defs/loop'}}},
    {'type':'object','properties':{'x':{'type':'string','pattern':'(a+)+$'}}},
    {'type':'object','allOf':[{'type':'object'}]},
    {'type':'object','additionalProperties':True},
    {'type':['object','null']},
    {'type':'object','properties':{'x':{'type':'array','items':{'type':'string'},'maxItems':101}}},
    {'type':'object','properties':{'x':{'type':'string','maxLength':8193}}},
    {'type':'object','required':'name'},
    {'type':'object','$schema':'http://json-schema.org/draft-07/schema#'},
])
def test_unsafe_or_invalid_schemas_are_rejected(schema):
    with pytest.raises(ValueError): schema_validator(schema)


@pytest.mark.parametrize('value',[{'x':float('nan')},{'x':object()},{'x':'\ud800'},{'x':'\0'}, {1:'bad'}, {'x':'a'*65536}])
def test_invalid_json_never_reaches_postgresql(value):
    with pytest.raises(ValueError): bounded_json(value)


def test_depth_and_node_limits():
    deep={}; child=deep
    for _ in range(17): child['x']={}; child=child['x']
    with pytest.raises(ValueError): bounded_json(deep)
    with pytest.raises(ValueError): bounded_json({'x':[0]*4096})
    assert tags(['inventory','priority','inventory'])==['inventory','priority']
    with pytest.raises(ValueError): tags(['two words'])


def test_validation_errors_do_not_echo_record_values():
    with pytest.raises(ValueError) as e: validate_record(SCHEMA,{'name':'private-value'*10})
    assert str(e.value)=='record_invalid:name:maxLength'
