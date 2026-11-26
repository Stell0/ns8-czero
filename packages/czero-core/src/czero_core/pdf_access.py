# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Private, exact-original PDF authorization and short-lived approval challenges."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import os
import stat
import time

from joserfc import jwe
from joserfc.jwk import OctKey
from sqlalchemy import text

from .extraction import ExtractionError, MAX_PDF_BYTES


@dataclass(frozen=True)
class PdfAuthorization:
    digest: str
    actor_id: object
    restricted: bool
    password: str | None = field(repr=False)


class PdfApprovalRequired(ExtractionError):
    def __init__(self, token):
        super().__init__('pdf_extraction_approval_required')
        self.token = token


class PdfAccess:
    def __init__(self, key):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError('invalid_pdf_unlock_key')
        self._challenge_key = hmac.digest(key, b'c0-pdf-approval-v1', 'sha256')
        self._password_key = OctKey.import_key(hmac.digest(key, b'c0-pdf-password-v1', 'sha256'))

    @classmethod
    def configured(cls):
        path = os.getenv('CZERO_PDF_UNLOCK_KEY_FILE')
        if not path:
            return None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                        or info.st_uid != os.geteuid() or info.st_size != 32):
                    raise ValueError('invalid_pdf_unlock_key')
                return cls(stream.read(33))
        except (OSError, ValueError):
            return None

    def challenge(self, binding, expires):
        payload = '\0'.join(map(str, [*binding, expires])).encode()
        return f'{expires}.{hmac.digest(self._challenge_key, payload, "sha256").hex()}'

    def approved(self, binding, token):
        now = int(time.time())
        if isinstance(token, str) and len(token) <= 80 and token.isascii():
            expires, _, signature = token.partition('.')
            if expires.isdecimal() and len(signature) == 64 and now <= int(expires) <= now + 900:
                return hmac.compare_digest(token, self.challenge(binding, int(expires)))
        return False

    def check(self, stream, *, actor_id, space_id, target, revision, password=None, token=None):
        from .protected_pdf import inspect_pdf

        if password is not None and (not isinstance(password, str) or len(password.encode()) > 1024
                                     or '\0' in password):
            raise ValueError('invalid_pdf_password')
        status = inspect_pdf(stream, password)
        if not status.encrypted:
            if password is not None or token is not None:
                raise ValueError('unexpected_pdf_authorization')
            return None
        digest = original_digest(stream)
        binding = (actor_id, space_id, target, revision, digest)
        approved = self.approved(binding, token)
        if (status.restricted and not approved) or (token is not None and not approved):
            raise PdfApprovalRequired(self.challenge(binding, int(time.time()) + 900))
        return PdfAuthorization(digest, actor_id, status.restricted, password if status.password_required else None)

    @staticmethod
    def _binding(row):
        return '|'.join(str(row[key]) for key in ('id', 'space_id', 'source_id', 'content_hash')).encode()

    def save(self, connection, row, authorization):
        if row['content_hash'] != authorization.digest:
            raise ExtractionError('invalid_file')
        sealed = None
        if authorization.password is not None:
            sealed = jwe.encrypt_compact({'alg': 'dir', 'enc': 'A256GCM'},
                self._binding(row) + b'\0' + authorization.password.encode(),
                self._password_key, algorithms=['dir', 'A256GCM'])
        connection.execute(text('''INSERT INTO c0_pdf_authorizations
            (version_id,space_id,approved_by,restricted,sealed_password)
            VALUES (:id,:space,:actor,:restricted,:secret)
            ON CONFLICT(version_id) DO UPDATE SET approved_by=EXCLUDED.approved_by,
              restricted=EXCLUDED.restricted,sealed_password=EXCLUDED.sealed_password,approved_at=now()'''),
            {'id': row['id'], 'space': row['space_id'], 'actor': authorization.actor_id,
             'restricted': authorization.restricted, 'secret': sealed})

    @staticmethod
    def get(connection, row):
        return connection.execute(text('''SELECT approved_by,restricted,sealed_password
            FROM c0_pdf_authorizations WHERE version_id=:id AND space_id=:space'''),
            {'id': row['id'], 'space': row['space_id']}).mappings().one_or_none()

    def authorization(self, row, saved):
        password = None
        if saved['sealed_password'] is not None:
            try:
                payload = jwe.decrypt_compact(saved['sealed_password'], self._password_key,
                    algorithms=['dir', 'A256GCM']).plaintext
                binding, marker, raw = payload.partition(b'\0')
                if not marker or not hmac.compare_digest(binding, self._binding(row)):
                    raise ValueError('pdf_authorization_mismatch')
                password = raw.decode()
            except Exception:
                raise ExtractionError('pdf_unlock_unavailable') from None
        return PdfAuthorization(row['content_hash'], saved['approved_by'], saved['restricted'], password)


def original_digest(stream):
    size = 0
    digest = hashlib.sha256()
    stream.seek(0)
    try:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(block)
            if size > MAX_PDF_BYTES:
                raise ExtractionError('too_large')
            digest.update(block)
        return digest.hexdigest()
    finally:
        stream.seek(0)


@contextmanager
def pdf_input(path, row, saved, access):
    if saved is None:
        yield path
        return
    if access is None:
        raise ExtractionError('pdf_unlock_unavailable')
    from .protected_pdf import working_pdf
    authorization = access.authorization(row, saved)
    with working_pdf(path, authorization.password, restricted_approved=authorization.restricted) as working:
        yield working
