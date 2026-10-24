# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded first-party access administration; summaries never confer authority."""
from uuid import UUID

from sqlalchemy import text

from .client_onboarding import ClientOnboardingService, OnboardingRejected
from .identity import Actor, PermissionDenied, Role
from .oauth_clients import ClientConflict
from .oauth_grants import GrantRejected, _date
from .renewal import RenewalRejected


def permissions(role, scopes=None):
    rank = {None: 0, 'reader': 1, 'editor': 2, 'admin': 3}[role]
    return {name: rank >= level and (scopes is None or 'c0:' + scope in scopes)
            for name, scope, level in [('read', 'read', 1), ('write', 'write', 2), ('manage', 'admin', 3)]}


def page_limits(limit, offset, maximum):
    if (type(limit) is not int or not 1 <= limit <= maximum
            or type(offset) is not int or not 0 <= offset <= 100000):
        raise ValueError('invalid_page')


class WorkspaceAccessService:
    """Reuse current access/client/grant services; never contact an IdP on reads."""
    def __init__(self, grants):
        self.grants = grants
        self.access = grants.access
        self.onboarding = ClientOnboardingService(grants)

    def _authorize(self, connection, actor):
        # Browser administration only. A Manage-only delegated token is neither
        # a browser CSRF context nor permission to enumerate native authority.
        if not isinstance(actor, Actor) or actor.delegation is not None or actor.delegated_scopes is not None:
            raise PermissionDenied()
        self.access.checked_actor(connection, actor).require(Role.ADMIN)

    def _account(self, connection, identifier):
        if not isinstance(identifier, UUID):
            raise ValueError('account_not_found')
        row = connection.execute(text('''SELECT a.id,a.username,a.display_name,a.last_seen,a.access_revision,
            CASE WHEN a.account_key=:owner THEN 'admin' ELSE m.role END AS role,
            a.account_key=:owner AS is_owner,
            EXISTS(SELECT 1 FROM c0_account_blocks b WHERE b.account_id=a.id) AS blocked
            FROM c0_accounts a LEFT JOIN c0_memberships m ON m.account_id=a.id
            WHERE a.id=:id AND a.issuer=:issuer'''),
            {'id': identifier, 'issuer': self.access.issuer, 'owner': self.access.owner_account_key}).mappings().one_or_none()
        if row is None:
            raise ValueError('account_not_found')
        return {**row, 'permissions': permissions(row['role'])}

    def overview(self, actor, *, limit=25, offset=0):
        page_limits(limit, offset, 100)
        with self.access.database.engine.begin() as connection:
            self.grants._lock(connection, roles=True)
            self._authorize(connection, actor)
            rows = connection.execute(text('''SELECT a.id FROM c0_accounts a
                WHERE a.issuer=:issuer ORDER BY EXISTS (
                    SELECT 1 FROM c0_client_onboarding o JOIN c0_cimd_policy p ON p.id=1
                    WHERE o.account_id=a.id AND o.issuer=:issuer AND o.native_client=:native
                    AND o.resource=:resource AND o.expires_at>:now AND p.enabled
                    AND o.policy_revision=p.revision) DESC,a.username,a.id LIMIT :limit OFFSET :offset'''),
                {'issuer': self.access.issuer, 'native': self.grants.native_client, 'resource': self.grants.resource,
                 'now': _date(self.grants._now()), 'limit': limit+1, 'offset': offset}).scalars().all()
            pending = connection.execute(text('''SELECT count(*) FROM c0_client_onboarding o
                JOIN c0_cimd_policy p ON p.id=1 JOIN c0_accounts a ON a.id=o.account_id
                WHERE o.issuer=:issuer AND a.issuer=:issuer AND o.native_client=:native
                AND o.resource=:resource AND o.expires_at>:now AND p.enabled AND o.policy_revision=p.revision'''),
                {'issuer': self.access.issuer, 'native': self.grants.native_client,
                 'resource': self.grants.resource, 'now': _date(self.grants._now())}).scalar_one()
            return {'accounts': [self._account(connection, key) for key in rows[:limit]],
                    'has_more': len(rows)>limit, 'offset': offset, 'pending_count': pending}

    def _request(self, connection, identifier):
        if not isinstance(identifier, UUID):
            raise OnboardingRejected()
        policy = self.grants.cimd._policy(connection)
        row = connection.execute(text('''SELECT o.* FROM c0_client_onboarding o
            JOIN c0_accounts a ON a.id=o.account_id WHERE o.id=:id AND o.expires_at>:now
            AND o.issuer=:issuer AND a.issuer=:issuer AND o.native_client=:native
            AND o.resource=:resource AND o.policy_revision=:policy'''),
            {'id': identifier, 'now': _date(self.grants._now()), 'issuer': self.access.issuer,
             'native': self.grants.native_client, 'resource': self.grants.resource,
             'policy': policy['revision']}).mappings().one_or_none()
        if row is None:
            raise OnboardingRejected()
        return row

    def _request_view(self, connection, row):
        view = self.onboarding._view(connection, row)
        client = self.grants.clients._registered(connection, row['metadata_url'])
        review = client is not None and client.get('review_required', False)
        approved = view['approved'] and not review
        state = ('waiting_for_consent' if approved and set(view['scopes']) <= set(view['allowed_scopes'])
                 else 'needs_permissions' if approved else 'needs_approval')
        return {**view, 'id': row['id'], 'kind': 'request', 'status': state,
                'account_id': row['account_id'], 'client_name': client['client_name'] if client else None,
                'permissions': permissions(None)}

    def request(self, actor, identifier):
        with self.access.database.engine.begin() as connection:
            self.onboarding._lock(connection)
            self._authorize(connection, actor)
            row = self._request(connection, identifier)
            return {**self._request_view(connection, row),
                    'account': self._account(connection, row['account_id'])}

    def applications(self, actor, account_id, *, limit=10, offset=0):
        page_limits(limit, offset, 50)
        with self.access.database.engine.begin() as connection:
            self.grants._lock(connection, roles=True)
            self._authorize(connection, actor)
            account = self._account(connection, account_id)
            rows = connection.execute(text('''SELECT kind,id FROM (
                SELECT 0 AS kind,o.id FROM c0_client_onboarding o JOIN c0_cimd_policy p ON p.id=1
                WHERE o.account_id=:account AND o.expires_at>:now AND o.issuer=:issuer
                AND o.native_client=:native AND o.resource=:resource AND p.enabled AND o.policy_revision=p.revision
                UNION ALL SELECT 1 AS kind,g.id FROM c0_oauth_grants g
                WHERE g.account_id=:account AND g.issuer=:issuer AND g.native_client=:native AND g.resource=:resource
                AND EXISTS(SELECT 1 FROM c0_oauth_tokens t WHERE t.grant_id=g.id)
                ) entries ORDER BY kind,id LIMIT :limit OFFSET :offset'''),
                {'account': account_id, 'now': _date(self.grants._now()), 'issuer': self.access.issuer,
                 'native': self.grants.native_client, 'resource': self.grants.resource,
                 'limit': limit+1, 'offset': offset}).mappings().all()
            items = []
            for row in rows[:limit]:
                if row['kind'] == 0:
                    items.append(self._request_view(connection, self._request(connection, row['id'])))
                else:
                    items.append(self._connection(connection, row['id'], account))
            return {'applications': items, 'has_more': len(rows)>limit, 'offset': offset}

    def _connection(self, connection, identifier, account):
        row = connection.execute(text('''SELECT g.*,c.name AS client_name FROM c0_oauth_grants g
            JOIN c0_oauth_clients c ON c.id=g.client_id WHERE g.id=:id'''), {'id': identifier}).mappings().one()
        now = _date(self.grants._now())
        client = self.grants.clients._by_id(connection, row['client_id'])
        valid = (account['role'] is not None and not account['blocked'] and client is not None
                 and client['revision'] == row['client_revision'] and not client.get('review_required', False)
                 and (row['expires_at'] is not None and row['expires_at']>now
                      or row['persistent'] and row['expires_at'] is None and row['idle_until']>now)
                 and (not row['persistent'] or self.grants.background_enabled))
        state = 'connected' if valid else 'needs_reconnect'
        if valid and row['native_authority_id'] is not None:
            native = None if self.grants.authority is None else connection.execute(text('''SELECT * FROM c0_native_authority
                WHERE id=:id AND issuer=:issuer AND native_client=:native'''),
                {'id': row['native_authority_id'], 'issuer': self.access.issuer,
                 'native': self.grants.native_client}).mappings().one_or_none()
            # A stale provider proof may renew normally. It is not a reconnect
            # requirement, nor does this summary extend deadlines/check authority.
            if (native is None or native['account_id'] != account['id'] or native['revoked']
                    or native['checking'] or native['idle_until']<=now
                    or native['expires_at'] is not None and native['expires_at']<=now
                    or native['authority_kind']=='background' and not self.grants.background_enabled):
                state = 'needs_reconnect'
            else:
                try:
                    self.grants.authority._open(native)
                except RenewalRejected:
                    state = 'needs_reconnect'
                if state=='connected' and native['verified_until']<=now:
                    state = 'renewal_required'
        return {'id': row['id'], 'kind': 'connection', 'account_id': account['id'],
                'client_name': row['client_name'], 'client_id': row['client_id'], 'scopes': row['scopes'],
                'persistent': row['persistent'], 'expires_at': row['expires_at'], 'idle_until': row['idle_until'],
                'last_used_at': row['last_used_at'], 'status': state,
                'permissions': permissions(account['role'], row['scopes']) if state=='connected' else permissions(None)}

    def decline(self, actor, identifier):
        with self.access.database.engine.begin() as connection:
            self.onboarding._lock(connection)
            self._authorize(connection, actor)
            row = self._request(connection, identifier)
            connection.execute(text('DELETE FROM c0_client_onboarding WHERE id=:id'), {'id': row['id']})

    def approve(self, actor, identifier, metadata, *, scopes, expected_digest,
                client_id=None, expected_revision=None, cache_seconds=0):
        scopes = self.grants.cimd._scopes(metadata, scopes)
        with self.access.database.engine.begin() as connection:
            self.onboarding._lock(connection)
            self._authorize(connection, actor)
            row = self._request(connection, identifier)
            account = self._account(connection, row['account_id'])
            if account['blocked'] or account['role'] is None:
                raise PermissionDenied()
            if metadata.client_id != row['metadata_url'] or row['parameters']['redirect_uri'] not in metadata.redirect_uris:
                raise ClientConflict()
            existing = connection.execute(text('''SELECT c.id,c.scopes,c.enabled,c.revision FROM c0_cimd_clients b
                JOIN c0_oauth_clients c ON c.id=b.client_id WHERE b.metadata_url=:url'''),
                {'url': row['metadata_url']}).mappings().one_or_none()
            earlier = set(existing['scopes']) if existing else set()
            if (existing is not None and (not existing['enabled'] or client_id!=existing['id']
                    or expected_revision!=existing['revision']) or existing is None and client_id is not None
                    or not earlier <= set(scopes) or not set(scopes) <= earlier | set(row['parameters'].get('scope','c0:read').split())):
                raise ClientConflict()
            return self.grants.cimd._approve(connection, actor, metadata, scopes=scopes,
                expected_digest=expected_digest, client_id=client_id, expected_revision=expected_revision,
                cache_seconds=cache_seconds)

    def disconnect(self, actor, identifier):
        if not isinstance(identifier, UUID):
            raise GrantRejected()
        with self.access.database.engine.begin() as connection:
            self.grants._lock(connection, roles=True)
            self._authorize(connection, actor)
            row = connection.execute(text('''SELECT client_id FROM c0_oauth_grants
                WHERE id=:id AND issuer=:issuer AND native_client=:native AND resource=:resource'''),
                {'id': identifier, 'issuer': self.access.issuer, 'native': self.grants.native_client,
                 'resource': self.grants.resource}).mappings().one_or_none()
            if row is None:
                raise GrantRejected()
            # All first-party disconnects finish after in-flight authorized
            # operations, including legacy UUID clients; siblings stay intact.
            connection.execute(text('SELECT pg_advisory_xact_lock(49382)'))
            connection.execute(text('DELETE FROM c0_oauth_grants WHERE id=:id'), {'id': identifier})
