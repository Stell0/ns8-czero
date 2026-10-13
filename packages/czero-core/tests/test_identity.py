# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import hashlib
from uuid import UUID

import pytest
from joserfc import jwt
from joserfc.jwk import OctKey, RSAKey

from czero_core.identity import Actor, PermissionDenied, Role, TokenRejected, TokenVerifier

NOW = 2_000_000_000
ISSUER = "https://idp.example.test/realms/users.example.test"
NONCE = "unit-only-oidc-nonce"
ACCOUNT = "6cc309bc-264e-4577-8ca8-bd56ec021e47"


@pytest.fixture(scope="module")
def signer():
    return RSAKey.generate_key(2048, {"kid": "trusted", "use": "sig"})


@pytest.fixture
def verifier(signer):
    return TokenVerifier(ISSUER, "czero1", {"keys": [signer.as_dict(private=False)]}, now=lambda: NOW)


def claims(**changes):
    return {"iss": ISSUER, "aud": "czero1", "sub": "provider-subject",
            "ldap_uuid": ACCOUNT, "preferred_username": "owner", "name": "Owner",
            "iat": NOW - 30, "exp": NOW + 300, "typ": "Bearer", **changes}


def signed(signer, payload=None, header=None):
    return jwt.encode({"alg": "RS256", "kid": "trusted", **(header or {})},
                      payload if payload is not None else claims(), signer)


def test_valid_signed_identity_has_no_token_role_authority(verifier, signer):
    value = signed(signer, claims(role="admin", realm_access={"roles": ["admin"]}, ldap_uuid=ACCOUNT.upper()))
    identity = verifier.verify_access_token(value)
    assert identity.issuer == ISSUER
    assert identity.account_key == ACCOUNT
    assert identity.subject == "provider-subject"
    assert identity.username == "owner"
    assert identity.expires_at == NOW + 300
    assert not hasattr(identity, "role")
    assert value not in repr(identity)


@pytest.mark.parametrize("missing", ["iss", "aud", "sub", "exp", "iat", "typ", "ldap_uuid", "preferred_username"])
def test_missing_identity_or_validation_claim_is_rejected(verifier, signer, missing):
    payload = claims()
    del payload[missing]
    with pytest.raises(TokenRejected, match="^invalid_token$"):
        verifier.verify_access_token(signed(signer, payload))


@pytest.mark.parametrize("updates", [
    {"iss": "https://other.example.test"}, {"aud": "another-app"}, {"aud": ["another-app"]},
    {"exp": NOW - 1}, {"nbf": NOW + 1}, {"iat": NOW + 1}, {"iat": True},
    {"sub": ""}, {"sub": ["not-a-subject"]}, {"typ": "ID"},
    {"ldap_uuid": "not-a-uuid"}, {"preferred_username": ["owner"]},
    {"preferred_username": "\nowner"}, {"exp": float("inf")},
    {"aud": ["czero1", 42]},
])
def test_invalid_claims_fail_closed(verifier, signer, updates):
    with pytest.raises(TokenRejected, match="^invalid_token$"):
        verifier.verify_access_token(signed(signer, claims(**updates)))


@pytest.mark.parametrize("header", [{"kid": "unregistered"}, {"jku": "https://untrusted.example.test/keys"},
                                    {"jwk": {"kty": "RSA"}}, {"x5u": "https://untrusted.example.test/cert"}])
def test_token_cannot_select_an_untrusted_key_source(verifier, signer, header):
    with pytest.raises(TokenRejected, match="^invalid_token$"):
        verifier.verify_access_token(signed(signer, header=header))


def test_bad_signature_and_hmac_confusion_are_rejected(verifier, signer):
    value = signed(signer)
    parts = value.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    with pytest.raises(TokenRejected):
        verifier.verify_access_token(".".join(parts))
    hmac_value = jwt.encode({"alg": "HS256", "kid": "trusted"}, claims(), OctKey.generate_key(256))
    with pytest.raises(TokenRejected):
        verifier.verify_access_token(hmac_value)


@pytest.mark.parametrize("value", [None, "", "malformed", "x" * 16_385])
def test_invalid_token_inputs_are_bounded(verifier, value):
    with pytest.raises(TokenRejected, match="^invalid_token$"):
        verifier.verify_access_token(value)


def test_id_token_requires_nonce_and_authorized_party(verifier, signer):
    value = signed(signer, claims(typ="ID", nonce=NONCE, aud=["czero1", "account"], azp="czero1"))
    assert verifier.verify_id_token(value, nonce=NONCE).account_key == ACCOUNT
    for updates in [{"nonce": "wrong"}, {"azp": "another-app"}]:
        with pytest.raises(TokenRejected):
            verifier.verify_id_token(signed(signer, claims(**{"typ": "ID", "nonce": NONCE, **updates})), nonce=NONCE)
    for payload in [claims(typ="ID"), claims(typ="ID", nonce=NONCE, aud=["czero1", "account"])]:
        with pytest.raises(TokenRejected):
            verifier.verify_id_token(signed(signer, payload), nonce=NONCE)


def test_oidc_access_token_hash_binding(verifier, signer):
    access = "opaque-unit-test-value"
    digest = hashlib.sha256(access.encode()).digest()[:16]
    at_hash = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    value = signed(signer, claims(typ="ID", nonce=NONCE, at_hash=at_hash))
    assert verifier.verify_id_token(value, nonce=NONCE, access_token=access).username == "owner"
    with pytest.raises(TokenRejected):
        verifier.verify_id_token(value, nonce=NONCE, access_token="different-unit-value")
    with pytest.raises(TokenRejected):
        verifier.verify_id_token(value, nonce=NONCE)


def test_id_token_rejects_access_token_confusion_and_non_ascii_hash_input(verifier, signer):
    with pytest.raises(TokenRejected):
        verifier.verify_id_token(signed(signer, claims(nonce=NONCE)), nonce=NONCE)
    value = signed(signer, claims(typ="ID", nonce=NONCE, at_hash="unmatched"))
    with pytest.raises(TokenRejected):
        verifier.verify_id_token(value, nonce=NONCE, access_token="non-ascii-\u00e9")


@pytest.mark.parametrize("role,owner", [("admin", False), (Role.READER, True), (Role.ADMIN, "true")])
def test_actor_requires_a_resolved_role_and_valid_owner_flag(role, owner):
    with pytest.raises(ValueError):
        Actor(UUID(int=1), role, owner)


@pytest.mark.parametrize("role,minimum,allowed", [
    (Role.READER, Role.READER, True), (Role.READER, Role.EDITOR, False), (Role.READER, Role.ADMIN, False),
    (Role.EDITOR, Role.READER, True), (Role.EDITOR, Role.EDITOR, True), (Role.EDITOR, Role.ADMIN, False),
    (Role.ADMIN, Role.READER, True), (Role.ADMIN, Role.EDITOR, True), (Role.ADMIN, Role.ADMIN, True),
])
def test_shared_role_boundaries(role, minimum, allowed):
    actor = Actor(UUID(int=1), role)
    if allowed:
        actor.require(minimum)
    else:
        with pytest.raises(PermissionDenied, match="^forbidden$"):
            actor.require(minimum)
