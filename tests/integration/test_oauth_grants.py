# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import secrets
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.identity import PermissionDenied, Role
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_grants import GrantRejected, OAuthGrantService, pkce_challenge
from czero_core.sessions import SessionContext
from test_auth_http import application, ORIGIN, PrivateFixture

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
RESOURCE = ORIGIN + '/mcp'
CALLBACK = 'https://client.example.test/callback'


@pytest.fixture
def grants(application):
    app, owner_token, member_token, _, database, _ = application
    access = app.state.auth.access
    owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    clock = [1900000000.0]
    service = OAuthGrantService(access, 'czero900', RESOURCE, now=lambda: clock[0])
    clients = OAuthClientService(access)
    client = clients.register(owner, 'Grant fixture ' + uuid4().hex, [CALLBACK], scopes=list(('c0:read', 'c0:write')))
    session = SessionContext(owner, datetime.fromtimestamp(clock[0] + 600, timezone.utc), 'test-only-csrf')
    yield PrivateFixture((service, clients, client, session, clock, app, member_token))
    with database.engine.begin() as connection:
        connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id': UUID(client['client_id'])})


def issue(service, client, session, *, scopes=frozenset(('c0:read',)), **overrides):
    verifier = secrets.token_urlsafe(32)
    parameters = {'callback': CALLBACK, 'scopes': scopes,
                  'challenge': pkce_challenge(verifier), 'resource': RESOURCE, **overrides}
    return PrivateFixture((service.issue_code(session, client['client_id'], **parameters), verifier))


def redeem(service, client, values, **overrides):
    return service.exchange_code(values[0], client['client_id'], **{
        'callback': CALLBACK, 'verifier': values[1], 'resource': RESOURCE, **overrides})


def test_codes_tokens_are_hash_only_exactly_bound_and_single_use(grants):
    service, _, client, session, _, _, _ = grants
    values = issue(service, client, session)
    for changes in [{'resource': ORIGIN + '/other'}, {'callback': CALLBACK + '/other'}, {'verifier': 'x' * 43}]:
        with pytest.raises(GrantRejected, match='^invalid_grant$'):
            redeem(service, client, values, **changes)
    pair = redeem(service, client, values)
    assert pair.expires_in == 300 and pair.scopes == frozenset(('c0:read',))
    assert pair.access_token not in repr(pair) and pair.refresh_token not in repr(pair)
    verified = service.verify(pair.access_token, resource=RESOURCE)
    assert verified.actor == session.actor and verified.client_id == client['client_id']
    assert verified.issuer == service.access.issuer and verified.resource == RESOURCE
    with pytest.raises(GrantRejected):
        redeem(service, client, values)
    with pytest.raises(GrantRejected):
        service.verify(pair.access_token, resource=ORIGIN + '/other')
    with service.access.database.engine.connect() as connection:
        # Only count/category diagnostics; never materialize raw token rows.
        assert connection.execute(text('''SELECT count(*) FROM c0_oauth_tokens t
            JOIN c0_oauth_grants g ON g.id=t.grant_id WHERE g.account_id=:id
            AND length(t.hash)=64'''), {'id': session.actor.user_id}).scalar_one() == 2
        columns = connection.execute(text("""SELECT column_name FROM information_schema.columns
            WHERE table_name IN ('c0_oauth_codes','c0_oauth_tokens')""")).scalars().all()
        assert not {'code', 'token', 'access_token', 'refresh_token'} & set(columns)


def test_concurrent_exchange_has_exactly_one_winner(grants):
    service, _, client, session, _, _, _ = grants
    values = issue(service, client, session)
    def exchange(_):
        try:
            redeem(service, client, values)
            return 'issued'
        except GrantRejected:
            return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(exchange, range(2))) == ['issued', 'rejected']


def test_rotation_narrows_scopes_and_replay_commits_family_revocation(grants):
    service, _, client, session, _, _, _ = grants
    pair = redeem(service, client, issue(service, client, session, scopes=frozenset(('c0:read', 'c0:write'))))
    with pytest.raises(GrantRejected):
        service.refresh(pair.refresh_token, client['client_id'], resource=ORIGIN + '/other')
    second = service.refresh(pair.refresh_token, client['client_id'], resource=RESOURCE, scopes={'c0:read'})
    assert second.scopes == frozenset(('c0:read',))
    with pytest.raises(GrantRejected):
        service.verify(pair.access_token, resource=RESOURCE)
    with pytest.raises(GrantRejected):
        service.refresh(second.refresh_token, client['client_id'], resource=RESOURCE, scopes={'c0:read', 'c0:write'})
    assert service.verify(second.access_token, resource=RESOURCE).scopes == frozenset(('c0:read',))
    with pytest.raises(GrantRejected):
        service.refresh(pair.refresh_token, client['client_id'], resource=RESOURCE)
    for value in [pair.access_token, second.access_token]:
        with pytest.raises(GrantRejected):
            service.verify(value, resource=RESOURCE)
    with pytest.raises(GrantRejected):
        service.refresh(second.refresh_token, client['client_id'], resource=RESOURCE)


def test_expiry_native_identity_client_epoch_and_explicit_revocation(grants):
    service, clients, client, session, clock, _, _ = grants
    values = issue(service, client, session)
    clock[0] += 300
    with pytest.raises(GrantRejected):
        redeem(service, client, values)
    pair = redeem(service, client, issue(service, client, session))
    other = OAuthGrantService(service.access, 'czero901', RESOURCE, now=lambda: clock[0])
    with pytest.raises(GrantRejected):
        other.verify(pair.access_token, resource=RESOURCE)
    clients.set_enabled(session.actor, UUID(client['client_id']), enabled=False, expected_revision=1)
    clients.set_enabled(session.actor, UUID(client['client_id']), enabled=True, expected_revision=2)
    with pytest.raises(GrantRejected):
        service.verify(pair.access_token, resource=RESOURCE)
    pair = redeem(service, client, issue(service, client, session))
    service.revoke(pair.refresh_token, client['client_id'], resource=RESOURCE)
    service.revoke(pair.refresh_token, client['client_id'], resource=RESOURCE)
    service.revoke('not-a-token', client['client_id'], resource=RESOURCE)
    with pytest.raises(GrantRejected):
        service.verify(pair.access_token, resource=RESOURCE)
    pair = redeem(service, client, issue(service, client, session))
    clock[0] += 300
    with pytest.raises(GrantRejected):
        service.verify(pair.access_token, resource=RESOURCE)
    with pytest.raises(GrantRejected):
        service.refresh(pair.refresh_token, client['client_id'], resource=RESOURCE)
    with pytest.raises(GrantRejected):
        issue(service, client, session)


def test_membership_changes_permanently_revoke_grants_and_recheck_issue_roles(grants):
    service, _, client, session, _, app, member_token = grants
    access = service.access
    with pytest.raises(PermissionDenied):
        access.resolve(app.state.auth.oidc.verify_access_token(member_token))
    member_id = next(row['id'] for row in access.list_accounts(session.actor) if row['username'] == 'member')
    access.set_role(session.actor, member_id, Role.EDITOR)
    actor = access.resolve(app.state.auth.oidc.verify_access_token(member_token))
    member_session = SessionContext(actor, session.expires_at, 'test-only-csrf')
    pair = redeem(service, client, issue(service, client, member_session, scopes={'c0:read', 'c0:write'}))
    access.set_role(session.actor, member_id, None)
    access.set_role(session.actor, member_id, Role.EDITOR)
    with pytest.raises(GrantRejected):
        service.verify(pair.access_token, resource=RESOURCE)
    access.set_role(session.actor, member_id, Role.READER)
    with pytest.raises(PermissionDenied):
        issue(service, client, member_session, scopes={'c0:write'})
    with pytest.raises(GrantRejected):
        issue(service, client, session, scopes={'c0:admin'})


def test_pending_grants_are_bounded_and_expired_rows_are_collected(grants):
    service, _, client, session, clock, _, _ = grants
    for _ in range(32):
        issue(service, client, session)
    with pytest.raises(GrantRejected):
        issue(service, client, session)
    clock[0] += 300
    # Unredeemed expired codes must not exhaust a user's entire grant quota.
    issue(service, client, session)
    with service.access.database.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM c0_oauth_grants WHERE account_id=:id'),
            {'id': session.actor.user_id}).scalar_one() == 1
    clock[0] += 300
    renewed = SessionContext(session.actor, datetime.fromtimestamp(clock[0] + 600, timezone.utc), 'test-only-csrf')
    issue(service, client, renewed)
    with service.access.database.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM c0_oauth_grants WHERE account_id=:id'),
            {'id': session.actor.user_id}).scalar_one() == 1


def test_invalid_client_redirect_scope_and_second_client_cannot_use_grant(grants):
    service, clients, client, session, _, _, _ = grants
    for overrides in [{'callback': CALLBACK + '/other'}, {'scopes': {'c0:admin'}},
                      {'scopes': set()}, {'scopes': ['c0:read']}, {'scopes': {'other'}},
                      {'challenge': 'x' * 42}, {'resource': ORIGIN + '/other'}]:
        with pytest.raises(GrantRejected):
            issue(service, client, session, **overrides)
    second = clients.register(session.actor, 'Other grant fixture ' + uuid4().hex, [CALLBACK])
    try:
        values = issue(service, client, session)
        with pytest.raises(GrantRejected):
            redeem(service, second, values)
        pair = redeem(service, client, values)
        with pytest.raises(GrantRejected):
            service.refresh(pair.refresh_token, second['client_id'], resource=RESOURCE)
        with pytest.raises(GrantRejected):
            service.revoke(pair.refresh_token, second['client_id'], resource=RESOURCE)
        assert service.verify(pair.access_token, resource=RESOURCE).client_id == client['client_id']
    finally:
        with service.access.database.engine.begin() as connection:
            connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id': UUID(second['client_id'])})


def test_revoke_issue_race_cannot_leave_a_live_delegation(grants):
    service, _, client, session, _, app, member_token = grants
    access = service.access
    with pytest.raises(PermissionDenied):
        access.resolve(app.state.auth.oidc.verify_access_token(member_token))
    member_id = next(row['id'] for row in access.list_accounts(session.actor) if row['username'] == 'member')
    access.set_role(session.actor, member_id, Role.EDITOR)
    actor = access.resolve(app.state.auth.oidc.verify_access_token(member_token))
    member_session = SessionContext(actor, session.expires_at, 'test-only-csrf')
    def create():
        try:
            issue(service, client, member_session)
        except PermissionDenied:
            pass
    with ThreadPoolExecutor(max_workers=2) as pool:
        creation = pool.submit(create)
        revocation = pool.submit(access.set_role, session.actor, member_id, None)
        creation.result()
        revocation.result()
    with access.database.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM c0_oauth_grants WHERE account_id=:id'),
            {'id': member_id}).scalar_one() == 0


def test_refresh_rotation_work_is_bounded_and_limit_revokes_family(grants):
    service, _, client, session, _, _, _ = grants
    pair = redeem(service, client, issue(service, client, session))
    for _ in range(127):
        pair = service.refresh(pair.refresh_token, client['client_id'], resource=RESOURCE)
    with pytest.raises(GrantRejected):
        service.refresh(pair.refresh_token, client['client_id'], resource=RESOURCE)
    with pytest.raises(GrantRejected):
        service.verify(pair.access_token, resource=RESOURCE)
