# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private native diagnostic; no optional network inference or provider descriptors."""
import json

from czero_core import core_version
from czero_core.database import Database
from czero_core.retrieval_config import load_settings
from czero_app import __version__ as app_version


def status():
    settings = load_settings()
    try:
        database = Database()
    except ValueError:
        health = {'status': 'unavailable', 'reason': 'database_configuration_invalid'}
    else:
        try:
            health = database.health()
        finally:
            database.close()
    return {'core_version': core_version, 'app_version': app_version, 'database': health,
            'retrieval': {'configuration_valid': settings.issue is None,
                          'embeddings_configured': settings.embedding is not None,
                          'scorer_mode': settings.scorer_mode}}


if __name__ == '__main__':
    print(json.dumps(status()))
