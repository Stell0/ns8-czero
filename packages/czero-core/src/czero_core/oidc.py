# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded NS8 OIDC discovery and authorization-code client operations."""
from dataclasses import dataclass, field, replace
import json
import threading
import time
from urllib.parse import urlencode, urlsplit

from authlib.integrations.httpx_client import OAuth2Client
from authlib.oauth2.rfc6749.errors import OAuth2Error
import httpx2

from .identity import TokenRejected, TokenVerifier, VerifiedIdentity
from .sessions import LoginSecrets, PendingLogin


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

    def authorization_url(self, pending: PendingLogin) -> str:
        metadata = self._discovery()
        with self._oauth_client() as client:
            url, _ = client.create_authorization_url(metadata["authorization_endpoint"],
                state=pending.state, nonce=pending.nonce, code_verifier=pending.code_verifier)
        return url

    def exchange(self, code: str, login: LoginSecrets) -> VerifiedIdentity:
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
            return replace(identity, expires_at=min(identity.expires_at, access.expires_at))
        except (KeyError, TypeError):
            raise TokenRejected() from None

    def verify_access_token(self, token: str) -> VerifiedIdentity:
        return self._token_verifier().verify_access_token(token)

    def logout_url(self) -> str:
        return self._discovery()["end_session_endpoint"] + "?" + urlencode({
            "client_id": self.config.client_id, "post_logout_redirect_uri": self.config.logout_return_uri})
