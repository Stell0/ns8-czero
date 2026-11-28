# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import PermissionDenied, Role, VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.sessions import LoginStateRejected, SessionRejected, SessionService

pytestmark = pytest.mark.skipif(not os.getenv("CZERO_TEST_DATABASE_URL"), reason="isolated PostgreSQL URL required")


@pytest.fixture
def sessions():
    database = Database(os.environ["CZERO_TEST_DATABASE_URL"])
    migrate_database(database)
    issuer = "https://idp.example.test/realms/" + str(uuid4())
    key = uuid4()
    access = AccessService(database, issuer, key)
    current = [time.time()]
    service = SessionService(access, "czero1", now=lambda: current[0])
    identity = VerifiedIdentity(issuer, "subject", str(key), "owner", "Owner", current[0] + 300)
    yield service, identity, current
    with database.engine.begin() as connection:
        connection.execute(text("DELETE FROM c0_login_states WHERE issuer = :issuer"), {"issuer": issuer})
        connection.execute(text("DELETE FROM c0_accounts WHERE issuer = :issuer"), {"issuer": issuer})
    database.close()


def test_login_state_is_browser_bound_and_consumed_once(sessions):
    service, _, _ = sessions
    pending = service.begin_login()
    assert pending.state not in repr(pending)
    assert pending.code_verifier not in repr(pending)
    with pytest.raises(LoginStateRejected):
        service.consume_login(pending.state, "wrong-binding")
    recovered = service.consume_login(pending.state, pending.browser_binding)
    assert recovered.nonce == pending.nonce
    assert recovered.code_verifier == pending.code_verifier
    with pytest.raises(LoginStateRejected):
        service.consume_login(pending.state, pending.browser_binding)


def test_expired_or_foreign_client_login_state_is_rejected(sessions):
    service, _, current = sessions
    pending = service.begin_login()
    foreign = SessionService(service.access, "czero2", now=lambda: current[0])
    with pytest.raises(LoginStateRejected):
        foreign.consume_login(pending.state, pending.browser_binding)
    current[0] += 301
    with pytest.raises(LoginStateRejected):
        service.consume_login(pending.state, pending.browser_binding)


def test_simultaneous_callbacks_can_consume_state_only_once(sessions):
    service, _, _ = sessions
    pending = service.begin_login()
    def consume():
        try:
            service.consume_login(pending.state, pending.browser_binding)
            return True
        except LoginStateRejected:
            return False
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: consume(), range(2)))
    assert sorted(results) == [False, True]


def test_session_is_opaque_expiring_and_logout_revokes_it(sessions):
    service, identity, current = sessions
    cookie = service.create(identity)
    context = service.get(cookie)
    assert context.actor.is_owner
    assert cookie not in repr(context)
    assert context.csrf_token not in repr(context)
    with service.access.database.engine.connect() as connection:
        values = connection.execute(text("SELECT token_hash FROM c0_sessions WHERE issuer = :issuer"),
                                    {"issuer": identity.issuer}).scalars().all()
    assert values and cookie not in values
    service.destroy(cookie)
    with pytest.raises(SessionRejected):
        service.get(cookie)
    cookie = service.create(identity)
    current[0] = identity.expires_at
    with pytest.raises(SessionRejected):
        service.get(cookie)


@pytest.mark.parametrize("supplied", [None, "", "wrong", "non-ascii-\u00e9"])
def test_cookie_writes_require_the_session_csrf_value(sessions, supplied):
    service, identity, _ = sessions
    context = service.get(service.create(identity))
    service.check_csrf(context, context.csrf_token)
    with pytest.raises(PermissionDenied):
        service.check_csrf(context, supplied)


def test_session_rechecks_member_roles_and_client_context(sessions):
    service, identity, current = sessions
    owner = service.access.resolve(identity)
    member_identity = VerifiedIdentity(identity.issuer, "member", str(uuid4()), "member", "Member", current[0] + 300)
    with pytest.raises(PermissionDenied):
        service.create(member_identity)
    account = next(row for row in service.access.list_accounts(owner) if row["username"] == "member")
    service.access.set_role(owner, account["id"], Role.EDITOR)
    cookie = service.create(member_identity)
    assert service.get(cookie).actor.role is Role.EDITOR
    foreign = SessionService(service.access, "czero2", now=lambda: current[0])
    with pytest.raises(SessionRejected):
        foreign.get(cookie)
    service.access.set_role(owner, account["id"], Role.READER)
    assert service.get(cookie).actor.role is Role.READER
    service.access.set_role(owner, account["id"], None)
    with pytest.raises(PermissionDenied):
        service.get(cookie)


@pytest.mark.parametrize('interruption', ['logout','replacement','deadline'])
def test_late_provider_response_cannot_publish_session(sessions, interruption):
    service, identity, clock = sessions
    old = service.create(identity)
    context = service.get(old)
    owner = 'b' * 43
    pending = service.begin_login(prior_cookie=old, return_target='account')
    service.bind_browser_login(pending, owner, old)
    attempt = service.claim_browser_login(pending.state, pending.browser_binding, owner, old)
    assert attempt.return_target == 'account'
    if interruption == 'logout':
        service.logout(old, context.csrf_token, owner=owner)
    elif interruption == 'replacement':
        newer = service.begin_login(prior_cookie=old)
        service.bind_browser_login(newer, owner, old)
    else:
        # Expire the login transaction independently of the test identity.
        with service.access.database.engine.begin() as conn:
            conn.execute(text('UPDATE c0_login_states SET expires_at=now() WHERE issuer=:issuer'),
                         {'issuer':identity.issuer})
        clock[0] += 1
    with pytest.raises(LoginStateRejected):
        service.create(identity, attempt=attempt)
    with service.access.database.engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM c0_sessions WHERE issuer=:issuer'),
                            {'issuer':identity.issuer}).scalar_one() == (0 if interruption == 'logout' else 1)


def test_lost_fence_or_draft_never_admits_new_account(sessions):
    from dataclasses import replace
    service, identity, _ = sessions
    service.access.admit_readers = True
    owner = 'x' * 43
    pending = service.begin_login()
    service.bind_browser_login(pending, owner, None)
    claim = service.claim_browser_login(pending.state, pending.browser_binding, owner, None)
    replacement = service.begin_login()
    service.bind_browser_login(replacement, owner, None)
    stranger = replace(identity, account_key=str(uuid4()), subject='new-person', username='new-person')
    touched = []
    def unavailable(connection, account_id):
        touched.append(account_id)
        return False
    with pytest.raises(LoginStateRejected):
        service.create(stranger, attempt=claim, bind_flow=unavailable)
    assert not touched
    claim = service.claim_browser_login(replacement.state, replacement.browser_binding, owner, None)
    with pytest.raises(LoginStateRejected):
        service.create(stranger, attempt=claim, bind_flow=unavailable)
    assert len(touched) == 1
    with service.access.database.engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM c0_accounts WHERE issuer=:issuer'),
                            {'issuer': identity.issuer}).scalar_one() == 0


@pytest.mark.parametrize('after_publication', [299, 300])
def test_logout_receipt_deadline_starts_at_publication(sessions, after_publication):
    from dataclasses import replace
    service, identity, clock = sessions
    prior = service.create(identity)
    csrf = service.get(prior).csrf_token
    owner = 'b' * 43
    pending = service.begin_login(prior_cookie=prior, return_target='account')
    proof = pending.browser_binding
    service.bind_browser_login(pending, owner, prior)
    login = service.claim_browser_login(pending.state, proof, owner, prior)
    clock[0] += 299
    successor = service.create(replace(identity, expires_at=clock[0] + 900), attempt=login)

    clock[0] += after_publication
    service.begin_login()  # Run normal expired-state cleanup.
    assert service.recovery_target(pending.state, proof) is None
    with pytest.raises(LoginStateRejected):
        service.claim_browser_login(pending.state, proof, owner, prior)
    if after_publication == 299:
        service.logout(prior, csrf)
        with pytest.raises(SessionRejected):
            service.get(successor)
    else:
        with pytest.raises(SessionRejected):
            service.logout(prior, csrf)
        assert service.get(successor).actor.is_owner
