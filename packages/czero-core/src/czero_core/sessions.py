# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""One-use browser login state and opaque, expiring server sessions."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import secrets
import time
from typing import Callable

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


def _digest(value: str) -> str:
    if not isinstance(value, str) or not value.isascii() or not 1 <= len(value) <= 128:
        raise ValueError("invalid_secret")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _date(value: float) -> datetime:
    return datetime.fromtimestamp(value, timezone.utc)


class SessionService:
    def __init__(self, access: AccessService, client_id: str, *,
                 now: Callable[[], float] = time.time, max_session_seconds: int = 3600):
        if not isinstance(client_id, str) or not 1 <= len(client_id) <= 128:
            raise ValueError("invalid_client")
        if type(max_session_seconds) is not int or not 60 <= max_session_seconds <= 3600:
            raise ValueError("invalid_session_limit")
        self.access = access
        self.client_id = client_id
        self._now = now
        self.max_session_seconds = max_session_seconds

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

    def create(self, identity: VerifiedIdentity) -> str:
        current = self._now()
        expires = min(identity.expires_at, current + self.max_session_seconds)
        if expires <= current:
            raise SessionRejected()
        actor = self.access.resolve(identity)
        cookie = secrets.token_urlsafe(32)
        with self.access.database.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO c0_sessions (token_hash, account_id, csrf_token, issuer, client_id, expires_at)
                VALUES (:token, :account, :csrf, :issuer, :client, :expires)
            """), {"token": _digest(cookie), "account": actor.user_id, "csrf": secrets.token_urlsafe(32),
                   "issuer": self.access.issuer, "client": self.client_id, "expires": _date(expires)})
        return cookie

    def get(self, cookie: str) -> SessionContext:
        try:
            hashed = _digest(cookie)
        except ValueError:
            raise SessionRejected() from None
        with self.access.database.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT account_id, csrf_token, expires_at FROM c0_sessions
                WHERE token_hash = :token AND issuer = :issuer AND client_id = :client AND expires_at > :now
            """), {"token": hashed, "issuer": self.access.issuer, "client": self.client_id,
                   "now": _date(self._now())}).mappings().one_or_none()
        if row is None:
            raise SessionRejected()
        # A role stored in a browser/session never confers authority.
        actor = self.access.authorize(Actor(row["account_id"], Role.READER), Role.READER)
        return SessionContext(actor, row["expires_at"], row["csrf_token"])

    def destroy(self, cookie: str) -> None:
        try:
            hashed = _digest(cookie)
        except ValueError:
            return
        with self.access.database.engine.begin() as connection:
            connection.execute(text("""
                DELETE FROM c0_sessions WHERE token_hash = :token AND issuer = :issuer AND client_id = :client
            """), {"token": hashed, "issuer": self.access.issuer, "client": self.client_id})

    @staticmethod
    def check_csrf(context: SessionContext, supplied: str | None) -> None:
        if not isinstance(supplied, str) or not 1 <= len(supplied) <= 128:
            raise PermissionDenied()
        if not hmac.compare_digest(supplied.encode(), context.csrf_token.encode()):
            raise PermissionDenied()
