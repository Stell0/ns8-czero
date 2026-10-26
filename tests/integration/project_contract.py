# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Additive project operations; the frozen original 77 contracts remain exact."""
PROJECT_OPERATIONS = frozenset({
    'project_get', 'project_initialize', 'project_configure',
    'project_topic_set', 'project_records_list',
})
TOOL_COUNT = 77 + len(PROJECT_OPERATIONS)
