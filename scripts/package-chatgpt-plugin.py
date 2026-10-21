#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Build a private, per-instance web plugin source tree and reproducible archive."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'plugins/c0-knowledge'
ASSETS = (
    'plugin.json',
    'skills/c0-setup/SKILL.md', 'skills/c0-research/SKILL.md',
    'skills/c0-maintain-knowledge/SKILL.md',
    'references/connection.md', 'references/maintenance.md',
)


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
    value = value.removeprefix('plugin_')
    if not re.fullmatch(r'(?:asdk_app_|connector_|templated_apps_)[A-Za-z0-9_-]{1,192}', value):
        raise ValueError('Supply the registered ChatGPT app ID, not a workspace plugin ID or URL')
    return value


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()


def build(url, connection, name, output, *, template=TEMPLATE, license_file=ROOT / 'LICENSE'):
    url, connection = mcp_url(url), app_id(connection)
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', name) or len(name) > 64:
        raise ValueError('Use a unique lowercase kebab-case plugin name, at most 64 characters')
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Choose a new output directory; existing output is never replaced')
    payload = {}
    for item in ASSETS:
        path = template / item
        if not path.is_file() or path.is_symlink() or any(p.is_symlink() for p in path.parents if p != template.parent):
            raise ValueError('Missing or unsafe package template')
        payload['plugins/' + name + '/' + item] = path.read_bytes()
    if not license_file.is_file() or license_file.is_symlink():
        raise ValueError('Missing package license')
    base = 'plugins/' + name + '/'
    manifest = json.loads(payload[base + 'plugin.json'])
    manifest['name'] = name
    payload[base + 'plugin.json'] = json_bytes(manifest)
    payload[base + '.app.json'] = json_bytes({'apps': {'c0': {'id': connection, 'required': True}}})
    payload[base + 'LICENSE'] = license_file.read_bytes()
    payload[base + 'references/instance.md'] = (
        '# This C0 instance\n\n'
        f'- Canonical MCP URL: `{url}`\n'
        f'- Registered ChatGPT app ID: `{connection}`\n\n'
        'Use only this app. The operator must verify in ChatGPT that the app ID belongs '
        'to this URL; offline generation cannot prove that association. Do not substitute '
        'another connection, request credentials in chat or infer additional access.\n'
    ).encode()
    payload['.agents/plugins/marketplace.json'] = json_bytes({
        'name': name + '-marketplace', 'interface': {'displayName': name},
        'plugins': [{'name': name, 'source': {'source': 'local', 'path': './plugins/' + name},
                     'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
                     'category': 'Productivity'}],
    })
    payload['INSTALL.md'] = (
        '# Private ChatGPT web package\n\n'
        f'Package: {name} {manifest["version"]}\n\n'
        f'Instance: `{url}`\n\n'
        f'Required registered app: `{connection}`\n\n'
        'First verify this URL/app association in ChatGPT and complete C0 CIMD approval '
        'and sign-in. Generation does not connect accounts or grant permissions.\n\n'
        '## Individual/private setup\n\n'
        'In ChatGPT web, invoke Plugin Creator where your account permits it. Attach '
        'the packaged skill and reference files (or the source archive if the creator '
        'can inspect it). Ask it to create a private plugin from those instructions '
        'and include the exact registered C0 app above. Review the saved skills and '
        'app binding. Preserve all three distinct named skills and resolve their linked '
        'reference material if attachments are flattened or renamed. Install it and '
        'test in a new conversation. Do not assume ZIP '
        'attachment alone installs a plugin. Keep it private until verified.\n\n'
        '## Managed workspace setup\n\n'
        'Put the generated tree in an operator-controlled GitHub repository. A workspace '
        'admin uses Admin > Plugins > Add > Import marketplace with the repository URL '
        'and a reviewed commit. Use the generated root as Path if nested. Enable the '
        'required app for the intended test role; each user completes their own login. '
        'This tree references .app.json and contains no inline MCP declaration.\n\n'
        '## Acceptance\n\n'
        'Confirm the packaged skills are available in ChatGPT web, invoke c0-setup, '
        'check account/space, and research a known topic with original citations. '
        'Test permitted maintenance in an owned fixture and Reader denial. Record '
        'actual web evidence for both routes; directory/ZIP validation or desktop '
        'execution alone does not establish web readiness. No public submission is performed.\n'
    ).encode()
    # Preflight every input before creating output. Build in a private sibling;
    # publish only to an exclusively-created destination, never merge directories.
    parent = output.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError('Choose an existing non-symlink output parent')
    staging = Path(tempfile.mkdtemp(prefix='.c0-plugin-', dir=parent))
    claimed = False
    try:
        for name_in_zip, content in sorted(payload.items()):
            destination = staging / name_in_zip
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            destination.chmod(0o644)
        archive = staging / 'plugin.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
            for path, content in sorted(payload.items()):
                item = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                item.create_system = 3
                item.external_attr = 0o100644 << 16
                z.writestr(item, content)
        sums = {path: hashlib.sha256(content).hexdigest() for path, content in payload.items()}
        sums['plugin.zip'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        (staging / 'SHA256SUMS').write_text(''.join(digest + '  ' + path + '\n' for path, digest in sorted(sums.items())))
        output.mkdir(mode=0o700)  # Exclusive; a concurrent writer must win or fail.
        claimed = True
        for entry in staging.iterdir():
            entry.rename(output / entry.name)
    except BaseException:
        if claimed:
            shutil.rmtree(output)
        raise
    finally:
        shutil.rmtree(staging)
    return {'name': manifest['name'], 'version': manifest['version'],
            'archive_sha256': sums['plugin.zip'], 'output': str(output)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mcp-url', required=True)
    p.add_argument('--chatgpt-app-id', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    try:
        result = build(args.mcp_url, args.chatgpt_app_id, args.name, args.output)
    except (ValueError, OSError, json.JSONDecodeError):
        p.exit(2, 'Package not created: check inputs, template and new output directory.\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
