# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded delegated grants for trusted consent and OAuth transport adapters."""
import base64
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import secrets
import time
from uuid import UUID, uuid4

from sqlalchemy import text

from .identity import Actor, PermissionDenied, Role
from .oauth_clients import OAuthClientService, redirect_uri, internal_id
from .operations import SCOPES
from .sessions import SessionContext


class GrantRejected(ValueError):
    def __init__(self):
        super().__init__('invalid_grant')


@dataclass(frozen=True)
class DelegatedAccess:
    actor: Actor
    client_id: str
    scopes: frozenset[str]
    expires_at: datetime
    resource: str
    issuer: str


@dataclass(frozen=True, repr=False)
class DelegationBinding:
    """Private Core attestation; no raw token and no request-selected callback."""
    service: object = field(repr=False)
    digest: str = field(repr=False)

    def validate(self, connection):
        if not isinstance(self.service, OAuthGrantService):
            raise GrantRejected()
        return self.service._verify_digest(connection, self.digest, self.service.resource, bind=False)


@dataclass(frozen=True)
class TokenPair:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(repr=False)
    scopes: frozenset[str]
    expires_in: int


@dataclass(frozen=True)
class CodeMetadata:
    code: str = field(repr=False)
    challenge: str = field(repr=False)
    client_id: str
    callback: str
    scopes: frozenset[str]
    expires_at: datetime
    subject: UUID
    resource: str


@dataclass(frozen=True)
class RefreshMetadata:
    token: str = field(repr=False)
    client_id: str
    scopes: frozenset[str]
    expires_at: datetime
    subject: UUID
    resource: str


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', value):
        raise GrantRejected()
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def pkce_challenge(verifier):
    if not isinstance(verifier, str) or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', verifier):
        raise GrantRejected()
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')


def _date(value):
    return datetime.fromtimestamp(value, timezone.utc)


class OAuthGrantService:
    """Bounded grants; token claims never confer persisted role authority.

    The app supplies its configured resource/native client and a verified,
    CSRF-protected session after explicit consent. Legacy grants remain capped
    by that session/one hour. Opt-in renewable grants share its absolute/idle
    bounds. Trusted native checks run before grant transactions; captured actors
    recheck persisted proof without network work inside content transactions.
    """
    def __init__(self, access, native_client, resource, *, now=time.time, authority=None):
        if not isinstance(native_client, str) or not 1 <= len(native_client) <= 128:
            raise ValueError('invalid_native_client')
        resource = redirect_uri(resource)
        if not resource.startswith('https://'):
            raise ValueError('invalid_resource')
        self.access = access
        self.clients = OAuthClientService(access)
        from .cimd import CimdService
        self.cimd = CimdService(access, now=now)
        self.native_client = native_client
        self.resource = resource
        self._now = now
        self.authority = authority
        if authority is not None:
            from .renewal import NativeAuthorityService
            if (not isinstance(authority, NativeAuthorityService) or authority.access is not access
                    or authority.client_id != native_client):
                raise ValueError('invalid_renewal_configuration')

    def _prepare(self, value, kind, client_id, resource):
        # Provider work precedes the grant transaction/locks. Captured Core
        # operations recheck the resulting persisted proof without network I/O.
        digest = _digest(value)
        if resource != self.resource:
            raise GrantRejected()
        table = 'c0_oauth_codes' if kind == 'code' else 'c0_oauth_tokens'
        token_filter = '' if kind == 'code' else 'AND t.kind=:kind'
        consumed = 'false' if kind == 'code' else 't.consumed'
        with self.access.database.engine.connect() as connection:
            row = connection.execute(text(f"""SELECT g.*, {consumed} AS token_consumed FROM {table} t
                JOIN c0_oauth_grants g ON g.id=t.grant_id
                WHERE t.hash=:hash AND t.expires_at>:now
                AND g.issuer=:issuer AND g.native_client=:native AND g.resource=:resource
                AND g.expires_at>:now {token_filter}"""),
                {'hash': digest, 'now': _date(self._now()), 'issuer': self.access.issuer,
                 'native': self.native_client, 'resource': self.resource, 'kind': kind}).mappings().one_or_none()
            if row is None:
                raise GrantRejected()
            client = self.clients._by_id(connection, row['client_id'])
            if (client is None or client['revision'] != row['client_revision']
                    or (client_id is not None and client['client_id'] != client_id)):
                raise GrantRejected()
            try:
                self.access._actor(connection, row['account_id']).require(Role.READER)
            except PermissionDenied:
                raise GrantRejected() from None
        if row['native_authority_id'] is not None and not row['token_consumed']:
            if self.authority is None:
                raise GrantRejected()
            from .renewal import RenewalRejected
            try:
                self.authority.authenticate(row['native_authority_id'])
            except RenewalRejected:
                raise GrantRejected() from None

    def _lock(self, connection, *, roles=False):
        if roles:
            connection.execute(text('SELECT pg_advisory_xact_lock(49372)'))
        connection.execute(text('SELECT pg_advisory_xact_lock(49378)'))
        connection.execute(text('SELECT pg_advisory_xact_lock(49379)'))

    def _clean(self, connection):
        connection.execute(text('DELETE FROM c0_oauth_grants WHERE expires_at<=:now'), {'now': _date(self._now())})
        connection.execute(text('''DELETE FROM c0_oauth_grants g USING c0_oauth_codes c
            WHERE c.grant_id=g.id AND c.expires_at<=:now
            AND NOT EXISTS (SELECT 1 FROM c0_oauth_tokens t WHERE t.grant_id=g.id)'''),
            {'now': _date(self._now())})

    def _grant(self, connection, identifier, client_id, resource, *, check_native=True):
        if resource != self.resource or not isinstance(client_id, str):
            raise GrantRejected()
        row = connection.execute(text('''SELECT * FROM c0_oauth_grants WHERE id=:id
            AND issuer=:issuer AND native_client=:native AND resource=:resource AND expires_at>:now'''),
            {'id': identifier, 'issuer': self.access.issuer, 'native': self.native_client,
             'resource': self.resource, 'now': _date(self._now())}).mappings().one_or_none()
        if row is None:
            raise GrantRejected()
        client = self.clients._by_id(connection, row['client_id'])
        if client is None or client['client_id'] != client_id or client['revision'] != row['client_revision']:
            raise GrantRejected()
        try:
            actor = self.access._actor(connection, row['account_id'])
            actor.require(Role.READER)
        except PermissionDenied:
            raise GrantRejected() from None
        if row['native_authority_id'] is not None and check_native:
            if self.authority is None:
                raise GrantRejected()
            from .renewal import RenewalRejected
            try:
                self.authority.peek(connection, row['native_authority_id'], account_id=row['account_id'])
            except RenewalRejected:
                raise GrantRejected() from None
        return row, actor

    def issue_code(self, session, client_id, *, callback, scopes, challenge, resource, verification=None):
        """Called only after explicit, CSRF-protected consent by this session."""
        with self.access.database.engine.begin() as connection:
            return self._issue_code(connection, session, client_id, callback=callback,
                scopes=scopes, challenge=challenge, resource=resource, verification=verification)

    def _issue_code(self, connection, session, client_id, *, callback, scopes, challenge, resource, verification=None):
        """Called only after explicit, CSRF-protected consent by this session."""
        if not isinstance(session, SessionContext) or session.expires_at.tzinfo is None:
            raise GrantRejected()
        if type(scopes) not in (set, frozenset) or not scopes or not scopes <= SCOPES:
            raise GrantRejected()
        if not isinstance(challenge, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', challenge):
            raise GrantRejected()
        if resource != self.resource:
            raise GrantRejected()
        try:
            callback = redirect_uri(callback)
        except ValueError:
            raise GrantRejected() from None
        self._lock(connection, roles=True)
        self._clean(connection)
        actor = self.access.checked_actor(connection, session.actor)
        actor.require(Role.READER)
        current = self._now()
        expires = min(session.expires_at.timestamp(), current + 3600)
        if session.native_authority_id is not None:
            if self.authority is None:
                raise GrantRejected()
            from .renewal import RenewalRejected
            try:
                native = self.authority.peek(connection, session.native_authority_id, account_id=session.actor.user_id)
            except RenewalRejected:
                raise GrantRejected() from None
            expires = min(session.expires_at.timestamp(), native['expires_at'].timestamp())
        if expires <= current:
            raise GrantRejected()
        code = secrets.token_urlsafe(32)
        for scope, role in [('c0:write', Role.EDITOR), ('c0:admin', Role.ADMIN)]:
            if scope in scopes:
                actor.require(role)
        client = self.clients._registered(connection, client_id)
        if client is None or callback not in client['redirect_uris'] or not scopes <= set(client['allowed_scopes']):
            raise GrantRejected()
        if client.get('registration_kind') == 'cimd':
            from .cimd import CimdRejected
            try:
                self.cimd._check_proof(connection, client, verification)
            except CimdRejected:
                raise GrantRejected() from None
        if connection.execute(text('SELECT count(*) FROM c0_oauth_grants')).scalar_one() >= 1000:
            raise GrantRejected()
        if connection.execute(text('''SELECT count(*) FROM c0_oauth_grants
                WHERE account_id=:id AND issuer=:issuer AND native_client=:native'''),
                {'id': actor.user_id, 'issuer': self.access.issuer, 'native': self.native_client}).scalar_one() >= 32:
            raise GrantRejected()
        identifier = uuid4()
        connection.execute(text('''INSERT INTO c0_oauth_grants
            (id,account_id,client_id,client_revision,issuer,native_client,resource,scopes,expires_at,native_authority_id)
            VALUES (:id,:account,:client,:revision,:issuer,:native,:resource,CAST(:scopes AS jsonb),:expires,:authority)'''),
            {'id': identifier, 'account': actor.user_id, 'client': internal_id(client), 'revision': client['revision'],
             'issuer': self.access.issuer, 'native': self.native_client, 'resource': self.resource,
             'scopes': json.dumps(sorted(scopes)), 'expires': _date(expires), 'authority': session.native_authority_id})
        connection.execute(text('''INSERT INTO c0_oauth_codes(hash,grant_id,redirect_uri,challenge,expires_at)
            VALUES (:hash,:grant,:redirect,:challenge,:expires)'''),
            {'hash': _digest(code), 'grant': identifier, 'redirect': callback,
             'challenge': challenge, 'expires': _date(min(expires, current + 300))})
        return code

    def _tokens(self, connection, grant, scopes):
        client = self.clients._by_id(connection, grant['client_id'])
        if client is None:
            raise GrantRejected()
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32) if 'refresh_token' in client.get(
            'grant_types', ['authorization_code', 'refresh_token']) else None
        access_expiry = min(grant['expires_at'].timestamp(), self._now() + 300)
        if grant['native_authority_id'] is not None:
            native = self.authority.peek(connection, grant['native_authority_id'], account_id=grant['account_id'])
            access_expiry = min(access_expiry, native['idle_until'].timestamp())
        for value, kind, expiry in [(access, 'access', _date(access_expiry)),
                                   (refresh, 'refresh', grant['expires_at'])]:
            if value is None:
                continue
            connection.execute(text('''INSERT INTO c0_oauth_tokens(hash,grant_id,kind,expires_at)
                VALUES (:hash,:grant,:kind,:expires)'''),
                {'hash': _digest(value), 'grant': grant['id'], 'kind': kind, 'expires': expiry})
        return TokenPair(access, refresh, frozenset(scopes), max(0, int(access_expiry - self._now())))

    def exchange_code(self, code, client_id, *, callback, verifier, resource):
        digest, challenge = _digest(code), pkce_challenge(verifier)
        self._prepare(code, 'code', client_id, resource)
        with self.access.database.engine.begin() as connection:
            self._lock(connection)
            row = connection.execute(text('''SELECT * FROM c0_oauth_codes WHERE hash=:hash AND expires_at>:now'''),
                {'hash': digest, 'now': _date(self._now())}).mappings().one_or_none()
            if row is None or row['redirect_uri'] != callback or not hmac.compare_digest(row['challenge'], challenge):
                raise GrantRejected()
            grant, _ = self._grant(connection, row['grant_id'], client_id, resource)
            connection.execute(text('DELETE FROM c0_oauth_codes WHERE hash=:hash'), {'hash': digest})
            return self._tokens(connection, grant, grant['scopes'])

    def _authorization_code(self, code, client_id):
        """Trusted SDK loader; exchange still verifies the actual raw request."""
        digest = _digest(code)
        self._prepare(code, 'code', client_id, self.resource)
        with self.access.database.engine.connect() as connection:
            row = connection.execute(text('''SELECT * FROM c0_oauth_codes WHERE hash=:hash AND expires_at>:now'''),
                {'hash': digest, 'now': _date(self._now())}).mappings().one_or_none()
            if row is None:
                raise GrantRejected()
            grant, _ = self._grant(connection, row['grant_id'], client_id, self.resource)
            return CodeMetadata(code, row['challenge'], client_id, row['redirect_uri'],
                frozenset(grant['scopes']), row['expires_at'], grant['account_id'], self.resource)

    def _refresh_token(self, token, client_id):
        """Trusted SDK loader; a consumed-token replay revokes before parsing scope.

        Otherwise SDK scope rejection could short-circuit family revocation.
        Call only after the transport has validated the exact resource.
        """
        digest = _digest(token)
        self._prepare(token, 'refresh', client_id, self.resource)
        rejected = False
        result = None
        with self.access.database.engine.begin() as connection:
            self._lock(connection)
            row = connection.execute(text('''SELECT * FROM c0_oauth_tokens
                WHERE hash=:hash AND kind='refresh' AND expires_at>:now'''),
                {'hash': digest, 'now': _date(self._now())}).mappings().one_or_none()
            if row is None:
                raise GrantRejected()
            grant, _ = self._grant(connection, row['grant_id'], client_id, self.resource, check_native=not row['consumed'])
            if row['consumed']:
                connection.execute(text('DELETE FROM c0_oauth_grants WHERE id=:id'), {'id': grant['id']})
                rejected = True
            else:
                result = RefreshMetadata(token, client_id, frozenset(grant['scopes']),
                    row['expires_at'], grant['account_id'], self.resource)
        if rejected:
            raise GrantRejected()
        return result

    def refresh(self, token, client_id, *, resource, scopes=None):
        digest = _digest(token)
        self._prepare(token, 'refresh', client_id, resource)
        rejected = False
        result = None
        with self.access.database.engine.begin() as connection:
            self._lock(connection)
            row = connection.execute(text('''SELECT * FROM c0_oauth_tokens
                WHERE hash=:hash AND kind='refresh' AND expires_at>:now'''),
                {'hash': digest, 'now': _date(self._now())}).mappings().one_or_none()
            if row is None:
                raise GrantRejected()
            grant, _ = self._grant(connection, row['grant_id'], client_id, resource, check_native=not row['consumed'])
            if row['consumed']:
                # Commit family revocation before reporting replay failure.
                connection.execute(text('DELETE FROM c0_oauth_grants WHERE id=:id'), {'id': grant['id']})
                rejected = True
            else:
                if scopes is None:
                    scopes = frozenset(grant['scopes'])
                if type(scopes) not in (set, frozenset) or not scopes or not scopes <= set(grant['scopes']):
                    raise GrantRejected()
                # Narrowing is durable; later refresh cannot restore old scopes.
                connection.execute(text('UPDATE c0_oauth_grants SET scopes=CAST(:scopes AS jsonb) WHERE id=:id'),
                    {'scopes': json.dumps(sorted(scopes)), 'id': grant['id']})
                connection.execute(text('UPDATE c0_oauth_tokens SET consumed=true WHERE hash=:hash'), {'hash': digest})
                # Keep consumed refresh hashes for replay detection, discard old
                # access hashes and bound rotation work within the grant lifetime.
                connection.execute(text("DELETE FROM c0_oauth_tokens WHERE grant_id=:id AND kind='access'"), {'id': grant['id']})
                if connection.execute(text('SELECT count(*) FROM c0_oauth_tokens WHERE grant_id=:id'),
                        {'id': grant['id']}).scalar_one() >= (2048 if grant['native_authority_id'] else 128):
                    connection.execute(text('DELETE FROM c0_oauth_grants WHERE id=:id'), {'id': grant['id']})
                    rejected = True
                else:
                    result = self._tokens(connection, grant, scopes)
        if rejected:
            raise GrantRejected()
        return result

    def verify(self, token, *, resource):
        digest = _digest(token)
        self._prepare(token, 'access', None, resource)
        with self.access.database.engine.connect() as connection:
            return self._verify_digest(connection, digest, resource, bind=True)

    def _verify_digest(self, connection, digest, resource, *, bind):
        row = connection.execute(text('''SELECT t.*,g.client_id FROM c0_oauth_tokens t
            JOIN c0_oauth_grants g ON g.id=t.grant_id
            WHERE t.hash=:hash AND t.kind='access' AND NOT t.consumed AND t.expires_at>:now'''),
            {'hash': digest, 'now': _date(self._now())}).mappings().one_or_none()
        if row is None:
            raise GrantRejected()
        client = self.clients._by_id(connection, row['client_id'])
        if client is None:
            raise GrantRejected()
        grant, actor = self._grant(connection, row['grant_id'], client['client_id'], resource)
        scopes = frozenset(grant['scopes'])
        if bind:
            actor = replace(actor, delegation=DelegationBinding(self, digest), delegated_scopes=scopes)
        return DelegatedAccess(actor, client['client_id'], scopes,
            row['expires_at'], self.resource, self.access.issuer)

    def revoke(self, token, client_id, *, resource):
        """An unknown/malformed token is an idempotent revocation success."""
        try:
            digest = _digest(token)
        except GrantRejected:
            return
        with self.access.database.engine.begin() as connection:
            self._lock(connection)
            row = connection.execute(text('SELECT grant_id FROM c0_oauth_tokens WHERE hash=:hash'),
                {'hash': digest}).mappings().one_or_none()
            if row is None:
                return
            self._grant(connection, row['grant_id'], client_id, resource, check_native=False)
            connection.execute(text('DELETE FROM c0_oauth_grants WHERE id=:id'), {'id': row['grant_id']})
