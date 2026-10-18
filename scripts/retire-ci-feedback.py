#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Retire proven old feedback without ever cancelling full acceptance."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote


def gh(*args):
    return subprocess.check_output(['gh', *map(str, args)], text=True)


def retire(selection, repo, run_id, branch):
    current = json.loads(gh('api', f'repos/{repo}/actions/runs/{run_id}'))
    number = selection.get('pr_number')
    if number:
        pr = json.loads(gh('api', f'repos/{repo}/pulls/{number}'))
        if pr['head']['sha'] != selection['source']:
            return []  # An older full run must not cancel a newer draft.
    runs = json.loads(gh('api', f'repos/{repo}/actions/workflows/validate.yml/runs?per_page=100&branch='+quote(branch, safe='')))['workflow_runs']
    cancelled = []
    for run in runs:
        if (run['id'] == int(run_id) or run['status'] == 'completed'
                or run['created_at'] >= current['created_at']
                or run['head_sha'] == selection['source']):
            continue
        with tempfile.TemporaryDirectory(prefix='c0-obsolete-feedback-') as directory:
            try:
                gh('run', 'download', run['id'], '--repo', repo, '--name', 'ci-selection', '--dir', directory)
                prior = json.loads((Path(directory)/'ci-selection.json').read_text())
            except (subprocess.CalledProcessError, OSError, ValueError):
                continue  # Missing or ambiguous evidence always preserves the run.
        if (prior.get('mode') not in {'docs', 'scoped'} or prior.get('pr_number') != number
                or prior.get('source') != run['head_sha'] or prior.get('event') not in {'push', 'pull_request'}):
            continue
        # Re-read after downloading; never cancel a run that finished meanwhile.
        latest = json.loads(gh('api', f'repos/{repo}/actions/runs/{run["id"]}'))
        if latest['status'] != 'completed':
            try:
                gh('api', '--method', 'POST', f'repos/{repo}/actions/runs/{run["id"]}/cancel')
            except subprocess.CalledProcessError:
                latest = json.loads(gh('api', f'repos/{repo}/actions/runs/{run["id"]}'))
                if latest['status'] == 'completed':
                    continue
                raise
            cancelled.append(run['id'])
    return cancelled


if __name__ == '__main__':
    selection = json.loads(Path('ci-selection.json').read_text())
    assert selection['mode'] == 'full'
    cancelled = retire(selection, os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID'],
        os.environ.get('GITHUB_HEAD_REF') or os.environ['GITHUB_REF_NAME'])
    print(json.dumps({'retired_development_runs': cancelled, 'full_runs_preserved': True}))
