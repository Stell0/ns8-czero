# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persist verified accounts and application-wide memberships in PostgreSQL."""
import time
from uuid import UUID, uuid4

from sqlalchemy import text

from .database import Database
from .identity import Actor, PermissionDenied, Role, VerifiedIdentity


class AccessService:
    """One configured issuer/owner and three roles for the shared instance.

    Native NS8 configuration supplies the owner's LDAP UUID. Names remain
    display metadata; they never assign access. Every privileged operation
    rechecks persisted membership, including calls with a stale Actor.
    """

    def __init__(self, database: Database, issuer: str, owner_account_key: UUID):
        self.database = database
        self.issuer = issuer
        self.owner_account_key = UUID(str(owner_account_key))

    def resolve(self, identity: VerifiedIdentity) -> Actor:
        if identity.issuer != self.issuer or identity.expires_at <= time.time():
            raise PermissionDenied()
        # Keep an authenticated, unadmitted profile for owner-reviewed sharing.
        # Commit the identity separately; recording it confers no permission.
        with self.database.engine.begin() as connection:
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
            current = self._actor(connection, actor.user_id)
            current.require(minimum)
            return current

    def list_accounts(self, actor: Actor, *, limit: int = 100) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid_limit")
        with self.database.engine.connect() as connection:
            self._actor(connection, actor.user_id).require(Role.ADMIN)
            rows = connection.execute(text("""
                SELECT a.id, a.username, a.display_name, a.account_key,
                       CASE WHEN a.account_key = :owner THEN 'admin' ELSE m.role END AS role,
                       a.account_key = :owner AS is_owner
                FROM c0_accounts a LEFT JOIN c0_memberships m ON m.account_id = a.id
                WHERE a.issuer = :issuer ORDER BY a.username, a.id LIMIT :limit
            """), {"owner": self.owner_account_key, "issuer": self.issuer, "limit": limit}).mappings().all()
            return [dict(row) for row in rows]

    def set_role(self, actor: Actor, account_id: UUID, role: Role | None) -> None:
        if role is not None and not isinstance(role, Role):
            raise ValueError("invalid_role")
        with self.database.engine.begin() as connection:
            # Rare administrative changes serialize before acquiring account
            # locks, avoiding opposing-admin deadlocks and stale-role writes.
            connection.execute(text("SELECT pg_advisory_xact_lock(49372)"))
            self._actor(connection, actor.user_id).require(Role.ADMIN)
            target = connection.execute(text("""
                SELECT account_key FROM c0_accounts WHERE id = :id AND issuer = :issuer
                FOR UPDATE
            """), {"id": account_id, "issuer": self.issuer}).scalar_one_or_none()
            if target is None:
                raise ValueError("account_not_found")
            if target == self.owner_account_key:
                raise PermissionDenied()
            if role is None:
                connection.execute(text("DELETE FROM c0_memberships WHERE account_id = :id"), {"id": account_id})
            else:
                connection.execute(text("""
                    INSERT INTO c0_memberships (account_id, role) VALUES (:id, :role)
                    ON CONFLICT (account_id) DO UPDATE SET role = EXCLUDED.role
                """), {"id": account_id, "role": role.value})
