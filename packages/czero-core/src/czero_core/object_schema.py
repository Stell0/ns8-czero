# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded JSON Schema contracts; validation never fetches or executes data."""
import json
import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
DRAFT = "https://json-schema.org/draft/2020-12/schema"
# An intentionally small, nonrecursive subset. No regex, combinators or refs:
# administrative schemas cannot introduce network calls or validation blowups.
KEYWORDS = {'$schema','title','description','type','properties','required',
    'additionalProperties','items','minItems','maxItems','minLength','maxLength',
    'minimum','maximum','exclusiveMinimum','exclusiveMaximum','enum','const'}


def bounded_json(value, *, maximum=65536, object_root=True):
    if object_root and type(value) is not dict:
        raise ValueError('invalid_json_object')
    nodes = 0
    def visit(node, depth):
        nonlocal nodes
        nodes += 1
        if depth > 16 or nodes > 4096:
            raise ValueError('json_too_complex')
        if type(node) is dict:
            for key, item in node.items():
                if type(key) is not str:
                    raise ValueError('invalid_json_key')
                visit(item,depth+1)
        elif type(node) is list:
            for item in node: visit(item,depth+1)
        elif type(node) not in (str,int,float,bool,type(None)):
            raise ValueError('invalid_json_value')
    visit(value,0)
    try:
        encoded = json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(encoded.encode('utf-8')) > maximum or '\u0000' in encoded:
            raise ValueError('json_too_large')
        # PostgreSQL rejects U+0000 and malformed Unicode; catch before SQL.
        if '\\u0000' in encoded or any(0xD800<=ord(c)<=0xDFFF for c in encoded):
            raise ValueError('invalid_json_value')
        # Ensure input strings have no unpaired surrogate even when escaped.
        encoded.encode('utf-8'); value = json.loads(encoded)
        def unicode_check(node):
            if isinstance(node,str): node.encode('utf-8')
            elif isinstance(node,dict):
                for k,v in node.items(): k.encode('utf-8'); unicode_check(v)
            elif isinstance(node,list):
                for v in node: unicode_check(v)
        unicode_check(value)
        return value
    except (TypeError,OverflowError,UnicodeError):
        raise ValueError('invalid_json_value') from None


def name(value):
    if type(value) is not str or not NAME.fullmatch(value):
        raise ValueError('invalid_name')
    return value


def schema_validator(schema):
    schema = bounded_json(schema,maximum=16384)
    if schema.get('type') != 'object' or schema.get('$schema',DRAFT) != DRAFT:
        raise ValueError('invalid_schema')
    def check(node,depth=0):
        if depth>8 or type(node) is not dict or set(node)-KEYWORDS:
            raise ValueError('unsupported_schema')
        if '$schema' in node and node['$schema']!=DRAFT: raise ValueError('invalid_schema')
        if node.get('type') not in ('object','array','string','integer','number','boolean','null'):
            raise ValueError('unsupported_schema')
        if node.get('additionalProperties',False) is not False:
            raise ValueError('unsupported_schema')
        # Every object explicitly bounds unknown fields.
        if node.get('type')=='object': node['additionalProperties']=False
        properties=node.get('properties',{})
        if type(properties) is not dict or len(properties)>64:
            raise ValueError('invalid_schema')
        for key,child in properties.items():
            if not FIELD.fullmatch(key): raise ValueError('invalid_schema')
            check(child,depth+1)
        if 'items' in node: check(node['items'],depth+1)
        if node.get('type')=='array' and ('items' not in node or not 0<=node.get('maxItems',100)<=100):
            raise ValueError('invalid_schema')
        if node.get('type')=='array': node.setdefault('maxItems',100)
        if node.get('type')=='string': node.setdefault('maxLength',8192)
        if 'maxLength' in node and (type(node['maxLength']) is not int or not 0<=node['maxLength']<=8192):
            raise ValueError('invalid_schema')
    try:
        check(schema)
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)
    except (SchemaError,TypeError):
        raise ValueError('invalid_schema') from None


def validate_record(schema,data):
    validator=schema_validator(schema)
    data=bounded_json(data)
    try: validator.validate(data)
    except ValidationError as error:
        # Path/keyword only: values and library error messages stay private.
        path='.'.join(str(p) for p in error.absolute_path)
        raise ValueError('record_invalid:'+path+':'+str(error.validator)) from None
    return data


def tags(value):
    if type(value) is not list or len(value)>32 or any(type(t) is not str or not NAME.fullmatch(t) for t in value):
        raise ValueError('invalid_tags')
    return sorted(set(value))
