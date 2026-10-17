# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persisted protected-space grants; selectors never supply authority."""
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.spaces import SpaceConflict, SpaceService
from test_access import access, account_named, identity, record_unadmitted
from test_auth_http import application
from test_oauth_grants import grants, issue, redeem, RESOURCE
from czero_core.oauth_grants import GrantRejected
from czero_core.operations import ScopeDenied
from czero_core.sessions import SessionContext
from datetime import datetime, timezone

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def spaces(access):
    accounts, database, key = access
    owner = accounts.resolve(identity(accounts, key))
    service = SpaceService(database, accounts)
    owned = []
    yield service, owner, owned
    with database.engine.begin() as c:
        for identifier in owned:
            c.execute(text('DELETE FROM c0_space_receipts WHERE result->>\'id\'=:id'), {'id': identifier})
            c.execute(text('DELETE FROM c0_space_grants WHERE space_id=:id'), {'id': UUID(identifier)})
            c.execute(text('DELETE FROM c0_spaces WHERE id=:id'), {'id': UUID(identifier)})
        c.execute(text('''DELETE FROM c0_space_receipts WHERE actor_id IN
            (SELECT id FROM c0_accounts WHERE issuer=:issuer)'''), {'issuer': accounts.issuer})


def create(fixture, **changes):
    service, owner, owned = fixture
    values = {'name': 'Investigation ' + uuid4().hex, 'idempotency_key': uuid4().hex, **changes}
    result = service.create(owner, **values)
    if result['id'] not in owned:
        owned.append(result['id'])
    return result


def member(fixture, role):
    service, owner, _ = fixture
    key = uuid4(); name = 'space-member-' + key.hex
    record_unadmitted(service.access, key, name)
    account = account_named(service.access, owner, name)
    service.access.set_role(owner, account['id'], role)
    return service.access.resolve(identity(service.access, key, name))


def authorized(service, actor, space, role=Role.READER):
    with service.database.engine.connect() as c:
        return service.authorize(c, actor, role, space_id=space)


def test_existing_identity_is_shared_and_creation_replays_without_overwriting(spaces):
    service, owner, _ = spaces
    with service.database.engine.connect() as c:
        old_id = c.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one()
    shared = next(s for s in service.list(owner)['spaces'] if s['shared'])
    assert shared['id'] == str(old_id) and shared['role'] == 'admin'
    request = {'name': 'Investigation ' + uuid4().hex, 'idempotency_key': uuid4().hex}
    first = create(spaces, **request)
    assert service.create(owner, **request) == first
    with pytest.raises(SpaceConflict):
        service.create(owner, **{**request, 'name': 'Changed'})
    with pytest.raises(SpaceConflict):
        service.create(owner, **{**request, 'idempotency_key': uuid4().hex})
    assert not first['shared'] and first['role'] == 'admin'
    assert authorized(service, owner, first['id'], Role.ADMIN).is_owner
    assert authorized(service, owner, None).role is Role.ADMIN


@pytest.mark.parametrize('role', list(Role))
def test_discovery_grants_and_current_application_role_cap(spaces, role):
    service, owner, _ = spaces
    actor = member(spaces, role); private = create(spaces)
    forged = Actor(actor.user_id, Role.ADMIN, True)
    discovered = service.list(forged)['spaces']
    assert all(s['shared'] for s in discovered) if role is not Role.ADMIN else any(s['id'] == private['id'] for s in discovered)
    if role is Role.ADMIN:
        assert authorized(service, forged, private['id'], Role.ADMIN).role is Role.ADMIN
    else:
        with pytest.raises(PermissionDenied): authorized(service, forged, private['id'])
        with pytest.raises(PermissionDenied): service.create(forged, 'Forbidden', idempotency_key=uuid4().hex)
        grant = service.set_grant(owner, private['id'], actor.user_id, role,
                                  expected_revision=0, idempotency_key=uuid4().hex)
        assert grant['role'] == role.value and grant['revision'] == 1
        assert authorized(service, forged, private['id'], role).role is role
        if role is Role.EDITOR:
            service.access.set_role(owner, actor.user_id, Role.READER)
            assert authorized(service, forged, private['id']).role is Role.READER
            with pytest.raises(PermissionDenied): authorized(service, forged, private['id'], Role.EDITOR)
    service.access.set_role(owner, actor.user_id, None)
    with pytest.raises(PermissionDenied): authorized(service, forged, private['id'])
    with pytest.raises(PermissionDenied): service.list(forged)


def test_grant_revision_tombstones_replay_and_unknown_selectors_fail_closed(spaces):
    service, owner, _ = spaces
    actor = member(spaces, Role.EDITOR); private = create(spaces)
    request = {'expected_revision': 0, 'idempotency_key': uuid4().hex}
    first = service.set_grant(owner, private['id'], actor.user_id, Role.EDITOR, **request)
    revoked = service.set_grant(owner, private['id'], actor.user_id, None,
                                expected_revision=1, idempotency_key=uuid4().hex)
    assert revoked['revision'] == 2 and revoked['role'] is None
    assert service.set_grant(owner, private['id'], actor.user_id, Role.EDITOR, **request) == first
    with pytest.raises(PermissionDenied): authorized(service, actor, private['id'])
    with pytest.raises(SpaceConflict):
        service.set_grant(owner, private['id'], actor.user_id, Role.EDITOR,
                          expected_revision=0, idempotency_key=uuid4().hex)
    for value in (str(uuid4()), str(UUID(int=0))):
        with pytest.raises(PermissionDenied): authorized(service, actor, value)
    for value in ('', 'invalid', 1, True, {}, []):
        with pytest.raises(ValueError): authorized(service, owner, value)
    with pytest.raises(PermissionDenied): service.list_grants(actor, private['id'])
    grants = service.list_grants(owner, private['id'])['grants']
    assert len(grants) == 1 and grants[0] == revoked


def test_two_administrators_cannot_overwrite_a_grant_revision(spaces):
    service, owner, _ = spaces
    admin = member(spaces, Role.ADMIN); editor = member(spaces, Role.EDITOR)
    private = create(spaces)
    def change(actor, role):
        try:
            return service.set_grant(actor, private['id'], editor.user_id, role,
                                     expected_revision=0, idempotency_key=uuid4().hex)
        except SpaceConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(change, owner, Role.READER)
        second = pool.submit(change, admin, Role.EDITOR)
        results = [first.result(), second.result()]
    assert sum(r is not None for r in results) == 1
    assert service.list_grants(owner, private['id'])['grants'][0]['revision'] == 1


@pytest.fixture
def delegated_space(grants):
    tokens, _, client, session, clock, *_ = grants
    service = SpaceService(tokens.access.database, tokens.access)
    private = service.create(session.actor, 'Delegated investigation ' + uuid4().hex,
                             idempotency_key=uuid4().hex)
    key = uuid4(); name = 'delegated-space-' + key.hex
    record_unadmitted(tokens.access, key, name)
    account = account_named(tokens.access, session.actor, name)
    tokens.access.set_role(session.actor, account['id'], Role.EDITOR)
    editor = tokens.access.resolve(identity(tokens.access, key, name))
    native = SessionContext(editor, datetime.fromtimestamp(clock[0] + 600, timezone.utc), 'fixture-only-csrf')
    first = service.set_grant(session.actor, private['id'], editor.user_id, Role.EDITOR,
                              expected_revision=0, idempotency_key=uuid4().hex)
    yield service, private, editor, native, first, grants
    with service.database.engine.begin() as c:
        c.execute(text('''DELETE FROM c0_space_receipts WHERE actor_id IN
            (SELECT id FROM c0_accounts WHERE issuer=:issuer)'''), {'issuer': service.access.issuer})
        c.execute(text('DELETE FROM c0_spaces WHERE id=:id'), {'id': UUID(private['id'])})


def test_captured_delegated_actor_cannot_revive_after_grant_regrant(delegated_space):
    service, private, editor, native, _, fixture = delegated_space
    tokens, _, client, owner_session, *_ = fixture
    pair = redeem(tokens, client, issue(tokens, client, native, scopes={'c0:read', 'c0:write'}))
    delegated = tokens.verify(pair.access_token, resource=RESOURCE).actor
    assert authorized(service, delegated, private['id'], Role.EDITOR).role is Role.EDITOR
    service.set_grant(owner_session.actor, private['id'], editor.user_id, None,
                       expected_revision=1, idempotency_key=uuid4().hex)
    with pytest.raises(GrantRejected): tokens.verify(pair.access_token, resource=RESOURCE)
    with pytest.raises(PermissionDenied): service.access.authorize(delegated, Role.READER)
    service.set_grant(owner_session.actor, private['id'], editor.user_id, Role.EDITOR,
                       expected_revision=2, idempotency_key=uuid4().hex)
    with pytest.raises(PermissionDenied): authorized(service, delegated, private['id'], Role.EDITOR)
    assert authorized(service, editor, private['id'], Role.EDITOR).role is Role.EDITOR


def test_effective_space_role_precedes_scope_challenge(delegated_space):
    service, private, editor, native, _, fixture = delegated_space
    tokens, _, client, owner_session, *_ = fixture
    pair = redeem(tokens, client, issue(tokens, client, native, scopes={'c0:read'}))
    delegated = tokens.verify(pair.access_token, resource=RESOURCE).actor
    with pytest.raises(ScopeDenied) as denied:
        authorized(service, delegated, private['id'], Role.EDITOR)
    assert denied.value.scope == 'c0:write'
    service.set_grant(owner_session.actor, private['id'], editor.user_id, Role.READER,
                       expected_revision=1, idempotency_key=uuid4().hex)
    pair = redeem(tokens, client, issue(tokens, client, native, scopes={'c0:read'}))
    delegated = tokens.verify(pair.access_token, resource=RESOURCE).actor
    with pytest.raises(PermissionDenied) as denied:
        authorized(service, delegated, private['id'], Role.EDITOR)
    assert not isinstance(denied.value, ScopeDenied)


def test_write_only_authority_is_not_blocked_by_a_global_read_scope(delegated_space):
    service, private, _, native, _, fixture = delegated_space
    tokens, _, client, _, _, app, _ = fixture
    pair = redeem(tokens, client, issue(tokens, client, native, scopes={'c0:write'}))
    delegated = tokens.verify(pair.access_token, resource=RESOURCE).actor
    assert authorized(service, delegated, private['id'], Role.EDITOR).role is Role.EDITOR
    with pytest.raises(ScopeDenied) as denied:
        authorized(service, delegated, private['id'])
    assert denied.value.scope == 'c0:read'
    descriptions = app.state.operations.describe(delegated, scopes={'c0:read', 'c0:write', 'c0:admin'})
    assert {'wiki_pages_resolve', 'wiki_pages_upsert'} <= {d['name'] for d in descriptions}
    assert pair.access_token not in repr(delegated) and pair.refresh_token not in repr(delegated)
