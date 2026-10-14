# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""FastAPI transport for shared Core authentication and membership services."""
from dataclasses import dataclass, field
import logging
import os
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyCookie, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import Actor, PermissionDenied, Role, TokenRejected
from czero_core.oidc import OidcClient, OidcConfig, OidcUnavailable
from czero_core.sessions import LoginStateRejected, SessionRejected, SessionService


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
            access = AccessService(database, issuer, UUID(owner))
            return cls(access, SessionService(access, client), OidcClient(config))
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


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role | None


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
        if isinstance(error, (TokenRejected, SessionRejected)):
            return JSONResponse({"detail": str(error)}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        if isinstance(error, OidcUnavailable):
            return JSONResponse({"detail": "authentication_unavailable"}, status_code=503)
        logging.getLogger("czero.auth").error("Authentication service failed (%s)", type(error).__name__)
        return JSONResponse({"detail": "service_unavailable"}, status_code=503)

    for error_class in (PermissionDenied, LoginStateRejected, TokenRejected, SessionRejected, OidcUnavailable, SQLAlchemyError):
        app.add_exception_handler(error_class, error_response)

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        response = await call_next(request)
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
        return RequestAccess(context.actor, context.csrf_token)

    def read_context(request: Request, bearer=Security(bearer_scheme), cookie=Security(cookie_scheme)):
        return authenticate(request)

    def write_context(request: Request, bearer=Security(bearer_scheme), cookie=Security(cookie_scheme)):
        return authenticate(request, write=True)

    @app.get("/api/v1/auth/status")
    def auth_status():
        return {"configured": auth is not None}

    @app.get("/api/v1/me")
    def current_user(context: RequestAccess = Depends(read_context)):
        result = configured().access.profile(context.actor)
        if context.csrf_token is not None:
            result["csrf_token"] = context.csrf_token
        return result

    @app.get("/api/v1/access/accounts")
    def accounts(limit: int = 100, context: RequestAccess = Depends(read_context)):
        try:
            return {"accounts": configured().access.list_accounts(context.actor, limit=limit)}
        except PermissionDenied:
            raise
        except ValueError:
            raise HTTPException(422, "invalid_limit") from None

    @app.put("/api/v1/access/accounts/{account_id}", status_code=204)
    def change_role(account_id: UUID, data: RoleUpdate, context: RequestAccess = Depends(write_context)):
        try:
            configured().access.set_role(context.actor, account_id, data.role)
        except PermissionDenied:
            raise
        except ValueError:
            raise HTTPException(404, "account_not_found") from None
        return Response(status_code=204)

    @app.get("/auth/login", include_in_schema=False)
    def login():
        active = configured()
        pending = active.sessions.begin_login()
        response = RedirectResponse(active.oidc.authorization_url(pending), status_code=302)
        response.set_cookie("c0_login", pending.browser_binding, max_age=300,
                            secure=True, httponly=True, samesite="lax", path=cookie_path)
        return response

    @app.get("/auth/callback", include_in_schema=False)
    def callback(request: Request):
        active = configured()
        login = active.sessions.consume_login(request.query_params.get("state"), request.cookies.get("c0_login"))
        identity = active.oidc.exchange(request.query_params.get("code"), login)
        cookie = active.sessions.create(identity)
        response = RedirectResponse(cookie_path, status_code=302)
        response.set_cookie("c0_session", cookie, max_age=active.sessions.max_session_seconds,
                            secure=True, httponly=True, samesite="lax", path=cookie_path)
        response.delete_cookie("c0_login", path=cookie_path, secure=True, httponly=True, samesite="lax")
        return response

    @app.post("/auth/logout")
    def logout(request: Request, context: RequestAccess = Depends(write_context)):
        active = configured()
        active.sessions.destroy(request.cookies.get("c0_session"))
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
