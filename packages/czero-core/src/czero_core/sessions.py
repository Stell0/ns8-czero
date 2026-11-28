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


@dataclass(frozen=True, repr=False)
class BrowserLogin(LoginSecrets):
    state_hash: str = ''
    owner_hash: str = ''
    prior_session_hash: str | None = None
    return_target: str = ''


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

    def _known_browser(self, conn, digest):
        return conn.execute(text("""SELECT 1 FROM c0_sessions
            WHERE token_hash=:hash AND issuer=:issuer AND client_id=:client"""),
            {'hash': digest, 'issuer': self.access.issuer, 'client': self.client_id}).scalar() == 1

    def _can_replace(self, conn, digest):
        # Credential freshness is checked at the provider during sign-in. A
        # recorded revocation or loss of membership must already win locally.
        row = conn.execute(text("""SELECT s.account_id FROM c0_sessions s
            LEFT JOIN c0_native_authority n ON n.id=s.native_authority_id
            WHERE s.token_hash=:hash AND s.issuer=:issuer AND s.client_id=:client
              AND s.expires_at>:now AND (s.browser_idle_until IS NULL OR s.browser_idle_until>:now)
              AND (s.native_authority_id IS NULL OR (NOT n.revoked AND n.idle_until>:now
                  AND (n.expires_at IS NULL OR n.expires_at>:now)))"""),
            {'hash': digest, 'issuer': self.access.issuer, 'client': self.client_id,
             'now': _date(self._now())}).scalar_one_or_none()
        if row is None:
            return False
        try:
            self.access._actor(conn, row).require(Role.READER)
        except PermissionDenied:
            return False
        return True

    def known_browser(self, cookie):
        """Can this cookie anchor an explicit replacement sign-in?"""
        with self.access.database.engine.connect() as conn:
            return self._can_replace(conn, _digest(cookie))

    def begin_login(self, *, background=False, session=None, remembered=False, return_target=None, prior_cookie=None) -> PendingLogin:
        if type(background) is not bool or type(remembered) is not bool or remembered and self.authority is None:
            raise LoginStateRejected()
        if return_target is not None and (not isinstance(return_target, str) or len(return_target) > 2048):
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
            if prior_cookie and not self._can_replace(connection, _digest(prior_cookie)):
                raise LoginStateRejected()
            connection.execute(text("DELETE FROM c0_login_states WHERE expires_at <= :now"), {"now": _date(current)})
            count = connection.execute(text("""
                SELECT count(*) FROM c0_login_states WHERE issuer = :issuer AND client_id = :client
            """), {"issuer": self.access.issuer, "client": self.client_id}).scalar_one()
            if count >= 1000:
                raise LoginStateRejected()
            connection.execute(text("""
                INSERT INTO c0_login_states
                (state_hash, browser_hash, nonce, code_verifier, issuer, client_id, expires_at,background,expected_account_key,remembered,return_target,prior_session_hash)
                VALUES (:state, :browser, :nonce, :verifier, :issuer, :client, :expires,:background,:expected,:remembered,:target,:prior)
            """), {"state": _digest(pending.state), "browser": _digest(pending.browser_binding),
                   "nonce": pending.nonce, "verifier": pending.code_verifier,
                   "issuer": self.access.issuer, "client": self.client_id, "expires": _date(current + 300),
                   'background': background, 'expected': expected, 'remembered': remembered,
                   'target':return_target, 'prior':_digest(prior_cookie) if prior_cookie else None})
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
                AND background AND NOT claimed AND expires_at>:now'''), parameters).mappings().one_or_none()
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
                AND issuer = :issuer AND client_id = :client AND expires_at > :now AND NOT claimed AND owner_hash IS NULL
                RETURNING nonce, code_verifier,background,expected_account_key,remembered
            """), parameters).mappings().one_or_none()
            if row is None:
                raise LoginStateRejected()
        return LoginSecrets(row["nonce"], row["code_verifier"], row['background'], row['expected_account_key'], row['remembered'])

    def bind_browser_login(self, pending, owner, prior_cookie):
        """Fence previous login attempts before redirecting to the provider."""
        values = {'state': _digest(pending.state), 'proof': _digest(pending.browser_binding),
                  'owner': _digest(owner), 'issuer': self.access.issuer, 'client': self.client_id,
                  'prior': _digest(prior_cookie) if prior_cookie else None, 'now': _date(self._now())}
        with self.access.database.engine.begin() as conn:
            conn.execute(text('SELECT pg_advisory_xact_lock(49373)'))
            if values['prior'] and not self._can_replace(conn, values['prior']):
                raise LoginStateRejected()
            bound = conn.execute(text("""UPDATE c0_login_states SET owner_hash=:owner
                WHERE state_hash=:state AND browser_hash=:proof AND owner_hash IS NULL AND NOT claimed
                AND issuer=:issuer AND client_id=:client AND expires_at>:now
                AND prior_session_hash IS NOT DISTINCT FROM CAST(:prior AS varchar) RETURNING state_hash"""), values)
            if bound.scalar_one_or_none() is None:
                raise LoginStateRejected()
            conn.execute(text("""UPDATE c0_login_states SET claimed=true, owner_hash=NULL, nonce='', code_verifier=''
                WHERE issuer=:issuer AND client_id=:client AND owner_hash=:owner AND state_hash<>:state"""), values)

    def recovery_target(self, state, proof):
        """Return routing context only. The caller must separately verify the flow and browser."""
        try:
            values = {'state': _digest(state), 'proof': _digest(proof), 'now': _date(self._now()),
                      'issuer': self.access.issuer, 'client': self.client_id}
        except ValueError:
            return None
        with self.access.database.engine.connect() as conn:
            return conn.execute(text("""SELECT return_target FROM c0_login_states WHERE state_hash=:state
                AND browser_hash=:proof AND expires_at>:now AND issuer=:issuer AND client_id=:client"""),
                values).scalar_one_or_none()

    def claim_browser_login(self, state, proof, owner, prior_cookie):
        """Consume once before network I/O, retaining only the publication fence."""
        try:
            values = {'state': _digest(state), 'proof': _digest(proof), 'owner': _digest(owner),
                      'issuer': self.access.issuer, 'client': self.client_id, 'now': _date(self._now()),
                      'prior': _digest(prior_cookie) if prior_cookie else None}
        except ValueError:
            raise LoginStateRejected() from None
        with self.access.database.engine.begin() as conn:
            row = conn.execute(text("""SELECT * FROM c0_login_states WHERE state_hash=:state
                AND browser_hash=:proof AND owner_hash=:owner AND issuer=:issuer AND client_id=:client
                AND prior_session_hash IS NOT DISTINCT FROM CAST(:prior AS varchar)
                AND expires_at>:now AND NOT claimed FOR UPDATE"""), values).mappings().one_or_none()
            if row is None:
                raise LoginStateRejected()
            conn.execute(text("""UPDATE c0_login_states SET claimed=true, nonce='', code_verifier=''
                WHERE state_hash=:state"""), values)
        return BrowserLogin(row['nonce'], row['code_verifier'], row['background'], row['expected_account_key'],
                            row['remembered'], values['state'], values['owner'], values['prior'],
                            row['return_target'] or '')

    def _finish_browser_login(self, conn, attempt):
        conn.execute(text('SELECT pg_advisory_xact_lock(49373)'))
        if attempt.prior_session_hash and not self._can_replace(conn, attempt.prior_session_hash):
            raise LoginStateRejected()
        completed = conn.execute(text("""UPDATE c0_login_states SET owner_hash=NULL
            WHERE state_hash=:state
            AND owner_hash=:owner AND claimed AND expires_at>:now AND issuer=:issuer AND client_id=:client
            RETURNING state_hash"""), {'state': attempt.state_hash, 'owner': attempt.owner_hash,
            'now': _date(self._now()), 'issuer': self.access.issuer, 'client': self.client_id})
        if completed.scalar_one_or_none() is None:
            raise LoginStateRejected()

    def reject_browser_login(self, attempt, *, denied_identity=None):
        """Apply a denied sign-in only if it still owns this browser transition."""
        with self.access.database.engine.begin() as conn:
            conn.execute(text('SELECT pg_advisory_xact_lock(49372)'))
            self._finish_browser_login(conn, attempt)
            if denied_identity is not None:
                self.access._record_identity(conn, denied_identity, allow_admission=False)
            if attempt.prior_session_hash:
                conn.execute(text('SELECT pg_advisory_xact_lock(49382)'))
                self._remove_session(conn, attempt.prior_session_hash)

    def create(self, identity: VerifiedIdentity, *, renewal=None, background=False, expected_account_key=None, remembered=False, attempt=None, bind_flow=None) -> str:
        if type(background) is not bool or background and (expected_account_key is None or identity.account_key != expected_account_key):
            raise SessionRejected()
        if type(remembered) is not bool:
            raise SessionRejected()
        current = self._now()
        expires = min(identity.expires_at, current + self._fixed_session_seconds)
        if expires <= current:
            raise SessionRejected()
        actor = self.access.resolve(identity) if attempt is None else None
        cookie = secrets.token_urlsafe(32)
        with self.access.database.engine.begin() as connection:
            if attempt is not None:
                # Fence admission, native allocation, draft binding and publication
                # in one transaction. A lost attempt leaves no account or grant.
                connection.execute(text('SELECT pg_advisory_xact_lock(49372)'))
                self._finish_browser_login(connection, attempt)
                user_id = self.access._record_identity(connection, identity)
                actor = self.access._actor(connection, user_id)
                actor.require(Role.READER)
            native_id = None
            if renewal is not None:
                from .renewal import RenewalRejected, RenewalResult
                if self.authority is None or not isinstance(renewal, RenewalResult) or renewal.identity != identity:
                    raise RenewalRejected()
                native_id, absolute = self.authority.create(connection, actor, renewal, background=background, remembered=remembered)
                expires = current + REMEMBER_SECONDS if remembered else (absolute.timestamp() if absolute is not None else current + self.max_session_seconds)
            elif background or remembered:
                raise SessionRejected()
            if attempt is not None:
                if bind_flow is not None and not bind_flow(connection, actor.user_id):
                    raise LoginStateRejected()
                if attempt.prior_session_hash:
                    connection.execute(text('SELECT pg_advisory_xact_lock(49382)'))
                    prior = self._remove_session(connection, attempt.prior_session_hash, preserve_grants=True)
                    if prior is None:
                        raise LoginStateRejected()
                    # A logout already in flight can still own the prior cookie
                    # and CSRF until the replacement response reaches the browser.
                    connection.execute(text('''UPDATE c0_login_states SET successor_session_hash=:successor,
                        prior_csrf_hash=:csrf,prior_native_id=:native,
                        expires_at=:receipt_expires,return_target=NULL WHERE state_hash=:state'''),
                        {'successor': _digest(cookie), 'csrf': _digest(prior['csrf_token']),
                         'native': prior['native_authority_id'], 'state': attempt.state_hash,
                         'receipt_expires': _date(self._now() + 300)})
            connection.execute(text("""
                INSERT INTO c0_sessions (token_hash, account_id, csrf_token, issuer, client_id, expires_at, native_authority_id,
                    browser_idle_until,browser_idle_seconds,remembered)
                VALUES (:token, :account, :csrf, :issuer, :client, :expires, :native,:idle,:seconds,:remembered)
            """), {"token": _digest(cookie), "account": actor.user_id, "csrf": secrets.token_urlsafe(32),
                   "issuer": self.access.issuer, "client": self.client_id, "expires": _date(expires), "native": native_id,
                   'idle': _date(expires) if remembered else (_date(min(expires,current+self.authority.policy.idle_seconds)) if native_id is not None else None),
                   'seconds': REMEMBER_SECONDS if remembered else (self.authority.policy.idle_seconds if native_id is not None else None),
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
        native = None
        if row['native_authority_id'] is not None:
            if self.authority is None:
                raise SessionRejected()
            native = self.authority.peek(connection, row['native_authority_id'], account_id=row['account_id'])
        actor = self.access._actor(connection, row['account_id'])
        actor.require(Role.READER)
        # Ordinary consent retains its original finite delegation deadline; the
        # bound actor still rechecks the independent browser idle window.
        expires = row['expires_at']
        if row['browser_idle_until'] is not None and (native is None or native['authority_kind'] != 'session'):
            expires = min(expires, row['browser_idle_until'])
        return SessionContext(actor, expires, row['csrf_token'], row['native_authority_id'], row['remembered'])

    def destroy(self, cookie: str) -> None:
        self._destroy(cookie)

    def replace_browser(self, cookie: str) -> None:
        """Retire a prior cookie after verified sign-in, retaining client grants."""
        self._destroy(cookie, preserve_grants=True)

    def logout(self, cookie: str, supplied_csrf: str | None, *, owner=None) -> None:
        """Revoke only this cookie's authority without contacting the provider."""
        self._destroy(cookie, supplied_csrf=supplied_csrf, csrf_required=True, owner=owner)

    def _destroy(self, cookie, *, supplied_csrf=None, csrf_required=False, preserve_grants=False, owner=None):
        try:
            hashed = _digest(cookie)
        except ValueError:
            if csrf_required:
                raise SessionRejected() from None
            return
        with self.access.database.engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(49373)'))
            connection.execute(text('SELECT pg_advisory_xact_lock(49382)'))
            if csrf_required and not self._known_browser(connection, hashed):
                try:
                    csrf_hash = _digest(supplied_csrf)
                except ValueError:
                    raise PermissionDenied() from None
                receipt_proved = False
                while True:
                    # Later links follow only the server-recorded successor.
                    # Each iteration consumes one of the bounded live receipts.
                    prior = connection.execute(text("""DELETE FROM c0_login_states
                        WHERE issuer=:issuer AND client_id=:client AND prior_session_hash=:prior
                        AND (:proved OR prior_csrf_hash=:csrf)
                        AND successor_session_hash IS NOT NULL AND expires_at>:now
                        RETURNING successor_session_hash, prior_native_id"""),
                        {'issuer': self.access.issuer, 'client': self.client_id, 'prior': hashed,
                         'csrf': csrf_hash, 'proved': receipt_proved, 'now': _date(self._now())}).mappings().one_or_none()
                    if prior is None:
                        if not receipt_proved:
                            raise SessionRejected()
                        break
                    self._retire_native(connection, prior['prior_native_id'], preserve_grants=False)
                    hashed = prior['successor_session_hash']
                    receipt_proved = True
                self._remove_session(connection, hashed)
            else:
                self._remove_session(connection, hashed, supplied_csrf=supplied_csrf,
                                     csrf_required=csrf_required, preserve_grants=preserve_grants)
            if csrf_required:
                connection.execute(text("""DELETE FROM c0_login_states WHERE issuer=:issuer AND client_id=:client
                    AND (prior_session_hash=:prior OR owner_hash=:owner)"""),
                    {'issuer': self.access.issuer, 'client': self.client_id, 'prior': hashed,
                     'owner': _digest(owner) if owner else None})

    def _remove_session(self, connection, hashed, *, supplied_csrf=None, csrf_required=False, preserve_grants=False):
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
        self._retire_native(connection, row['native_authority_id'], preserve_grants=preserve_grants)
        return row

    def _retire_native(self, connection, native_id, *, preserve_grants):
        if native_id is None:
            return
        if preserve_grants:
            connection.execute(text('''UPDATE c0_native_authority n
                SET revoked=true,credential=NULL,checking=false WHERE n.id=:id
                AND NOT EXISTS(SELECT 1 FROM c0_oauth_grants g WHERE g.native_authority_id=n.id
                    AND (g.expires_at>:now OR (g.persistent AND g.idle_until>:now)))'''),
                {'id': native_id, 'now': _date(self._now())})
            return
        connection.execute(text('''DELETE FROM c0_oauth_grants g USING c0_native_authority n
            WHERE g.native_authority_id=:id AND n.id=g.native_authority_id
            AND n.authority_kind='background' AND NOT g.persistent'''), {'id': native_id})
        connection.execute(text("""UPDATE c0_native_authority
            SET revoked=true,credential=NULL,checking=false WHERE id=:id
            AND (authority_kind IN ('session','remembered') OR NOT EXISTS(SELECT 1 FROM c0_oauth_grants
                WHERE native_authority_id=:id AND persistent AND idle_until>:now))"""),
            {'id': native_id, 'now': _date(self._now())})

    @staticmethod
    def check_csrf(context: SessionContext, supplied: str | None) -> None:
        SessionService._check_csrf(context.csrf_token, supplied)

    @staticmethod
    def _check_csrf(expected, supplied):
        if not isinstance(supplied, str) or not 1 <= len(supplied) <= 128:
            raise PermissionDenied()
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise PermissionDenied()
