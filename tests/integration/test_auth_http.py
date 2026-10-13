# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from pathlib import Path
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from joserfc import jwt
from joserfc.jwk import RSAKey
import pytest
from sqlalchemy import text

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import TokenVerifier
from czero_core.migrate import migrate_database
from czero_core.oidc import OidcConfig, OidcUnavailable
from czero_core.sessions import SessionService

pytestmark = pytest.mark.skipif(not os.getenv("CZERO_TEST_DATABASE_URL"), reason="isolated PostgreSQL URL required")
ORIGIN = "https://c0.example.test"


class PrivateFixture(tuple):
    def __repr__(self):
        return "<private authentication fixture>"


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setenv("CZERO_MODULE_ID", "czero900")
    monkeypatch.setenv("CZERO_DATABASE_URL", os.environ["CZERO_TEST_DATABASE_URL"])
    from czero_app.auth import AppAuth
    from czero_app.main import create_app
    database = Database(os.environ["CZERO_TEST_DATABASE_URL"])
    migrate_database(database)
    issuer = "https://idp.example.test/realms/" + str(uuid4())
    owner_key, member_key = uuid4(), uuid4()
    signer = RSAKey.generate_key(2048, {"kid": "trusted", "use": "sig"})
    verifier = TokenVerifier(issuer, "czero900", {"keys": [signer.as_dict(private=False)]})
    def token(key, username, kind="Bearer", **extra):
        claims = {"iss": issuer, "aud": "czero900", "ldap_uuid": str(key), "sub": str(key),
                  "preferred_username": username, "iat": int(time.time()) - 1,
                  "exp": int(time.time()) + 300, "typ": kind, **extra}
        return jwt.encode({"alg": "RS256", "kid": "trusted"}, claims, signer)
    class Provider:
        config = OidcConfig(issuer, "czero900", "unit-only-client-value", ORIGIN)
        verify_access_token = staticmethod(verifier.verify_access_token)
        def authorization_url(self, pending):
            return issuer + "/authorize?" + urlencode({"state": pending.state})
        def exchange(self, code, login):
            return verifier.verify_id_token(token(owner_key, "owner", "ID", nonce=login.nonce), nonce=login.nonce)
        def logout_url(self):
            return issuer + "/logout?" + urlencode({"client_id": "czero900", "post_logout_redirect_uri": ORIGIN + "/"})
        def close(self):
            pass
    access = AccessService(database, issuer, owner_key)
    auth = AppAuth(access, SessionService(access, "czero900"), Provider())
    app = create_app("czero900", Path(__file__).resolve().parents[2] / "app/static", "", database, auth=auth)
    yield PrivateFixture((app, token(owner_key, "owner"), token(member_key, "member", role="admin"), token(owner_key, "owner", "ID"), database, issuer))
    with database.engine.begin() as connection:
        connection.execute(text("DELETE FROM c0_login_states WHERE issuer = :issuer"), {"issuer": issuer})
        connection.execute(text("DELETE FROM c0_accounts WHERE issuer = :issuer"), {"issuer": issuer})
    database.close()


def test_rest_roles_and_negative_token_authorization(application):
    async def check():
        app, owner, member, id_token, _, _ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get("/api/v1/me")).status_code == 401
            for value in ("malformed", id_token):
                result = await client.get("/api/v1/me", headers={"Authorization": "Bearer " + value})
                assert result.status_code == 401
                assert result.json() == {"detail": "invalid_token"}
            assert (await client.get("/api/v1/me", headers={"Authorization": "Bearer " + member})).status_code == 403
            client.headers["Authorization"] = "Bearer " + owner
            me = (await client.get("/api/v1/me")).json()
            assert me["role"] == "admin" and me["is_owner"]
            assert "csrf_token" not in me
            account = next(row for row in (await client.get("/api/v1/access/accounts")).json()["accounts"] if row["username"] == "member")
            path = "/api/v1/access/accounts/" + account["id"]
            assert (await client.put(path, json={"role": "reader"})).status_code == 204
            client.headers["Authorization"] = "Bearer " + member
            assert (await client.get("/api/v1/me")).json()["role"] == "reader"
            assert (await client.put(path, json={"role": "admin"})).status_code == 403
            client.headers["Authorization"] = "Bearer " + owner
            assert (await client.put(path, json={"role": "editor"})).status_code == 204
            client.headers["Authorization"] = "Bearer " + member
            assert (await client.get("/api/v1/access/accounts")).status_code == 403
            client.headers["Authorization"] = "Bearer " + owner
            assert (await client.put("/api/v1/access/accounts/" + me["id"], json={"role": "reader"})).status_code == 403
    asyncio.run(check())


def test_browser_cookie_flags_callback_logout_and_csrf(application):
    async def check():
        app, _, _, _, _, _ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get("/api/v1/auth/status")).json() == {"configured": True}
            started = await client.get("/auth/login")
            assert started.status_code == 302
            flags = started.headers["set-cookie"]
            assert "HttpOnly" in flags and "Secure" in flags and "SameSite=lax" in flags
            state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
            completed = await client.get("/auth/callback", params={"state": state, "code": "unit-only-code"})
            assert completed.status_code == 302
            assert completed.headers["location"] == "/"
            flags = completed.headers["set-cookie"]
            assert "HttpOnly" in flags and "Secure" in flags and "SameSite=lax" in flags
            me = await client.get("/api/v1/me")
            assert me.headers["cache-control"] == "no-store"
            assert me.json()["username"] == "owner"
            invalid_bearer = await client.get("/api/v1/me", headers={"Authorization": "Bearer malformed"})
            assert invalid_bearer.status_code == 401
            assert (await client.post("/auth/logout")).status_code == 403
            csrf = me.json()["csrf_token"]
            assert (await client.post("/auth/logout", headers={"X-C0-CSRF": csrf, "Origin": "https://untrusted.example.test"})).status_code == 403
            result = await client.post("/auth/logout", headers={"X-C0-CSRF": csrf, "Origin": ORIGIN})
            assert result.status_code == 200 and "logout_url" in result.json()
            assert (await client.get("/api/v1/me")).status_code == 401
            replayed = await client.get("/auth/callback", params={"state": state, "code": "unit-only-code"})
            assert replayed.status_code == 400
    asyncio.run(check())


def test_expired_cookie_session_is_rejected(application):
    async def check():
        app, _, _, _, database, issuer = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            started = await client.get("/auth/login")
            state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
            await client.get("/auth/callback", params={"state": state, "code": "unit-only-code"})
            with database.engine.begin() as connection:
                connection.execute(text("UPDATE c0_sessions SET expires_at = now() - interval '1 second' WHERE issuer = :issuer"), {"issuer": issuer})
            assert (await client.get("/api/v1/me")).status_code == 401
    asyncio.run(check())


def test_local_logout_completes_during_provider_outage(application, monkeypatch):
    async def check():
        app, _, _, _, _, _ = application
        def unavailable():
            raise OidcUnavailable()
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            started = await client.get("/auth/login")
            state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
            await client.get("/auth/callback", params={"state": state, "code": "unit-only-code"})
            csrf = (await client.get("/api/v1/me")).json()["csrf_token"]
            monkeypatch.setattr(app.state.auth.oidc, "logout_url", unavailable)
            result = await client.post("/auth/logout", headers={"X-C0-CSRF": csrf, "Origin": ORIGIN})
            assert result.status_code == 200
            assert result.json() == {"logout_url": ORIGIN + "/", "provider_logout": False}
            assert (await client.get("/api/v1/me")).status_code == 401
    asyncio.run(check())
