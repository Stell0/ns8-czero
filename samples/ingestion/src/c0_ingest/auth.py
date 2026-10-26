# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Dedicated public-client OAuth. Never reads another application's token store."""
from contextlib import contextmanager
import fcntl
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import urllib.error
import urllib.request
import webbrowser

from mcp.client.auth.oauth2 import PKCEParameters
from .errors import C0Error
from .http import open_url
from .state import atomic, read


def destination(config):
    value = config['url']
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path != '/mcp' or value.endswith('/')):
        raise C0Error('Configure a canonical HTTPS hostname-root /mcp endpoint')
    origin = f'https://{url.netloc}'
    issuer = config.get('issuer', origin + '/oauth')
    if issuer != origin + '/oauth':
        raise C0Error('C0 issuer must match the configured endpoint origin and /oauth')
    return origin, issuer


@contextmanager
def locked(path):
    """One process per job/store; lock files remain so waiters keep one inode."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def metadata(config):
    origin, issuer = destination(config)
    try:
        request = urllib.request.Request(origin + '/.well-known/oauth-authorization-server/oauth')
        with open_url(request) as response:
            result = json.loads(response.read(65537))
        if result['issuer'] != issuer:
            raise ValueError
        for key, path in [('authorization_endpoint', '/authorize'), ('token_endpoint', '/token')]:
            if result[key] != issuer + path:
                raise ValueError
        return result
    except (OSError, ValueError, KeyError):
        raise C0Error('OAuth metadata is unavailable or differs from the configured C0 issuer') from None


def store_path(config):
    path = Path(config['credentials_file']).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise C0Error('A private absolute dedicated credential-file path is required')
    return path


def stored(config):
    path = store_path(config)
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise C0Error('Run auth login; credential file must be private (mode 0600)')
    try:
        value = read(path)
        _, issuer = destination(config)
        if (value['format'] != 1 or value['server_url'] != config['url']
                or value['issuer'] != issuer or value['client_id'] != config['client_id']):
            raise ValueError
        return value
    except (OSError, KeyError, ValueError, TypeError):
        raise C0Error('Credential binding mismatch; use a dedicated ingestion login') from None


def exchange(config, fields):
    info = metadata(config)
    request = urllib.request.Request(info['token_endpoint'],
        data=urlencode({**fields, 'client_id': config['client_id'], 'resource': config['url']}).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with open_url(request) as response:
            result = json.loads(response.read(65537))
        if (not isinstance(result.get('access_token'), str) or not result['access_token']
                or type(result.get('expires_in')) is not int or result['expires_in'] <= 0
                or result.get('token_type', '').lower() != 'bearer'):
            raise ValueError
        return result
    except (OSError, KeyError, ValueError, TypeError):
        raise C0Error('OAuth outcome failed or is uncertain; run auth login, do not replay refresh') from None


def save_tokens(config, tokens, previous=None):
    _, issuer = destination(config)
    refresh = tokens.get('refresh_token', (previous or {}).get('refresh_token'))
    if not isinstance(refresh, str) or not refresh:
        raise C0Error('No refresh token; reconnect and explicitly select background access')
    wanted = set(config.get('scopes', 'c0:read c0:write').split())
    scopes = tokens.get('scope', (previous or {}).get('scope', ' '.join(sorted(wanted))))
    if set(scopes.split()) != wanted:
        raise C0Error('Consented scopes differ; explicitly consent to the configured scopes')
    value = {'format': 1, 'server_url': config['url'], 'issuer': issuer,
             'client_id': config['client_id'], 'access_token': tokens['access_token'],
             'refresh_token': refresh, 'scope': scopes,
             'expires_at': time.time() + tokens['expires_in']}
    atomic(store_path(config), value)
    return value['access_token']


def credentials(config):
    """A durable marker prevents retry after an interrupted/uncertain rotation."""
    path = store_path(config)
    pending = path.with_suffix(path.suffix + '.pending')
    with locked(str(path) + '.lock'):
        if pending.exists():
            raise C0Error('Previous OAuth outcome is uncertain; run auth login before continuing')
        value = stored(config)
        if set(value['scope'].split()) != set(config.get('scopes', 'c0:read c0:write').split()):
            raise C0Error('Stored scopes differ from this job; run auth login')
        if value['expires_at'] > time.time() + 30:
            return value['access_token']
        if not value.get('refresh_token'):
            raise C0Error('No refresh token; reconnect with background access')
        # Commit uncertainty before sending. A crash after rotation cannot replay it.
        atomic(pending, {'refresh_started': True})
        tokens = exchange(config, {'grant_type': 'refresh_token', 'refresh_token': value['refresh_token']})
        token = save_tokens(config, tokens, value)
        pending.unlink()
        return token


def login(config, *, launch=webbrowser.open, timeout=300):
    """Interactive only; normal scripts never open a browser or print auth URLs."""
    _, expected_issuer = destination(config)
    redirect = config['redirect_uri']
    url = urlsplit(redirect)
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
            or not url.path.startswith('/') or url.username or url.query or url.fragment):
        raise C0Error('Register an exact http://127.0.0.1:PORT/path callback')
    state = secrets.token_urlsafe(32)
    pkce = PKCEParameters.generate()
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(3)
            super().setup()

        def log_message(self, *args):
            pass  # Callback query contains private one-use OAuth values.

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            valid = (parsed.path == url.path and self.headers.get('Host') == url.netloc
                     and query.get('state') == [state]
                     and query.get('iss', [expected_issuer]) == [expected_issuer]
                     and all(len(v) == 1 for v in query.values()))
            if valid and query.get('code', [''])[0] and 'error' not in query:
                result['code'] = query['code'][0]
            elif valid:
                result['error'] = True
            self.send_response(200 if valid else 400)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(b'Return to the ingestion terminal.' if valid else b'Invalid callback.')

    path = store_path(config)
    with locked(str(path) + '.lock'):
        if path.exists():
            stored(config)  # Never replace an unrelated application's credential store.
        with HTTPServer(('127.0.0.1', url.port), Callback) as server:
            server.timeout = 1
            info = metadata(config)
            target = info['authorization_endpoint'] + '?' + urlencode({
                'response_type': 'code', 'client_id': config['client_id'], 'redirect_uri': redirect,
                'scope': config.get('scopes', 'c0:read c0:write'), 'resource': config['url'],
                'state': state, 'code_challenge': pkce.code_challenge, 'code_challenge_method': 'S256'})
            if not launch(target):
                raise C0Error('Cannot open a local browser; run auth login on the operator workstation')
            until = time.monotonic() + timeout
            while not result and time.monotonic() < until:
                server.handle_request()
            if not result.get('code'):
                raise C0Error('Login denied or timed out; no ingestion was performed')
            tokens = exchange(config, {'grant_type': 'authorization_code', 'code': result['code'],
                                      'redirect_uri': redirect, 'code_verifier': pkce.code_verifier})
            save_tokens(config, tokens)
            path.with_suffix(path.suffix + '.pending').unlink(missing_ok=True)
    return {'status': 'connected', 'credentials': 'dedicated private store'}


def disconnect(config):
    """Public revocation of this job's grant; never touch another connection."""
    path = store_path(config)
    with locked(str(path) + '.lock'):
        value = stored(config)
        _, issuer = destination(config)
        info = metadata(config)
        if info.get('revocation_endpoint') != issuer + '/revoke':
            raise C0Error('Unexpected revocation endpoint; disconnect through the C0 account page')
        request = urllib.request.Request(info['revocation_endpoint'],
            data=urlencode({'token': value['refresh_token'], 'token_type_hint': 'refresh_token',
                            'client_id': config['client_id'], 'resource': config['url']}).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            with open_url(request) as response:
                if response.status != 200:
                    raise ValueError
        except (OSError, ValueError):
            raise C0Error('Disconnect is unconfirmed; inspect C0 connections before deleting local credentials') from None
        path.unlink()
        path.with_suffix(path.suffix + '.pending').unlink(missing_ok=True)
    return {'status': 'disconnected', 'writes_c0_content': 0}
