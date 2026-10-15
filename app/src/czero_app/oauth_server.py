# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded app adapter around official OAuth handlers and verified NS8 SSO."""
from functools import partial
import logging
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit

from anyio import to_thread
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.routes import build_metadata
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from pydantic import BaseModel, ConfigDict, Field, AnyHttpUrl
from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import FormData

from czero_core.identity import PermissionDenied, Role
from czero_core.oauth_grants import OAuthGrantService
from czero_core.oauth_consent import ConsentRejected, OAuthConsentService
from czero_core.operations import SCOPES
from czero_app.oauth_provider import OAuthProvider, raw_request, pending_response

COOKIE = 'c0_consent'
COOKIE_PATTERN = re.compile(r'([A-Za-z0-9_-]{43})\.([A-Za-z0-9_-]{43})\Z')
AUTHORIZE_FIELDS = {'client_id','redirect_uri','response_type','code_challenge','code_challenge_method','state','scope','resource'}
TOKEN_FIELDS = {'client_id','grant_type','code','redirect_uri','code_verifier','refresh_token','scope','resource','client_secret'}
REVOKE_FIELDS = {'client_id','token','token_type_hint','client_secret','resource'}


class ConsentChoice(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    approve: bool
    scopes: list[str] | None = Field(default=None, max_length=3)


def pending_cookie(request):
    match = COOKIE_PATTERN.fullmatch(request.cookies.get(COOKIE, ''))
    if match is None:
        raise ConsentRejected()
    return match.groups()


class PublicRevocationRequest:
    """SDK 2.3.0 requires nullable client_secret even for public revocation."""
    def __init__(self, request, form):
        self.request, self.data = request, FormData({**dict(form), 'client_secret': None})

    def __getattr__(self, name):
        return getattr(self.request, name)

    async def form(self):
        return self.data


def install_oauth_server(app, auth, read_context, write_context, static_dir: Path):
    origin = auth.oidc.config.public_origin.rstrip('/')
    grants = OAuthGrantService(auth.access, auth.sessions.client_id, origin + '/mcp')
    consent = OAuthConsentService(grants)
    provider = OAuthProvider(grants, consent, origin)
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
        if raw.get('resource') != grants.resource:
            return JSONResponse({'error':'invalid_target'}, status_code=400)
        if kind == 'authorize':
            saved = await to_thread.run_sync(partial(grants.clients._lookup, raw.get('client_id')))
            if saved is None or raw.get('redirect_uri') not in saved['redirect_uris']:
                return JSONResponse({'error':'invalid_request'}, status_code=400)
        request_token, response_token = raw_request.set(raw), pending_response.set(None)
        try:
            incoming = PublicRevocationRequest(request, form) if kind == 'revoke' else request
            response = await handlers[kind].handle(incoming)
            pending = pending_response.get()
            if kind == 'authorize' and pending is not None and response.status_code == 302:
                response.set_cookie(COOKIE, pending.request + '.' + pending.binding, max_age=300,
                    secure=True, httponly=True, samesite='lax', path='/')
            response.headers['Cache-Control'] = 'no-store'
            return response
        finally:
            raw_request.reset(request_token)
            pending_response.reset(response_token)

    def handler(kind):
        async def endpoint(request):
            try:
                return await bounded(request, kind)
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
        return JSONResponse(metadata.model_dump(mode='json', by_alias=True, exclude_none=True),
            headers={'Cache-Control':'no-store'})

    def browser_session(request):
        if request.headers.get('authorization') is not None:
            raise PermissionDenied()
        return auth.sessions.get(request.cookies.get('c0_session'))

    @app.get('/oauth/consent', include_in_schema=False)
    def consent_page(request: Request):
        consent.view(*pending_cookie(request))
        if not request.cookies.get('c0_session'):
            return RedirectResponse('/auth/login', status_code=302)
        browser_session(request)
        return FileResponse(static_dir / 'consent.html', media_type='text/html', headers={'Cache-Control':'no-store'})

    @app.get('/oauth/consent.js', include_in_schema=False)
    def consent_script():
        return FileResponse(static_dir / 'consent.js', media_type='text/javascript')

    @app.get('/oauth/consent/request', include_in_schema=False)
    def consent_request(request: Request):
        session = browser_session(request)
        view = consent.view(*pending_cookie(request))
        eligible = []
        for scope, role in [('c0:read',Role.READER),('c0:write',Role.EDITOR),('c0:admin',Role.ADMIN)]:
            try:
                session.actor.require(role)
                if scope in view['scopes']:
                    eligible.append(scope)
            except PermissionDenied:
                pass
        return {**view, 'eligible_scopes':eligible, 'csrf_token':session.csrf_token,
                'profile':auth.access.profile(session.actor)}

    @app.post('/oauth/consent', include_in_schema=False)
    def consent_complete(request: Request, choice: ConsentChoice, context=Depends(write_context)):
        session = browser_session(request)
        result = consent.complete(session, *pending_cookie(request), approve=choice.approve,
            scopes=set(choice.scopes) if choice.scopes is not None else None)
        values = {'code':result.code} if result.code else {'error':'access_denied'}
        if result.state is not None:
            values['state'] = result.state
        response = JSONResponse({'redirect_uri':result.callback + '?' + urlencode(values)},
            headers={'Cache-Control':'no-store'})
        response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='lax')
        return response

    @app.exception_handler(ConsentRejected)
    def rejected(request, error):
        return JSONResponse({'detail':'invalid_consent'}, status_code=400, headers={'Cache-Control':'no-store'})
    return grants, consent
