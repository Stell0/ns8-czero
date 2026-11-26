# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import os
import logging
import time
import sys
import stat
from uuid import UUID
from czero_core.worker import main
from czero_app.job_handlers import build_registry


def github_token():
    """Optional operator credential: never a source setting or a Redis value."""
    path=os.getenv('CZERO_GITHUB_TOKEN_FILE')
    if not path:return None
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(descriptor,'rb') as secret:
        info=os.fstat(secret.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077 or info.st_uid!=os.geteuid() or info.st_size>4096:
            raise ValueError('invalid_github_credential_file')
        return secret.read(4097).decode('ascii').strip()


def update_sources():
    if importlib.util.find_spec('czero_core.automatic_sources') is None:return
    from czero_core.database import Database
    from czero_core.access import AccessService
    from czero_core.automatic_sources import AutomaticSourceService
    from czero_core.sources import SourceService,OriginalStore
    from czero_core.source_updates import SourceUpdater
    from czero_core.source_collectors import collect
    from czero_core.worker import deadline,JobTimedOut
    issuer=os.getenv('CZERO_OIDC_ISSUER');owner=os.getenv('CZERO_OWNER_LDAP_UUID')
    if not issuer or not owner:return
    database=None
    try:
        database=Database()
        access=AccessService(database,issuer,UUID(owner))
        originals=OriginalStore(os.getenv('CZERO_SOURCE_DIR','/var/lib/czero/sources'))
        sources=SourceService(database,access,build_registry(database,originals,access=access),originals)
        def registered(kind,config,cursor,**options):
            return collect(kind,config,cursor,github_token=github_token() if kind=='github' else None,**options)
        service = AutomaticSourceService(database, access)
        options = {}
        from czero_core.extraction_queue import ExtractionQueue
        if hasattr(ExtractionQueue, 'enqueue_automatic_attachment') and os.getenv('CZERO_EXTRACTION_UNITS') == '1':
            from czero_app.extraction_worker import configured_queue
            options['extraction_queue'] = lambda: configured_queue(database, access, originals)
        if hasattr(service, 'drive_status'):
            from czero_app.google_drive import GoogleDrive
            try:
                origin = os.getenv('CZERO_AUTH_PUBLIC_ORIGIN', '').rstrip('/')
                callback = origin + os.getenv('CZERO_BASE_PATH', '') + '/auth/google-drive/callback'
                provider = GoogleDrive.configured(callback) if origin else None
            except (ValueError, OSError):
                provider = None
                logging.getLogger('czero.worker').warning('Invalid Google Drive configuration')
            if provider:
                options.update(drive_collector=provider.collect, drive_recheck=provider.recheck)
        # Two 25-second parsers, 40 seconds of Google I/O and a 9-second
        # permission recheck fit before the 120-second lease expires.
        with deadline(110 if options else 25):
            SourceUpdater(service, sources, collector=registered, **options).tick()
    except JobTimedOut:
        # A claimed lease expires; the next invocation reconciles publication.
        pass
    except Exception:
        logging.getLogger('czero.worker').warning('C0 source update unavailable')
    finally:
        if database is not None:database.close()


if __name__ == '__main__':
    if importlib.util.find_spec('czero_core.automatic_sources') is not None:
        started = time.monotonic()
        update_sources()
        # Reserve one 30-second handler and shutdown time inside TimeoutStartSec=150.
        remaining = max(1, min(60, 110 - int(time.monotonic() - started)))
        sys.exit(main(build_registry(), budget_seconds=remaining))
    sys.exit(main(build_registry()))
