# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Small versioned research-project contracts over C0's existing typed records."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import re
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .object_schema import bounded_json, schema_validator, validate_record

PREFIX = 'c0_project_'
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def string(maximum=128, *, minimum=1, values=None):
    result = {'type': 'string', 'minLength': minimum, 'maxLength': maximum}
    if values is not None:
        result['enum'] = values
    return result


def integer(minimum, maximum):
    return {'type': 'integer', 'minimum': minimum, 'maximum': maximum}


def array(item=None, maximum=100):
    return {'type': 'array', 'items': item or string(), 'maxItems': maximum}


def record(**properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


RESEARCH = record(normal_daily_attempts=integer(1, 50), urgent_total_daily_attempts=integer(1, 100),
    urgent_priority={'type': 'integer', 'const': 0}, child_priority_increment=integer(1, 100),
    max_children_per_investigation=integer(1, 3), max_attempts=integer(1, 10),
    max_active_items=integer(1, 1000), max_new_roots_per_day=integer(1, 50))
MONITORING = record(enabled={'type': 'boolean'}, mandatory_primary_topic_refresh={'type': 'boolean', 'const': True},
    max_queries_per_topic=integer(1, 50), max_sources_per_topic=integer(1, 100), overlap_hours=integer(0, 168))
SCHEDULE = record(daily_local_time=string(5), weekly_day=string(values=DAYS), weekly_local_time=string(5),
    execution_provider=string(values=['external_agent']), enabled={'type': 'boolean'})
MANIFEST = record(schema_version={'type': 'integer', 'const': 1}, project_id=string(36), space_id=string(36),
    name=string(128), description=string(2048, minimum=0), language=string(35), timezone=string(100),
    purpose=string(4096), scope=string(4096), exclusions=array(string(512)), primary_topic_ids=array(),
    research=RESEARCH, monitoring=MONITORING, schedule=SCHEDULE,
    reporting=record(upcoming_days=integer(1, 90), quiet_day_report={'type': 'boolean'}),
    maintenance=record(semantic_pages_per_week=integer(1, 100), max_inventory=integer(1, 10000)),
    connector_ids=array(), state=record(initialized={'type': 'boolean'},
        migration_status=string(values=['not_started', 'prepared', 'imported'])))
TOPIC = record(key=string(128), schema_version={'type': 'integer', 'const': 1}, topic_id=string(), label=string(256),
    classification=string(values=['user', 'adjacent', 'peripheral']),
    lifecycle=string(values=['active', 'provisional', 'archived', 'retired']), aliases=array(string(256)),
    parent_ids=array(maximum=8), anchor_ids=array(maximum=8), originating_question=string(2048, minimum=0),
    direct_contribution=string(2048, minimum=0), assessment_ref=string(512, minimum=0),
    authorization_ref=string(512, minimum=0), authorized_by=string(36, minimum=0),
    created_at=string(40), expires_at=string(40, minimum=0))
TOPIC_INPUT=deepcopy(TOPIC)
for _field in ('key','schema_version','authorized_by','created_at','expires_at'):
    TOPIC_INPUT['properties'].pop(_field)
TOPIC_INPUT['required']=['topic_id','label','classification']
WEBSITE = record(seeds=array(string(4096),maximum=100),allowed_roots=array(string(4096),maximum=100),
    sitemaps=array(string(4096),maximum=100),exclude=array(string(4096),maximum=100),
    profile=string(values=['generic','docusaurus','sphinx']),selectors=array(string(4096),maximum=100),
    remove_selectors=array(string(4096),maximum=100),language=string(128,minimum=0),product=string(128,minimum=0),
    product_version=string(128,minimum=0),manual=string(128,minimum=0),interval_ms=integer(100,60000),
    max_total_bytes=integer(65536,67108864),max_cache_pages=integer(1,1000),configuration_version=string(128))
CONNECTOR_DEFINITION = record(id=string(64), adapter=string(values=['local_files','http','rss_atom','sitemap','website','github','c0_space','wikiplant_export']),
    enabled={'type':'boolean'}, include=array(string(512)), paths=array(string(512)), url=string(4096),
    repository=string(150), root=string(1024), source_space_id=string(36), authorization_ref=string(512),
    max_items=integer(1,1000), max_requests=integer(1,500), max_bytes=integer(1,16777216),
    max_pages=integer(1,20), max_depth=integer(1,4), timeout=integer(1,30),website=WEBSITE)
CONNECTOR_DEFINITION['required']=['id','adapter','enabled','include','max_items','max_requests','max_bytes','max_pages','max_depth','timeout']
SCHEMAS = {
    'manifest_v1': record(key=string(128), version=integer(1, 2147483647), manifest=MANIFEST),
    'config_v1': record(key=string(128), version=integer(1, 2147483647), manifest=MANIFEST,
        actor_id=string(36), authorization_ref=string(512), recorded_at=string(40)),
    'topic_v1': TOPIC,
    'connector_v1': record(key=string(128), connector_id=string(64), definition=CONNECTOR_DEFINITION,
        definition_hash=string(64), authorization_ref=string(512), approved_by=string(36)),
    'connector_sync_v1': record(key=string(128), connector_id=string(64), definition_hash=string(64),
        last_attempt_at=string(40), last_success_at=string(40,minimum=0),
        status=string(values=['complete','partial','blocked']), last_error=string(128,minimum=0),
        retry_after=string(40,minimum=0), remote_cursor=string(4096,minimum=0), progress_cursor=string(4096,minimum=0),
        attempt_count=integer(0,10),
        verified_items=integer(0,1000), discovered_items=integer(0,1000)),
    'source_sync_v1': record(key=string(128), connector_id=string(64), definition_hash=string(64), external_id=string(128),
        parent_external_id=string(4096), parent_content_hash=string(64), part_number=integer(1,256),
        start_byte=integer(0,16777216), end_byte=integer(0,16777216),
        last_attempt_at=string(40), last_success_at=string(40,minimum=0), last_content_hash=string(64),
        source_id=string(36), version_id=string(36), extraction_status=string(values=['queued','ready','failed']),
        sync_status=string(values=['queued','verified','failed','partial']), last_error=string(128,minimum=0),
        retry_after=string(40,minimum=0), remote_cursor=string(4096,minimum=0), provenance=record(original_url=string(4096,minimum=0),
            canonical_url=string(4096,minimum=0), retrieved_at=string(40), published_at=string(40,minimum=0),
            updated_at=string(40,minimum=0), details=string(8192))),
}
SCHEMAS['connector_config_v1'] = {**SCHEMAS['connector_v1'],
    'properties': {**SCHEMAS['connector_v1']['properties'], 'version':integer(1,2147483647)},
    'required': [*SCHEMAS['connector_v1']['required'],'version']}
SCHEMAS['source_part_v1'] = SCHEMAS['source_sync_v1']
SCHEMAS['source_snapshot_v1'] = record(key=string(128),connector_id=string(64),external_id=string(4096),
    content_hash=string(64),part_receipt_ids=array(string(36),maximum=100),total_bytes=integer(1,16777216),verified_at=string(40))
# Operational rows are separate bounded records, not a project-sized JSON blob.
WORKFLOWS = ['initialize','daily','weekly','manual_research','source_sync','maintenance','report_publication']
LEASE = record(run_id=string(64),lease_owner=string(128),fencing_generation=integer(1,2147483647))
QUEUE_INPUT = record(stable_id=string(128),topic_id=string(128),question=string(2048),
    kind=string(values=['investigation','validation','contradiction']),
    origin=string(values=['user','initialization','monitoring','discovery','research','calendar','maintenance']),
    origin_reference=string(512),priority=integer(0,100),priority_reason=string(512),urgency_reason=string(512,minimum=0),
    parent_ids=array(maximum=8),related_pages=array(string(36),maximum=20),not_before=string(40,minimum=0),
    due_at=string(40,minimum=0),question_conditions=string(1024,minimum=0),entity_version=string(128,minimum=0),
    time_window=string(128,minimum=0),assessment_ref=string(512),direct_contribution=string(2048),
    anchor_ids=array(maximum=8),novelty_key=string(128),novelty_refs=array(string(512),maximum=20),
    root_reason=string(values=['user_request','approved_initialization','independent_external_event','derived']),
    authorization_ref=string(512,minimum=0),excluded={'type':'boolean'},
    semantic_matches=array(record(target_id=string(),equivalent={'type':'boolean'},new_evidence={'type':'boolean'},
        assessment_ref=string(512),reason=string(1024)),maximum=20),
    independent_parents=array(record(parent_id=string(),reason=string(1024),evidence_refs=array(string(512),maximum=10)),maximum=8))
SCHEMAS.update({
    'run_v1': record(key=string(128),run_id=string(64),project_id=string(36),config_version=integer(1,2147483647),workflow_type=string(values=WORKFLOWS),
        local_cycle_date=string(10),cycle_key=string(128),scheduled_for=string(40),started_at=string(40),finished_at=string(40,minimum=0),
        state=string(values=['running','complete','partial','blocked']),current_phase=string(64),attempt_count=integer(1,10),
        lease_owner=string(128),lease_actor_id=string(36),lease_expiry=string(40,minimum=0),fencing_generation=integer(1,2147483647),
        error_code=string(128,minimum=0),result_refs=array(string(128),maximum=100)),
    'checkpoint_v1': record(key=string(128),run_id=string(64),config_version=integer(1,2147483647),phase=string(64),
        status=string(values=['SAVED','PARTIAL','BLOCKED']),payload_hash=string(64),
        references=array(string(128),maximum=100),summary=string(4096,minimum=0),recorded_at=string(40)),
    'queue_v1': record(key=string(128),project_id=string(36),stable_id=string(),topic_id=string(),question=string(2048),
        kind=QUEUE_INPUT['properties']['kind'],origin=QUEUE_INPUT['properties']['origin'],origin_reference=string(512),
        priority=integer(0,100),expansion_priority=integer(0,100),priority_reason=string(512),urgency_reason=string(512,minimum=0),
        parent_ids=array(maximum=8),lineage_root_id=string(),root_ids=array(maximum=8),anchor_ids=array(maximum=8),
        dedup_key=string(64),question_key=string(64),context_key=string(64),root_admitted={'type':'boolean'},novelty_key=string(128),related_pages=array(string(36),maximum=20),
        created_at=string(40),not_before=string(40,minimum=0),due_at=string(40,minimum=0),
        status=string(values=['pending','deferred','in_progress','retry_wait','awaiting_merge','complete','blocked','archived']),
        terminal={'type':'boolean'},defer_reason=string(128,minimum=0),attempt_count=integer(0,10),retry_after=string(40,minimum=0),
        result_reference=string(128,minimum=0),last_attempt_id=string(64,minimum=0),admission_ref=string(128)),
    'admission_v1': record(key=string(128),candidate_id=string(),
        disposition=string(values=['admit','merge','defer_capacity','archive_candidate','reject_scope','needs_user_scope_decision']),
        reason=string(256),target_id=string(128,minimum=0),candidate=QUEUE_INPUT,
        config_version=integer(1,2147483647),decided_at=string(40)),
    'budget_v1': record(key=string(128),project_id=string(36),local_date=string(10),timezone=string(100),
        window_end=string(40),ordinary_limit=integer(1,50),total_limit=integer(1,100),used=integer(0,100),
        roots_admitted=integer(0,10000),roots_limit=integer(1,50),config_version=integer(1,2147483647)),
    'budget_pointer_v1': record(key=string(128),local_date=string(10),window_end=string(40)),
    'attempt_v1': record(key=string(128),attempt_id=string(64),queue_id=string(),run_id=string(64),
        project_id=string(36),local_date=string(10),slot=integer(1,100),attempt_number=integer(1,10),
        priority=integer(0,100),anchor_ids=array(maximum=8),selection_reason=string(512),reserved_at=string(40),
        state=string(values=['reserved','invoking','uncertain','failed','result_saved','complete']),
        result_reference=string(128,minimum=0),invocation_ref=string(128,minimum=0),fencing_generation=integer(1,2147483647)),
    'invocation_v1': record(key=string(128),attempt_id=string(64),
        state=string(values=['started','returned','uncertain','failed']),result_reference=string(128,minimum=0),external_reference=string(512,minimum=0),
        error_code=string(128,minimum=0),recorded_at=string(40),run_id=string(64),fencing_generation=integer(1,2147483647)),
})
SCHEMAS['connector_lease_v1']=record(key=string(128),connector_id=string(64),run_id=string(64))
SCHEMAS['completion_v1']=record(key=string(128),attempt_id=string(64),result_reference=string(128),
    commit_references=array(string(128),maximum=100),recorded_at=string(40))
SCHEMAS.update({
    'monitor_cycle_v1': record(key=string(128),cycle_id=string(64),project_id=string(36),topic_id=string(),local_date=string(10),
        config_version=integer(1,2147483647),scope_hash=string(64),coverage_start=string(40),coverage_end=string(40),
        max_queries=integer(1,50),max_sources=integer(1,100),queries_used=integer(0,50),sources_used=integer(0,100),
        status=string(values=['in_progress','complete','no_material_update','partial','blocked','awaiting_merge']),
        result_reference=string(36,minimum=0),successful_watermark=string(40,minimum=0),summary=string(4096,minimum=0)),
    'monitor_call_v1': record(key=string(128),call_id=string(64),cycle_id=string(64),kind=string(values=['query','source']),
        ordinal=integer(1,100),scope_hash=string(64),request_text=string(2048),run_id=string(64),fencing_generation=integer(1,2147483647),
        state=string(values=['reserved','started','succeeded','failed','uncertain']),external_reference=string(512,minimum=0),
        selected_sources=array(string(512),maximum=100),version_id=string(36,minimum=0),citation_ids=array(string(36),maximum=100),
        replaces_call_id=string(64,minimum=0),summary=string(2048,minimum=0),reserved_at=string(40),recorded_at=string(40)),
    'monitor_watermark_v1': record(key=string(128),topic_id=string(),scope_hash=string(64),cycle_id=string(64),coverage_end=string(40)),
    'monitor_success_v1': record(key=string(128),cycle_id=string(64),scope_hash=string(64),coverage_start=string(40),coverage_end=string(40),
        query_ids=array(string(64),maximum=50),source_ids=array(string(64),maximum=100),result_reference=string(36,minimum=0),verified_at=string(40)),
})
SCHEMAS['monitor_call_history_v1']=SCHEMAS['monitor_call_v1']
SCHEMAS['runner_observation_v1']=record(key=string(128),project_id=string(36),config_version=integer(1,2147483647),
    provider=string(values=['chatgpt_work','external_runner']),workflow_type=string(values=['daily','weekly']),
    observation_source=string(values=['operator_report','runner_report','sdk_simulation']),
    status=string(values=['unverified','blocked','reported_installed','reported_execution']),
    task_reference=string(512,minimum=0),run_id=string(64,minimum=0),evidence_reference=string(512,minimum=0),
    summary=string(4096),actor_id=string(36),recorded_at=string(40))

CHALLENGE_QUERY=record(request_id=string(128),query=string(512),
    state=string(values=['succeeded','failed','uncertain']),snapshot_chunk_id=string(36,minimum=0),
    external_reference=string(512,minimum=0),replaces=string(128,minimum=0))
CHALLENGE=record(state=string(values=['not_required','not_searched','searched','partial','blocked']),
    reason=string(2048),strongest_alternative=string(2048,minimum=0),
    falsification_conditions=array(string(512),maximum=5),queries=array(CHALLENGE_QUERY,maximum=3),
    counter_citation_ids=array(string(36),maximum=10),coverage=string(2048,minimum=0),
    conclusion_change=string(2048,minimum=0))
FINDING_INPUT=record(statement=string(2048),
    classification=string(values=['observed_fact','supported_inference','hypothesis','contradiction','outdated_assertion','unknown']),
    confidence=integer(0,100),rationale=string(2048),citation_ids=array(string(36),maximum=32),
    claim_id=string(36,minimum=0),claim_revision=integer(0,2147483647),consequential={'type':'boolean'},
    applicability_limits=array(string(512),maximum=8),challenge=CHALLENGE)
RESULT_INPUT=record(summary=string(8192),changes=string(4096),importance=string(4096),
    assumptions=array(string(512),maximum=8),uncertainties=array(string(512),maximum=8),
    assessment_ref=string(512),findings=array(FINDING_INPUT,maximum=20))
RESULT_INPUT['properties']['findings']['minItems']=1
SCHEMAS.update({
    'result_v1':record(key=string(128),result_id=string(64),project_id=string(36),run_id=string(64),
        attempt_id=string(64,minimum=0),cycle_id=string(64,minimum=0),topic_id=string(),scope_hash=string(64),
        config_version=integer(1,2147483647),local_date=string(10),content_version=integer(1,2147483647),
        question=string(2048),summary=string(8192),changes=string(4096),importance=string(4096),
        assumptions=array(string(512),maximum=8),uncertainties=array(string(512),maximum=8),
        assessment_ref=string(512),finding_ids=array(string(36),maximum=20),payload_hash=string(64),
        state=string(values=['awaiting_merge','partial','published']),publication_reference=string(36,minimum=0),
        saved_at=string(40)),
    'finding_v1':record(key=string(128),result_id=string(64),content_version=integer(1,2147483647),ordinal=integer(1,20),
        **FINDING_INPUT['properties'],evidence_hash=string(64),claim_value_hash=string(64,minimum=0),
        valid_from=string(40,minimum=0),valid_to=string(40,minimum=0)),
    'result_publication_v1':record(key=string(128),result_reference=string(36),content_version=integer(1,2147483647),
        config_version=integer(1,2147483647),run_id=string(64),wiki_revision_ids=array(string(36),maximum=20),
        wiki_hashes=array(string(64),maximum=20),claim_ids=array(string(36),maximum=20),verified_at=string(40)),
})
SCHEMAS['result_history_v1']=SCHEMAS['result_v1']
REPORT_MEMBER_INPUT=record(result_reference=string(36),disposition=string(values=['included','deferred']),
    location=string(values=['main','appendix']),wiki_revision_id=string(36),start_byte=integer(0,131071),
    end_byte=integer(1,131072),reason=string(2048,minimum=0),assessment_ref=string(512))
SCHEMAS.update({
    'report_v1':record(key=string(128),report_id=string(64),project_id=string(36),
        report_type=string(values=['daily','weekly']),local_date=string(10),language=string(35),
        config_version=integer(1,2147483647),source_config_version=integer(1,2147483647),
        source_run_id=string(64),publisher_run_id=string(64),current_version=integer(0,2147483647),
        draft_generation=integer(1,2147483647),draft_open={'type':'boolean'},cutoff_at=string(40),
        included_count=integer(0,10000),deferred_count=integer(0,10000),inventory_hash=string(64),
        monitoring_expected=integer(0,700),monitoring_complete=integer(0,700),coverage_complete={'type':'boolean'},
        wiki_page_id=string(36,minimum=0),wiki_revision_id=string(36,minimum=0),wiki_revision=integer(0,2147483647),
        content_hash=string(64,minimum=0),saved_status=string(values=['draft','saved']),saved_at=string(40,minimum=0)),
    'report_member_v1':record(key=string(128),report_reference=string(36),report_id=string(64),report_version=integer(1,2147483647),
        draft_generation=integer(1,2147483647),result_reference=string(36),result_version=integer(1,2147483647),
        disposition=string(values=['included','deferred']),location=string(values=['main','appendix']),
        wiki_revision_id=string(36),wiki_hash=string(64),start_byte=integer(0,131071),end_byte=integer(1,131072),
        entry_hash=string(64),reason=string(2048,minimum=0),assessment_ref=string(512)),
    'report_delivery_v1':record(key=string(128),report_reference=string(36),report_version=integer(1,2147483647),
        content_hash=string(64),channel=string(values=['external_result','notification','human_read']),
        state=string(values=['started','succeeded','failed','uncertain']),attempt_count=integer(0,5),
        retry_after=string(40,minimum=0),run_id=string(64),fencing_generation=integer(1,2147483647),
        external_reference=string(512,minimum=0),evidence_reference=string(512,minimum=0),
        observation_source=string(values=['operator_report','runner_report','sdk_simulation']),
        recorded_at=string(40),actor_id=string(36)),
})
SCHEMAS['report_history_v1']=SCHEMAS['report_v1']
SCHEMAS['report_delivery_history_v1']=SCHEMAS['report_delivery_v1']

EVENT_INPUT=record(event_id=string(128),topic_id=string(128),kind=string(values=['event','research_refresh']),
    title=string(256),description=string(4096,minimum=0),start_time=string(40,minimum=0),end_time=string(40,minimum=0),
    timezone=string(100),date_precision=string(values=['date','time','month','year','unknown']),
    source_reference=string(512),status=string(values=['scheduled','tentative','completed','cancelled','unsupported']),
    refresh_question=string(2048,minimum=0),priority=integer(0,100),expansion_priority=integer(0,100),
    parent_ids=array(maximum=8),related_pages=array(string(36),maximum=20),lead_days=integer(0,90),
    recurrence=record(frequency=string(values=['none','daily','weekly','monthly']),interval=integer(1,365),until=string(10,minimum=0)))
SEMANTIC_INPUT=record(status=string(values=['reviewed','partial','blocked']),assessment=string(4096),
    assessment_ref=string(512),limitations=array(string(512),maximum=8),citation_ids=array(string(36),maximum=32),
    proposed_question=string(2048,minimum=0))
SCHEMAS.update({
    'topic_history_v1':record(key=string(128),topic_id=string(128),version=integer(1,2147483647),
        topic=TOPIC,actor_id=string(36),recorded_at=string(40),observation=string(values=['changed','upgrade_snapshot'])),
    'event_v1':record(key=string(128),project_id=string(36),**EVENT_INPUT['properties'],last_checked_at=string(40)),
    'event_history_v1':record(key=string(128),event_id=string(128),version=integer(1,2147483647),
        definition=EVENT_INPUT,actor_id=string(36),recorded_at=string(40)),
    'event_occurrence_v1':record(key=string(128),event_id=string(128),local_date=string(10),
        queue_id=string(128,minimum=0),lineage_root_id=string(128,minimum=0),admission_reference=string(36),
        disposition=string(64),recorded_at=string(40)),
    'audit_v1':record(key=string(128),run_id=string(64),config_version=integer(1,2147483647),kind=string(32),
        cursor=string(36,minimum=0),cursor_revision=integer(0,2147483647),scanned=integer(0,10000),finding_count=integer(0,100000),
        state=string(values=['partial','complete','blocked']),limitations=array(string(512),maximum=8),updated_at=string(40)),
    'audit_finding_v1':record(key=string(128),audit_reference=string(36),resource_id=string(128),
        kind=string(64),detail=string(2048),reference_ids=array(string(36),maximum=32),recorded_at=string(40)),
    'audit_cursor_v1':record(key=string(128),kind=string(32),after_id=string(36,minimum=0),rounds=integer(0,2147483647)),
    'audit_observation_v1':record(key=string(128),kind=string(32),resource_id=string(128),audit_reference=string(36),
        issue_count=integer(0,1000),checked_at=string(40)),
    'semantic_round_v1':record(key=string(128),run_id=string(64),config_version=integer(1,2147483647),
        selected_ids=array(string(36),maximum=100),inventory_total=integer(0,2147483647),
        inventory_complete={'type':'boolean'},semantic_coverage_complete={'type':'boolean'},limit=integer(1,100),
        state=string(values=['partial','complete']),cursor_before=string(36,minimum=0),cursor_after=string(36,minimum=0),cursor_rounds=integer(0,2147483647)),
    'semantic_cursor_v1':record(key=string(128),last_page_id=string(36,minimum=0),rounds=integer(0,2147483647)),
    'semantic_selection_v1':record(key=string(128),round_id=string(64),page_id=string(36),wiki_revision_id=string(36),
        wiki_revision=integer(1,2147483647),content_hash=string(64),state=string(values=['pending','reviewed','partial','blocked'])),
    'semantic_review_v1':record(key=string(128),selection_reference=string(36),wiki_revision_id=string(36),
        content_hash=string(64),**SEMANTIC_INPUT['properties'],actor_id=string(36),recorded_at=string(40)),
    'archive_v1':record(key=string(128),run_id=string(64),topic_id=string(128),topic_snapshot=TOPIC,
        summary=string(4096),assessment_ref=string(512),reference_ids=array(string(36),maximum=100),archived_at=string(40)),
    'release_check_v1':record(key=string(128),repository=string(150),installed_version=string(64),
        latest_version=string(64,minimum=0),metadata_version_id=string(36,minimum=0),metadata_hash=string(64,minimum=0),
        status=string(values=['available','up_to_date','no_release','failed','partial','security_alert']),
        summary=string(2048),checked_at=string(40),last_success_at=string(40,minimum=0),
        week_start=string(10),retry_after=string(40,minimum=0),attempts=integer(1,3)),
    'release_identity_v1':record(key=string(128),repository=string(150),version=string(64),
        identity_hash=string(64),metadata_version_id=string(36),observed_at=string(40)),
})
SCHEMAS['semantic_selection_history_v1']=SCHEMAS['semantic_selection_v1']
SCHEMAS['release_check_history_v1']=SCHEMAS['release_check_v1']
PROJECT_UNIQUE_FIELDS = {'queue_v1': ['key','dedup_key']}


def project_unique_fields(kind):
    return list(PROJECT_UNIQUE_FIELDS.get(kind,['key']))


SCHEMAS = {key: schema_validator(value).schema for key, value in SCHEMAS.items()}
DEFAULTS = {
    'schema_version': 1, 'description': '', 'language': 'en', 'timezone': 'UTC', 'exclusions': [],
    'primary_topic_ids': [], 'connector_ids': [],
    'research': {'normal_daily_attempts': 5, 'urgent_total_daily_attempts': 10, 'urgent_priority': 0,
        'child_priority_increment': 20, 'max_children_per_investigation': 3, 'max_attempts': 3,
        'max_active_items': 50, 'max_new_roots_per_day': 5},
    'monitoring': {'enabled': True, 'mandatory_primary_topic_refresh': True,
        'max_queries_per_topic': 5, 'max_sources_per_topic': 10, 'overlap_hours': 12},
    'schedule': {'daily_local_time': '06:00', 'weekly_day': 'sunday', 'weekly_local_time': '08:00',
        'execution_provider': 'external_agent', 'enabled': False},
    'reporting': {'upcoming_days': 7, 'quiet_day_report': True},
    'maintenance': {'semantic_pages_per_week': 30, 'max_inventory': 1000},
    'state': {'initialized': False, 'migration_status': 'not_started'},
}


def identifier(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        raise ValueError('invalid_project_identifier')
    return value


def timestamp(value):
    if type(value) is not str:
        raise ValueError('invalid_project_time')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise ValueError('invalid_project_time') from None


def normalize_manifest(value):
    """Compatible v1 additions only; unknown/future versions fail closed."""
    value = bounded_json(value)
    result = deepcopy(DEFAULTS)
    for key, item in value.items():
        if key in result and type(result[key]) is dict and type(item) is dict:
            result[key].update(item)
        else:
            result[key] = item
    result = validate_record(MANIFEST, result)
    if str(UUID(result['space_id'])) != result['space_id'] or str(UUID(result['project_id'])) != result['project_id']:
        raise ValueError('invalid_project_identity')
    if result['project_id'] != result['space_id']:
        raise ValueError('project_identity_must_match_space')
    try:
        ZoneInfo(result['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('invalid_project_timezone') from None
    if not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*', result['language']):
        raise ValueError('invalid_project_language')
    for field in ('daily_local_time', 'weekly_local_time'):
        if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', result['schedule'][field]):
            raise ValueError('invalid_project_schedule')
    if result['research']['urgent_total_daily_attempts'] < result['research']['normal_daily_attempts']:
        raise ValueError('invalid_project_budgets')
    for field in ('primary_topic_ids', 'connector_ids'):
        values = result[field]
        if len(values) != len(set(values)):
            raise ValueError('duplicate_project_identifier')
        for item in values:
            identifier(item)
    if result['state']['initialized'] and (not result['primary_topic_ids'] or not result['monitoring']['enabled']):
        raise ValueError('active_project_requires_monitoring')
    return result


def next_occurrence(manifest, workflow, after):
    """Strictly future; gaps move forward by the gap, folds choose first occurrence."""
    if workflow not in ('daily', 'weekly') or after.tzinfo is None:
        raise ValueError('invalid_project_schedule')
    zone = ZoneInfo(manifest['timezone'])
    local = after.astimezone(zone)
    hour, minute = map(int, manifest['schedule'][workflow + '_local_time'].split(':'))
    for offset in range(9):
        day = local.date() + timedelta(days=offset)
        if workflow == 'weekly' and day.weekday() != DAYS.index(manifest['schedule']['weekly_day']):
            continue
        candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone, fold=0).astimezone(timezone.utc)
        if candidate > after.astimezone(timezone.utc):
            return candidate
    raise ValueError('invalid_project_schedule')


def occurrence_on_day(manifest, workflow, local_day):
    """Configured occurrence, with the same gap/fold policy as next_occurrence."""
    if workflow not in ('daily','weekly'):
        raise ValueError('invalid_project_schedule')
    day=date.fromisoformat(local_day)
    if day.isoformat()!=local_day or (workflow=='weekly' and day.weekday()!=DAYS.index(manifest['schedule']['weekly_day'])):
        raise ValueError('invalid_project_cycle_date')
    hour,minute=map(int,manifest['schedule'][workflow+'_local_time'].split(':'))
    return datetime(day.year,day.month,day.day,hour,minute,tzinfo=ZoneInfo(manifest['timezone']),fold=0).astimezone(timezone.utc)
