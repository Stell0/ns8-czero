#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bind the complete-diff policy to trusted GitHub event identities."""
import json
import os
from pathlib import Path
import subprocess

from ci_policy import SHA, classify, git_changes, validation_mode

event_name = os.environ['GITHUB_EVENT_NAME']
event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
pr = event.get('pull_request') if event_name == 'pull_request' else None
requested = event.get('inputs', {}).get('pr_number', '')
if event_name == 'workflow_dispatch' and requested:
    if not str(requested).isdigit() or int(requested) <= 0:
        raise SystemExit('Invalid manual PR number')
    pr = json.loads(subprocess.check_output(['gh', 'api', 'repos/'+os.environ['GITHUB_REPOSITORY']+
        '/pulls/'+str(int(requested))], text=True))
if pr:
    assert source == pr['head']['sha'], 'Dispatch the exact current PR head ref'
    base = pr['base']['sha']
    number, draft = pr['number'], pr['draft']
else:
    assert source == os.environ['GITHUB_SHA'], 'Checkout differs from event source'
    base = event.get('before', '')
    if not SHA.fullmatch(base) or set(base) == {'0'}:
        base = subprocess.check_output(['git', 'rev-parse', 'HEAD^'], text=True).strip()
    number, draft = None, False
selected = classify(git_changes(base, source, pr=pr is not None))
selected.update(source=source, base=base, draft=draft, event=event_name, pr_number=number)
selected['mode'] = validation_mode(selected['kind'], selected['feedback'], event_name, draft)
if event_name == 'push' and event.get('ref', '').startswith('refs/tags/'):
    selected['mode'] = 'full'
Path('ci-selection.json').write_text(json.dumps(selected, indent=2)+'\n')
with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
    for key in ('source', 'base', 'kind', 'feedback', 'mode'):
        out.write(key+'='+selected[key]+'\n')
    out.write('pr_number='+str(number or '')+'\n')
print(json.dumps(selected, indent=2))
