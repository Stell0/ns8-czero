# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Remembered browser clocks and concurrency on disposable PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
import secrets

import pytest
from sqlalchemy import text

from test_persistent_oauth import persistent, RESOURCE, CALLBACK
from czero_core.identity import PermissionDenied, Role
from czero_core.access import AccessService
from uuid import uuid4
from czero_core.oauth_grants import GrantRejected, pkce_challenge
from czero_core.renewal import ConnectionPolicy, RenewalRejected, RenewalResult, RenewalUnavailable
from czero_core.sessions import LoginStateRejected, REMEMBER_SECONDS, SessionRejected, SessionService


def remembered(f):
    return f['sessions'].create(f['identity'], renewal=RenewalResult(f['identity'], 'offline-remembered', offline=True), remembered=True)


def test_seven_day_rolling_browser_restart_and_exact_boundary(persistent):
    f=persistent;cookie=remembered(f);sessions=f['sessions'];start=f['current'][0]
    for elapsed in (3601, 28801, REMEMBER_SECONDS-1):
        f['current'][0]=start+elapsed
        assert sessions.get(cookie).remembered
    # Authentication alone (including a failed HTTP operation) never slides it.
    assert sessions.get(cookie).expires_at.timestamp()==pytest.approx(start+REMEMBER_SECONDS,abs=0.00001,rel=0)
    context=sessions.renew_browser(cookie)
    assert context.expires_at.timestamp()==pytest.approx(f['current'][0]+REMEMBER_SECONDS,abs=0.00001,rel=0)
    restarted=SessionService(f['access'],'native1',authority=f['authority'],now=lambda:f['current'][0])
    f['current'][0]+=REMEMBER_SECONDS-1
    assert restarted.get(cookie).remembered
    f['current'][0]+=1
    with pytest.raises(SessionRejected):restarted.get(cookie)
    with pytest.raises(SessionRejected):restarted.renew_browser(cookie)


def test_offline_authority_required_without_enabling_background_consent(persistent):
    f=persistent
    for renewal in (None, RenewalResult(f['identity'], 'online')):
        with pytest.raises((SessionRejected,RenewalRejected)):
            f['sessions'].create(f['identity'],renewal=renewal,remembered=True)
    cookie=remembered(f);context=f['sessions'].get(cookie)
    with pytest.raises(GrantRejected):f['issue'](session=context)
    pair=f['issue'](session=context,persistent=False)
    with f['database'].engine.connect() as c:
        expiry=c.execute(text('SELECT expires_at FROM c0_oauth_grants WHERE native_authority_id=:id'),{'id':context.native_authority_id}).scalar_one()
    assert expiry.timestamp()==pytest.approx(f['current'][0]+f['authority'].policy.absolute_seconds,abs=0.00001,rel=0)


def test_connection_activity_cannot_slide_browser_deadline(persistent):
    f=persistent;cookie=remembered(f);context=f['sessions'].get(cookie)
    pair=f['issue'](session=context,persistent=False)
    before=context.expires_at
    f['current'][0]+=120
    f['grants'].verify(pair.access_token,resource=RESOURCE)
    with f['database'].engine.connect() as c:
        assert c.execute(text('SELECT expires_at FROM c0_sessions WHERE native_authority_id=:id'),{'id':context.native_authority_id}).scalar_one()==before
    f['current'][0]=before.timestamp()
    with pytest.raises(SessionRejected):f['sessions'].get(cookie)


def test_background_flow_preserves_browser_choice_with_short_connection_policy(persistent):
    f=persistent;f['authority'].connection_policy=ConnectionPolicy(60)
    cookie=remembered(f);context=f['sessions'].get(cookie)
    pending=f['sessions'].begin_login(background=True,session=context)
    assert pending.background and pending.remembered
    consumed=f['sessions'].consume_login(pending.state,pending.browser_binding)
    assert consumed.remembered and consumed.expected_account_key==f['identity'].account_key
    background=f['sessions'].create(f['identity'],renewal=RenewalResult(f['identity'],'offline-background',offline=True),
        background=True,remembered=consumed.remembered,expected_account_key=consumed.expected_account_key)
    context=f['sessions'].get(background)
    pair=f['issue'](session=context)
    with f['database'].engine.connect() as c:
        grant=c.execute(text('SELECT idle_until FROM c0_oauth_grants WHERE native_authority_id=:id'),{'id':context.native_authority_id}).scalar_one()
    assert grant.timestamp()==pytest.approx(f['current'][0]+60,abs=0.00001,rel=0)
    f['current'][0]+=61
    assert f['sessions'].get(background).remembered
    with pytest.raises(GrantRejected):f['grants'].verify(pair.access_token,resource=RESOURCE)


def test_signin_intent_expiry_binding_and_concurrent_one_use(persistent):
    f=persistent;sessions=f['sessions'];intent,browser=sessions.begin_sign_in()
    with pytest.raises(LoginStateRejected):sessions.consume_sign_in(intent,'wrong-binding')
    def consume(_):
        try:sessions.consume_sign_in(intent,browser);return True
        except LoginStateRejected:return False
    with ThreadPoolExecutor(2) as executor:assert sum(executor.map(consume,range(2)))==1
    intent,browser=sessions.begin_sign_in();f['current'][0]+=300
    with pytest.raises(LoginStateRejected):sessions.consume_sign_in(intent,browser)


def test_logout_wins_over_inflight_provider_check_and_late_renewal(persistent):
    f=persistent;cookie=remembered(f);context=f['sessions'].get(cookie)
    entered,release=Event(),Event();original=f['authority'].check
    def check(credential):
        entered.set();assert release.wait(10);return original(credential)
    f['authority'].check=check
    with ThreadPoolExecutor(1) as executor:
        future=executor.submit(f['sessions'].get,cookie)
        assert entered.wait(10)
        f['sessions'].logout(cookie,context.csrf_token);release.set()
        with pytest.raises((SessionRejected,RenewalRejected)):future.result(10)
    with pytest.raises(SessionRejected):f['sessions'].renew_browser(cookie)


def test_parallel_browser_renewal_is_persistent_and_logout_cannot_revive(persistent):
    f=persistent;cookie=remembered(f);context=f['sessions'].get(cookie);f['current'][0]+=3601
    f['sessions'].get(cookie)
    with ThreadPoolExecutor(4) as executor:
        contexts=list(executor.map(lambda _:f['sessions'].renew_browser(cookie),range(4)))
    assert all(c.expires_at.timestamp()==pytest.approx(f['current'][0]+REMEMBER_SECONDS,abs=0.00001,rel=0) for c in contexts)
    f['sessions'].logout(cookie,context.csrf_token)
    with pytest.raises(SessionRejected):f['sessions'].renew_browser(cookie)


def test_membership_block_and_provider_rejection_stop_remembered_access(persistent):
    f=persistent;key=uuid4()
    identity=replace(f['identity'],account_key=str(key),subject='member')
    admission=AccessService(f['database'],f['access'].issuer,f['access'].owner_account_key,admit_readers=True)
    member=admission.resolve(identity)
    member_cookie=f['sessions'].create(identity,renewal=RenewalResult(identity,'offline-member',offline=True),remembered=True)
    f['access'].set_role(f['context'].actor,member.user_id,None)
    with pytest.raises((PermissionDenied,RenewalRejected)):f['sessions'].get(member_cookie)
    with pytest.raises((PermissionDenied,RenewalRejected)):f['sessions'].renew_browser(member_cookie)
    # Use the owner fixture for provider failures, which must never slide browser expiry.
    cookie=remembered(f);context=f['sessions'].get(cookie)
    f['failure'][0]=RenewalUnavailable()
    with pytest.raises(RenewalUnavailable):f['sessions'].get(cookie)
    with pytest.raises(RenewalRejected):f['sessions'].renew_browser(cookie)
    f['failure'][0]=RenewalRejected()
    with pytest.raises(RenewalRejected):f['sessions'].get(cookie)
    f['failure'][0]=None
    with pytest.raises(RenewalRejected):f['sessions'].get(cookie)


def test_membership_revocation_wins_over_inflight_remembered_renewal(persistent):
    f=persistent;key=uuid4()
    identity=replace(f['identity'],account_key=str(key),subject='concurrent-member')
    admission=AccessService(f['database'],f['access'].issuer,f['access'].owner_account_key,admit_readers=True)
    member=admission.resolve(identity)
    cookie=f['sessions'].create(identity,renewal=RenewalResult(identity,'offline-member',offline=True),remembered=True)
    entered,release=Event(),Event()
    def check(credential):
        entered.set();assert release.wait(10)
        return RenewalResult(replace(identity,expires_at=f['current'][0]+300),'offline-rotated',offline=True)
    f['authority'].check=check
    with ThreadPoolExecutor(1) as executor:
        future=executor.submit(f['sessions'].get,cookie)
        assert entered.wait(10)
        f['access'].set_role(f['context'].actor,member.user_id,None);release.set()
        with pytest.raises((PermissionDenied,RenewalRejected)):future.result(10)
    with pytest.raises((PermissionDenied,RenewalRejected)):f['sessions'].renew_browser(cookie)


def test_ordinary_browser_idle_is_independent_of_valid_mcp_refresh(persistent):
    f=persistent;sessions=f['sessions'];start=f['current'][0]
    cookie=sessions.create(f['identity'],renewal=RenewalResult(f['identity'],'online-initial'))
    context=sessions.get(cookie)
    assert context.expires_at.timestamp()==pytest.approx(start+3600,abs=0.00001,rel=0)
    pair=f['issue'](session=context,persistent=False)
    for elapsed in (300,600):
        f['current'][0]=start+elapsed
        pair=f['grants'].refresh(pair.refresh_token,f['client']['client_id'],resource=RESOURCE)
        assert f['grants'].verify(pair.access_token,resource=RESOURCE).actor.is_owner
    with pytest.raises(SessionRejected):sessions.get(cookie)
    with pytest.raises(SessionRejected):sessions.renew_browser(cookie)
    # Browser expiry cannot revoke separately valid finite delegated authority.
    assert f['grants'].verify(pair.access_token,resource=RESOURCE).actor.is_owner


def test_reauthentication_retires_browser_without_revoking_finite_connections(persistent):
    f=persistent;old=remembered(f);context=f['sessions'].get(old)
    pair=f['issue'](session=context,persistent=False)
    fresh=remembered(f)
    f['sessions'].replace_browser(old)
    with pytest.raises(SessionRejected):f['sessions'].get(old)
    with pytest.raises(SessionRejected):f['sessions'].renew_browser(old)
    assert f['sessions'].get(fresh).remembered
    # Another sign-in's authority cleanup cannot revoke the retained grant.
    remembered(f)
    assert f['grants'].verify(pair.access_token,resource=RESOURCE).actor.is_owner
    assert f['grants'].refresh(pair.refresh_token,f['client']['client_id'],resource=RESOURCE).expires_in>0


def test_reauthentication_wins_over_inflight_old_browser_read(persistent):
    f=persistent;old=remembered(f);entered,release=Event(),Event();original=f['authority'].check
    def check(credential):
        entered.set();assert release.wait(10);return original(credential)
    f['authority'].check=check
    with ThreadPoolExecutor(1) as executor:
        future=executor.submit(f['sessions'].get,old)
        assert entered.wait(10)
        fresh=remembered(f);f['sessions'].replace_browser(old);release.set()
        with pytest.raises((SessionRejected,RenewalRejected)):future.result(10)
    f['authority'].check=original
    assert f['sessions'].get(fresh).remembered
    with pytest.raises(SessionRejected):f['sessions'].renew_browser(old)
