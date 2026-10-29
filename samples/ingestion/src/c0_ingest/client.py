# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Synchronous adapter over the official MCP client, with explicit space checks."""
from contextlib import asynccontextmanager
import json
from functools import partial

import anyio
from anyio.from_thread import start_blocking_portal
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from .auth import credentials, destination
from .errors import C0Error


class CredentialAuth(httpx2.Auth):
    def __init__(self, config):
        self.config = config

    async def async_auth_flow(self, request):
        token = await anyio.to_thread.run_sync(partial(credentials, self.config))
        request.headers['Authorization'] = 'Bearer ' + token
        yield request  # No automatic replay of writes or interactive scope upgrade.


@asynccontextmanager
async def connection(config):
    async with httpx2.AsyncClient(auth=CredentialAuth(config), follow_redirects=False,
                                 timeout=httpx2.Timeout(60)) as http:
        async with Client(streamable_http_client(config['url'], http_client=http)) as client:
            yield client


class SDKTransport:
    def __init__(self, config):
        self.portal_context = start_blocking_portal()
        self.portal = self.portal_context.__enter__()
        self.context = self.portal.wrap_async_context_manager(connection(config))
        try:
            self.client = self.context.__enter__()
        except BaseException as exc:
            self.portal_context.__exit__(None, None, None)
            if isinstance(exc, C0Error):
                raise
            raise C0Error('MCP connection failed; inspect authentication before retrying') from None

    def resource(self, uri):
        try:
            result = self.portal.call(self.client.read_resource, uri)
            return json.loads(result.contents[0].text)
        except Exception:
            raise C0Error('MCP capability discovery failed; inspect authentication') from None

    def call(self, name, arguments):
        try:
            result = self.portal.call(self.client.call_tool, name, arguments)
            return result.model_dump(by_alias=True, mode='json')
        except Exception:
            raise C0Error('MCP call failed; reconcile the operation before retrying') from None

    def close(self):
        try:
            self.context.__exit__(None, None, None)
        finally:
            self.portal_context.__exit__(None, None, None)


class C0:
    def __init__(self, config, *, transport=None, bootstrap=False):
        destination(config)
        self.config = config
        self.space_id = None
        self.writes = 0
        self.bootstrap = bootstrap
        self.transport = transport or SDKTransport(config)
        try:
            self.capabilities = self.transport.resource('c0://capabilities')
            self.operations = {op['name']: op for op in self.capabilities['operations']}
            self.profile = self.call('get_profile')
            if not config.get('account_id') or self.profile['id'] != config['account_id']:
                raise C0Error('Authenticated account ID differs from the configured expected account')
            if config.get('identity') and self.profile['nickname'] != config['identity']:
                raise C0Error('Authenticated account name differs from the configured expected account')
        except BaseException:
            self.close()
            raise

    def close(self):
        self.transport.close()

    def call(self, name, **arguments):
        operation = self.operations.get(name)
        if not operation:
            raise C0Error('Required C0 operation is unavailable: ' + name)
        properties = operation['input_schema'].get('properties', {})
        if 'space_id' in properties:
            requested = arguments.get('space_id', self.space_id)
            if not requested or requested != self.space_id:
                raise C0Error('Missing or wrong target space_id')
            arguments['space_id'] = requested
        if name == 'knowledge_search':
            options = arguments.get('options', {})
            if not self.space_id or options.get('space_id', self.space_id) != self.space_id:
                raise C0Error('Missing or wrong target search space_id')
            arguments['options'] = {**options, 'space_id': self.space_id}
        if not operation['read_only']:
            if name in {'spaces_create', 'object_types_create'}:
                if not getattr(self, 'bootstrap', False):
                    raise C0Error('Global creation requires explicit Admin bootstrap')
            elif 'space_id' not in arguments:
                raise C0Error('Write has no explicit space selector')
            self.writes += 1
        return self.decode(name, self.transport.call(name, arguments))

    @staticmethod
    def decode(name, raw):
        if raw.get('isError'):
            # Retain value-free API codes, never arbitrary server text or challenges.
            known = {'content_superseded', 'insufficient_scope', 'permission_denied', 'object_conflict', 'object_not_found',
                     'knowledge_conflict', 'knowledge_not_found', 'evidence_not_ready', 'space_conflict',
                     'invalid_space_request', 'invalid_knowledge_request', 'invalid_operation_request',
                     'service_unavailable', 'project_conflict', 'project_not_found', 'invalid_project_request', 'project_core_upgrade_required', 'project_connection_not_configured'}
            code = next((item.get('text') for item in raw.get('content', [])
                         if item.get('type') == 'text' and item.get('text') in known), 'operation_rejected')
            raise C0Error(code + ': ' + name + '; inspect authority/current state before retrying')
        if raw.get('structuredContent') is not None:
            return raw['structuredContent']
        for item in raw.get('content', []):
            if item.get('type') == 'text':
                return json.loads(item['text'])
        raise C0Error('C0 operation returned no structured payload: ' + name)

    def read_many(self, calls):
        for name, _ in calls:
            if name not in self.operations or not self.operations[name]['read_only']:
                raise C0Error('Batch is restricted to discovered read-only operations')
        return [self.call(name, **args) for name, args in calls]

    def listing(self, name, field, **arguments):
        rows, offset = [], 0
        while True:
            page = self.call(name, limit=100, offset=offset, **arguments)[field]
            rows.extend(page)
            if len(page) < 100:
                return rows
            offset += len(page)

    def select_space(self, space_id, *, writable=True):
        if not space_id:
            raise C0Error('Configure an explicit target space ID before syncing')
        self.space_id = space_id
        try:
            space = self.call('spaces_get', space_id=space_id)
        except C0Error:
            self.space_id = None
            raise
        if (writable and space['shared']) or space['role'] not in (('editor', 'admin') if writable else ('reader','editor','admin')):
            self.space_id = None
            raise C0Error('Target must be an accessible protected Editor/Admin space')
        return space
