# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from czero_core import core_health
from czero_app import __version__

_MODULE_ID = re.compile(r"czero[0-9]+\Z")


def create_app(module_id: str | None = None, static_dir: Path | None = None) -> FastAPI:
    """Create the NS8 path-mounted instance application."""
    instance_id = module_id if module_id is not None else os.getenv("CZERO_MODULE_ID", "")
    if not _MODULE_ID.fullmatch(instance_id):
        raise ValueError("CZERO_MODULE_ID must be an assigned Czero module id")

    if static_dir is None:
        default_static_dir = Path(__file__).resolve().parents[2] / "static"
        static_dir = Path(os.getenv("CZERO_STATIC_DIR", default_static_dir))
    home_page = static_dir / "index.html"

    instance_app = FastAPI(
        title="C0 API",
        version=__version__,
        description="Czero reference application API",
        redoc_url=None,
    )

    @instance_app.get("/", include_in_schema=False)
    async def home() -> FileResponse:
        return FileResponse(home_page, media_type="text/html")

    @instance_app.get("/agents", response_class=HTMLResponse, include_in_schema=False)
    async def agents() -> str:
        return (
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>C0 agent capabilities</title><main><h1>C0 agent capabilities</h1>"
            "<p>This M01 reference runtime exposes a health endpoint and OpenAPI. "
            "Authentication, storage, search and MCP are planned milestones.</p>"
            "<ul><li><a href='./api/v1/health'>GET api/v1/health</a></li>"
            "<li><a href='./docs'>OpenAPI documentation</a></li></ul></main></html>"
        )

    @instance_app.get("/api/v1/health", name="health")
    async def health() -> dict[str, str]:
        return {**core_health(), "app_version": __version__}

    # NS8's Traefik route preserves /czero/<module-id>. A mount gives each
    # instance its own stable external prefix and makes OpenAPI account for it.
    root = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    root.mount(f"/czero/{instance_id}", instance_app, name=instance_id)
    return root


app = create_app()
