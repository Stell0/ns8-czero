# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed project errors shared by current and legacy MCP serialization."""
PROJECT_OPERATIONS=frozenset({
    'project_event_set','project_audit_step','project_semantic_select','project_semantic_review',
    'project_peripheral_archive','project_release_observe','project_diagnostics_get',
    'project_result_save','project_result_publish','project_report_prepare','project_report_member_set',
    'project_report_finalize','project_report_get','project_report_delivery_observe',
    'project_agent_package_get',
    'project_schedule_get','project_runner_observe',
    'project_monitor_begin','project_monitor_reserve','project_monitor_observe','project_monitor_finish',
    'project_get','project_initialize','project_configure','project_topic_set','project_records_list',
    'project_connector_set','project_source_status_get','project_source_status_set','project_connector_status_set',
    'project_source_snapshot_set','project_record_get','project_run_claim','project_run_checkpoint','project_queue_admit',
    'project_queue_retune','project_attempt_reserve','project_invocation_set','project_research_complete',
})
PUBLIC_ERRORS=frozenset({(409,'project_conflict'),(404,'project_not_found'),(422,'invalid_project_request'),
    (409,'project_connection_not_configured'),
    (503,'project_core_upgrade_required'),(503,'service_unavailable')})


def mcp_project_error(operation,status,detail):
    if operation not in PROJECT_OPERATIONS:return None
    return (detail,status) if type(status) is int and type(detail) is str and (status,detail) in PUBLIC_ERRORS else ('service_unavailable',503)
