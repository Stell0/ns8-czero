# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded NS8 OIDC discovery and authorization-code client operations."""
from dataclasses import dataclass, field, replace
import json
import re
import errno
import socket
import threading
import time
from urllib.parse import urlencode, urlsplit

from authlib.integrations.httpx_client import OAuth2Client
from authlib.oauth2.rfc6749.errors import OAuth2Error
import httpx2

from .identity import TokenRejected, TokenVerifier, VerifiedIdentity
from .sessions import LoginSecrets, PendingLogin
from .renewal import RenewalRejected, RenewalResult, RenewalUnavailable


class OidcUnavailable(ValueError):
    def __init__(self):
        super().__init__("authentication_unavailable")


def _origin(value: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("invalid_oidc_url")
    return parsed.scheme, parsed.netloc.lower()


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    client_id: str
    client_secret: str = field(repr=False)
    public_origin: str
    base_path: str = ""

    def __post_init__(self):
        _origin(self.issuer)
        _origin(self.public_origin)
        if urlsplit(self.issuer).query or urlsplit(self.public_origin).query or urlsplit(self.public_origin).path not in ("", "/"):
            raise ValueError("invalid_oidc_url")
        if not isinstance(self.client_id, str) or not 1 <= len(self.client_id) <= 128:
            raise ValueError("invalid_oidc_client")
        if not isinstance(self.client_secret, str) or not 1 <= len(self.client_secret) <= 1024:
            raise ValueError("invalid_oidc_client")
        if self.base_path and (not self.base_path.startswith("/") or "//" in self.base_path or "?" in self.base_path or "#" in self.base_path):
            raise ValueError("invalid_oidc_base_path")

    @property
    def callback_uri(self) -> str:
        return self.public_origin.rstrip("/") + self.base_path + "/auth/callback"

    @property
    def logout_return_uri(self) -> str:
        return self.public_origin.rstrip("/") + self.base_path + "/"


class OidcClient:
    def __init__(self, config: OidcConfig, *, transport=None):
        self.config = config
        self._transport = transport
        self._http = httpx2.Client(timeout=3.0, follow_redirects=False, transport=transport)
        self._lock = threading.RLock()
        self._metadata = None
        self._metadata_until = 0.0
        self._verifier = None
        self._keys_until = 0.0

    def close(self) -> None:
        self._http.close()

    def health(self) -> dict[str, str]:
        """Check trusted discovery/keys without exposing URLs or driver errors."""
        try:
            self._token_verifier()
            return {"status": "ok"}
        except OidcUnavailable as error:
            reason = "metadata_invalid"
            current = error
            seen = set()
            while current is not None and id(current) not in seen:
                seen.add(id(current))
                # Inspect locally, return only a fixed category. Exception
                # strings can contain private URLs and must never be emitted.
                message = str(current).lower()
                if "certificate_verify_failed" in message or "certificate verify failed" in message:
                    reason = "tls_verification_failed"
                    break
                if isinstance(current, httpx2.TimeoutException):
                    reason = "timeout"
                elif isinstance(current, httpx2.HTTPStatusError):
                    reason = "provider_http_error"
                elif isinstance(current, httpx2.ConnectError):
                    reason = "connection_failed"
                elif isinstance(current, socket.gaierror):
                    reason = "dns_failed"
                elif isinstance(current, OSError):
                    if current.errno == errno.ECONNREFUSED:
                        reason = "connection_refused"
                    elif current.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
                        reason = "network_unreachable"
                current = current.__cause__ or current.__context__
            return {"status": "unavailable", "reason": reason}

    def _json(self, url: str) -> dict:
        try:
            chunks = []
            length = 0
            with self._http.stream("GET", url) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > 262_144:
                        raise OidcUnavailable()
                    chunks.append(chunk)
            result = json.loads(b"".join(chunks))
            if not isinstance(result, dict):
                raise OidcUnavailable()
            return result
        except (httpx2.HTTPError, ValueError):
            raise OidcUnavailable() from None

    def _discovery(self) -> dict:
        with self._lock:
            if self._metadata is not None and time.monotonic() < self._metadata_until:
                return self._metadata
            result = self._json(self.config.issuer.rstrip("/") + "/.well-known/openid-configuration")
            try:
                if result.get("issuer") != self.config.issuer:
                    raise ValueError()
                for field_name in ("authorization_endpoint", "token_endpoint", "jwks_uri", "end_session_endpoint"):
                    value = result[field_name]
                    if not isinstance(value, str) or len(value) > 2048 or _origin(value) != _origin(self.config.issuer):
                        raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise OidcUnavailable() from None
            self._metadata = result
            self._metadata_until = time.monotonic() + 300
            return result

    def _token_verifier(self) -> TokenVerifier:
        with self._lock:
            if self._verifier is not None and time.monotonic() < self._keys_until:
                return self._verifier
            jwks = self._json(self._discovery()["jwks_uri"])
            try:
                self._verifier = TokenVerifier(self.config.issuer, self.config.client_id, jwks)
            except (TypeError, ValueError):
                raise OidcUnavailable() from None
            self._keys_until = time.monotonic() + 300
            return self._verifier

    def _oauth_client(self) -> OAuth2Client:
        return OAuth2Client(self.config.client_id, self.config.client_secret,
            scope="openid profile", redirect_uri=self.config.callback_uri,
            code_challenge_method="S256", timeout=3.0, follow_redirects=False, transport=self._transport)

    def authorization_url(self, pending: PendingLogin, *, reauthenticate: bool = False) -> str:
        metadata = self._discovery()
        with self._oauth_client() as client:
            url, _ = client.create_authorization_url(metadata["authorization_endpoint"],
                state=pending.state, nonce=pending.nonce, code_verifier=pending.code_verifier,
                **({"prompt": "login"} if reauthenticate else {}))
        return url

    def exchange(self, code: str, login: LoginSecrets) -> VerifiedIdentity:
        return self._exchange(code, login)[0]

    def _exchange(self, code: str, login: LoginSecrets):
        if not isinstance(code, str) or not code.isascii() or not 1 <= len(code) <= 4096:
            raise TokenRejected()
        metadata = self._discovery()
        try:
            with self._oauth_client() as client:
                result = client.fetch_token(metadata["token_endpoint"], grant_type="authorization_code",
                    code=code, code_verifier=login.code_verifier)
        except (httpx2.HTTPError, OAuth2Error, ValueError):
            raise OidcUnavailable() from None
        try:
            verifier = self._token_verifier()
            identity = verifier.verify_id_token(result["id_token"], nonce=login.nonce, access_token=result["access_token"])
            access = verifier.verify_access_token(result["access_token"])
            if access.account_key != identity.account_key or access.subject != identity.subject:
                raise TokenRejected()
            return replace(identity, expires_at=min(identity.expires_at, access.expires_at)), result
        except (KeyError, TypeError):
            raise TokenRejected() from None

    def exchange_renewable(self, code, login):
        identity, result = self._exchange(code, login)
        refresh = result.get('refresh_token')
        if not isinstance(refresh, str) or not 1 <= len(refresh) <= 16384:
            # A provider that doesn't issue refresh authority remains bounded
            # by its original token expiry; never fabricate renewal authority.
            return identity, None
        original = self._token_verifier()._decode(result['id_token'])
        original = {name: original[name] for name in ('iss', 'sub', 'aud', 'azp', 'auth_time') if name in original}
        credential = json.dumps({'access': result['access_token'], 'refresh': refresh,
                                 'nonce': login.nonce, 'id_context': original})
        return identity, RenewalResult(identity, credential)

    def _private_post(self, url, data, *, reject=False, rotating=False):
        try:
            with self._http.stream('POST', url, data=data,
                    auth=httpx2.BasicAuth(self.config.client_id, self.config.client_secret)) as response:
                if reject and response.status_code in (400, 401):
                    raise RenewalRejected()
                response.raise_for_status()
                chunks, length = [], 0
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > 65536:
                        raise RenewalRejected()
                    chunks.append(chunk)
                result = json.loads(b''.join(chunks))
                if not isinstance(result, dict):
                    raise RenewalRejected()
                return result
        except httpx2.RequestError:
            # The provider may already have rotated the credential when a
            # transport failure prevents us receiving its response. Never retry
            # that ambiguous refresh with the old credential.
            if rotating:
                raise RenewalRejected() from None
            raise RenewalUnavailable() from None
        except (httpx2.HTTPStatusError, OidcUnavailable):
            raise RenewalUnavailable() from None
        except (ValueError, TypeError, RecursionError):
            raise RenewalRejected() from None

    def check_renewal(self, credential):
        """Check provider session every authentication; refresh before expiry.

        Introspection never grants roles. The trusted same-origin provider's
        active flag supplements local signature/audience/identity verification.
        Credentials and provider error descriptions never leave this adapter.
        """
        try:
            saved = json.loads(credential)
            access_token, refresh, nonce = (saved[name] for name in ('access', 'refresh', 'nonce'))
            if any(not isinstance(v, str) or not 1 <= len(v) <= 16384 for v in (access_token, refresh, nonce)):
                raise RenewalRejected()
            original = saved['id_context']
            if not isinstance(original, dict) or original.get('iss') != self.config.issuer:
                raise RenewalRejected()
            metadata = self._discovery()
            introspection = metadata.get('introspection_endpoint')
            if (not isinstance(introspection, str) or len(introspection) > 2048
                    or _origin(introspection) != _origin(self.config.issuer)):
                raise RenewalRejected()
            verifier = self._token_verifier()
            # An expired access token can still renew using its original
            # provider refresh credential. The authority row binds identity.
            try:
                identity = verifier.verify_access_token(access_token)
                needs_refresh = identity.expires_at <= time.time() + 30
            except TokenRejected:
                needs_refresh = True
            if needs_refresh:
                result = self._private_post(metadata['token_endpoint'],
                    {'grant_type': 'refresh_token', 'refresh_token': refresh}, reject=True, rotating=True)
                if str(result.get('token_type', '')).lower() != 'bearer':
                    raise RenewalRejected()
                access_token = result['access_token']
                identity = verifier.verify_access_token(access_token)
                if 'id_token' in result:
                    verified_id = verifier.verify_refresh_id_token(result['id_token'], nonce=nonce,
                                                                   access_token=access_token, original=original)
                    if (verified_id.account_key != identity.account_key or verified_id.subject != identity.subject):
                        raise RenewalRejected()
                refresh = result.get('refresh_token', refresh)
                if not isinstance(refresh, str) or not 1 <= len(refresh) <= 16384:
                    raise RenewalRejected()
            if identity.issuer != original['iss'] or identity.subject != original['sub']:
                raise RenewalRejected()
            if not needs_refresh:
                active = self._private_post(introspection, {'token': access_token, 'token_type_hint': 'access_token'}, reject=True)
                if active.get('active') is not True:
                    raise RenewalRejected()
            return RenewalResult(identity, json.dumps({'access': access_token, 'refresh': refresh,
                                                       'nonce': nonce, 'id_context': original}))
        except (OidcUnavailable, RenewalUnavailable):
            raise RenewalUnavailable() from None
        except (KeyError, TypeError, ValueError, TokenRejected):
            raise RenewalRejected() from None

    def verify_access_token(self, token: str) -> VerifiedIdentity:
        if not isinstance(token, str) or len(token) > 16_384 or not re.fullmatch(
                r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
            raise TokenRejected()
        return self._token_verifier().verify_access_token(token)

    def logout_url(self) -> str:
        return self._discovery()["end_session_endpoint"] + "?" + urlencode({
            "client_id": self.config.client_id, "post_logout_redirect_uri": self.config.logout_return_uri})
