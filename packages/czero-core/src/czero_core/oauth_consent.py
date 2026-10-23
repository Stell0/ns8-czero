# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""One-use browser-bound consent; HTTP, cookies and SSO remain app concerns."""
from dataclasses import dataclass, field
import json
import re
import secrets

from sqlalchemy import text

from .oauth_grants import GrantRejected, _date, _digest
from .oauth_clients import redirect_uri, internal_id
from .operations import SCOPES
from .sessions import SessionContext


class ConsentRejected(ValueError):
    def __init__(self):
        super().__init__('invalid_consent')


@dataclass(frozen=True)
class PendingConsent:
    request: str = field(repr=False)
    binding: str = field(repr=False)


@dataclass(frozen=True)
class ConsentResult:
    callback: str
    state: str | None = field(repr=False)
    code: str | None = field(repr=False)


class OAuthConsentService:
    def __init__(self, grants):
        self.grants = grants

    def begin(self, client_id, *, callback, scopes, challenge, state, resource, verification=None):
        with self.grants.access.database.engine.begin() as connection:
            return self._begin(connection, client_id, callback=callback, scopes=scopes,
                challenge=challenge, state=state, resource=resource, verification=verification)

    def _begin(self, connection, client_id, *, callback, scopes, challenge, state, resource, verification=None):
        if (type(scopes) not in (set, frozenset) or not scopes or not scopes <= SCOPES
                or not isinstance(challenge, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', challenge)
                or resource != self.grants.resource):
            raise ConsentRejected()
        if state is not None and (not isinstance(state, str) or not state.isascii()
                or not state.isprintable() or not 1 <= len(state) <= 512):
            raise ConsentRejected()
        try:
            callback = redirect_uri(callback)
        except ValueError:
            raise ConsentRejected() from None
        pending = PendingConsent(secrets.token_urlsafe(32), secrets.token_urlsafe(32))
        self.grants._lock(connection, roles=True)
        connection.execute(text('SELECT pg_advisory_xact_lock(49380)'))
        now = _date(self.grants._now())
        connection.execute(text('DELETE FROM c0_oauth_consent WHERE expires_at<=:now'), {'now': now})
        client = self.grants.clients._registered(connection, client_id)
        if client is None or callback not in client['redirect_uris'] or not scopes <= set(client['allowed_scopes']):
            raise ConsentRejected()
        if client.get('registration_kind') == 'cimd':
            from .cimd import CimdRejected
            try:
                self.grants.cimd._check_proof(connection, client, verification)
            except CimdRejected:
                raise ConsentRejected() from None
        if connection.execute(text('SELECT count(*) FROM c0_oauth_consent')).scalar_one() >= 1000:
            raise ConsentRejected()
        if connection.execute(text('SELECT count(*) FROM c0_oauth_consent WHERE client_id=:id'),
                {'id': internal_id(client)}).scalar_one() >= 32:
            raise ConsentRejected()
        connection.execute(text('''INSERT INTO c0_oauth_consent
            (hash,browser_hash,client_id,client_revision,issuer,native_client,resource,callback,scopes,challenge,state,expires_at)
            VALUES (:hash,:browser,:client,:revision,:issuer,:native,:resource,:callback,CAST(:scopes AS jsonb),:challenge,:state,:expires)'''),
            {'hash': _digest(pending.request), 'browser': _digest(pending.binding),
             'client': internal_id(client), 'revision': client['revision'], 'issuer': self.grants.access.issuer,
             'native': self.grants.native_client, 'resource': resource, 'callback': callback,
             'scopes': json.dumps(sorted(scopes)), 'challenge': challenge, 'state': state,
             'expires': _date(self.grants._now() + 300)})
        return pending

    def _request(self, connection, request, binding):
        try:
            parameters = {'hash': _digest(request), 'browser': _digest(binding), 'now': _date(self.grants._now()),
                'issuer': self.grants.access.issuer, 'native': self.grants.native_client, 'resource': self.grants.resource}
        except GrantRejected:
            raise ConsentRejected() from None
        row = connection.execute(text('''SELECT * FROM c0_oauth_consent
            WHERE hash=:hash AND browser_hash=:browser AND expires_at>:now
            AND issuer=:issuer AND native_client=:native AND resource=:resource'''), parameters).mappings().one_or_none()
        if row is None:
            raise ConsentRejected()
        client = self.grants.clients._by_id(connection, row['client_id'])
        if client is None or client['revision'] != row['client_revision']:
            raise ConsentRejected()
        return row, client

    def view(self, request, binding):
        with self.grants.access.database.engine.connect() as connection:
            row, client = self._request(connection, request, binding)
            # State/challenge/binding and native identity stay out of the UI DTO.
            return {'client_id': client['client_id'], 'client_name': client['client_name'],
                'callback': row['callback'], 'scopes': row['scopes'], 'resource': row['resource'],
                'expires_at': row['expires_at']}

    def complete(self, session, request, binding, *, approve, scopes=None, verification=None):
        """Trusted app adapter checks same-origin CSRF before invoking this."""
        if (not isinstance(session, SessionContext) or type(approve) is not bool
                or session.expires_at.tzinfo is None):
            raise ConsentRejected()
        with self.grants.access.database.engine.begin() as connection:
            # Stable lock order: role -> grant -> consent. Failed consent/code
            # creation rolls back both; concurrent completions have one winner.
            self.grants._lock(connection, roles=True)
            connection.execute(text('SELECT pg_advisory_xact_lock(49380)'))
            row, client = self._request(connection, request, binding)
            if session.expires_at.timestamp() <= self.grants._now():
                raise ConsentRejected()
            self.grants.access.checked_actor(connection, session.actor)
            code = None
            if approve:
                if scopes is None:
                    scopes = frozenset(row['scopes'])
                if type(scopes) not in (set, frozenset) or not scopes or not scopes <= set(row['scopes']):
                    raise ConsentRejected()
                code = self.grants._issue_code(connection, session, client['client_id'],
                    callback=row['callback'], scopes=scopes, challenge=row['challenge'], resource=row['resource'], verification=verification)
            connection.execute(text('DELETE FROM c0_oauth_consent WHERE hash=:hash'), {'hash': row['hash']})
            return ConsentResult(row['callback'], row['state'], code)
