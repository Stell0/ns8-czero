# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from uuid import uuid4

import pytest

from czero_core.identity import Actor, PermissionDenied, Role
from czero_core.operations import Operation, OperationRegistry, OperationRejected, ScopeDenied


def test_capability_and_execution_use_current_roles_and_scopes():
    actor = Actor(uuid4(), Role.ADMIN)
    current = {actor.user_id: actor}
    calls = []
    def authorize(stale, minimum):
        value = current.get(stale.user_id)
        if value is None:
            raise PermissionDenied()
        value.require(minimum)
        return value
    registry = OperationRegistry(authorize)
    for name, role, scope, read_only in [('read', Role.READER, 'c0:read', True),
            ('edit', Role.EDITOR, 'c0:write', False), ('admin', Role.ADMIN, 'c0:admin', False)]:
        registry.register(Operation(name, name, role, scope, {'type':'object'}, {'type':'object'},
            lambda caller, arguments: calls.append(caller.role) or arguments, read_only))
    assert [op['name'] for op in registry.describe(actor, scopes={'c0:read'})] == ['read']
    assert registry.execute('read', actor, {'query':'untrusted text'}, scopes={'c0:read'}) == {'query':'untrusted text'}
    with pytest.raises(ScopeDenied) as denied:
        registry.execute('edit', actor, {}, scopes={'c0:read'})
    assert denied.value.scope == 'c0:write'
    current[actor.user_id] = Actor(actor.user_id, Role.READER)
    assert [op['name'] for op in registry.describe(actor)] == ['read']
    with pytest.raises(PermissionDenied):
        registry.execute('edit', actor, {}, scopes={'c0:write'})
    registry.execute('read', actor, {}, scopes={'c0:read'})
    assert calls == [Role.ADMIN, Role.READER]
    current.clear()
    with pytest.raises(PermissionDenied):
        registry.describe(actor)
    with pytest.raises(PermissionDenied):
        registry.execute('read', actor, {}, scopes={'c0:read'})


def test_untrusted_arguments_cannot_select_code_or_bypass_byte_limits():
    actor = Actor(uuid4(), Role.READER)
    calls = []
    registry = OperationRegistry(lambda actor, role: actor)
    schema = {'type':'object', 'properties':{'text':{'type':'string'}}}
    registry.register(Operation('read', 'Read', Role.READER, 'c0:read', schema, {},
        lambda actor, arguments: calls.append(arguments)))
    schema['properties']['text']['type'] = 'integer'
    metadata = registry.describe(actor)
    metadata[0]['input_schema']['properties']['text']['type'] = 'boolean'
    assert registry.definition('read')['input_schema']['properties']['text']['type'] == 'string'
    for scopes in ('not-c0:read-permitted', ['c0:read'], {'arbitrary:scope'}):
        with pytest.raises(OperationRejected):
            registry.execute('read', actor, {}, scopes=scopes)
        with pytest.raises(OperationRejected):
            registry.describe(actor, scopes=scopes)
    for name, arguments in [('os.system', {}), ('read', []), ('read', {'value':float('nan')}),
            ('read', {'value':object()}), ('read', {'value':'x' * 1048576})]:
        with pytest.raises(OperationRejected, match='^invalid_operation_request$'):
            registry.execute(name, actor, arguments)
    assert calls == []


def test_scope_filters_cannot_expand_bound_invocation_authority():
    actor = Actor(uuid4(), Role.ADMIN, delegated_scopes=frozenset({'c0:read'}))
    calls = []
    registry = OperationRegistry(lambda actor, role: actor)
    registry.register(Operation('edit', 'Edit', Role.EDITOR, 'c0:write', {}, {},
        lambda actor, arguments: calls.append(arguments), False))
    assert registry.describe(actor, scopes={'c0:read','c0:write'})[0]['name'] == 'edit'
    for scopes in (None, {'c0:read','c0:write','c0:admin'}):
        with pytest.raises(ScopeDenied) as denied:
            registry.execute('edit', actor, {}, scopes=scopes)
        assert denied.value.scope == 'c0:write'
    assert calls == []


def test_trusted_operation_policy_denial_precedes_scope_challenge():
    from dataclasses import replace
    actor = Actor(uuid4(), Role.ADMIN, delegated_scopes=frozenset({'c0:read'}))
    calls = []
    registry = OperationRegistry(lambda actor, role: actor)
    def policy(current, arguments):
        calls.append(arguments['space_id'])
        result = replace(current, role=Role.READER)
        result.require(Role.EDITOR)
        return result
    registry.register(Operation('edit', 'Edit', Role.EDITOR, 'c0:write', {}, {},
        lambda actor, arguments: pytest.fail('Denied operation invoked'), False, preauthorize=policy))
    with pytest.raises(PermissionDenied) as denied:
        registry.execute('edit', actor, {'space_id':'denied'}, scopes={'c0:read'})
    assert not isinstance(denied.value, ScopeDenied) and calls == ['denied']
    assert registry.describe(actor, scopes={'c0:read','c0:write'})[0]['name'] == 'edit'
