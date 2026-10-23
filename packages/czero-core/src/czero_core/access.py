# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persist verified accounts and application-wide memberships in PostgreSQL."""
import time
from dataclasses import replace
from uuid import UUID, uuid4

from sqlalchemy import text

from .database import Database
from .identity import Actor, PermissionDenied, Role, VerifiedIdentity
from .spaces import require_scope


class AccessService:
    """One configured issuer/owner and three roles for the shared instance.

    Native NS8 configuration supplies the owner's LDAP UUID. Names remain
    display metadata; they never assign access. Every privileged operation
    rechecks persisted membership, including calls with a stale Actor.
    """

    def __init__(self, database: Database, issuer: str, owner_account_key: UUID, *, admit_readers=False):
        if type(admit_readers) is not bool:
            raise ValueError('invalid_admission_policy')
        self.database = database
        self.issuer = issuer
        self.owner_account_key = UUID(str(owner_account_key))
        self.admit_readers = admit_readers

    def resolve(self, identity: VerifiedIdentity) -> Actor:
        if (not isinstance(identity, VerifiedIdentity) or identity.issuer != self.issuer
                or identity.expires_at <= time.time()):
            raise PermissionDenied()
        # Keep an authenticated, unadmitted profile for owner-reviewed sharing.
        # Commit the identity separately; recording it confers no permission.
        with self.database.engine.begin() as connection:
            if self.admit_readers:
                connection.execute(text('SELECT pg_advisory_xact_lock(49372)'))
            user_id = connection.execute(text("""
                INSERT INTO c0_accounts (id, issuer, account_key, subject, username, display_name)
                VALUES (:id, :issuer, :key, :subject, :username, :display_name)
                ON CONFLICT (issuer, account_key) DO UPDATE
                SET subject = EXCLUDED.subject, username = EXCLUDED.username,
                    display_name = EXCLUDED.display_name, last_seen = now()
                RETURNING id
            """), {"id": uuid4(), "issuer": self.issuer, "key": UUID(identity.account_key),
                   "subject": identity.subject, "username": identity.username,
                   "display_name": identity.display_name}).scalar_one()
            if self.admit_readers and UUID(identity.account_key) != self.owner_account_key:
                connection.execute(text('''INSERT INTO c0_memberships(account_id,role)
                    SELECT :id,'reader' WHERE NOT EXISTS
                    (SELECT 1 FROM c0_account_blocks WHERE account_id=:id)
                    ON CONFLICT(account_id) DO NOTHING'''), {'id': user_id})
        with self.database.engine.connect() as connection:
            return self._actor(connection, user_id)

    def _actor(self, connection, user_id: UUID) -> Actor:
        row = connection.execute(text("""
            SELECT a.account_key, m.role FROM c0_accounts a
            LEFT JOIN c0_memberships m ON m.account_id = a.id
            WHERE a.id = :id AND a.issuer = :issuer
        """), {"id": user_id, "issuer": self.issuer}).mappings().one_or_none()
        if row is None:
            raise PermissionDenied()
        if row["account_key"] == self.owner_account_key:
            return Actor(user_id, Role.ADMIN, True)
        if row["role"] is None:
            raise PermissionDenied()
        return Actor(user_id, Role(row["role"]))

    def authorize(self, actor: Actor, minimum: Role) -> Actor:
        """Revalidate a caller at a shared service boundary."""
        with self.database.engine.connect() as connection:
            current = self.checked_actor(connection, actor)
            current.require(minimum)
            return current

    def checked_actor(self, connection, actor):
        """Refresh membership without losing a captured delegated token binding.

        Native adapters still supply trusted first-party Actors. A delegated
        Actor retains only a masked hash and trusted Core verifier; its original
        access token/grant must remain valid in this very transaction. A later
        role/space regrant cannot revive a token already deleted by revocation.
        """
        if not isinstance(actor, Actor):
            raise PermissionDenied()
        # Session/delegation checks hold the final revocation lock through
        # the caller's transaction, including non-content administrative writes.
        if actor.session_binding is not None or actor.delegation is not None:
            connection.execute(text('SELECT pg_advisory_xact_lock_shared(49382)'))
        current = self._actor(connection, actor.user_id)
        if actor.delegation is not None:
            from .oauth_grants import DelegationBinding, GrantRejected
            if not isinstance(actor.delegation, DelegationBinding):
                raise PermissionDenied()
            try:
                delegated = actor.delegation.validate(connection)
            except GrantRejected:
                raise PermissionDenied() from None
            if delegated.actor.user_id != current.user_id or delegated.issuer != self.issuer:
                raise PermissionDenied()
            current = replace(current, delegation=actor.delegation,
                              delegated_scopes=delegated.scopes)
        if actor.session_binding is not None:
            from .sessions import SessionBinding, SessionRejected
            from .renewal import RenewalRejected
            if not isinstance(actor.session_binding, SessionBinding):
                raise PermissionDenied()
            try:
                session = actor.session_binding.validate(connection)
            except (SessionRejected, RenewalRejected):
                raise PermissionDenied() from None
            if (session.actor.user_id != current.user_id
                    or actor.session_binding.service.access.issuer != self.issuer):
                raise PermissionDenied()
            current = replace(current, session_binding=actor.session_binding)
        return current

    def list_accounts(self, actor: Actor, *, limit: int = 100) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid_limit")
        with self.database.engine.connect() as connection:
            current = self.checked_actor(connection, actor)
            current.require(Role.ADMIN)
            require_scope(current, Role.ADMIN)
            rows = connection.execute(text("""
                SELECT a.id, a.username, a.display_name, a.account_key, a.last_seen,
                       CASE WHEN a.account_key = :owner THEN 'admin' ELSE m.role END AS role,
                       a.account_key = :owner AS is_owner
                FROM c0_accounts a LEFT JOIN c0_memberships m ON m.account_id = a.id
                WHERE a.issuer = :issuer ORDER BY a.username, a.id LIMIT :limit
            """), {"owner": self.owner_account_key, "issuer": self.issuer, "limit": limit}).mappings().all()
            return [dict(row) for row in rows]

    def profile(self, actor: Actor) -> dict:
        with self.database.engine.connect() as connection:
            current = self.checked_actor(connection, actor)
            current.require(Role.READER)
            require_scope(current, Role.READER)
            row = connection.execute(text("""
                SELECT id, username, display_name FROM c0_accounts
                WHERE id = :id AND issuer = :issuer
            """), {"id": actor.user_id, "issuer": self.issuer}).mappings().one()
            return {**dict(row), "role": current.role.value, "is_owner": current.is_owner}

    def set_role(self, actor: Actor, account_id: UUID, role: Role | None) -> None:
        if role is not None and not isinstance(role, Role):
            raise ValueError("invalid_role")
        with self.database.engine.begin() as connection:
            # Rare administrative changes serialize before acquiring account
            # locks, avoiding opposing-admin deadlocks and stale-role writes.
            connection.execute(text("SELECT pg_advisory_xact_lock(49372)"))
            current = self.checked_actor(connection, actor)
            current.require(Role.ADMIN)
            require_scope(current, Role.ADMIN)
            target = connection.execute(text("""
                SELECT account_key FROM c0_accounts WHERE id = :id AND issuer = :issuer
                FOR UPDATE
            """), {"id": account_id, "issuer": self.issuer}).scalar_one_or_none()
            if target is None:
                raise ValueError("account_not_found")
            if target == self.owner_account_key:
                raise PermissionDenied()
            # Delegation never survives a membership change, including a later
            # regrant of the same role. Grant issuance takes this role lock too.
            connection.execute(text('DELETE FROM c0_oauth_grants WHERE account_id=:id'), {'id': account_id})
            connection.execute(text('UPDATE c0_native_authority SET revoked=true,credential=NULL,checking=false WHERE account_id=:id'),
                               {'id': account_id})
            if role is None:
                connection.execute(text('INSERT INTO c0_account_blocks(account_id) VALUES (:id) ON CONFLICT DO NOTHING'),
                                   {'id': account_id})
                connection.execute(text("DELETE FROM c0_memberships WHERE account_id = :id"), {"id": account_id})
            else:
                connection.execute(text('DELETE FROM c0_account_blocks WHERE account_id=:id'), {'id': account_id})
                connection.execute(text("""
                    INSERT INTO c0_memberships (account_id, role) VALUES (:id, :role)
                    ON CONFLICT (account_id) DO UPDATE SET role = EXCLUDED.role
                """), {"id": account_id, "role": role.value})
