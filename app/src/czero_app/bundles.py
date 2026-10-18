# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Typed single-space content bundles; Core owns execution and authority."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_serializer
from starlette.responses import JSONResponse

from czero_core.bundles import KnowledgeBundleService
from czero_core.identity import PermissionDenied, Role
from czero_core.knowledge import EvidenceNotReady
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound
from czero_app.annotations import ApplicabilityValue, VerificationValue, AnnotationView, Kind, Namespace, UTCTime
from czero_app.auth import RequestAccess
from czero_app.knowledge import PageView, PageSummary, EntityView, ClaimView, RelationView, LinkView, RemovedView
from czero_app.objects import ObjectView, DeletedView as ObjectDeletedView


class BundleResultReference(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    step: int = Field(alias='$result', ge=0, lt=25)
    path: Literal['id','revision','content.id','content.number']

    @model_serializer
    def reference(self):
        # Preserve the reserved wire spelling through REST's model round trip.
        return {'$result':self.step,'path':self.path}


Identifier = Annotated[UUID, Field(strict=False)] | BundleResultReference
Revision = Annotated[int, Field(strict=True, ge=1, lt=2147483647)] | BundleResultReference
AnnotationRevision = Annotated[int, Field(strict=True, ge=0, lt=2147483646)] | BundleResultReference


class BundleArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)

    @model_serializer(mode='wrap')
    def supplied_fields(self, handler):
        value = handler(self)
        return {key:value[key] for key in self.model_fields_set}


class BundleTarget(BundleArguments):
    kind: Kind
    id: Identifier
    revision: Revision


class BundleChunkReference(BundleArguments):
    kind: Literal['chunk']
    id: Identifier


class BundleApplicability(ApplicabilityValue):
    supersedes: list[BundleTarget] | None = Field(default=None, max_length=32)
    source_references: list[BundleChunkReference] | None = Field(default=None, max_length=32)


class BundleVerification(VerificationValue):
    source_references: list[BundleChunkReference] | None = Field(default=None, max_length=32)


class BundleWikiUpsertArguments(BundleArguments):
    slug: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(repr=False, max_length=131072)
    metadata: dict[str, JsonValue] | None = Field(default=None, repr=False)
    expected_revision: Revision | None = None


class BundleWikiArchiveArguments(BundleArguments):
    page_id: Identifier
    expected_revision: Revision


class BundleEntityCreateArguments(BundleArguments):
    kind: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    aliases: list[str] | None = Field(default=None, max_length=15)
    metadata: dict[str, JsonValue] | None = Field(default=None, repr=False)


class BundleEntityUpdateArguments(BundleArguments):
    entity_id: Identifier
    label: str = Field(min_length=1, max_length=128)
    expected_revision: Revision
    metadata: dict[str, JsonValue] | None = Field(default=None, repr=False)


class BundleEntityArchiveArguments(BundleArguments):
    entity_id: Identifier
    expected_revision: Revision


class BundleEntityAliasArguments(BundleEntityArchiveArguments):
    value: str = Field(min_length=1, max_length=128)


class BundleEntityLinkArguments(BundleArguments):
    entity_id: Identifier
    target_kind: Literal['object','page','source','document','chunk']
    target_id: Identifier


class BundleEntityUnlinkArguments(BundleArguments):
    entity_id: Identifier
    link_id: Identifier


class BundleClaimCreateArguments(BundleArguments):
    entity_id: Identifier
    predicate: str = Field(min_length=1, max_length=64)
    value: dict[str, JsonValue] = Field(repr=False)
    evidence_chunk_ids: list[Identifier] = Field(min_length=1, max_length=32)
    page_id: Identifier | None = None
    metadata: dict[str, JsonValue] | None = Field(default=None, repr=False)
    valid_from: UTCTime | None = None
    valid_to: UTCTime | None = None


class BundleClaimUpdateArguments(BundleArguments):
    claim_id: Identifier
    expected_revision: Revision
    metadata: dict[str, JsonValue] = Field(repr=False)
    evidence_chunk_ids: list[Identifier] | None = Field(default=None, min_length=1, max_length=32)


class BundleClaimArchiveArguments(BundleArguments):
    claim_id: Identifier
    expected_revision: Revision


class BundleRelationCreateArguments(BundleArguments):
    source_id: Identifier
    target_id: Identifier
    kind: str = Field(min_length=1, max_length=64)
    metadata: dict[str, JsonValue] | None = Field(default=None, repr=False)


class BundleRelationUpdateArguments(BundleArguments):
    relation_id: Identifier
    expected_revision: Revision
    metadata: dict[str, JsonValue] = Field(repr=False)
    deleted: bool = False


class BundleObjectCreateArguments(BundleArguments):
    type_name: str = Field(min_length=1, max_length=64)
    data: dict[str, JsonValue] = Field(repr=False)
    tags: list[str] | None = Field(default=None, max_length=32)


class BundleObjectUpdateArguments(BundleArguments):
    object_id: Identifier
    data: dict[str, JsonValue] = Field(repr=False)
    expected_revision: Revision
    tags: list[str] | None = Field(default=None, max_length=32)


class BundleObjectDeleteArguments(BundleArguments):
    object_id: Identifier
    expected_revision: Revision


class BundleAnnotationUpdateArguments(BundleArguments):
    target: BundleTarget
    namespace: Namespace
    value: BundleApplicability | BundleVerification = Field(repr=False)
    expected_revision: AnnotationRevision


class BundleStepBase(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class BundleWikiUpsertStep(BundleStepBase):
    operation: Literal['wiki.upsert']
    arguments: BundleWikiUpsertArguments


class BundleWikiArchiveStep(BundleStepBase):
    operation: Literal['wiki.archive']
    arguments: BundleWikiArchiveArguments


class BundleEntityCreateStep(BundleStepBase):
    operation: Literal['entity.create']
    arguments: BundleEntityCreateArguments


class BundleEntityUpdateStep(BundleStepBase):
    operation: Literal['entity.update']
    arguments: BundleEntityUpdateArguments


class BundleEntityArchiveStep(BundleStepBase):
    operation: Literal['entity.archive']
    arguments: BundleEntityArchiveArguments


class BundleEntityAliasStep(BundleStepBase):
    operation: Literal['entity.alias']
    arguments: BundleEntityAliasArguments


class BundleEntityLinkStep(BundleStepBase):
    operation: Literal['entity.link']
    arguments: BundleEntityLinkArguments


class BundleEntityUnlinkStep(BundleStepBase):
    operation: Literal['entity.unlink']
    arguments: BundleEntityUnlinkArguments


class BundleClaimCreateStep(BundleStepBase):
    operation: Literal['claim.create']
    arguments: BundleClaimCreateArguments


class BundleClaimUpdateStep(BundleStepBase):
    operation: Literal['claim.update']
    arguments: BundleClaimUpdateArguments


class BundleClaimArchiveStep(BundleStepBase):
    operation: Literal['claim.archive']
    arguments: BundleClaimArchiveArguments


class BundleRelationCreateStep(BundleStepBase):
    operation: Literal['relation.create']
    arguments: BundleRelationCreateArguments


class BundleRelationUpdateStep(BundleStepBase):
    operation: Literal['relation.update']
    arguments: BundleRelationUpdateArguments


class BundleObjectCreateStep(BundleStepBase):
    operation: Literal['object.create']
    arguments: BundleObjectCreateArguments


class BundleObjectUpdateStep(BundleStepBase):
    operation: Literal['object.update']
    arguments: BundleObjectUpdateArguments


class BundleObjectDeleteStep(BundleStepBase):
    operation: Literal['object.delete']
    arguments: BundleObjectDeleteArguments


class BundleAnnotationUpdateStep(BundleStepBase):
    operation: Literal['annotation.update']
    arguments: BundleAnnotationUpdateArguments


BundleStep = Annotated[BundleWikiUpsertStep | BundleWikiArchiveStep | BundleEntityCreateStep | BundleEntityUpdateStep |
    BundleEntityArchiveStep | BundleEntityAliasStep | BundleEntityLinkStep | BundleEntityUnlinkStep | BundleClaimCreateStep |
    BundleClaimUpdateStep | BundleClaimArchiveStep | BundleRelationCreateStep | BundleRelationUpdateStep | BundleObjectCreateStep |
    BundleObjectUpdateStep | BundleObjectDeleteStep | BundleAnnotationUpdateStep, Field(discriminator='operation')]


class BundleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    space_id: UUID | None = None
    operations: list[BundleStep] = Field(min_length=1, max_length=25, repr=False,
        description='One space, at most 25 trusted content writes and 262144 aggregate JSON bytes. Only earlier result UUID/revision references are allowed.')
    idempotency_key: str = Field(min_length=1, max_length=128,
        description='One receipt for the whole bundle. Unchanged retry returns its original snapshot; changed payloads conflict.')


BundleRecord = (PageView | PageSummary | EntityView | ClaimView | RelationView |
                LinkView | RemovedView | ObjectView | ObjectDeletedView | AnnotationView)


class BundleResult(BaseModel):
    space_id: UUID
    results: list[BundleRecord] = Field(min_length=1,max_length=25)


_RESULT_MODELS = {
    'wiki.upsert':PageView, 'wiki.archive':PageSummary,
    'entity.create':EntityView, 'entity.update':EntityView,
    'entity.archive':EntityView, 'entity.alias':EntityView,
    'entity.link':LinkView, 'entity.unlink':RemovedView,
    'claim.create':ClaimView, 'claim.update':ClaimView, 'claim.archive':ClaimView,
    'relation.create':RelationView, 'relation.update':RelationView,
    'object.create':ObjectView, 'object.update':ObjectView, 'object.delete':ObjectDeletedView,
    'annotation.update':AnnotationView,
}


_PATH = '/api/v1/knowledge/bundles/apply'


def install_bundle_routes(app, database, auth, write_context):
    service = KnowledgeBundleService(database, auth.access if auth else None)
    app.state.bundles = service
    operation = app.state.operation_catalog.bind
    previous_validation = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def bundle_validation(request, error):
        if request.url.path.endswith(_PATH):
            return JSONResponse({'detail':'invalid_knowledge_request'},status_code=422)
        return await previous_validation(request,error)

    @app.post(_PATH, response_model=BundleResult)
    @operation('knowledge_bundle_apply', 'Publish 1–25 content mutations atomically in one space. Use expected revisions and ready evidence; earlier result references are allowed. Retry returns the original whole snapshot. No files, jobs, schemas, grants or external I/O.',
        Role.EDITOR, BundleResult, read_only=False, space_field='data.space_id')
    def apply(data: BundleRequest, context: RequestAccess = Depends(write_context)):
        if auth is None:
            raise HTTPException(503,'authentication_not_configured')
        selected = service.in_space(data.space_id) if data.space_id is not None else service
        try:
            result = selected.apply(context.actor,
                [step.model_dump(mode='json',exclude_unset=True) for step in data.operations],
                idempotency_key=data.idempotency_key)
        except PermissionDenied:
            raise
        except EvidenceNotReady:
            raise HTTPException(409,'evidence_not_ready') from None
        except KnowledgeConflict:
            raise HTTPException(409,'knowledge_conflict') from None
        except KnowledgeNotFound:
            raise HTTPException(404,'knowledge_not_found') from None
        except ValueError:
            raise HTTPException(422,'invalid_knowledge_request') from None
        if len(result['results'])!=len(data.operations):
            raise RuntimeError('invalid_bundle_result')
        # Only normalize the stored snapshot through the same public DTO as its
        # individual operation. Never re-read current content during retry.
        return BundleResult(space_id=result['space_id'],results=[
            _RESULT_MODELS[step.operation].model_validate(row)
            for step,row in zip(data.operations,result['results'])])
    return service
