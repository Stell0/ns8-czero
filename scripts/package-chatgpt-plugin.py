#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Build a private, per-instance web plugin source tree and reproducible archive."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app/src'))
from czero_app.agent_packages import TEMPLATE, mcp_url, app_id, json_bytes, plugin_payload, zip_bytes


def build(url, connection, name, output, *, template=TEMPLATE, license_file=ROOT / 'LICENSE'):
    url, connection = mcp_url(url), app_id(connection)
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', name) or len(name) > 64:
        raise ValueError('Use a unique lowercase kebab-case plugin name, at most 64 characters')
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Choose a new output directory; existing output is never replaced')
    base = 'plugins/' + name + '/'
    payload = {base + path: content for path, content in plugin_payload(url, connection, name,
        template=template, license_file=license_file).items()}
    manifest = json.loads(payload[base + 'plugin.json'])
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
        '## Single-plugin upload\n\n'
        'Where ChatGPT offers a plugin archive upload, use plugin.zip. Its manifest, '
        'app reference and skills are at the archive root. Do not upload a ZIP of the '
        'whole marketplace tree: that is not a single plugin archive. Verify the '
        'imported app binding and all four skills before relying on the upload.\n\n'
        '## Individual/private setup\n\n'
        'In ChatGPT web, invoke Plugin Creator where your account permits it. Attach '
        'the packaged skill and reference files (or the source archive if the creator '
        'can inspect it). Ask it to create a private plugin from those instructions '
        'and include the exact registered C0 app above. Review the saved skills and '
        'app binding. Preserve all four distinct named skills and resolve their linked '
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
        'If project tools are available, test a read-only `project_get` and missing-tool refusal without a fallback. Test permitted maintenance in an owned fixture and Reader denial. Record '
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
        archive.write_bytes(zip_bytes({path.removeprefix(base): content
            for path, content in payload.items() if path.startswith(base)}))
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
