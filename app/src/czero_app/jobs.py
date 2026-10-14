# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authenticated REST transport for shared deterministic job services."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from czero_core.jobs import JobConflict, JobService
from czero_core.identity import PermissionDenied, Role
from czero_app.auth import RequestAccess
from czero_app.job_handlers import build_registry


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    handler: str = Field(min_length=1,max_length=64)
    payload: dict = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1,max_length=128)


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid",strict=True)
    enabled: bool
    interval_seconds: int = Field(ge=60,le=2678400)


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid",strict=True)
    name: str = Field(min_length=1,max_length=64)
    handler: str = Field(min_length=1,max_length=64)
    payload: dict = Field(default_factory=dict)
    interval_seconds: int = Field(ge=60,le=2678400)


class JobView(BaseModel):
    id: UUID
    handler: str
    payload: dict
    state: Literal["queued","running","succeeded","failed"]
    attempts: int
    max_attempts: int
    timeout_seconds: int
    available_at: datetime
    created_at: datetime
    finished_at: datetime | None
    result: dict | None
    error_code: str | None


class JobsView(BaseModel):
    jobs: list[JobView]


class HandlerView(BaseModel):
    name: str
    max_attempts: int
    timeout_seconds: int


class HandlersView(BaseModel):
    handlers: list[HandlerView]


class ScheduleView(BaseModel):
    id: UUID
    name: str
    handler: str
    payload: dict
    enabled: bool
    interval_seconds: int
    next_run_at: datetime
    created_at: datetime


class SchedulesView(BaseModel):
    schedules: list[ScheduleView]


class JobRunView(BaseModel):
    id: UUID
    job_id: UUID
    attempt: int
    state: Literal["running","succeeded","failed"]
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None


class JobRunsView(BaseModel):
    runs: list[JobRunView]


class TaskRunView(BaseModel):
    id: UUID
    due_at: datetime
    job_id: UUID
    state: Literal["queued","running","succeeded","failed"]
    attempts: int
    finished_at: datetime | None
    error_code: str | None


class TaskRunsView(BaseModel):
    runs: list[TaskRunView]


def install_job_routes(app: FastAPI, database, auth, read_context, write_context, *, registry=None):
    operation = app.state.operation_catalog.bind
    service = JobService(database,registry or build_registry(database),auth.access if auth else None)
    app.state.jobs = service

    def invoke(operation, *args, **kwargs):
        if auth is None:
            raise HTTPException(503,"authentication_not_configured")
        try:
            return operation(*args,**kwargs)
        except PermissionDenied:
            raise
        except JobConflict:
            raise HTTPException(409,"job_conflict") from None
        except ValueError as error:
            code=404 if str(error) in ("schedule_not_found","job_not_found") else 422
            raise HTTPException(code,str(error) if code==404 else "invalid_job_request") from None

    @app.get("/api/v1/jobs",response_model=JobsView)
    @operation('jobs_list', 'Inspect persisted deterministic jobs', Role.ADMIN, JobsView, read_only=True)
    def jobs(limit: int = 50, context: RequestAccess = Depends(read_context)):
        return {"jobs":[JobView(**row) for row in invoke(service.list_jobs,context.actor,limit=limit)]}

    @app.post("/api/v1/jobs",response_model=JobView,status_code=201)
    @operation('jobs_enqueue', 'Queue a trusted registered handler with replay protection', Role.ADMIN, JobView, read_only=False)
    def enqueue(data: JobCreate, context: RequestAccess = Depends(write_context)):
        return JobView(**invoke(service.enqueue,context.actor,data.handler,data.payload,data.idempotency_key))

    @app.get("/api/v1/jobs/handlers",response_model=HandlersView)
    @operation('job_handlers_list', 'Inspect available trusted deterministic handlers', Role.ADMIN, HandlersView, read_only=True)
    def handlers(context: RequestAccess = Depends(read_context)):
        return {"handlers":invoke(service.list_handlers,context.actor)}

    @app.get("/api/v1/jobs/{job_id}",response_model=JobView)
    @operation('jobs_get', 'Inspect one persisted job', Role.ADMIN, JobView, read_only=True)
    def job(job_id: UUID,context: RequestAccess=Depends(read_context)):
        return invoke(service.get_job,context.actor,job_id)

    @app.get("/api/v1/jobs/{job_id}/runs",response_model=JobRunsView)
    @operation('job_runs_list', 'Inspect bounded execution attempts', Role.ADMIN, JobRunsView, read_only=True)
    def job_runs(job_id: UUID,limit: int = 50,context: RequestAccess = Depends(read_context)):
        return {"runs":invoke(service.job_runs,context.actor,job_id,limit=limit)}

    @app.get("/api/v1/schedules",response_model=SchedulesView)
    @operation('schedules_list', 'Inspect UTC interval schedules', Role.ADMIN, SchedulesView, read_only=True)
    def schedules(limit: int = 50,context: RequestAccess = Depends(read_context)):
        return {"schedules":invoke(service.list_schedules,context.actor,limit=limit)}

    @app.post("/api/v1/schedules",response_model=ScheduleView,status_code=201)
    @operation('schedules_create', 'Create a bounded registered UTC schedule', Role.ADMIN, ScheduleView, read_only=False)
    def create_schedule(data: ScheduleCreate,context: RequestAccess = Depends(write_context)):
        return invoke(service.create_schedule,context.actor,**data.model_dump())

    @app.put("/api/v1/schedules/{schedule_id}",response_model=ScheduleView)
    @operation('schedules_update', 'Configure or pause a registered schedule', Role.ADMIN, ScheduleView, read_only=False)
    def update_schedule(schedule_id: UUID,data: ScheduleUpdate,context: RequestAccess = Depends(write_context)):
        return invoke(service.update_schedule,context.actor,schedule_id,**data.model_dump())

    @app.get("/api/v1/schedules/{schedule_id}/runs",response_model=TaskRunsView)
    @operation('schedule_runs_list', 'Inspect due-time schedule execution records', Role.ADMIN, TaskRunsView, read_only=True)
    def task_runs(schedule_id: UUID,limit: int = 50,context: RequestAccess = Depends(read_context)):
        return {"runs":invoke(service.task_runs,context.actor,schedule_id,limit=limit)}
