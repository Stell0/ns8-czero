# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Match Robot's sibling-library import path for runpy fixture tests."""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def robot_library_path(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
