# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded extraction pool runner invoked by the native NS8 timer."""
import json
import os
import sys
import signal
from threading import Event
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
            from czero_core.extraction_queue import ExtractionQueue, ExtractionPool
            issuer = os.environ['CZERO_OIDC_ISSUER']
            owner = UUID(os.environ['CZERO_OWNER_LDAP_UUID'])
            database = Database()
            access = AccessService(database, issuer, owner)
            originals = OriginalStore(os.getenv('CZERO_SOURCE_DIR', '/var/lib/czero/sources'))
            workers=int(os.getenv('CZERO_EXTRACTION_WORKERS','2'))
            ocr=os.getenv('CZERO_EXTRACTION_OCR_ENABLED','0')
            if ocr not in ('0','1'): raise ValueError('invalid_extraction_flag')
            cache=os.getenv('CZERO_EXTRACTION_CACHE_ENABLED','1')
            if cache not in ('0','1'): raise ValueError('invalid_cache_flag')
            queue=ExtractionQueue(database,access,originals,enabled=True,instance_workers=workers,
                document_workers=int(os.getenv('CZERO_EXTRACTION_DOCUMENT_WORKERS','2')),
                space_workers=int(os.getenv('CZERO_EXTRACTION_SPACE_WORKERS','2')),
                max_queued_units=int(os.getenv('CZERO_EXTRACTION_MAX_QUEUED_UNITS','2000')),
                max_staging_bytes=int(os.getenv('CZERO_EXTRACTION_MAX_STAGING_BYTES','33554432')),
                ocr_language=os.getenv('CZERO_EXTRACTION_OCR_LANGUAGE','eng') if ocr=='1' else None,cache_enabled=cache=='1')
            stop=Event()
            previous=signal.signal(signal.SIGTERM,lambda *_:stop.set())
            try: result=ExtractionPool(queue,workers=workers).tick(stop=stop)
            finally: signal.signal(signal.SIGTERM,previous)
        else: result={'processed':processed,'workers':0}
        print(json.dumps(result))
        return 0
    except Exception:
        print('C0 extraction worker failed', file=sys.stderr)
        return 1
    finally:
        if database is not None:
            database.close()


if __name__ == '__main__':
    sys.exit(main())
