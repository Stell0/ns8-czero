# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private native settings format; Core performs runtime validation too."""
import base64
import json
import math
import re
from urllib.parse import urlsplit

VARIABLE = 'CZERO_RETRIEVAL_CONFIG_B64'


def defaults():
    return {'format': 1, 'embedding': {'enabled': False, 'endpoint': '', 'model': '',
            'dimensions': 1536, 'send_dimensions': False, 'api_key': '', 'timeout': 3},
        'scorer': {'mode': 'off', 'endpoint': '', 'model': '', 'api_key': '',
                   'timeout': 3, 'threshold': .7},
        'limits': {'max_limit': 50, 'candidates': 64, 'graph_depth': 3, 'scorer_candidates': 16}}


def validate(value):
    expected = defaults()
    if not isinstance(value, dict) or set(value) != set(expected) or type(value['format']) is not int or value['format'] != 1:
        raise ValueError('invalid_retrieval_configuration')
    for section in ('embedding', 'scorer', 'limits'):
        if not isinstance(value[section], dict) or set(value[section]) != set(expected[section]):
            raise ValueError('invalid_retrieval_configuration')
    for name in ('embedding', 'scorer'):
        item = value[name]
        active = item['enabled'] if name == 'embedding' else item['mode'] != 'off'
        if name == 'embedding':
            if type(item['enabled']) is not bool or type(item['send_dimensions']) is not bool or type(item['dimensions']) is not int or not 1 <= item['dimensions'] <= 2000:
                raise ValueError('invalid_retrieval_configuration')
        elif item['mode'] not in ('off', 'rerank', 'filter'):
            raise ValueError('invalid_retrieval_configuration')
        endpoint, model, key = item['endpoint'], item['model'], item['api_key']
        if not all(isinstance(v, str) for v in (endpoint, model, key)):
            raise ValueError('invalid_retrieval_configuration')
        if active or endpoint or model:
            url = urlsplit(endpoint)
            if (len(endpoint) > 2048 or url.scheme != 'https' or not url.hostname
                    or url.username is not None or url.password is not None or url.query or url.fragment
                    or any(c.isspace() or ord(c) < 32 for c in endpoint)
                    or (url.port is not None and not 1 <= url.port <= 65535)
                    or not re.fullmatch(r'[A-Za-z0-9_./:-]{1,128}', model)):
                raise ValueError('invalid_retrieval_configuration')
        if len(key) > 4096 or not key.isascii() or any(c.isspace() or ord(c) < 33 for c in key):
            raise ValueError('invalid_retrieval_configuration')
        for field, low, high in [('timeout', .05, 5)] + ([('threshold', 0, 1)] if name == 'scorer' else []):
            number = item[field]
            if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
                raise ValueError('invalid_retrieval_configuration')
    caps = value['limits']
    for name, low, high in [('max_limit', 1, 50), ('candidates', 1, 64), ('graph_depth', 0, 3), ('scorer_candidates', 1, 16)]:
        if type(caps[name]) is not int or not low <= caps[name] <= high:
            raise ValueError('invalid_retrieval_configuration')
    if caps['candidates'] < caps['max_limit']:
        raise ValueError('invalid_retrieval_configuration')
    encode(value)
    return value


def encode(value):
    encoded = base64.b64encode(json.dumps(value, allow_nan=False, separators=(',', ':')).encode()).decode('ascii')
    if len(encoded) > 32768:
        raise ValueError('invalid_retrieval_configuration')
    return VARIABLE + '=' + encoded + '\n'


def read(path):
    if not path.exists():
        return defaults()
    raw = path.read_text()
    if len(raw) > 32800 or not raw.startswith(VARIABLE + '=') or len(raw.splitlines()) != 1:
        raise ValueError('invalid_retrieval_configuration')
    return validate(json.loads(base64.b64decode(raw.strip().split('=', 1)[1], validate=True)))


def merge(previous, patch):
    result = json.loads(json.dumps(previous))
    if not isinstance(patch, dict) or set(patch) - {'embedding', 'scorer', 'limits'}:
        raise ValueError('invalid_retrieval_configuration')
    for section, changes in patch.items():
        allowed = set(result[section]) | ({'clear_api_key'} if section != 'limits' else set())
        if not isinstance(changes, dict) or set(changes) - allowed:
            raise ValueError('invalid_retrieval_configuration')
        changes = changes.copy()
        if section != 'limits':
            clear = changes.pop('clear_api_key', False)
            if type(clear) is not bool or (clear and changes.get('api_key')):
                raise ValueError('invalid_retrieval_configuration')
            key = changes.pop('api_key', '')
            if not isinstance(key, str):
                raise ValueError('invalid_retrieval_configuration')
            if clear or changes.get('endpoint', result[section]['endpoint']) != result[section]['endpoint']:
                result[section]['api_key'] = ''
            if key:
                result[section]['api_key'] = key
        result[section].update(changes)
    return validate(result)


def public(value):
    result = json.loads(json.dumps(value))
    result.pop('format')
    for section in ('embedding', 'scorer'):
        result[section]['api_key_configured'] = bool(result[section].pop('api_key'))
    return result
