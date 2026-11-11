# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Batch selectors preserve the single-selector policy and original bindings."""
from uuid import UUID, uuid4
import pytest
from czero_core.identity import PermissionDenied, Role
from czero_core.operations import ScopeDenied
from czero_core.spaces import SpaceService, hold_authority
from test_spaces import spaces, create, member
from test_access import access
from test_api_keys import setup


@pytest.mark.parametrize('role', list(Role))
@pytest.mark.parametrize('minimum', list(Role))
def test_batch_matches_single_for_grants_unknown_and_shared(spaces, role, minimum):
    service, owner, _ = spaces
    actor = member(spaces, role)
    granted, denied = create(spaces)['id'], create(spaces)['id']
    service.set_grant(owner, granted, actor.user_id, Role.READER,
                      expected_revision=0, idempotency_key=uuid4().hex)
    with service.database.engine.begin() as c:
        ids = [UUID(granted), UUID(denied), uuid4(), service.shared_id(c)]
        hold_authority(c)
        try:
            batch = service.authorize_many(c, actor, ids, minimum)
        except PermissionDenied:
            with pytest.raises(PermissionDenied): actor.require(minimum)
            return
        single = {}
        for identifier in ids:
            try: single[identifier] = service.authorize(c, actor, minimum, space_id=identifier)
            except PermissionDenied: pass
        assert batch == single


def test_key_ceiling_and_revocation_fail_globally(access):
    keys, owner, shared = setup(access)
    service = SpaceService(access[1], access[0])
    private = service.create(owner, 'Batch ' + uuid4().hex, idempotency_key=uuid4().hex)
    try:
        issued = keys.create(owner, name='Batch', scopes={'c0:read'}, space_ids=[shared])
        actor = keys.verify(issued['key'], resource=keys.resource).actor
        with access[1].engine.begin() as c:
            hold_authority(c)
            found = service.authorize_many(c, actor, [shared, private['id']])
            assert set(found) == {UUID(shared)}
            assert found[UUID(shared)].api_key_binding is actor.api_key_binding
            with pytest.raises(ScopeDenied): service.authorize_many(c, actor, [shared], Role.EDITOR)
        keys.revoke(owner, issued['id'])
        with access[1].engine.begin() as c, pytest.raises(PermissionDenied):
            hold_authority(c)
            service.authorize_many(c, actor, [private['id']])
    finally:
        with access[1].engine.begin() as c:
            from sqlalchemy import text
            c.execute(text('DELETE FROM c0_spaces WHERE id=:id'), {'id': UUID(private['id'])})


@pytest.mark.parametrize('ids', [[], [uuid4()] * 2, [uuid4() for _ in range(12)], [None], ['bad']])
def test_batch_bounds(spaces, ids):
    service, owner, _ = spaces
    with service.database.engine.begin() as c, pytest.raises(ValueError):
        service.authorize_many(c, owner, ids)
