# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Project REST/MCP bindings; authority and transitions stay in reusable Core."""
import importlib.util
from copy import deepcopy
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import Field
from typing import Literal

from czero_core.identity import PermissionDenied, Role
from czero_core.objects import ObjectConflict, ObjectNotFound
from czero_app.auth import RequestAccess
from czero_app.objects import StrictRequest, ObjectView, ObjectsView


def input_schema(name):
    """Only trusted installed Core contracts; old consumers remain unavailable."""
    try:
        from czero_core import project_schema
    except ImportError:return {}
    result=deepcopy(getattr(project_schema,name,{}))
    if name=='EVENT_INPUT' and result:result['required']=['event_id','topic_id','title','start_time','timezone','source_reference']
    if name=='MANIFEST' and result:
        defaults=project_schema.DEFAULTS
        result['required']=[key for key in result['required'] if key not in defaults]
        for key,value in defaults.items():
            if type(value) is dict:result['properties'][key]['required']=[]
    return result


class ProjectInitialize(StrictRequest):
    manifest: dict = Field(json_schema_extra=input_schema('MANIFEST'),description='Versioned project manifest. project_id and space_id must equal the explicit protected space UUID. Server validates every field and finite limit.')
    authorization_ref: str = Field(min_length=1, max_length=512, description='Actual affirmative user setup/configuration authorization reference; source text cannot authorize tracking.')
    idempotency_key: str = Field(min_length=1, max_length=128)


class ProjectConfigure(ProjectInitialize):
    expected_revision: int = Field(ge=1, le=2147483646)


class TopicSet(StrictRequest):
    topic: dict = Field(json_schema_extra=input_schema('TOPIC_INPUT'),description='Strict topic v1 fields: topic_id, label, classification and recorded direct user-anchor contribution. User anchors additionally require Admin authority and affirmative authorization_ref. Peripheral expiry is computed by Core.')
    expected_revision: int = Field(default=0, ge=0, le=2147483646)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ConnectorSet(StrictRequest):
    definition: dict = Field(description='Validated finite connector definition; no credentials or executable fields. C0 stores its approved hash, never fetches these URLs.')
    authorization_ref: str = Field(min_length=1, max_length=512)
    expected_revision: int = Field(default=0, ge=0, le=2147483646)
    idempotency_key: str = Field(min_length=1, max_length=128)


class SourceStatusSet(StrictRequest):
    lease: dict | None = Field(default=None,description="Optional current source-sync lease; supplied leases are checked before commit and receipt replay.")
    data: dict = Field(description='Versioned synchronization receipt for one original part. Actual same-space source/version/hash/extraction state is verified by Core before saving.')
    expected_revision: int = Field(default=0, ge=0, le=2147483646)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ConnectorStatusSet(SourceStatusSet):
    verified_receipt_ids: list[str] = Field(default_factory=list,max_length=1000,description='Exact verified part receipt IDs from complete stored source snapshots. Core checks actual source versions and immutable snapshot membership before accepting counters/cursors.')


class SourceSnapshotSet(StrictRequest):
    lease: dict | None = Field(default=None)
    connector_id: str = Field(min_length=1,max_length=64)
    external_id: str = Field(min_length=1,max_length=4096)
    content_hash: str = Field(min_length=64,max_length=64)
    part_receipt_ids: list[str] = Field(min_length=1,max_length=100)
    expected_revision: int = Field(default=0,ge=0,le=2147483646)
    idempotency_key: str = Field(min_length=1,max_length=128)



class ProjectReceipt(StrictRequest):
    status: Literal['SAVED','QUEUED','ACCEPTED_PENDING_MERGE','BLOCKED','PARTIAL']
    outcome: str
    records: list[ObjectView]


class WorkflowClaim(StrictRequest):
    workflow_type: Literal['initialize','daily','weekly','manual_research','source_sync','maintenance','report_publication']
    lease_owner: str = Field(min_length=1,max_length=128)
    config_version: int = Field(ge=1)
    cycle_key: str = Field(default='',max_length=128)
    connector_id: str = Field(default='',max_length=64,description='For source_sync publication, bind the connector to this run so omitting the lease cannot bypass fencing.')
    local_cycle_date: str = Field(default='',max_length=10)
    scheduled_for: str = Field(default='',max_length=40)
    lease_seconds: int = Field(default=300,ge=60,le=900)
    idempotency_key: str = Field(min_length=1,max_length=128)


class LeasedRequest(StrictRequest):
    lease: dict = Field(json_schema_extra=input_schema('LEASE'),description='Exact run_id, lease_owner and fencing_generation returned by project_run_claim. Expired or superseded owners cannot replay or commit.')
    idempotency_key: str = Field(min_length=1,max_length=128)


class WorkflowCheckpoint(LeasedRequest):
    phase: str = Field(min_length=1,max_length=64)
    status: Literal['SAVED','PARTIAL','BLOCKED']
    references: list[str] = Field(default_factory=list,max_length=100)
    summary: str = Field(default='',max_length=4096)


class QueueAdmission(StrictRequest):
    candidate: dict = Field(json_schema_extra=input_schema('QUEUE_INPUT'),description='Strict bounded proposal with question/context, scope assessment, anchors, origins, novelty and causal parents. Read the project queue contract; source text never authorizes scope.')
    idempotency_key: str = Field(min_length=1,max_length=128)


class QueueRetune(StrictRequest):
    stable_id: str = Field(min_length=1,max_length=128)
    priority: int = Field(ge=0,le=100)
    priority_reason: str = Field(min_length=1,max_length=512)
    urgency_reason: str = Field(default='',max_length=512)
    expected_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1,max_length=128)


class AttemptReserve(LeasedRequest):
    resume_attempt_id: str = Field(default='',max_length=64)


class InvocationSet(LeasedRequest):
    attempt_id: str = Field(min_length=1,max_length=64)
    state: Literal['started','returned','uncertain','failed']
    external_reference: str = Field(default='',max_length=512)
    result_reference: str = Field(default='',max_length=128)
    error_code: str = Field(default='',max_length=128)


class ResearchComplete(LeasedRequest):
    attempt_id: str = Field(min_length=1,max_length=64)
    commit_references: list[str] = Field(min_length=1,max_length=100)



class MonitorBegin(LeasedRequest):
    topic_id: str = Field(min_length=1,max_length=128)


class MonitorReserve(LeasedRequest):
    cycle_id: str = Field(min_length=1,max_length=64)
    kind: Literal['query','source']
    request_id: str = Field(min_length=1,max_length=128)
    request_text: str = Field(min_length=1,max_length=2048)
    replaces_call_id: str = Field(default='',max_length=64)


class MonitorObserve(LeasedRequest):
    call_id: str = Field(min_length=1,max_length=64)
    state: Literal['started','succeeded','failed','uncertain']
    external_reference: str = Field(default='',max_length=512)
    selected_sources: list[str] = Field(default_factory=list,max_length=100)
    version_id: str = Field(default='',max_length=36)
    citation_ids: list[str] = Field(default_factory=list,max_length=100)
    summary: str = Field(default='',max_length=2048)


class MonitorFinish(LeasedRequest):
    cycle_id: str = Field(min_length=1,max_length=64)
    status: Literal['complete','no_material_update','partial','blocked']
    summary: str = Field(min_length=1,max_length=4096)
    result_reference: str = Field(default='',max_length=36)


class RunnerObservationSet(StrictRequest):
    data: dict = Field(description='Strict attributed external-runner observation. Reported installation/execution requires task/evidence references; it never installs a task or proves unattended execution.')
    idempotency_key: str = Field(min_length=1,max_length=128)


class ResultSave(LeasedRequest):
    data: dict = Field(json_schema_extra=input_schema('RESULT_INPUT'),description='Strict result with summary, changes, importance, assumptions, uncertainties, assessment_ref and bounded findings. Factual findings need actual ready immutable citation IDs; consequential conclusions require recorded contrary checks.')
    attempt_id: str = Field(default='',max_length=64)
    cycle_id: str = Field(default='',max_length=64)
    expected_revision: int = Field(default=0,ge=0,le=2147483646)


class ResultPublish(LeasedRequest):
    result_reference: str = Field(min_length=36,max_length=36)
    wiki_revision_ids: list[str] = Field(min_length=1,max_length=20)


class ReportPrepare(LeasedRequest):
    report_type: Literal['daily','weekly']
    local_date: str = Field(default='',max_length=10)
    amend: bool = False
    expected_revision: int = Field(default=0,ge=0,le=2147483646)


class ReportMember(LeasedRequest):
    report_reference: str = Field(min_length=36,max_length=36)
    data: dict = Field(json_schema_extra=input_schema('REPORT_MEMBER_INPUT'),description='Actual result_reference, included/deferred disposition, main/appendix location, actual wiki_revision_id, UTF-8 start_byte/end_byte, reason and assessment_ref. Deferred evidence remains due in later reports.')
    expected_revision: int = Field(default=0,ge=0,le=2147483646)


class ReportFinalize(LeasedRequest):
    report_reference: str = Field(min_length=36,max_length=36)
    wiki_revision_id: str = Field(min_length=36,max_length=36)


class ReportDelivery(LeasedRequest):
    report_reference: str = Field(min_length=36,max_length=36)
    channel: Literal['external_result','notification','human_read']
    state: Literal['started','succeeded','failed','uncertain']
    report_version: int | None = Field(default=None,ge=1)
    external_reference: str = Field(default='',max_length=512)
    evidence_reference: str = Field(default='',max_length=512)
    observation_source: Literal['operator_report','runner_report','sdk_simulation'] = 'runner_report'


class ReportView(StrictRequest):
    report: ObjectView | None
    members: list[ObjectView]
    more: bool
    deliveries: list[ObjectView]


class EventSet(StrictRequest):
    data: dict = Field(json_schema_extra=input_schema('EVENT_INPUT'),description='Project event definition. Partial dates cannot run refreshes; causal expansion priority survives urgency changes. Source reference is provenance, never authorization to expand scope.')
    expected_revision: int = Field(default=0,ge=0,le=2147483646)
    idempotency_key: str = Field(min_length=1,max_length=128)


class AuditStep(LeasedRequest):
    kind: Literal['configuration','wiki','claims','documents','chunks','queue','topics','sources']
    limit: int = Field(default=10,ge=1,le=10)


class SemanticSelect(LeasedRequest):
    refresh_changed: bool = False


class SemanticReview(LeasedRequest):
    selection_reference: str = Field(min_length=36,max_length=36)
    data: dict = Field(json_schema_extra=input_schema('SEMANTIC_INPUT'),description='Actual current-revision external semantic assessment. Complete the bounded selected batch only; global coverage is recorded separately. Proposed questions still require ordinary admission.')


class PeripheralArchive(LeasedRequest):
    topic_id: str = Field(min_length=1,max_length=128)
    summary: str = Field(min_length=8,max_length=4096)
    assessment_ref: str = Field(min_length=1,max_length=512)
    reference_ids: list[str] = Field(default_factory=list,max_length=100)


class ReleaseObservation(LeasedRequest):
    repository: Literal['Stell0/ns8-czero','Kabutojira/WikiPlant']
    installed_version: str = Field(min_length=1,max_length=64)
    metadata_version_id: str = Field(default='',max_length=36)
    error_code: str = Field(default='',max_length=128)


class ProjectDiagnostics(StrictRequest):
    project_id: str
    manifest_version: int
    last_successful_runs: dict[str,dict | None]
    connectors: list[dict]
    latest_daily_report: ObjectView | None
    errors: list[dict]
    errors_may_be_incomplete: bool
    structural_findings: int
    external_execution_verified: Literal[False]


class ProjectExportPage(StrictRequest):
    schema_version: Literal[1]
    project_id: str
    kind: str
    rows: list[dict]
    next_cursor: str
    watermarks: dict[str,int]
    limitations: list[str]


class ScheduleOccurrence(StrictRequest):
    latest_due: str
    local_cycle_date: str
    next_occurrence: str


class ProjectScheduleView(StrictRequest):
    project_id: str
    space_id: str
    manifest_version: int
    timezone: str
    server_now: str
    local_date: str
    desired: dict
    occurrences: dict[str,ScheduleOccurrence]
    execution_provider: Literal['external_agent']
    installed_by_c0: Literal[False]
    verification: str


class ProjectAgentPackageView(StrictRequest):
    schema_version: Literal[1]
    project_id: str
    space_id: str
    manifest_version: int
    mcp_url: str
    format: Literal['skill','plugin']
    name: str
    file_count: int = Field(ge=1,le=16)
    archive_sha256: str = Field(min_length=64,max_length=64)
    archive_base64: str = Field(max_length=350000)


def install_project_routes(app, database, auth, read_context, write_context):
    # Producer work can precede the immutable Core release. Old consumers stay
    # operational and explicitly reject project work until their pin is adopted.
    service = None
    if importlib.util.find_spec('czero_core.projects') is not None:
        from czero_core.projects import ProjectService
        service = ProjectService(database, auth.access if auth else None)
    app.state.projects = service
    operation = app.state.operation_catalog.bind

    def invoke(space_id, method, actor, **arguments):
        if auth is None:
            raise HTTPException(503, 'authentication_not_configured')
        if service is None or not hasattr(service, method):
            raise HTTPException(503, 'project_core_upgrade_required')
        try:
            return getattr(service.in_space(space_id), method)(actor, **arguments)
        except PermissionDenied:
            raise
        except ObjectConflict:
            raise HTTPException(409, 'project_conflict') from None
        except ObjectNotFound:
            raise HTTPException(404, 'project_not_found') from None
        except ValueError as error:
            if error.args==('content_superseded',):raise HTTPException(410,'content_superseded') from None
            raise HTTPException(422, 'invalid_project_request') from None

    @app.get('/api/v1/project', response_model=ObjectView)
    @operation('project_get', 'Read the selected protected project manifest and current configuration revision. Explicit space required; never falls back to Shared.', Role.READER, ObjectView, space_field='space_id')
    def get(space_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'get', context.actor)

    @app.post('/api/v1/project/initialize', response_model=ObjectView)
    @operation('project_initialize', 'Admin: initialize project state in an existing protected space using actual setup authorization. Replay returns its original receipt; creates no spaces, schedules or knowledge.', Role.ADMIN, ObjectView, read_only=False, space_field='space_id')
    def initialize(data: ProjectInitialize, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'initialize', context.actor, **data.model_dump())

    @app.put('/api/v1/project', response_model=ObjectView)
    @operation('project_configure', 'Admin: save a validated project configuration at its expected revision, retaining immutable configuration history. Does not grant space access or install schedules.', Role.ADMIN, ObjectView, read_only=False, space_field='space_id')
    def configure(data: ProjectConfigure, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'configure', context.actor, **data.model_dump())

    @app.post('/api/v1/project/topics', response_model=ObjectView)
    @operation('project_topic_set', 'Save a classified project topic with revision protection. Direct active user-anchor contribution is required. User anchor changes also require Admin scope and recorded affirmative tracking authorization. Peripheral topics are terminal.', Role.EDITOR, ObjectView, read_only=False, space_field='space_id')
    def topic(data: TopicSet, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'set_topic', context.actor, **data.model_dump())

    @app.get('/api/v1/project/records', response_model=ObjectsView)
    @operation('project_records_list', 'Read a bounded page of project records by versioned kind, including topic_v1 and immutable config_v1 history. A full page means coverage may be incomplete.', Role.READER, ObjectsView, space_field='space_id')
    def records(kind: str, space_id: UUID, limit: int = 50, offset: int = 0, descending: bool=False, context: RequestAccess = Depends(read_context)):
        if descending and (service is None or not hasattr(service,'monitor_begin')):raise HTTPException(503,'project_core_upgrade_required')
        options={'descending':True} if descending else {}
        return {'objects': invoke(space_id, 'list_records', context.actor, kind=kind, limit=limit, offset=offset,**options)}
    @app.put('/api/v1/project/connectors', response_model=ObjectView)
    @operation('project_connector_set', 'Admin: approve a finite source connector definition and its hash with actual user authorization. Explicit cross-space subscriptions recheck source-space authority. No fetch or schedule is executed.', Role.ADMIN, ObjectView, read_only=False, space_field='space_id')
    def connector(data: ConnectorSet, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'set_connector', context.actor, **data.model_dump())

    @app.get('/api/v1/project/source-status', response_model=ObjectView)
    @operation('project_source_status_get', 'Read the stored synchronization receipt for an exact connector/external part in this project. Ready extraction and verified publication are distinct.', Role.READER, ObjectView, space_field='space_id')
    def source_status(connector_id: str, external_id: str, space_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'source_status', context.actor, connector_id=connector_id, external_id=external_id)

    @app.put('/api/v1/project/source-status', response_model=ObjectView)
    @operation('project_source_status_set', 'Save a revision-safe synchronization receipt. Core checks enabled project connector and actual same-space immutable source/version/hash/extraction status. A queued version cannot be marked verified.', Role.EDITOR, ObjectView, read_only=False, space_field='space_id')
    def save_source_status(data: SourceStatusSet, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'save_source_status', context.actor, **data.model_dump())
    @app.put('/api/v1/project/connector-status', response_model=ObjectView)
    @operation('project_connector_status_set', 'Record bounded external connector coverage and counters at its current revision. Failed/partial collection preserves the last successful cursor. This is a collector observation, not proof that the whole external site was audited.', Role.EDITOR, ObjectView, read_only=False, space_field='space_id')
    def connector_status(data: ConnectorStatusSet, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'save_connector_status', context.actor, **data.model_dump())
    @app.put('/api/v1/project/source-snapshot',response_model=ObjectView)
    @operation('project_source_snapshot_set', 'Save the current complete original source snapshot from verified ordered part receipts. Core checks identities, offsets and combined text hash, atomically publishes current membership and removes superseded parts.', Role.EDITOR,ObjectView,read_only=False,space_field='space_id')
    def source_snapshot(data: SourceSnapshotSet,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'save_source_snapshot',context.actor,**data.model_dump(mode='json'))
    @app.get('/api/v1/project/record',response_model=ObjectView)
    @operation('project_record_get','Read one exact versioned project record by logical identity. Explicit protected space and current read authority are required.',Role.READER,ObjectView,space_field='space_id')
    def record(kind: str,identity: str,space_id: UUID,context: RequestAccess=Depends(read_context)):
        return invoke(space_id,'get_record',context.actor,kind=kind,identity=identity)

    @app.post('/api/v1/project/runs/claim',response_model=ProjectReceipt)
    @operation('project_run_claim','Claim or renew a logical project workflow at an acknowledged manifest version. No agent is executed. Persisted actor-bound leases and fencing reject concurrent owners; completed cycles remain complete.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def run_claim(data: WorkflowClaim,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'claim_run',context.actor,**data.model_dump())

    @app.post('/api/v1/project/runs/checkpoint',response_model=ProjectReceipt)
    @operation('project_run_checkpoint','Save an ordered phase checkpoint under a current fenced lease. References must exist in this space. PARTIAL/BLOCKED are durable incomplete observations, never successful execution proof.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def run_checkpoint(data: WorkflowCheckpoint,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'checkpoint_run',context.actor,**data.model_dump())

    @app.post('/api/v1/project/queue',response_model=ProjectReceipt)
    @operation('project_queue_admit','Apply the same scope, deduplication, lineage and capacity policy to every work origin. Returns admit/merge/defer_capacity/archive_candidate/reject_scope/needs_user_scope_decision with actual stored IDs. Does not execute research.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def queue_admit(data: QueueAdmission,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'admit',context.actor,**data.model_dump())

    @app.put('/api/v1/project/queue/priority',response_model=ProjectReceipt)
    @operation('project_queue_retune','Change current priority at its expected revision with a recorded reason. Urgency changes never reset causal expansion depth, attempts or lineage.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def queue_retune(data: QueueRetune,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'retune_queue',context.actor,**data.model_dump())

    @app.post('/api/v1/project/attempts/reserve',response_model=ProjectReceipt)
    @operation('project_attempt_reserve','Atomically select and reserve one eligible queued attempt before external research. Slots beyond the ordinary limit require priority zero. Resume the stored attempt after interruption; an uncertain invocation must be reconciled before another call.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def attempt_reserve(data: AttemptReserve,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'reserve',context.actor,**data.model_dump())

    @app.post('/api/v1/project/attempts/invocation',response_model=ProjectReceipt)
    @operation('project_invocation_set','Persist external invocation start/outcome separately from its consumed reservation. A returned result requires actual stored same-space resource identity and remains ACCEPTED_PENDING_MERGE. C0 cannot prove exactly-once external execution.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def invocation_set(data: InvocationSet,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'invocation',context.actor,**data.model_dump())

    @app.post('/api/v1/project/attempts/complete',response_model=ProjectReceipt)
    @operation('project_research_complete','Complete a result awaiting merge only after stored same-space commit references have been verified. Does not reserve another attempt, execute an agent or publish notifications.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def research_complete(data: ResearchComplete,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'complete_research',context.actor,**data.model_dump())
    @app.post('/api/v1/project/monitoring/begin',response_model=ProjectReceipt)
    @operation('project_monitor_begin','Start/resume this daily primary user-topic monitoring cycle under a current fenced lease. Caps and coverage survive retries. This consumes zero queue slots and performs no search.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def monitor_begin(data: MonitorBegin,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'monitor_begin',context.actor,**data.model_dump())

    @app.post('/api/v1/project/monitoring/reserve',response_model=ProjectReceipt)
    @operation('project_monitor_reserve','Reserve a bounded monitoring query or selected-source inspection before an external call. Reuse request_id to resume, retaining consumed counters and uncertain outcomes. Retries must explicitly name the failed request they replace.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def monitor_reserve(data: MonitorReserve,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'monitor_reserve',context.actor,**data.model_dump())

    @app.post('/api/v1/project/monitoring/observe',response_model=ProjectReceipt)
    @operation('project_monitor_observe','Record monitoring invocation start and an actual observed outcome separately from reservation. Source success requires matching ready immutable passage/version IDs; query success requires a real external result reference. Uncertain is not no-news.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def monitor_observe(data: MonitorObserve,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'monitor_observe',context.actor,**data.model_dump())

    @app.post('/api/v1/project/monitoring/finish',response_model=ProjectReceipt)
    @operation('project_monitor_finish','Finalize bounded monitoring coverage. Successful queries and inspection of every selected source are required for no_material_update. Failed/unresolved checks retain the successful watermark. Material results remain pending until evidence and Wiki commits are verified.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def monitor_finish(data: MonitorFinish,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'monitor_finish',context.actor,**data.model_dump())

    @app.get('/api/v1/project/schedule',response_model=ProjectScheduleView)
    @operation('project_schedule_get','Read desired external-agent daily/weekly IANA calendar occurrences and stable local cycle dates. DST gaps move forward and folds use the first occurrence. This does not install tasks or establish unattended authentication/execution.',Role.READER,ProjectScheduleView,space_field='space_id')
    def project_schedule(space_id: UUID,context: RequestAccess=Depends(read_context)):
        return invoke(space_id,'schedule',context.actor)

    @app.post('/api/v1/project/runner-observations',response_model=ProjectReceipt)
    @operation('project_runner_observe','Store an attributed operator/runner/simulation report with real task/evidence references. Reported execution must name a completed stored same-project run. This does not enable schedules, grant authority or verify the external host.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def runner_observation(data: RunnerObservationSet,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'observe_runner',context.actor,**data.model_dump())

    @app.get('/api/v1/project/agent-package',response_model=ProjectAgentPackageView)
    @operation('project_agent_package_get','Generate a private project-bound skill or plugin archive from current authorized configuration. Select format plugin only with the actual verified ChatGPT app ID. Generation is read-only and does not install a plugin, grant scopes or schedule tasks.',Role.READER,ProjectAgentPackageView,space_field='space_id')
    def agent_package(space_id: UUID,format: Literal['skill','plugin']='skill',chatgpt_app_id: str='',context: RequestAccess=Depends(read_context)):
        from czero_app.project_agent_packages import project_package
        stored=invoke(space_id,'get',context.actor)
        if not hasattr(service,'monitor_begin'):raise HTTPException(503,'project_core_upgrade_required')
        topics=[invoke(space_id,'get_record',context.actor,kind='topic_v1',identity=identity)
            for identity in stored['data']['manifest']['primary_topic_ids']]
        metadata=getattr(app.state,'connection_metadata',lambda:{'mcp_url':None})()
        if not metadata['mcp_url']:raise HTTPException(409,'project_connection_not_configured')
        try:result=project_package(metadata['mcp_url'],stored,topics,format=format,connection=chatgpt_app_id)
        except ValueError:raise HTTPException(422,'invalid_project_request') from None
        if invoke(space_id,'get',context.actor)['revision']!=stored['revision']:raise HTTPException(409,'project_conflict')
        for topic in topics:
            if invoke(space_id,'get_record',context.actor,kind='topic_v1',identity=topic['data']['topic_id'])['revision']!=topic['revision']:
                raise HTTPException(409,'project_conflict')
        return result
    @app.post('/api/v1/project/results',response_model=ProjectReceipt)
    @operation('project_result_save','Save a versioned research or monitoring result under its current lease. Core verifies ready immutable passages, claim revisions and bounded contrary checks. Partial findings remain incomplete; saving does not publish Wiki knowledge.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def result_save(data: ResultSave,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'save_result',context.actor,**data.model_dump())

    @app.post('/api/v1/project/results/publish',response_model=ProjectReceipt)
    @operation('project_result_publish','Verify a saved result against actual current same-space Wiki revisions and ready evidence. Wiki metadata must bind the project and result UUIDs. Markdown bodies contain Markdown; metadata remains separate. New revisions require explicit verification.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def result_publish(data: ResultPublish,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'publish_result',context.actor,**data.model_dump())

    @app.post('/api/v1/project/reports/prepare',response_model=ProjectReceipt)
    @operation('project_report_prepare','Prepare or resume one stable daily/weekly report draft. A report_publication run can report incomplete research coverage without rerunning research. Amendments require the current expected revision.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def report_prepare(data: ReportPrepare,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'prepare_report',context.actor,**data.model_dump())

    @app.post('/api/v1/project/reports/members',response_model=ProjectReceipt)
    @operation('project_report_member_set','Bind a result to its substantive saved report entry or explicit deferral. Core verifies actual Wiki revision, UTF-8 range and hashes. Appendices require saved references; deferred completed evidence remains due for later reporting.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def report_member(data: ReportMember,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'set_report_member',context.actor,**data.model_dump())

    @app.post('/api/v1/project/reports/finalize',response_model=ProjectReceipt)
    @operation('project_report_finalize','Save and read back the actual Wiki report revision after checking every completed unreported result is included or explicitly deferred. Coverage failures remain visible. SAVED proves persistence only, not external publication, notification or reading.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def report_finalize(data: ReportFinalize,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'finalize_report',context.actor,**data.model_dump())

    @app.get('/api/v1/project/reports',response_model=ReportView)
    @operation('project_report_get','Read the exact local-date report or latest saved daily/weekly report with a pinned Wiki identity that may expire, bounded membership and independent delivery observations. Follow pagination before claiming complete membership.',Role.READER,ReportView,space_field='space_id')
    def report_get(space_id: UUID,report_type: Literal['daily','weekly']='daily',local_date: str='',limit: int=50,offset: int=0,context: RequestAccess=Depends(read_context)):
        return invoke(space_id,'get_report',context.actor,report_type=report_type,local_date=local_date,limit=limit,offset=offset)

    @app.post('/api/v1/project/reports/delivery',response_model=ProjectReceipt)
    @operation('project_report_delivery_observe','Reserve external publication before its call, then record an attributed observed outcome with actual evidence. Unknown outcomes require reconciliation; retries reuse the saved report. Notification and human reading require separate observations and are never inferred.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def report_delivery(data: ReportDelivery,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'observe_report_delivery',context.actor,**data.model_dump())
    @app.put('/api/v1/project/events',response_model=ObjectView)
    @operation('project_event_set','Save a versioned project calendar event or bounded recurring refresh definition. Dates are distinct from source publication/retrieval. No investigation or ongoing scope is authorized merely by saving an event.',Role.EDITOR,ObjectView,read_only=False,space_field='space_id')
    def event_set(data: EventSet,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'set_event',context.actor,**data.model_dump())

    @app.post('/api/v1/project/maintenance/audit',response_model=ProjectReceipt)
    @operation('project_audit_step','Inspect a bounded deterministic structural slice under a weekly/maintenance lease. Actual findings and cursors persist; PARTIAL is not a full audit. External URLs and semantic truth are not checked.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def audit_step(data: AuditStep,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'audit_step',context.actor,**data.model_dump())

    @app.post('/api/v1/project/maintenance/semantic/select',response_model=ProjectReceipt)
    @operation('project_semantic_select','Reserve/resume a bounded risk-and-rotation batch of actual Wiki revisions. Use refresh_changed explicitly after stale-revision conflicts. Selection performs no semantic reasoning or model execution.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def semantic_select(data: SemanticSelect,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'semantic_select',context.actor,**data.model_dump())

    @app.post('/api/v1/project/maintenance/semantic/review',response_model=ProjectReceipt)
    @operation('project_semantic_review','Save an attributed semantic assessment for one reserved exact current Wiki revision. Stale revisions reject and never inherit verification. Rotation advances only after the selected batch is reviewed; global coverage remains explicit.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def semantic_review(data: SemanticReview,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'semantic_review',context.actor,**data.model_dump())

    @app.post('/api/v1/project/maintenance/archive',response_model=ProjectReceipt)
    @operation('project_peripheral_archive','Archive an expired peripheral topic only at a distinct future weekly checkpoint. Save compact summary, assessment and actual ready references while preserving topic history, research lineage and evidence. No reactivation or deletion occurs.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def peripheral_archive(data: PeripheralArchive,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'archive_peripheral',context.actor,**data.model_dump())

    @app.post('/api/v1/project/maintenance/releases',response_model=ProjectReceipt)
    @operation('project_release_observe','Record bounded workflow release observations from actual ready saved metadata, or explicit retrieval failure. Failed/stale/incomplete data cannot mean up-to-date. Bounded retry and changed published identities persist; no runtime update is installed.',Role.EDITOR,ProjectReceipt,read_only=False,space_field='space_id')
    def release_observe(data: ReleaseObservation,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'observe_release',context.actor,**data.model_dump())

    @app.get('/api/v1/project/diagnostics',response_model=ProjectDiagnostics)
    @operation('project_diagnostics_get','Read current project status: actual successful daily/weekly runs, latest saved report, current connector-definition coverage, bounded incomplete work and structural finding counts. Stored observations do not verify an external agent or unattended execution.',Role.READER,ProjectDiagnostics,space_field='space_id')
    def diagnostics(space_id: UUID,context: RequestAccess=Depends(read_context)):
        return invoke(space_id,'diagnostics',context.actor)

    @app.get('/api/v1/project/export',response_model=ProjectExportPage)
    @operation('project_export_get','Read one bounded page from the fixed project interchange catalog, including current content identities and explicit current text fragments. Expired exact fragments return content_superseded. Select the exact protected space and follow returned cursors. Read-only export excludes permissions, credentials, jobs and server file paths; verify all hashes and change watermarks before accepting a local export.',Role.READER,ProjectExportPage,space_field='space_id')
    def export_get(space_id: UUID,kind: str,after: str='',limit: int=50,resource_id: str='',context: RequestAccess=Depends(read_context)):
        return invoke(space_id,'export_page',context.actor,kind=kind,after=after,limit=limit,resource_id=resource_id)
    return service
