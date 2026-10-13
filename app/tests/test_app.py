# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from czero_app.main import create_app

STATIC = Path(__file__).resolve().parents[1] / "static"


@pytest.fixture
def client():
    async def get(path):
        async with AsyncClient(
            transport=ASGITransport(app=create_app("czero17", STATIC)),
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
        "core_version": "0.1.0",
        "app_version": "0.1.0",
    }
    assert client("/czero/czero18/api/v1/health").status_code == 404


def test_agents_page_describes_only_available_capabilities(client):
    response = client("/czero/czero17/agents")
    assert response.status_code == 200
    assert "Authentication, storage, search and MCP are planned" in response.text
    assert "./docs" in response.text


def test_openapi_documents_the_health_endpoint(client):
    response = client("/czero/czero17/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert "/api/v1/health" in document["paths"]
    assert document["info"]["version"] == "0.1.0"
    assert document["servers"][0]["url"] == "/czero/czero17"


def test_invalid_module_id_is_rejected():
    with pytest.raises(ValueError, match="assigned Czero module id"):
        create_app("other1", STATIC)
