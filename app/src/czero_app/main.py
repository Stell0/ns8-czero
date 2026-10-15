# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
from html import escape
from pathlib import Path
from contextlib import asynccontextmanager, AsyncExitStack
from typing import Literal

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from fastapi.responses import FileResponse, HTMLResponse

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
from czero_core.retrieval_config import load_settings
from czero_app.operations import OperationCatalog
from czero_core.identity import Role
from czero_app.oauth import install_oauth_routes

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


def create_app(module_id: str | None = None, static_dir: Path | None = None,
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

    if static_dir is None:
        default_static_dir = Path(__file__).resolve().parents[2] / "static"
        static_dir = Path(os.getenv("CZERO_STATIC_DIR", default_static_dir))
    home_page = static_dir / "index.html"

    database = database if database is not None else Database()
    auth = auth if auth is not None else AppAuth.from_env(database, base_path)
    mcp_child = None

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with AsyncExitStack() as stack:
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
    # Keep the body guard inside the existing response-header middleware;
    # multipart errors are handled before crossing its task-group boundary.
    instance_app.add_middleware(UploadBodyLimit)
    read_context, write_context = install_auth_routes(instance_app, auth, base_path)
    instance_app.state.read_context = read_context
    instance_app.state.write_context = write_context
    catalog = OperationCatalog(auth)
    instance_app.state.operations = catalog.registry
    instance_app.state.operation_catalog = catalog
    originals = OriginalStore(os.getenv('CZERO_SOURCE_DIR', '/var/lib/czero/sources'))
    retrieval_settings=load_settings()
    registry = build_registry(database, originals, settings=retrieval_settings)
    install_job_routes(instance_app, database, auth, read_context, write_context, registry=registry)
    sources = install_source_routes(instance_app, database, auth, read_context, write_context, registry, originals)
    knowledge = install_knowledge_routes(instance_app, database, auth, read_context, write_context)
    install_retrieval_routes(instance_app, database, auth, read_context, settings=retrieval_settings)
    install_object_routes(instance_app, database, auth, read_context, write_context,
        reference_resolvers={**sources.reference_resolvers(), **knowledge.reference_resolvers()})
    install_oauth_routes(instance_app, auth, read_context, write_context)
    catalog.annotate_openapi(instance_app)

    @instance_app.get("/", include_in_schema=False)
    async def home() -> FileResponse:
        return FileResponse(home_page, media_type="text/html")

    @instance_app.get('/app.css', include_in_schema=False)
    async def shared_style() -> FileResponse:
        return FileResponse(static_dir / 'app.css', media_type='text/css')

    @instance_app.get('/navigation.js', include_in_schema=False)
    async def shared_navigation() -> FileResponse:
        return FileResponse(static_dir / 'navigation.js', media_type='text/javascript')

    # Presentation assets only; the domain REST/MCP interfaces stay unchanged.
    @instance_app.get('/site.js', include_in_schema=False)
    async def site_script() -> FileResponse:
        return FileResponse(static_dir / 'site.js', media_type='text/javascript')

    @instance_app.get('/reader.js', include_in_schema=False)
    async def reader_script() -> FileResponse:
        return FileResponse(static_dir / 'reader.js', media_type='text/javascript')

    @instance_app.get('/vendor/markdown-it-15.0.2.min.js', include_in_schema=False)
    async def markdown_script() -> FileResponse:
        return FileResponse(static_dir / 'vendor' / 'markdown-it-15.0.2.min.js', media_type='text/javascript')

    @instance_app.get('/admin', include_in_schema=False)
    async def admin_page() -> FileResponse:
        return FileResponse(static_dir / 'admin.html', media_type='text/html')

    @instance_app.get('/admin.js', include_in_schema=False)
    async def admin_script() -> FileResponse:
        return FileResponse(static_dir / 'admin.js', media_type='text/javascript')

    @instance_app.get("/objects", include_in_schema=False)
    async def objects_page() -> FileResponse:
        return FileResponse(static_dir / "objects.html", media_type="text/html")

    @instance_app.get('/search', include_in_schema=False)
    async def search_page() -> FileResponse:
        return FileResponse(static_dir / 'search.html', media_type='text/html')

    @instance_app.get('/search.js', include_in_schema=False)
    async def search_script() -> FileResponse:
        return FileResponse(static_dir / 'search.js', media_type='text/javascript')

    @instance_app.get('/record-fields.js', include_in_schema=False)
    async def record_fields_script() -> FileResponse:
        return FileResponse(static_dir / 'record-fields.js', media_type='text/javascript')

    @instance_app.get("/objects.js", include_in_schema=False)
    async def objects_script() -> FileResponse:
        return FileResponse(static_dir / "objects.js", media_type="text/javascript")

    @instance_app.get("/status.js", include_in_schema=False)
    async def status_script() -> FileResponse:
        return FileResponse(static_dir / "status.js", media_type="text/javascript")

    @instance_app.get('/sources', include_in_schema=False)
    async def sources_page() -> FileResponse:
        return FileResponse(static_dir / 'sources.html', media_type='text/html')

    @instance_app.get('/sources.js', include_in_schema=False)
    async def sources_script() -> FileResponse:
        return FileResponse(static_dir / 'sources.js', media_type='text/javascript')

    @instance_app.get('/wiki', include_in_schema=False)
    async def wiki_page() -> FileResponse:
        return FileResponse(static_dir / 'wiki.html', media_type='text/html')

    @instance_app.get('/wiki.js', include_in_schema=False)
    async def wiki_script() -> FileResponse:
        return FileResponse(static_dir / 'wiki.js', media_type='text/javascript')

    @instance_app.get("/auth.js", include_in_schema=False)
    async def auth_script() -> FileResponse:
        return FileResponse(static_dir / "auth.js", media_type="text/javascript")

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

    def capabilities(request):
        context = read_context(request) if (request.headers.get('authorization') is not None
            or request.cookies.get('c0_session')) else None
        operations = catalog.registry.describe(context.actor, scopes=context.scopes) if context else []
        return {'version': 1, 'authenticated': context is not None,
                'role': auth.access.authorize(context.actor, Role.READER).role.value if context else None,
                **connection_metadata(),
                'operations': operations,
                'rest_attachments': ['multipart source upload', 'retained original download', 'Markdown export']}

    @instance_app.get('/agents/capabilities.json')
    def capability_json(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return capabilities(request)

    @instance_app.get("/agents", response_class=HTMLResponse, include_in_schema=False)
    def agents(request: Request, response: Response) -> str:
        response.headers['Cache-Control'] = 'no-store'
        current = capabilities(request)
        available = ''.join('<li><code>' + escape(operation['name']) + '</code>: '
            + escape(operation['description']) + ' (' + escape(operation['required_scope']) + ')</li>'
            for operation in current['operations'])
        caller = ('Current role: ' + current['role']) if current['authenticated'] else 'Sign in to inspect your available operations.'
        connection = (
            '<h2>Connect an MCP client</h2><p>Remote MCP Streamable HTTP is available at '
            '<code>' + escape(current['mcp_url']) + '</code>. Ask an application Admin to approve '
            'your public client ID and exact callback, then sign in and explicitly consent. '
            'Use S256 and the exact server URL as the resource; no client secret or dynamic registration.</p>'
            '<p>Scopes: <code>c0:read</code>, <code>c0:write</code>, <code>c0:admin</code>. '
            'Your current role also limits every operation.</p>'
            '<label for="technical-mcp-url">Server URL</label><input id="technical-mcp-url" readonly value="' + escape(current['mcp_url'], quote=True) + '"><button type="button" data-copy-target="technical-mcp-url" data-copy-status="technical-copy-status">Copy server URL</button><p id="technical-copy-status" role="status" aria-live="polite"></p>'
            '<ul><li><a href="' + escape(current['oauth']['protected_resource_metadata'], quote=True) + '">Protected-resource metadata</a></li>'
            '<li><a href="' + escape(current['oauth']['authorization_metadata'], quote=True) + '">OAuth authorization metadata</a></li></ul>'
        ) if current['interfaces']['mcp'] else (
            '<p>MCP is unavailable until NS8 sign-in and hostname-root routing are configured.</p>')
        reference = (
            "<p>This reference runtime exposes a health endpoint and OpenAPI. "
            "Database readiness is available. Configured NS8 OIDC protects identity and membership endpoints. "
            "Admins can inspect/enqueue registered jobs and configure UTC interval schedules. "
            "A native timer wakes the standalone worker about once a minute; jobs survive restarts. "
            "Readers can inspect typed objects, sources, extracted documents and citations, and search source text. Wiki pages, immutable revisions, entity aliases, sourced claims and bounded graph queries are available. Editors can author knowledge, write records/relations and upload or retry evidence. Admins register schemas. Knowledge retrieval supports optional configured embeddings, hybrid ranking and bounded System One scoring, with text fallback. </p>"
            "<ul><li><a href='./api/v1/health'>GET api/v1/health</a></li>"
            "<li><a href='./docs'>OpenAPI documentation</a></li>"
            "<li><a href='./agents/capabilities.json'>Caller-aware capability JSON</a></li></ul>"
            + connection + "<h2>Available operations</h2><p>" + escape(caller) + "</p><ul>" + available + "</ul>"
        )
        return (static_dir / 'agents.html').read_text().replace('<!--CAPABILITIES-->', reference)

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
        grants, _ = install_oauth_server(instance_app, auth, read_context, write_context, static_dir)
        mcp_child = create_mcp_app(catalog.registry, grants,
            issuer_url=auth.oidc.config.public_origin.rstrip('/') + '/oauth')
        instance_app.state.mcp_app = mcp_child
        instance_app.mount('/', mcp_child, name='mcp')

    default_openapi = instance_app.openapi

    def described_openapi():
        schema = default_openapi()
        schema['x-c0-interfaces'] = connection_metadata()
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
