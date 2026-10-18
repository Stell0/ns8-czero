#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Publish canonical main aliases only from a fully accepted immutable candidate."""
import json
import os
from pathlib import Path
import re
import subprocess

from ci_policy import classify, git_changes, verify_gate

proof = json.loads(Path('ci-proof.json').read_text())
verify_gate(proof, proof['source'], proof['base'], proof['diff_hash'], require_full=True)
tag = os.environ.get('C0_RELEASE_TAG', '')
if tag:
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', tag) or tag.startswith('core-v'):
        raise SystemExit('Invalid module release tag')
    current = json.loads(subprocess.check_output(['gh', 'api', 'repos/'+os.environ['GITHUB_REPOSITORY']+
        '/commits/'+tag], text=True))['sha']
else:
    current = json.loads(subprocess.check_output(['gh', 'api', 'repos/'+os.environ['GITHUB_REPOSITORY']+
        '/git/ref/heads/main'], text=True))['object']['sha']
if current != proof['source']:
    if tag:
        raise SystemExit('Release tag changed: canonical publication blocked')
    # A lightweight documentation merge must not strand an in-flight accepted
    # runtime candidate. Its runtime/build tree remains exactly the accepted one.
    subprocess.run(['git', '-c', 'credential.helper=', '-c',
        'credential.helper=!gh auth git-credential', 'fetch', '--no-tags', 'origin', current], check=True)
    subprocess.run(['git', 'merge-base', '--is-ancestor', proof['source'], current], check=True)
    if classify(git_changes(proof['source'], current, pr=False))['kind'] != 'docs':
        raise SystemExit('Main runtime advanced: canonical publication blocked')
candidate = json.loads(Path('candidate-images.json').read_text())
assert candidate['source'] == proof['source']
# Dependency aliases first, module last. The module itself keeps immutable
# candidate sibling tags; another main run cannot replace its tested inputs.
for image in [*candidate['images'][1:], candidate['images'][0]]:
    repository = image['reference'].rsplit(':', 1)[0]
    for alias in ((tag,) if tag else ('main', 'latest')):
        subprocess.run(['skopeo', 'copy', '--all', '--preserve-digests',
            'docker://'+repository+'@'+image['digest'], 'docker://'+repository+':'+alias], check=True)
    result = json.loads(subprocess.check_output(['skopeo', 'inspect', 'docker://'+repository+':'+(tag or 'main')], text=True))
    assert result['Digest'] == image['digest'] and result['Labels']['org.opencontainers.image.revision'] == proof['source']
Path('main-publication.json').write_text(json.dumps({'source': proof['source'], 'images': candidate['images'],
    'publication_ref_commit': current, 'documentation_descendant': current != proof['source'],
    'aliases': [tag] if tag else ['main', 'latest'], 'canonical_aliases_verified': True}, indent=2)+'\n')
print('Canonical aliases match fully accepted candidate identities')
