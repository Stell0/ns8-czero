# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from czero_core.access import AccessService
from czero_core.identity import PermissionDenied, Role
from czero_core.spaces import SpaceService
from test_access import access, identity, owner_actor, account_named

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def open_access(fixture):
    service, database, owner_key = fixture
    return AccessService(database, service.issuer, owner_key, admit_readers=True)


def test_admission_is_explicit_for_core_consumers(access):
    closed, _, _ = access
    key = uuid4()
    with pytest.raises(PermissionDenied):
        closed.resolve(identity(closed, key, 'new-reader'))
    service = open_access(access)
    reader = service.resolve(identity(service, key, 'new-reader'))
    assert reader.role is Role.READER and not reader.is_owner
    with pytest.raises(PermissionDenied):
        service.authorize(reader, Role.EDITOR)


def test_concurrent_first_signins_keep_one_identity_and_membership(access):
    service = open_access(access)
    value = identity(service, uuid4(), 'concurrent-reader')
    with ThreadPoolExecutor(max_workers=4) as pool:
        actors = list(pool.map(lambda _: service.resolve(value), range(8)))
    assert len({a.user_id for a in actors}) == 1
    with service.database.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM c0_memberships WHERE account_id=:id'),
                         {'id': actors[0].user_id}).scalar_one() == 1


@pytest.mark.parametrize('role', list(Role))
def test_existing_explicit_roles_are_never_replaced_by_default(access, role):
    service = open_access(access)
    owner = owner_actor(access)
    value = identity(service, uuid4(), 'explicit-role')
    member = service.resolve(value)
    service.set_role(owner, member.user_id, role)
    assert service.resolve(value).role is role


def test_block_survives_repeat_renamed_and_concurrent_signin_until_explicit_regrant(access):
    service = open_access(access)
    owner = owner_actor(access)
    value = identity(service, uuid4(), 'blocked-reader')
    stale = service.resolve(value)
    service.set_role(owner, stale.user_id, None)
    def denied(_):
        try: service.resolve(replace(value, username='renamed-blocked'))
        except PermissionDenied: return True
        return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(denied, range(8)))
    with pytest.raises(PermissionDenied):
        service.authorize(stale, Role.READER)
    assert account_named(service, owner, 'renamed-blocked')['role'] is None
    service.set_role(owner, stale.user_id, Role.EDITOR)
    assert service.resolve(value).role is Role.EDITOR


@pytest.mark.parametrize('change', [{'issuer': 'https://wrong.example.test'}, {'expires_at': 0}])
def test_unverified_domain_or_expired_identity_never_gains_membership(access, change):
    service = open_access(access)
    owner = owner_actor(access)
    before = service.list_accounts(owner)
    with pytest.raises(PermissionDenied):
        service.resolve(replace(identity(service, uuid4(), 'invalid-reader'), **change))
    assert service.list_accounts(owner) == before


def test_default_reader_has_shared_only_and_no_administration(access):
    service = open_access(access)
    owner = owner_actor(access)
    spaces = SpaceService(service.database, service)
    protected = spaces.create(owner, 'Private ' + uuid4().hex, idempotency_key=uuid4().hex)
    reader = service.resolve(identity(service, uuid4(), 'shared-reader'))
    visible = spaces.list(reader)['spaces']
    assert len(visible) == 1 and visible[0]['shared']
    with service.database.engine.connect() as connection:
        with pytest.raises(PermissionDenied):
            spaces.authorize(connection, reader, space_id=protected['id'])
    with pytest.raises(PermissionDenied):
        service.list_accounts(reader)
    with service.database.engine.begin() as connection:
        connection.execute(text('DELETE FROM c0_space_receipts WHERE actor_id=:id'), {'id': owner.user_id})
        connection.execute(text('DELETE FROM c0_spaces WHERE id=:id'), {'id': protected['id']})
