# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Instance-bound downloads; fixed trusted assets and no network or file writes."""
import hashlib
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from czero_core.identity import Role
from czero_app.agent_packages import connection_reference, package_name, plugin_payload, skill_payload, zip_bytes


class PluginDownload(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    chatgpt_app_id: str = Field(min_length=1, max_length=2048)


def install_agent_downloads(app, connection_metadata, read_context, write_context):
    previous_validation = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def download_validation(request, error):
        if request.url.path.endswith('/agents/plugin.zip'):
            return JSONResponse({'detail': 'invalid_chatgpt_connection'}, status_code=422,
                                headers={'Cache-Control': 'no-store'})
        return await previous_validation(request, error)

    def url():
        value = connection_metadata()['mcp_url']
        if value is None:
            raise HTTPException(409, 'connection_not_configured')
        return value

    def response(payload, name):
        value = zip_bytes(payload)
        return Response(value, media_type='application/zip', headers={
            'Content-Disposition': 'attachment; filename="' + name + '"',
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'X-C0-Package-SHA256': hashlib.sha256(value).hexdigest()})

    @app.get('/agents/connection.json', include_in_schema=False)
    def connection(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        current = connection_metadata()
        mcp = current['mcp_url']
        host = urlsplit(mcp).hostname if mcp else None
        adapter = getattr(app.state, 'cimd', None)
        return {'available': bool(mcp), 'name': 'C0', 'hostname': host,
                'client_metadata_enabled': adapter.service.enabled() if adapter else False,
                'description': 'C0 Knowledge Storage on ' + host if host else None,
                'mcp_url': mcp, 'skill_url': './agents/c0-memory.skill' if mcp else None}

    @app.get('/agents/c0-memory.skill', include_in_schema=False)
    def skill():
        mcp = url()
        return response(skill_payload(mcp), package_name(mcp, 'c0-memory') + '.skill')

    @app.post('/agents/plugin.zip', include_in_schema=False)
    def plugin(data: PluginDownload, request: Request, context=Depends(write_context)):
        if request.headers.get('authorization') is not None:
            raise HTTPException(403, 'browser_signin_required')
        app.state.auth.access.authorize(context.actor, Role.READER)
        mcp = url()
        try:
            identifier = connection_reference(data.chatgpt_app_id)
        except ValueError:
            raise HTTPException(422, 'invalid_chatgpt_connection') from None
        name = package_name(mcp)
        return response(plugin_payload(mcp, identifier, name), name + '.zip')
