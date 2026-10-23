# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Browser-bound client approval handoff; no fetching or delegated authority."""
import json
import re
import secrets

from sqlalchemy import text

from .cimd import CimdRejected
from .cimd_metadata import metadata_url
from .identity import PermissionDenied, Role
from .oauth_clients import redirect_uri
from .oauth_consent import ConsentRejected, OAuthConsentService, PendingConsent
from .oauth_grants import GrantRejected, _date, _digest
from .operations import SCOPES
from .sessions import SessionContext


class OnboardingRejected(ValueError):
    def __init__(self):
        super().__init__('connection_request_unavailable')


class ClientOnboardingService:
    def __init__(self, grants):
        self.grants = grants

    def _lock(self, connection):
        self.grants._lock(connection, roles=True)
        connection.execute(text('SELECT pg_advisory_xact_lock(49380)'))
        connection.execute(text('SELECT pg_advisory_xact_lock(49383)'))

    def _session(self, connection, session):
        if (not isinstance(session, SessionContext) or session.expires_at.tzinfo is None
                or session.expires_at.timestamp() <= self.grants._now()):
            raise OnboardingRejected()
        actor = self.grants.access.checked_actor(connection, session.actor)
        actor.require(Role.READER)
        if actor.delegation is not None or actor.delegated_scopes is not None:
            raise PermissionDenied()
        return actor

    def begin(self, parameters):
        """The transport has already rejected duplicate names and credentials."""
        fields = {'client_id', 'redirect_uri', 'response_type', 'code_challenge',
                  'code_challenge_method', 'state', 'scope', 'resource'}
        try:
            if (type(parameters) is not dict or set(parameters) - fields
                    or any(type(v) is not str for v in parameters.values())
                    or len(json.dumps(parameters).encode()) > 8192
                    or parameters.get('response_type') != 'code'
                    or parameters.get('code_challenge_method') != 'S256'
                    or not re.fullmatch(r'[A-Za-z0-9_-]{43}', parameters.get('code_challenge', ''))
                    or parameters.get('resource') != self.grants.resource):
                raise ValueError()
            url = metadata_url(parameters['client_id'])
            redirect_uri(parameters['redirect_uri'])
            scopes = parameters.get('scope', 'c0:read').split()
            if not scopes or len(scopes) != len(set(scopes)) or not set(scopes) <= SCOPES:
                raise ValueError()
            state = parameters.get('state')
            if state is not None and (not state.isascii() or not state.isprintable() or not 1 <= len(state) <= 512):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise OnboardingRejected() from None
        pending = PendingConsent(secrets.token_urlsafe(32), secrets.token_urlsafe(32))
        with self.grants.access.database.engine.begin() as connection:
            self._lock(connection)
            policy = self.grants.cimd._policy(connection)
            now = _date(self.grants._now())
            connection.execute(text('DELETE FROM c0_client_onboarding WHERE expires_at<=:now'), {'now': now})
            if (connection.execute(text('SELECT count(*) FROM c0_client_onboarding')).scalar_one() >= 1000
                    or connection.execute(text('SELECT count(*) FROM c0_client_onboarding WHERE metadata_url=:url'),
                                          {'url': url}).scalar_one() >= 32):
                raise OnboardingRejected()
            connection.execute(text('''INSERT INTO c0_client_onboarding
                (hash,browser_hash,metadata_url,issuer,native_client,resource,policy_revision,parameters,expires_at)
                VALUES (:hash,:browser,:url,:issuer,:native,:resource,:policy,CAST(:parameters AS jsonb),:expires)'''),
                {'hash': _digest(pending.request), 'browser': _digest(pending.binding), 'url': url,
                 'issuer': self.grants.access.issuer, 'native': self.grants.native_client,
                 'resource': self.grants.resource, 'policy': policy['revision'],
                 'parameters': json.dumps(parameters), 'expires': _date(self.grants._now() + 300)})
        return pending

    def _request(self, connection, request, binding):
        try:
            request_hash, browser_hash = _digest(request), _digest(binding)
            policy = self.grants.cimd._policy(connection)
        except (GrantRejected, CimdRejected):
            raise OnboardingRejected() from None
        row = connection.execute(text('''SELECT * FROM c0_client_onboarding
            WHERE hash=:hash AND browser_hash=:browser AND expires_at>:now
            AND issuer=:issuer AND native_client=:native AND resource=:resource AND policy_revision=:policy'''),
            {'hash': request_hash, 'browser': browser_hash, 'now': _date(self.grants._now()),
             'issuer': self.grants.access.issuer, 'native': self.grants.native_client,
             'resource': self.grants.resource, 'policy': policy['revision']}).mappings().one_or_none()
        if row is None:
            raise OnboardingRejected()
        return row

    def available(self, request, binding):
        """Trusted SSO return routing only; disclose no request parameters."""
        with self.grants.access.database.engine.connect() as connection:
            self._request(connection, request, binding)

    def _view(self, connection, row):
        raw = row['parameters']
        client = self.grants.clients._registered(connection, row['metadata_url'])
        approved = client is not None and raw['redirect_uri'] in client['redirect_uris']
        return {'metadata_url': row['metadata_url'], 'callback': raw['redirect_uri'],
                'scopes': raw.get('scope', 'c0:read').split(), 'expires_at': row['expires_at'],
                'approved': approved, 'allowed_scopes': client['allowed_scopes'] if approved else []}

    def view(self, session, request, binding):
        with self.grants.access.database.engine.connect() as connection:
            actor = self._session(connection, session)
            row = self._request(connection, request, binding)
            if row['account_id'] is not None and row['account_id'] != actor.user_id:
                raise OnboardingRejected()
            return self._view(connection, row)

    def submit(self, session, request, binding):
        """Trusted adapter requires same-origin CSRF for this approval request."""
        with self.grants.access.database.engine.begin() as connection:
            self._lock(connection)
            actor = self._session(connection, session)
            row = self._request(connection, request, binding)
            if row['account_id'] not in (None, actor.user_id):
                raise OnboardingRejected()
            if row['account_id'] is None:
                count = connection.execute(text('SELECT count(*) FROM c0_client_onboarding WHERE account_id=:id AND expires_at>:now'),
                    {'id': actor.user_id, 'now': _date(self.grants._now())}).scalar_one()
                if count >= 16:
                    raise OnboardingRejected()
                connection.execute(text('UPDATE c0_client_onboarding SET account_id=:id WHERE hash=:hash'),
                                   {'id': actor.user_id, 'hash': row['hash']})
            return self._view(connection, row)

    def requests(self, actor):
        with self.grants.access.database.engine.connect() as connection:
            self.grants.clients._authorize(connection, actor)
            policy = self.grants.cimd._policy(connection)
            rows = connection.execute(text('''SELECT o.*,a.username FROM c0_client_onboarding o
                JOIN c0_accounts a ON a.id=o.account_id WHERE o.expires_at>:now
                AND o.issuer=:issuer AND o.native_client=:native AND o.resource=:resource
                AND o.policy_revision=:policy ORDER BY o.expires_at DESC,o.hash LIMIT 64'''),
                {'now': _date(self.grants._now()), 'issuer': self.grants.access.issuer,
                 'native': self.grants.native_client, 'resource': self.grants.resource,
                 'policy': policy['revision']}).mappings().all()
            return [{**self._view(connection, row), 'username': row['username']} for row in rows]

    def complete(self, session, request, binding, *, scopes, verification):
        """Atomically consume the handoff and create ordinary explicit consent."""
        with self.grants.access.database.engine.begin() as connection:
            self._lock(connection)
            actor = self._session(connection, session)
            row = self._request(connection, request, binding)
            if row['account_id'] != actor.user_id:
                raise OnboardingRejected()
            raw = row['parameters']
            if type(scopes) not in (set, frozenset) or not scopes or not scopes <= set(raw.get('scope', 'c0:read').split()):
                raise OnboardingRejected()
            try:
                pending = OAuthConsentService(self.grants)._begin(connection, row['metadata_url'],
                    callback=raw['redirect_uri'], scopes=scopes, challenge=raw['code_challenge'],
                    state=raw.get('state'), resource=raw['resource'], verification=verification)
            except ConsentRejected:
                raise OnboardingRejected() from None
            connection.execute(text('DELETE FROM c0_client_onboarding WHERE hash=:hash'), {'hash': row['hash']})
            return pending
