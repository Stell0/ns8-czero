# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import TYPE_CHECKING as _TYPE_CHECKING

from .health import core_health, core_version

__all__ = ["core_health", "core_version", "Database"]

if _TYPE_CHECKING:
    from .database import Database


def __getattr__(name):
    # Isolated parsers can start without importing the database driver.
    if name == "Database":
        from .database import Database

        globals()[name] = Database
        return Database
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))
