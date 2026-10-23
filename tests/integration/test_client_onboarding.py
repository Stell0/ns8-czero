# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
import secrets
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.client_onboarding import ClientOnboardingService, OnboardingRejected
from czero_core.cimd import CimdRejected
from czero_core.identity import PermissionDenied, Role
from czero_core.oauth_consent import OAuthConsentService
from czero_core.oauth_grants import pkce_challenge
from test_cimd import cimd, proof
from test_oauth_grants import grants, CALLBACK, RESOURCE
from test_auth_http import application

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def onboarding(cimd):
    service = ClientOnboardingService(cimd[0])
    yield service, cimd
    with service.grants.access.database.engine.begin() as connection:
        connection.execute(text('DELETE FROM c0_client_onboarding WHERE issuer=:issuer'),
                           {'issuer': service.grants.access.issuer})


def parameters(fixture, **changes):
    _, (_, _, _, metadata, *_) = fixture
    verifier = secrets.token_urlsafe(32)
    return {'client_id': metadata.client_id, 'redirect_uri': CALLBACK, 'response_type': 'code',
            'code_challenge_method': 'S256', 'code_challenge': pkce_challenge(verifier),
            'state': 'private-onboarding-state', 'scope': 'c0:read c0:write', 'resource': RESOURCE, **changes}, verifier


def test_unknown_client_can_request_review_but_receives_no_authority(onboarding):
    service, fixture = onboarding
    _, registry, client, _, _, (_, _, _, session, *_) = fixture
    raw, _ = parameters(onboarding, client_id='https://new.example.test/client.json')
    pending = service.begin(raw)
    assert pending.request not in repr(pending) and pending.binding not in repr(pending)
    assert service.requests(session.actor) == []
    view = service.submit(session, pending.request, pending.binding)
    assert not view['approved'] and view['allowed_scopes'] == []
    assert not {'state', 'code_challenge', 'hash', 'browser_hash', 'issuer', 'native_client'} & view.keys()
    queue = service.requests(session.actor)
    assert len(queue) == 1 and queue[0]['metadata_url'] == raw['client_id']
    assert 'private-onboarding-state' not in json.dumps(queue, default=str)
    with pytest.raises(OnboardingRejected):
        service.complete(session, pending.request, pending.binding, scopes={'c0:read'}, verification=proof(fixture))
    assert service.view(session, pending.request, pending.binding) == view
    with service.grants.access.database.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM c0_oauth_grants WHERE account_id=:id'),
                                  {'id': session.actor.user_id}).scalar_one() == 0


def test_handoff_is_atomic_one_use_and_explicitly_narrows_before_existing_consent(onboarding):
    service, fixture = onboarding
    *_, (_, _, _, session, *__) = fixture
    raw, verifier = parameters(onboarding)
    pending = service.begin(raw)
    service.submit(session, pending.request, pending.binding)
    consent = service.complete(session, pending.request, pending.binding, scopes={'c0:read'}, verification=proof(fixture))
    with pytest.raises(OnboardingRejected):
        service.view(session, pending.request, pending.binding)
    consent_service = OAuthConsentService(service.grants)
    view = consent_service.view(consent.request, consent.binding)
    assert view['scopes'] == ['c0:read']
    result = consent_service.complete(session, consent.request, consent.binding, approve=True, verification=proof(fixture))
    assert result.state == raw['state']
    pair = service.grants.exchange_code(result.code, raw['client_id'], callback=CALLBACK, verifier=verifier, resource=RESOURCE)
    assert service.grants.verify(pair.access_token, resource=RESOURCE).scopes == frozenset({'c0:read'})


def test_concurrent_handoff_has_one_winner(onboarding):
    service, fixture = onboarding
    session = fixture[-1][3]
    pending = service.begin(parameters(onboarding)[0])
    service.submit(session, pending.request, pending.binding)
    verification = proof(fixture)
    def complete(_):
        try:
            service.complete(session, pending.request, pending.binding, scopes={'c0:read'}, verification=verification)
            return True
        except OnboardingRejected: return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(complete, range(2))) == [False, True]


@pytest.mark.parametrize('changes', [
    {'client_id': 'http://example.test/client.json'}, {'client_id': 'https://127.0.0.1/client.json'},
    {'redirect_uri': 'https://example.test/callback?token=x'}, {'code_challenge': 'bad'},
    {'code_challenge_method': 'plain'}, {'response_type': 'token'}, {'resource': RESOURCE + '/wrong'},
    {'scope': 'c0:read c0:read'}, {'scope': 'unapproved'}, {'state': '\nunsafe'},
    {'state': 'x' * 513}, {'client_secret': 'never-accepted'}, {'optional_unknown': 'not-normalized'},
])
def test_malformed_requests_are_rejected_before_storage(onboarding, changes):
    service, fixture = onboarding
    with pytest.raises(OnboardingRejected): service.begin(parameters(onboarding, **changes)[0])
    assert service.requests(fixture[-1][3].actor) == []


def test_browser_instance_expiry_and_policy_revision_bindings(onboarding):
    service, fixture = onboarding
    grants, registry, *_, (_, _, _, session, clock, *__) = fixture
    pending = service.begin(parameters(onboarding)[0])
    for binding in [None, secrets.token_urlsafe(32), 'bad']:
        with pytest.raises(OnboardingRejected): service.available(pending.request, binding)
    other_native = ClientOnboardingService(type(grants)(grants.access, 'another-native', RESOURCE, now=grants._now))
    with pytest.raises(OnboardingRejected): other_native.available(pending.request, pending.binding)
    registry.sync_policy(False)
    with pytest.raises(CimdRejected): service.begin(parameters(onboarding)[0])
    registry.sync_policy(True)
    with pytest.raises(OnboardingRejected): service.available(pending.request, pending.binding)
    pending = service.begin(parameters(onboarding)[0])
    clock[0] += 301
    with pytest.raises(OnboardingRejected): service.available(pending.request, pending.binding)


def test_queue_is_admin_only_and_submitted_identity_is_pinned(onboarding):
    service, fixture = onboarding
    grants = service.grants
    session = fixture[-1][3]
    app, member_token = fixture[-1][-2:]
    identity = app.state.auth.oidc.verify_access_token(member_token)
    with pytest.raises(PermissionDenied): grants.access.resolve(identity)
    account = next(a for a in grants.access.list_accounts(session.actor) if a['username'] == 'member')
    grants.access.set_role(session.actor, account['id'], Role.READER)
    reader = grants.access.resolve(identity)
    reader_session = replace(session, actor=reader)
    pending = service.begin(parameters(onboarding)[0])
    service.submit(reader_session, pending.request, pending.binding)
    with pytest.raises(PermissionDenied): service.requests(reader)
    with pytest.raises(OnboardingRejected): service.view(session, pending.request, pending.binding)
    assert len(service.requests(session.actor)) == 1
    grants.access.set_role(session.actor, reader.user_id, None)
    with pytest.raises(PermissionDenied): service.view(reader_session, pending.request, pending.binding)


def test_failed_metadata_or_scope_check_does_not_consume_request(onboarding):
    service, fixture = onboarding
    session = fixture[-1][3]
    pending = service.begin(parameters(onboarding)[0])
    service.submit(session, pending.request, pending.binding)
    for scopes, verification in [({'c0:admin'}, proof(fixture)), ({'c0:read'}, None), (set(), proof(fixture))]:
        with pytest.raises(OnboardingRejected):
            service.complete(session, pending.request, pending.binding, scopes=scopes, verification=verification)
        assert service.view(session, pending.request, pending.binding)['approved']


def test_per_client_storage_limit_is_bounded(onboarding):
    service, _ = onboarding
    raw, _ = parameters(onboarding)
    for _ in range(32): service.begin(raw)
    with pytest.raises(OnboardingRejected): service.begin(raw)
