# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual PostgreSQL approval, exact identities and authority lifecycle."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import secrets
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.cimd import CimdRejected
from czero_core.cimd_metadata import parse_metadata
from czero_core.identity import PermissionDenied, Role
from czero_core.oauth_clients import ClientConflict
from czero_core.oauth_consent import ConsentRejected, OAuthConsentService
from czero_core.oauth_grants import GrantRejected, pkce_challenge
from czero_core.migrate import migrate_database
from test_auth_http import application, PrivateFixture
from test_oauth_grants import grants, CALLBACK, RESOURCE, issue, redeem

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def cimd(grants):
    service, clients, manual, session, clock, app, member = grants
    registry = service.cimd
    registry.sync_policy(True)
    url = 'https://client.example.test/' + uuid4().hex + '/client.json'
    def metadata(**changes):
        return parse_metadata(url, json.dumps({'client_id': url, 'client_name': 'Approved public client',
            'redirect_uris': [CALLBACK], 'token_endpoint_auth_method': 'none',
            'grant_types': ['authorization_code', 'refresh_token'], **changes}).encode())
    value = metadata()
    client = registry.approve(session.actor, value, expected_digest=value.digest,
                              scopes=['c0:read', 'c0:write'], cache_seconds=60)
    yield PrivateFixture((service, registry, client, value, metadata, grants))
    registry.sync_policy(False)
    with service.access.database.engine.begin() as connection:
        connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id': UUID(client['client_id'])})


def proof(fixture):
    _, registry, client, value, *_ = fixture
    return registry.observe(value, expected_revision=client['revision'])


def pair(fixture, *, verification=None):
    service, _, _, value, _, (_, _, _, session, *_) = fixture
    verification = verification or proof(fixture)
    values = issue(service, {'client_id': value.client_id}, session, verification=verification)
    return redeem(service, {'client_id': value.client_id}, values)


def pending(fixture):
    service, _, _, value, *_ = fixture
    verifier = secrets.token_urlsafe(32)
    consent = OAuthConsentService(service)
    request = consent.begin(value.client_id, callback=CALLBACK, scopes={'c0:read'},
        challenge=pkce_challenge(verifier), state='private-test-state', resource=RESOURCE,
        verification=proof(fixture))
    return consent, request, verifier


def test_url_public_identity_internal_uuid_is_not_an_alias(cimd):
    service, registry, client, value, _, (__, clients, manual, session, *_) = cimd
    assert clients._lookup(client['client_id']) is None
    lookup = clients._lookup(value.client_id)
    assert lookup['internal_id'] == UUID(client['client_id']) and lookup['client_id'] == value.client_id
    assert lookup['registration_kind'] == 'cimd'
    tokens = pair(cimd)
    assert service.verify(tokens.access_token, resource=RESOURCE).client_id == value.client_id
    with pytest.raises(GrantRejected):
        service.refresh(tokens.refresh_token, client['client_id'], resource=RESOURCE)
    rotated = service.refresh(tokens.refresh_token, value.client_id, resource=RESOURCE)
    assert service.verify(rotated.access_token, resource=RESOURCE).actor.user_id == session.actor.user_id
    assert clients._lookup(manual['client_id'])['client_id'] == manual['client_id']
    assert all(UUID(row['client_id']) for row in clients.list(session.actor))


def test_code_and_consent_need_fresh_request_local_proof_but_denial_needs_no_fetch(cimd):
    service, registry, client, value, _, (_, _, _, session, clock, *_) = cimd
    with pytest.raises(GrantRejected):
        issue(service, {'client_id': value.client_id}, session)
    consent, request, verifier = pending(cimd)
    assert consent.view(request.request, request.binding)['client_id'] == value.client_id
    attestation = proof(cimd)
    clock[0] += 31
    with pytest.raises(GrantRejected):
        pair(cimd, verification=attestation)
    with pytest.raises(GrantRejected):
        consent.complete(session, request.request, request.binding, approve=True, verification=attestation)
    result = consent.complete(session, request.request, request.binding, approve=False)
    assert result.code is None
    consent, request, verifier = pending(cimd)
    result = consent.complete(session, request.request, request.binding, approve=True, verification=proof(cimd))
    tokens = service.exchange_code(result.code, value.client_id, callback=CALLBACK, verifier=verifier, resource=RESOURCE)
    assert service.verify(tokens.access_token, resource=RESOURCE).client_id == value.client_id


def test_metadata_changes_stick_for_review_without_interrupting_existing_grants(cimd):
    service, registry, client, value, metadata, (_, _, _, session, *_) = cimd
    tokens = pair(cimd)
    consent, request, _ = pending(cimd)
    changed = metadata(client_name='Changed public client')
    with pytest.raises(CimdRejected):
        registry.observe(changed, expected_revision=1)
    with pytest.raises(ConsentRejected):
        consent.view(request.request, request.binding)
    assert registry.status(session.actor)['clients'][0]['review_required']
    with pytest.raises(CimdRejected):
        registry.observe(value, expected_revision=1)
    # Reversion and create retry cannot silently approve a change.
    assert registry.approve(session.actor, value, expected_digest=value.digest,
        scopes=['c0:read', 'c0:write'])['review_required']
    rotated = service.refresh(tokens.refresh_token, value.client_id, resource=RESOURCE)
    assert service.verify(rotated.access_token, resource=RESOURCE).client_id == value.client_id
    reviewed = registry.approve(session.actor, changed, expected_digest=changed.digest,
        scopes=['c0:read'], client_id=UUID(client['client_id']), expected_revision=1)
    assert reviewed['revision'] == 2 and not reviewed['review_required']
    with pytest.raises(GrantRejected):
        service.verify(rotated.access_token, resource=RESOURCE)


def test_policy_off_revokes_only_cimd_and_reenable_or_restart_cannot_revive(cimd):
    service, registry, client, value, _, (_, _, manual, session, *_) = cimd
    old = redeem(service, manual, issue(service, manual, session))
    tokens = pair(cimd)
    captured = service.verify(tokens.access_token, resource=RESOURCE).actor
    consent, request, _ = pending(cimd)
    registry.sync_policy(True)
    assert service.verify(tokens.access_token, resource=RESOURCE)
    registry.sync_policy(False)
    registry.sync_policy(False)
    assert not registry.enabled()
    assert service.verify(old.access_token, resource=RESOURCE)
    with pytest.raises(PermissionDenied):
        service.access.authorize(captured, Role.READER)
    with pytest.raises(CimdRejected):
        registry.approval(value.client_id)
    registry.sync_policy(True)
    with pytest.raises(GrantRejected):
        service.refresh(tokens.refresh_token, value.client_id, resource=RESOURCE)
    with pytest.raises(ConsentRejected):
        consent.view(request.request, request.binding)
    assert pair(cimd)


def test_disabled_client_duplicates_keep_uuid_revision_and_disabled_state(cimd):
    service, registry, client, value, _, (_, clients, _, session, *_) = cimd
    tokens = pair(cimd)
    captured = service.verify(tokens.access_token, resource=RESOURCE).actor
    clients.set_enabled(session.actor, UUID(client['client_id']), enabled=False, expected_revision=1)
    repeated = registry.approve(session.actor, value, expected_digest=value.digest,
        scopes=['c0:read', 'c0:write'])
    assert repeated['client_id'] == client['client_id'] and not repeated['enabled'] and repeated['revision'] == 2
    with pytest.raises(PermissionDenied):
        service.access.authorize(captured, Role.READER)
    clients.set_enabled(session.actor, UUID(client['client_id']), enabled=True, expected_revision=2)
    with pytest.raises(GrantRejected):
        service.verify(tokens.access_token, resource=RESOURCE)


def test_approval_conflicts_and_scope_ceiling_are_checked_after_admin_authority(cimd):
    service, registry, client, value, metadata, (_, _, _, session, *_) = cimd
    with pytest.raises(ClientConflict):
        registry.approve(session.actor, value, expected_digest='0' * 64)
    with pytest.raises(ClientConflict):
        registry.approve(session.actor, value, expected_digest=value.digest, scopes=['c0:admin'])
    for changes in [dict(client_id=UUID(client['client_id']), expected_revision=2),
                    dict(client_id=uuid4(), expected_revision=1)]:
        with pytest.raises(ClientConflict):
            registry.approve(session.actor, value, expected_digest=value.digest, **changes)
    with pytest.raises(ValueError, match='invalid_client_scopes'):
        limited = metadata(scope='c0:read')
        registry.approve(session.actor, limited, expected_digest=limited.digest, scopes=['c0:write'])
    registry.sync_policy(False)
    with pytest.raises(CimdRejected):
        registry.approve(session.actor, value, expected_digest=value.digest, scopes=['c0:read', 'c0:write'])


def test_authorization_code_only_has_no_refresh_authority(cimd):
    service, registry, client, value, metadata, (_, _, _, session, *_) = cimd
    value = metadata(grant_types=['authorization_code'])
    updated = registry.approve(session.actor, value, expected_digest=value.digest, scopes=['c0:read'],
        client_id=UUID(client['client_id']), expected_revision=1)
    fixture = (service, registry, updated, value, metadata, cimd[-1])
    tokens = pair(fixture)
    assert tokens.refresh_token is None
    with service.access.database.engine.connect() as connection:
        assert connection.execute(text('''SELECT count(*) FROM c0_oauth_tokens t JOIN c0_oauth_grants g
            ON g.id=t.grant_id WHERE g.client_id=:id AND t.kind='refresh' '''),
            {'id': UUID(client['client_id'])}).scalar_one() == 0


def test_concurrent_duplicate_approval_has_one_stable_binding_and_reapproval_one_winner(cimd):
    _, registry, client, value, metadata, (_, _, _, session, *_) = cimd
    def approve(_):
        return registry.approve(session.actor, value, expected_digest=value.digest,
            scopes=['c0:read', 'c0:write'])['client_id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(approve, range(2))) == [client['client_id']] * 2
    changed = metadata(client_name='Reviewed change')
    def reapprove(_):
        try:
            registry.approve(session.actor, changed, expected_digest=changed.digest,
                client_id=UUID(client['client_id']), expected_revision=1)
            return 'approved'
        except ClientConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reapprove, range(2))) == ['approved', 'conflict']


def test_restart_migration_preserves_policy_approval_and_unexpired_authority(cimd):
    service, registry, client, value, _, (_, _, _, session, *_) = cimd
    tokens = pair(cimd)
    before = registry.status(session.actor)
    for _ in range(2):
        migrate_database(service.access.database)
        registry.sync_policy(True)
        assert registry.status(session.actor) == before
        assert service.verify(tokens.access_token, resource=RESOURCE).client_id == value.client_id


def test_concurrent_refresh_and_disable_cannot_leave_usable_post_disable_authority(cimd):
    service, registry, client, value, _, (_, clients, _, session, *_) = cimd
    tokens = pair(cimd)
    def refresh():
        try:
            return service.refresh(tokens.refresh_token, value.client_id, resource=RESOURCE)
        except GrantRejected:
            return None
    def disable():
        return clients.set_enabled(session.actor, UUID(client['client_id']), enabled=False, expected_revision=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        renewed, disabled = pool.submit(refresh), pool.submit(disable)
        result = renewed.result()
        assert not disabled.result()['enabled']
    if result:
        with pytest.raises(GrantRejected):
            service.verify(result.access_token, resource=RESOURCE)
    with pytest.raises(GrantRejected):
        service.verify(tokens.access_token, resource=RESOURCE)


def test_unknown_urls_disabled_and_stale_proofs_fail_closed(cimd):
    service, registry, client, value, _, (_, clients, _, session, *_) = cimd
    with pytest.raises(CimdRejected):
        registry.approval('https://unknown.example.test/client.json')
    attestation = proof(cimd)
    registry.sync_policy(False)
    registry.sync_policy(True)
    with pytest.raises(GrantRejected):
        pair(cimd, verification=attestation)
    attestation = proof(cimd)
    registry.approve(session.actor, value, expected_digest=value.digest, scopes=['c0:read', 'c0:write'],
        client_id=UUID(client['client_id']), expected_revision=1)
    with pytest.raises(GrantRejected):
        pair(cimd, verification=attestation)
    with pytest.raises(CimdRejected):
        registry.observe(value, expected_revision=1)


def test_admin_authority_and_total_manual_cimd_client_bound(cimd):
    service, registry, client, value, metadata, (_, clients, _, session, _, app, member_token) = cimd
    with pytest.raises(PermissionDenied):
        service.access.resolve(app.state.auth.oidc.verify_access_token(member_token))
    account = next(row['id'] for row in service.access.list_accounts(session.actor) if row['username'] == 'member')
    service.access.set_role(session.actor, account, Role.READER)
    reader = service.access.resolve(app.state.auth.oidc.verify_access_token(member_token))
    for operation in [lambda: registry.status(reader), lambda: registry.authorize_preview(reader),
                      lambda: registry.approve(reader, value, expected_digest=value.digest)]:
        with pytest.raises(PermissionDenied):
            operation()
    identifiers = []
    try:
        with service.access.database.engine.begin() as connection:
            count = connection.execute(text('SELECT count(*) FROM c0_oauth_clients')).scalar_one()
            for _ in range(64 - count):
                identifier = uuid4()
                identifiers.append(identifier)
                connection.execute(text('''INSERT INTO c0_oauth_clients(id,name,descriptor_hash,redirect_uris,scopes)
                    VALUES (:id,'Capacity fixture',:hash,CAST(:uris AS jsonb),CAST(:scopes AS jsonb))'''),
                    {'id': identifier, 'hash': identifier.hex, 'uris': json.dumps([CALLBACK]),
                     'scopes': json.dumps(['c0:read'])})
        other_url = 'https://client.example.test/' + uuid4().hex
        other = parse_metadata(other_url, json.dumps({'client_id': other_url, 'client_name': 'Over limit',
            'redirect_uris': [CALLBACK], 'token_endpoint_auth_method': 'none'}).encode())
        with pytest.raises(ValueError, match='oauth_client_limit'):
            registry.approve(session.actor, other, expected_digest=other.digest)
        with pytest.raises(ValueError, match='oauth_client_limit'):
            clients.register(session.actor, 'Over manual limit ' + uuid4().hex, [CALLBACK])
    finally:
        with service.access.database.engine.begin() as connection:
            for identifier in identifiers:
                connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id': identifier})


def test_cimd_disable_waits_for_inflight_actor_transaction_then_rejects_capture(cimd):
    from threading import Event
    from time import monotonic
    service, registry, client, value, _, (_, clients, _, session, *_) = cimd
    tokens = pair(cimd)
    captured = service.verify(tokens.access_token, resource=RESOURCE).actor
    entered = Event()
    def disable():
        entered.set()
        return clients.set_enabled(session.actor, UUID(client['client_id']), enabled=False, expected_revision=1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with service.access.database.engine.begin() as connection:
            service.access.checked_actor(connection, captured)
            future = pool.submit(disable)
            assert entered.wait(2)
            deadline = monotonic() + 3
            waiting = False
            while monotonic() < deadline:
                with service.access.database.engine.connect() as observer:
                    waiting = observer.execute(text('''SELECT EXISTS (SELECT 1 FROM pg_locks
                        WHERE locktype='advisory' AND objid=49382 AND NOT granted)''')).scalar_one()
                if waiting:
                    break
            assert waiting and not future.done()
        assert not future.result(timeout=3)['enabled']
    with pytest.raises(PermissionDenied):
        service.access.authorize(captured, Role.READER)


def test_native_policy_applies_without_authentication_and_unchanged_sync_is_noop(cimd):
    from czero_core.cimd import CimdPolicyService
    service, registry, client, value, _, (_, _, _, session, *_) = cimd
    tokens = pair(cimd)
    native = CimdPolicyService(service.access.database)
    assert native.enabled()
    before = registry.status(session.actor)
    native.sync_policy(True)
    assert registry.status(session.actor) == before
    native.sync_policy(False)
    assert not native.enabled()
    native.sync_policy(True)
    with pytest.raises(GrantRejected):
        service.verify(tokens.access_token, resource=RESOURCE)


def test_valid_metadata_change_observed_while_disabled_still_requires_review(cimd):
    service, registry, client, value, metadata, (_, clients, _, session, *_) = cimd
    clients.set_enabled(session.actor, UUID(client['client_id']), enabled=False, expected_revision=1)
    changed = metadata(client_name='Changed while disabled')
    with pytest.raises(CimdRejected):
        registry.observe(changed, expected_revision=2)
    assert registry.status(session.actor)['clients'][0]['review_required']
    clients.set_enabled(session.actor, UUID(client['client_id']), enabled=True, expected_revision=2)
    with pytest.raises(CimdRejected):
        registry.approval(value.client_id)


@pytest.mark.parametrize('operation', ['revoke', 'replay', 'rotation'])
def test_cimd_token_revocation_finishes_after_inflight_actor_transaction(cimd, operation):
    from threading import Event
    from time import monotonic
    service, registry, client, value, _, (_, _, _, session, *_) = cimd
    tokens = pair(cimd)
    replay_token = tokens.refresh_token
    if operation == 'replay':
        tokens = service.refresh(replay_token, value.client_id, resource=RESOURCE)
    captured = service.verify(tokens.access_token, resource=RESOURCE).actor
    entered = Event()
    def change():
        entered.set()
        if operation == 'revoke':
            service.revoke(tokens.access_token, value.client_id, resource=RESOURCE)
        elif operation == 'replay':
            with pytest.raises(GrantRejected):
                service.refresh(replay_token, value.client_id, resource=RESOURCE)
        else:
            service.refresh(tokens.refresh_token, value.client_id, resource=RESOURCE)
        return 'finished'
    with ThreadPoolExecutor(max_workers=1) as pool:
        with service.access.database.engine.begin() as connection:
            service.access.checked_actor(connection, captured)
            future = pool.submit(change)
            assert entered.wait(2)
            deadline, waiting = monotonic() + 3, False
            while monotonic() < deadline and not future.done():
                with service.access.database.engine.connect() as observer:
                    waiting = observer.execute(text('''SELECT EXISTS (SELECT 1 FROM pg_locks
                        WHERE locktype='advisory' AND objid=49382 AND NOT granted)''')).scalar_one()
                if waiting:
                    break
            assert waiting and not future.done()
        assert future.result(timeout=3) == 'finished'
    with pytest.raises(PermissionDenied):
        service.access.authorize(captured, Role.READER)
