# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from czero_app import auth_check


def test_disabled_diagnostic_does_not_construct_network_client(monkeypatch):
    monkeypatch.delenv("CZERO_OIDC_ISSUER", raising=False)
    monkeypatch.setattr(auth_check, "OidcClient", lambda *a: (_ for _ in ()).throw(AssertionError()))
    assert auth_check.status() == {"configured": False, "status": "disabled"}


def test_native_diagnostic_keeps_credentials_private_and_closes_client(monkeypatch):
    for key,value in {"CZERO_OIDC_ISSUER":"https://idp.example.test/realms/users",
        "CZERO_OIDC_CLIENT_ID":"czero1", "CZERO_OIDC_CLIENT_SECRET":"private-client-value",
        "CZERO_AUTH_PUBLIC_ORIGIN":"https://c0.example.test", "CZERO_BASE_PATH":""}.items():
        monkeypatch.setenv(key,value)
    closed=[]
    class Client:
        def __init__(self, config):assert config.client_secret=="private-client-value"
        def health(self):return {"status":"unavailable", "reason":"tls_verification_failed"}
        def close(self):closed.append(True)
    monkeypatch.setattr(auth_check,"OidcClient",Client)
    assert auth_check.status()=={"configured":True,"status":"unavailable","reason":"tls_verification_failed"}
    assert closed==[True]
    monkeypatch.setenv("CZERO_OIDC_ISSUER","http://private.invalid")
    assert auth_check.status()=={"configured":True,"status":"unavailable","reason":"configuration_invalid"}
