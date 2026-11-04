# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Personal credentials with transaction-bound revocation and fixed space ceilings."""
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import secrets
from uuid import UUID, uuid4

from sqlalchemy import text
from .identity import PermissionDenied, Role, TokenRejected
from .spaces import SpaceService

KEY = re.compile(r'c0k_[A-Za-z0-9_-]{43}')


def revoke_account_keys(connection, account_id):
    # Supported predecessor setup can change grants before this store exists.
    # There is no key authority to invalidate on those earlier schemas.
    if connection.execute(text("SELECT to_regclass('c0_api_keys') IS NOT NULL")).scalar_one():
        connection.execute(text('UPDATE c0_api_keys SET revoked_at=now() WHERE account_id=:id AND revoked_at IS NULL'),
                           {'id':account_id})


@dataclass(frozen=True, repr=False)
class ApiKeyBinding:
    service: object = field(repr=False)
    digest: str = field(repr=False)

    def validate(self, connection):
        if not isinstance(self.service, ApiKeyService):
            raise PermissionDenied()
        return self.service._row(connection, self.digest)


@dataclass(frozen=True)
class ApiKeyAccess:
    actor: object
    client_id: str
    scopes: frozenset[str]
    expires_at: datetime | None
    resource: str


class ApiKeyService:
    def __init__(self, access, *, client_id, client_secret, resource, now=None):
        self.access, self.resource = access, resource
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.configuration = hmac.new(client_secret.encode(), json.dumps(
            ['c0-api-key-v1', access.issuer, client_id, resource],
            separators=(',', ':')).encode(), hashlib.sha256).hexdigest()

    def _row(self, c, digest):
        row = c.execute(text("""SELECT k.* FROM c0_api_keys k JOIN c0_accounts a ON a.id=k.account_id
            WHERE k.digest=:digest AND k.configuration=:configuration AND k.revoked_at IS NULL
            AND (k.expires_at IS NULL OR k.expires_at>:now)
            AND a.access_revision=k.account_revision
            AND NOT EXISTS (SELECT 1 FROM unnest(k.space_ids) AS selected(id)
                LEFT JOIN c0_space_grants g ON g.space_id=selected.id AND g.account_id=k.account_id
                WHERE COALESCE(g.revision,0) IS DISTINCT FROM CAST(k.space_revisions->>CAST(selected.id AS text) AS bigint))"""),
            {'digest': digest, 'configuration': self.configuration, 'now': self._now()}).mappings().one_or_none()
        if row is None:
            raise TokenRejected()
        return row

    def _personal(self, c, actor):
        current = self.access.checked_actor(c, actor)
        current.require(Role.READER)
        if current.delegated_scopes is not None or current.api_key_binding is not None:
            raise PermissionDenied()
        return current

    @staticmethod
    def _metadata(row):
        return {k: row[k] for k in ('id', 'name', 'scopes', 'space_ids', 'created_at',
                                   'expires_at', 'revoked_at', 'last_used_at')}

    def create(self, actor, *, name, scopes, space_ids, lifetime_days=90):
        if not isinstance(name, str) or not name.strip() or len(name)>128 or not name.isprintable():
            raise ValueError('invalid_key_name')
        if not isinstance(scopes, (set, frozenset)) or not scopes or not scopes <= {'c0:read', 'c0:write'}:
            raise ValueError('invalid_key_scopes')
        if not isinstance(space_ids, (list, tuple)) or not 1<=len(space_ids)<=100:
            raise ValueError('invalid_key_spaces')
        identifiers = [UUID(str(value)) for value in space_ids]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError('invalid_key_spaces')
        if lifetime_days is not None and (type(lifetime_days) is not int or not 1<=lifetime_days<=365):
            raise ValueError('invalid_key_expiration')
        now = self._now()
        token = 'c0k_' + secrets.token_urlsafe(32)
        values = dict(id=uuid4(), name=name.strip(), scopes=sorted(scopes), space_ids=identifiers,
                      created_at=now, expires_at=now+timedelta(days=lifetime_days) if lifetime_days else None,
                      digest=hashlib.sha256(token.encode()).hexdigest(), configuration=self.configuration)
        with self.access.database.engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(49372)'))
            current = self._personal(c, actor)
            # Space policy changes also take the role lock; issuance cannot race a grant change.
            for identifier in identifiers:
                SpaceService(self.access.database, self.access).authorize(c, current,
                    Role.EDITOR if 'c0:write' in scopes else Role.READER, space_id=identifier)
            # Older released writers already advance these persisted revisions.
            # Their permission edits must invalidate keys without knowing this table.
            values['account_revision'] = c.execute(text('SELECT access_revision FROM c0_accounts WHERE id=:id'),
                                                   {'id':current.user_id}).scalar_one()
            revisions = dict(c.execute(text('SELECT space_id,revision FROM c0_space_grants WHERE account_id=:id AND space_id=ANY(CAST(:spaces AS uuid[]))'),
                                      {'id':current.user_id,'spaces':identifiers}).all())
            values['space_revisions'] = json.dumps({str(identifier):revisions.get(identifier,0) for identifier in identifiers})
            count = c.execute(text('SELECT count(*) FROM c0_api_keys WHERE account_id=:id AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>:now)'),
                              {'id': current.user_id, 'now': now}).scalar_one()
            if count >= 100:
                raise ValueError('api_key_limit')
            c.execute(text("""INSERT INTO c0_api_keys
                (id,account_id,digest,configuration,name,scopes,space_ids,created_at,expires_at,account_revision,space_revisions)
                VALUES (:id,:account,:digest,:configuration,:name,:scopes,:space_ids,:created_at,:expires_at,:account_revision,CAST(:space_revisions AS jsonb))"""),
                {**values, 'account': current.user_id})
        return {**{k:values[k] for k in ('id','name','scopes','space_ids','created_at','expires_at')}, 'key': token}

    def list(self, actor):
        with self.access.database.engine.begin() as c:
            current = self._personal(c, actor)
            rows = c.execute(text('SELECT * FROM c0_api_keys WHERE account_id=:id ORDER BY (revoked_at IS NULL AND (expires_at IS NULL OR expires_at>now())) DESC, created_at DESC LIMIT 100'),
                             {'id': current.user_id}).mappings().all()
            return [self._metadata(row) for row in rows]

    def revoke(self, actor, identifier):
        with self.access.database.engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(49372)'))
            c.execute(text('SELECT pg_advisory_xact_lock(49382)'))
            current = self._personal(c, actor)
            c.execute(text('UPDATE c0_api_keys SET revoked_at=COALESCE(revoked_at,:now) WHERE id=:id AND account_id=:account'),
                      {'now':self._now(), 'id':UUID(str(identifier)), 'account':current.user_id})

    def verify(self, token, *, resource):
        if not isinstance(token, str) or not KEY.fullmatch(token) or resource != self.resource:
            raise TokenRejected()
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.access.database.engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock_shared(49382)'))
            row = self._row(c, digest)
            actor = self.access._actor(c, row['account_id'])
            actor = replace(actor, api_key_binding=ApiKeyBinding(self, digest), delegated_scopes=frozenset(row['scopes']))
            c.execute(text('UPDATE c0_api_keys SET last_used_at=:now WHERE id=:id AND (last_used_at IS NULL OR last_used_at<:before)'),
                      {'now':self._now(), 'before':self._now()-timedelta(minutes=5), 'id':row['id']})
            return ApiKeyAccess(actor, 'api-key:'+str(row['id']), frozenset(row['scopes']), row['expires_at'], resource)
