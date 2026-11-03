# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit producer-only extraction runner; not installed into the NS8 timer."""
import json
import os
import sys
from uuid import UUID

from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.sources import OriginalStore


def main():
    database = None
    try:
        flag = os.getenv('CZERO_EXTRACTION_UNITS', '0')
        if flag not in ('0', '1'):
            raise ValueError('invalid_extraction_flag')
        processed = 0
        if flag == '1':
            from czero_core.extraction_queue import ExtractionQueue, ExtractionWorker
            issuer = os.environ['CZERO_OIDC_ISSUER']
            owner = UUID(os.environ['CZERO_OWNER_LDAP_UUID'])
            database = Database()
            access = AccessService(database, issuer, owner)
            originals = OriginalStore(os.getenv('CZERO_SOURCE_DIR', '/var/lib/czero/sources'))
            processed = ExtractionWorker(ExtractionQueue(database,access,originals,enabled=True)).tick()
        print(json.dumps({'processed':processed}))
        return 0
    except Exception:
        print('C0 extraction worker failed', file=sys.stderr)
        return 1
    finally:
        if database is not None:
            database.close()


if __name__ == '__main__':
    sys.exit(main())
