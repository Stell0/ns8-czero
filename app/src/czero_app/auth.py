# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""FastAPI transport for shared Core authentication and membership services."""
from dataclasses import dataclass, field
import hashlib
import secrets
import logging
import os
import re
from uuid import UUID
from urllib.parse import parse_qsl, urlencode

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyCookie, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from czero_app.auth_events import flow_reference
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import Actor, PermissionDenied, Role, TokenRejected
from czero_core.oidc import OidcClient, OidcConfig, OidcUnavailable, OfflineUnavailable
from czero_core.sessions import LoginStateRejected, SessionRejected, SessionService, REMEMBER_SECONDS
from czero_core.oauth_grants import GrantRejected
from czero_core.renewal import ConnectionPolicy, NativeAuthorityService, RenewalRejected, RenewalUnavailable, SessionPolicy


LOGIN_PATHS = frozenset(('account', 'agents', 'admin', 'admin/advanced', 'admin/spaces',
                         'admin/work', 'wiki', 'sources', 'search', 'automatic-sources',
                         'tables', 'projects', 'explore'))
UUID_ROUTE = r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
LOGIN_DETAIL = re.compile(
    rf'(?:wiki|sources|evidence)/{UUID_ROUTE}|'
    rf'tables/[A-Za-z0-9_.-]{{1,128}}|explore/[A-Za-z0-9_-]{{1,32}}(?:/{UUID_ROUTE})?'
)
LOGIN_QUERY = frozenset(('space_id', 'revision', 'version', 'revision_id', 'reference',
                         'query', 'kind', 'mode', 'rerank', 'graph_depth', 'offset',
                         'facts_offset', 'related_offset', 'type', 'sort', 'direction',
                         'tag', 'where'))


def login_return(value: str | None) -> str:
    if not value or len(value) > 1600:
        return ''
    path, separator, selector = value.partition('?')
    if path and path not in LOGIN_PATHS and not LOGIN_DETAIL.fullmatch(path):
        return ''
    if path.endswith(('/.', '/..')):
        return ''
    if not separator:
        return path
    try:
        pairs = parse_qsl(selector, keep_blank_values=True, max_num_fields=32, errors='strict')
    except ValueError:
        return ''
    query = urlencode([(name, item) for name, item in pairs if name in LOGIN_QUERY])
    if len(query) > 1600:
        return ''
    return path + ('?' + query if query else '')


_FLOW = re.compile(r'/oauth/(consent|connect)\?flow=([A-Za-z0-9_-]{43})\Z')


def cookie_namespace(cookie_path):
    # Legacy deployments can serve multiple C0 instances on one host.
    return hashlib.sha256(cookie_path.encode('utf-8')).hexdigest()[:32]


def attempt_cookie(state, cookie_path):
    key = hashlib.sha256(state.encode('ascii')).hexdigest()[:32]
    return f'__Host-c0-attempt-{cookie_namespace(cookie_path)}-{key}'


def browser_cookie(request, name):
    """Reject ambiguous cookies (including duplicate Cookie headers)."""
    matches = [value for header in request.headers.getlist('cookie') for part in header.split(';')
               for key, _, value in [part.strip().partition('=')] if key == name]
    if len(matches) > 1:
        raise LoginStateRejected()
    return matches[0] if matches else None


def secret_cookie(request, name):
    value = browser_cookie(request, name)
    return value if value and re.fullmatch(r'[A-Za-z0-9_-]{43}', value) else None


def callback_fields(request, issuer):
    raw = request.scope['query_string']
    try:
        if len(raw) > 16384:
            raise ValueError
        pairs = parse_qsl(raw.decode('ascii'), keep_blank_values=True, strict_parsing=True,
                          errors='strict', max_num_fields=6)
        fields = dict(pairs)
        if (len(fields) != len(pairs) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', fields.get('state', ''))
                or set(fields) - {'state','code','error','error_description','iss','session_state'}
                or ('code' in fields) == ('error' in fields)
                or fields.get('iss', issuer) != issuer or ('error_description' in fields and 'error' not in fields)
                or 'code' in fields and not re.fullmatch(r'[!-~]{1,8192}', fields['code'])
                or 'error' in fields and not re.fullmatch(r'[A-Za-z0-9_]{1,64}', fields['error'])):
            raise ValueError
    except (ValueError, UnicodeError):
        raise LoginStateRejected() from None
    return fields


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
    owner_cookie = '__Host-c0-login-owner-' + cookie_namespace(cookie_path)
    fenced = bool(auth and hasattr(auth.sessions, 'claim_browser_login'))
    attempt_path = '/' if fenced else cookie_path
    bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")
    cookie_scheme = APIKeyCookie(name="c0_session", auto_error=False, scheme_name="SessionCookie")

    async def error_response(request, error):
        if isinstance(error, PermissionDenied):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        if isinstance(error, LoginStateRejected):
            if request.url.path.endswith(('/auth/login','/auth/callback')):
                return login_failure(request)
            return JSONResponse({"detail": "invalid_login_state"}, status_code=400)
        if isinstance(error, (TokenRejected, SessionRejected, RenewalRejected)):
            return JSONResponse({"detail": str(error)}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        if isinstance(error, (OidcUnavailable, RenewalUnavailable)):
            if request.url.path.endswith(('/auth/login','/auth/callback')):
                return login_failure(request, 'provider_unavailable', status=503)
            return JSONResponse({"detail": "authentication_unavailable"}, status_code=503)
        logging.getLogger("czero.auth").error("Authentication service failed (%s)", type(error).__name__)
        if request.url.path.endswith(('/auth/login','/auth/callback')):
            return login_failure(request, 'dependency_unavailable', status=503)
        return JSONResponse({"detail": "service_unavailable"}, status_code=503)

    for error_class in (PermissionDenied, LoginStateRejected, TokenRejected, SessionRejected, RenewalRejected, RenewalUnavailable, OidcUnavailable, SQLAlchemyError):
        app.add_exception_handler(error_class, error_response)

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        response = await call_next(request)
        # Consume only the confirmed attempt, including on a handled storage or provider failure.
        claimed = getattr(request.state, 'claimed_login_cookie', None)
        if claimed:
            response.delete_cookie(claimed, path=attempt_path, secure=True, httponly=True, samesite='lax')
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
            if len(request.headers.getlist('authorization')) != 1:
                raise TokenRejected()
            if authorization[7:].startswith('c0k_') and len(authorization[7:]) != 43:
                keys = getattr(app.state, 'api_keys', None)
                if keys is None:
                    raise TokenRejected()
                current = keys.verify(authorization[7:], resource=keys.resource)
                return RequestAccess(current.actor, scopes=current.scopes)
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
                request.state.c0_auth_reason = 'origin_rejected'
                raise PermissionDenied()
            try:
                active.sessions.check_csrf(context, request.headers.get("x-c0-csrf"))
            except PermissionDenied:
                request.state.c0_auth_reason = 'csrf_rejected'
                raise
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

    def remembered_unavailable(request, attempt=None):
        if attempt is None:
            configured().sessions.destroy(request.cookies.get('c0_session'))
        else:
            try:
                configured().sessions.reject_browser_login(attempt)
            except LoginStateRejected:
                return login_failure(request)
        response = app.state.website.render({'error': 'remembered_unavailable'}, status_code=403)
        response.headers['Referrer-Policy'] = 'no-referrer'
        for name in ('c0_login', 'c0_session', 'c0_login_return'):
            response.delete_cookie(name, path=cookie_path, secure=True, httponly=True, samesite='lax')
        return response

    def login_failure(request, reason='callback_rejected', *, status=400, retry=None):
        request.state.c0_auth_reason = reason
        boot = {'error': reason}
        reference = getattr(request.state, 'c0_request_id', None)
        if reference:
            boot['reference'] = reference
        if retry:
            boot['restart'] = retry
        response = app.state.website.render(boot, status_code=status)
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    def begin_browser_login(request, target='', **kwargs):
        sessions = configured().sessions
        if fenced:
            kwargs.update(return_target=target, prior_cookie=secret_cookie(request, 'c0_session'))
        return sessions.begin_login(**kwargs)

    def start_login(request, pending):
        active = configured()
        switch = request.query_params.get('switch_account') == 'true'
        destination = active.oidc.authorization_url(pending, reauthenticate=True) if switch or pending.background else active.oidc.authorization_url(pending)
        response = RedirectResponse(destination, status_code=302, headers={'Referrer-Policy':'no-referrer'})
        name = 'c0_login'
        if fenced:
            owner = secret_cookie(request, owner_cookie)
            if owner is None:
                owner = secrets.token_urlsafe(32)
            # A new redirect supersedes the prior native login. Consent cookies
            # survive independently so its tab can still reopen its live draft.
            prefix = attempt_cookie(pending.state, cookie_path)[:-32]
            stale = [key for key in request.cookies if key.startswith(prefix)]
            if len(stale) >= 12:
                raise LoginStateRejected()
            active.sessions.bind_browser_login(pending, owner, secret_cookie(request, 'c0_session'))
            name = attempt_cookie(pending.state, cookie_path)
            response.set_cookie(owner_cookie, owner, max_age=300, secure=True, httponly=True, samesite='lax', path='/')
        response.set_cookie(name, pending.browser_binding, max_age=300,
            secure=True, httponly=True, samesite='lax', path=attempt_path)
        return response

    @app.get('/auth/sign-in', include_in_schema=False)
    def sign_in(request: Request):
        active = configured()
        intent, browser = active.sessions.begin_sign_in()
        target = login_return(request.query_params.get('return_to'))
        response = app.state.website.render({'intent': intent, 'return_to': target})
        # The user explicitly started a fresh sign-in. Discard a retired
        # predecessor before its new attempt snapshots the browser binding.
        prior = secret_cookie(request, 'c0_session')
        if fenced and prior and not active.sessions.known_browser(prior):
            response.delete_cookie('c0_session', path=cookie_path, secure=True, httponly=True, samesite='lax')
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
        target = login_return(form.get('return_to'))
        pending = await to_thread.run_sync(partial(begin_browser_login, request, target, remembered=remembered))
        try:
            response = await to_thread.run_sync(start_login, request, pending)
        except OidcUnavailable:
            if not remembered:
                raise
            return await to_thread.run_sync(remembered_unavailable, request)
        response.delete_cookie('c0_signin', path=cookie_path, secure=True, httponly=True, samesite='lax')
        if fenced:
            return response
        if target:
            response.set_cookie('c0_login_return', target, max_age=300, secure=True, httponly=True, samesite='lax', path=cookie_path)
        else:
            response.delete_cookie('c0_login_return', path=cookie_path, secure=True, httponly=True, samesite='lax')
        return response

    @app.get("/auth/login", include_in_schema=False)
    def login(request: Request):
        active = configured()
        target = login_return(request.query_params.get('return_to'))
        flow = request.query_params.get('flow')
        stage = request.query_params.get('stage')
        background_name = 'c0_background_login'
        if flow is not None or stage is not None:
            if (not fenced or len(request.query_params.getlist('flow')) != 1
                    or len(request.query_params.getlist('stage')) != 1
                    or not re.fullmatch(r'[A-Za-z0-9_-]{43}', flow or '')
                    or stage not in ('consent', 'connect', 'background')):
                return login_failure(request)
            review = 'connect' if stage == 'connect' else 'consent'
            verify_flow = getattr(app.state, 'verified_oauth_flow', None)
            if verify_flow is None or not verify_flow(request, review, flow):
                return login_failure(request)
            target = '/oauth/' + review + '?flow=' + flow
            background_name = '__Host-c0-background-' + flow
        background = browser_cookie(request, background_name) if stage in (None, 'background') else None
        if stage == 'background' and not background:
            return login_failure(request)

        if background is not None:
            match = re.fullmatch(r'([A-Za-z0-9_-]{43})\.([A-Za-z0-9_-]{43})', background)
            if match is None:
                raise LoginStateRejected()
            pending = active.sessions.pending_login(*match.groups())
        else:
            pending = begin_browser_login(request, target)
        response = start_login(request, pending)
        response.delete_cookie(background_name, path=attempt_path,
            secure=True, httponly=True, samesite='lax')
        if fenced:
            return response
        if target:
            response.set_cookie('c0_login_return', target, max_age=300,
                secure=True, httponly=True, samesite='lax', path=cookie_path)
        else:
            response.delete_cookie('c0_login_return', path=cookie_path,
                secure=True, httponly=True, samesite='lax')
        return response

    @app.get("/auth/callback", include_in_schema=False)
    def callback(request: Request):
        active = configured()
        fields, proof = {}, None
        try:
            fields = callback_fields(request, active.oidc.config.issuer)
            name = attempt_cookie(fields['state'], cookie_path) if fenced else 'c0_login'
            proof = browser_cookie(request, name)
            if fenced:
                login = active.sessions.claim_browser_login(fields['state'], proof,
                    secret_cookie(request, owner_cookie), secret_cookie(request, 'c0_session'))
            else:
                login = active.sessions.consume_login(fields['state'], proof)
        except LoginStateRejected:
            retry = None
            if fenced and proof:
                target = active.sessions.recovery_target(fields['state'], proof)
                flow = _FLOW.fullmatch(target or '')
                if flow and app.state.verified_oauth_flow(request, *flow.groups()):
                    retry = target
            return login_failure(request, retry=retry)

        if fenced:
            request.state.claimed_login_cookie = name

        target = getattr(login, 'return_target', '')
        flow = _FLOW.fullmatch(target)
        if flow:
            request.state.c0_flow_ref = flow_reference(flow.group(2))
        if flow and not app.state.verified_oauth_flow(request, *flow.groups()):
            return login_failure(request)
        if 'error' in fields:
            reason = 'provider_unavailable' if fields['error'] in ('temporarily_unavailable','server_error') else 'provider_rejected'
            return login_failure(request, reason, status=503 if reason == 'provider_unavailable' else 400,
                                 retry=target if flow else None)
        renewal = None
        try:
            if active.sessions.authority is not None:
                identity, renewal = active.oidc.exchange_renewable(fields['code'], login)
            else:
                identity = active.oidc.exchange(fields['code'], login)
        except (OfflineUnavailable, OidcUnavailable, TokenRejected) as error:
            if login.remembered:
                return remembered_unavailable(request, login if fenced else None)
            reason = 'provider_unavailable' if isinstance(error, OidcUnavailable) else 'provider_rejected'
            return login_failure(request, reason, status=503 if reason == 'provider_unavailable' else 401,
                                 retry=target if flow else None)
        try:
            extra = {'background': True, 'expected_account_key': login.expected_account_key} if login.background else {}
            if fenced:
                if flow:
                    def bind_flow(connection, account_id):
                        return app.state.verified_oauth_flow(request, *flow.groups(),
                            connection=connection, account_id=account_id)
                    extra['bind_flow'] = bind_flow
                extra['attempt'] = login
            cookie = active.sessions.create(identity, renewal=renewal, remembered=login.remembered, **extra)
        except (LoginStateRejected, SessionRejected):
            return login_failure(request)
        except RenewalRejected:
            return login_failure(request, 'native_authority_rejected', status=401)
        except PermissionDenied:
            if fenced:
                try:
                    active.sessions.reject_browser_login(login, denied_identity=identity)
                except LoginStateRejected:
                    return login_failure(request)
            else:
                active.sessions.destroy(request.cookies.get("c0_session"))
            # Admission failure does not clear the provider's SSO session.
            # Retry must explicitly reauthenticate instead of reusing it.
            response = app.state.website.render({'error': 'access_denied'}, status_code=403)
            response.headers['Referrer-Policy'] = 'no-referrer'
            if not fenced:
                response.delete_cookie(name, path=cookie_path, secure=True, httponly=True, samesite="lax")
            response.delete_cookie("c0_session", path=cookie_path,
                                   secure=True, httponly=True, samesite="lax")
            response.delete_cookie('c0_login_return', path=cookie_path,
                secure=True, httponly=True, samesite='lax')
            return response
        if fenced:
            destination = target if flow else cookie_path + login_return(target)
        else:
            active.sessions.replace_browser(request.cookies.get('c0_session'))
            destination = cookie_path
            destination += login_return(request.cookies.get('c0_login_return'))
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
        if not fenced:
            response.delete_cookie(name, path=cookie_path, secure=True, httponly=True, samesite="lax")
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
        extra = {'owner': secret_cookie(request, owner_cookie)} if fenced else {}
        active.sessions.logout(cookie, request.headers.get('x-c0-csrf'), **extra)
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
