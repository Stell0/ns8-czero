# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Administrator-approved public OAuth clients; no client secrets or URL fetches."""
import json
import hashlib
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy import text

from .identity import Actor, PermissionDenied, Role
from .operations import SCOPES


class ClientConflict(ValueError):
    def __init__(self):
        super().__init__('oauth_client_conflict')


def redirect_uri(value):
    if not isinstance(value, str) or not value.isascii() or not 1 <= len(value) <= 1024:
        raise ValueError('invalid_redirect_uri')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if (not parsed.hostname or parsed.username is not None or parsed.password is not None
                or '?' in value or '#' in value or '*' in value or '\\' in value
                or any(character.isspace() or ord(character) < 33 for character in value)
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError()
        if parsed.scheme != 'https' and not (parsed.scheme == 'http'
                and parsed.hostname in ('127.0.0.1', '::1', 'localhost')):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('invalid_redirect_uri') from None
    # Exact strings are retained; authorization must never match wildcards.
    return value


def _view(row):
    return {'client_id': str(row['id']), 'client_name': row['name'],
            'redirect_uris': row['redirect_uris'], 'allowed_scopes': row['scopes'],
            'token_endpoint_auth_method': 'none', 'enabled': row['enabled'],
            'revision': row['revision'], 'created_at': row['created_at']}


class OAuthClientService:
    def __init__(self, access):
        self.access = access

    def _authorize(self, connection, actor):
        if self.access is None:
            raise PermissionDenied()
        self.access._actor(connection, actor.user_id).require(Role.ADMIN)

    def register(self, actor: Actor, name: str, redirect_uris: list[str], *, scopes=('c0:read',)):
        if self.access is None:
            raise PermissionDenied()
        with self.access.database.engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(49378)'))
            self._authorize(connection, actor)
            if not isinstance(name, str) or not name.strip() or not name.isprintable() or len(name) > 128:
                raise ValueError('invalid_client_name')
            if not isinstance(redirect_uris, list) or not 1 <= len(redirect_uris) <= 4:
                raise ValueError('invalid_redirect_uri')
            uris = [redirect_uri(value) for value in redirect_uris]
            if len(set(uris)) != len(uris):
                raise ValueError('invalid_redirect_uri')
            if type(scopes) not in (list, tuple, set, frozenset) or not 1 <= len(scopes) <= 3:
                raise ValueError('invalid_client_scopes')
            if any(not isinstance(value, str) or value not in SCOPES for value in scopes):
                raise ValueError('invalid_client_scopes')
            if len(set(scopes)) != len(scopes):
                raise ValueError('invalid_client_scopes')
            fingerprint = hashlib.sha256(json.dumps({'name': name, 'uris': uris,
                'scopes': sorted(scopes)}, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
            existing = connection.execute(text('SELECT * FROM c0_oauth_clients WHERE descriptor_hash=:hash'),
                {'hash': fingerprint}).mappings().one_or_none()
            if existing is not None:
                # Identical retries cannot silently reenable a disabled client.
                return _view(existing)
            if connection.execute(text('SELECT count(*) FROM c0_oauth_clients')).scalar_one() >= 64:
                raise ValueError('oauth_client_limit')
            row = connection.execute(text('''INSERT INTO c0_oauth_clients(id,name,descriptor_hash,redirect_uris,scopes)
                VALUES (:id,:name,:hash,CAST(:uris AS jsonb),CAST(:scopes AS jsonb)) RETURNING *'''),
                {'id': uuid4(), 'name': name, 'uris': json.dumps(uris),
                 'hash': fingerprint, 'scopes': json.dumps(sorted(scopes))}).mappings().one()
            return _view(row)

    def list(self, actor: Actor):
        if self.access is None:
            raise PermissionDenied()
        with self.access.database.engine.connect() as connection:
            self._authorize(connection, actor)
            return [_view(row) for row in connection.execute(text(
                'SELECT * FROM c0_oauth_clients ORDER BY created_at,id LIMIT 64')).mappings()]

    def set_enabled(self, actor: Actor, client_id: UUID, *, enabled: bool, expected_revision: int):
        if self.access is None:
            raise PermissionDenied()
        with self.access.database.engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(49378)'))
            self._authorize(connection, actor)
            if not isinstance(client_id, UUID) or type(enabled) is not bool or type(expected_revision) is not int:
                raise ValueError('invalid_client_update')
            row = connection.execute(text('''UPDATE c0_oauth_clients SET enabled=:enabled,revision=revision+1
                WHERE id=:id AND revision=:revision AND revision<2147483646 RETURNING *'''),
                {'id': client_id, 'enabled': enabled, 'revision': expected_revision}).mappings().one_or_none()
            if row is None:
                raise ClientConflict()
            return _view(row)

    def _registered(self, connection, client_id):
        """Trusted OAuth adapter lookup; public callers cannot list clients."""
        try:
            identifier = UUID(client_id)
        except (TypeError, ValueError, AttributeError):
            return None
        row = connection.execute(text('SELECT * FROM c0_oauth_clients WHERE id=:id AND enabled'),
            {'id': identifier}).mappings().one_or_none()
        return _view(row) if row is not None else None
