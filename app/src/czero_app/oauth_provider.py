# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Official OAuth provider contracts over Core; no native token passthrough."""
from contextvars import ContextVar
from functools import partial

from anyio import to_thread
from mcp.server.auth.provider import AuthorizationCode, RefreshToken, AccessToken, AuthorizeError, TokenError
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import Field

from czero_core.oauth_grants import GrantRejected
from czero_core.oauth_consent import ConsentRejected
from czero_core.cimd import CimdRejected
from czero_app.cimd_fetch import FetchRejected

raw_request = ContextVar('c0_oauth_raw_request', default=None)
pending_response = ContextVar('c0_oauth_pending_response', default=None)
request_kind = ContextVar('c0_oauth_request_kind', default=None)


class PrivateCode(AuthorizationCode):
    code: str = Field(repr=False)
    code_challenge: str = Field(repr=False)


class PrivateRefresh(RefreshToken):
    token: str = Field(repr=False)


class PrivateAccess(AccessToken):
    token: str = Field(repr=False)


class PrivateTokenResponse(OAuthToken):
    access_token: str = Field(repr=False)
    refresh_token: str | None = Field(default=None, repr=False)


class OAuthProvider:
    def __init__(self, grants, consent, origin, *, cimd=None):
        self.grants, self.consent, self.origin = grants, consent, origin
        self.cimd = cimd

    async def _revoke_requested_token(self, value):
        if request_kind.get() != 'revoke':
            return False
        raw = raw_request.get()
        if not isinstance(raw, dict) or raw.get('token') != value:
            raise TokenError('invalid_request')
        # The SDK has authenticated this client and validated the revocation
        # request before invoking its loaders. Core checks ownership/resource
        # and deletes the family without provider authentication. Returning its
        # now-absent metadata retains the SDK's idempotent successful response.
        try:
            await to_thread.run_sync(partial(self.grants.revoke, value,
                raw['client_id'], resource=raw['resource']))
        except GrantRejected:
            pass
        return True

    async def get_client(self, client_id):
        value = await to_thread.run_sync(partial(self.grants.clients._lookup, client_id))
        if value is None:
            return None
        return OAuthClientInformationFull(client_id=value['client_id'], client_name=value['client_name'],
            redirect_uris=value['redirect_uris'], scope=' '.join(value['allowed_scopes']),
            token_endpoint_auth_method='none', grant_types=value.get('grant_types', ['authorization_code','refresh_token']), response_types=['code'])

    async def register_client(self, client_info):
        raise NotImplementedError('Dynamic registration is disabled')

    async def authorize(self, client, params):
        raw = raw_request.get()
        if raw is None:
            raise AuthorizeError('invalid_request')
        try:
            verification = await self.cimd.verification(client.client_id) if self.cimd is not None else None
            pending = await to_thread.run_sync(partial(self.consent.begin, client.client_id,
                callback=raw['redirect_uri'], scopes=set(params.scopes or ['c0:read']),
                challenge=params.code_challenge, state=params.state, resource=params.resource, verification=verification))
        except (ConsentRejected, CimdRejected, FetchRejected):
            raise AuthorizeError('invalid_request') from None
        pending_response.set(pending)
        return self.origin + '/oauth/consent'

    async def load_authorization_code(self, client, authorization_code):
        try:
            value = await to_thread.run_sync(partial(self.grants._authorization_code, authorization_code, client.client_id))
        except GrantRejected:
            return None
        return PrivateCode(code=value.code, code_challenge=value.challenge, client_id=value.client_id,
            scopes=sorted(value.scopes), expires_at=value.expires_at.timestamp(), redirect_uri=value.callback,
            redirect_uri_provided_explicitly=True, resource=value.resource, subject=str(value.subject))

    @staticmethod
    def _response(pair):
        return PrivateTokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token,
            token_type='Bearer', expires_in=pair.expires_in, scope=' '.join(sorted(pair.scopes)))

    async def exchange_authorization_code(self, client, authorization_code):
        raw = raw_request.get()
        if raw is None:
            raise TokenError('invalid_request')
        try:
            pair = await to_thread.run_sync(partial(self.grants.exchange_code, authorization_code.code,
                client.client_id, callback=raw.get('redirect_uri'), verifier=raw.get('code_verifier'), resource=raw.get('resource')))
        except GrantRejected:
            raise TokenError('invalid_grant') from None
        return self._response(pair)

    async def load_refresh_token(self, client, refresh_token):
        if await self._revoke_requested_token(refresh_token):
            return None
        try:
            value = await to_thread.run_sync(partial(self.grants._refresh_token, refresh_token, client.client_id))
        except GrantRejected:
            return None
        return PrivateRefresh(token=value.token, client_id=value.client_id, scopes=sorted(value.scopes),
            expires_at=int(value.expires_at.timestamp()), resource=value.resource, subject=str(value.subject))

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        raw = raw_request.get()
        if raw is None:
            raise TokenError('invalid_request')
        try:
            pair = await to_thread.run_sync(partial(self.grants.refresh, refresh_token.token,
                client.client_id, scopes=set(scopes), resource=raw.get('resource')))
        except GrantRejected:
            raise TokenError('invalid_grant') from None
        return self._response(pair)

    async def load_access_token(self, token):
        if await self._revoke_requested_token(token):
            return None
        try:
            value = await to_thread.run_sync(partial(self.grants.verify, token, resource=self.grants.resource))
        except GrantRejected:
            return None
        return PrivateAccess(token=token, client_id=value.client_id, scopes=sorted(value.scopes),
            expires_at=int(value.expires_at.timestamp()), resource=value.resource,
            subject=str(value.actor.user_id), claims={'iss': self.origin + '/oauth'})

    async def revoke_token(self, token):
        await to_thread.run_sync(partial(self.grants.revoke, token.token, token.client_id, resource=self.grants.resource))

    async def exchange_identity_assertion(self, client, params):
        raise TokenError('unsupported_grant_type')
