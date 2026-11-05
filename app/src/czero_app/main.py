# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
from pathlib import Path
from contextlib import asynccontextmanager, AsyncExitStack
from typing import Literal

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from czero_core import core_health, Database
from czero_app import __version__
from czero_app.auth import AppAuth, install_auth_routes
from czero_app.jobs import install_job_routes
from czero_app.objects import install_object_routes
from czero_app.sources import install_source_routes, UploadBodyLimit
from czero_app.job_handlers import build_registry
from czero_core.sources import OriginalStore
from czero_app.knowledge import install_knowledge_routes
from czero_app.retrieval import install_retrieval_routes
from czero_app.annotations import install_annotation_routes
from czero_app.bundles import install_bundle_routes
from czero_core.retrieval_config import load_settings
from czero_app.operations import OperationCatalog
from czero_core.identity import Role
from czero_app.oauth import install_oauth_routes
from czero_app.spaces import install_space_routes, ExactSpaceSelector
from czero_app.profile import install_profile_routes
from czero_app.projects import install_project_routes

_MODULE_ID = re.compile(r"czero[0-9]+\Z")


class DatabaseHealth(BaseModel):
    status: Literal["ok", "unavailable"]
    schema_revision: str | None = None
    vector_version: str | None = None
    reason: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    core_version: str
    app_version: str
    database: DatabaseHealth


def create_app(module_id: str | None = None, frontend_dir: Path | None = None,
               base_path: str | None = None, database: Database | None = None,
               *, auth: AppAuth | None = None) -> FastAPI:
    """Create a hostname-root application or preserve a legacy NS8 path."""
    instance_id = module_id if module_id is not None else os.getenv("CZERO_MODULE_ID", "")
    if not _MODULE_ID.fullmatch(instance_id):
        raise ValueError("CZERO_MODULE_ID must be an assigned Czero module id")

    legacy_path = f"/czero/{instance_id}"
    base_path = os.getenv("CZERO_BASE_PATH", legacy_path) if base_path is None else base_path
    if base_path not in ("", legacy_path):
        raise ValueError("CZERO_BASE_PATH must be empty or the assigned instance path")

    if frontend_dir is None:
        frontend_dir = Path(os.getenv('CZERO_FRONTEND_DIR',
            Path(__file__).resolve().parents[2] / 'frontend' / 'dist'))

    database = database if database is not None else Database()
    auth = auth if auth is not None else AppAuth.from_env(database, base_path)
    mcp_child = None
    from czero_app.cimd_config import configured as cimd_configured
    cimd_enabled = cimd_configured() and auth is not None and not base_path

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with AsyncExitStack() as stack:
                from anyio import to_thread
                from czero_core.cimd import CimdPolicyService
                await to_thread.run_sync(CimdPolicyService(database).sync_policy, bool(cimd_enabled))
                cimd = getattr(instance_app.state, 'cimd', None)
                if cimd is not None:
                    stack.push_async_callback(cimd.fetcher.aclose)
                if mcp_child is not None:
                    await stack.enter_async_context(mcp_child.router.lifespan_context(mcp_child))
                yield
        finally:
            if auth is not None:
                auth.oidc.close()
            database.close()

    instance_app = FastAPI(
        title="C0 API",
        version=__version__,
        description="Czero reference application API",
        redoc_url=None,
        lifespan=lifespan,
    )
    instance_app.state.auth = auth
    from czero_app.website import Website
    instance_app.state.website = Website(frontend_dir, base_path)
    instance_app.state.website.install(instance_app)
    instance_app.add_middleware(ExactSpaceSelector)
    # Keep the body guard inside the existing response-header middleware;
    # multipart errors are handled before crossing its task-group boundary.
    instance_app.add_middleware(UploadBodyLimit)
    read_context, write_context = install_auth_routes(instance_app, auth, base_path)
    instance_app.state.read_context = read_context
    instance_app.state.write_context = write_context
    from czero_app.api_keys import install as install_api_keys
    install_api_keys(instance_app, auth, read_context, write_context)
    catalog = OperationCatalog(auth)
    instance_app.state.operations = catalog.registry
    instance_app.state.operation_catalog = catalog
    install_profile_routes(instance_app, auth, read_context)
    install_project_routes(instance_app, database, auth, read_context, write_context)
    install_space_routes(instance_app, database, auth, read_context, write_context)
    originals = OriginalStore(os.getenv('CZERO_SOURCE_DIR', '/var/lib/czero/sources'))
    retrieval_settings=load_settings()
    registry = build_registry(database, originals, settings=retrieval_settings)
    install_job_routes(instance_app, database, auth, read_context, write_context, registry=registry)
    sources = install_source_routes(instance_app, database, auth, read_context, write_context, registry, originals)
    from czero_app.extraction_status import install as install_extraction_status
    install_extraction_status(instance_app,auth,sources,read_context,write_context)
    knowledge = install_knowledge_routes(instance_app, database, auth, read_context, write_context)
    install_retrieval_routes(instance_app, database, auth, read_context, settings=retrieval_settings)
    install_annotation_routes(instance_app, database, auth, read_context, write_context)
    install_bundle_routes(instance_app, database, auth, write_context)
    install_object_routes(instance_app, database, auth, read_context, write_context,
        reference_resolvers={**sources.reference_resolvers(), **knowledge.reference_resolvers()})
    install_oauth_routes(instance_app, auth, read_context, write_context)
    catalog.annotate_openapi(instance_app)

    def connection_metadata():
        available = mcp_child is not None
        origin = auth.oidc.config.public_origin.rstrip('/') if available else None
        return {'interfaces': {'rest': True, 'mcp': available},
                'rest_base': base_path + '/api/v1',
                'mcp_url': origin + '/mcp' if available else None,
                'oauth': {'authorization_server': origin + '/oauth',
                    'authorization_metadata': origin + '/.well-known/oauth-authorization-server/oauth',
                    'protected_resource_metadata': origin + '/.well-known/oauth-protected-resource/mcp',
                    'scopes': ['c0:read', 'c0:write', 'c0:admin'],
                    'public_clients_only': True, 'dynamic_registration': False} if available else None}

    instance_app.state.connection_metadata = connection_metadata
    from czero_app.agent_downloads import install_agent_downloads
    install_agent_downloads(instance_app, connection_metadata, read_context, write_context)

    def capabilities(request):
        context = read_context(request) if (request.headers.get('authorization') is not None
            or request.cookies.get('c0_session')) else None
        from czero_app.tool_guidance import presented_operations
        operations = presented_operations(catalog.registry.describe(context.actor, scopes=context.scopes)) if context else []
        from czero_app.agent_guidance import agent_guidance
        return {'version': 1, 'authenticated': context is not None,
                'role': auth.access.authorize(context.actor, Role.READER).role.value if context else None,
                **connection_metadata(),
                'operations': operations, 'guidance': agent_guidance(operations),
                'rest_attachments': ['multipart source upload', 'retained original download', 'Markdown export']}

    @instance_app.get('/agents/capabilities.json')
    def capability_json(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return capabilities(request)

    @instance_app.get("/api/v1/health", name="health", response_model=HealthResponse,
                      response_model_exclude_none=True,
                      responses={503: {"description": "Database unavailable"}})
    def health(response: Response) -> HealthResponse:
        db_health = database.health()
        result = {**core_health(), "app_version": __version__, "database": db_health}
        if db_health["status"] != "ok":
            response.status_code = 503
            result["status"] = "degraded"
        return HealthResponse(**result)

    if auth is not None and not base_path:
        from czero_app.oauth_server import install_oauth_server
        from czero_app.mcp_transport import create_mcp_app
        grants, _ = install_oauth_server(instance_app, auth, read_context, write_context)
        mcp_child = create_mcp_app(catalog.registry, grants,
            issuer_url=auth.oidc.config.public_origin.rstrip('/') + '/oauth', api_keys=getattr(instance_app.state, 'api_keys', None))
        instance_app.state.mcp_app = mcp_child
        instance_app.mount('/', mcp_child, name='mcp')
    elif auth is not None:
        # Keep first-party access administration on supported legacy REST
        # mounts without advertising or mounting OAuth/MCP on those paths.
        from czero_core.oauth_grants import OAuthGrantService
        from czero_app.workspace_access import install_workspace_routes
        workspace_grants = OAuthGrantService(auth.access, auth.sessions.client_id,
            auth.oidc.config.public_origin.rstrip('/') + base_path + '/mcp',
            authority=auth.sessions.authority)
        install_workspace_routes(instance_app, workspace_grants, read_context, write_context, None)


    default_openapi = instance_app.openapi

    def described_openapi():
        schema = default_openapi()
        schema['x-c0-interfaces'] = connection_metadata()
        from czero_app.agent_guidance import agent_guidance
        schema['x-c0-agent-guidance'] = agent_guidance()
        return schema

    instance_app.openapi = described_openapi

    if not base_path:
        return instance_app

    # NS8's Traefik route preserves /czero/<module-id>. A mount gives each
    # instance its own stable external prefix and makes OpenAPI account for it.
    root = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=lifespan)
    root.mount(base_path, instance_app, name=instance_id)
    return root


app = create_app()
