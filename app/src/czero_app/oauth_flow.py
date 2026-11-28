# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""First-party OAuth flow selector and its independent host-only browser proof."""
import re

from czero_core.oauth_consent import ConsentRejected
from czero_app.auth_events import current_event, flow_reference

PREFIX = '__Host-c0-flow-'
SELECTOR = re.compile(r'[A-Za-z0-9_-]{43}\Z')
BINDING = re.compile(r'(?:s-)?[A-Za-z0-9_-]{43}\Z')
MAX_FLOWS = 16


def browser_flows(request):
    flows = {}
    for header in request.headers.getlist('cookie'):
        for item in header.split(';'):
            name, _, proof = item.strip().partition('=')
            if name.startswith(PREFIX):
                selector = name[len(PREFIX):]
                if (not SELECTOR.fullmatch(selector) or not BINDING.fullmatch(proof)
                        or selector in flows or len(flows) >= MAX_FLOWS):
                    raise ConsentRejected()
                flows[selector] = proof
    return flows


def selected(request, *, selector=None):
    if selector is None:
        values = request.query_params.getlist('flow')
        if not values:
            return None
        if len(values) != 1:
            raise ConsentRejected()
        selector = values[0]
    if not isinstance(selector, str) or not SELECTOR.fullmatch(selector):
        raise ConsentRejected()
    proof = browser_flows(request).get(selector)
    if proof is None:
        raise ConsentRejected()
    return selector, proof


def flow_url(path, selector):
    return path + '?flow=' + selector if selector else path


def login_url(stage, selector):
    if selector:
        return f'/auth/login?flow={selector}&stage={stage}'
    return '/auth/login'


def set_flow_cookie(response, pending):
    event = current_event.get()
    if event is not None:
        event['c0_flow_ref'] = flow_reference(pending.request)
    response.set_cookie(PREFIX + pending.request, pending.binding, max_age=300, secure=True,
                        httponly=True, samesite='lax', path='/')
    response.headers['Referrer-Policy'] = 'no-referrer'
