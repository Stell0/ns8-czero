# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""First-party browser routes for an Editor's outgoing Google connection."""
import secrets
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from czero_core.identity import PermissionDenied
from czero_app.auth import RequestAccess
from czero_app.automatic_source_errors import AutomaticSourceError
from czero_app.google_drive import GoogleDrive, folder_id_from_link

ROOT = '/api/v1/automatic-sources/google-drive'
CALLBACK = '/auth/google-drive/callback'


class DriveConnect(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    offline: bool


class DriveTarget(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    identifier: UUID | None = Field(default=None, strict=False)
    expected_revision: int | None = Field(default=None, ge=1)


class DrivePreview(DriveTarget):
    folder_url: str | None = Field(default=None, min_length=1, max_length=2048)


class DriveSave(DriveTarget):
    preview_token: str = Field(min_length=43, max_length=43)
    name: str = Field(min_length=1, max_length=256)
    enabled: bool = False
    interval_seconds: int | None = Field(default=None, ge=300, le=2678400)
    idempotency_key: str = Field(min_length=1, max_length=128)


class DriveRun(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


def install(app, auth, service, invoke, read_context, write_context):
    """No operation-catalog registration: delegated clients cannot use this authority."""
    capable = hasattr(service, 'drive_status')
    uri = auth.oidc.config.public_origin.rstrip('/') + app.state.website.base_path + CALLBACK if auth else None
    try:
        app.state.google_drive = GoogleDrive.configured(uri) if capable and uri else None
    except (OSError, ValueError):
        # A bad optional credential must not take public-source collection offline.
        import logging
        logging.getLogger('czero.drive').error('Invalid Google Drive configuration')
        app.state.google_drive = None

    def browser(context):
        if context.actor.session_binding is None or context.csrf_token is None or context.scopes is not None:
            raise PermissionDenied()
        return context.actor

    def provider():
        if app.state.google_drive is None:
            raise AutomaticSourceError('drive_unavailable', 503)
        return app.state.google_drive

    @app.get(ROOT + '/connection')
    def status(space_id: UUID, context: RequestAccess = Depends(read_context)):
        actor = browser(context)
        if capable:
            state = invoke(space_id, 'drive_status', actor)
        else:
            state = {'connected': False, 'offline': False, 'reconnect_required': False}
        return {'available': app.state.google_drive is not None, **state}

    @app.post(ROOT + '/connect')
    def connect(space_id: UUID, data: DriveConnect, context: RequestAccess = Depends(write_context)):
        actor = browser(context)
        google = provider()
        verifier = secrets.token_urlsafe(64)
        state = invoke(space_id, 'begin_drive_oauth', actor, session_key=context.csrf_token,
                       verifier=verifier, offline=data.offline)
        return {'url': google.authorization_url(state, verifier, uri, data.offline)}

    @app.get(CALLBACK, include_in_schema=False)
    def callback(request: Request, context: RequestAccess = Depends(read_context)):
        actor = browser(context)
        google = provider()
        params = request.query_params
        if (len(request.scope.get('query_string', b'')) > 8192 or len(params.multi_items()) != len(params)
                or request.headers.get('host', '').lower() != urlsplit(uri).netloc.lower()
                or not params.get('state') or len(params['state']) != 43
                or bool(params.get('code')) == bool(params.get('error'))
                or len(params.get('code', '')) > 4096
                or ('iss' in params and params['iss'] != 'https://accounts.google.com')):
            raise HTTPException(400, 'invalid_drive_callback')
        state = params['state']
        attempt = service.take_drive_oauth(actor, session_key=context.csrf_token, state=state)
        outcome = 'cancelled' if params.get('error') == 'access_denied' else 'error'
        if 'code' in params:
            try:
                subject, ciphertext = google.exchange(params['code'], attempt['verifier'], uri, attempt['offline'])
                service.finish_drive_oauth(actor, session_key=context.csrf_token, state=state,
                                          subject=subject, credential=ciphertext, offline=attempt['offline'])
                outcome = 'connected'
            except (ValueError, RuntimeError, PermissionDenied):
                # Never send Google's diagnostic or authorization code back to the browser.
                outcome = 'error'
        query = urlencode({'space_id': str(attempt['space_id']), 'google_drive': outcome,
                           'offline': int(attempt['offline'])})
        return RedirectResponse(app.state.website.base_path + '/automatic-sources?' + query, status_code=303,
                                headers={'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store'})

    @app.delete(ROOT + '/connection', status_code=204)
    def disconnect(space_id: UUID, context: RequestAccess = Depends(write_context)):
        actor = browser(context)
        if not capable:
            raise AutomaticSourceError('drive_unavailable', 503)
        # Local authority is space-scoped. Revoking the whole Google client grant
        # here would also revoke a person's independently connected spaces.
        invoke(space_id, 'disconnect_drive', actor)
        return Response(status_code=204)

    @app.post(ROOT + '/preview')
    def preview(space_id: UUID, data: DrivePreview, context: RequestAccess = Depends(write_context)):
        actor = browser(context)
        google = provider()
        try:
            target = folder_id_from_link(data.folder_url) if data.folder_url is not None else None
        except RuntimeError:
            raise AutomaticSourceError('invalid_drive_folder') from None
        return invoke(space_id, 'preview_drive', actor, folder_id=target, provider=google,
                      identifier=data.identifier, expected_revision=data.expected_revision)

    @app.post(ROOT + '/save')
    def save(space_id: UUID, data: DriveSave, context: RequestAccess = Depends(write_context)):
        actor = browser(context)
        provider()
        return invoke(space_id, 'save_drive', actor, **data.model_dump())

    @app.post(ROOT + '/{identifier}/run')
    def run(space_id: UUID, identifier: UUID, data: DriveRun, context: RequestAccess = Depends(write_context)):
        actor = browser(context)
        provider()
        return invoke(space_id, 'command_drive', actor, identifier=identifier, action='run', **data.model_dump())
