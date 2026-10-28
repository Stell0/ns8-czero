# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

core_version = "0.35.1"


def core_health() -> dict[str, str]:
    """Return the stable, transport-independent C0 Core health payload."""
    return {"status": "ok", "service": "czero", "core_version": core_version}
