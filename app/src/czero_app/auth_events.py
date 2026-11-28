# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded request-local diagnostics. References cannot authenticate a request."""
from contextvars import ContextVar
import hmac
import re
import secrets

current_event = ContextVar('c0_auth_event', default=None)
_reference_key = secrets.token_bytes(32)

ROUTES = frozenset({
    '/auth/sign-in', '/auth/login', '/auth/callback', '/auth/logout', '/oauth/authorize',
    '/oauth/consent', '/oauth/consent/request', '/oauth/consent/background', '/oauth/token',
    '/oauth/revoke', '/oauth/connect', '/oauth/connect/request', '/oauth/connect/approve',
    '/oauth/connect/review', '/oauth/connect/continue', '/mcp',
})
REASONS = frozenset({
    'callback_rejected', 'provider_unavailable', 'provider_rejected', 'session_expired', 'csrf_rejected',
    'origin_rejected', 'draft_mismatch', 'draft_unavailable', 'grant_limit', 'completed',
    'metadata_changed', 'metadata_rejected', 'refresh_replay', 'rotation_limit', 'native_authority_rejected',
    'grant_rejected', 'credential_rejected', 'dependency_unavailable', 'discovery_challenge',
    'code_exchanged', 'refresh_rotated', 'onboarding_unavailable', 'tool_error',
})


def _reference(label, value):
    if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{43}', value):
        return hmac.digest(_reference_key, label + value.encode('ascii'), 'sha256')[:12].hex()
    return '-'


def flow_reference(selector):
    return _reference(b'flow:', selector)


def mark(reason, *, access_token=None, issued_code=None):
    event = current_event.get()
    if event is None:
        return
    if reason in REASONS:
        event['c0_auth_reason'] = reason
    if access_token is not None:
        event['c0_generation_ref'] = _reference(b'access:', access_token)
    if issued_code is not None:
        event['c0_exchange_ref'] = _reference(b'code:', issued_code)
