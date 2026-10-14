# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted extension point shared by the application API and worker."""
from czero_core.jobs import default_registry
import os
from czero_core.sources import OriginalStore, register_source_handlers


def build_registry(database=None, originals=None):
    # Forks register synchronous deterministic handlers here in trusted code.
    registry = default_registry()
    originals = originals or OriginalStore(os.getenv('CZERO_SOURCE_DIR', '/var/lib/czero/sources'))
    register_source_handlers(registry, database, originals)
    return registry
