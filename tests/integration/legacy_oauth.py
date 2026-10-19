# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Seed immutable predecessor columns without invoking newer-schema services."""
from datetime import datetime, timezone
import hashlib
import json
import secrets
import time
from uuid import uuid4

from sqlalchemy import text
from czero_core.oauth_grants import TokenPair


def legacy_pair(database, actor, issuer, native_client, client, resource, scopes):
    identifier, current = uuid4(), time.time()
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with database.engine.begin() as c:
        c.execute(text('''INSERT INTO c0_oauth_grants
            (id,account_id,client_id,client_revision,issuer,native_client,resource,scopes,expires_at)
            VALUES (:id,:account,:client,:revision,:issuer,:native,:resource,CAST(:scopes AS jsonb),:expires)'''),
            {'id': identifier, 'account': actor.user_id, 'client': client['client_id'], 'revision': client['revision'],
             'issuer': issuer, 'native': native_client, 'resource': resource,
             'scopes': json.dumps(sorted(scopes)), 'expires': datetime.fromtimestamp(current+600,timezone.utc)})
        for value,kind,seconds in ((access,'access',300),(refresh,'refresh',600)):
            c.execute(text('''INSERT INTO c0_oauth_tokens(hash,grant_id,kind,expires_at)
                VALUES (:hash,:grant,:kind,:expires)'''),
                {'hash':hashlib.sha256(value.encode()).hexdigest(),'grant':identifier,'kind':kind,
                 'expires':datetime.fromtimestamp(current+seconds,timezone.utc)})
    return TokenPair(access,refresh,frozenset(scopes),300)
