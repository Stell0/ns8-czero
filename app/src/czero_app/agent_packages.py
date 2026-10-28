# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded deterministic end-user archives, shared by HTTP and the offline CLI."""
import hashlib
from io import BytesIO
import ipaddress
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = Path(os.getenv('CZERO_AGENT_PACKAGE_DIR', ROOT / 'plugins/c0-knowledge'))
ASSETS = ('plugin.json', 'skills/c0-setup/SKILL.md', 'skills/c0-research/SKILL.md',
          'skills/c0-maintain-knowledge/SKILL.md', 'skills/c0-projects/SKILL.md',
          'references/connection.md', 'references/maintenance.md', 'references/projects.md')

def mcp_url(value):
    try:
        p = urlsplit(value)
        host = p.hostname
        valid = (len(value) <= 2048 and value.isascii() and p.scheme == 'https' and host and
                 p.username is None and p.password is None and p.port in (None, 443) and
                 p.path == '/mcp' and not p.query and not p.fragment and
                 not any(c.isspace() or c == '\\' for c in value) and
                 len(host) <= 253 and '.' in host and any(c.isalpha() for c in host.split('.')[-1]) and
                 all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                     for label in host.split('.')) and
                 value == 'https://' + host + (':443' if p.port == 443 else '') + '/mcp')
        if not valid:
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Use the exact canonical HTTPS hostname-root /mcp URL without credentials, query or fragment') from None
    return value


def app_id(value):
    # The management page URL has a plugin_ wrapper; .app.json needs the app ID.
    if not isinstance(value, str):
        raise ValueError('invalid_connection')
    value = value.removeprefix('plugin_')
    if not re.fullmatch(r'(?:asdk_app_|connector_|templated_apps_)[A-Za-z0-9][A-Za-z0-9_-]{0,191}', value):
        raise ValueError('Supply the registered ChatGPT app ID, not a workspace plugin ID or URL')
    return value


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()


def connection_reference(value):
    """Accept the technical ID or its ordinary ChatGPT management-page URL."""
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('invalid_connection')
    if value.startswith('https://'):
        parsed = urlsplit(value)
        if (parsed.netloc != 'chatgpt.com' or parsed.query or parsed.fragment
                or not re.fullmatch(r'/(?:admin/)?plugins/[^/]+', parsed.path)):
            raise ValueError('invalid_connection')
        value = parsed.path.rsplit('/', 1)[1]
    return app_id(value)


def package_name(url, prefix='c0-knowledge'):
    host = urlsplit(mcp_url(url)).hostname
    return prefix + '-' + host.replace('.', '-')[:32].rstrip('-') + '-' + hashlib.sha256(host.encode()).hexdigest()[:8]


def asset(template, path):
    target = template / path
    if (not target.is_file() or target.is_symlink()
            or any(p.is_symlink() for p in target.parents if p != template.parent)
            or target.stat().st_size > 131072):
        raise ValueError('Missing or unsafe package template')
    return target.read_bytes()


def license_bytes(template, license_file=None):
    path = license_file or (template / 'LICENSE' if (template / 'LICENSE').is_file() else ROOT / 'LICENSE')
    return asset(path.parent, path.name)


def plugin_payload(url, connection, name, *, template=TEMPLATE, license_file=None):
    url, connection = mcp_url(url), app_id(connection)
    if not isinstance(name, str) or len(name) > 64 or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', name):
        raise ValueError('invalid_package_name')
    payload = {item: asset(template, item) for item in ASSETS}
    host = urlsplit(url).hostname
    manifest = json.loads(payload['plugin.json'])
    manifest['name'] = name
    manifest['description'] = 'Research and maintain C0 knowledge on ' + host + '.'
    manifest['extensions']['com.openai']['interface']['displayName'] = 'C0 — ' + host[:59]
    manifest['extensions']['com.openai']['interface']['shortDescription'] = 'Your C0 knowledge memory'
    payload['plugin.json'] = json_bytes(manifest)
    payload['.app.json'] = json_bytes({'apps': {'c0': {'id': connection, 'required': True}}})
    payload['LICENSE'] = license_bytes(template, license_file)
    payload['references/instance.md'] = (
        '# This C0 instance\n\n'
        f'- Instance: `{host}`\n'
        f'- Canonical MCP URL: `{url}`\n'
        f'- Registered ChatGPT app ID: `{connection}`\n\n'
        'Use only this app. Verify in ChatGPT that it connects to this URL. '
        'Generation cannot prove their association. Do not substitute another '
        'connection, ask for credentials in chat or infer additional access.\n'
    ).encode()
    return payload


def skill_payload(url, *, template=TEMPLATE, license_file=None):
    url = mcp_url(url)
    host = urlsplit(url).hostname
    name = package_name(url, 'c0-memory')
    skill = asset(template, 'memory-skill.md').decode('utf-8')
    for key, value in {'SKILL_NAME': name, 'INSTANCE_HOST': host,
                       'INSTANCE_URL': url.removesuffix('/mcp'), 'MCP_URL': url}.items():
        skill = skill.replace('{{' + key + '}}', value)
    # JSON string quoting is valid YAML scalar quoting, including non-ASCII.
    metadata = ('interface:\n  display_name: ' + json.dumps('C0 — ' + host) + '\n'
        '  short_description: "Search and maintain this C0 knowledge memory"\n'
        'dependencies:\n  tools:\n    - type: "mcp"\n      value: "c0"\n'
        '      description: ' + json.dumps('C0 memory on ' + host) + '\n'
        '      transport: "streamable_http"\n      url: ' + json.dumps(url) + '\n')
    return {'SKILL.md': skill.encode(), 'agents/openai.yaml': metadata.encode(),
            'LICENSE': license_bytes(template, license_file)}


def zip_bytes(payload):
    if not payload or len(payload) > 16 or sum(map(len, payload.values())) > 262144:
        raise ValueError('invalid_package_size')
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(payload.items()):
            if (name.startswith('/') or '\\' in name
                    or any(part in ('', '.', '..') for part in name.split('/'))):
                raise ValueError('invalid_package_path')
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return output.getvalue()
