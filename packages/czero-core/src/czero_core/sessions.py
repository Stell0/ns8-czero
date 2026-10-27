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

REMEMBER_SECONDS = 7 * 86400


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
    background: bool = False
    expected_account_key: str | None = field(default=None, repr=False)
    remembered: bool = False


@dataclass(frozen=True)
class LoginSecrets:
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)
    background: bool = False
    expected_account_key: str | None = field(default=None, repr=False)
    remembered: bool = False


@dataclass(frozen=True)
class SessionContext:
    actor: Actor
    expires_at: datetime
    csrf_token: str = field(repr=False)
    native_authority_id: UUID | None = field(default=None, repr=False)
    remembered: bool = False


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

    def begin_sign_in(self):
        intent, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.access.database.engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(49373)'))
            connection.execute(text('DELETE FROM c0_signin_intents WHERE expires_at<=:now'), {'now': _date(self._now())})
            if connection.execute(text('SELECT count(*) FROM c0_signin_intents')).scalar_one() >= 1000:
                raise LoginStateRejected()
            connection.execute(text('''INSERT INTO c0_signin_intents(hash,browser_hash,issuer,client_id,expires_at)
                VALUES (:hash,:browser,:issuer,:client,:expires)'''),
                {'hash': _digest(intent), 'browser': _digest(browser), 'issuer': self.access.issuer,
                 'client': self.client_id, 'expires': _date(self._now()+300)})
        return intent, browser

    def consume_sign_in(self, intent, browser):
        try:
            parameters = {'hash': _digest(intent), 'browser': _digest(browser), 'issuer': self.access.issuer,
                          'client': self.client_id, 'now': _date(self._now())}
        except ValueError:
            raise LoginStateRejected() from None
        with self.access.database.engine.begin() as connection:
            found = connection.execute(text('''DELETE FROM c0_signin_intents WHERE hash=:hash AND browser_hash=:browser
                AND issuer=:issuer AND client_id=:client AND expires_at>:now RETURNING hash'''), parameters).scalar_one_or_none()
            if found is None:
                raise LoginStateRejected()

    def begin_login(self, *, background=False, session=None, remembered=False) -> PendingLogin:
        if type(background) is not bool or type(remembered) is not bool or remembered and self.authority is None:
            raise LoginStateRejected()
        expected = None
        if background:
            if self.authority is None or self.authority.connection_policy is None or not isinstance(session, SessionContext):
                raise LoginStateRejected()
            with self.access.database.engine.connect() as connection:
                if session.expires_at.timestamp() <= self._now():
                    raise LoginStateRejected()
                actor = self.access.checked_actor(connection, session.actor)
                expected = str(connection.execute(text('SELECT account_key FROM c0_accounts WHERE id=:id'),
                    {'id': actor.user_id}).scalar_one())
        remembered = remembered or bool(background and session.remembered)
        pending = PendingLogin(*(secrets.token_urlsafe(32) for _ in range(4)), background, expected, remembered)
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
                (state_hash, browser_hash, nonce, code_verifier, issuer, client_id, expires_at,background,expected_account_key,remembered)
                VALUES (:state, :browser, :nonce, :verifier, :issuer, :client, :expires,:background,:expected,:remembered)
            """), {"state": _digest(pending.state), "browser": _digest(pending.browser_binding),
                   "nonce": pending.nonce, "verifier": pending.code_verifier,
                   "issuer": self.access.issuer, "client": self.client_id, "expires": _date(current + 300),
                   'background': background, 'expected': expected, 'remembered': remembered})
        return pending

    def pending_login(self, state, browser_binding):
        """Resume only a previously CSRF-authorized background sign-in."""
        try:
            parameters = {'state': _digest(state), 'browser': _digest(browser_binding),
                'issuer': self.access.issuer, 'client': self.client_id, 'now': _date(self._now())}
        except ValueError:
            raise LoginStateRejected() from None
        with self.access.database.engine.connect() as connection:
            row = connection.execute(text('''SELECT nonce,code_verifier,expected_account_key,remembered FROM c0_login_states
                WHERE state_hash=:state AND browser_hash=:browser AND issuer=:issuer AND client_id=:client
                AND background AND expires_at>:now'''), parameters).mappings().one_or_none()
        if row is None or self.authority is None or self.authority.connection_policy is None:
            raise LoginStateRejected()
        return PendingLogin(state, browser_binding, row['nonce'], row['code_verifier'], True, row['expected_account_key'], row['remembered'])

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
                RETURNING nonce, code_verifier,background,expected_account_key,remembered
            """), parameters).mappings().one_or_none()
            if row is None:
                raise LoginStateRejected()
        return LoginSecrets(row["nonce"], row["code_verifier"], row['background'], row['expected_account_key'], row['remembered'])

    def create(self, identity: VerifiedIdentity, *, renewal=None, background=False, expected_account_key=None, remembered=False) -> str:
        if type(background) is not bool or background and (expected_account_key is None or identity.account_key != expected_account_key):
            raise SessionRejected()
        if type(remembered) is not bool:
            raise SessionRejected()
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
                native_id, absolute = self.authority.create(connection, actor, renewal, background=background, remembered=remembered)
                expires = current + REMEMBER_SECONDS if remembered else (absolute.timestamp() if absolute is not None else current + self.max_session_seconds)
            elif background or remembered:
                raise SessionRejected()
            connection.execute(text("""
                INSERT INTO c0_sessions (token_hash, account_id, csrf_token, issuer, client_id, expires_at, native_authority_id,
                    browser_idle_until,browser_idle_seconds,remembered)
                VALUES (:token, :account, :csrf, :issuer, :client, :expires, :native,:idle,:seconds,:remembered)
            """), {"token": _digest(cookie), "account": actor.user_id, "csrf": secrets.token_urlsafe(32),
                   "issuer": self.access.issuer, "client": self.client_id, "expires": _date(expires), "native": native_id,
                   'idle': _date(expires) if remembered else (_date(min(expires,current+self.authority.policy.idle_seconds)) if background else None),
                   'seconds': REMEMBER_SECONDS if remembered else (self.authority.policy.idle_seconds if background else None),
                   'remembered': remembered})
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
                AND (browser_idle_until IS NULL OR browser_idle_until>:now)
            """), {"token": hashed, "issuer": self.access.issuer, "client": self.client_id,
                   "now": _date(self._now())}).mappings().one_or_none()
        if row is None:
            raise SessionRejected()
        if row['native_authority_id'] is not None:
            if self.authority is None:
                raise SessionRejected()
            self.authority.authenticate(row['native_authority_id'])
        # Recheck after provider I/O. Logout and browser idle/absolute expiry
        # must win; delegated use of the offline authority cannot slide a cookie.
        with self.access.database.engine.begin() as connection:
            self._context(connection, hashed)
            connection.execute(text('''UPDATE c0_sessions
                SET browser_idle_until=LEAST(expires_at,:now + browser_idle_seconds * interval '1 second')
                WHERE token_hash=:token AND NOT remembered AND browser_idle_until>:now AND expires_at>:now'''),
                {'token':hashed,'now':_date(self._now())})
            context = self._context(connection, hashed)
        return replace(context, actor=replace(context.actor, session_binding=SessionBinding(self, hashed)))

    def renew_browser(self, cookie):
        """Slide only a successful first-party browser request, after its work."""
        try:
            hashed = _digest(cookie)
        except ValueError:
            raise SessionRejected() from None
        with self.access.database.engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock_shared(49372)'))
            connection.execute(text('SELECT pg_advisory_xact_lock(49382)'))
            context = self._context(connection, hashed)
            if context.remembered:
                connection.execute(text('''UPDATE c0_sessions SET expires_at=:expires,browser_idle_until=:expires
                    WHERE token_hash=:hash AND remembered'''),
                    {'hash': hashed, 'expires': _date(self._now()+REMEMBER_SECONDS)})
            return self._context(connection, hashed)

    def _context(self, connection, hashed):
        row = connection.execute(text("""SELECT account_id,csrf_token,expires_at,native_authority_id,browser_idle_until,remembered
            FROM c0_sessions WHERE token_hash=:token AND issuer=:issuer AND client_id=:client
            AND expires_at>:now AND (browser_idle_until IS NULL OR browser_idle_until>:now)"""), {'token': hashed, 'issuer': self.access.issuer,
                'client': self.client_id, 'now': _date(self._now())}).mappings().one_or_none()
        if row is None:
            raise SessionRejected()
        if row['native_authority_id'] is not None:
            if self.authority is None:
                raise SessionRejected()
            self.authority.peek(connection, row['native_authority_id'], account_id=row['account_id'])
        actor = self.access._actor(connection, row['account_id'])
        actor.require(Role.READER)
        expires = min(row['expires_at'],row['browser_idle_until']) if row['browser_idle_until'] is not None else row['expires_at']
        return SessionContext(actor, expires, row['csrf_token'], row['native_authority_id'], row['remembered'])

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
                connection.execute(text('''DELETE FROM c0_oauth_grants g USING c0_native_authority n
                    WHERE g.native_authority_id=:id AND n.id=g.native_authority_id
                    AND n.authority_kind='background' AND NOT g.persistent'''), {'id': row['native_authority_id']})
                connection.execute(text("""UPDATE c0_native_authority
                    SET revoked=true,credential=NULL,checking=false WHERE id=:id
                    AND (authority_kind IN ('session','remembered') OR NOT EXISTS(SELECT 1 FROM c0_oauth_grants
                        WHERE native_authority_id=:id AND persistent AND idle_until>:now))"""),
                    {'id': row['native_authority_id'], 'now': _date(self._now())})

    @staticmethod
    def check_csrf(context: SessionContext, supplied: str | None) -> None:
        SessionService._check_csrf(context.csrf_token, supplied)

    @staticmethod
    def _check_csrf(expected, supplied):
        if not isinstance(supplied, str) or not 1 <= len(supplied) <= 128:
            raise PermissionDenied()
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise PermissionDenied()
