# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Additive project operations; the frozen original 77 contracts remain exact."""
PROJECT_OPERATIONS = frozenset({
    'project_record_get','project_run_claim','project_run_checkpoint','project_queue_admit',
    'project_queue_retune','project_attempt_reserve','project_invocation_set','project_research_complete',
    'project_get', 'project_initialize', 'project_configure',
    'project_topic_set', 'project_records_list',
    'project_connector_set', 'project_source_status_get', 'project_source_status_set', 'project_connector_status_set', 'project_source_snapshot_set',
})
TOOL_COUNT = 77 + len(PROJECT_OPERATIONS)
