# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Controlled-clock native lifecycle on an isolated real PostgreSQL database."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
import time
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.renewal import NativeAuthorityService, RenewalRejected, RenewalResult, RenewalUnavailable, SessionPolicy
from czero_core.sessions import SessionService, SessionRejected

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL URL required')


@pytest.fixture
def renewable():
    db = Database(os.environ['CZERO_TEST_DATABASE_URL'])
    migrate_database(db)
    current = [time.time()]
    issuer = 'https://idp.example.test/' + str(uuid4())
    key = uuid4()
    access = AccessService(db, issuer, key)
    identity = VerifiedIdentity(issuer, 'subject', str(key), 'owner', 'Owner', current[0] + 300)
    calls, failure = [], [None]
    def check(credential):
        if failure[0] is not None:
            raise failure[0]
        calls.append(credential)
        return RenewalResult(replace(identity, expires_at=current[0] + 300), 'rotation-' + str(len(calls)))
    authority = NativeAuthorityService(access, 'native1', 's' * 32, check,
        policy=SessionPolicy(3600, 600), now=lambda: current[0])
    sessions = SessionService(access, 'native1', now=lambda: current[0], authority=authority)
    yield sessions, authority, identity, current, calls, failure
    with db.engine.begin() as c:
        c.execute(text('DELETE FROM c0_oauth_clients WHERE name=:name'), {'name':'Renewal '+identity.account_key})
        c.execute(text('DELETE FROM c0_sessions WHERE issuer=:issuer'), {'issuer': issuer})
        c.execute(text('DELETE FROM c0_accounts WHERE issuer=:issuer'), {'issuer': issuer})
    db.close()


def login(fixture):
    sessions, _, identity, *_ = fixture
    return sessions.create(identity, renewal=RenewalResult(identity, 'initial-private-refresh'))


def test_renews_beyond_original_expiry_and_keeps_absolute_bound(renewable):
    sessions, authority, identity, current, calls, _ = renewable
    cookie = login(renewable)
    context = sessions.get(cookie)
    absolute = context.expires_at
    for _ in range(8):
        current[0] += 400
        assert sessions.get(cookie).expires_at == absolute
    assert current[0] > identity.expires_at + 300
    assert calls[:2] == ['initial-private-refresh', 'rotation-1']
    current[0] = absolute.timestamp()
    with pytest.raises(SessionRejected):
        sessions.get(cookie)


def test_idle_deadline_cannot_be_revived(renewable):
    sessions, _, _, current, calls, _ = renewable
    cookie = login(renewable)
    current[0] += 600
    with pytest.raises((SessionRejected, RenewalRejected)):
        sessions.get(cookie)
    assert calls == []


def test_provider_outage_denies_without_extending_and_recovers_before_idle(renewable):
    sessions, _, _, current, calls, failure = renewable
    cookie = login(renewable)
    current[0] += 301
    failure[0] = RenewalUnavailable()
    with pytest.raises(RenewalUnavailable):
        sessions.get(cookie)
    failure[0] = None
    current[0] += 30
    assert sessions.get(cookie).actor.is_owner
    assert calls == ['initial-private-refresh']


def test_confirmed_provider_rejection_is_durable_and_masks_credentials(renewable):
    sessions, authority, _, _, calls, failure = renewable
    cookie = login(renewable)
    context = sessions.get(cookie)
    failure[0] = RenewalRejected()
    with pytest.raises(RenewalRejected):
        sessions.get(cookie)
    failure[0] = None
    with pytest.raises(RenewalRejected):
        sessions.get(cookie)
    with authority.access.database.engine.connect() as c:
        row = c.execute(text('SELECT revoked,credential FROM c0_native_authority WHERE id=:id'),
                        {'id': context.native_authority_id}).one()
    assert row == (True, None)
    assert len(calls) == 1


def test_parallel_requests_serialize_rotated_native_credentials(renewable):
    sessions, _, _, _, calls, _ = renewable
    cookie = login(renewable)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: sessions.get(cookie), range(4)))
    assert all(r.actor.is_owner for r in results)
    assert calls == ['initial-private-refresh', 'rotation-1', 'rotation-2', 'rotation-3']


def test_ciphertext_is_context_bound_and_survives_process_restart(renewable):
    sessions, authority, identity, current, _, _ = renewable
    cookie = login(renewable)
    context = sessions.get(cookie)
    with authority.access.database.engine.connect() as c:
        encrypted = c.execute(text('SELECT credential FROM c0_native_authority WHERE id=:id'),
                              {'id': context.native_authority_id}).scalar_one()
    assert 'rotation-' not in encrypted and 'initial-private-refresh' not in encrypted
    assert 'initial-private-refresh' not in repr(RenewalResult(identity, 'initial-private-refresh'))
    restarted = NativeAuthorityService(authority.access, 'native1', 's'*32, authority.check,
                                     policy=authority.policy, now=lambda: current[0])
    restored = SessionService(authority.access, 'native1', authority=restarted, now=lambda: current[0])
    assert restored.get(cookie).actor.is_owner
    changed = NativeAuthorityService(authority.access, 'native1', 't'*32, authority.check,
                                    policy=authority.policy, now=lambda: current[0])
    with pytest.raises(RenewalRejected):
        changed.authenticate(context.native_authority_id)
    with pytest.raises(RenewalRejected):
        restored.get(cookie)


def test_swapped_identity_is_never_adopted(renewable):
    sessions, authority, identity, _, _, _ = renewable
    cookie = login(renewable)
    authority.check = lambda _: RenewalResult(replace(identity, subject='different'), 'private')
    with pytest.raises(RenewalRejected):
        sessions.get(cookie)
    authority.check = lambda _: RenewalResult(identity, 'private')
    with pytest.raises(RenewalRejected):
        sessions.get(cookie)


def test_legacy_sessions_keep_native_expiry_and_logout_revokes_renewal(renewable):
    sessions, authority, identity, current, calls, _ = renewable
    legacy = sessions.create(identity)
    cookie = login(renewable)
    context = sessions.get(cookie)
    sessions.destroy(cookie)
    with pytest.raises(SessionRejected):
        sessions.get(cookie)
    with authority.access.database.engine.connect() as c:
        with pytest.raises(RenewalRejected):
            authority.peek(c, context.native_authority_id)
    current[0] = identity.expires_at
    with pytest.raises(SessionRejected):
        sessions.get(legacy)


@pytest.mark.parametrize('absolute,idle', [(True, 60), (60, True), (59, 59), (86401, 60), (60, 61)])
def test_invalid_policy_is_rejected(absolute, idle):
    with pytest.raises(ValueError, match='invalid_session_policy'):
        SessionPolicy(absolute, idle)


def delegated(fixture, *, scopes=None):
    from czero_core.oauth_clients import OAuthClientService
    from czero_core.oauth_grants import OAuthGrantService, pkce_challenge
    sessions, authority, _, clock, *_ = fixture
    cookie = login(fixture)
    context = sessions.get(cookie)
    resource, callback = 'https://c0.example.test/mcp', 'https://client.example.test/callback'
    clients = OAuthClientService(sessions.access)
    client = clients.register(context.actor, 'Renewal '+str(authority.access.owner_account_key), [callback], scopes=['c0:read','c0:write'])
    grants = OAuthGrantService(sessions.access, 'native1', resource, authority=authority, now=lambda: clock[0])
    verifier = 'v'*43
    code = grants.issue_code(context, client['client_id'], callback=callback, scopes=scopes or {'c0:read','c0:write'},
                             challenge=pkce_challenge(verifier), resource=resource)
    pair = grants.exchange_code(code, client['client_id'], callback=callback, verifier=verifier, resource=resource)
    return grants, clients, client, pair, cookie, context


def test_crash_marker_requires_fresh_login_without_replaying_native_credential(renewable):
    sessions, authority, _, _, calls, _ = renewable
    cookie = login(renewable)
    context = sessions.get(cookie)
    original = authority.check
    def interrupted(_):
        raise RuntimeError('simulated process interruption')
    authority.check = interrupted
    with pytest.raises(RuntimeError, match='simulated process interruption'):
        sessions.get(cookie)
    authority.check = original
    with authority.access.database.engine.connect() as c:
        assert c.execute(text('SELECT checking FROM c0_native_authority WHERE id=:id'),
                         {'id':context.native_authority_id}).scalar_one()
    with pytest.raises(RenewalRejected):
        sessions.get(cookie)
    assert calls == ['initial-private-refresh']
    with authority.access.database.engine.connect() as c:
        assert c.execute(text('SELECT revoked,credential,checking FROM c0_native_authority WHERE id=:id'),
                         {'id':context.native_authority_id}).one() == (True,None,False)


def test_captured_browser_actor_is_rechecked_after_logout(renewable):
    from czero_core.identity import PermissionDenied
    sessions, _, _, _, calls, _ = renewable
    cookie = login(renewable)
    context = sessions.get(cookie)
    assert sessions.access.profile(context.actor)['is_owner']
    sessions.logout(cookie, context.csrf_token)
    with pytest.raises(PermissionDenied):
        sessions.access.profile(context.actor)
    from czero_core.wiki import WikiService
    with pytest.raises(PermissionDenied):
        WikiService(sessions.access.database,sessions.access).create_page(
            context.actor,'denied-after-logout','Denied','Never written',idempotency_key='denied')
    assert calls == ['initial-private-refresh']


def test_logout_completes_while_provider_check_is_in_flight(renewable):
    from threading import Event
    sessions, authority, identity, _, _, _ = renewable
    cookie = login(renewable)
    context = sessions.get(cookie)
    started, release = Event(), Event()
    def check(_):
        started.set()
        assert release.wait(5)
        return RenewalResult(identity, 'late-rotated-private-credential')
    authority.check = check
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(sessions.get,cookie)
        try:
            assert started.wait(2)
            pool.submit(sessions.logout,cookie,context.csrf_token).result(timeout=2)
        finally:
            release.set()
        with pytest.raises(RenewalRejected):pending.result(timeout=2)
    with pytest.raises(SessionRejected):sessions.get(cookie)


def test_outage_invalidates_captured_proof_without_extending_and_can_recover(renewable):
    from czero_core.identity import PermissionDenied
    sessions, _, _, clock, _, failure = renewable
    cookie = login(renewable)
    context = sessions.get(cookie)
    clock[0] += 10
    failure[0] = RenewalUnavailable()
    with pytest.raises(RenewalUnavailable):sessions.get(cookie)
    with pytest.raises(PermissionDenied):sessions.access.profile(context.actor)
    failure[0] = None
    clock[0] += 1
    assert sessions.get(cookie).actor.is_owner


def test_delegated_refresh_beyond_native_expiry_narrows_and_replay_revokes_during_outage(renewable):
    from czero_core.oauth_grants import GrantRejected
    grants, _, client, first, _, _ = delegated(renewable)
    _, _, identity, clock, calls, failure = renewable
    clock[0] = identity.expires_at + 1
    with pytest.raises(GrantRejected):grants.verify(first.access_token,resource=grants.resource)
    second = grants.refresh(first.refresh_token,client['client_id'],resource=grants.resource,scopes={'c0:read'})
    assert second.scopes == frozenset({'c0:read'}) and 1 <= second.expires_in <= 300
    assert grants.verify(second.access_token,resource=grants.resource).actor.is_owner
    with pytest.raises(GrantRejected):
        grants.refresh(second.refresh_token,client['client_id'],resource=grants.resource,scopes={'c0:read','c0:write'})
    before = len(calls)
    failure[0] = RenewalUnavailable()
    with pytest.raises(GrantRejected):grants._refresh_token(first.refresh_token,client['client_id'])
    with pytest.raises(GrantRejected):grants.verify(second.access_token,resource=grants.resource)
    assert len(calls)==before


def test_concurrent_delegated_refresh_has_one_winner_and_replay_revokes_family(renewable):
    from czero_core.oauth_grants import GrantRejected
    grants, _, client, pair, _, _ = delegated(renewable)
    def rotate(_):
        try:return grants.refresh(pair.refresh_token,client['client_id'],resource=grants.resource)
        except GrantRejected:return None
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(rotate,range(4)))
    winners=[result for result in results if result is not None]
    assert len(winners)==1
    with pytest.raises(GrantRejected):grants.verify(winners[0].access_token,resource=grants.resource)


def test_browser_logout_revokes_linked_delegation_and_preserves_other_native_session(renewable):
    from czero_core.oauth_grants import GrantRejected
    grants, _, _, pair, cookie, context = delegated(renewable)
    sessions, *_ = renewable
    other = login(renewable)
    assert grants.verify(pair.access_token,resource=grants.resource).actor.is_owner
    sessions.logout(cookie,context.csrf_token)
    with pytest.raises(GrantRejected):grants.verify(pair.access_token,resource=grants.resource)
    assert sessions.get(other).actor.is_owner


def test_short_idle_policy_bounds_advertised_access_lifetime(renewable):
    from czero_core.oauth_grants import GrantRejected
    _, authority, _, clock, *_ = renewable
    authority.policy = SessionPolicy(3600,60)
    grants, _, client, pair, _, _ = delegated(renewable)
    assert 1 <= pair.expires_in <= 60
    clock[0] += 60
    with pytest.raises(GrantRejected):grants.refresh(pair.refresh_token,client['client_id'],resource=grants.resource)


def test_client_disable_during_native_check_wins_before_delegated_use(renewable):
    from threading import Event
    from uuid import UUID
    from czero_core.oauth_grants import GrantRejected
    grants, clients, client, pair, _, context = delegated(renewable)
    _, authority, identity, _, _, _ = renewable
    started, release = Event(), Event()
    def check(_):
        started.set()
        assert release.wait(5)
        return RenewalResult(identity,'late-rotation')
    authority.check = check
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(grants.verify,pair.access_token,resource=grants.resource)
        try:
            assert started.wait(2)
            clients.set_enabled(context.actor,UUID(client['client_id']),enabled=False,expected_revision=1)
        finally:release.set()
        with pytest.raises(GrantRejected):pending.result(timeout=2)
    assert authority.authenticate(context.native_authority_id)['revoked'] is False


def test_role_revocation_during_native_check_cannot_be_reversed_by_late_reply(renewable):
    from threading import Event
    from czero_core.identity import PermissionDenied,Role
    sessions, authority, identity, clock, _, _ = renewable
    access = authority.access
    owner = access.resolve(identity)
    member = replace(identity,subject='member',account_key=str(uuid4()),username='member')
    with pytest.raises(PermissionDenied):access.resolve(member)
    with access.database.engine.connect() as c:
        identifier = c.execute(text('SELECT id FROM c0_accounts WHERE issuer=:issuer AND account_key=:key'),
                               {'issuer':access.issuer,'key':member.account_key}).scalar_one()
    access.set_role(owner,identifier,Role.EDITOR)
    cookie = sessions.create(member,renewal=RenewalResult(member,'member-initial-refresh'))
    started, release = Event(), Event()
    def check(_):
        started.set()
        assert release.wait(5)
        return RenewalResult(replace(member,expires_at=clock[0]+300),'late-member-rotation')
    authority.check = check
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(sessions.get,cookie)
        try:
            assert started.wait(2)
            access.set_role(owner,identifier,None)
        finally:release.set()
        with pytest.raises(RenewalRejected):pending.result(timeout=2)
    access.set_role(owner,identifier,Role.EDITOR)
    with pytest.raises(RenewalRejected):sessions.get(cookie)


def test_revoked_browser_cannot_complete_previously_captured_consent(renewable):
    from czero_core.identity import PermissionDenied
    from czero_core.oauth_grants import pkce_challenge
    grants, _, client, _, cookie, context = delegated(renewable)
    sessions, *_ = renewable
    sessions.logout(cookie,context.csrf_token)
    with pytest.raises(PermissionDenied):
        grants.issue_code(context,client['client_id'],callback=client['redirect_uris'][0],scopes={'c0:read'},
                          challenge=pkce_challenge('v'*43),resource=grants.resource)


@pytest.mark.parametrize('absolute,idle', [(60,60),(28800,3600),(86400,3600)])
def test_configured_absolute_bound_survives_continuous_renewal(renewable,absolute,idle):
    sessions,authority,_,clock,calls,_=renewable
    authority.policy=SessionPolicy(absolute,idle)
    started=clock[0]
    cookie=login(renewable)
    context=sessions.get(cookie)
    for offset in range(min(299,idle-1),absolute,min(299,idle-1)):
        clock[0]=started+offset
        assert sessions.get(cookie).expires_at==context.expires_at
    count=len(calls)
    clock[0]=started+absolute
    with pytest.raises(SessionRejected):sessions.get(cookie)
    assert len(calls)==count


def test_local_logout_requires_cookie_bound_csrf_even_when_provider_is_unavailable(renewable):
    from czero_core.identity import PermissionDenied
    sessions,_,_,_,_,failure=renewable
    cookie=login(renewable)
    context=sessions.get(cookie)
    failure[0]=RenewalUnavailable()
    with pytest.raises(PermissionDenied):sessions.logout(cookie,'wrong-csrf')
    sessions.logout(cookie,context.csrf_token)
    with pytest.raises(SessionRejected):sessions.get(cookie)


def test_native_ciphertext_cannot_be_rebound_to_another_browser_session(renewable):
    sessions,authority,_,_,_,_=renewable
    first,second=login(renewable),login(renewable)
    left,right=sessions.get(first),sessions.get(second)
    with authority.access.database.engine.begin() as c:
        c.execute(text('''UPDATE c0_native_authority SET credential=(SELECT credential FROM c0_native_authority WHERE id=:left)
            WHERE id=:right'''),{'left':left.native_authority_id,'right':right.native_authority_id})
    with pytest.raises(RenewalRejected):sessions.get(second)
    assert sessions.get(first).actor.is_owner


def test_oversized_sealed_credential_is_rejected_before_database_write(renewable):
    sessions,authority,identity,_,_,_=renewable
    with pytest.raises(RenewalRejected):sessions.create(identity,renewal=RenewalResult(identity,'\x00'*32768))
    with authority.access.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_native_authority WHERE issuer=:issuer'),{'issuer':identity.issuer}).scalar_one()==0


def test_logout_waits_for_inflight_authorized_transaction_before_revoking(renewable):
    from concurrent.futures import TimeoutError
    from threading import Event
    from czero_core.identity import PermissionDenied
    sessions,_,_,_,_,_=renewable
    cookie=login(renewable);context=sessions.get(cookie)
    entered,release,revoking=Event(),Event(),Event()
    def writer():
        with sessions.access.database.engine.begin() as c:
            sessions.access.checked_actor(c,context.actor)
            entered.set();assert release.wait(5)
            c.execute(text("UPDATE c0_accounts SET display_name='Committed authorized change' WHERE id=:id"),{'id':context.actor.user_id})
    def logout():
        revoking.set();sessions.logout(cookie,context.csrf_token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(writer)
        try:
            assert entered.wait(2)
            revoked=pool.submit(logout);assert revoking.wait(2)
            with pytest.raises(TimeoutError):revoked.result(timeout=0.1)
        finally:release.set()
        pending.result(timeout=2);revoked.result(timeout=2)
    with pytest.raises(PermissionDenied):sessions.access.profile(context.actor)


def test_cancelled_lock_acquisition_cannot_leak_session_lock_to_pool(renewable):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    sessions,authority,_,_,_,_=renewable
    cookie=login(renewable);context=sessions.get(cookie)
    engine=authority.access.database.engine
    def cancel_after_acquiring(connection,cursor,statement,parameters,context,executemany):
        if statement.startswith('SELECT pg_advisory_lock(49383,'):
            cursor.execute('SET LOCAL statement_timeout=10')
            return statement+', pg_sleep(0.1)',parameters
        return statement,parameters
    event.listen(engine,'before_cursor_execute',cancel_after_acquiring,retval=True)
    try:
        with pytest.raises(OperationalError):authority.authenticate(context.native_authority_id)
    finally:
        event.remove(engine,'before_cursor_execute',cancel_after_acquiring)
    with engine.connect() as c:
        try:
            assert c.execute(text("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND classid=49383 AND granted AND database=(SELECT oid FROM pg_database WHERE datname=current_database())")).scalar_one()==0
        finally:
            c.execute(text('SELECT pg_advisory_unlock_all()'))


def replacement_services(fixture):
    from czero_core.oauth_grants import OAuthGrantService
    sessions,authority,_,clock,*_=fixture
    replacement=NativeAuthorityService(sessions.access,'native2','t'*32,authority.check,policy=authority.policy,now=lambda:clock[0])
    browser=SessionService(sessions.access,'native2',authority=replacement,now=lambda:clock[0])
    grants=OAuthGrantService(sessions.access,'native2','https://c0.example.test/mcp',authority=replacement,now=lambda:clock[0])
    return browser,grants


def test_new_native_client_does_not_inherit_invalid_old_browser_quota(renewable):
    sessions,_,identity,*_=renewable
    old=login(renewable)
    for _ in range(31):login(renewable)
    replacement,_=replacement_services(renewable)
    cookie=replacement.create(identity,renewal=RenewalResult(identity,'new-native-client-refresh'))
    assert replacement.get(cookie).actor.is_owner
    with pytest.raises(SessionRejected):replacement.get(old)
    with pytest.raises(SessionRejected):sessions.get(cookie)


def test_new_native_client_has_fresh_grant_budget_without_rewriting_approved_client(renewable):
    from czero_core.oauth_grants import GrantRejected,pkce_challenge
    grants,clients,client,pair,_,context=delegated(renewable)
    for _ in range(31):
        grants.issue_code(context,client['client_id'],callback=client['redirect_uris'][0],scopes={'c0:read'},
                          challenge=pkce_challenge('v'*43),resource=grants.resource)
    replacement,new_grants=replacement_services(renewable)
    identity=renewable[2]
    cookie=replacement.create(identity,renewal=RenewalResult(identity,'new-client-refresh'))
    current=replacement.get(cookie)
    code=new_grants.issue_code(current,client['client_id'],callback=client['redirect_uris'][0],scopes={'c0:read'},
                               challenge=pkce_challenge('v'*43),resource=new_grants.resource)
    new_pair=new_grants.exchange_code(code,client['client_id'],callback=client['redirect_uris'][0],verifier='v'*43,resource=new_grants.resource)
    assert new_grants.verify(new_pair.access_token,resource=new_grants.resource).actor.is_owner
    with pytest.raises(GrantRejected):new_grants.verify(pair.access_token,resource=new_grants.resource)
    assert clients._lookup(client['client_id'])==client


@pytest.mark.parametrize('fixed_limit', [120, 3600])
def test_missing_provider_refresh_keeps_fixed_session_cap(renewable, fixed_limit):
    _, authority, identity, clock, calls, _ = renewable
    authority.policy = SessionPolicy(28800, 3600)
    sessions = SessionService(authority.access, authority.client_id, authority=authority,
                              max_session_seconds=fixed_limit, now=lambda: clock[0])
    long_identity = replace(identity, expires_at=clock[0] + 14400)
    cookie = sessions.create(long_identity)
    context = sessions.get(cookie)
    assert context.native_authority_id is None
    assert context.expires_at.timestamp() == pytest.approx(clock[0] + fixed_limit)
    assert calls == []
