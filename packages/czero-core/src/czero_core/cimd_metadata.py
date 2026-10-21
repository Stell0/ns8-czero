# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, transport-independent approval-relevant public client metadata."""
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import re
from urllib.parse import unquote, urlsplit

from .oauth_clients import redirect_uri
from .operations import SCOPES


class MetadataRejected(ValueError):
    def __init__(self):
        super().__init__('invalid_client_metadata')


def metadata_url(value):
    if (not isinstance(value, str) or not value.isascii() or not 1 <= len(value) <= 2048
            or any(ord(c) < 33 or ord(c) > 126 for c in value) or '\\' in value
            or '?' in value or '#' in value):
        raise MetadataRejected()
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if (parsed.scheme != 'https' or not host or not parsed.path
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443) or host.endswith('.') or len(host) > 253
                or not re.fullmatch(r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*', host)
                or any(not 1 <= len(label) <= 63 or label.startswith('-') or label.endswith('-')
                       for label in host.split('.')) or not any(c.isalpha() for c in host)):
            raise MetadataRejected()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise MetadataRejected()
        path = unquote(parsed.path, errors='strict')
        if ('\\' in path or re.search(r'%(?:2f|5c)', parsed.path, re.I)
                or any(part in ('.', '..') for part in path.split('/'))
                or any(ord(c) < 33 or ord(c) == 127 for c in path)):
            raise MetadataRejected()
    except (ValueError, UnicodeError):
        raise MetadataRejected() from None
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise MetadataRejected()
        result[key] = value
    return result


def _inspect(value, depth=0):
    if depth > 16:
        raise MetadataRejected()
    if isinstance(value, dict):
        # Even unused extension fields must not carry secrets/private JWKs.
        forbidden = {'client_secret', 'client_secret_expires_at', 'private_key',
                     'd', 'p', 'q', 'dp', 'dq', 'qi', 'oth', 'k'}
        if forbidden.intersection(value):
            raise MetadataRejected()
        for item in value.values():
            _inspect(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _inspect(item, depth + 1)


def _strings(value, allowed, *, minimum=1, maximum=4):
    if (type(value) is not list or not minimum <= len(value) <= maximum
            or any(type(item) is not str or item not in allowed for item in value)
            or len(set(value)) != len(value)):
        raise MetadataRejected()
    return tuple(sorted(value))


@dataclass(frozen=True)
class ClientMetadata:
    client_id: str
    client_name: str
    redirect_uris: tuple[str, ...]
    grant_types: tuple[str, ...]
    scope_ceiling: tuple[str, ...] | None

    def descriptor(self):
        return {'client_id': self.client_id, 'client_name': self.client_name,
                'redirect_uris': list(self.redirect_uris), 'token_endpoint_auth_method': 'none',
                'grant_types': list(self.grant_types), 'response_types': ['code'],
                'scope_ceiling': None if self.scope_ceiling is None else list(self.scope_ceiling)}

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(self.descriptor(), sort_keys=True,
            separators=(',', ':'), ensure_ascii=True).encode('ascii')).hexdigest()


def parse_metadata(url, body):
    metadata_url(url)
    if type(body) is not bytes or not 0 < len(body) <= 32768:
        raise MetadataRejected()
    try:
        value = json.loads(body.decode('utf-8'), object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(MetadataRejected()))
        _inspect(value)
        if type(value) is not dict or value.get('client_id') != url:
            raise MetadataRejected()
        name = value.get('client_name')
        if (type(name) is not str or not name.strip() or not name.isprintable()
                or len(name) > 128):
            raise MetadataRejected()
        callbacks = value.get('redirect_uris')
        if (type(callbacks) is not list or not 1 <= len(callbacks) <= 4
                or any(type(item) is not str for item in callbacks)
                or len(set(callbacks)) != len(callbacks)):
            raise MetadataRejected()
        callbacks = tuple(sorted(redirect_uri(item) for item in callbacks))
        if 'token_endpoint_auth_methods_supported' in value:
            methods = value['token_endpoint_auth_methods_supported']
            if (type(methods) is not list or not 1 <= len(methods) <= 16
                    or any(type(item) is not str for item in methods)
                    or len(set(methods)) != len(methods) or 'none' not in methods):
                raise MetadataRejected()
        elif value.get('token_endpoint_auth_method') != 'none':
            raise MetadataRejected()
        grants = _strings(value.get('grant_types', ['authorization_code']),
                          {'authorization_code', 'refresh_token'}, maximum=2)
        if 'authorization_code' not in grants:
            raise MetadataRejected()
        _strings(value.get('response_types', ['code']), {'code'}, maximum=1)
        ceiling = None
        if 'scope' in value:
            scope = value['scope']
            if type(scope) is not str or scope != ' '.join(scope.split()):
                raise MetadataRejected()
            ceiling = _strings(scope.split(' '), SCOPES, maximum=3)
        return ClientMetadata(url, name, callbacks, grants, ceiling)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise MetadataRejected() from None
