# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit delegated grants for trusted consent and OAuth transport adapters."""
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
    """Token claims never confer persisted role authority.

    The app supplies its configured resource/native client and a verified,
    CSRF-protected session after explicit consent. Legacy grants remain capped
    by that session/one hour. Interactive renewable grants share native bounds;
    explicit persistent grants use separately attested offline inactivity bounds.
    Trusted native checks run before grant transactions; captured actors
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

    @property
    def background_enabled(self):
        return self.authority is not None and self.authority.connection_policy is not None

    def _persistent_refresh(self, grant, generation):
        prefix = bytes.fromhex(grant['refresh_family']) + generation.to_bytes(4, 'big')
        binding = json.dumps(['c0-persistent-refresh-v1', str(grant['id']), str(grant['account_id']),
            str(grant['client_id']), grant['client_revision'], self.access.issuer,
            self.native_client, self.resource], separators=(',', ':')).encode()
        mac = hmac.digest(self.authority._refresh_key, binding + prefix, 'sha256')[:16]
        return base64.urlsafe_b64encode(prefix + mac).rstrip(b'=').decode('ascii')

    def _refresh_row(self, connection, token):
        digest = _digest(token)
        row = connection.execute(text('''SELECT * FROM c0_oauth_tokens
            WHERE hash=:hash AND kind='refresh' AND expires_at>:now'''),
            {'hash': digest, 'now': _date(self._now())}).mappings().one_or_none()
        if row is not None or not self.background_enabled:
            return row
        raw = base64.urlsafe_b64decode(token + '=')
        family, generation = raw[:12].hex(), int.from_bytes(raw[12:16], 'big')
        grant = connection.execute(text('''SELECT * FROM c0_oauth_grants
            WHERE persistent AND refresh_family=:family AND idle_until>:now'''),
            {'family': family, 'now': _date(self._now())}).mappings().one_or_none()
        if (grant is None or generation >= grant['refresh_generation']
                or not hmac.compare_digest(token, self._persistent_refresh(grant, generation))):
            return None
        # Prior issued generations identify replay, never authorization.
        return {'grant_id': grant['id'], 'consumed': True, 'expires_at': grant['idle_until']}

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
            parameters = {'hash': digest, 'now': _date(self._now()), 'issuer': self.access.issuer,
                'native': self.native_client, 'resource': resource, 'kind': kind}
            lifetime = '(g.expires_at>:now OR (g.persistent AND g.expires_at IS NULL AND g.idle_until>:now))'
            if kind == 'refresh':
                refresh = self._refresh_row(connection, value)
                row = None if refresh is None else connection.execute(text(f'''SELECT g.* FROM c0_oauth_grants g
                    WHERE g.id=:id AND g.issuer=:issuer AND g.native_client=:native AND g.resource=:resource
                    AND {lifetime}'''), {**parameters, 'id': refresh['grant_id']}).mappings().one_or_none()
                if row is not None:
                    row = {**row, 'token_consumed': refresh['consumed']}
            else:
                row = connection.execute(text(f"""SELECT g.*, {consumed} AS token_consumed FROM {table} t
                    JOIN c0_oauth_grants g ON g.id=t.grant_id
                    WHERE t.hash=:hash AND t.expires_at>:now
                    AND g.issuer=:issuer AND g.native_client=:native AND g.resource=:resource
                    AND {lifetime} {token_filter}"""), parameters).mappings().one_or_none()
            if row is None:
                raise GrantRejected()
            if row['persistent'] and not self.background_enabled:
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
        if row['persistent'] and not row['token_consumed']:
            with self.access.database.engine.begin() as connection:
                self._lock(connection, roles=True, client_id=client['client_id'])
                self._grant(connection, row['id'], client['client_id'], resource)
                native = self.authority.peek(connection, row['native_authority_id'], account_id=row['account_id'])
                activity = {'id': row['id'], 'now': _date(self._now()),
                    'idle': _date(self._now() + native['idle_seconds'])}
                connection.execute(text('''UPDATE c0_oauth_grants SET last_used_at=:now,idle_until=:idle
                    WHERE id=:id AND persistent'''), activity)
                # A successful access-token use also counts as activity. Keep
                # the current refresh credential aligned with that deadline;
                # otherwise it could expire before the grant's advertised idle
                # bound. Old generations remain replay-only and are not revived.
                connection.execute(text("""UPDATE c0_oauth_tokens SET expires_at=:idle
                    WHERE grant_id=:id AND kind='refresh' AND NOT consumed"""), activity)

    def _lock(self, connection, *, roles=False, client_id=None):
        if roles or (isinstance(client_id, str) and client_id[:8].lower() == 'https://'):
            connection.execute(text('SELECT pg_advisory_xact_lock(49372)'))
        connection.execute(text('SELECT pg_advisory_xact_lock(49378)'))
        connection.execute(text('SELECT pg_advisory_xact_lock(49379)'))

    @staticmethod
    def _cimd_revocation_lock(connection, client_id):
        # URL-client rotation/revocation must finish after transactions already
        # using its old delegated actor. The legacy UUID contract is unchanged.
        if connection.execute(text('SELECT 1 FROM c0_cimd_clients WHERE client_id=:id'),
                              {'id': client_id}).scalar_one_or_none():
            connection.execute(text('SELECT pg_advisory_xact_lock(49382)'))

    def _clean(self, connection):
        connection.execute(text('DELETE FROM c0_oauth_grants WHERE expires_at<=:now OR (persistent AND idle_until<=:now)'),
                           {'now': _date(self._now())})
        connection.execute(text('''DELETE FROM c0_oauth_grants g USING c0_oauth_codes c
            WHERE c.grant_id=g.id AND c.expires_at<=:now
            AND NOT EXISTS (SELECT 1 FROM c0_oauth_tokens t WHERE t.grant_id=g.id)'''),
            {'now': _date(self._now())})

    def _grant(self, connection, identifier, client_id, resource, *, check_native=True):
        if resource != self.resource or not isinstance(client_id, str):
            raise GrantRejected()
        row = connection.execute(text('''SELECT * FROM c0_oauth_grants WHERE id=:id
            AND issuer=:issuer AND native_client=:native AND resource=:resource
            AND (expires_at>:now OR (persistent AND expires_at IS NULL AND idle_until>:now))'''),
            {'id': identifier, 'issuer': self.access.issuer, 'native': self.native_client,
             'resource': self.resource, 'now': _date(self._now())}).mappings().one_or_none()
        if row is None:
            raise GrantRejected()
        if row['persistent'] and not self.background_enabled:
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

    def issue_code(self, session, client_id, *, callback, scopes, challenge, resource, verification=None, persistent=False):
        """Called only after explicit, CSRF-protected consent by this session."""
        with self.access.database.engine.begin() as connection:
            return self._issue_code(connection, session, client_id, callback=callback,
                scopes=scopes, challenge=challenge, resource=resource, verification=verification, persistent=persistent)

    def _issue_code(self, connection, session, client_id, *, callback, scopes, challenge, resource, verification=None, persistent=False):
        """Called only after explicit, CSRF-protected consent by this session."""
        if not isinstance(session, SessionContext) or session.expires_at.tzinfo is None or type(persistent) is not bool:
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
            expires = min(session.expires_at.timestamp(), native['expires_at'].timestamp()) if native['expires_at'] is not None else session.expires_at.timestamp()
        if session.expires_at.timestamp() <= current or expires <= current:
            raise GrantRejected()
        if persistent:
            if (not self.background_enabled or session.native_authority_id is None
                    or native['authority_kind'] != 'background'):
                raise GrantRejected()
            expires = None
        code = secrets.token_urlsafe(32)
        for scope, role in [('c0:write', Role.EDITOR), ('c0:admin', Role.ADMIN)]:
            if scope in scopes:
                actor.require(role)
        client = self.clients._registered(connection, client_id)
        if client is None or callback not in client['redirect_uris'] or not scopes <= set(client['allowed_scopes']):
            raise GrantRejected()
        if persistent and 'refresh_token' not in client.get('grant_types', ['authorization_code', 'refresh_token']):
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
            (id,account_id,client_id,client_revision,issuer,native_client,resource,scopes,expires_at,native_authority_id,
             persistent,idle_until,last_used_at,refresh_family)
            VALUES (:id,:account,:client,:revision,:issuer,:native,:resource,CAST(:scopes AS jsonb),:expires,:authority,
             :persistent,:idle,:used,:family)'''),
            {'id': identifier, 'account': actor.user_id, 'client': internal_id(client), 'revision': client['revision'],
             'issuer': self.access.issuer, 'native': self.native_client, 'resource': self.resource,
             'scopes': json.dumps(sorted(scopes)), 'expires': _date(expires) if expires is not None else None,
             'authority': session.native_authority_id, 'persistent': persistent,
             'idle': _date(current + native['idle_seconds']) if persistent else None,
             'used': _date(current) if persistent else None, 'family': secrets.token_hex(12) if persistent else None})
        connection.execute(text('''INSERT INTO c0_oauth_codes(hash,grant_id,redirect_uri,challenge,expires_at)
            VALUES (:hash,:grant,:redirect,:challenge,:expires)'''),
            {'hash': _digest(code), 'grant': identifier, 'redirect': callback,
             'challenge': challenge, 'expires': _date(min(expires, current + 300) if expires is not None else current + 300)})
        return code

    def _tokens(self, connection, grant, scopes):
        client = self.clients._by_id(connection, grant['client_id'])
        if client is None:
            raise GrantRejected()
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32) if 'refresh_token' in client.get(
            'grant_types', ['authorization_code', 'refresh_token']) else None
        grant_expiry = grant['idle_until'] if grant['persistent'] else grant['expires_at']
        if grant['persistent']:
            refresh = self._persistent_refresh(grant, grant['refresh_generation'])
            connection.execute(text("DELETE FROM c0_oauth_tokens WHERE grant_id=:id AND kind='refresh'"), {'id': grant['id']})
        access_expiry = min(grant_expiry.timestamp(), self._now() + 300)
        if grant['native_authority_id'] is not None:
            native = self.authority.peek(connection, grant['native_authority_id'], account_id=grant['account_id'])
            access_expiry = min(access_expiry, native['idle_until'].timestamp())
        for value, kind, expiry in [(access, 'access', _date(access_expiry)),
                                   (refresh, 'refresh', grant_expiry)]:
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
            self._lock(connection, client_id=client_id)
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
            self._lock(connection, client_id=client_id)
            row = self._refresh_row(connection, token)
            if row is None:
                raise GrantRejected()
            grant, _ = self._grant(connection, row['grant_id'], client_id, self.resource, check_native=not row['consumed'])
            if row['consumed']:
                self._cimd_revocation_lock(connection, grant['client_id'])
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
            self._lock(connection, client_id=client_id)
            row = self._refresh_row(connection, token)
            if row is None:
                raise GrantRejected()
            grant, _ = self._grant(connection, row['grant_id'], client_id, resource, check_native=not row['consumed'])
            self._cimd_revocation_lock(connection, grant['client_id'])
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
                if (grant['persistent'] and grant['refresh_generation'] == 4294967295
                        or not grant['persistent'] and connection.execute(text('SELECT count(*) FROM c0_oauth_tokens WHERE grant_id=:id'),
                            {'id': grant['id']}).scalar_one() >= (2048 if grant['native_authority_id'] else 128)):
                    connection.execute(text('DELETE FROM c0_oauth_grants WHERE id=:id'), {'id': grant['id']})
                    rejected = True
                else:
                    if grant['persistent']:
                        connection.execute(text('UPDATE c0_oauth_grants SET refresh_generation=refresh_generation+1 WHERE id=:id'), {'id': grant['id']})
                        grant = {**grant, 'refresh_generation': grant['refresh_generation'] + 1}
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
            self._lock(connection, client_id=client_id)
            row = connection.execute(text('SELECT grant_id FROM c0_oauth_tokens WHERE hash=:hash'),
                {'hash': digest}).mappings().one_or_none()
            if row is None:
                row = self._refresh_row(connection, token)
                if row is None:
                    return
            grant, _ = self._grant(connection, row['grant_id'], client_id, resource, check_native=False)
            self._cimd_revocation_lock(connection, grant['client_id'])
            connection.execute(text('DELETE FROM c0_oauth_grants WHERE id=:id'), {'id': row['grant_id']})

    def connections(self, actor):
        """First-party account view; no token, native credential or other user."""
        if actor.delegation is not None or actor.delegated_scopes is not None:
            raise PermissionDenied()
        with self.access.database.engine.connect() as connection:
            self.access.checked_actor(connection, actor).require(Role.READER)
            rows = connection.execute(text('''SELECT g.id,c.name AS client_name,g.scopes,g.persistent,
                g.expires_at,g.idle_until,g.last_used_at FROM c0_oauth_grants g
                JOIN c0_oauth_clients c ON c.id=g.client_id WHERE g.account_id=:account
                AND g.issuer=:issuer AND g.native_client=:native AND g.resource=:resource
                AND c.enabled AND c.revision=g.client_revision
                AND (g.expires_at>:now OR (g.persistent AND g.idle_until>:now))
                ORDER BY g.last_used_at DESC NULLS LAST,g.id LIMIT 32'''),
                {'account': actor.user_id, 'issuer': self.access.issuer, 'native': self.native_client,
                 'resource': self.resource, 'now': _date(self._now())}).mappings().all()
            return [{**row, 'id': str(row['id'])} for row in rows]

    def disconnect(self, actor, identifier):
        if actor.delegation is not None or actor.delegated_scopes is not None or not isinstance(identifier, UUID):
            raise PermissionDenied()
        with self.access.database.engine.begin() as connection:
            self._lock(connection, roles=True)
            self.access.checked_actor(connection, actor).require(Role.READER)
            row = connection.execute(text('''SELECT client_id FROM c0_oauth_grants WHERE id=:id
                AND account_id=:account AND issuer=:issuer AND native_client=:native AND resource=:resource'''),
                {'id': identifier, 'account': actor.user_id, 'issuer': self.access.issuer,
                 'native': self.native_client, 'resource': self.resource}).mappings().one_or_none()
            if row is None:
                raise GrantRejected()
            self._cimd_revocation_lock(connection, row['client_id'])
            connection.execute(text('DELETE FROM c0_oauth_grants WHERE id=:id'), {'id': identifier})
