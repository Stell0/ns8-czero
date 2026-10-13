# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from czero_core import core_health, core_version


def test_core_health_is_transport_independent():
    assert core_health() == {
        "status": "ok",
        "service": "czero",
        "core_version": core_version,
    }
