# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared actor-scoped receipts for bounded, transactional domain mutations."""
from datetime import datetime
import hashlib
import json
import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .identity import Role

MUTATION_LOCK = 49376
_KEY = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')


def json_value(value):
    if isinstance(value, UUID): return str(value)
    if isinstance(value, datetime): return value.isoformat()
    raise TypeError('invalid_result')


def snapshot(value):
    """Reads and retries share the original JSON-compatible result shape."""
    return json.loads(json.dumps(value, default=json_value, ensure_ascii=False, allow_nan=False))


def mutate(database, authorize, actor, operation, payload, key, execute, *, conflict):
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError('invalid_idempotency_key')
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    fingerprint = hashlib.sha256((operation + '\n' + encoded).encode()).hexdigest()
    try:
        with database.engine.begin() as connection:
            authorize(connection, actor, Role.EDITOR)
            # Preserve Wiki's existing cursor/receipt serialization and lock order.
            connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': MUTATION_LOCK})
            # A caller can lose membership while waiting for an earlier writer.
            current = authorize(connection, actor, Role.EDITOR)
            receipt = connection.execute(text('SELECT fingerprint,result FROM c0_knowledge_receipts WHERE actor_id=:actor AND key=:key'),
                {'actor': current.user_id, 'key': key}).mappings().one_or_none()
            if receipt:
                if receipt['fingerprint'] != fingerprint: raise conflict()
                return receipt['result']
            result = snapshot(execute(connection, current))
            connection.execute(text('''INSERT INTO c0_knowledge_receipts(actor_id,key,fingerprint,result)
                VALUES (:actor,:key,:fingerprint,CAST(:result AS jsonb))'''),
                {'actor': current.user_id, 'key': key, 'fingerprint': fingerprint, 'result': json.dumps(result, ensure_ascii=False)})
            return result
    except IntegrityError:
        raise conflict() from None
