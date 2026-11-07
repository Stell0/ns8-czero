# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Optional thin coordinator transport over the installed Core capability."""
import importlib.util
from copy import deepcopy
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field

from czero_app.auth import RequestAccess
from czero_app.objects import StrictRequest
from czero_core.identity import Role


def schema(name):
    if importlib.util.find_spec('czero_core.compilation_schema') is None:
        return {}
    from czero_core import compilation_schema
    return deepcopy(getattr(compilation_schema, name))


def publication_schema(name):
    if importlib.util.find_spec('czero_core.compilation_plan_schema') is None:
        return {}
    from czero_core import compilation_plan_schema
    return deepcopy(getattr(compilation_plan_schema, name))


class TargetSelections(StrictRequest):
    targets: list[dict] = Field(min_length=1,max_length=25,
        json_schema_extra={'items':publication_schema('TARGET_SELECTION')})


class PlanValidate(StrictRequest):
    data: dict = Field(json_schema_extra=publication_schema('VALIDATE'))


class PlanApply(StrictRequest):
    data: dict = Field(json_schema_extra=publication_schema('APPLY'))
    idempotency_key: str = Field(min_length=1, max_length=128)


class PlanVerify(PlanApply):
    data: dict = Field(json_schema_extra=publication_schema('VERIFY'))


class PolicySet(StrictRequest):
    data: dict = Field(json_schema_extra=schema('POLICY'))
    expected_revision: int = Field(ge=0, le=2147483646)
    authorization_ref: str = Field(default='', max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)


class Proposal(StrictRequest):
    data: dict = Field(json_schema_extra=schema('PROPOSAL'))
    idempotency_key: str = Field(min_length=1, max_length=128)


class RunClaim(Proposal):
    data: dict = Field(json_schema_extra=schema('CLAIM'))


class RunCheckpoint(Proposal):
    data: dict = Field(json_schema_extra=schema('CHECKPOINT'))


class BindingSelections(StrictRequest):
    selections: list[dict] = Field(min_length=1, max_length=3,
        json_schema_extra={'items': schema('SOURCE_SELECTION')})


def install(app, database, auth, read_context, write_context):
    app.state.compilation = None
    if importlib.util.find_spec('czero_core.compilation') is None:
        return  # Released consumers must not advertise unsupported operations.
    from czero_core.compilation import (CompilationService, CompilationConflict,
        CompilationNotFound, CompilationNotReady, CompilationDisabled)
    from czero_core.current_content import ContentSuperseded
    from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound
    service = CompilationService(database, auth.access if auth else None)
    app.state.compilation = service
    operation = app.state.operation_catalog.bind

    def invoke(space_id, method, actor, **arguments):
        if auth is None:
            raise HTTPException(503, 'authentication_not_configured')
        try:
            return getattr(service.in_space(space_id), method)(actor, **arguments)
        except CompilationDisabled:
            raise HTTPException(403, 'compilation_disabled') from None
        except KnowledgeConflict:
            raise HTTPException(409, 'compilation_conflict') from None
        except KnowledgeNotFound:
            raise HTTPException(404, 'compilation_not_found') from None
        except CompilationNotReady:
            raise HTTPException(409, 'compilation_source_not_ready') from None
        except ContentSuperseded:
            raise HTTPException(410, 'content_superseded') from None
        except ValueError:
            raise HTTPException(422, 'invalid_compilation_request') from None

    previous_validation = app.exception_handlers[RequestValidationError]
    @app.exception_handler(RequestValidationError)
    async def validation(request, error):
        if '/api/v1/compilation/' in request.url.path:
            return JSONResponse({'detail': 'invalid_compilation_request'}, status_code=422)
        return await previous_validation(request, error)

    @app.get('/api/v1/compilation/policy', response_model=dict)
    @operation('compilation_policy_get', 'Read selected-space compiler policy. Absent policy is disabled and creates no rows.', Role.READER, dict, space_field='space_id')
    def policy_get(space_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'policy', context.actor)

    @app.put('/api/v1/compilation/policy', response_model=dict)
    @operation('compilation_policy_set', 'Admin: replace bounded compiler policy at the expected revision. Enabling requires actual operator authorization reference. Installs no scheduler and publishes no knowledge.', Role.ADMIN, dict, read_only=False, space_field='space_id')
    def policy_set(data: PolicySet, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'configure', context.actor, **data.model_dump())

    @app.post('/api/v1/compilation/source-bindings', response_model=dict)
    @operation('compilation_source_bindings_get', 'Read exact current original source/chunk bindings for a bounded selection. Metadata only, no writes. Expired citations return 410; never substitute another generation.', Role.READER, dict, space_field='space_id')
    def bindings(data: BindingSelections, space_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'source_bindings', context.actor, **data.model_dump())

    @app.post('/api/v1/compilation/proposals', response_model=dict)
    @operation('compilation_propose', 'Editor: queue a bounded source-backed improvement under enabled policy; deduplicates stable targets and exact inputs. No raw queries, answers or prompts. Contradictions remain held. Does not compile or publish.', Role.EDITOR, dict, read_only=False, space_field='space_id')
    def propose(data: Proposal, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'propose', context.actor, **data.model_dump())

    @app.get('/api/v1/compilation/tasks', response_model=dict)
    @operation('compilation_tasks_list', 'Read bounded selected-space proposal metadata and keyset recovery cursor. Does not lease or process work.', Role.READER, dict, space_field='space_id')
    def tasks(space_id: UUID, state: str | None = None, topic_key: str | None = None,
              limit: int = Query(default=50, ge=1, le=100), after: UUID | None = None,
              context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'list_tasks', context.actor, state=state, topic_key=topic_key, limit=limit, after=after)

    @app.get('/api/v1/compilation/tasks/{task_id}', response_model=dict)
    @operation('compilation_tasks_get', 'Read one exact selected-space proposal, revisions and recovery identities.', Role.READER, dict, space_field='space_id')
    def task(task_id: UUID, space_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'get_task', context.actor, task_id=task_id)

    @app.post('/api/v1/compilation/runs/claim', response_model=dict)
    @operation('compilation_run_claim', 'Editor: claim/renew/recover one bounded logical run under enabled policy, retaining actor/owner/fence, budgets and retry history. No model execution. Keep actual returned revisions; stale replay is denied.', Role.EDITOR, dict, read_only=False, space_field='space_id')
    def claim(data: RunClaim, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'claim_run', context.actor, **data.model_dump())

    @app.post('/api/v1/compilation/runs/checkpoint', response_model=dict)
    @operation('compilation_run_checkpoint', 'Editor: record a fixed metadata-only task/model-budget/run observation at live fence and expected revisions. Reserve before external calls; reconcile uncertainty. Cannot publish or mark M2 verification.', Role.EDITOR, dict, read_only=False, space_field='space_id')
    def checkpoint(data: RunCheckpoint, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'checkpoint', context.actor, **data.model_dump())

    @app.get('/api/v1/compilation/status', response_model=dict)
    @operation('compilation_status_get', 'Read actual bounded compiler progress, stale observations, budgets and lease validity. No writes; bounded completion is not complete corpus coverage or verified compilation.', Role.READER, dict, space_field='space_id')
    def status(space_id: UUID, run_id: UUID | None = None, limit: int = Query(default=10, ge=1, le=100),
               context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'status', context.actor, run_id=run_id, limit=limit)

    @app.get('/api/v1/compilation/dependencies', response_model=dict)
    @operation('compilation_dependencies_list', 'Read indexed selected-space source-to-target observations and current identity freshness. Requires source or target filter; observed support is not verified knowledge.', Role.READER, dict, space_field='space_id')
    def dependencies(space_id: UUID, logical_document_id: UUID | None = None, target_id: UUID | None = None,
                     limit: int = Query(default=50, ge=1, le=100), after: UUID | None = None,
                     context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'list_dependencies', context.actor, logical_document_id=logical_document_id,
            target_id=target_id, limit=limit, after=after)

    if importlib.util.find_spec('czero_core.compilation_plans') is None:
        return  # M1 Core remains a fully supported coordination-only consumer.

    @app.post('/api/v1/compilation/target-bindings', response_model=dict)
    @operation('compilation_target_bindings_get', 'Read current selected-space target identity hashes and compiler ownership for a bounded selection. Metadata only; read actual content separately and compare revisions. No local hashing tool or policy enablement required. No writes.', Role.READER, dict, space_field='space_id')
    def target_bindings(data: TargetSelections, space_id: UUID, context: RequestAccess = Depends(read_context)):
        return invoke(space_id, 'target_bindings', context.actor, **data.model_dump())

    @app.post('/api/v1/compilation/plans/validate', response_model=dict)
    @operation('compilation_plan_validate', 'Editor: dry-run one closed source-backed plan under enabled policy and a live fence. Persists no content or progress. Returns plan hash and review eligibility; does not prove semantic truth or grant publication authority.', Role.EDITOR, dict, space_field='space_id', required_scope='c0:write')
    def plan_validate(data: PlanValidate, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'validate_plan', context.actor, **data.model_dump())

    @app.post('/api/v1/compilation/apply', response_model=dict)
    @operation('compilation_apply', 'Editor: atomically publish a validated exact plan and source dependencies under current policy, revisions and fence. Queue-only, authored edits and uncertain/contrary plans require exact-plan approval. Returns applied_pending_verify, never verified truth. Preserve replay key after uncertain response.', Role.EDITOR, dict, read_only=False, space_field='space_id')
    def plan_apply(data: PlanApply, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'apply_plan', context.actor, **data.model_dump())

    @app.post('/api/v1/compilation/verify', response_model=dict)
    @operation('compilation_verify', 'Editor: record fresh target/annotation/original readback matching an actual applied outcome at the live fence. Completes matching work only; does not promote verification status or establish complete corpus coverage. Reconcile edits, expired citations and lost fences.', Role.EDITOR, dict, read_only=False, space_field='space_id')
    def plan_verify(data: PlanVerify, space_id: UUID, context: RequestAccess = Depends(write_context)):
        return invoke(space_id, 'verify_plan', context.actor, **data.model_dump())
