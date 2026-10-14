# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted extension point shared by the application API and worker."""
from czero_core.jobs import default_registry
import os
from czero_core.sources import OriginalStore, register_source_handlers
from czero_core.embeddings import EmbeddingStore, register_embedding_handlers
from czero_core.retrieval_config import load_settings
from sqlalchemy.exc import SQLAlchemyError
import logging


def build_registry(database=None, originals=None, *, settings=None, transport=None):
    # Forks register synchronous deterministic handlers here in trusted code.
    registry = default_registry()
    originals = originals or OriginalStore(os.getenv('CZERO_SOURCE_DIR', '/var/lib/czero/sources'))
    register_source_handlers(registry, database, originals)
    # Disabled providers still have a safe handler if an Admin enables their
    # dormant schedule; unknown handlers must not stop the whole worker.
    settings=settings or load_settings()
    embedding,_=settings.clients(transport=transport)
    store=EmbeddingStore(database,embedding)
    if database is not None and hasattr(database,'engine'):
        try:
            with database.engine.begin() as connection:store._activate(connection)
        except (ValueError,SQLAlchemyError):
            # Optional indexing cannot prevent the provider-free app starting.
            # Worker errors/status expose incomplete configured indexing.
            logging.getLogger(__name__).warning('Optional embedding profile activation unavailable')
    register_embedding_handlers(registry,store)
    return registry
