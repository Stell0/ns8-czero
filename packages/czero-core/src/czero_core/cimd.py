# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Administrator approval and local authority for optional CIMD clients.

Network validation belongs to the application. Only trusted Python adapters may
supply ClientMetadata or VerificationProof; neither is a public request DTO.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import time
from uuid import UUID, uuid4

from sqlalchemy import text

from .cimd_metadata import ClientMetadata, metadata_url
from .oauth_clients import ClientConflict, OAuthClientService
from .operations import SCOPES


class CimdRejected(ValueError):
    def __init__(self):
        super().__init__('cimd_unavailable')


@dataclass(frozen=True)
class VerificationProof:
    service: object = field(repr=False)
    client_id: UUID
    metadata_url: str
    revision: int
    policy_revision: int
    metadata_digest: str
    verified_at: float


def _date(value):
    return datetime.fromtimestamp(value, timezone.utc)


def _lock(connection):
    # Match grant/consent order; final revocation lock is acquired only after
    # current administrator checks. Reads already in flight finish before return.
    for key in (49372, 49378, 49379, 49380):
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})


def _revoke(connection, identifier=None):
    connection.execute(text('SELECT pg_advisory_xact_lock(49382)'))
    selection = 'SELECT client_id FROM c0_cimd_clients' if identifier is None else 'SELECT CAST(:id AS uuid)'
    for table in ('c0_oauth_grants', 'c0_oauth_consent'):
        connection.execute(text(f'DELETE FROM {table} WHERE client_id IN ({selection})'), {'id': identifier})


def _view(row):
    return {'client_id': str(row['client_id']), 'metadata_url': row['metadata_url'],
            'client_name': row['name'], 'enabled': row['enabled'], 'revision': row['revision'],
            'allowed_scopes': row['scopes'], 'metadata_digest': row['metadata_digest'],
            'approved_descriptor': row['approved_descriptor'], 'review_required': row['review_required'],
            'verified_at': row['verified_at'], 'fresh_until': row['fresh_until']}


_QUERY = '''SELECT c.*,b.client_id,b.metadata_url,b.approved_descriptor,b.metadata_digest,
    b.review_required,b.verified_at,b.fresh_until FROM c0_cimd_clients b
    JOIN c0_oauth_clients c ON c.id=b.client_id'''


class CimdPolicyService:
    """Trusted installation policy, independent of authentication availability."""
    def __init__(self, database):
        self.database = database

    def enabled(self):
        with self.database.engine.connect() as connection:
            return connection.execute(text('SELECT enabled FROM c0_cimd_policy WHERE id=1')).scalar_one()

    def sync_policy(self, enabled):
        """Trusted native configuration only, never an HTTP administration API."""
        if type(enabled) is not bool:
            raise ValueError('invalid_cimd_policy')
        with self.database.engine.begin() as connection:
            _lock(connection)
            row = connection.execute(text('SELECT * FROM c0_cimd_policy WHERE id=1')).mappings().one()
            if row['enabled'] == enabled:
                return
            if row['revision'] >= 2147483646:
                raise CimdRejected()
            _revoke(connection)
            connection.execute(text('UPDATE c0_cimd_policy SET enabled=:enabled,revision=revision+1 WHERE id=1'),
                               {'enabled': enabled})


class CimdService(CimdPolicyService):
    def __init__(self, access, *, now=time.time):
        super().__init__(access.database)
        self.access = access
        self.clients = OAuthClientService(access)
        self._now = now

    @staticmethod
    def _policy(connection):
        row = connection.execute(text('SELECT * FROM c0_cimd_policy WHERE id=1')).mappings().one()
        if not row['enabled']:
            raise CimdRejected()
        return row

    def status(self, actor):
        with self.access.database.engine.connect() as connection:
            self.clients._authorize(connection, actor)
            policy = connection.execute(text('SELECT * FROM c0_cimd_policy WHERE id=1')).mappings().one()
            rows = connection.execute(text(_QUERY + ' ORDER BY c.created_at,c.id LIMIT 64')).mappings()
            return {'enabled': policy['enabled'], 'revision': policy['revision'],
                    'clients': [_view(row) for row in rows]}

    def authorize_preview(self, actor):
        with self.access.database.engine.connect() as connection:
            self.clients._authorize(connection, actor)
            self._policy(connection)

    def approval(self, url):
        """Trusted prefetch gate: unknown/disabled URLs never cause network work."""
        metadata_url(url)
        with self.access.database.engine.connect() as connection:
            self._policy(connection)
            row = connection.execute(text(_QUERY + ' WHERE b.metadata_url=:url AND c.enabled'),
                                     {'url': url}).mappings().one_or_none()
            if row is None or row['review_required']:
                raise CimdRejected()
            return _view(row)

    @staticmethod
    def _scopes(metadata, scopes):
        if (not isinstance(metadata, ClientMetadata) or type(scopes) not in (list, tuple, set, frozenset)
                or not 1 <= len(scopes) <= 3 or any(type(s) is not str or s not in SCOPES for s in scopes)
                or len(set(scopes)) != len(scopes)
                or (metadata.scope_ceiling is not None and not set(scopes) <= set(metadata.scope_ceiling))):
            raise ValueError('invalid_client_scopes')
        return sorted(scopes)

    def approve(self, actor, metadata, *, scopes=('c0:read',), expected_digest,
                client_id=None, expected_revision=None, cache_seconds=0):
        scopes = self._scopes(metadata, scopes)
        if metadata.digest != expected_digest:
            raise ClientConflict()
        if (not 0 <= cache_seconds <= 300 or (client_id is not None and
                (not isinstance(client_id, UUID) or type(expected_revision) is not int))):
            raise ValueError('invalid_client_update')
        with self.access.database.engine.begin() as connection:
            _lock(connection)
            self.clients._authorize(connection, actor)
            self._policy(connection)
            row = connection.execute(text(_QUERY + ' WHERE b.metadata_url=:url'),
                                     {'url': metadata.client_id}).mappings().one_or_none()
            if client_id is None and row is not None:
                if row['metadata_digest'] != expected_digest or row['scopes'] != scopes:
                    raise ClientConflict()
                return _view(row)  # Never reenable or clear a sticky review.
            if client_id is not None:
                if (row is None or row['client_id'] != client_id or row['revision'] != expected_revision
                        or expected_revision >= 2147483646):
                    raise ClientConflict()
                _revoke(connection, client_id)
                connection.execute(text('''UPDATE c0_oauth_clients SET name=:name,redirect_uris=CAST(:uris AS jsonb),
                    scopes=CAST(:scopes AS jsonb),revision=revision+1 WHERE id=:id'''),
                    {'id': client_id, 'name': metadata.client_name, 'uris': json.dumps(metadata.redirect_uris),
                     'scopes': json.dumps(scopes)})
            else:
                if connection.execute(text('SELECT count(*) FROM c0_oauth_clients')).scalar_one() >= 64:
                    raise ValueError('oauth_client_limit')
                client_id = uuid4()
                # A dedicated namespace cannot collide with legacy descriptor digests.
                connection.execute(text('''INSERT INTO c0_oauth_clients(id,name,descriptor_hash,redirect_uris,scopes)
                    VALUES (:id,:name,:hash,CAST(:uris AS jsonb),CAST(:scopes AS jsonb))'''),
                    {'id': client_id, 'name': metadata.client_name, 'hash': 'cimd:' + client_id.hex,
                     'uris': json.dumps(metadata.redirect_uris), 'scopes': json.dumps(scopes)})
            now = self._now()
            connection.execute(text('''INSERT INTO c0_cimd_clients
                (client_id,metadata_url,approved_descriptor,metadata_digest,verified_at,fresh_until)
                VALUES (:id,:url,CAST(:descriptor AS jsonb),:digest,:now,:fresh)
                ON CONFLICT (client_id) DO UPDATE SET approved_descriptor=EXCLUDED.approved_descriptor,
                    metadata_digest=EXCLUDED.metadata_digest,verified_at=EXCLUDED.verified_at,
                    fresh_until=EXCLUDED.fresh_until,review_required=false'''),
                {'id': client_id, 'url': metadata.client_id, 'descriptor': json.dumps(metadata.descriptor()),
                 'digest': metadata.digest, 'now': _date(now), 'fresh': _date(now + cache_seconds)})
            return _view(connection.execute(text(_QUERY + ' WHERE b.client_id=:id'),
                                           {'id': client_id}).mappings().one())

    def observe(self, metadata, *, expected_revision, cache_seconds=0):
        """Attest a trusted fetch/cache hit; commit changed-document review first."""
        if not isinstance(metadata, ClientMetadata) or not 0 <= cache_seconds <= 300:
            raise CimdRejected()
        result = None
        with self.access.database.engine.begin() as connection:
            _lock(connection)
            policy = self._policy(connection)
            row = connection.execute(text(_QUERY + ' WHERE b.metadata_url=:url'),
                                     {'url': metadata.client_id}).mappings().one_or_none()
            if row is None or row['revision'] != expected_revision or row['review_required']:
                raise CimdRejected()
            if row['metadata_digest'] != metadata.digest:
                connection.execute(text('UPDATE c0_cimd_clients SET review_required=true WHERE client_id=:id'),
                                   {'id': row['client_id']})
                connection.execute(text('DELETE FROM c0_oauth_consent WHERE client_id=:id'),
                                   {'id': row['client_id']})
            else:
                now = self._now()
                connection.execute(text('UPDATE c0_cimd_clients SET verified_at=:now,fresh_until=:fresh WHERE client_id=:id'),
                    {'id': row['client_id'], 'now': _date(now), 'fresh': _date(now + cache_seconds)})
                if row['enabled']:
                    result = VerificationProof(self, row['client_id'], metadata.client_id, row['revision'],
                                               policy['revision'], metadata.digest, now)
        if result is None:
            raise CimdRejected()
        return result

    def _check_proof(self, connection, client, proof):
        policy = self._policy(connection)
        if (not isinstance(proof, VerificationProof) or proof.service is not self
                or proof.metadata_url != client['client_id'] or proof.client_id != client['internal_id']
                or proof.revision != client['revision'] or proof.policy_revision != policy['revision']
                or proof.metadata_digest != client['metadata_digest'] or client['review_required']
                or not 0 <= self._now() - proof.verified_at <= 30):
            raise CimdRejected()
