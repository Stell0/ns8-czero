# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""FastAPI transport for shared Core authentication and membership services."""
from dataclasses import dataclass, field
from html import escape
import logging
import os
import re
from uuid import UUID
from urllib.parse import parse_qsl

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import APIKeyCookie, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import Actor, PermissionDenied, Role, TokenRejected
from czero_core.oidc import OidcClient, OidcConfig, OidcUnavailable, OfflineUnavailable
from czero_core.sessions import LoginStateRejected, SessionRejected, SessionService, REMEMBER_SECONDS
from czero_core.oauth_grants import GrantRejected
from czero_core.renewal import ConnectionPolicy, NativeAuthorityService, RenewalRejected, RenewalUnavailable, SessionPolicy


class SafeAccessLog(logging.Filter):
    """OAuth codes/state and request query data never enter access logs."""
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            values = list(record.args)
            values[2] = str(values[2]).split("?", 1)[0]
            record.args = tuple(values)
        return True


@dataclass
class AppAuth:
    access: AccessService
    sessions: SessionService
    oidc: OidcClient

    @classmethod
    def from_env(cls, database: Database, base_path: str):
        names = ("CZERO_OIDC_ISSUER", "CZERO_OIDC_CLIENT_ID", "CZERO_OIDC_CLIENT_SECRET",
                 "CZERO_AUTH_PUBLIC_ORIGIN", "CZERO_OWNER_LDAP_UUID")
        values = [os.getenv(name, "") for name in names]
        if not all(values):
            return None
        try:
            issuer, client, secret, origin, owner = values
            config = OidcConfig(issuer, client, secret, origin, base_path)
            access = AccessService(database, issuer, UUID(owner), admit_readers=True)
            policy = SessionPolicy(int(os.getenv('CZERO_SESSION_ABSOLUTE_SECONDS', '28800')),
                                   int(os.getenv('CZERO_SESSION_IDLE_SECONDS', '3600')))
            oidc = OidcClient(config)
            try:
                connections = ConnectionPolicy(int(os.getenv('CZERO_CONNECTION_IDLE_SECONDS', '2592000')))
                authority = NativeAuthorityService(access, client, secret, oidc.check_renewal,
                    policy=policy, connection_policy=connections)
                return cls(access, SessionService(access, client, authority=authority), oidc)
            except (TypeError, ValueError):
                oidc.close()
                raise
        except (TypeError, ValueError):
            logging.getLogger("czero.auth").error("Authentication configuration is invalid")
            return None


@dataclass(frozen=True)
class RequestAccess:
    actor: Actor
    csrf_token: str | None = field(default=None, repr=False)
    # None is reserved for verified first-party tokens/browser sessions.
    # Delegated clients receive an explicit verified scope set.
    scopes: frozenset[str] | None = None
    remembered: bool | None = None


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role | None
    expected_revision: int | None = Field(default=None, strict=True, ge=1, le=9223372036854775806)


def install_auth_routes(app: FastAPI, auth: AppAuth | None, base_path: str) -> tuple:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, SafeAccessLog) for item in logger.filters):
        logger.addFilter(SafeAccessLog())
    cookie_path = base_path + "/"
    bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")
    cookie_scheme = APIKeyCookie(name="c0_session", auto_error=False, scheme_name="SessionCookie")

    async def error_response(request, error):
        if isinstance(error, PermissionDenied):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        if isinstance(error, LoginStateRejected):
            return JSONResponse({"detail": "invalid_login_state"}, status_code=400)
        if isinstance(error, (TokenRejected, SessionRejected, RenewalRejected)):
            return JSONResponse({"detail": str(error)}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        if isinstance(error, (OidcUnavailable, RenewalUnavailable)):
            return JSONResponse({"detail": "authentication_unavailable"}, status_code=503)
        logging.getLogger("czero.auth").error("Authentication service failed (%s)", type(error).__name__)
        return JSONResponse({"detail": "service_unavailable"}, status_code=503)

    for error_class in (PermissionDenied, LoginStateRejected, TokenRejected, SessionRejected, RenewalRejected, RenewalUnavailable, OidcUnavailable, SQLAlchemyError):
        app.add_exception_handler(error_class, error_response)

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        response = await call_next(request)
        cookie = getattr(request.state, 'remembered_cookie', None)
        if cookie and response.status_code < 400 and request.url.path != '/auth/logout':
            try:
                # Final current-role/session check: late replies cannot revive logout.
                from anyio import to_thread
                context = await to_thread.run_sync(auth.sessions.renew_browser, cookie)
                if context.remembered:
                    response.set_cookie('c0_session', cookie, max_age=REMEMBER_SECONDS,
                        secure=True, httponly=True, samesite='lax', path=cookie_path)
            except (SessionRejected, RenewalRejected, PermissionDenied):
                pass
        if "/api/v1/" in request.url.path or "/auth/" in request.url.path:
            response.headers["Cache-Control"] = "no-store"
        return response

    def configured() -> AppAuth:
        if auth is None:
            raise HTTPException(503, "authentication_not_configured")
        return auth

    def authenticate(request: Request, *, write: bool = False) -> RequestAccess:
        authorization = request.headers.get("authorization")
        if authorization is not None:
            if not authorization.startswith("Bearer ") or not authorization[7:]:
                raise TokenRejected()
            active = configured()
            grants = getattr(app.state, 'delegated_grants', None)
            if grants is not None and re.fullmatch(r'[A-Za-z0-9_-]{43}', authorization[7:]):
                try:
                    delegated = grants.verify(authorization[7:], resource=grants.resource)
                except GrantRejected:
                    raise TokenRejected() from None
                return RequestAccess(delegated.actor, scopes=delegated.scopes)
            identity = active.oidc.verify_access_token(authorization[7:])
            return RequestAccess(active.access.resolve(identity))
        cookie = request.cookies.get("c0_session")
        if not cookie:
            raise HTTPException(401, "not_authenticated", headers={"WWW-Authenticate": "Bearer"})
        active = configured()
        context = active.sessions.get(cookie)
        if write:
            if request.headers.get("origin") != active.oidc.config.public_origin.rstrip("/"):
                raise PermissionDenied()
            active.sessions.check_csrf(context, request.headers.get("x-c0-csrf"))
        if context.remembered:
            request.state.remembered_cookie = cookie
        return RequestAccess(context.actor, context.csrf_token, remembered=context.remembered)

    def read_context(request: Request, bearer=Security(bearer_scheme), cookie=Security(cookie_scheme)):
        return authenticate(request)

    def write_context(request: Request, bearer=Security(bearer_scheme), cookie=Security(cookie_scheme)):
        return authenticate(request, write=True)

    @app.get("/api/v1/auth/status")
    def auth_status():
        return {"configured": auth is not None}

    @app.get("/api/v1/me")
    def current_user(space_id: UUID | None = None, context: RequestAccess = Depends(read_context)):
        if context.scopes is not None and 'c0:read' not in context.scopes:
            raise PermissionDenied()
        result = configured().access.profile(context.actor)
        if space_id is not None:
            from czero_core.spaces import SpaceService
            active = configured().access
            with active.database.engine.connect() as connection:
                current = SpaceService(active.database, active).authorize(connection, context.actor, space_id=space_id)
            result['application_role'] = result['role']
            result['role'] = current.role.value
            result['space_id'] = str(current.space_id)
        if context.csrf_token is not None:
            result["csrf_token"] = context.csrf_token
            result['browser_session'] = {'remembered': context.remembered}
            if context.remembered:
                result['browser_session']['idle_seconds'] = REMEMBER_SECONDS
        return result

    @app.get("/api/v1/access/accounts")
    def accounts(limit: int = 100, context: RequestAccess = Depends(read_context)):
        if context.scopes is not None and 'c0:admin' not in context.scopes:
            raise PermissionDenied()
        try:
            return {"accounts": configured().access.list_accounts(context.actor, limit=limit)}
        except PermissionDenied:
            raise
        except ValueError:
            raise HTTPException(422, "invalid_limit") from None

    @app.put("/api/v1/access/accounts/{account_id}", status_code=204)
    def change_role(account_id: UUID, data: RoleUpdate, context: RequestAccess = Depends(write_context)):
        if context.scopes is not None and 'c0:admin' not in context.scopes:
            raise PermissionDenied()
        try:
            configured().access.set_role(context.actor, account_id, data.role, expected_revision=data.expected_revision)
        except PermissionDenied:
            raise
        except ValueError as error:
            from czero_core.access import AccessConflict
            if isinstance(error, AccessConflict):
                raise HTTPException(409, "access_changed") from None
            raise HTTPException(404, "account_not_found") from None
        return Response(status_code=204)

    def remembered_unavailable(request):
        configured().sessions.destroy(request.cookies.get('c0_session'))
        response = HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Remembered sign-in unavailable</title><main><h1>Remembered sign-in unavailable</h1>'
            '<p>Your sign-in provider could not authorize remembered access. Try ordinary sign-in with the option unchecked.</p>'
            f'<a href="{escape(base_path, quote=True)}/auth/sign-in">Return to sign-in</a></main></html>',
            status_code=403, headers={'Referrer-Policy':'no-referrer'})
        for name in ('c0_login', 'c0_session', 'c0_login_return'):
            response.delete_cookie(name, path=cookie_path, secure=True, httponly=True, samesite='lax')
        return response

    def start_login(request, pending):
        active = configured()
        switch = request.query_params.get('switch_account') == 'true'
        destination = active.oidc.authorization_url(pending, reauthenticate=True) if switch or pending.background else active.oidc.authorization_url(pending)
        response = RedirectResponse(destination, status_code=302, headers={'Referrer-Policy':'no-referrer'})
        response.set_cookie('c0_login', pending.browser_binding, max_age=300,
            secure=True, httponly=True, samesite='lax', path=cookie_path)
        return response

    @app.get('/auth/sign-in', include_in_schema=False)
    def sign_in(request: Request):
        active = configured()
        intent, browser = active.sessions.begin_sign_in()
        action = escape(base_path+'/auth/sign-in', quote=True)
        target = request.query_params.get('return_to', '')
        target = target if target in ('agents', 'admin') else ''
        response = HTMLResponse(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Sign in to C0</title>'
            f'<link rel="stylesheet" href="{escape(base_path, quote=True)}/app.css"></head>'
            '<body><main><h1>Sign in to C0</h1>'
            f'<form id="website-sign-in" method="post" action="{action}">'
            f'<input type="hidden" name="intent" value="{intent}">'
            f'<input type="hidden" name="return_to" value="{target}">'
            '<label><input type="checkbox" name="remember" value="yes"> Remember this device</label>'
            '<p>Stay signed in until you have not used this website for seven days. '
            'Use this only on a device you trust. Otherwise, sign-in uses the normal session limits.</p>'
            '<p>AI assistant connections have their own permission and sign-in choices.</p>'
            '<button type="submit">Continue with NethServer</button></form></main></body></html>',
            # A no-referrer navigation form sends Origin:null in Chromium.
            # Send only the origin so the same-origin POST remains verifiable.
            headers={'Referrer-Policy': 'strict-origin', 'Content-Security-Policy': "default-src 'none'; style-src 'self'; frame-ancestors 'none'"})
        response.set_cookie('c0_signin', browser, max_age=300, secure=True, httponly=True, samesite='lax', path=cookie_path)
        return response

    @app.post('/auth/sign-in', include_in_schema=False)
    async def submit_sign_in(request: Request):
        active = configured()
        if (request.headers.get('origin') != active.oidc.config.public_origin.rstrip('/')
                or request.headers.get('authorization') is not None):
            raise PermissionDenied()
        if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
            raise LoginStateRejected()
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 16384:
                raise LoginStateRejected()
            body.extend(chunk)
        try:
            pairs = parse_qsl(body.decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=4)
        except (ValueError, UnicodeError):
            raise LoginStateRejected() from None
        form = dict(pairs)
        if (len(pairs) != len(form) or set(form)-{'intent', 'remember', 'return_to'}
                or form.get('remember') not in (None, 'yes')):
            raise LoginStateRejected()
        from anyio import to_thread
        await to_thread.run_sync(active.sessions.consume_sign_in, form.get('intent'), request.cookies.get('c0_signin'))
        from functools import partial
        remembered = form.get('remember') == 'yes'
        if remembered and active.sessions.authority is None:
            return await to_thread.run_sync(remembered_unavailable, request)
        pending = await to_thread.run_sync(partial(active.sessions.begin_login, remembered=remembered))
        try:
            response = await to_thread.run_sync(start_login, request, pending)
        except OidcUnavailable:
            if not remembered:
                raise
            return await to_thread.run_sync(remembered_unavailable, request)
        response.delete_cookie('c0_signin', path=cookie_path, secure=True, httponly=True, samesite='lax')
        target = form.get('return_to')
        if target in ('agents', 'admin'):
            response.set_cookie('c0_login_return', target, max_age=300, secure=True, httponly=True, samesite='lax', path=cookie_path)
        else:
            response.delete_cookie('c0_login_return', path=cookie_path, secure=True, httponly=True, samesite='lax')
        return response

    @app.get("/auth/login", include_in_schema=False)
    def login(request: Request):
        active = configured()
        background = request.cookies.get('c0_background_login')
        if background is not None:
            match = re.fullmatch(r'([A-Za-z0-9_-]{43})\.([A-Za-z0-9_-]{43})', background)
            if match is None:
                raise LoginStateRejected()
            pending = active.sessions.pending_login(*match.groups())
        else:
            pending = active.sessions.begin_login()
        response = start_login(request, pending)
        response.delete_cookie('c0_background_login', path=cookie_path,
            secure=True, httponly=True, samesite='lax')
        target = request.query_params.get('return_to')
        if target in ('agents', 'admin'):
            response.set_cookie('c0_login_return', target, max_age=300,
                secure=True, httponly=True, samesite='lax', path=cookie_path)
        else:
            response.delete_cookie('c0_login_return', path=cookie_path,
                secure=True, httponly=True, samesite='lax')
        return response

    @app.get("/auth/callback", include_in_schema=False)
    def callback(request: Request):
        active = configured()
        login = active.sessions.consume_login(request.query_params.get("state"), request.cookies.get("c0_login"))
        renewal = None
        try:
            if active.sessions.authority is not None:
                identity, renewal = active.oidc.exchange_renewable(request.query_params.get("code"), login)
            else:
                identity = active.oidc.exchange(request.query_params.get("code"), login)
        except (OfflineUnavailable, OidcUnavailable, TokenRejected):
            if not login.remembered:
                raise
            return remembered_unavailable(request)
        try:
            extra = {'background': True, 'expected_account_key': login.expected_account_key} if login.background else {}
            cookie = active.sessions.create(identity, renewal=renewal, remembered=login.remembered, **extra)
        except PermissionDenied:
            active.sessions.destroy(request.cookies.get("c0_session"))
            # Admission failure does not clear the provider's SSO session.
            # Retry must explicitly reauthenticate instead of reusing it.
            retry = escape(base_path + "/auth/login?switch_account=true", quote=True)
            response = HTMLResponse(
                '<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>C0 access denied</title><main><h1>Access denied</h1>'
                '<p>This account does not have access to C0. '
                'Sign in with an authorized account or ask an administrator for access.</p>'
                '<p>If the sign-in provider keeps your current name, use its '
                'restart or switch-account control to choose another account.</p>'
                f'<p><a href="{retry}">Sign in with another account</a></p>'
                '</main></html>', status_code=403,
                headers={"Referrer-Policy": "no-referrer"})
            response.delete_cookie("c0_login", path=cookie_path,
                                   secure=True, httponly=True, samesite="lax")
            response.delete_cookie("c0_session", path=cookie_path,
                                   secure=True, httponly=True, samesite="lax")
            response.delete_cookie('c0_login_return', path=cookie_path,
                secure=True, httponly=True, samesite='lax')
            return response
        active.sessions.replace_browser(request.cookies.get('c0_session'))
        destination = cookie_path
        if request.cookies.get('c0_login_return') in ('agents', 'admin'):
            destination += request.cookies['c0_login_return']
        onboarding = getattr(app.state, 'client_onboarding', None)
        if onboarding is not None and request.cookies.get('c0_onboarding'):
            # The destination is fixed: original OAuth state stays server-side.
            # The handoff page explains expiry and never trusts a redirect URL.
            destination = '/oauth/connect'
        consent = getattr(app.state, 'oauth_consent', None)
        if destination == cookie_path and consent is not None and request.cookies.get('c0_consent'):
            from czero_app.oauth_server import pending_cookie
            from czero_core.oauth_consent import ConsentRejected
            try:
                consent.view(*pending_cookie(request))
                destination = '/oauth/consent'
            except ConsentRejected:
                pass
        response = RedirectResponse(destination, status_code=302)
        response.set_cookie("c0_session", cookie, max_age=REMEMBER_SECONDS if login.remembered else active.sessions.max_session_seconds,
                            secure=True, httponly=True, samesite="lax", path=cookie_path)
        response.delete_cookie("c0_login", path=cookie_path, secure=True, httponly=True, samesite="lax")
        response.delete_cookie('c0_login_return', path=cookie_path,
            secure=True, httponly=True, samesite='lax')
        return response

    @app.post("/auth/logout")
    def logout(request: Request, cookie=Security(cookie_scheme)):
        active = configured()
        if (request.headers.get('authorization') is not None
                or request.headers.get('origin') != active.oidc.config.public_origin.rstrip('/')):
            raise PermissionDenied()
        # Local revocation cannot depend on provider authentication/availability.
        active.sessions.logout(cookie, request.headers.get('x-c0-csrf'))
        try:
            logout_url = active.oidc.logout_url()
            provider_logout = True
        except OidcUnavailable:
            # Local revocation must complete even when provider logout cannot.
            logout_url = active.oidc.config.logout_return_uri
            provider_logout = False
        response = JSONResponse({"logout_url": logout_url, "provider_logout": provider_logout})
        response.delete_cookie("c0_session", path=cookie_path, secure=True, httponly=True, samesite="lax")
        return response

    return read_context, write_context
