# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import logging

from httpx import ASGITransport, AsyncClient

from czero_app.auth import SafeAccessLog
from czero_app.main import create_app


def test_access_logs_do_not_contain_callback_query_credentials():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 1,
        '%s - "%s %s HTTP/%s" %d',
        ("address", "GET", "/auth/callback?code=sensitive-value&state=sensitive-value", "1.1", 302), None)
    assert SafeAccessLog().filter(record)
    assert "sensitive-value" not in record.getMessage()
    assert "/auth/callback" in record.getMessage()


def test_unconfigured_app_fails_closed_and_documents_auth_schemes():
    async def check():
        app = create_app("czero901", base_path="")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://c0.example.test") as client:
            assert (await client.get("/api/v1/auth/status")).json() == {"configured": False}
            assert (await client.get("/auth/login")).status_code == 503
            assert (await client.get("/api/v1/me")).status_code == 401
            document = (await client.get("/openapi.json")).json()
            assert document["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
            assert document["components"]["securitySchemes"]["SessionCookie"]["name"] == "c0_session"
            assert document["paths"]["/api/v1/me"]["get"]["security"] == [{"BearerAuth": []}, {"SessionCookie": []}]
    asyncio.run(check())


def test_request_id_reaches_default_uvicorn_logs():
    import subprocess
    import sys
    from textwrap import dedent

    result = subprocess.run([sys.executable, '-c', dedent("""
        import asyncio

        import uvicorn
        from httpx import ASGITransport, AsyncClient
        from czero_app.main import create_app

        uvicorn.Config('czero_app.main:app').configure_logging()

        async def main():
            app = create_app('czero901', base_path='')
            async with AsyncClient(transport=ASGITransport(app=app), base_url='https://c0.example.test') as client:
                response = await client.get('/api/v1/me?probe=private-test-marker')
                assert response.status_code == 401
                print(response.headers['x-c0-request-id'])

        asyncio.run(main())
    """)], check=True, capture_output=True, text=True, timeout=20)

    request_id = result.stdout.strip()
    assert len(request_id) == 32
    assert f'rest response 401 request {request_id}' in result.stderr
    assert 'private-test-marker' not in result.stderr
