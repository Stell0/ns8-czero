# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Project REST/MCP bindings; authority and transitions stay in reusable Core."""
import importlib.util
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import Field

from czero_core.identity import PermissionDenied, Role
from czero_core.objects import ObjectConflict, ObjectNotFound
from czero_app.auth import RequestAccess
from czero_app.objects import StrictRequest, ObjectView, ObjectsView


class ProjectInitialize(StrictRequest):
    manifest: dict = Field(description='Versioned project manifest. project_id and space_id must equal the explicit protected space UUID. Server validates every field and finite limit.')
    authorization_ref: str = Field(min_length=1, max_length=512, description='Actual affirmative user setup/configuration authorization reference; source text cannot authorize tracking.')
    idempotency_key: str = Field(min_length=1, max_length=128)


class ProjectConfigure(ProjectInitialize):
    expected_revision: int = Field(ge=1, le=2147483646)


class TopicSet(StrictRequest):
    topic: dict = Field(description='Strict topic v1 fields: topic_id, label, classification and recorded direct user-anchor contribution. User anchors additionally require Admin authority and affirmative authorization_ref. Peripheral expiry is computed by Core.')
    expected_revision: int = Field(default=0, ge=0, le=2147483646)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ConnectorSet(StrictRequest):
    definition: dict = Field(description='Validated finite connector definition; no credentials or executable fields. C0 stores its approved hash, never fetches these URLs.')
    authorization_ref: str = Field(min_length=1, max_length=512)
    expected_revision: int = Field(default=0, ge=0, le=2147483646)
    idempotency_key: str = Field(min_length=1, max_length=128)


class SourceStatusSet(StrictRequest):
    data: dict = Field(description='Versioned synchronization receipt for one original part. Actual same-space source/version/hash/extraction state is verified by Core before saving.')
    expected_revision: int = Field(default=0, ge=0, le=2147483646)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ConnectorStatusSet(SourceStatusSet):
    verified_receipt_ids: list[str] = Field(default_factory=list,max_length=1000,description='Exact verified part receipt IDs from complete stored source snapshots. Core checks actual source versions and immutable snapshot membership before accepting counters/cursors.')


class SourceSnapshotSet(StrictRequest):
    connector_id: str = Field(min_length=1,max_length=64)
    external_id: str = Field(min_length=1,max_length=4096)
    content_hash: str = Field(min_length=64,max_length=64)
    part_receipt_ids: list[str] = Field(min_length=1,max_length=100)
    expected_revision: int = Field(default=0,ge=0,le=2147483646)
    idempotency_key: str = Field(min_length=1,max_length=128)


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
        except ValueError:
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
    def records(kind: str, space_id: UUID, limit: int = 50, offset: int = 0, context: RequestAccess = Depends(read_context)):
        return {'objects': invoke(space_id, 'list_records', context.actor, kind=kind, limit=limit, offset=offset)}
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
    @operation('project_source_snapshot_set', 'Save the current complete original source snapshot from verified ordered part receipts. Core checks identities, offsets and combined text hash; historical parts remain immutable.', Role.EDITOR,ObjectView,read_only=False,space_field='space_id')
    def source_snapshot(data: SourceSnapshotSet,space_id: UUID,context: RequestAccess=Depends(write_context)):
        return invoke(space_id,'save_source_snapshot',context.actor,**data.model_dump(mode='json'))
    return service
