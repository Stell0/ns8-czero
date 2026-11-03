# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit native-operator recovery; never a public HTTP/MCP handoff."""
import argparse
import json
import os
import sys
from uuid import UUID

from sqlalchemy import text

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.sources import OriginalStore


def main():
    parser=argparse.ArgumentParser(description='Retry failed extraction units within their staging lifetime')
    parser.add_argument('--run',required=True,type=UUID)
    parser.add_argument('--space',required=True,type=UUID)
    parser.add_argument('--expected-revision',required=True,type=int)
    parser.add_argument('--idempotency-key',required=True)
    args=parser.parse_args()
    database=None
    try:
        if os.getenv('CZERO_EXTRACTION_UNITS','0')!='1': raise ValueError('extraction_units_disabled')
        from czero_core.extraction_queue import ExtractionQueue
        issuer=os.environ['CZERO_OIDC_ISSUER']; owner=UUID(os.environ['CZERO_OWNER_LDAP_UUID'])
        database=Database()
        access=AccessService(database,issuer,owner)
        with database.engine.connect() as c:
            identifier=c.execute(text('SELECT id FROM c0_accounts WHERE issuer=:issuer AND account_key=:key'),
                {'issuer':issuer,'key':owner}).scalar_one_or_none()
        if identifier is None: raise PermissionDenied()
        queue=ExtractionQueue(database,access,OriginalStore(os.getenv('CZERO_SOURCE_DIR','/var/lib/czero/sources')),enabled=True).in_space(args.space)
        result=queue.retry_failed(Actor(identifier,Role.READER),args.run,
            expected_revision=args.expected_revision,idempotency_key=args.idempotency_key)
        print(json.dumps(result)); return 0
    except Exception:
        print('C0 extraction retry failed',file=sys.stderr); return 1
    finally:
        if database is not None: database.close()


if __name__=='__main__': sys.exit(main())
