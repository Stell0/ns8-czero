# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""REST adapters for the same bounded object operations used by extensions."""
from datetime import datetime
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from czero_core.identity import PermissionDenied, Role
from czero_core.objects import ObjectConflict, ObjectNotFound, ObjectService
from czero_app.auth import RequestAccess
from czero_app.object_errors import object_validation_code


class StrictRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)


class TypeCreate(StrictRequest):
    name: str = Field(min_length=1,max_length=64)
    label: str = Field(min_length=1,max_length=128)
    json_schema: dict = Field(alias='schema', description=(
        'Bounded object-root Draft 2020-12 schema. Use properties, required and additionalProperties:false. '
        'References, regexes and combinators are unsupported. Unique string properties require explicit maxLength <=128.'))
    unique_fields: list[str] = Field(default_factory=list,max_length=8, description=(
        'Optional top-level scalar properties enforced unique per type. '
        'Each unique string must explicitly declare maxLength <=128 in schema.properties.'))


class TypeView(BaseModel):
    name: str
    label: str
    json_schema: dict = Field(alias='schema')
    unique_fields: list[str]
    created_at: datetime


class TypesView(BaseModel):
    types: list[TypeView]


class ObjectCreate(StrictRequest):
    type_name: str = Field(min_length=1,max_length=64)
    data: dict
    tags: list[str] = Field(default_factory=list,max_length=32)


class ObjectUpdate(StrictRequest):
    data: dict
    expected_revision: int = Field(ge=1,le=2147483647)
    tags: list[str] | None = Field(default=None,max_length=32)


class ObjectView(BaseModel):
    id: UUID
    type_name: str
    data: dict
    tags: list[str]
    revision: int
    created_at: datetime
    updated_at: datetime


class ObjectsView(BaseModel):
    objects: list[ObjectView]


class DeletedView(BaseModel):
    id: UUID
    revision: int
    deleted: Literal[True]


class BatchCreate(ObjectCreate):
    operation: Literal['create']


class BatchUpdate(ObjectUpdate):
    operation: Literal['update']
    id: str = Field(min_length=36,max_length=36)


class BatchDelete(StrictRequest):
    operation: Literal['delete']
    id: str = Field(min_length=36,max_length=36)
    expected_revision: int = Field(ge=1,le=2147483647)


class BatchRequest(StrictRequest):
    operations: list[Annotated[BatchCreate | BatchUpdate | BatchDelete,Field(discriminator='operation')]] = Field(min_length=1,max_length=25)


class BatchView(BaseModel):
    results: list[ObjectView | DeletedView]


class RelationCreate(StrictRequest):
    source_id: str = Field(min_length=36,max_length=36)
    target_id: str = Field(min_length=36,max_length=36)
    source_type: str = Field(min_length=1,max_length=64)
    target_type: str = Field(min_length=1,max_length=64)
    kind: str = Field(min_length=1,max_length=64)


class RelationView(BaseModel):
    id: UUID
    source_id: UUID
    target_id: UUID
    kind: str
    created_at: datetime
    source_type: str | None = None
    target_type: str | None = None


class RelationsView(BaseModel):
    relations: list[RelationView]


class ReferenceView(BaseModel):
    kind: str
    id: UUID
    type_name: str
    data: dict


class EventView(BaseModel):
    id: int
    object_id: UUID
    type_name: str
    revision: int
    operation: Literal['create','update','delete','relation_add','relation_remove']
    actor_id: UUID
    created_at: datetime


class EventsView(BaseModel):
    events: list[EventView]


def install_object_routes(app: FastAPI,database,auth,read_context,write_context, *, reference_resolvers=None):
    operation = app.state.operation_catalog.bind
    service=ObjectService(database,auth.access if auth else None,reference_resolvers=reference_resolvers)
    app.state.objects=service

    def invoke(operation,*args,**kwargs):
        if auth is None: raise HTTPException(503,'authentication_not_configured')
        try: return operation(*args,**kwargs)
        except PermissionDenied: raise
        except ObjectConflict: raise HTTPException(409,'object_conflict') from None
        except ObjectNotFound: raise HTTPException(404,'object_not_found') from None
        except ValueError as error:
            detail=object_validation_code(str(error)) or 'invalid_object_request'
            raise HTTPException(422,detail) from None

    @app.get('/api/v1/object-types',response_model=TypesView)
    @operation('object_types_list', 'List immutable object type definitions', Role.READER, TypesView, read_only=True)
    def types(limit: int=100,offset: int=0,context: RequestAccess=Depends(read_context)):
        return {'types':invoke(service.list_types,context.actor,limit=limit,offset=offset)}

    @app.post('/api/v1/object-types',response_model=TypeView,status_code=201)
    @operation('object_types_create', 'Register an immutable bounded object schema. Unique strings require explicit maxLength <=128.', Role.ADMIN, TypeView, read_only=False)
    def register(data: TypeCreate,context: RequestAccess=Depends(write_context)):
        return invoke(service.register_type,context.actor,data.name,data.label,data.json_schema,data.unique_fields)

    @app.get('/api/v1/object-types/{type_name}',response_model=TypeView)
    @operation('object_types_get', 'Inspect one immutable object type', Role.READER, TypeView, read_only=True)
    def type_detail(type_name: str,context: RequestAccess=Depends(read_context)):
        return invoke(service.get_type,context.actor,type_name)

    @app.get('/api/v1/objects',response_model=ObjectsView)
    @operation('objects_list', 'List and filter typed object records', Role.READER, ObjectsView, read_only=True)
    def objects(type_name: str,limit: int=50,offset: int=0,where: str='{}',tag: str | None=None,
                context: RequestAccess=Depends(read_context)):
        if len(where.encode('utf-8'))>4096: raise HTTPException(422,'invalid_filter')
        try: filters=json.loads(where)
        except (ValueError,RecursionError): raise HTTPException(422,'invalid_filter') from None
        return {'objects':invoke(service.list,context.actor,type_name,limit=limit,offset=offset,where=filters,tag=tag)}

    @app.post('/api/v1/objects',response_model=ObjectView,status_code=201)
    @operation('objects_create', 'Create a typed object record', Role.EDITOR, ObjectView, read_only=False)
    def create(data: ObjectCreate,context: RequestAccess=Depends(write_context)):
        return invoke(service.create,context.actor,data.type_name,data.data,record_tags=data.tags)

    @app.post('/api/v1/objects/batch',response_model=BatchView)
    @operation('objects_batch', 'Apply an atomic bounded object mutation batch', Role.EDITOR, BatchView, read_only=False)
    def batch(data: BatchRequest,context: RequestAccess=Depends(write_context)):
        operations=[]
        for op in data.operations:
            value=op.model_dump(exclude_none=True)
            operations.append(value)
        return {'results':invoke(service.batch,context.actor,operations)}

    @app.get('/api/v1/object-events',response_model=EventsView)
    @operation('objects_changes', 'Read commit-ordered object changes', Role.READER, EventsView, read_only=True)
    def events(after: int=0,limit: int=50,context: RequestAccess=Depends(read_context)):
        return {'events':invoke(service.events,context.actor,after=after,limit=limit)}

    @app.post('/api/v1/object-relations',response_model=RelationView,status_code=201)
    @operation('object_relations_create', 'Connect two typed object records', Role.EDITOR, RelationView, read_only=False)
    def relation(data: RelationCreate,context: RequestAccess=Depends(write_context)):
        return invoke(service.add_relation,context.actor,**data.model_dump())

    @app.delete('/api/v1/object-relations/{relation_id}',status_code=204)
    @operation('object_relations_delete', 'Remove an object relation', Role.EDITOR, None, read_only=False)
    def remove_relation(relation_id: UUID,context: RequestAccess=Depends(write_context)):
        invoke(service.remove_relation,context.actor,relation_id)

    @app.get('/api/v1/objects/{object_id}',response_model=ObjectView)
    @operation('objects_get', 'Read one object record and revision', Role.READER, ObjectView, read_only=True)
    def detail(object_id: UUID,context: RequestAccess=Depends(read_context)):
        return invoke(service.get,context.actor,object_id)

    @app.put('/api/v1/objects/{object_id}',response_model=ObjectView)
    @operation('objects_update', 'Update a record with its expected revision', Role.EDITOR, ObjectView, read_only=False)
    def update(object_id: UUID,data: ObjectUpdate,context: RequestAccess=Depends(write_context)):
        return invoke(service.update,context.actor,object_id,data.data,expected_revision=data.expected_revision,record_tags=data.tags)

    @app.delete('/api/v1/objects/{object_id}',response_model=DeletedView)
    @operation('objects_delete', 'Delete a record with its expected revision', Role.EDITOR, DeletedView, read_only=False)
    def delete(object_id: UUID,expected_revision: int,context: RequestAccess=Depends(write_context)):
        return invoke(service.delete,context.actor,object_id,expected_revision=expected_revision)

    @app.get('/api/v1/objects/{object_id}/relations',response_model=RelationsView)
    @operation('object_relations_list', 'List relations of an object record', Role.READER, RelationsView, read_only=True)
    def relations(object_id: UUID,limit: int=50,offset: int=0,context: RequestAccess=Depends(read_context)):
        return {'relations':invoke(service.relations,context.actor,object_id,limit=limit,offset=offset)}

    @app.get('/api/v1/references/{kind}/{resource_id}',response_model=ReferenceView)
    @operation('references_get', 'Resolve a registered typed reference', Role.READER, ReferenceView, read_only=True)
    def reference(kind: str,resource_id: UUID,type_name: str,context: RequestAccess=Depends(read_context)):
        return invoke(service.resolve_reference,context.actor,kind,resource_id,type_name)
