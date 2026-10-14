# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind typed application handlers once for REST and other transports."""
from functools import wraps
import inspect
from typing import get_type_hints

from fastapi import HTTPException
from pydantic import ConfigDict, TypeAdapter, ValidationError, create_model

from czero_core.identity import PermissionDenied, Role
from czero_core.operations import Operation, OperationRegistry, OperationRejected
from czero_app.auth import RequestAccess


class OperationCatalog:
    def __init__(self, auth):
        def authorize(actor, role):
            if auth is None:
                raise PermissionDenied()
            return auth.access.authorize(actor, role)
        self.registry = OperationRegistry(authorize)

    def bind(self, name, description, role, result_model, *, read_only=True):
        """Keep FastAPI's signature/CSRF dependencies and reuse its typed handler."""
        def decorate(handler):
            signature = inspect.signature(handler)
            hints = get_type_hints(handler, include_extras=True)
            fields = {key: (hints[key], parameter.default if parameter.default is not inspect.Parameter.empty else ...)
                      for key, parameter in signature.parameters.items() if key != 'context'}
            model = create_model(name + '_arguments', __config__=ConfigDict(extra='forbid'), **fields)
            output = TypeAdapter(result_model)
            scope = 'c0:admin' if role is Role.ADMIN else ('c0:read' if read_only else 'c0:write')

            def invoke(actor, arguments):
                try:
                    parsed = model.model_validate(arguments)
                except ValidationError:
                    raise OperationRejected() from None
                values = {key: getattr(parsed, key) for key in fields}
                value = handler(context=RequestAccess(actor), **values)
                # The same DTO performs UUID/time normalization in every transport.
                try:
                    return output.dump_python(output.validate_python(value), mode='json', by_alias=True)
                except ValidationError:
                    raise HTTPException(503, 'invalid_operation_result') from None

            self.registry.register(Operation(name, description, role, scope,
                model.model_json_schema(), output.json_schema(), invoke, read_only))

            @wraps(handler)
            def route(*args, **kwargs):
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                context = bound.arguments.pop('context')
                arguments = model.model_validate(bound.arguments).model_dump(mode='json', by_alias=True)
                try:
                    return self.registry.execute(name, context.actor, arguments, scopes=context.scopes)
                except OperationRejected:
                    raise HTTPException(422, 'invalid_operation_request') from None

            route.__c0_operation__ = name
            return route
        return decorate

    def annotate_openapi(self, app):
        for route in app.routes:
            name = getattr(getattr(route, 'endpoint', None), '__c0_operation__', None)
            if name:
                metadata = self.registry.definition(name)
                route.operation_id = name
                route.openapi_extra = {**(route.openapi_extra or {}), 'x-c0-operation': {
                    key: metadata[key] for key in ('name', 'minimum_role', 'required_scope', 'read_only')}}
