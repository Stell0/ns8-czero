#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Require current GitHub acceptance proof before merge, release or deployment."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from ci_policy import EMPTY_TREE, SHA, classify, git_changes, required_jobs, verify_gate


def gh(*args):
    return subprocess.check_output(['gh', *map(str, args)], text=True)


def accepted_source(repo, source, *, pr_number=None, require_full=False):
    if not SHA.fullmatch(source):
        raise ValueError('invalid_promotion_source')
    current_pr = json.loads(gh('api', 'repos/'+repo+'/pulls/'+str(pr_number))) if pr_number else None
    if current_pr and (current_pr['head']['sha'] != source or current_pr['draft'] or current_pr['state'] != 'open'):
        raise ValueError('current_ready_PR_required')
    runs = json.loads(gh('run', 'list', '--repo', repo, '--workflow', 'validate.yml',
        '--commit', source, '--limit', '50', '--json', 'databaseId,headSha,status,conclusion'))
    for run in runs:
        if run['headSha'] != source or run['status'] != 'completed' or run['conclusion'] != 'success':
            continue
        with tempfile.TemporaryDirectory(prefix='c0-acceptance-') as directory:
            gh('run', 'download', run['databaseId'], '--repo', repo, '--name', 'ci-acceptance-proof', '--dir', directory)
            proof = json.loads((Path(directory)/'ci-proof.json').read_text())
        if proof.get('run_id') != run['databaseId'] or (require_full and proof.get('mode') != 'full'):
            continue
        base = current_pr['base']['sha'] if current_pr else proof['base']
        if not SHA.fullmatch(base):
            raise ValueError('invalid_promotion_base')
        git = ['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential']
        if subprocess.check_output(['git', 'rev-parse', '--is-shallow-repository'], text=True).strip() == 'true':
            subprocess.run([*git, 'fetch', '--no-tags', '--unshallow', 'origin'], check=True)
        subprocess.run([*git, 'fetch', '--no-tags', 'origin', source, *([base] if base != EMPTY_TREE else [])], check=True)
        selected = classify(git_changes(base, source, pr=proof.get('pr_number') is not None))
        if selected['kind'] != proof['kind']:
            raise ValueError('promotion_classification_changed')
        verify_gate(proof, source, base, selected['diff_hash'], require_full=require_full)
        if current_pr:
            subprocess.run(['git', 'merge-base', '--is-ancestor', base, source], check=True)
        jobs = json.loads(gh('api', 'repos/'+repo+'/actions/runs/'+str(run['databaseId'])+'/jobs?per_page=100'))['jobs']
        assert any(j['name'] == 'C0 merge gate' and j['conclusion'] == 'success' for j in jobs)
        for name in required_jobs(proof['kind'], proof['mode']):
            matches = [j for j in jobs if j['name'] == name or j['name'].startswith(name+' /')]
            if not matches or any(j['status'] != 'completed' or j['conclusion'] != 'success' for j in matches):
                raise ValueError('actual_required_jobs_missing')
        return proof
    raise ValueError('successful_current_acceptance_not_found')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'Stell0/ns8-czero'))
    p.add_argument('--source', required=True)
    p.add_argument('--pr', type=int)
    p.add_argument('--full', action='store_true', help='Required for Core release and runtime deployment')
    p.add_argument('--output')
    args = p.parse_args()
    proof = accepted_source(args.repo, args.source, pr_number=args.pr, require_full=args.full)
    if args.output:
        Path(args.output).write_text(json.dumps(proof, indent=2)+'\n')
    print('Verified '+proof['mode']+' acceptance for '+args.source+' in run '+str(proof['run_id']))


if __name__ == '__main__':
    main()
