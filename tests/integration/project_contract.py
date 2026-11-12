# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Additive project operations; the frozen original 77 contracts remain exact."""
PROJECT_OPERATIONS = frozenset({
    'project_export_get',
    'project_event_set','project_audit_step','project_semantic_select','project_semantic_review',
    'project_peripheral_archive','project_release_observe','project_diagnostics_get',
    'project_result_save','project_result_publish','project_report_prepare','project_report_member_set',
    'project_report_finalize','project_report_get','project_report_delivery_observe',
    'project_agent_package_get',
    'project_schedule_get','project_runner_observe',
    'project_record_get','project_run_claim','project_run_checkpoint','project_queue_admit',
    'project_queue_retune','project_attempt_reserve','project_invocation_set','project_research_complete',
    'project_monitor_begin','project_monitor_reserve','project_monitor_observe','project_monitor_finish',
    'project_get', 'project_initialize', 'project_configure',
    'project_topic_set', 'project_records_list',
    'project_connector_set', 'project_source_status_get', 'project_source_status_set', 'project_connector_status_set', 'project_source_snapshot_set',
})
DOCUMENT_OPERATIONS = frozenset({'source_documents_list','source_documents_get','source_version_document_get','source_document_outline_get','source_document_sections_get',
    'source_document_references_get','context_bundle_get'})
COMPILATION_OPERATIONS = frozenset({'compilation_policy_get', 'compilation_policy_set',
    'compilation_source_bindings_get', 'compilation_propose', 'compilation_tasks_list',
    'compilation_tasks_get', 'compilation_run_claim', 'compilation_run_checkpoint',
    'compilation_status_get', 'compilation_dependencies_list',
    'compilation_target_bindings_get', 'compilation_plan_validate', 'compilation_apply', 'compilation_verify',
    'compilation_discovery_get','compilation_discover','compilation_assessment_complete',
    'compilation_semantic_select','compilation_semantic_review'})
REFERENCE_OPERATIONS = frozenset({'cross_space_ref_create','cross_space_refs_list','cross_space_ref_delete'})
SPACE_ACCESS_OPERATIONS = frozenset({'space_access_set'})
TOOL_COUNT = len(REFERENCE_OPERATIONS) + len(COMPILATION_OPERATIONS) + len(SPACE_ACCESS_OPERATIONS) + 75 + len(PROJECT_OPERATIONS) + len(DOCUMENT_OPERATIONS)

REMOVED_HISTORY_OPERATIONS=frozenset({'wiki_revisions_list','knowledge_annotations_history','source_document_history'})
CHANGED_VALIDATION_CONTRACTS=frozenset({'claims_annotate','claims_create','claims_get','claims_list','claims_retract','knowledge_bundle_apply','sources_list'})
