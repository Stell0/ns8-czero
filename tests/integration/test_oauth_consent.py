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
from czero_core.oauth_consent import ConsentRejected, OAuthConsentService
from czero_core.oauth_grants import GrantRejected, OAuthGrantService, pkce_challenge
from czero_core.sessions import SessionContext
from test_oauth_grants import grants, CALLBACK, RESOURCE
from test_auth_http import application, PrivateFixture

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def consent(grants):
    service, _, client, *_ = grants
    pending = OAuthConsentService(service)
    yield pending, grants
    with service.access.database.engine.begin() as connection:
        connection.execute(text('DELETE FROM c0_oauth_consent WHERE client_id=:id'), {'id': UUID(client['client_id'])})


def begin(fixture, **overrides):
    service, (_, _, client, *_) = fixture
    verifier = secrets.token_urlsafe(32)
    request = service.begin(client['client_id'], **{'callback': CALLBACK, 'scopes': {'c0:read'},
        'challenge': pkce_challenge(verifier), 'state':'unit-fixture-state', 'resource':RESOURCE, **overrides})
    return PrivateFixture((request, verifier))


def test_browser_binding_one_use_and_atomic_code_creation(consent):
    pending, (grants, _, client, session, *_) = consent
    request, verifier = begin(consent)
    assert request.request not in repr(request) and request.binding not in repr(request)
    for binding in [None, 'bad', secrets.token_urlsafe(32)]:
        with pytest.raises(ConsentRejected):
            pending.view(request.request, binding)
    view = pending.view(request.request, request.binding)
    assert view['client_id'] == client['client_id'] and view['callback'] == CALLBACK
    assert not {'state','challenge','browser_hash','issuer','native_client'} & view.keys()
    result = pending.complete(session, request.request, request.binding, approve=True)
    assert result.code not in repr(result) and result.state not in repr(result)
    assert result.callback == CALLBACK and result.state == 'unit-fixture-state'
    with pytest.raises(ConsentRejected):
        pending.complete(session, request.request, request.binding, approve=True)
    pair = grants.exchange_code(result.code, client['client_id'], callback=CALLBACK, verifier=verifier, resource=RESOURCE)
    assert grants.verify(pair.access_token, resource=RESOURCE).actor == session.actor


def test_denial_consumes_request_without_grant_and_exact_state_is_retained(consent):
    pending, (grants, _, _, session, *_) = consent
    request, _ = begin(consent)
    result = pending.complete(session, request.request, request.binding, approve=False, scopes=set())
    assert result.code is None and result.state == 'unit-fixture-state'
    with pytest.raises(ConsentRejected):
        pending.view(request.request, request.binding)
    with grants.access.database.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM c0_oauth_grants WHERE account_id=:id'),
            {'id': session.actor.user_id}).scalar_one() == 0


def test_failed_role_approval_rolls_back_then_reader_can_narrow_scope(consent):
    pending, (grants, _, client, session, _, app, member_token) = consent
    access = grants.access
    with pytest.raises(PermissionDenied):
        access.resolve(app.state.auth.oidc.verify_access_token(member_token))
    identifier = next(row['id'] for row in access.list_accounts(session.actor) if row['username'] == 'member')
    access.set_role(session.actor, identifier, Role.READER)
    member = access.resolve(app.state.auth.oidc.verify_access_token(member_token))
    reader = SessionContext(member, session.expires_at, 'test-only-csrf')
    request, verifier = begin(consent, scopes={'c0:read', 'c0:write'})
    with pytest.raises(PermissionDenied):
        pending.complete(reader, request.request, request.binding, approve=True)
    assert set(pending.view(request.request, request.binding)['scopes']) == {'c0:read','c0:write'}
    result = pending.complete(reader, request.request, request.binding, approve=True, scopes={'c0:read'})
    pair = grants.exchange_code(result.code, client['client_id'], callback=CALLBACK, verifier=verifier, resource=RESOURCE)
    assert grants.verify(pair.access_token, resource=RESOURCE).scopes == frozenset(('c0:read',))


def test_concurrent_completions_have_exactly_one_code(consent):
    pending, (_, _, _, session, *_) = consent
    request, _ = begin(consent)
    def complete(_):
        try:
            pending.complete(session, request.request, request.binding, approve=True)
            return 'issued'
        except ConsentRejected:
            return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(complete, range(2))) == ['issued','rejected']


def test_expiry_native_context_and_client_epoch_invalidate_pending_requests(consent):
    pending, (grants, clients, client, session, clock, *_) = consent
    request, _ = begin(consent)
    other = OAuthConsentService(OAuthGrantService(grants.access, 'czero901', RESOURCE, now=lambda: clock[0]))
    with pytest.raises(ConsentRejected):
        other.view(request.request, request.binding)
    clients.set_enabled(session.actor, UUID(client['client_id']), enabled=False, expected_revision=1)
    clients.set_enabled(session.actor, UUID(client['client_id']), enabled=True, expected_revision=2)
    with pytest.raises(ConsentRejected):
        pending.view(request.request, request.binding)
    request, _ = begin(consent)
    clock[0] += 300
    with pytest.raises(ConsentRejected):
        pending.complete(session, request.request, request.binding, approve=True)


def test_pending_capacity_and_exact_parameter_validation(consent):
    pending, (_, _, _, _, clock, *_) = consent
    for changes in [{'resource':'https://other.example.test/mcp'}, {'callback': CALLBACK+'/'},
                    {'scopes':{'c0:admin'}}, {'scopes':set()}, {'state':'x'*513},
                    {'state':'\n'}, {'state':'é'}, {'challenge':'x'*42}]:
        with pytest.raises(ConsentRejected):
            begin(consent, **changes)
    for _ in range(32):
        begin(consent)
    with pytest.raises(ConsentRejected):
        begin(consent)
    clock[0] += 300
    request, _ = begin(consent)
    assert pending.view(request.request, request.binding)['scopes'] == ['c0:read']


def test_invalid_or_expired_completion_preserves_pending_request(consent):
    pending, (_, _, _, session, clock, *_) = consent
    request, _ = begin(consent)
    expired = SessionContext(session.actor, datetime.fromtimestamp(clock[0] - 1, timezone.utc), 'test-only-csrf')
    for current, approve, scopes in [(None, True, None), (expired, True, None),
                                     (session, 'true', None), (session, True, set()),
                                     (session, True, {'c0:admin'})]:
        with pytest.raises(ConsentRejected):
            pending.complete(current, request.request, request.binding, approve=approve, scopes=scopes)
        assert pending.view(request.request, request.binding)['scopes'] == ['c0:read']
