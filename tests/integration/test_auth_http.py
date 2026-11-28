# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
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
        def authorization_url(self, pending, *, reauthenticate=False):
            return issuer + "/authorize?" + urlencode({"state": pending.state,
                **({"prompt": "login"} if reauthenticate else {})})
        def exchange(self, code, login):
            key, username = (member_key, "member") if code == "unit-only-forbidden-code" else (owner_key, "owner")
            return verifier.verify_id_token(token(key, username, "ID", nonce=login.nonce), nonce=login.nonce)
        def logout_url(self):
            return issuer + "/logout?" + urlencode({"client_id": "czero900", "post_logout_redirect_uri": ORIGIN + "/"})
        def close(self):
            pass
    access = AccessService(database, issuer, owner_key)
    auth = AppAuth(access, SessionService(access, "czero900"), Provider())
    app = create_app("czero900", Path(__file__).resolve().parents[2] / "app/frontend/dist", "", database, auth=auth)
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


@pytest.mark.parametrize('target,expected', [
    ('admin/advanced', '/admin/advanced'),
    ('wiki/33333333-3333-4333-8333-333333333333?space_id=22222222-2222-4222-8222-222222222222&revision=3',
     '/wiki/33333333-3333-4333-8333-333333333333?space_id=22222222-2222-4222-8222-222222222222&revision=3'),
    ('sources/33333333-3333-4333-8333-333333333333?version=22222222-2222-4222-8222-222222222222',
     '/sources/33333333-3333-4333-8333-333333333333?version=22222222-2222-4222-8222-222222222222'),
    ('search?query=Juniper+batch&mode=text', '/search?query=Juniper+batch&mode=text'),
    ('not-a-website-route', '/'),
])
def test_sign_in_returns_to_supported_website_destination(application, target, expected):
    async def check():
        app, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            page = await client.get('/auth/sign-in', params={'return_to': target})
            boot = json.loads(page.text.split('<script id="c0-boot" type="application/json">')[1].split('</script>')[0])
            login = await client.post('/auth/sign-in', headers={'Origin': ORIGIN}, data={
                'intent': boot['intent'], 'return_to': boot['return_to'],
            })
            assert login.status_code == 302
            state = parse_qs(urlsplit(login.headers['location']).query)['state'][0]
            callback = await client.get('/auth/callback', params={'state': state, 'code': 'unit-only-code'})
            assert callback.status_code == 302
            assert callback.headers['location'] == expected
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


@pytest.mark.parametrize("base_path", ["", "/czero/czero900"])
@pytest.mark.parametrize("already_signed_in", [False, True])
def test_forbidden_browser_login_can_retry_with_another_account(application, base_path, already_signed_in):
    async def check():
        from czero_app.main import create_app
        app, owner, member, _, database, _ = application
        auth = app.state.auth
        if base_path:
            app = create_app("czero900", Path(__file__).resolve().parents[2] / "app/frontend/dist",
                             base_path, database, auth=app.state.auth)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            old_session = None
            if already_signed_in:
                identity = auth.oidc.verify_access_token(owner)
                old_session = auth.sessions.create(identity)
                client.cookies.set('c0_session', old_session, domain='c0.example.test', path=base_path+'/')
                assert (await client.get(base_path + '/api/v1/me')).status_code == 200
            started = await client.get(base_path + "/auth/login")
            state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
            assert "prompt" not in parse_qs(urlsplit(started.headers["location"]).query)
            from czero_app.auth import attempt_cookie
            cookie_name = attempt_cookie(state, base_path + '/') if hasattr(auth.sessions, 'claim_browser_login') else 'c0_login'
            binding = client.cookies.get(cookie_name)
            if hasattr(auth.sessions, 'claim_browser_login'):
                from czero_app.auth import cookie_namespace
                namespace = cookie_namespace(base_path + '/')
                owner_name = '__Host-c0-login-owner-' + namespace
                assert cookie_name.startswith('__Host-c0-attempt-' + namespace + '-')
                proof_cookies = [c for c in client.cookies.jar if c.name in (cookie_name, owner_name)]
                assert len(proof_cookies) == 2
                assert all(c.path == '/' and c.secure and not c.domain_specified for c in proof_cookies)
                assert all(c.path == base_path + '/' for c in client.cookies.jar if c.name == 'c0_session')
            denied = await client.get(base_path + "/auth/callback",
                params={"state": state, "code": "unit-only-forbidden-code"})
            assert denied.status_code == 403
            assert denied.headers["content-type"].startswith("text/html")
            assert denied.headers["cache-control"] == "no-store"
            assert denied.headers["referrer-policy"] == "no-referrer"
            boot=json.loads(denied.text.split('id="c0-boot" type="application/json">')[1].split('</script>')[0])
            assert boot=={'error':'access_denied'}
            with database.engine.connect() as connection:
                recorded = connection.execute(text('''SELECT a.username,m.role FROM c0_accounts a
                    LEFT JOIN c0_memberships m ON m.account_id=a.id
                    WHERE a.issuer=:issuer AND a.username='member' '''), {'issuer': auth.access.issuer}).one()
                assert tuple(recorded) == ('member', None)
            assert '<base href="'+base_path+'/"' in denied.text
            assert state not in denied.text and "unit-only-forbidden-code" not in denied.text
            binding_present = cookie_name in client.cookies
            session_present = "c0_session" in client.cookies
            assert not binding_present and not session_present
            if old_session:
                stale = await client.get(base_path + '/api/v1/me', headers={'Cookie':'c0_session='+old_session})
                assert stale.status_code == 401
            assert (await client.get(base_path + "/api/v1/me")).status_code == 401
            replay = await client.get(base_path + "/auth/callback",
                params={"state":state,"code":"unit-only-code"}, headers={"Cookie":cookie_name+"="+binding})
            assert replay.status_code == 400
            api_denied = await client.get(base_path + "/api/v1/me",
                headers={"Authorization": "Bearer " + member})
            assert api_denied.status_code == 403 and api_denied.json() == {"detail": "forbidden"}
            retry = await client.get(base_path + "/auth/login?switch_account=true")
            parameters = parse_qs(urlsplit(retry.headers["location"]).query)
            assert parameters["prompt"] == ["login"] and parameters["state"] != [state]
            accepted = await client.get(base_path + "/auth/callback",
                params={"state": parameters["state"][0], "code": "unit-only-code"})
            assert accepted.status_code == 302 and accepted.headers["location"] == base_path + "/"
            assert (await client.get(base_path + "/api/v1/me")).json()["username"] == "owner"
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


def test_rejected_callback_never_consumes_malformed_input_or_reuses_provider_error(application):
    async def check():
        app, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as browser:
            started = await browser.get('/auth/login')
            state = parse_qs(urlsplit(started.headers['location']).query)['state'][0]
            for bad in [
                [('code','one'), ('code','two')],
                [('state',state), ('code','one')],
                [('code','one'), ('error','access_denied')],
                [('iss','https://untrusted.invalid'), ('code','one')],
            ]:
                response = await browser.get('/auth/callback', params=[('state',state), *bad])
                assert response.status_code == 400
                assert 'callback_rejected' in response.text and state not in response.text
            error = await browser.get('/auth/callback', params={'state':state,'error':'temporarily_unavailable',
                                                                'error_description':'private-provider-explanation'})
            assert error.status_code == 503 and 'provider_unavailable' in error.text
            assert state not in error.text and 'private-provider-explanation' not in error.text
            assert error.headers['cache-control'] == 'no-store'
            assert error.headers['referrer-policy'] == 'no-referrer'
            stale = await browser.get('/auth/callback', params={'state':state,'code':'unit-only-code'})
            assert stale.status_code == 400
            fresh = await browser.get('/auth/login')
            next_state = parse_qs(urlsplit(fresh.headers['location']).query)['state'][0]
            assert next_state != state
            completed = await browser.get('/auth/callback', params={'state':next_state,'code':'unit-only-code'})
            assert completed.status_code == 302 and (await browser.get('/api/v1/me')).status_code == 200
    asyncio.run(check())


def test_logout_received_with_predecessor_cookie_after_callback_publication(application):
    async def check():
        app, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as browser:
            for step in range(3):
                start = await browser.get('/auth/login')
                state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]
                callback = await browser.get('/auth/callback', params={'state':state,'code':'unit-only-code'})
                assert callback.status_code == 302
                if step == 0:
                    old = browser.cookies['c0_session']
                    csrf = (await browser.get('/api/v1/me')).json()['csrf_token']
            headers = {'Cookie':'c0_session='+old,'Origin':ORIGIN, 'X-C0-CSRF':'wrong-proof'}
            assert (await browser.get('/auth/login',headers={'Cookie':'c0_session='+old})).status_code == 400
            assert (await browser.post('/auth/logout',headers=headers)).status_code in (401,403)
            assert (await browser.get('/api/v1/me')).status_code == 200
            headers['X-C0-CSRF'] = csrf
            successor = browser.cookies['c0_session']
            assert (await browser.post('/auth/logout',headers=headers)).status_code == 200
            assert (await browser.get('/api/v1/me',headers={'Cookie':'c0_session='+successor})).status_code == 401
            assert (await browser.post('/auth/logout',headers=headers)).status_code in (401,403)
    asyncio.run(check())

@pytest.mark.parametrize('failure', ['provider','database','authority'])
def test_callback_error_does_not_fill_browser_attempt_capacity(application, monkeypatch, failure):
    async def check():
        app, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as browser:
            if failure != 'provider':
                from sqlalchemy.exc import SQLAlchemyError
                from czero_core.renewal import RenewalRejected
                def unavailable(*args, **kwargs):
                    raise SQLAlchemyError() if failure == 'database' else RenewalRejected()
                monkeypatch.setattr(app.state.auth.sessions, 'create', unavailable)
            for _ in range(13):
                started = await browser.get('/auth/login')
                assert started.status_code == 302
                state = parse_qs(urlsplit(started.headers['location']).query)['state'][0]
                params = {'error': 'access_denied'} if failure == 'provider' else {'code':'unit-only-code'}
                denied = await browser.get('/auth/callback', params={'state': state, **params})
                assert denied.status_code == {'provider':400,'database':503,'authority':401}[failure]
                assert not any('c0-attempt-' in cookie for cookie in browser.cookies)
            assert (await browser.get('/auth/login')).status_code == 302
    asyncio.run(check())
