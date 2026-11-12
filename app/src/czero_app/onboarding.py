# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Human sign-in and explicit approval around the bounded Core handoff."""
from functools import partial
import re

from anyio import to_thread
from fastapi import Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from czero_core.client_onboarding import OnboardingRejected


def pending(request):
    match = re.fullmatch(r'([A-Za-z0-9_-]{43})\.([A-Za-z0-9_-]{43})',
                         request.cookies.get('c0_onboarding', ''))
    if match is None:
        raise OnboardingRejected()
    return match.groups()


class ConnectionScopes(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    scopes: list[str] = Field(min_length=1, max_length=3)


def install_onboarding_routes(app, service, cimd, auth, read_context, write_context,
                              browser_session):
    @app.get('/oauth/connect', include_in_schema=False)
    def page(request: Request):
        try:
            service.available(*pending(request))
        except OnboardingRejected:
            pass  # The page explains expiry without leaking the request.
        else:
            if not request.cookies.get('c0_session'):
                return RedirectResponse('/auth/login', status_code=302,
                    headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
        response = app.state.website.render()
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @app.post('/oauth/connect/request', include_in_schema=False)
    async def submit(request: Request, context=Depends(write_context)):
        session = await to_thread.run_sync(partial(browser_session, request))
        tokens = pending(request)
        view = await to_thread.run_sync(partial(service.submit, session, *tokens))
        if view['self_service_allowed'] and 'c0:read' in view['scopes']:
            # Fetch only after first-party sign-in and CSRF-bound account admission.
            fetched = await cimd.fetcher.fetch(view['metadata_url'], cache=True)
            session = await to_thread.run_sync(partial(browser_session, request))
            await to_thread.run_sync(partial(service.register_reader, session, *tokens,
                fetched.metadata, cache_seconds=fetched.remaining))
            view = await to_thread.run_sync(partial(service.view, session, *tokens))
        if view['approved']:
            scopes = set(view['scopes']) & set(view['allowed_scopes'])
            if scopes:
                verification = await cimd.verification(view['metadata_url'])
                session = await to_thread.run_sync(partial(browser_session, request))
                consent = await to_thread.run_sync(partial(service.complete, session, *tokens,
                    scopes=scopes, verification=verification))
                response = JSONResponse({'next': '/oauth/consent'}, headers={'Cache-Control': 'no-store'})
                response.set_cookie('c0_consent', consent.request + '.' + consent.binding,
                    max_age=300, secure=True, httponly=True, samesite='lax', path='/')
                response.delete_cookie('c0_onboarding', path='/', secure=True, httponly=True, samesite='lax')
                return response
        return {**view, 'profile': auth.access.profile(session.actor), 'csrf_token': session.csrf_token}

    @app.post('/oauth/connect/continue', include_in_schema=False)
    async def proceed(request: Request, data: ConnectionScopes, context=Depends(write_context)):
        if len(set(data.scopes)) != len(data.scopes):
            raise OnboardingRejected()
        session = await to_thread.run_sync(partial(browser_session, request))
        tokens = pending(request)
        view = await to_thread.run_sync(partial(service.view, session, *tokens))
        verification = await cimd.verification(view['metadata_url'])
        session = await to_thread.run_sync(partial(browser_session, request))
        consent = await to_thread.run_sync(partial(service.complete, session, *tokens,
            scopes=set(data.scopes), verification=verification))
        response = JSONResponse({'next': '/oauth/consent'}, headers={'Cache-Control': 'no-store'})
        response.set_cookie('c0_consent', consent.request + '.' + consent.binding,
            max_age=300, secure=True, httponly=True, samesite='lax', path='/')
        response.delete_cookie('c0_onboarding', path='/', secure=True, httponly=True, samesite='lax')
        return response

    @app.get('/api/v1/oauth/connection-requests')
    def requests(context=Depends(read_context)):
        return {'requests': service.requests(context.actor)}

    @app.exception_handler(OnboardingRejected)
    def rejected(request, error):
        return JSONResponse({'detail': 'connection_request_unavailable'}, status_code=410,
                            headers={'Cache-Control': 'no-store'})
