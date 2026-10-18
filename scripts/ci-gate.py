#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Create acceptance proof from this run's actual jobs, never from old statuses."""
import json
import os
from pathlib import Path
import subprocess

from ci_policy import classify, git_changes, verify_gate


selection = json.loads(Path('ci-selection.json').read_text())
source, base = selection['source'], selection['base']
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == source
actual = classify(git_changes(base, source, pr=selection.get('pr_number') is not None))
assert actual['diff_hash'] == selection['diff_hash'] and actual['kind'] == selection['kind']
draft = selection['draft']
if selection.get('pr_number') is not None:
    pr = json.loads(subprocess.check_output(['gh', 'api', 'repos/'+os.environ['GITHUB_REPOSITORY']+
        '/pulls/'+str(selection['pr_number'])], text=True))
    assert pr['head']['sha'] == source and pr['base']['sha'] == base, 'PR changed during validation'
    subprocess.run(['git', 'merge-base', '--is-ancestor', base, source], check=True)
    draft = pr['draft']
jobs = {key: value['result'] for key, value in json.loads(os.environ['CI_NEEDS']).items()}
images = native = False
if selection['mode'] == 'full':
    image_proof = json.loads(Path('candidate-images.json').read_text())
    native_proof = json.loads(Path('native-acceptance.json').read_text())
    images = image_proof['source'] == source and len(image_proof['images']) == 3
    native = native_proof['source'] == source and native_proof['accepted'] is True
proof = {**selection, 'draft': draft, 'jobs': jobs,
         'run_id': int(os.environ['GITHUB_RUN_ID']), 'run_attempt': int(os.environ['GITHUB_RUN_ATTEMPT']),
         'images_verified': images, 'native_verified': native}
Path('ci-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
verify_gate(proof, source, base, actual['diff_hash'])
print('C0 merge acceptance verified for '+source+' ('+selection['mode']+')')
