# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real PostgreSQL access administration: authority boundaries and exact targets."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.access import AccessConflict
from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.oauth_clients import ClientConflict
from czero_core.client_onboarding import OnboardingRejected
from czero_core.oauth_grants import GrantRejected, _digest
from czero_core.workspace_access import WorkspaceAccessService, permissions
from test_access import access, owner_actor, identity, record_unadmitted, account_named
from test_persistent_oauth import persistent, refresh, RESOURCE
from test_client_onboarding import onboarding, parameters, cimd, grants, application

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='disposable PostgreSQL required')


def test_revision_rejects_stale_and_aba_permission_changes(access):
    service, _, _ = access; owner = owner_actor(access)
    key = uuid4(); record_unadmitted(service, key, 'subject')
    member = account_named(service, owner, 'subject')
    service.set_role(owner, member['id'], Role.READER, expected_revision=member['access_revision'])
    with pytest.raises(AccessConflict):
        service.set_role(owner, member['id'], Role.ADMIN, expected_revision=member['access_revision'])
    service.set_role(owner, member['id'], None)
    assert account_named(service, owner, 'subject')['blocked']
    with pytest.raises(AccessConflict):
        service.set_role(owner, member['id'], Role.EDITOR, expected_revision=member['access_revision'])
    current = account_named(service, owner, 'subject')
    service.set_role(owner, member['id'], None, expected_revision=current['access_revision'])
    assert account_named(service, owner, 'subject')['access_revision'] == current['access_revision']
    with pytest.raises(PermissionDenied):service.resolve(identity(service, key, 'renamed'))
    service.set_role(owner, member['id'], Role.EDITOR, expected_revision=current['access_revision'])
    assert service.resolve(identity(service, key, 'renamed')).role is Role.EDITOR


def test_concurrent_revision_changes_have_one_winner(access):
    service, _, _ = access; owner = owner_actor(access)
    record_unadmitted(service, uuid4(), 'subject'); member = account_named(service, owner, 'subject')
    def update(role):
        try:service.set_role(owner, member['id'], role, expected_revision=member['access_revision']);return True
        except AccessConflict:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update,[Role.READER,Role.EDITOR])) == [False,True]


def test_overview_is_first_party_current_admin_scoped_and_paginated(persistent):
    f=persistent;service=WorkspaceAccessService(f['grants']);owner=f['context'].actor
    for name in ('member-a','member-b'):
        key=uuid4()
        with pytest.raises(PermissionDenied):f['access'].resolve(identity(f['access'],key,name))
    first=service.overview(owner,limit=2);second=service.overview(owner,limit=2,offset=2)
    assert len(first['accounts'])==2 and first['has_more']
    assert len(second['accounts'])==1 and not second['has_more']
    assert not {a['id'] for a in first['accounts']} & {a['id'] for a in second['accounts']}
    assert all('account_key' not in a for a in first['accounts'])
    for bad in (Actor(owner.user_id,Role.ADMIN,True,delegated_scopes=frozenset({'c0:admin'})),):
        with pytest.raises(PermissionDenied):service.overview(bad)
    for limit in (True,0,101):
        with pytest.raises(ValueError):service.overview(owner,limit=limit)
    with pytest.raises(ValueError):service.applications(owner,uuid4())


def test_admin_disconnect_only_exact_grant_and_never_native_siblings(persistent):
    f=persistent;service=WorkspaceAccessService(f['grants']);owner=f['context'].actor
    first=f['issue']();second=f['issue']()
    rows=service.applications(owner,owner.user_id)['applications']
    with f['database'].engine.connect() as c:
        first_id=c.execute(text('SELECT grant_id FROM c0_oauth_tokens WHERE hash=:hash'),{'hash':_digest(first.access_token)}).scalar_one()
    assert len(rows)==2 and all(r['status']=='connected' and r['permissions']['write'] for r in rows)
    service.disconnect(owner,first_id)
    with pytest.raises(GrantRejected):refresh(f,first)
    with pytest.raises(GrantRejected):f['grants'].verify(first.access_token,resource=RESOURCE)
    assert refresh(f,second).access_token
    assert f['sessions'].get(f['cookie']).actor==owner
    assert len(service.applications(owner,owner.user_id)['applications'])==1
    with pytest.raises(GrantRejected):service.disconnect(owner,first_id)


def test_summary_does_not_extend_or_contact_native_authority(persistent):
    f=persistent;service=WorkspaceAccessService(f['grants']);owner=f['context'].actor
    f['issue']();calls=len(f['calls']);f['current'][0]+=301
    # A separate trusted administrator is used after this fixture browser's proof expires.
    owner=Actor(owner.user_id,Role.ADMIN,True)
    row=service.applications(owner,owner.user_id)['applications'][0]
    assert row['status']=='renewal_required' and not any(row['permissions'].values())
    assert len(f['calls'])==calls
    with f['database'].engine.begin() as c:
        c.execute(text('UPDATE c0_native_authority SET revoked=true WHERE account_id=:id'),{'id':owner.user_id})
    assert service.applications(owner,owner.user_id)['applications'][0]['status']=='needs_reconnect'


def test_read_and_manage_scopes_are_independent():
    assert permissions('admin',{'c0:admin'})=={'read':False,'write':False,'manage':True}
    assert permissions('reader',{'c0:read','c0:write'})=={'read':True,'write':False,'manage':False}


def test_request_safe_id_decline_consumes_exact_handoff_only(onboarding):
    old,f=onboarding;session=f[-1][3];service=WorkspaceAccessService(old.grants)
    pending=old.begin(parameters(onboarding)[0]);old.submit(session,pending.request,pending.binding)
    second=old.begin(parameters(onboarding)[0]);old.submit(session,second.request,second.binding)
    overview=service.overview(session.actor)
    assert overview['pending_count']==2
    rows=service.applications(session.actor,session.actor.user_id)['applications']
    assert len(rows)==2 and all(r['kind']=='request' for r in rows)
    assert not any(key in row for row in rows for key in ('hash','browser_hash','parameters','state','code_challenge'))
    service.decline(session.actor,rows[0]['id'])
    assert len(service.applications(session.actor,session.actor.user_id)['applications'])==1
    with pytest.raises(OnboardingRejected):service.decline(session.actor,rows[0]['id'])
    failures=0
    for token in (pending,second):
        try:old.view(session,token.request,token.binding)
        except OnboardingRejected:failures+=1
    assert failures==1 and service.overview(session.actor)['pending_count']==1


def test_blocked_request_cannot_be_approved_and_current_role_is_rechecked(onboarding):
    old,f=onboarding;session=f[-1][3];service=WorkspaceAccessService(old.grants)
    member_key=uuid4()
    with pytest.raises(PermissionDenied):old.grants.access.resolve(identity(old.grants.access,member_key,'person'))
    account=account_named(old.grants.access,session.actor,'person')
    old.grants.access.set_role(session.actor,account['id'],Role.READER)
    reader=old.grants.access.resolve(identity(old.grants.access,member_key,'person'))
    pending=old.begin(parameters(onboarding)[0]);old.submit(replace(session,actor=reader),pending.request,pending.binding)
    request=service.applications(session.actor,reader.user_id)['applications'][0]
    old.grants.access.set_role(session.actor,reader.user_id,None)
    with pytest.raises(PermissionDenied):
        service.approve(session.actor,request['id'],f[3],scopes=['c0:read'],expected_digest=f[3].digest)
    with pytest.raises(PermissionDenied):service.decline(reader,request['id'])
    service.decline(session.actor,request['id'])


def test_request_bound_approval_preserves_scopes_and_requires_live_request(onboarding):
    old,f=onboarding;grants,registry,client,metadata,*_=f;session=f[-1][3]
    service=WorkspaceAccessService(grants)
    pending=old.begin(parameters(onboarding)[0]);old.submit(session,pending.request,pending.binding)
    request=service.applications(session.actor,session.actor.user_id)['applications'][0]
    state=registry.status(session.actor)['clients'][0]
    with pytest.raises(ClientConflict):
        service.approve(session.actor,request['id'],metadata,scopes=['c0:read'],expected_digest=metadata.digest,
                        client_id=UUID(state['client_id']),expected_revision=state['revision'])
    result=service.approve(session.actor,request['id'],metadata,scopes=state['allowed_scopes'],expected_digest=metadata.digest,
                          client_id=UUID(state['client_id']),expected_revision=state['revision'])
    assert result['allowed_scopes']==state['allowed_scopes']
    assert service.request(session.actor,request['id'])['status']=='waiting_for_consent'
    service.decline(session.actor,request['id'])
    with pytest.raises(OnboardingRejected):
        service.approve(session.actor,request['id'],metadata,scopes=state['allowed_scopes'],expected_digest=metadata.digest)


@pytest.mark.parametrize('role',[Role.READER,Role.EDITOR])
def test_forged_admin_and_nonadmins_cannot_administer(persistent,role):
    f=persistent;owner=f['context'].actor;key=uuid4()
    with pytest.raises(PermissionDenied):f['access'].resolve(identity(f['access'],key,'member'))
    account=account_named(f['access'],owner,'member');f['access'].set_role(owner,account['id'],role)
    actor=f['access'].resolve(identity(f['access'],key,'member'));service=WorkspaceAccessService(f['grants'])
    for caller in (actor,Actor(actor.user_id,Role.ADMIN,True)):
        for action in (lambda:service.overview(caller),lambda:service.applications(caller,owner.user_id),
                       lambda:service.decline(caller,uuid4()),lambda:service.disconnect(caller,uuid4())):
            with pytest.raises(PermissionDenied):action()


def test_disconnect_preserves_other_user_and_foreign_bindings(persistent):
    from legacy_oauth import legacy_pair
    f=persistent;owner=f['context'].actor;service=WorkspaceAccessService(f['grants'])
    own=f['issue']();key=uuid4()
    with pytest.raises(PermissionDenied):f['access'].resolve(identity(f['access'],key,'other'))
    account=account_named(f['access'],owner,'other');f['access'].set_role(owner,account['id'],Role.READER)
    actor=f['access'].resolve(identity(f['access'],key,'other'))
    other=legacy_pair(f['database'],actor,f['access'].issuer,'native1',f['client'],RESOURCE,{'c0:read'})
    foreign=legacy_pair(f['database'],actor,f['access'].issuer,'foreign-native',f['client'],RESOURCE,{'c0:read'})
    with f['database'].engine.connect() as c:
        ownid=c.execute(text('SELECT grant_id FROM c0_oauth_tokens WHERE hash=:hash'),{'hash':_digest(own.access_token)}).scalar_one()
        foreignid=c.execute(text('SELECT grant_id FROM c0_oauth_tokens WHERE hash=:hash'),{'hash':_digest(foreign.access_token)}).scalar_one()
    with pytest.raises(GrantRejected):service.disconnect(owner,foreignid)
    service.disconnect(owner,ownid)
    assert f['grants'].verify(other.access_token,resource=RESOURCE).actor.user_id==actor.user_id
    assert len(service.applications(owner,actor.user_id)['applications'])==1


def test_decline_and_continue_have_one_winner(onboarding):
    from test_cimd import proof
    old,f=onboarding;session=f[-1][3];service=WorkspaceAccessService(old.grants)
    pending=old.begin(parameters(onboarding)[0]);old.submit(session,pending.request,pending.binding)
    key=service.applications(session.actor,session.actor.user_id)['applications'][0]['id']
    def run(kind):
        try:
            if kind=='decline':service.decline(session.actor,key)
            else:old.complete(session,pending.request,pending.binding,scopes={'c0:read'},verification=proof(f))
            return True
        except OnboardingRejected:return False
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(run,['decline','continue']))==[False,True]
