# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verified NS8 identities and simple application-wide role boundaries.

The caller supplies trusted issuer keys. Token headers never select a remote
key source, and token role claims never assign C0 permissions.
"""
import base64
from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import hmac
import math
import time
from typing import Callable
from urllib.parse import urlsplit
from uuid import UUID

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry


class TokenRejected(ValueError):
    def __init__(self):
        super().__init__("invalid_token")


class PermissionDenied(ValueError):
    def __init__(self):
        super().__init__("forbidden")


class Role(StrEnum):
    READER = "reader"
    EDITOR = "editor"
    ADMIN = "admin"


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    role: Role
    is_owner: bool = False
    # Internal trusted context, never request arguments or identity authority.
    # Exclude from identity equality and representations; services refresh it.
    delegation: object | None = field(default=None, repr=False, compare=False)
    delegated_scopes: frozenset[str] | None = field(default=None, repr=False, compare=False)
    space_id: UUID | None = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.user_id, UUID) or not isinstance(self.role, Role) or type(self.is_owner) is not bool:
            raise ValueError("Invalid admitted actor")
        if self.is_owner and self.role is not Role.ADMIN:
            raise ValueError("The owner requires Admin access")

    def require(self, minimum: Role) -> None:
        ranks = {Role.READER: 1, Role.EDITOR: 2, Role.ADMIN: 3}
        if not isinstance(minimum, Role) or ranks[self.role] < ranks[minimum]:
            raise PermissionDenied()


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    account_key: str
    username: str
    display_name: str
    expires_at: float


def _text(value, maximum: int) -> str:
    if not isinstance(value, str) or not 0 < len(value) <= maximum or not value.isprintable():
        raise TokenRejected()
    return value


class TokenVerifier:
    """Validate NS8 Keycloak RS256 access and ID tokens using trusted JWKS.

    Discovery, key caching and membership admission are separate services.
    The returned identity grants no role on its own.
    """

    def __init__(self, issuer: str, audience: str, jwks: dict,
                 *, now: Callable[[], int] | None = None):
        url = urlsplit(issuer)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Invalid trusted issuer")
        self.issuer = _text(issuer, 1024)
        self.audience = _text(audience, 128)
        self._now = now or (lambda: int(time.time()))
        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list) or not 1 <= len(jwks["keys"]) <= 32:
            raise ValueError("Invalid trusted key set")
        # Keycloak may publish encryption keys too; keep only RSA signing keys.
        keys = [key for key in jwks["keys"] if isinstance(key, dict) and key.get("kty") == "RSA"
                and key.get("use", "sig") == "sig" and key.get("alg", "RS256") == "RS256"]
        if not keys:
            raise ValueError("No trusted RSA signing keys")
        self._keys = KeySet.import_key_set({"keys": keys})

    def _decode(self, value: str) -> dict:
        if not isinstance(value, str) or not value.isascii() or not 0 < len(value) <= 16_384:
            raise TokenRejected()
        try:
            token = jwt.decode(value, self._keys, algorithms=["RS256"])
            if any(name in token.header for name in ("jku", "jwk", "x5u")):
                raise TokenRejected()
            _text(token.header.get("kid"), 128)
            current = self._now()
            JWTClaimsRegistry(now=current, leeway=0,
                iss={"essential": True, "value": self.issuer},
                aud={"essential": True, "value": self.audience},
                sub={"essential": True}, exp={"essential": True}, iat={"essential": True},
                ldap_uuid={"essential": True}, preferred_username={"essential": True},
            ).validate(token.claims)
            audiences = token.claims["aud"]
            if isinstance(audiences, list):
                if not 1 <= len(audiences) <= 16:
                    raise TokenRejected()
                for audience in audiences:
                    _text(audience, 1024)
            else:
                _text(audiences, 1024)
            for name in ("exp", "iat", "nbf"):
                if name in token.claims:
                    number = token.claims[name]
                    if type(number) not in (int, float) or not math.isfinite(number):
                        raise TokenRejected()
            if token.claims["exp"] <= current:
                raise TokenRejected()
            return token.claims
        except (JoseError, KeyError, TypeError, ValueError, OverflowError):
            raise TokenRejected() from None

    def _identity(self, claims: dict) -> VerifiedIdentity:
        try:
            return VerifiedIdentity(self.issuer, _text(claims["sub"], 255),
                str(UUID(_text(claims["ldap_uuid"], 64))),
                _text(claims["preferred_username"], 128),
                _text(claims.get("name", claims["preferred_username"]), 256), claims["exp"])
        except (KeyError, TypeError, ValueError):
            raise TokenRejected() from None

    def verify_access_token(self, value: str) -> VerifiedIdentity:
        claims = self._decode(value)
        if claims.get("typ") != "Bearer":
            raise TokenRejected()
        return self._identity(claims)

    def verify_id_token(self, value: str, *, nonce: str,
                        access_token: str | None = None) -> VerifiedIdentity:
        claims = self._decode(value)
        if claims.get("typ") not in (None, "ID"):
            raise TokenRejected()
        supplied_nonce = _text(claims.get("nonce"), 128)
        if not hmac.compare_digest(supplied_nonce.encode(), _text(nonce, 128).encode()):
            raise TokenRejected()
        audiences = claims["aud"]
        if isinstance(audiences, list) and len(audiences) > 1 and claims.get("azp") != self.audience:
            raise TokenRejected()
        if "azp" in claims and claims["azp"] != self.audience:
            raise TokenRejected()
        if "at_hash" in claims:
            access = _text(access_token, 16_384)
            if not access.isascii():
                raise TokenRejected()
            digest = hashlib.sha256(access.encode("ascii")).digest()[:16]
            expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
            if not hmac.compare_digest(_text(claims["at_hash"], 128).encode(), expected.encode()):
                raise TokenRejected()
        return self._identity(claims)
