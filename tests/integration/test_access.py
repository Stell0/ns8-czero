# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import Actor, PermissionDenied, Role, VerifiedIdentity
from czero_core.migrate import migrate_database

pytestmark = pytest.mark.skipif(not os.getenv("CZERO_TEST_DATABASE_URL"), reason="isolated PostgreSQL URL required")


@pytest.fixture
def access():
    database = Database(os.environ["CZERO_TEST_DATABASE_URL"])
    migrate_database(database)
    issuer = "https://idp.example.test/realms/" + str(uuid4())
    owner_key = uuid4()
    service = AccessService(database, issuer, owner_key)
    yield service, database, owner_key
    with database.engine.begin() as connection:
        connection.execute(text("DELETE FROM c0_accounts WHERE issuer = :issuer"), {"issuer": issuer})
    database.close()


def identity(service, key, username="owner", subject="provider-subject"):
    return VerifiedIdentity(service.issuer, subject, str(key), username, username.title(), time.time() + 300)


def owner_actor(access):
    service, _, key = access
    return service.resolve(identity(service, key))


def record_unadmitted(service, key, username):
    with pytest.raises(PermissionDenied):
        service.resolve(identity(service, key, username))


def account_named(service, actor, name):
    return next(account for account in service.list_accounts(actor) if account["username"] == name)


def test_owner_is_pinned_to_ldap_key_and_rename_preserves_identity(access):
    service, _, key = access
    original = owner_actor(access)
    assert original.is_owner and original.role is Role.ADMIN
    renamed = service.resolve(identity(service, key, "renamed-owner", "new-provider-subject"))
    assert renamed.user_id == original.user_id
    assert renamed.is_owner
    record_unadmitted(service, uuid4(), "owner")
    assert len(service.list_accounts(renamed)) == 2


@pytest.mark.parametrize("role", list(Role))
def test_verified_member_role_persists_and_does_not_follow_username_reuse(access, role):
    service, _, _ = access
    owner = owner_actor(access)
    key = uuid4()
    record_unadmitted(service, key, "member")
    account = account_named(service, owner, "member")
    service.set_role(owner, account["id"], role)
    member = service.resolve(identity(service, key, "member"))
    assert member.role is role and not member.is_owner
    renamed = service.resolve(identity(service, key, "renamed-member"))
    assert renamed.user_id == member.user_id and renamed.role is role
    record_unadmitted(service, uuid4(), "member")


def test_reader_editor_and_forged_actor_cannot_administer(access):
    service, _, _ = access
    owner = owner_actor(access)
    for role in (Role.READER, Role.EDITOR):
        key = uuid4()
        record_unadmitted(service, key, role.value)
        account = account_named(service, owner, role.value)
        service.set_role(owner, account["id"], role)
        member = service.resolve(identity(service, key, role.value))
        for actor in (member, Actor(member.user_id, Role.ADMIN, True)):
            with pytest.raises(PermissionDenied):
                service.list_accounts(actor)
            with pytest.raises(PermissionDenied):
                service.set_role(actor, owner.user_id, Role.ADMIN)


def test_revocation_rechecks_a_stale_actor_at_service_boundary(access):
    service, _, _ = access
    owner = owner_actor(access)
    key = uuid4()
    record_unadmitted(service, key, "administrator")
    account = account_named(service, owner, "administrator")
    service.set_role(owner, account["id"], Role.ADMIN)
    stale = service.resolve(identity(service, key, "administrator"))
    assert service.list_accounts(stale)
    service.set_role(owner, stale.user_id, None)
    with pytest.raises(PermissionDenied):
        service.list_accounts(stale)
    with pytest.raises(PermissionDenied):
        service.resolve(identity(service, key, "administrator"))


def test_owner_role_cannot_be_changed_and_invalid_target_has_no_side_effect(access):
    service, _, _ = access
    owner = owner_actor(access)
    before = service.list_accounts(owner)
    for role in (None, Role.READER):
        with pytest.raises(PermissionDenied):
            service.set_role(owner, owner.user_id, role)
    with pytest.raises(ValueError, match="account_not_found"):
        service.set_role(owner, uuid4(), Role.ADMIN)
    assert service.list_accounts(owner) == before


def test_issuer_boundary_rejects_other_domain_identity(access):
    service, _, key = access
    value = identity(service, key)
    foreign = VerifiedIdentity("https://another.example.test/realms/users", value.subject,
                               value.account_key, value.username, value.display_name, value.expires_at)
    with pytest.raises(PermissionDenied):
        service.resolve(foreign)
    assert len(service.list_accounts(owner_actor(access))) == 1


def test_user_data_uses_bound_parameters(access):
    service, database, _ = access
    owner = owner_actor(access)
    record_unadmitted(service, uuid4(), "name'; DROP TABLE c0_accounts; --")
    assert len(service.list_accounts(owner)) == 2
    assert database.health()["status"] == "ok"
