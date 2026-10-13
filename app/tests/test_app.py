# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from czero_app.main import create_app

STATIC = Path(__file__).resolve().parents[1] / "static"
DATABASE_READY = {"status": "ok", "schema_revision": "0003_sessions", "vector_version": "0.8.7"}


def ready_database():
    return SimpleNamespace(health=lambda: DATABASE_READY, close=lambda: None)



@pytest.fixture
def client():
    async def get(path):
        async with AsyncClient(
            transport=ASGITransport(app=create_app("czero17", STATIC, database=ready_database())),
            base_url="http://testserver",
        ) as session:
            return await session.get(path)

    return lambda path: asyncio.run(get(path))


def test_instance_landing_page_and_links(client):
    response = client("/czero/czero17/")
    assert response.status_code == 200
    assert "C0 application foundation" in response.text
    assert "./api/v1/health" in response.text


def test_health_contract_is_mounted_under_only_this_instance(client):
    response = client("/czero/czero17/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "czero",
        "core_version": "0.6.2",
        "app_version": "0.7.2",
        "database": DATABASE_READY,
    }
    assert client("/czero/czero18/api/v1/health").status_code == 404


def test_agents_page_describes_only_available_capabilities(client):
    response = client("/czero/czero17/agents")
    assert response.status_code == 200
    assert "Objects, search and MCP are planned" in response.text
    assert "./docs" in response.text


def test_openapi_documents_the_health_endpoint(client):
    response = client("/czero/czero17/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert "/api/v1/health" in document["paths"]
    assert document["info"]["version"] == "0.7.2"
    assert document["servers"][0]["url"] == "/czero/czero17"


def test_invalid_module_id_is_rejected():
    with pytest.raises(ValueError, match="assigned Czero module id"):
        create_app("other1", STATIC)


def test_hostname_root_endpoints_and_openapi():
    async def check():
        async with AsyncClient(transport=ASGITransport(app=create_app("czero17", STATIC, "", database=ready_database())),
                               base_url="https://c0.example.test") as session:
            for path in ("/", "/agents", "/api/v1/health", "/openapi.json", "/docs"):
                assert (await session.get(path)).status_code == 200
            document = (await session.get("/openapi.json")).json()
            assert "/api/v1/health" in document["paths"]
            assert "servers" not in document
            assert (await session.get("/czero/czero17/api/v1/health")).status_code == 404
    asyncio.run(check())


@pytest.mark.parametrize("path", ["/arbitrary", "/czero/czero18", "/", "https://other.test"])
def test_invalid_base_path_is_rejected(path):
    with pytest.raises(ValueError, match="CZERO_BASE_PATH"):
        create_app("czero17", STATIC, path)


def test_database_unavailable_is_a_safe_503():
    unavailable = {"status": "unavailable", "reason": "database_unavailable"}
    async def check():
        app = create_app("czero17", STATIC, "", database=SimpleNamespace(
            health=lambda: unavailable, close=lambda: None))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as session:
            response = await session.get("/api/v1/health")
            assert response.status_code == 503
            assert response.json()["status"] == "degraded"
            assert response.json()["database"] == unavailable
            assert "password" not in response.text
            assert (await session.get("/")).status_code == 200
    asyncio.run(check())
