# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Run both full crawl entry paths with an independent synthetic GitHub API."""
import base64
import copy
import hashlib
from pathlib import Path
import pytest
from c0_ingest.jobs import init_job
from c0_ingest.state import read
from github_vault.config import load, parser
from github_vault.scrape import scrape
from github_vault.models import validate


@pytest.mark.parametrize('pilot', [False, True])
def test_crawl_uses_configured_pilot_snapshot_hashes_and_resume(tmp_path, monkeypatch, pilot):
    job = tmp_path / 'job'
    init_job(job)
    config = load(job / 'config/source.toml')
    config['github']['external_discovery'] = False
    body = b'# Example\n\nIndependent original GitHub evidence.\n'
    calls = []
    repo = {'id': 7, 'full_name': 'acme/example-project', 'html_url': 'https://github.com/acme/example-project',
            'owner': {'id': 8, 'login': 'acme', 'type': 'Organization'}, 'private': False,
            'fork': False, 'archived': False, 'default_branch': 'main', 'stargazers_count': 0}

    class API:
        def __init__(self, *args, **kwargs):
            self.token, self.requests, self.cached = None, 0, 0

        def get(self, path, params=None):
            calls.append(path); self.requests += 1
            if path == '/repos/acme/example-project':
                return copy.deepcopy(repo), None
            if path.endswith('/commits/main'):
                return {'sha': 'a' * 40}, None
            if path.endswith('/readme'):
                return {'path': 'README.md'}, None
            if '/git/trees/' in path:
                return {'tree': [{'type': 'blob', 'path': 'README.md', 'sha': 'b' * 40, 'size': len(body)}]}, None
            if '/git/blobs/' in path:
                return {'encoding': 'base64', 'content': base64.b64encode(body).decode()}, None
            if path.endswith('/languages'):
                return {'Python': 10}, None
            pytest.fail('unexpected GitHub request ' + path)

        def pages(self, path, params=None):
            calls.append(path); self.requests += 1
            if path == '/orgs/acme/repos':
                return iter([copy.deepcopy(repo)])
            if path.endswith('/commits'):
                return iter([{'sha': 'c' * 40, 'author': {'id': 1, 'login': 'alice', 'type': 'User', 'html_url': 'https://github.com/alice'},
                              'html_url': 'https://github.com/acme/example-project/commit/' + 'c' * 40,
                              'commit': {'author': {'date': '2025-01-01T00:00:00Z'}, 'committer': {'date': '2025-01-01T00:00:00Z'}}}])
            return iter([])

        def search(self, *args, **kwargs):
            return []

    monkeypatch.setattr('github_vault.scrape.GitHub', API)
    flags = ['--config', str(job / 'config/source.toml'), '--resume', '--limit-repos', '1']
    if pilot:
        flags.append('--pilot')
    args = parser('fixture', 'scrape').parse_args(flags)
    first, code = scrape(config, args)
    assert code == 2 and first['status'] == 'partial'
    manifest, records = validate(first['snapshot'])
    assert manifest['counts']['repositories'] == 1 and manifest['counts']['documents'] == 1
    assert records['documents'][0]['sha256'] == hashlib.sha256(body).hexdigest()
    assert (Path(first['snapshot']) / records['documents'][0]['content_path']).read_bytes() == body
    assert records['people'][0]['login'] == 'alice'
    first_calls = list(calls)
    calls.clear()
    second, code = scrape(config, args)
    assert code == 2 and second['snapshot'] != first['snapshot']
    assert not any('/git/blobs/' in path for path in calls)
    assert read(Path(config['paths']['snapshots']) / 'latest.json')['snapshot_id'] == Path(second['snapshot']).name
    assert any('/git/blobs/' in path for path in first_calls)
