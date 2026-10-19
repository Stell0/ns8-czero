# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""One-use browser login state and opaque, expiring server sessions."""
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import hmac
import secrets
import time
from typing import Callable
from uuid import UUID

from sqlalchemy import text

from .access import AccessService
from .identity import Actor, PermissionDenied, Role, VerifiedIdentity


class LoginStateRejected(ValueError):
    def __init__(self):
        super().__init__("invalid_login_state")


class SessionRejected(ValueError):
    def __init__(self):
        super().__init__("invalid_session")


@dataclass(frozen=True)
class PendingLogin:
    state: str = field(repr=False)
    browser_binding: str = field(repr=False)
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)


@dataclass(frozen=True)
class LoginSecrets:
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)


@dataclass(frozen=True)
class SessionContext:
    actor: Actor
    expires_at: datetime
    csrf_token: str = field(repr=False)
    native_authority_id: UUID | None = field(default=None, repr=False)


@dataclass(frozen=True, repr=False)
class SessionBinding:
    """Private browser attestation rechecked inside every Core transaction."""
    service: object = field(repr=False)
    digest: str = field(repr=False)

    def validate(self, connection):
        if not isinstance(self.service, SessionService):
            raise SessionRejected()
        return self.service._context(connection, self.digest)


def _digest(value: str) -> str:
    if not isinstance(value, str) or not value.isascii() or not 1 <= len(value) <= 128:
        raise ValueError("invalid_secret")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _date(value: float) -> datetime:
    return datetime.fromtimestamp(value, timezone.utc)


class SessionService:
    def __init__(self, access: AccessService, client_id: str, *,
                 now: Callable[[], float] = time.time, max_session_seconds: int = 3600, authority=None):
        if not isinstance(client_id, str) or not 1 <= len(client_id) <= 128:
            raise ValueError("invalid_client")
        if type(max_session_seconds) is not int or not 60 <= max_session_seconds <= 3600:
            raise ValueError("invalid_session_limit")
        self.access = access
        self.client_id = client_id
        self._now = now
        self.authority = authority
        if authority is not None:
            from .renewal import NativeAuthorityService
            if (not isinstance(authority, NativeAuthorityService) or authority.access is not access
                    or authority.client_id != client_id):
                raise ValueError('invalid_renewal_configuration')
        self.max_session_seconds = authority.policy.absolute_seconds if authority else max_session_seconds
        self._fixed_session_seconds = min(max_session_seconds, self.max_session_seconds)

    def begin_login(self) -> PendingLogin:
        pending = PendingLogin(*(secrets.token_urlsafe(32) for _ in range(4)))
        current = self._now()
        with self.access.database.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(49373)"))
            connection.execute(text("DELETE FROM c0_login_states WHERE expires_at <= :now"), {"now": _date(current)})
            count = connection.execute(text("""
                SELECT count(*) FROM c0_login_states WHERE issuer = :issuer AND client_id = :client
            """), {"issuer": self.access.issuer, "client": self.client_id}).scalar_one()
            if count >= 1000:
                raise LoginStateRejected()
            connection.execute(text("""
                INSERT INTO c0_login_states
                (state_hash, browser_hash, nonce, code_verifier, issuer, client_id, expires_at)
                VALUES (:state, :browser, :nonce, :verifier, :issuer, :client, :expires)
            """), {"state": _digest(pending.state), "browser": _digest(pending.browser_binding),
                   "nonce": pending.nonce, "verifier": pending.code_verifier,
                   "issuer": self.access.issuer, "client": self.client_id, "expires": _date(current + 300)})
        return pending

    def consume_login(self, state: str, browser_binding: str) -> LoginSecrets:
        try:
            parameters = {"state": _digest(state), "browser": _digest(browser_binding),
                          "issuer": self.access.issuer, "client": self.client_id, "now": _date(self._now())}
        except ValueError:
            raise LoginStateRejected() from None
        with self.access.database.engine.begin() as connection:
            row = connection.execute(text("""
                DELETE FROM c0_login_states WHERE state_hash = :state AND browser_hash = :browser
                AND issuer = :issuer AND client_id = :client AND expires_at > :now
                RETURNING nonce, code_verifier
            """), parameters).mappings().one_or_none()
            if row is None:
                raise LoginStateRejected()
        return LoginSecrets(row["nonce"], row["code_verifier"])

    def create(self, identity: VerifiedIdentity, *, renewal=None) -> str:
        current = self._now()
        expires = min(identity.expires_at, current + self._fixed_session_seconds)
        if expires <= current:
            raise SessionRejected()
        actor = self.access.resolve(identity)
        cookie = secrets.token_urlsafe(32)
        with self.access.database.engine.begin() as connection:
            native_id = None
            if renewal is not None:
                from .renewal import RenewalRejected, RenewalResult
                if self.authority is None or not isinstance(renewal, RenewalResult) or renewal.identity != identity:
                    raise RenewalRejected()
                native_id, absolute = self.authority.create(connection, actor, renewal)
                expires = absolute.timestamp()
            connection.execute(text("""
                INSERT INTO c0_sessions (token_hash, account_id, csrf_token, issuer, client_id, expires_at, native_authority_id)
                VALUES (:token, :account, :csrf, :issuer, :client, :expires, :native)
            """), {"token": _digest(cookie), "account": actor.user_id, "csrf": secrets.token_urlsafe(32),
                   "issuer": self.access.issuer, "client": self.client_id, "expires": _date(expires), "native": native_id})
        return cookie

    def get(self, cookie: str) -> SessionContext:
        try:
            hashed = _digest(cookie)
        except ValueError:
            raise SessionRejected() from None
        with self.access.database.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT account_id, csrf_token, expires_at, native_authority_id FROM c0_sessions
                WHERE token_hash = :token AND issuer = :issuer AND client_id = :client AND expires_at > :now
            """), {"token": hashed, "issuer": self.access.issuer, "client": self.client_id,
                   "now": _date(self._now())}).mappings().one_or_none()
        if row is None:
            raise SessionRejected()
        if row['native_authority_id'] is not None:
            if self.authority is None:
                raise SessionRejected()
            self.authority.authenticate(row['native_authority_id'])
            # A concurrent logout must win over an in-flight provider reply.
            with self.access.database.engine.connect() as connection:
                if not connection.execute(text('SELECT 1 FROM c0_sessions WHERE token_hash=:token'),
                                          {'token': hashed}).scalar_one_or_none():
                    raise SessionRejected()
                self.authority.peek(connection, row['native_authority_id'], account_id=row['account_id'])
        with self.access.database.engine.connect() as connection:
            context = self._context(connection, hashed)
        return replace(context, actor=replace(context.actor, session_binding=SessionBinding(self, hashed)))

    def _context(self, connection, hashed):
        row = connection.execute(text("""SELECT account_id,csrf_token,expires_at,native_authority_id
            FROM c0_sessions WHERE token_hash=:token AND issuer=:issuer AND client_id=:client
            AND expires_at>:now"""), {'token': hashed, 'issuer': self.access.issuer,
                'client': self.client_id, 'now': _date(self._now())}).mappings().one_or_none()
        if row is None:
            raise SessionRejected()
        if row['native_authority_id'] is not None:
            if self.authority is None:
                raise SessionRejected()
            self.authority.peek(connection, row['native_authority_id'], account_id=row['account_id'])
        actor = self.access._actor(connection, row['account_id'])
        actor.require(Role.READER)
        return SessionContext(actor, row['expires_at'], row['csrf_token'], row['native_authority_id'])

    def destroy(self, cookie: str) -> None:
        self._destroy(cookie)

    def logout(self, cookie: str, supplied_csrf: str | None) -> None:
        """Revoke only this cookie's authority without contacting the provider."""
        self._destroy(cookie, supplied_csrf=supplied_csrf, csrf_required=True)

    def _destroy(self, cookie, *, supplied_csrf=None, csrf_required=False):
        try:
            hashed = _digest(cookie)
        except ValueError:
            if csrf_required:
                raise SessionRejected() from None
            return
        with self.access.database.engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(49382)'))
            row = connection.execute(text("""SELECT csrf_token,native_authority_id FROM c0_sessions
                WHERE token_hash=:token AND issuer=:issuer AND client_id=:client FOR UPDATE"""),
                {'token': hashed, 'issuer': self.access.issuer, 'client': self.client_id}).mappings().one_or_none()
            if row is None:
                if csrf_required:
                    raise SessionRejected()
                return
            if csrf_required:
                self._check_csrf(row['csrf_token'], supplied_csrf)
            connection.execute(text('DELETE FROM c0_sessions WHERE token_hash=:token'), {'token': hashed})
            if row['native_authority_id'] is not None:
                connection.execute(text("""UPDATE c0_native_authority
                    SET revoked=true,credential=NULL,checking=false WHERE id=:id"""), {'id': row['native_authority_id']})

    @staticmethod
    def check_csrf(context: SessionContext, supplied: str | None) -> None:
        SessionService._check_csrf(context.csrf_token, supplied)

    @staticmethod
    def _check_csrf(expected, supplied):
        if not isinstance(supplied, str) or not 1 <= len(supplied) <= 128:
            raise PermissionDenied()
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise PermissionDenied()
