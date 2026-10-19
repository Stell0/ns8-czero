# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persisted space policies; a selector is never proof of membership."""
import hashlib
import json
from copy import copy
from dataclasses import replace
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .identity import PermissionDenied, Role
from .operations import ScopeDenied
from .receipts import _KEY, snapshot

SPACE_LOCK = 49381
_RANK = {Role.READER: 1, Role.EDITOR: 2, Role.ADMIN: 3}


def content_row(row):
    """Remove storage ownership only at the SQL row boundary, never in payloads."""
    return {key: value for key, value in row.items() if key != 'space_id'}


def hold_authority(connection):
    """Linearize a content write with role, client and token invalidation.

    Call after the content mutex, before refreshing authority and touching rows.
    Administrative policy writers never acquire content mutexes. Shared locks
    allow independent content transactions while a revocation waits for their
    commits; after revocation commits a captured token cannot start a write.
    """
    for lock in (49372, 49378, 49379, 49382):
        connection.execute(text('SELECT pg_advisory_xact_lock_shared(:key)'), {'key': lock})


def next_cursor(connection, space_id, kind):
    return connection.execute(text('''INSERT INTO c0_space_cursors(space_id,kind,value)
        VALUES (:space,:kind,1) ON CONFLICT(space_id,kind)
        DO UPDATE SET value=c0_space_cursors.value+1 RETURNING value'''),
        {'space': space_id, 'kind': kind}).scalar_one()


class SpaceBound:
    """A trusted service copy carries selection, never mutable request state."""
    _space_id = None
    _space_children = ()

    def in_space(self, space_id):
        selected = copy(self)
        selected._space_id = space_uuid(space_id)
        for child in self._space_children:
            setattr(selected, child, getattr(self, child).in_space(space_id))
        return selected

    def _space(self, connection):
        return self._space_id if self._space_id is not None else SpaceService.shared_id(connection)

    def _space_authorize(self, connection, actor, role=Role.READER):
        return SpaceService(self.database, self.access).authorize(
            connection, actor, role, space_id=self._space_id)


def require_scope(actor, role):
    scope = {Role.READER: 'c0:read', Role.EDITOR: 'c0:write', Role.ADMIN: 'c0:admin'}[role]
    if actor.delegated_scopes is not None and scope not in actor.delegated_scopes:
        raise ScopeDenied(scope)


class SpaceConflict(Exception):
    pass


def space_uuid(value):
    if not isinstance(value, (str, UUID)):
        raise ValueError('invalid_space')
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        raise ValueError('invalid_space') from None


def _paging(limit, offset):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 100000:
        raise ValueError('invalid_paging')


class SpaceService:
    def __init__(self, database, access):
        self.database, self.access = database, access

    @staticmethod
    def shared_id(connection):
        return connection.execute(text('SELECT knowledge_space_id FROM instance_metadata')).scalar_one()

    def _actor(self, connection, actor, minimum):
        if self.access is None:
            raise PermissionDenied()
        current = self.access.checked_actor(connection, actor)
        current.require(minimum)
        return current

    def authorize(self, connection, actor, minimum=Role.READER, *, space_id=None, check_scopes=True):
        current = self._actor(connection, actor, Role.READER)
        identifier = self.shared_id(connection) if space_id is None else space_uuid(space_id)
        shared = connection.execute(text('SELECT shared FROM c0_spaces WHERE id=:id'),
                                    {'id': identifier}).scalar_one_or_none()
        # Unknown and inaccessible selectors have the same denial. Never
        # reinterpret them as the default shared space or infer from a UUID.
        if shared is None:
            raise PermissionDenied()
        if current.role is Role.ADMIN or shared:
            current.require(minimum)
            if check_scopes:
                require_scope(current, minimum)
            return replace(current, space_id=identifier)
        grant = connection.execute(text('''SELECT role FROM c0_space_grants
            WHERE space_id=:space AND account_id=:account'''),
            {'space': identifier, 'account': current.user_id}).scalar_one_or_none()
        if grant is None:
            raise PermissionDenied()
        effective = min((current.role, Role(grant)), key=_RANK.__getitem__)
        result = replace(current, role=effective, space_id=identifier)
        result.require(minimum)
        if check_scopes:
            require_scope(result, minimum)
        return result

    def list(self, actor, *, limit=100, offset=0):
        _paging(limit, offset)
        with self.database.engine.connect() as c:
            current = self._actor(c, actor, Role.READER)
            require_scope(current, Role.READER)
            rows = c.execute(text('''SELECT s.id,s.name,s.shared,s.revision,s.created_at,
                CASE WHEN :admin THEN 'admin' WHEN s.shared THEN CAST(:role AS text)
                WHEN CAST(:role AS text)='reader' THEN 'reader' ELSE g.role::text END AS role
                FROM c0_spaces s LEFT JOIN c0_space_grants g
                ON g.space_id=s.id AND g.account_id=:account
                WHERE s.shared OR :admin OR g.role IS NOT NULL
                ORDER BY s.shared DESC,s.name,s.id LIMIT :limit OFFSET :offset'''),
                {'admin': current.role is Role.ADMIN, 'role': current.role.value,
                 'account': current.user_id, 'limit': limit, 'offset': offset}).mappings().all()
            return snapshot({'spaces': [dict(row) for row in rows]})

    def get(self, actor, space_id):
        identifier = space_uuid(space_id)
        with self.database.engine.connect() as c:
            current = self.authorize(c, actor, space_id=identifier)
            row = c.execute(text('SELECT id,name,shared,revision,created_at FROM c0_spaces WHERE id=:id'),
                            {'id': identifier}).mappings().one()
            return snapshot({**row, 'role': current.role.value})

    def _mutate(self, actor, operation, payload, key, execute):
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise ValueError('invalid_idempotency_key')
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        fingerprint = hashlib.sha256((operation + '\n' + encoded).encode()).hexdigest()
        try:
            with self.database.engine.begin() as c:
                # Catalogue/grant writes never acquire content mutation locks.
                # Preserve role -> delegation -> space ordering for revocation.
                for lock in (49372, 49379, SPACE_LOCK):
                    c.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
                current = self._actor(c, actor, Role.ADMIN)
                require_scope(current, Role.ADMIN)
                receipt = c.execute(text('''SELECT fingerprint,result FROM c0_space_receipts
                    WHERE actor_id=:actor AND key=:key'''),
                    {'actor': current.user_id, 'key': key}).mappings().one_or_none()
                if receipt:
                    if receipt['fingerprint'] != fingerprint:
                        raise SpaceConflict()
                    return receipt['result']
                result = snapshot(execute(c, current))
                c.execute(text('''INSERT INTO c0_space_receipts(actor_id,key,fingerprint,result)
                    VALUES (:actor,:key,:fingerprint,CAST(:result AS jsonb))'''),
                    {'actor': current.user_id, 'key': key, 'fingerprint': fingerprint,
                     'result': json.dumps(result, ensure_ascii=False)})
                return result
        except IntegrityError:
            raise SpaceConflict() from None

    def create(self, actor, name, *, idempotency_key):
        if not isinstance(name, str) or not name.strip() or len(name) > 128 or not name.isprintable():
            raise ValueError('invalid_space_name')
        try:
            name.encode('utf-8')
        except UnicodeError:
            raise ValueError('invalid_space_name') from None
        name = name.strip()
        def execute(c, current):
            if c.execute(text('SELECT count(*) FROM c0_spaces')).scalar_one() >= 1000:
                raise SpaceConflict()
            row = c.execute(text('''INSERT INTO c0_spaces(id,name,created_by)
                VALUES (:id,:name,:actor) RETURNING id,name,shared,revision,created_at'''),
                {'id': uuid4(), 'name': name, 'actor': current.user_id}).mappings().one()
            return {**row, 'role': 'admin'}
        return self._mutate(actor, 'space.create', {'name': name}, idempotency_key, execute)

    def list_grants(self, actor, space_id, *, limit=100, offset=0):
        _paging(limit, offset)
        identifier = space_uuid(space_id)
        with self.database.engine.connect() as c:
            self._actor(c, actor, Role.ADMIN)
            self.authorize(c, actor, Role.ADMIN, space_id=identifier)
            rows = c.execute(text('''SELECT * FROM c0_space_grants WHERE space_id=:space
                ORDER BY account_id LIMIT :limit OFFSET :offset'''),
                {'space': identifier, 'limit': limit, 'offset': offset}).mappings().all()
            return snapshot({'grants': [dict(row) for row in rows]})

    def set_grant(self, actor, space_id, account_id, role, *, expected_revision, idempotency_key):
        identifier, account = space_uuid(space_id), space_uuid(account_id)
        if role not in (None, Role.READER, Role.EDITOR) or (role is not None and not isinstance(role, Role)):
            raise ValueError('invalid_space_role')
        if type(expected_revision) is not int or not 0 <= expected_revision < 2147483646:
            raise ValueError('invalid_revision')
        value = role.value if role is not None else None
        def execute(c, current):
            self.authorize(c, current, Role.ADMIN, space_id=identifier)
            if identifier == self.shared_id(c):
                raise ValueError('shared_space_policy_immutable')
            target = c.execute(text('SELECT id FROM c0_accounts WHERE id=:id AND issuer=:issuer'),
                {'id': account, 'issuer': self.access.issuer}).scalar_one_or_none()
            if target is None:
                raise ValueError('account_not_found')
            if role is not None:
                target_actor = self.access._actor(c, account)
                if _RANK[role] > _RANK[target_actor.role]:
                    raise ValueError('space_role_exceeds_application_role')
            old = c.execute(text('''SELECT * FROM c0_space_grants
                WHERE space_id=:space AND account_id=:account FOR UPDATE'''),
                {'space': identifier, 'account': account}).mappings().one_or_none()
            if (old['revision'] if old else 0) != expected_revision:
                raise SpaceConflict()
            if old and old['role'] == value:
                return dict(old)
            if old is None:
                row = c.execute(text('''INSERT INTO c0_space_grants(space_id,account_id,role,revision)
                    VALUES (:space,:account,:role,1) RETURNING *'''),
                    {'space': identifier, 'account': account, 'role': value}).mappings().one()
            else:
                row = c.execute(text('''UPDATE c0_space_grants SET role=:role,
                    revision=revision+1,updated_at=now() WHERE space_id=:space
                    AND account_id=:account RETURNING *'''),
                    {'space': identifier, 'account': account, 'role': value}).mappings().one()
            # Persist the tombstone/revision and invalidate old opaque authority
            # in the same transaction. Regrant cannot revive any old token.
            c.execute(text('DELETE FROM c0_oauth_grants WHERE account_id=:id'), {'id': account})
            return dict(row)
        return self._mutate(actor, 'space.grant', {'space_id': str(identifier),
            'account_id': str(account), 'role': value, 'expected_revision': expected_revision},
            idempotency_key, execute)
