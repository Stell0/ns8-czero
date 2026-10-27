# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private renewable authority; providers never select roles or extend deadlines."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hmac
import hashlib
import json
import math
import time
from uuid import uuid4

from joserfc import jwe
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from sqlalchemy import text

from .identity import PermissionDenied, Role, VerifiedIdentity
from .sessions import REMEMBER_SECONDS


class RenewalRejected(ValueError):
    def __init__(self):
        super().__init__('invalid_session')


class RenewalUnavailable(ValueError):
    def __init__(self):
        super().__init__('authentication_unavailable')


@dataclass(frozen=True)
class SessionPolicy:
    absolute_seconds: int = 28800
    idle_seconds: int = 3600

    def __post_init__(self):
        if (type(self.absolute_seconds) is not int or type(self.idle_seconds) is not int
                or not 60 <= self.idle_seconds <= self.absolute_seconds <= 86400):
            raise ValueError('invalid_session_policy')


@dataclass(frozen=True)
class ConnectionPolicy:
    idle_seconds: int = 30 * 86400

    def __post_init__(self):
        if type(self.idle_seconds) is not int or not 60 <= self.idle_seconds <= 31536000:
            raise ValueError('invalid_connection_policy')


@dataclass(frozen=True)
class RenewalResult:
    identity: VerifiedIdentity
    credential: str = field(repr=False)
    offline: bool = False

    def __post_init__(self):
        if (not isinstance(self.identity, VerifiedIdentity)
                or type(self.offline) is not bool
                or not isinstance(self.credential, str) or not 1 <= len(self.credential.encode()) <= 32768):
            raise RenewalRejected()


def _date(value):
    return datetime.fromtimestamp(value, timezone.utc)


class NativeAuthorityService:
    """Trusted check callback must contact the provider, even before token expiry.

    It returns newly verified same-account identity and current credential after
    active-session checking/rotation. Rejection is permanent; unavailability is
    retryable but confers no authority. Network calls must be bounded by the
    configured provider adapter. Session locks serialize checks across processes.
    No grant lock is acquired here; grant callers authenticate before taking
    their grant lock, and captured-operation checks use only persisted proof.
    """
    def __init__(self, access, client_id, secret, check, *, policy=None, connection_policy=None, now=time.time):
        if (not isinstance(client_id, str) or not 1 <= len(client_id) <= 128
                or not isinstance(secret, str) or len(secret.encode()) < 32 or not callable(check)):
            raise ValueError('invalid_renewal_configuration')
        self.access, self.client_id, self.check = access, client_id, check
        self.policy = policy if policy is not None else SessionPolicy()
        if not isinstance(self.policy, SessionPolicy):
            raise ValueError('invalid_session_policy')
        if connection_policy is not None and not isinstance(connection_policy, ConnectionPolicy):
            raise ValueError('invalid_connection_policy')
        self.connection_policy = connection_policy
        self._now = now
        # Domain-separated key; native-secret/client replacement invalidates old
        # ciphertext without storing a decryption key in the database/backup.
        context = json.dumps(['c0-native-authority-v1', access.issuer, client_id]).encode()
        self._key = OctKey.import_key(hmac.digest(secret.encode(), context, 'sha256'))
        self._refresh_key = hmac.digest(secret.encode(), b'c0-persistent-refresh-v1\0' + context, 'sha256')

    def _seal(self, row, credential):
        payload = json.dumps({'binding': self._binding(row), 'credential': credential}, separators=(',', ':'))
        sealed = jwe.encrypt_compact({'alg': 'dir', 'enc': 'A256GCM'}, payload, self._key,
                                     algorithms=['dir', 'A256GCM'])
        if len(sealed) > 65536:
            raise RenewalRejected()
        return sealed

    @staticmethod
    def _binding(row):
        value = [str(row['id']), str(row['account_id']), row['issuer'], row['native_client'], row['subject']]
        return value + [row['authority_kind']] if row.get('authority_kind') in ('background','remembered') else value

    def _open(self, row):
        try:
            payload = json.loads(jwe.decrypt_compact(row['credential'], self._key,
                algorithms=['dir', 'A256GCM']).plaintext)
            if payload['binding'] != self._binding(row):
                raise RenewalRejected()
            value = payload['credential']
            if not isinstance(value, str) or not 1 <= len(value.encode()) <= 32768:
                raise RenewalRejected()
            return value
        except (JoseError, ValueError, KeyError, TypeError, UnicodeError):
            raise RenewalRejected() from None

    def create(self, connection, actor, result, *, background=False, remembered=False):
        if not isinstance(result, RenewalResult):
            raise RenewalRejected()
        if (type(background) is not bool or type(remembered) is not bool
                or background and self.connection_policy is None or (background or remembered) and not result.offline):
            raise RenewalRejected()
        current = self._now()
        identity = result.identity
        account = connection.execute(text('SELECT account_key FROM c0_accounts WHERE id=:id AND issuer=:issuer'),
            {'id': actor.user_id, 'issuer': self.access.issuer}).scalar_one_or_none()
        if (identity.issuer != self.access.issuer or str(account) != identity.account_key
                or not math.isfinite(identity.expires_at) or identity.expires_at <= current):
            raise RenewalRejected()
        self.access._actor(connection, actor.user_id).require(Role.READER)
        # Admission and creation linearize with role revocation. Expired or
        # revoked renewable rows cannot consume the bounded authority budget.
        connection.execute(text('SELECT pg_advisory_xact_lock_shared(49372)'))
        self.access._actor(connection, actor.user_id).require(Role.READER)
        connection.execute(text('SELECT pg_advisory_xact_lock(49374)'))
        connection.execute(text('''UPDATE c0_native_authority n SET revoked=true,credential=NULL,checking=false
            WHERE authority_kind IN ('background','remembered') AND issuer=:issuer AND native_client=:client
            AND NOT EXISTS(SELECT 1 FROM c0_sessions s WHERE s.native_authority_id=n.id AND s.expires_at>:now)
            AND NOT EXISTS(SELECT 1 FROM c0_oauth_grants g WHERE g.native_authority_id=n.id
                AND g.persistent AND g.idle_until>:now)'''),
            {'issuer':self.access.issuer,'client':self.client_id,'now':_date(current)})
        for table in ('c0_sessions', 'c0_oauth_grants'):
            connection.execute(text(f"""DELETE FROM {table} s USING c0_native_authority n
                WHERE s.native_authority_id=n.id
                AND (n.expires_at<=:now OR n.idle_until<=:now OR n.revoked)"""),
                {'now': _date(current)})
        connection.execute(text("""DELETE FROM c0_native_authority n
            WHERE (n.expires_at<=:now OR n.idle_until<=:now OR n.revoked)
            AND NOT EXISTS (SELECT 1 FROM c0_sessions s WHERE s.native_authority_id=n.id)
            AND NOT EXISTS (SELECT 1 FROM c0_oauth_grants g WHERE g.native_authority_id=n.id)"""),
            {'now': _date(current)})
        total = connection.execute(text('SELECT count(*) FROM c0_native_authority')).scalar_one()
        owned = connection.execute(text('''SELECT count(*) FROM c0_native_authority
            WHERE account_id=:id AND issuer=:issuer AND native_client=:client'''),
            {'id': actor.user_id, 'issuer': self.access.issuer, 'client': self.client_id}).scalar_one()
        if total >= 1000 or owned >= 32:
            raise RenewalRejected()
        row = {'id': uuid4(), 'account_id': actor.user_id, 'issuer': identity.issuer,
               'native_client': self.client_id, 'subject': identity.subject,
               'authority_kind': 'background' if background else ('remembered' if remembered else 'session')}
        absolute = None if background or remembered else current + self.policy.absolute_seconds
        connection_seconds = self.connection_policy.idle_seconds if background else None
        idle_seconds = max(connection_seconds or 0, REMEMBER_SECONDS) if remembered else (connection_seconds or self.policy.idle_seconds)
        connection.execute(text('''INSERT INTO c0_native_authority
            (id,account_id,issuer,native_client,subject,credential,verified_until,expires_at,idle_until,idle_seconds,authority_kind,connection_idle_seconds)
            VALUES (:id,:account_id,:issuer,:native_client,:subject,:credential,:verified,:expires,:idle,:seconds,:kind,:connection_seconds)'''),
            {**row, 'credential': self._seal(row, result.credential), 'verified': _date(identity.expires_at),
             'expires': _date(absolute) if absolute is not None else None,
             'idle': _date(current + idle_seconds if absolute is None else min(absolute, current + idle_seconds)),
             'seconds': idle_seconds, 'kind': row['authority_kind'], 'connection_seconds': connection_seconds})
        return row['id'], _date(absolute) if absolute is not None else None

    def peek(self, connection, identifier, *, account_id=None):
        row = connection.execute(text('''SELECT * FROM c0_native_authority WHERE id=:id
            AND issuer=:issuer AND native_client=:client AND NOT revoked
            AND (expires_at>:now OR (authority_kind IN ('background','remembered') AND expires_at IS NULL))
            AND idle_until>:now AND verified_until>:now'''),
            {'id': identifier, 'issuer': self.access.issuer, 'client': self.client_id,
             'now': _date(self._now())}).mappings().one_or_none()
        if row is None or (account_id is not None and row['account_id'] != account_id):
            raise RenewalRejected()
        if row['authority_kind'] == 'background' and self.connection_policy is None:
            raise RenewalRejected()
        self.access._actor(connection, row['account_id']).require(Role.READER)
        return row

    @staticmethod
    def _invalidate(connection, identifier):
        connection.execute(text("""UPDATE c0_native_authority
            SET revoked=true,credential=NULL,checking=false WHERE id=:id"""), {'id': identifier})

    def _row(self, connection, identifier):
        return connection.execute(text("""SELECT * FROM c0_native_authority
            WHERE id=:id AND issuer=:issuer AND native_client=:client FOR UPDATE"""),
            {'id': identifier, 'issuer': self.access.issuer, 'client': self.client_id}).mappings().one_or_none()

    def authenticate(self, identifier):
        # A session advisory lock spans the durable marker, bounded provider
        # call and credential commit. A process crash leaves checking=true;
        # the next caller must invalidate, never replay a possibly rotated key.
        key = int.from_bytes(hashlib.sha256(str(identifier).encode()).digest()[:4], 'big') & 0x7fffffff
        with self.access.database.engine.connect() as connection:
            try:
                connection.execute(text('SELECT pg_advisory_lock(49383,:key)'), {'key': key})
                connection.commit()
                return self._authenticate_locked(connection, identifier)
            finally:
                try:
                    connection.rollback()
                    # Acquisition can succeed before a cancelled statement
                    # reports failure. Always unlock, even if execute raised.
                    connection.execute(text('SELECT pg_advisory_unlock(49383,:key)'), {'key': key})
                    connection.commit()
                except BaseException:
                    # Never return a possibly session-locked connection.
                    connection.invalidate()
                    raise

    def _authenticate_locked(self, connection, identifier):
        rejected = False
        with connection.begin():
            row = self._row(connection, identifier)
            if row is None:
                raise RenewalRejected()
            current = self._now()
            try:
                if (row['revoked'] or row['checking'] or row['idle_until'] <= _date(current)
                        or row['expires_at'] is not None and row['expires_at'] <= _date(current)
                        or row['authority_kind'] == 'background' and self.connection_policy is None):
                    raise RenewalRejected()
                self.access._actor(connection, row['account_id']).require(Role.READER)
                credential = self._open(row)
                connection.execute(text('UPDATE c0_native_authority SET checking=true WHERE id=:id'), {'id': identifier})
            except (RenewalRejected, PermissionDenied):
                self._invalidate(connection, identifier)
                rejected = True
        if rejected:
            raise RenewalRejected()
        try:
            proof = self.check(credential)
            if not isinstance(proof, RenewalResult):
                raise RenewalRejected()
        except RenewalUnavailable:
            # Only a definite retryable outcome may clear the durable marker.
            # No identity, expiry, idle time or credential is extended.
            with connection.begin():
                connection.execute(text('''UPDATE c0_native_authority SET checking=false,
                    verified_until=LEAST(verified_until,:now) WHERE id=:id'''),
                    {'id': identifier, 'now': _date(self._now())})
            raise
        except RenewalRejected:
            with connection.begin():
                self._invalidate(connection, identifier)
            raise
        # Unexpected interruption leaves the committed marker in place.
        with connection.begin():
            row = self._row(connection, identifier)
            current = self._now()
            identity = proof.identity
            try:
                if (row is None or row['revoked'] or not row['checking']
                        or row['idle_until'] <= _date(current)
                        or row['expires_at'] is not None and row['expires_at'] <= _date(current)):
                    raise RenewalRejected()
                account = connection.execute(text('SELECT account_key FROM c0_accounts WHERE id=:id'),
                    {'id': row['account_id']}).scalar_one()
                if (identity.issuer != row['issuer'] or identity.subject != row['subject']
                        or identity.account_key != str(account) or not math.isfinite(identity.expires_at)
                        or identity.expires_at <= current):
                    raise RenewalRejected()
                if row['authority_kind'] in ('background','remembered') and not proof.offline:
                    raise RenewalRejected()
                self.access._actor(connection, row['account_id']).require(Role.READER)
                connection.execute(text("""UPDATE c0_native_authority SET credential=:credential,
                    verified_until=:verified,idle_until=LEAST(expires_at,:idle),checking=false WHERE id=:id"""),
                    {'id': identifier, 'credential': self._seal(row, proof.credential),
                     'verified': _date(min(identity.expires_at, row['expires_at'].timestamp()) if row['expires_at'] is not None else identity.expires_at),
                     'idle': _date(current + row['idle_seconds'])})
                result = self.peek(connection, identifier)
            except (RenewalRejected, PermissionDenied):
                self._invalidate(connection, identifier)
                rejected = True
        if rejected:
            raise RenewalRejected()
        return result

    def revoke(self, identifier):
        with self.access.database.engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(49382)'))
            connection.execute(text("""UPDATE c0_native_authority SET revoked=true,credential=NULL,checking=false
                WHERE id=:id AND issuer=:issuer AND native_client=:client"""),
                {'id': identifier, 'issuer': self.access.issuer, 'client': self.client_id})
