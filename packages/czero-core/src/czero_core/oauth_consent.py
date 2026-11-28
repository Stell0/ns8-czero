# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""One-use browser-bound consent; HTTP, cookies and SSO remain app concerns."""
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import re
import secrets

from sqlalchemy import text

from .oauth_grants import GrantRejected, _date, _digest
from .oauth_clients import redirect_uri, internal_id
from .identity import PermissionDenied, Role
from .operations import SCOPES
from .personal_data import require_consent_role
from .sessions import SessionContext


# Include the server-chosen mode in the existing browser-binding digest.
# Removing the prefix therefore cannot convert a pending session-only request.
_SESSION_ONLY_PREFIX = 's-'


def _session_only(binding):
    return len(binding) == 43 + len(_SESSION_ONLY_PREFIX) and binding.startswith(_SESSION_ONLY_PREFIX)


def _browser_hash(binding):
    if isinstance(binding, str) and _session_only(binding):
        _digest(binding[len(_SESSION_ONLY_PREFIX):])
        return hashlib.sha256(binding.encode('ascii')).hexdigest()
    return _digest(binding)


class ConsentRejected(ValueError):
    def __init__(self, reason='draft_unavailable'):
        self.reason = reason
        super().__init__('invalid_consent')


def eligible_consent_scopes(actor, requested):
    eligible = []
    for scope, role in (('c0:read', Role.READER), ('c0:write', Role.EDITOR),
                        ('c0:admin', Role.ADMIN)):
        if scope in requested:
            try:
                require_consent_role(actor, role)
            except PermissionDenied:
                continue
            eligible.append(scope)
    return eligible


@dataclass(frozen=True)
class PendingConsent:
    request: str = field(repr=False)
    binding: str = field(repr=False)
    stage: str = 'consent'


@dataclass(frozen=True)
class ConsentResult:
    callback: str
    state: str | None = field(repr=False)
    code: str | None = field(repr=False)


@dataclass(frozen=True)
class ConsentReceipt:
    decision: str


def request_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class OAuthConsentService:
    supports_session_only = True

    def __init__(self, grants):
        self.grants = grants

    def begin(self, client_id, *, callback, scopes, challenge, state, resource, verification=None, session_only=False,
              browser_flows=None, requested_scopes=None):
        with self.grants.access.database.engine.begin() as connection:
            return self._begin(connection, client_id, callback=callback, scopes=scopes,
                challenge=challenge, state=state, resource=resource, verification=verification,
                session_only=session_only, browser_flows=browser_flows, requested_scopes=requested_scopes)

    def _begin(self, connection, client_id, *, callback, scopes, challenge, state, resource, verification=None, session_only=False,
               browser_flows=None, requested_scopes=None, pending=None, expires=None, account_id=None):
        if (type(scopes) not in (set, frozenset) or not scopes or not scopes <= SCOPES
                or not isinstance(challenge, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', challenge)
                or resource != self.grants.resource or type(session_only) is not bool):
            raise ConsentRejected()
        if state is not None and (not isinstance(state, str) or not state.isascii()
                or not state.isprintable() or not 1 <= len(state) <= 512):
            raise ConsentRejected()
        try:
            callback = redirect_uri(callback)
        except ValueError:
            raise ConsentRejected() from None
        binding = secrets.token_urlsafe(32)
        if session_only:
            binding = _SESSION_ONLY_PREFIX + binding
        onboarding_transition = pending is not None
        pending = pending or PendingConsent(secrets.token_urlsafe(32), binding)
        self.grants._lock(connection, roles=True)
        connection.execute(text('SELECT pg_advisory_xact_lock(49380)'))
        now = _date(self.grants._now())
        connection.execute(text('DELETE FROM c0_oauth_consent WHERE expires_at<=:now'), {'now': now})
        client = self.grants.clients._registered(connection, client_id)
        if (client is None or not self.grants.clients.redirect_uri_matches(callback, client['redirect_uris'])
                or not scopes <= set(client['allowed_scopes'])):
            raise ConsentRejected()
        if client.get('registration_kind') == 'cimd':
            from .cimd import CimdRejected
            try:
                self.grants.cimd._check_proof(connection, client, verification)
            except CimdRejected as error:
                raise ConsentRejected(error.reason) from None
        fingerprint = state_hash = None
        if browser_flows is not None:
            # The original request remains identifiable after a staged scope reduction.
            original_scopes = sorted(requested_scopes or scopes)
            fingerprint = self._fingerprint(client, callback, resource, original_scopes, challenge, state, session_only)
            if state is not None:
                state_hash = request_hash(state)
                existing = self._resume(connection, client, state_hash, fingerprint, browser_flows)
                if existing is not None:
                    return existing
                if client.get('registration_kind') == 'cimd' and not onboarding_transition:
                    # Registry approval can change the route taken by an identical /authorize retry.
                    from .client_onboarding import ClientOnboardingService, OnboardingRejected
                    try:
                        existing = ClientOnboardingService(self.grants)._resume(connection, client_id, state,
                            callback, resource, original_scopes, challenge, browser_flows, session_only)
                    except OnboardingRejected:
                        raise ConsentRejected() from None
                    if existing is not None:
                        return existing
            if len(browser_flows) >= 16:
                raise ConsentRejected()
        counts = connection.execute(text("""SELECT count(*) AS total,
            count(*) FILTER (WHERE decision IS NULL) AS active,
            count(*) FILTER (WHERE client_id=:id) AS client_total,
            count(*) FILTER (WHERE client_id=:id AND decision IS NULL) AS client_active
            FROM c0_oauth_consent"""), {'id':internal_id(client)}).mappings().one()
        if (counts['active'] >= 1000 or counts['client_active'] >= 32
                or counts['total'] >= 8192 or counts['client_total'] >= 512):
            raise ConsentRejected()
        connection.execute(text('''INSERT INTO c0_oauth_consent
            (hash,browser_hash,client_id,client_revision,issuer,native_client,resource,callback,scopes,challenge,state,expires_at,expected_account_id,request_fingerprint,state_hash)
            VALUES (:hash,:browser,:client,:revision,:issuer,:native,:resource,:callback,CAST(:scopes AS jsonb),:challenge,:state,:expires,:account,:fingerprint,:state_hash)'''),
            {'hash': _digest(pending.request), 'browser': _browser_hash(pending.binding),
             'client': internal_id(client), 'revision': client['revision'], 'issuer': self.grants.access.issuer,
             'native': self.grants.native_client, 'resource': resource, 'callback': callback,
             'scopes': json.dumps(sorted(scopes)), 'challenge': challenge, 'state': state,
             'account': account_id, 'fingerprint':fingerprint, 'state_hash':state_hash,
             'expires': expires or _date(self.grants._now() + 300)})
        return pending

    @staticmethod
    def _fingerprint(client, callback, resource, scopes, challenge, state, session_only):
        return request_hash(json.dumps([client['client_id'], client['revision'], callback,
            resource, sorted(scopes), challenge, state, session_only]))

    def _resume(self, connection, client, state_hash, fingerprint, browser_flows):
        existing = connection.execute(text("""SELECT hash,browser_hash,request_fingerprint
            FROM c0_oauth_consent WHERE client_id=:client AND issuer=:issuer AND native_client=:native
            AND state_hash=:state AND expires_at>:now"""), {'client':internal_id(client),
            'issuer':self.grants.access.issuer, 'native':self.grants.native_client,
            'state':state_hash, 'now':_date(self.grants._now())}).mappings().first()
        if existing is None:
            return None
        for selector, proof in browser_flows:
            if (_digest(selector) == existing['hash'] and existing['request_fingerprint'] == fingerprint
                    and hmac.compare_digest(_browser_hash(proof), existing['browser_hash'])):
                return PendingConsent(selector, proof)
        raise ConsentRejected()

    def _request(self, connection, request, binding):
        try:
            parameters = {'hash': _digest(request), 'browser': _browser_hash(binding), 'now': _date(self.grants._now()),
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
            raise ConsentRejected('metadata_changed')
        return row, client

    def available(self, request, binding, *, account_id=None):
        with self.grants.access.database.engine.begin() as connection:
            self.bind_login_account(connection, request, binding, account_id)

    def bind_login_account(self, connection, request, binding, account_id):
        """Verify the selected flow in the same transaction that publishes login."""
        if account_id is not None:
            self.grants._lock(connection, roles=True)
            connection.execute(text('SELECT pg_advisory_xact_lock(49380)'))
        row, _ = self._request(connection, request, binding)
        if account_id is not None:
            if row['expected_account_id'] not in (None, account_id):
                raise ConsentRejected()
            if row['expected_account_id'] is None:
                connection.execute(text("""UPDATE c0_oauth_consent SET expected_account_id=:account
                    WHERE hash=:hash"""), {'account':account_id, 'hash':row['hash']})

    def review(self, session, request, binding):
        """Bind the first authenticated reviewer under the completion lock."""
        if not isinstance(session, SessionContext) or session.expires_at.timestamp() <= self.grants._now():
            raise ConsentRejected()
        with self.grants.access.database.engine.begin() as connection:
            self.grants._lock(connection, roles=True)
            connection.execute(text('SELECT pg_advisory_xact_lock(49380)'))
            row, client = self._request(connection, request, binding)
            actor = self.grants.access.checked_actor(connection, session.actor)
            if row['expected_account_id'] not in (None, actor.user_id):
                raise ConsentRejected()
            if row['decision'] is not None:
                return {'decision': 'approved' if row['decision'] else 'declined'}
            if row['expected_account_id'] is None:
                connection.execute(text("""UPDATE c0_oauth_consent SET expected_account_id=:account
                    WHERE hash=:hash"""), {'account': actor.user_id, 'hash': row['hash']})
            return self._view(row, client, binding)

    def view(self, request, binding):
        with self.grants.access.database.engine.connect() as connection:
            row, client = self._request(connection, request, binding)
            if row['decision'] is not None:
                raise ConsentRejected()
            return self._view(row, client, binding)

    @staticmethod
    def _view(row, client, binding):
        # State/challenge/binding and native identity stay out of the UI DTO.
        return {'client_id': client['client_id'], 'client_name': client['client_name'],
                'callback': row['callback'], 'scopes': row['scopes'], 'resource': row['resource'],
                'expires_at': row['expires_at'], 'background_requested': row['background_requested'],
                'session_only': _session_only(binding)}

    def prepare_background(self, session, request, binding, *, scopes):
        """Stage explicit offline sign-in, preserving the original five-minute bound."""
        if (not self.grants.background_enabled or not isinstance(session, SessionContext)
                or session.expires_at.timestamp() <= self.grants._now()
                or type(scopes) not in (set, frozenset) or not scopes):
            raise ConsentRejected()
        with self.grants.access.database.engine.begin() as connection:
            self.grants._lock(connection, roles=True)
            connection.execute(text('SELECT pg_advisory_xact_lock(49380)'))
            row, _ = self._request(connection, request, binding)
            actor = self.grants.access.checked_actor(connection, session.actor)
            if (row['decision'] is not None or _session_only(binding) or not scopes <= set(row['scopes'])
                    or row['expected_account_id'] not in (None, actor.user_id)):
                raise ConsentRejected()
            for scope, role in [('c0:write',Role.EDITOR),('c0:admin',Role.ADMIN)]:
                if scope in scopes:
                    require_consent_role(actor, role)
            connection.execute(text('''UPDATE c0_oauth_consent SET background_requested=true,
                expected_account_id=:account,scopes=CAST(:scopes AS jsonb) WHERE hash=:hash'''),
                {'account':actor.user_id,'scopes':json.dumps(sorted(scopes)),'hash':row['hash']})

    def complete(self, session, request, binding, *, approve, scopes=None, verification=None, persistent=False):
        """Trusted app adapter checks same-origin CSRF before invoking this."""
        if (not isinstance(session, SessionContext) or type(approve) is not bool
                or session.expires_at.tzinfo is None or type(persistent) is not bool):
            raise ConsentRejected()
        with self.grants.access.database.engine.begin() as connection:
            # Stable lock order: role -> grant -> consent. Failed consent/code
            # creation rolls back both; concurrent completions have one winner.
            self.grants._lock(connection, roles=True)
            connection.execute(text('SELECT pg_advisory_xact_lock(49380)'))
            row, client = self._request(connection, request, binding)
            if session.expires_at.timestamp() <= self.grants._now() or (persistent and _session_only(binding)):
                raise ConsentRejected()
            actor = self.grants.access.checked_actor(connection, session.actor)
            if row['expected_account_id'] not in (None, actor.user_id):
                raise ConsentRejected()
            if row['decision'] is not None:
                return ConsentReceipt('approved' if row['decision'] else 'declined')
            code = None
            if approve:
                if scopes is None:
                    scopes = frozenset(row['scopes'])
                if type(scopes) not in (set, frozenset) or not scopes or not scopes <= set(row['scopes']):
                    raise ConsentRejected()
                code = self.grants._issue_code(connection, session, client['client_id'],
                    callback=row['callback'], scopes=scopes, challenge=row['challenge'], resource=row['resource'],
                    verification=verification, persistent=persistent, session_only=_session_only(binding))
            if row['request_fingerprint'] is None:
                connection.execute(text('DELETE FROM c0_oauth_consent WHERE hash=:hash'), {'hash': row['hash']})
            else:
                connection.execute(text("""UPDATE c0_oauth_consent SET decision=:decision,
                    expected_account_id=:account,state=NULL,challenge='',callback='' WHERE hash=:hash"""),
                    {'decision':approve, 'account':actor.user_id, 'hash':row['hash']})
            return ConsentResult(row['callback'], row['state'], code)
