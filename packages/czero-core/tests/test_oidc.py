# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx2
import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey

from czero_core.oidc import OidcClient, OidcConfig, OidcUnavailable
from czero_core.identity import TokenRejected
from czero_core.sessions import LoginSecrets, PendingLogin

ISSUER = "https://idp.example.test/realms/users.example.test"
ORIGIN = "https://c0.example.test"


def test_connectivity_checks_keys_and_preserves_cached_success(provider):
    client, _, calls, *_ = provider
    assert client.health() == {"status": "ok"}
    assert len(calls) == 2
    assert client.health() == {"status": "ok"} and len(calls) == 2


@pytest.mark.parametrize("failure,reason", [
    (httpx2.ConnectError("CERTIFICATE_VERIFY_FAILED https://private.invalid/?secret=value"), "tls_verification_failed"),
    (httpx2.ConnectError("private address failed"), "connection_failed"),
    (httpx2.ReadTimeout("private address timed out"), "timeout"),
    (None, "provider_http_error"),
    ({"invalid": "private-metadata"}, "metadata_invalid"),
])
def test_connectivity_reports_only_fixed_error_categories(failure, reason):
    def handle(request):
        if isinstance(failure, Exception): raise failure
        return httpx2.Response(503 if failure is None else 200, json=failure)
    client = OidcClient(OidcConfig(ISSUER, "czero1", "private-client", ORIGIN),
                        transport=httpx2.MockTransport(handle))
    try:
        assert client.health() == {"status": "unavailable", "reason": reason}
    finally:
        client.close()


@pytest.mark.parametrize("value", ["invalid", "", "a.b", "a.b.c.d", "a.b.$", "a.b.c\n", "a"*16385, None])
def test_malformed_bearer_rejected_before_unavailable_provider(value):
    def handle(request): pytest.fail("Malformed token must not request provider keys")
    client = OidcClient(OidcConfig(ISSUER, "czero1", "private-client", ORIGIN),
                        transport=httpx2.MockTransport(handle))
    try:
        with pytest.raises(TokenRejected):client.verify_access_token(value)
    finally:
        client.close()


class PrivateFixture(tuple):
    def __repr__(self):
        return "<private OIDC fixture>"


@pytest.fixture
def provider():
    key = RSAKey.generate_key(2048, {"kid": "trusted", "use": "sig"})
    account = str(uuid4())
    calls = []
    nonce = "unit-only-login-nonce"
    verifier = "unit-only-code-verifier-value-that-is-long-enough"
    secret = "unit-only-client-value"
    metadata = {"issuer": ISSUER, "authorization_endpoint": ISSUER + "/protocol/openid-connect/auth",
                "token_endpoint": ISSUER + "/protocol/openid-connect/token",
                "jwks_uri": ISSUER + "/protocol/openid-connect/certs",
                "end_session_endpoint": ISSUER + "/protocol/openid-connect/logout"}
    tokens = {}
    for kind in ("ID", "Bearer"):
        claims = {"iss": ISSUER, "aud": "czero1", "sub": "subject", "ldap_uuid": account,
                  "preferred_username": "owner", "iat": int(time.time()) - 1,
                  "exp": int(time.time()) + 300, "typ": kind}
        if kind == "ID":
            claims["nonce"] = nonce
        tokens[kind] = jwt.encode({"alg": "RS256", "kid": "trusted"}, claims, key)
    def handle(request):
        calls.append(request.url.path)
        if request.url.path.endswith("openid-configuration"):
            return httpx2.Response(200, json=metadata)
        if request.url.path.endswith("certs"):
            return httpx2.Response(200, json={"keys": [key.as_dict(private=False)]})
        if request.url.path.endswith("token"):
            body = parse_qs(request.content.decode())
            assert body["grant_type"] == ["authorization_code"]
            assert body["code_verifier"] == [verifier]
            assert body["redirect_uri"] == [ORIGIN + "/auth/callback"]
            assert request.headers["authorization"].startswith("Basic ")
            return httpx2.Response(200, json={"access_token": tokens["Bearer"], "id_token": tokens["ID"],
                                              "token_type": "Bearer", "expires_in": 300})
        return httpx2.Response(404)
    config = OidcConfig(ISSUER, "czero1", secret, ORIGIN)
    client = OidcClient(config, transport=httpx2.MockTransport(handle))
    yield PrivateFixture((client, metadata, calls, nonce, verifier, tokens))
    client.close()


def test_login_uses_exact_callback_nonce_and_s256_pkce(provider):
    client, _, calls, nonce, verifier, _ = provider
    pending = PendingLogin("unit-only-state", "unit-only-browser", nonce, verifier)
    url = client.authorization_url(pending)
    query = parse_qs(urlsplit(url).query)
    assert query["client_id"] == ["czero1"]
    assert query["redirect_uri"] == [ORIGIN + "/auth/callback"]
    assert query["state"] == [pending.state]
    assert query["nonce"] == [nonce]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] != [verifier]
    assert "unit-only-client-value" not in url
    client.authorization_url(pending)
    assert calls.count("/realms/users.example.test/.well-known/openid-configuration") == 1


def test_exchange_validates_both_tokens_and_returned_identity(provider):
    client, _, _, nonce, verifier, tokens = provider
    identity = client.exchange("unit-only-code", LoginSecrets(nonce, verifier))
    assert identity.username == "owner"
    assert client.verify_access_token(tokens["Bearer"]).account_key == identity.account_key
    with pytest.raises(TokenRejected):
        client.exchange("unit-only-code", LoginSecrets("wrong-nonce", verifier))


@pytest.mark.parametrize("field", ["issuer", "token_endpoint", "jwks_uri", "authorization_endpoint", "end_session_endpoint"])
def test_discovery_cannot_redirect_credentials_to_another_origin(provider, field):
    client, metadata, _, _, _, _ = provider
    metadata[field] = "https://untrusted.example.test/endpoint"
    with pytest.raises(OidcUnavailable, match="^authentication_unavailable$"):
        client.authorization_url(PendingLogin("state", "browser", "nonce", "verifier"))


def test_network_failure_is_safe_and_does_not_echo_client_secret():
    def unavailable(request):
        raise httpx2.ConnectError("sensitive-provider-diagnostic", request=request)
    client = OidcClient(OidcConfig(ISSUER, "czero1", "sensitive-client-value", ORIGIN),
                        transport=httpx2.MockTransport(unavailable))
    try:
        with pytest.raises(OidcUnavailable) as error:
            client.authorization_url(PendingLogin("state", "browser", "nonce", "verifier"))
        assert str(error.value) == "authentication_unavailable"
        assert "sensitive" not in repr(client.config)
    finally:
        client.close()


def test_logout_url_contains_exact_return_uri_and_no_token_hint(provider):
    client, _, _, _, _, _ = provider
    query = parse_qs(urlsplit(client.logout_url()).query)
    assert query == {"client_id": ["czero1"], "post_logout_redirect_uri": [ORIGIN + "/"]}
