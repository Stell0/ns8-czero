# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Credential-scoped presentation of the existing immutable account identity."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import ConfigDict, Field
from typing_extensions import NotRequired, TypedDict

from czero_app.auth import RequestAccess
from czero_core.identity import Role


class Profile(TypedDict):
    __pydantic_config__ = ConfigDict(extra='forbid', strict=True)
    id: Annotated[str, Field(min_length=1, pattern=r'\S', description=(
        'Opaque account identifier, unchanged across refresh, reconnect and display-name changes.'))]
    name: NotRequired[str]
    email: NotRequired[str]
    nickname: NotRequired[str]


def install_profile_routes(app, auth, read_context):
    @app.get('/api/v1/profile', response_model=Profile)
    @app.state.operation_catalog.bind('get_profile',
        'Return the profile represented by the current authenticated credentials. '
        'Its opaque id stays the same across refresh, reconnect and display-name changes.',
        Role.READER, Profile)
    def profile(context: RequestAccess = Depends(read_context)) -> Profile:
        # Core rechecks the current membership and captured session/delegation
        # in the same transaction that reads the persisted account.
        value = auth.access.profile(context.actor)
        identifier = value.get('id')
        if not isinstance(identifier, UUID):
            raise HTTPException(503, 'invalid_operation_result')
        result: Profile = {'id': str(identifier)}
        for source, target in (('display_name', 'name'), ('username', 'nickname')):
            text = value.get(source)
            if isinstance(text, str) and text.strip():
                result[target] = text
        return result
