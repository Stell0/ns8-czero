# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Restricted native diagnostics for the configured OIDC runtime connection."""
import json
import os

from czero_core.oidc import OidcClient, OidcConfig


def status() -> dict:
    values = [os.getenv(name, "") for name in (
        "CZERO_OIDC_ISSUER", "CZERO_OIDC_CLIENT_ID", "CZERO_OIDC_CLIENT_SECRET",
        "CZERO_AUTH_PUBLIC_ORIGIN")]
    if not all(values):
        return {"configured": False, "status": "disabled"}
    try:
        config = OidcConfig(*values, base_path=os.getenv("CZERO_BASE_PATH", ""))
    except ValueError:
        return {"configured": True, "status": "unavailable", "reason": "configuration_invalid"}
    client = OidcClient(config)
    try:
        return {"configured": True, **client.health()}
    finally:
        client.close()


if __name__ == "__main__":
    print(json.dumps(status()))
