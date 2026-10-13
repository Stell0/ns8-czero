# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted extension point shared by the application API and worker."""
from czero_core.jobs import default_registry


def build_registry():
    # Forks register synchronous deterministic handlers here in trusted code.
    return default_registry()
