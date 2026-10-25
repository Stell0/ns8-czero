# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Shared literal private configuration for source adapters."""
from pathlib import Path
import re
from .auth import destination


def dotenv(path):
    """Literal KEY=value data; no shell execution or interpolation."""
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch('[A-Z][A-Z0-9_]*', key) or key in result:
            raise ValueError('Invalid or duplicate .env key')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError('Unclosed .env value')
            value = value[1:-1]
        if '\0' in value:
            raise ValueError('Invalid .env value')
        result[key] = value
    return result


def connection_settings(root):
    root = Path(root).resolve()
    env = dotenv(root / '.env')
    c0 = {'url': env['C0_URL'], 'identity': env['C0_ACCOUNT_NAME'],
          'account_id': env.get('C0_ACCOUNT_ID', ''), 'space_id': env.get('C0_SPACE_ID', ''),
          'space_name': env['C0_SPACE_NAME'], 'client_id': env['C0_CLIENT_ID'],
          'redirect_uri': env.get('C0_REDIRECT_URI', 'http://127.0.0.1:43220/callback/c0-ingestion'),
          'scopes': env.get('C0_SCOPES', 'c0:read c0:write'),
          'credentials_file': str(root / 'oauth.json'), 'poll_attempts': 20, 'poll_seconds': 3}
    destination(c0)
    if not c0['identity'] or not c0['space_name'] or not c0['client_id']:
        raise ValueError('Configure expected account, space and dedicated client ID in .env')
    if not set(c0['scopes'].split()) <= {'c0:read', 'c0:write', 'c0:admin'}:
        raise ValueError('Unsupported OAuth scopes')
    return c0
