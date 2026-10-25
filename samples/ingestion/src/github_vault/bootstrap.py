# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit Admin-only preparation, separate from ordinary ingestion."""
from c0_ingest.client import C0
from c0_ingest.errors import C0Error
from c0_ingest.state import digest
from .models import TYPES


def schema():
    return {'type': 'object', 'additionalProperties': False,
            'properties': {'external_key': {'type': 'string', 'maxLength': 128},
                           'github_id': {'type': 'integer'},
                           'url': {'type': 'string', 'maxLength': 4096},
                           'coverage': {'type': 'string', 'maxLength': 32},
                           'record_json': {'type': 'string', 'maxLength': 4096}},
            'required': ['external_key', 'github_id', 'url', 'coverage', 'record_json']}


def check_type(value):
    actual = value['schema']
    wanted = schema()
    if (value['unique_fields'] != ['external_key'] or actual.get('additionalProperties') is not False
            or set(actual.get('properties', {})) != set(wanted['properties'])
            or set(actual.get('required', [])) != set(wanted['required'])
            or any(actual['properties'][key].get('type') != spec['type'] for key, spec in wanted['properties'].items())):
        raise C0Error('Required immutable GitHub type is incompatible; no schema was overwritten')


def bootstrap(config):
    if 'c0:admin' not in config['scopes'].split():
        raise C0Error('Bootstrap requires separately consented c0:admin')
    client = C0(config, bootstrap=True)
    try:
        types = {t['name']: t for t in client.listing('object_types_list', 'types')}
        # Preflight every existing type before creating any missing one.
        for name in TYPES.values():
            if name in types:
                check_type(types[name])
        spaces = [s for s in client.listing('spaces_list', 'spaces') if s['name'] == config['space_name']]
        if config.get('space_id'):
            spaces = [s for s in spaces if s['id'] == config['space_id']]
            if len(spaces) != 1:
                raise C0Error('Configured target space is unavailable; refusing a replacement')
        elif len(spaces) > 1:
            raise C0Error('Ambiguous target space; configure its exact ID')
        if spaces and (spaces[0]['shared'] or spaces[0]['role'] != 'admin'):
            raise C0Error('Bootstrap requires Admin on the protected target space')
        if not spaces:
            spaces = [client.call('spaces_create', data={'name': config['space_name'],
                      'idempotency_key': digest(['ingest-space-v1', config['url'], client.profile['id'], config['space_name']])})]
        client.select_space(spaces[0]['id'])
        for name in TYPES.values():
            if name not in types:
                created = client.call('object_types_create', data={'name': name, 'label': name.replace('_', ' '),
                                      'schema': schema(), 'unique_fields': ['external_key']})
                check_type(created)
        return {'status': 'prepared', 'space_id': client.space_id, 'writes': client.writes}
    finally:
        client.close()
