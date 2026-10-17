# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted operation descriptions shared by transports and discovery.

Handlers and schemas come from application Python code, never requests.
Domain services remain responsible for transactional authorization.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
import json
import re
from typing import Callable

from .identity import Actor, PermissionDenied, Role

SCOPES = frozenset(('c0:read', 'c0:write', 'c0:admin'))
MAX_ARGUMENT_BYTES = 1024 * 1024


class OperationRejected(ValueError):
    def __init__(self):
        super().__init__('invalid_operation_request')


class ScopeDenied(PermissionDenied):
    def __init__(self, scope):
        super().__init__()
        self.scope = scope


@dataclass(frozen=True)
class Operation:
    name: str
    description: str
    role: Role
    scope: str
    input_schema: dict
    output_schema: dict
    handler: Callable
    read_only: bool = True
    # Trusted resource/space policy runs before a scope-upgrade challenge.
    preauthorize: Callable | None = None


class OperationRegistry:
    def __init__(self, authorize: Callable[[Actor, Role], Actor]):
        self._authorize = authorize
        self._operations: dict[str, Operation] = {}

    def register(self, operation: Operation):
        if (not isinstance(operation, Operation)
                or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', operation.name)
                or not isinstance(operation.description, str)
                or not 1 <= len(operation.description) <= 1024
                or not isinstance(operation.role, Role)
                or operation.scope not in SCOPES
                or type(operation.read_only) is not bool
                or not callable(operation.handler)
                or (operation.preauthorize is not None and not callable(operation.preauthorize))
                or not isinstance(operation.input_schema, dict)
                or not isinstance(operation.output_schema, dict)):
            raise ValueError('invalid_operation_registration')
        for schema in (operation.input_schema, operation.output_schema):
            if len(json.dumps(schema, allow_nan=False).encode()) > 65536:
                raise ValueError('operation_schema_too_large')
        if operation.name in self._operations or len(self._operations) >= 128:
            raise ValueError('duplicate_or_excess_operation')
        # Metadata returned to a transport must not mutate trusted definitions.
        self._operations[operation.name] = Operation(
            operation.name, operation.description, operation.role, operation.scope,
            deepcopy(operation.input_schema), deepcopy(operation.output_schema),
            operation.handler, operation.read_only, operation.preauthorize)

    def _current(self, actor: Actor, operation: Operation, scopes, arguments):
        self._validate_scopes(scopes)
        current = self._authorize(actor, operation.role)
        try:
            if not isinstance(arguments, dict):
                raise ValueError()
            if len(json.dumps(arguments, allow_nan=False).encode()) > MAX_ARGUMENT_BYTES:
                raise ValueError()
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise OperationRejected() from None
        if operation.preauthorize is not None:
            selected = operation.preauthorize(current, arguments)
            if not isinstance(selected, Actor) or selected.user_id != current.user_id:
                raise PermissionDenied()
            selected.require(operation.role)
            # A policy may narrow the effective role/space, but cannot discard
            # the invocation's actual delegation while refreshing that Actor.
            current = replace(selected, delegation=current.delegation,
                              delegated_scopes=current.delegated_scopes)
        if ((scopes is not None and operation.scope not in scopes)
                or (current.delegated_scopes is not None and operation.scope not in current.delegated_scopes)):
            raise ScopeDenied(operation.scope)
        return current

    @staticmethod
    def _validate_scopes(scopes):
        if scopes is not None and (type(scopes) not in (set, frozenset) or not scopes <= SCOPES):
            raise OperationRejected()

    @staticmethod
    def _metadata(operation):
        return {'name': operation.name, 'description': operation.description,
                'minimum_role': operation.role.value, 'required_scope': operation.scope,
                'read_only': operation.read_only,
                'input_schema': deepcopy(operation.input_schema),
                'output_schema': deepcopy(operation.output_schema)}

    def describe(self, actor: Actor, *, scopes=None):
        # One current membership read; never cache capabilities from token roles.
        self._validate_scopes(scopes)
        current = self._authorize(actor, Role.READER)
        result = []
        for operation in self._operations.values():
            try:
                current.require(operation.role)
            except PermissionDenied:
                continue
            if scopes is not None and operation.scope not in scopes:
                continue
            result.append(self._metadata(operation))
        return sorted(result, key=lambda value: value['name'])

    def execute(self, name: str, actor: Actor, arguments: dict, *, scopes=None):
        operation = self._operations.get(name) if isinstance(name, str) else None
        if operation is None:
            raise OperationRejected()
        current = self._current(actor, operation, scopes, arguments)
        return operation.handler(current, arguments)

    def definition(self, name):
        """Public metadata for a trusted registered route, without a handler."""
        return self._metadata(self._operations[name])
