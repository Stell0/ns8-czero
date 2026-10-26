#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Check a complete contribution for common private artifacts; still review its diff."""
import argparse
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b')
LITERAL = re.compile(r'''["']?(?:access_token|refresh_token|client_secret|password)["']?\s*[:=]\s*["']([^"'\n]+)["']''', re.I)
URL = re.compile(r'https?://[^\s<>"\'`)]+')


def issues(path, text, forbidden=()):
    result = set()
    p = Path(path)
    if any(part in ('.local', '.cache') for part in p.parts) or p.name in ('.env', 'oauth.json', 'auth.json', 'credentials.json'):
        result.add('private artifact')
    if SECRET.search(text):
        result.add('credential-shaped material')
    for match in LITERAL.finditer(text):
        if not (path.startswith('tests/') and re.search(r'synthetic|fixture|unit-only|test-', match[1], re.I)):
            result.add('literal credential; inspect manually')
    for match in URL.finditer(text):
        url = urlsplit(match[0].rstrip('.,;'))
        if url.username or url.password:
            result.add('URL credentials')
        host = url.hostname or ''
        if url.path == '/mcp' and not any(host == suffix or host.endswith('.' + suffix) for suffix in ('example.org', 'example.com', 'example.net', 'example', 'test', 'invalid')):
            result.add('non-example instance URL')
    if any(value and value in text for value in forbidden):
        result.add('private value from operator denylist')
    return sorted(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='origin/main', help='Verified original C0 main ref/full SHA')
    p.add_argument('--forbidden-file', type=Path, help='Private mode-0600 file: one value per line; values never printed')
    args = p.parse_args()
    paths = set()
    for commands in (['git', 'diff', '--name-only', '-z', args.base, 'HEAD', '--'],
                     ['git', 'diff', '--name-only', '-z', 'HEAD', '--'],
                     ['git', 'ls-files', '--others', '--exclude-standard', '-z']):
        paths.update(v for v in subprocess.check_output(commands, cwd=ROOT).decode().split('\0') if v)
    forbidden = []
    if args.forbidden_file:
        if args.forbidden_file.stat().st_mode & 0o077:
            raise SystemExit('Private denylist must have mode 0600')
        forbidden = args.forbidden_file.read_text().splitlines()
    failures, checked = [], 0
    for relative in sorted(paths):
        path = ROOT / relative
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            failures.append((relative, ['unexpected file type/size']))
            continue
        try:
            text = path.read_text()
        except UnicodeError:
            failures.append((relative, ['binary input requires explicit review']))
            continue
        checked += 1
        problem = issues(relative, text, forbidden)
        if problem:
            failures.append((relative, problem))
    for path, problem in failures:
        print(path + ': ' + '; '.join(problem))
    if failures:
        raise SystemExit('Public contribution needs privacy review; no private values printed')
    print(f'Public contribution checks pass for {checked} files; complete diff review is still required')


if __name__ == '__main__':
    main()
