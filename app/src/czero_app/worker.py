# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import os
import logging
import sys
from uuid import UUID
from czero_core.worker import main
from czero_app.job_handlers import build_registry


def update_sources():
    if importlib.util.find_spec('czero_core.automatic_sources') is None:return
    from czero_core.database import Database
    from czero_core.access import AccessService
    from czero_core.automatic_sources import AutomaticSourceService
    from czero_core.sources import SourceService,OriginalStore
    from czero_core.source_updates import SourceUpdater
    from czero_core.worker import deadline,JobTimedOut
    issuer=os.getenv('CZERO_OIDC_ISSUER');owner=os.getenv('CZERO_OWNER_LDAP_UUID')
    if not issuer or not owner:return
    database=None
    try:
        database=Database()
        access=AccessService(database,issuer,UUID(owner))
        originals=OriginalStore(os.getenv('CZERO_SOURCE_DIR','/var/lib/czero/sources'))
        sources=SourceService(database,access,build_registry(database,originals),originals)
        with deadline(25):
            SourceUpdater(AutomaticSourceService(database,access),sources).tick()
    except JobTimedOut:
        # A claimed lease expires; the next invocation reconciles publication.
        pass
    except Exception:
        logging.getLogger('czero.worker').warning('C0 source update unavailable')
    finally:
        if database is not None:database.close()


if __name__ == '__main__':
    if importlib.util.find_spec('czero_core.automatic_sources') is not None:
        update_sources()
        # Leave room for collection and the final job under the native lifetime guard.
        sys.exit(main(build_registry(), budget_seconds=60))
    sys.exit(main(build_registry()))
