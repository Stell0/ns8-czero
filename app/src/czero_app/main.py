# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel
from fastapi.responses import FileResponse, HTMLResponse

from czero_core import core_health, Database
from czero_app import __version__
from czero_app.auth import AppAuth, install_auth_routes
from czero_app.jobs import install_job_routes

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

    @asynccontextmanager
    async def lifespan(application):
        try:
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
    read_context, write_context = install_auth_routes(instance_app, auth, base_path)
    install_job_routes(instance_app, database, auth, read_context, write_context)

    @instance_app.get("/", include_in_schema=False)
    async def home() -> FileResponse:
        return FileResponse(home_page, media_type="text/html")

    @instance_app.get("/status.js", include_in_schema=False)
    async def status_script() -> FileResponse:
        return FileResponse(static_dir / "status.js", media_type="text/javascript")

    @instance_app.get("/auth.js", include_in_schema=False)
    async def auth_script() -> FileResponse:
        return FileResponse(static_dir / "auth.js", media_type="text/javascript")

    @instance_app.get("/agents", response_class=HTMLResponse, include_in_schema=False)
    async def agents() -> str:
        return (
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>C0 agent capabilities</title><main><h1>C0 agent capabilities</h1>"
            "<p>This reference runtime exposes a health endpoint and OpenAPI. "
            "Database readiness is available. Configured NS8 OIDC protects identity and membership endpoints. "
            "Admins can inspect/enqueue registered jobs and configure UTC interval schedules. "
            "A standalone worker CLI is available; the native wake timer is a pending milestone slice. "
            "Identity configuration is required for sign-in. Objects, search and MCP are planned milestones.</p>"
            "<ul><li><a href='./api/v1/health'>GET api/v1/health</a></li>"
            "<li><a href='./docs'>OpenAPI documentation</a></li></ul></main></html>"
        )

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

    if not base_path:
        return instance_app

    # NS8's Traefik route preserves /czero/<module-id>. A mount gives each
    # instance its own stable external prefix and makes OpenAPI account for it.
    root = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=lifespan)
    root.mount(base_path, instance_app, name=instance_id)
    return root


app = create_app()
