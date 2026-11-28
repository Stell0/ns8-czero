# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded app adapter around official OAuth handlers and verified NS8 SSO."""
from functools import partial
import hashlib
import hmac
import logging
import re
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from anyio import to_thread
from fastapi import Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.routes import build_metadata
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from pydantic import BaseModel, ConfigDict, Field, AnyHttpUrl
from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import FormData

from czero_core.identity import PermissionDenied
from czero_app.cimd_server import install_cimd_routes
from czero_core.oauth_grants import OAuthGrantService, GrantRejected
from czero_core.oauth_consent import ConsentRejected, OAuthConsentService, eligible_consent_scopes
from czero_core.operations import SCOPES
from czero_core.client_onboarding import ClientOnboardingService, OnboardingRejected
from czero_core.sessions import SessionRejected
from czero_core.renewal import RenewalRejected, RenewalUnavailable
from czero_app.auth_events import mark
from czero_app.oauth_flow import browser_flows, selected, flow_url, login_url, set_flow_cookie
from czero_app.oauth_provider import incoming_flows, OAuthProvider, raw_request, pending_response, request_kind

COOKIE = 'c0_consent'
COOKIE_PATTERN = re.compile(r'([A-Za-z0-9_-]{43})\.((?:s-)?[A-Za-z0-9_-]{43})\Z')
AUTHORIZE_FIELDS = {'client_id','redirect_uri','response_type','code_challenge','code_challenge_method','state','scope','resource','c0_session_only'}
TOKEN_FIELDS = {'client_id','grant_type','code','redirect_uri','code_verifier','refresh_token','scope','resource','client_secret'}
REVOKE_FIELDS = {'client_id','token','token_type_hint','client_secret','resource'}


class ConsentChoice(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    draft_id: str = Field(pattern=r'^[0-9a-f]{64}$')
    approve: bool
    scopes: list[str] | None = Field(default=None, max_length=3)
    persistent: bool = False


class BackgroundChoice(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    draft_id: str = Field(pattern=r'^[0-9a-f]{64}$')
    scopes: list[str] = Field(min_length=1, max_length=3)


def pending_cookie(request):
    tokens = selected(request)
    if tokens is not None:
        if not hasattr(request.app.state.oauth_consent, 'review'):
            raise ConsentRejected()
        return tokens
    if hasattr(request.app.state.oauth_consent, 'review'):
        raise ConsentRejected()
    match = COOKIE_PATTERN.fullmatch(request.cookies.get(COOKIE, ''))
    if match is None:
        raise ConsentRejected()
    return match.groups()


def consent_draft_id(pending, session):
    return hashlib.sha256(f'{pending[0]}:{session.actor.user_id}'.encode('ascii')).hexdigest()


def reviewed_pending(request, session, draft_id):
    pending = pending_cookie(request)
    if not hmac.compare_digest(draft_id, consent_draft_id(pending, session)):
        request.state.c0_auth_reason = 'draft_mismatch'
        raise ConsentRejected()
    return pending


class PublicRevocationRequest:
    """SDK 2.3.0 requires nullable client_secret even for public revocation."""
    def __init__(self, request, form):
        self.request, self.data = request, FormData({**dict(form), 'client_secret': None})

    def __getattr__(self, name):
        return getattr(self.request, name)

    async def form(self):
        return self.data


def install_oauth_server(app, auth, read_context, write_context):
    previous_validation = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def private_oauth_validation(request, error):
        if request.url.path in ('/oauth/consent', '/oauth/consent/background',
                                '/oauth/connect/approve', '/oauth/connect/continue'):
            return JSONResponse({'detail':'invalid_consent'}, status_code=422, headers={'Cache-Control':'no-store'})
        if request.url.path.startswith('/api/v1/oauth/connections/'):
            return JSONResponse({'detail':'invalid_connection'}, status_code=422, headers={'Cache-Control':'no-store'})
        return await previous_validation(request, error)

    origin = auth.oidc.config.public_origin.rstrip('/')
    grants = OAuthGrantService(auth.access, auth.sessions.client_id, origin + '/mcp', authority=auth.sessions.authority)
    # Older released Core retains exact matching until independent adoption.
    callback_matches = getattr(grants.clients, 'redirect_uri_matches', lambda callback, registered: callback in registered)
    consent = OAuthConsentService(grants)
    scoped_flows = hasattr(consent, 'review')
    onboarding = ClientOnboardingService(grants)
    app.state.client_onboarding = onboarding
    cimd = install_cimd_routes(app, grants.cimd, read_context, write_context)
    provider = OAuthProvider(grants, consent, origin, cimd=cimd)
    app.state.delegated_grants, app.state.oauth_consent = grants, consent
    authenticator = ClientAuthenticator(provider)
    handlers = {'authorize': AuthorizationHandler(provider), 'token': TokenHandler(provider, authenticator),
                'revoke': RevocationHandler(provider, authenticator)}

    async def bounded(request, kind):
        if request.headers.get('host') != urlsplit(origin).netloc:
            return JSONResponse({'error':'invalid_request'}, status_code=400, headers={'Cache-Control':'no-store'})
        if request.method == 'GET':
            if len(request.scope.get('query_string', b'')) > 16384:
                return JSONResponse({'error':'invalid_request'}, status_code=400)
            form = request.query_params
        else:
            if request.headers.get('content-type','').split(';')[0] != 'application/x-www-form-urlencoded':
                return JSONResponse({'error':'invalid_request'}, status_code=400)
            if len(await request.body()) > 16384:
                return JSONResponse({'error':'invalid_request'}, status_code=413)
            form = await request.form()
        fields = {'authorize':AUTHORIZE_FIELDS,'token':TOKEN_FIELDS,'revoke':REVOKE_FIELDS}[kind]
        if ((kind != 'authorize' and set(form) - fields)
                or any(len(form.getlist(key)) != 1 or not isinstance(form[key], str) for key in form)
                or form.get('client_secret') or request.headers.get('authorization')):
            return JSONResponse({'error':'invalid_request'}, status_code=400)
        # RFC 6749 section 3.1: ignore unknown authorization parameters only
        # after checking every raw name for duplicates. Core receives known fields.
        raw = {key: form[key] for key in form if key in fields}
        if kind == 'token' and raw.get('grant_type') in ('authorization_code', 'refresh_token'):
            request.state.c0_grant_kind = raw['grant_type']
        if raw.get('resource') != grants.resource:
            return JSONResponse({'error':'invalid_target'}, status_code=400)
        flows = None
        if kind == 'authorize':
            if scoped_flows:
                try:
                    flows = browser_flows(request)
                except ConsentRejected:
                    return JSONResponse({'error':'invalid_request'}, status_code=400)
            if ('c0_session_only' in raw and (raw['c0_session_only'] != 'true'
                    or not getattr(consent, 'supports_session_only', False))):
                return JSONResponse({'error':'invalid_request'}, status_code=400)
            saved = await to_thread.run_sync(partial(grants.clients._lookup, raw.get('client_id')))
            if saved is not None and not callback_matches(raw.get('redirect_uri'), saved['redirect_uris']):
                return JSONResponse({'error': 'invalid_request'}, status_code=400)
            if (raw.get('client_id', '').startswith('https://')
                    and (saved is None or not set(raw.get('scope', 'c0:read').split()) <= set(saved['allowed_scopes']))
                    and await to_thread.run_sync(grants.cimd.enabled)):
                if 'c0_session_only' in raw:
                    return JSONResponse({'error':'invalid_request'}, status_code=400)
                try:
                    pending = await to_thread.run_sync(partial(onboarding.begin, raw,
                        **({'browser_flows':tuple(flows.items())} if scoped_flows else {})))
                except OnboardingRejected:
                    return JSONResponse({'error': 'invalid_request'}, status_code=400)
                response = RedirectResponse(flow_url('/oauth/' + pending.stage, pending.request) if scoped_flows else '/oauth/connect', status_code=302,
                    headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
                if scoped_flows:
                    set_flow_cookie(response, pending)
                    return response
                response.set_cookie('c0_onboarding', pending.request + '.' + pending.binding,
                    max_age=300, secure=True, httponly=True, samesite='lax', path='/')
                response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='lax')
                return response
            if saved is None or not callback_matches(raw.get('redirect_uri'), saved['redirect_uris']):
                return JSONResponse({'error':'invalid_request'}, status_code=400)
        flows_token = incoming_flows.set(tuple(flows.items()) if flows is not None else None)
        request_token, response_token = raw_request.set(raw), pending_response.set(None)
        kind_token = request_kind.set(kind)
        try:
            incoming = PublicRevocationRequest(request, form) if kind == 'revoke' else request
            response = await handlers[kind].handle(incoming)
            pending = pending_response.get()
            if kind == 'authorize' and pending is not None and response.status_code == 302:
                if scoped_flows:
                    response.headers['location'] = origin + flow_url('/oauth/' + pending.stage, pending.request)
                    response.headers['Cache-Control'] = 'no-store'
                    set_flow_cookie(response, pending)
                    return response
                response.set_cookie(COOKIE, pending.request + '.' + pending.binding, max_age=300,
                    secure=True, httponly=True, samesite='lax', path='/')
                response.delete_cookie('c0_onboarding', path='/', secure=True, httponly=True, samesite='lax')
            response.headers['Cache-Control'] = 'no-store'
            return response
        finally:
            incoming_flows.reset(flows_token)
            request_kind.reset(kind_token)
            raw_request.reset(request_token)
            pending_response.reset(response_token)

    def handler(kind):
        async def endpoint(request):
            try:
                return await bounded(request, kind)
            except RenewalUnavailable as error:
                if kind == 'token' and getattr(error, 'before_refresh_rotation', False):
                    request.state.c0_auth_reason = 'provider_unavailable'
                    return JSONResponse({'error':'temporarily_unavailable', 'c0_rotation':'not_started'},
                                        status_code=503, headers={'Cache-Control':'no-store'})
                return JSONResponse({'error':'service_unavailable'}, status_code=503)
            except SQLAlchemyError:
                return JSONResponse({'error':'service_unavailable'}, status_code=503)
            except Exception as error:
                logging.getLogger('czero.oauth').error('OAuth handler failed (%s)', type(error).__name__)
                return JSONResponse({'error':'service_unavailable'}, status_code=503)
        return endpoint
    app.add_route('/oauth/authorize', handler('authorize'), methods=['GET','POST'])
    app.add_route('/oauth/token', handler('token'), methods=['POST'])
    app.add_route('/oauth/revoke', handler('revoke'), methods=['POST'])
    metadata = build_metadata(AnyHttpUrl(origin + '/oauth'), None,
        ClientRegistrationOptions(enabled=False, valid_scopes=sorted(SCOPES)), RevocationOptions(enabled=True))
    metadata.token_endpoint_auth_methods_supported = ['none']

    @app.get('/.well-known/oauth-authorization-server/oauth', include_in_schema=False)
    def authorization_metadata():
        metadata.client_id_metadata_document_supported = grants.cimd.enabled()
        return JSONResponse(metadata.model_dump(mode='json', by_alias=True, exclude_none=True),
            headers={'Cache-Control':'no-store'})

    def verified_oauth_flow(request, stage, flow, *, account_id=None, connection=None):
        if not scoped_flows or stage not in ('connect', 'consent'):
            return False
        try:
            tokens = selected(request, selector=flow)
            service = onboarding if stage == 'connect' else consent
            if connection is None:
                service.available(*tokens, account_id=account_id)
            else:
                service.bind_login_account(connection, *tokens, account_id)
            return True
        except (ConsentRejected, OnboardingRejected):
            return False

    app.state.verified_oauth_flow = verified_oauth_flow

    def browser_session(request):
        if request.headers.get('authorization') is not None:
            raise PermissionDenied()
        cookie = request.cookies.get('c0_session')
        session = auth.sessions.get(cookie)
        if session.remembered:
            request.state.remembered_cookie = cookie
        return session

    def background_ready(session):
        # The NS8 setting applies to new connections. Reuse an offline sign-in
        # only when its saved policy matches the current setting; existing
        # grants keep their own native authority and original policy.
        if not grants.background_enabled or session.native_authority_id is None:
            return False
        authority = auth.sessions.authority
        with auth.access.database.engine.connect() as connection:
            native = authority.peek(connection, session.native_authority_id, account_id=session.actor.user_id)
        return (native['authority_kind'] == 'background'
            and (native.get('connection_idle_seconds') or native['idle_seconds']) == authority.connection_policy.idle_seconds)

    @app.get('/api/v1/oauth/connections')
    def account_connections(request: Request, context=Depends(read_context)):
        session = browser_session(request)
        return {'connections': grants.connections(session.actor), 'csrf_token': session.csrf_token}

    @app.delete('/api/v1/oauth/connections/{identifier}', status_code=204)
    def disconnect_connection(identifier: UUID, request: Request, context=Depends(write_context)):
        session = browser_session(request)
        try:
            grants.disconnect(session.actor, identifier)
        except GrantRejected:
            raise HTTPException(404, 'connection_not_found') from None
        return Response(status_code=204)

    @app.get('/oauth/consent', include_in_schema=False)
    def consent_page(request: Request):
        tokens = pending_cookie(request)
        flow = request.query_params.get('flow')
        if flow and scoped_flows:
            consent.available(*tokens)
        else:
            consent.view(*tokens)
        destination = login_url('consent', flow)
        if not request.cookies.get('c0_session'):
            return RedirectResponse(destination, status_code=302,
                headers={'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})
        try:
            browser_session(request)
        except (SessionRejected, RenewalRejected):
            # The browser cookie can outlive its native identity. Preserve the
            # validated pending request, but require a fresh ordinary sign-in.
            response = RedirectResponse(destination, status_code=302,
                headers={'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})
            response.delete_cookie('c0_session', path='/', secure=True,
                httponly=True, samesite='lax')
            return response
        response = app.state.website.render()
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @app.get('/oauth/consent/request', include_in_schema=False)
    def consent_request(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        session = browser_session(request)
        tokens = pending_cookie(request)
        view = consent.review(session, *tokens) if scoped_flows and 'flow' in request.query_params else consent.view(*tokens)
        if 'decision' in view:
            return view
        draft_id = consent_draft_id(tokens, session)
        eligible = eligible_consent_scopes(session.actor, view['scopes'])
        authority = auth.sessions.authority
        client = grants.clients._lookup(view['client_id'])
        supported = (not view.pop('session_only', False) and grants.background_enabled and client is not None
            and 'refresh_token' in client.get('grant_types', ['authorization_code', 'refresh_token']))
        seconds = authority.connection_policy.idle_seconds if supported else None
        ready = bool(supported and background_ready(session))
        return {**view, 'eligible_scopes':eligible, 'csrf_token':session.csrf_token, 'draft_id':draft_id,
                'background_supported': bool(supported), 'background_ready': ready,
                'connection_idle_seconds': seconds,
                'profile':auth.access.profile(session.actor)}

    @app.post('/oauth/consent/background', include_in_schema=False)
    async def consent_background(request: Request, choice: BackgroundChoice, context=Depends(write_context)):
        session = await to_thread.run_sync(partial(browser_session, request))
        pending_request = reviewed_pending(request, session, choice.draft_id)
        await to_thread.run_sync(partial(consent.prepare_background, session, *pending_request,
            scopes=set(choice.scopes)))
        flow = request.query_params.get('flow')
        extra = {'return_target':flow_url('/oauth/consent', flow),
                 'prior_cookie':request.cookies.get('c0_session')} if flow else {}
        pending = await to_thread.run_sync(partial(auth.sessions.begin_login, background=True, session=session, **extra))
        response = JSONResponse({'next': login_url('background', flow)},
            headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
        response.set_cookie('__Host-c0-background-' + flow if flow else 'c0_background_login', pending.state + '.' + pending.browser_binding,
            max_age=300, secure=True, httponly=True, samesite='lax', path='/')
        return response

    @app.post('/oauth/consent', include_in_schema=False)
    async def consent_complete(request: Request, choice: ConsentChoice, context=Depends(write_context)):
        session = await to_thread.run_sync(partial(browser_session, request))
        pending = reviewed_pending(request, session, choice.draft_id)
        scoped = scoped_flows and 'flow' in request.query_params
        view = await to_thread.run_sync(partial(consent.review, session, *pending)) if scoped else None
        if view and 'decision' in view:
            request.state.c0_auth_reason = 'completed'
            return JSONResponse(view, headers={'Cache-Control':'no-store'})
        verification = None
        if choice.approve:
            view = view or await to_thread.run_sync(partial(consent.view, *pending))
            verification = await cimd.verification(view['client_id'])
        if choice.approve and choice.persistent and not await to_thread.run_sync(partial(background_ready, session)):
            raise ConsentRejected()
        try:
            result = await to_thread.run_sync(partial(consent.complete, session, *pending, approve=choice.approve,
                scopes=set(choice.scopes) if choice.scopes is not None else None, verification=verification,
                persistent=choice.persistent))
        except GrantRejected as error:
            if getattr(error, 'reason', '') == 'account_grant_limit':
                request.state.c0_auth_reason = 'grant_limit'
                raise HTTPException(409, 'account_grant_limit') from None
            raise ConsentRejected() from None
        request.state.c0_auth_reason = 'completed'
        if hasattr(result, 'decision'):
            return JSONResponse({'decision':result.decision}, headers={'Cache-Control':'no-store'})
        mark('completed', issued_code=result.code)
        values = {'code':result.code} if result.code else {'error':'access_denied'}
        if result.state is not None:
            values['state'] = result.state
        response = JSONResponse({'redirect_uri':result.callback + '?' + urlencode(values)},
            headers={'Cache-Control':'no-store'})
        if not scoped:
            response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='lax')
        return response

    @app.exception_handler(ConsentRejected)
    def rejected(request, error):
        if not getattr(request.state, 'c0_auth_reason', None):
            request.state.c0_auth_reason = getattr(error, 'reason', 'draft_unavailable')
        if (request.method == 'GET' and request.url.path == '/oauth/consent'
                and 'text/html' in request.headers.get('accept', '')):
            response = app.state.website.render({'error':'flow_unavailable'}, status_code=400)
            response.headers['Referrer-Policy'] = 'no-referrer'
            return response
        return JSONResponse({'detail':'invalid_consent'}, status_code=400, headers={'Cache-Control':'no-store'})
    from czero_app.onboarding import install_onboarding_routes
    from czero_app.workspace_access import install_workspace_routes
    install_workspace_routes(app, grants, read_context, write_context, cimd)

    install_onboarding_routes(app, onboarding, cimd, auth, read_context, write_context,
                              browser_session)
    return grants, consent
