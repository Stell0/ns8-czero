# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent delegation with real PostgreSQL and a controlled provider/clock."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import base64
import os
import secrets
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import PermissionDenied, Role, VerifiedIdentity
from czero_core.migrate import migrate_database
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_consent import ConsentRejected, OAuthConsentService
from czero_core.oauth_grants import GrantRejected, OAuthGrantService, pkce_challenge
from czero_core.renewal import ConnectionPolicy, NativeAuthorityService, RenewalRejected, RenewalResult, RenewalUnavailable, SessionPolicy
from czero_core.sessions import LoginStateRejected, SessionRejected, SessionService

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='disposable PostgreSQL required')
CALLBACK = 'https://client.example.test/callback'
RESOURCE = 'https://c0.example.test/mcp'


class PrivateFixture(dict):
    def __repr__(self):
        return '<private persistent OAuth fixture>'


@pytest.fixture
def persistent():
    database = Database(os.environ['CZERO_TEST_DATABASE_URL'])
    migrate_database(database)
    current = [time.time()]
    key = uuid4()
    access = AccessService(database, 'https://idp.example.test/'+str(key), key)
    identity = VerifiedIdentity(access.issuer, 'subject', str(key), 'owner', 'Owner', current[0]+300)
    failure = [None]
    calls = []
    def check(credential):
        if failure[0] is not None:
            raise failure[0]
        calls.append(credential)
        offline = credential.startswith('offline')
        return RenewalResult(replace(identity, expires_at=current[0]+300),
                             ('offline' if offline else 'online')+'-'+str(len(calls)), offline=offline)
    authority = NativeAuthorityService(access, 'native1', 's'*32, check,
        policy=SessionPolicy(3600, 600), connection_policy=ConnectionPolicy(), now=lambda:current[0])
    sessions = SessionService(access, 'native1', authority=authority, now=lambda:current[0])
    cookie = sessions.create(identity, renewal=RenewalResult(identity, 'offline-initial', offline=True),
        background=True, expected_account_key=str(key))
    context = sessions.get(cookie)
    clients = OAuthClientService(access)
    client = clients.register(context.actor, 'Persistent '+str(key), [CALLBACK], scopes=['c0:read','c0:write'])
    grants = OAuthGrantService(access, 'native1', RESOURCE, authority=authority, now=lambda:current[0])
    verifier = secrets.token_urlsafe(32)
    def issue(*, persistent=True, scopes=None, session=None):
        code = grants.issue_code(session or context, client['client_id'], callback=CALLBACK,
            scopes=scopes or {'c0:read','c0:write'}, challenge=pkce_challenge(verifier), resource=RESOURCE,
            persistent=persistent)
        return grants.exchange_code(code, client['client_id'], callback=CALLBACK, verifier=verifier, resource=RESOURCE)
    yield PrivateFixture(locals())
    with database.engine.begin() as connection:
        connection.execute(text('DELETE FROM c0_oauth_clients WHERE name=:name'), {'name':'Persistent '+str(key)})
        connection.execute(text('DELETE FROM c0_sessions WHERE issuer=:issuer'), {'issuer':access.issuer})
        connection.execute(text('DELETE FROM c0_login_states WHERE issuer=:issuer'), {'issuer':access.issuer})
        connection.execute(text('DELETE FROM c0_accounts WHERE issuer=:issuer'), {'issuer':access.issuer})
    database.close()


def refresh(f, pair):
    return f['grants'].refresh(pair.refresh_token, f['client']['client_id'], resource=RESOURCE)


def test_daily_refresh_continues_for_year_while_browser_stays_bounded(persistent):
    f=persistent;pair=f['issue']()
    assert pair.expires_in==300
    f['sessions'].logout(f['cookie'], f['context'].csrf_token)
    for _ in range(366):
        f['current'][0]+=86400
        pair=refresh(f,pair)
        assert pair.expires_in==300 and f['grants'].verify(pair.access_token,resource=RESOURCE).actor.is_owner
    with pytest.raises(SessionRejected):f['sessions'].get(f['cookie'])
    with f['database'].engine.connect() as c:
        assert c.execute(text('SELECT expires_at FROM c0_oauth_grants WHERE account_id=:id'),{'id':f['context'].actor.user_id}).scalar_one() is None


def test_inactivity_expiry_is_not_revived(persistent):
    f=persistent;pair=f['issue']();f['current'][0]+=30*86400
    with pytest.raises(GrantRejected):refresh(f,pair)


def test_delegated_activity_does_not_extend_browser_idle_deadline(persistent):
    f=persistent;pair=f['issue']()
    captured=f['context'].actor
    for _ in range(2):
        f['current'][0]+=300
        pair=refresh(f,pair)
    with pytest.raises(SessionRejected):f['sessions'].get(f['cookie'])
    with f['database'].engine.connect() as c:
        with pytest.raises(PermissionDenied):f['access'].checked_actor(c,captured)
    assert refresh(f,pair)


def test_active_background_browser_keeps_original_absolute_bound(persistent):
    f=persistent;pair=f['issue']()
    for _ in range(11):
        f['current'][0]+=300
        assert f['sessions'].get(f['cookie']).actor.is_owner
    f['current'][0]+=300
    with pytest.raises(SessionRejected):f['sessions'].get(f['cookie'])
    assert refresh(f,pair)


def test_2050_rotations_keep_two_rows_and_ancient_replay_revokes_family(persistent):
    f=persistent;first=pair=f['issue']()
    for _ in range(2050):pair=refresh(f,pair)
    with f['database'].engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_oauth_tokens t JOIN c0_oauth_grants g ON g.id=t.grant_id WHERE g.account_id=:id'),{'id':f['context'].actor.user_id}).scalar_one()==2
    f['failure'][0]=RenewalUnavailable()
    with pytest.raises(GrantRejected):f['grants']._refresh_token(first.refresh_token,f['client']['client_id'])
    f['failure'][0]=None
    with pytest.raises(GrantRejected):refresh(f,pair)


def test_forged_and_future_generations_do_not_revoke_valid_family(persistent):
    f=persistent;pair=f['issue']();raw=bytearray(base64.urlsafe_b64decode(pair.refresh_token+'='))
    raw[-1]^=1
    forged=base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
    with pytest.raises(GrantRejected):f['grants']._refresh_token(forged,f['client']['client_id'])
    with f['database'].engine.connect() as c:
        grant=c.execute(text('SELECT * FROM c0_oauth_grants WHERE account_id=:id'),{'id':f['context'].actor.user_id}).mappings().one()
    future=f['grants']._persistent_refresh(grant,grant['refresh_generation']+1)
    with pytest.raises(GrantRejected):refresh(f,replace(pair,refresh_token=future))
    assert refresh(f,pair)


def test_replay_with_wrong_client_or_resource_cannot_revoke_family(persistent):
    f=persistent;old=f['issue']();pair=refresh(f,old)
    for client,resource in [('not-a-client',RESOURCE),(f['client']['client_id'],'https://wrong.example.test/mcp')]:
        with pytest.raises(GrantRejected):f['grants'].refresh(old.refresh_token,client,resource=resource)
    assert refresh(f,pair)


def test_refresh_narrowing_cannot_be_reversed(persistent):
    f=persistent;pair=f['issue']()
    pair=f['grants'].refresh(pair.refresh_token,f['client']['client_id'],resource=RESOURCE,scopes={'c0:read'})
    with pytest.raises(GrantRejected):f['grants'].refresh(pair.refresh_token,f['client']['client_id'],resource=RESOURCE,scopes={'c0:read','c0:write'})
    assert refresh(f,pair).scopes==frozenset({'c0:read'})


def test_provider_outage_does_not_extend_idle_and_recovers(persistent):
    f=persistent;pair=f['issue']()
    with f['database'].engine.connect() as c:
        before=c.execute(text('SELECT idle_until FROM c0_oauth_grants WHERE account_id=:id'),{'id':f['context'].actor.user_id}).scalar_one()
    f['current'][0]+=86400;f['failure'][0]=RenewalUnavailable()
    with pytest.raises(RenewalUnavailable):refresh(f,pair)
    with f['database'].engine.connect() as c:
        assert c.execute(text('SELECT idle_until FROM c0_oauth_grants WHERE account_id=:id'),{'id':f['context'].actor.user_id}).scalar_one()==before
    f['failure'][0]=None
    assert refresh(f,pair)


def test_provider_rejection_is_durable(persistent):
    f=persistent;pair=f['issue']();f['failure'][0]=RenewalRejected()
    with pytest.raises(GrantRejected):refresh(f,pair)
    f['failure'][0]=None
    with pytest.raises(GrantRejected):refresh(f,pair)


def test_bounded_grant_from_offline_browser_is_not_silently_upgraded(persistent):
    f=persistent;pair=f['issue'](persistent=False);f['current'][0]+=3600
    with pytest.raises(GrantRejected):refresh(f,pair)


def test_unproved_background_authority_and_wrong_account_are_rejected(persistent):
    f=persistent
    with pytest.raises(RenewalRejected):f['sessions'].create(f['identity'],renewal=RenewalResult(f['identity'],'online'),background=True,expected_account_key=str(f['key']))
    with pytest.raises(SessionRejected):f['sessions'].create(f['identity'],renewal=RenewalResult(f['identity'],'offline',offline=True),background=True,expected_account_key=str(uuid4()))


def test_background_login_state_binds_verified_account_and_one_use(persistent):
    f=persistent;s=f['sessions']
    with pytest.raises(LoginStateRejected):s.begin_login(background=True)
    pending=s.begin_login(background=True,session=f['context'])
    assert s.pending_login(pending.state,pending.browser_binding)==pending
    with pytest.raises(LoginStateRejected):s.pending_login(pending.state,secrets.token_urlsafe(32))
    result=s.consume_login(pending.state,pending.browser_binding)
    assert result.background and result.expected_account_key==str(f['key'])
    with pytest.raises(LoginStateRejected):s.consume_login(pending.state,pending.browser_binding)


def test_parallel_refresh_detects_replay_and_never_leaves_two_live_families(persistent):
    f=persistent;pair=f['issue']()
    def attempt():
        try:return refresh(f,pair)
        except GrantRejected:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
    assert sum(v is not None for v in results)==1
    with pytest.raises(GrantRejected):refresh(f,next(v for v in results if v is not None))


def test_logout_preserves_only_explicit_background_grants(persistent):
    f=persistent;durable=f['issue']();bounded=f['issue'](persistent=False)
    f['sessions'].logout(f['cookie'],f['context'].csrf_token)
    with pytest.raises(GrantRejected):refresh(f,bounded)
    assert refresh(f,durable)


def test_connection_view_is_private_and_disconnect_revokes_only_selected_grant(persistent):
    f=persistent;one=f['issue']();two=f['issue']()
    rows=f['grants'].connections(f['context'].actor);assert len(rows)==2
    assert all(set(row)=={'id','client_name','scopes','persistent','expires_at','idle_until','last_used_at'} for row in rows)
    with pytest.raises(PermissionDenied):f['grants'].connections(f['grants'].verify(one.access_token,resource=RESOURCE).actor)
    f['grants'].disconnect(f['context'].actor,UUID(rows[0]['id']))
    successes=0
    for pair in (one,two):
        try:refresh(f,pair);successes+=1
        except GrantRejected:pass
    assert successes==1


def test_public_revoke_accepts_an_old_issued_refresh_generation(persistent):
    f=persistent;old=f['issue']();pair=refresh(f,old)
    f['grants'].revoke(old.refresh_token,f['client']['client_id'],resource=RESOURCE)
    with pytest.raises(GrantRejected):refresh(f,pair)


def test_existing_client_disable_revokes_persistent_access(persistent):
    f=persistent;pair=f['issue']()
    f['clients'].set_enabled(f['context'].actor,UUID(f['client']['client_id']),enabled=False,expected_revision=f['client']['revision'])
    with pytest.raises(GrantRejected):refresh(f,pair)


def test_membership_downgrade_then_revoke_and_regrant_cannot_restore_old_authority(persistent):
    f=persistent;key=uuid4();identity=replace(f['identity'],account_key=str(key),subject='editor',username='editor')
    editor=AccessService(f['database'],f['access'].issuer,f['key'],admit_readers=True).resolve(identity)
    f['access'].set_role(f['context'].actor,editor.user_id,Role.EDITOR)
    f['authority'].check=lambda credential:RenewalResult(replace(identity,expires_at=f['current'][0]+300),'offline-editor',offline=True)
    cookie=f['sessions'].create(identity,renewal=RenewalResult(identity,'offline-editor',offline=True),background=True,expected_account_key=str(key))
    context=f['sessions'].get(cookie);pair=f['issue'](session=context)
    f['access'].set_role(f['context'].actor,editor.user_id,Role.READER)
    with pytest.raises(GrantRejected):f['grants'].verify(pair.access_token,resource=RESOURCE)
    f['access'].set_role(f['context'].actor,editor.user_id,None)
    f['access'].set_role(f['context'].actor,editor.user_id,Role.EDITOR)
    with pytest.raises(GrantRejected):refresh(f,pair)


def test_native_secret_replacement_rejects_persistent_credentials(persistent):
    f=persistent;pair=f['issue']()
    changed=NativeAuthorityService(f['access'],'native1','x'*32,f['authority'].check,
        connection_policy=ConnectionPolicy(),now=lambda:f['current'][0])
    grants=OAuthGrantService(f['access'],'native1',RESOURCE,authority=changed,now=lambda:f['current'][0])
    with pytest.raises(GrantRejected):grants.refresh(pair.refresh_token,f['client']['client_id'],resource=RESOURCE)


def test_background_login_requires_policy_and_expires_after_five_minutes(persistent):
    f=persistent;pending=f['sessions'].begin_login(background=True,session=f['context'])
    f['current'][0]+=300
    with pytest.raises(LoginStateRejected):f['sessions'].pending_login(pending.state,pending.browser_binding)
    f['authority'].connection_policy=None
    with pytest.raises(LoginStateRejected):f['sessions'].begin_login(background=True,session=f['context'])


def test_background_consent_keeps_expiry_narrows_scope_and_pins_account(persistent):
    f=persistent;service=OAuthConsentService(f['grants']);verifier=secrets.token_urlsafe(32)
    pending=service.begin(f['client']['client_id'],callback=CALLBACK,scopes={'c0:read','c0:write'},
        challenge=pkce_challenge(verifier),state='private-state',resource=RESOURCE)
    before=service.view(pending.request,pending.binding)
    service.prepare_background(f['context'],pending.request,pending.binding,scopes={'c0:read'})
    after=service.view(pending.request,pending.binding)
    assert after['expires_at']==before['expires_at'] and after['scopes']==['c0:read'] and after['background_requested']
    other=AccessService(f['database'],f['access'].issuer,f['key'],admit_readers=True).resolve(
        replace(f['identity'],account_key=str(uuid4()),subject='reader',username='reader'))
    from czero_core.sessions import SessionContext
    switched=SessionContext(other,f['context'].expires_at,'private-csrf')
    with pytest.raises(ConsentRejected):service.complete(switched,pending.request,pending.binding,approve=True,scopes={'c0:read'},persistent=True)
    result=service.complete(f['context'],pending.request,pending.binding,approve=True,scopes={'c0:read'},persistent=True)
    pair=f['grants'].exchange_code(result.code,f['client']['client_id'],callback=CALLBACK,verifier=verifier,resource=RESOURCE)
    assert pair.scopes==frozenset({'c0:read'})


def test_policy_change_does_not_extend_previously_consented_inactivity(persistent):
    f=persistent;pair=f['issue']();f['authority'].connection_policy=ConnectionPolicy(60*86400)
    f['current'][0]+=86400;refresh(f,pair)
    with f['database'].engine.connect() as c:
        deadline=c.execute(text('SELECT idle_until FROM c0_oauth_grants WHERE account_id=:id'),{'id':f['context'].actor.user_id}).scalar_one()
    assert deadline.timestamp()==pytest.approx(f['current'][0]+30*86400,abs=0.000001,rel=0)


@pytest.mark.parametrize('seconds',[False,0,59,31536001,'2592000'])
def test_connection_policy_bounds(seconds):
    with pytest.raises(ValueError):ConnectionPolicy(seconds)
