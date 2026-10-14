# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Official SDK transport over the trusted C0 catalog and delegated grants.

The host must enter the returned router's lifespan before serving requests.
Public mounting/discovery follows OAuth consent/handler acceptance.
"""
import asyncio
from functools import partial
import json
import logging
import re
from urllib.parse import urlsplit

from anyio import to_thread
from fastapi import HTTPException
from mcp.server import Server
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.routes import create_protected_resource_routes
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp import types
from pydantic import AnyHttpUrl, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from czero_core.identity import PermissionDenied
from czero_core.oauth_grants import GrantRejected
from czero_core.operations import OperationRejected, SCOPES
from czero_app import __version__

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
RESOURCES = {
    'wiki/pages': ('wiki_pages_get', 'page_id', 'Wiki page with immutable content'),
    'source-versions': ('documents_get', 'version_id', 'Retained extracted document'),
    'entities': ('entities_get', 'entity_id', 'Knowledge entity metadata'),
}


class PrivateAccessToken(AccessToken):
    token: str = Field(repr=False)


class TransportUnavailable(Exception):
    pass


def _json(value):
    encoded = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    if len(encoded.encode('ascii')) > MAX_RESPONSE_BYTES:
        raise OperationRejected()
    return encoded


class TransportLimits:
    def __init__(self, app):
        self.app = app
        self.capacity = asyncio.BoundedSemaphore(8)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        async def private_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [(b'cache-control', b'no-store')]
            await send(message)
        if self.capacity.locked():
            return await JSONResponse({'error': 'server_busy'}, status_code=503)(scope, receive, private_send)
        async with self.capacity:
            try:
                await self.app(scope, receive, private_send)
            except TransportUnavailable:
                await JSONResponse({'error': 'service_unavailable'}, status_code=503)(scope, receive, private_send)


def create_mcp_app(registry, grants, *, issuer_url):
    resource = grants.resource
    parsed = urlsplit(resource)
    if parsed.path != '/mcp':
        raise ValueError('mcp_requires_hostname_root')
    if issuer_url != parsed.scheme + '://' + parsed.netloc + '/oauth':
        raise ValueError('invalid_mcp_issuer')

    async def verified(value):
        try:
            return await to_thread.run_sync(partial(grants.verify, value, resource=resource))
        except SQLAlchemyError:
            raise TransportUnavailable() from None

    class Verifier:
        async def verify_token(self, value):
            try:
                current = await verified(value)
            except GrantRejected:
                return None
            return PrivateAccessToken(token=value, client_id=current.client_id,
                subject=str(current.actor.user_id), scopes=sorted(current.scopes),
                expires_at=int(current.expires_at.timestamp()), resource=resource,
                claims={'iss': issuer_url})

    async def principal():
        token = get_access_token()
        if token is None:
            raise PermissionDenied()
        # Revocation/expiry is checked again at the operation boundary.
        return await verified(token.token)

    async def describe():
        current = await principal()
        return await to_thread.run_sync(partial(registry.describe, current.actor, scopes=current.scopes))

    async def execute(name, arguments):
        current = await principal()
        return await to_thread.run_sync(partial(registry.execute, name, current.actor,
            arguments, scopes=current.scopes))

    async def tools(ctx, params):
        return types.ListToolsResult(tools=[types.Tool(name=item['name'], description=item['description'],
            input_schema=item['input_schema'],
            output_schema=item['output_schema'] if item['output_schema'].get('type') == 'object' else None,
            annotations=types.ToolAnnotations(read_only_hint=item['read_only'])) for item in await describe()])

    async def call(ctx, params):
        try:
            result = await execute(params.name, params.arguments or {})
            encoded = _json(result)
            return types.CallToolResult(content=[types.TextContent(type='text', text=encoded)],
                structured_content=result if isinstance(result, dict) else None)
        except (PermissionDenied, GrantRejected):
            message = 'permission_denied'
        except (OperationRejected, HTTPException, ValueError):
            message = 'invalid_operation_request'
        except (SQLAlchemyError, TransportUnavailable):
            message = 'service_unavailable'
        except Exception as error:
            logging.getLogger('czero.mcp').error('Operation failed (%s)', type(error).__name__)
            message = 'service_unavailable'
        return types.CallToolResult(is_error=True, content=[types.TextContent(type='text', text=message)])

    async def resources(ctx, params):
        await describe()
        return types.ListResourcesResult(resources=[types.Resource(uri='c0://capabilities',
            name='Current capabilities', mime_type='application/json')])

    async def templates(ctx, params):
        names = {item['name'] for item in await describe()}
        return types.ListResourceTemplatesResult(resource_templates=[types.ResourceTemplate(
            uri_template='c0://' + path + '/{' + argument + '}', name=description,
            mime_type='application/json') for path, (operation, argument, description) in RESOURCES.items()
            if operation in names])

    async def read(ctx, params):
        uri = str(params.uri)
        try:
            if uri == 'c0://capabilities':
                result = {'operations': await describe()}
            else:
                match = re.fullmatch(r'c0://(wiki/pages|source-versions|entities)/([0-9a-fA-F-]{36})', uri)
                if match is None:
                    raise OperationRejected()
                operation, argument, _ = RESOURCES[match[1]]
                result = await execute(operation, {argument: match[2]})
            return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri,
                mime_type='application/json', text=_json(result))])
        except (PermissionDenied, GrantRejected, OperationRejected, HTTPException, ValueError):
            raise MCPError(-32602, 'invalid_resource_request') from None
        except (SQLAlchemyError, TransportUnavailable):
            raise MCPError(-32603, 'service_unavailable') from None

    server = Server('Czero', version=__version__, on_list_tools=tools, on_call_tool=call,
        on_list_resources=resources, on_list_resource_templates=templates, on_read_resource=read)
    child = server.streamable_http_app(stateless_http=True, json_response=True,
        max_request_body_size=1024 * 1024,
        auth=AuthSettings(issuer_url=issuer_url, resource_server_url=resource,
            validate_token_resource=True, required_scopes=[]), token_verifier=Verifier(),
        transport_security=TransportSecuritySettings(allowed_hosts=[parsed.netloc],
            allowed_origins=[parsed.scheme + '://' + parsed.netloc]))
    # Supported scopes describe capabilities; requiring all of them globally
    # would deny Readers. Replace the SDK default with its public route helper.
    metadata = create_protected_resource_routes(AnyHttpUrl(resource), [AnyHttpUrl(issuer_url)],
        scopes_supported=sorted(SCOPES), resource_name='Czero')
    path = metadata[0].path
    child.router.routes = [route for route in child.router.routes if route.path != path] + metadata
    child.add_middleware(TransportLimits)
    return child
