# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run only against an externally installed wheel/archive and disposable DB."""
from datetime import datetime, timezone
import json
import os
import secrets
import time
from uuid import UUID, uuid4

from sqlalchemy import text

from czero_core.access import AccessService
from czero_core.cimd_metadata import parse_metadata
from czero_core.database import Database
from czero_core.identity import VerifiedIdentity
from czero_core.oauth_grants import OAuthGrantService, GrantRejected, pkce_challenge
from czero_core.sessions import SessionContext


def main():
    if os.getenv('CZERO_DISPOSABLE_TEST') != '1':
        raise RuntimeError('Disposable fixture opt-in required')
    database = Database()
    issuer, approved, registry, started = None, None, None, False
    try:
        key, now = uuid4(), time.time()
        issuer = 'https://idp.example.test/' + uuid4().hex
        access = AccessService(database, issuer, key)
        actor = access.resolve(VerifiedIdentity(issuer, 'owner', str(key), 'owner', 'Owner', now + 600))
        session = SessionContext(actor, datetime.fromtimestamp(now + 600, timezone.utc), 'test-only-csrf')
        resource, callback = 'https://c0.example.test/mcp', 'https://client.example.test/callback'
        grants = OAuthGrantService(access, 'native1', resource)
        registry = grants.cimd
        assert not registry.enabled()
        started = True
        registry.sync_policy(True)
        url = 'https://client.example.test/' + uuid4().hex + '/client.json'
        metadata = parse_metadata(url, json.dumps({'client_id': url, 'client_name': 'Packaged CIMD client',
            'redirect_uris': [callback], 'token_endpoint_auth_method': 'none',
            'grant_types': ['authorization_code', 'refresh_token']}).encode())
        approved = registry.approve(actor, metadata, expected_digest=metadata.digest)
        assert grants.clients._lookup(approved['client_id']) is None
        attestation = registry.observe(metadata, expected_revision=1)
        verifier = secrets.token_urlsafe(32)
        code = grants.issue_code(session, url, callback=callback, scopes={'c0:read'},
            challenge=pkce_challenge(verifier), resource=resource, verification=attestation)
        tokens = grants.exchange_code(code, url, callback=callback, verifier=verifier, resource=resource)
        assert grants.verify(tokens.access_token, resource=resource).client_id == url
        rotated = grants.refresh(tokens.refresh_token, url, resource=resource)
        assert grants.verify(rotated.access_token, resource=resource).actor.user_id == actor.user_id
        registry.sync_policy(False)
        registry.sync_policy(True)
        try:
            grants.verify(rotated.access_token, resource=resource)
        except GrantRejected:
            pass
        else:
            raise AssertionError('Revoked CIMD authority revived')
        registry.sync_policy(False)
        grants.clients.set_enabled(actor, UUID(approved['client_id']), enabled=False, expected_revision=1)
        print(json.dumps({'approval': True, 'url_identity': True, 'rotation': True, 'revocation': True}))
    finally:
        try:
            if started:
                registry.sync_policy(False)
            with database.engine.begin() as connection:
                if approved is not None:
                    connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),
                                       {'id': UUID(approved['client_id'])})
                if issuer is not None:
                    connection.execute(text('DELETE FROM c0_accounts WHERE issuer=:issuer'), {'issuer': issuer})
        finally:
            database.close()


if __name__ == '__main__':
    main()
