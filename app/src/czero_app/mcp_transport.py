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
from czero_core.operations import OperationRejected, ScopeDenied, SCOPES
from czero_app import __version__
from czero_app.object_errors import mcp_object_error
from czero_app.knowledge_errors import KNOWLEDGE_OPERATIONS, mcp_knowledge_error

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


def _bad_request_body(body):
    """SDK envelope validation can include input_value; expose only fixed text."""
    code, message, request_id = -32600, 'invalid_mcp_request', None
    try:
        value = json.loads(body)
        error = value.get('error', {})
        candidate = error.get('code')
        if type(candidate) is int and candidate in (-32700, -32600, -32601, -32602, -32603):
            code = candidate
        # Existing resource errors have fixed application text and need normal
        # response correlation. Never pass through SDK validation diagnostics.
        if error.get('message') in ('invalid_resource_request', 'service_unavailable'):
            message = error['message']
            if value.get('id') is None or type(value.get('id')) in (str, int):
                request_id = value.get('id')
    except (ValueError, TypeError, AttributeError, RecursionError):
        pass
    return json.dumps({'jsonrpc':'2.0','id':request_id,
        'error':{'code':code,'message':message}}, separators=(',', ':')).encode()


async def oauth_tool_metadata(ctx, call_next):
    """Preserve the optional OAuth extension through MCP 2.3's wire sieve.

    The SDK's public middleware receives the already validated wire result.
    Copy only our trusted tool metadata; do not change any request or grant.
    Both protocol eras otherwise discard unknown top-level Tool properties.
    """
    result = await call_next(ctx)
    if ctx.method == 'tools/list':
        result = {**result, 'tools': [{**tool,
            'securitySchemes': tool['_meta']['securitySchemes']} for tool in result['tools']]}
    return result


class TransportLimits:
    def __init__(self, app):
        self.app = app
        self.capacity = asyncio.BoundedSemaphore(8)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        bad_start, bad_body, bad_overflow = None, bytearray(), False
        async def private_send(message):
            nonlocal bad_start, bad_overflow
            if message['type'] == 'http.response.start':
                bad_start, bad_overflow = None, False
                bad_body.clear()
                message = {**message, 'headers':list(message.get('headers', [])) + [(b'cache-control', b'no-store')]}
                if message['status'] == 400:
                    # Keep SDK request validation intact. Buffer only its bounded
                    # error response, never successful evidence/tool output.
                    bad_start = message
                    return
            if bad_start is not None and message['type'] == 'http.response.body':
                part = message.get('body', b'')
                if not bad_overflow and len(bad_body) + len(part) <= 16384:
                    bad_body.extend(part)
                else:
                    bad_overflow = True
                    bad_body.clear()
                if message.get('more_body', False):
                    return
                body = _bad_request_body(bytes(bad_body))
                headers = [(key,value) for key,value in bad_start['headers']
                    if key.lower() not in (b'content-length', b'content-type', b'transfer-encoding')]
                headers += [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())]
                await send({**bad_start, 'headers':headers})
                await send({'type':'http.response.body', 'body':body, 'more_body':False})
                bad_start = None
                return
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

    async def describe(*, include_scope_upgrades=False):
        current = await principal()
        # Discovery may show a role-eligible operation requiring fresh consent.
        # Execution and resource discovery always use the token's actual scopes.
        scopes = SCOPES if include_scope_upgrades else current.scopes
        return await to_thread.run_sync(partial(registry.describe, current.actor, scopes=scopes))

    async def execute(name, arguments):
        current = await principal()
        return await to_thread.run_sync(partial(registry.execute, name, current.actor,
            arguments, scopes=current.scopes))

    async def tools(ctx, params):
        return types.ListToolsResult(tools=[types.Tool(name=item['name'], description=item['description'],
            input_schema=item['input_schema'],
            output_schema=item['output_schema'] if item['output_schema'].get('type') == 'object' else None,
            annotations=types.ToolAnnotations(read_only_hint=item['read_only']),
            meta={'securitySchemes':[{'type':'oauth2', 'scopes':[item['required_scope']]}]})
            for item in await describe(include_scope_upgrades=True)])

    async def call(ctx, params):
        try:
            result = await execute(params.name, params.arguments or {})
            encoded = _json(result)
            return types.CallToolResult(content=[types.TextContent(type='text', text=encoded)],
                structured_content=result if isinstance(result, dict) else None)
        except ScopeDenied as error:
            # Core checks persisted membership/role before delegated scopes.
            # A role denial must never suggest that extra consent can admit it.
            challenge = (f'Bearer resource_metadata="{parsed.scheme}://{parsed.netloc}{path}", '
                'error="insufficient_scope", error_description="Additional OAuth scope is required", '
                f'scope="{error.scope}"')
            metadata = {'mcp/www_authenticate':[challenge]}
            if params.name in KNOWLEDGE_OPERATIONS:
                metadata['c0/error'] = {'code':'insufficient_scope', 'status':403}
            return types.CallToolResult(is_error=True,
                content=[types.TextContent(type='text', text='insufficient_scope')], meta=metadata)
        except (PermissionDenied, GrantRejected):
            message, status = 'permission_denied', 403
        except HTTPException as error:
            code = mcp_object_error(params.name, error.status_code, error.detail)
            if code is not None:
                return types.CallToolResult(is_error=True,
                    content=[types.TextContent(type='text', text=code)],
                    meta={'c0/error':{'code':code, 'status':error.status_code}})
            mapped = mcp_knowledge_error(params.name, error.status_code, error.detail)
            message, status = mapped if mapped is not None else ('invalid_operation_request', 422)
        except (OperationRejected, ValueError):
            message = 'invalid_knowledge_request' if params.name in KNOWLEDGE_OPERATIONS else 'invalid_operation_request'
            status = 422
        except (SQLAlchemyError, TransportUnavailable):
            message, status = 'service_unavailable', 503
        except Exception as error:
            logging.getLogger('czero.mcp').error('Operation failed (%s)', type(error).__name__)
            message, status = 'service_unavailable', 503
        metadata = {'c0/error':{'code':message, 'status':status}} if params.name in KNOWLEDGE_OPERATIONS else None
        return types.CallToolResult(is_error=True, content=[types.TextContent(type='text', text=message)], meta=metadata)

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
    server.middleware.append(oauth_tool_metadata)
    child = server.streamable_http_app(stateless_http=True, json_response=True,
        max_request_body_size=1024 * 1024,
        auth=AuthSettings(issuer_url=issuer_url, resource_server_url=resource,
            validate_token_resource=True, required_scopes=[]), token_verifier=Verifier(),
        transport_security=TransportSecuritySettings(allowed_hosts=[parsed.netloc],
            allowed_origins=[parsed.scheme + '://' + parsed.netloc]))
    # Start discovery with basic read access. Per-tool requirements/challenges
    # describe upgrades; no scope is globally mandatory for write/admin tokens.
    metadata = create_protected_resource_routes(AnyHttpUrl(resource), [AnyHttpUrl(issuer_url)],
        scopes_supported=['c0:read'], resource_name='Czero')
    path = metadata[0].path
    child.router.routes = [route for route in child.router.routes if route.path != path] + metadata
    child.add_middleware(TransportLimits)
    return child
