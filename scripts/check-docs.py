#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Lightweight checks only for the reviewed, non-packaged document allowlist."""
import json
from pathlib import Path
import re
import subprocess
import sys

from ci_policy import DOCS, classify_source
from documentation import check

selection = json.loads(Path(sys.argv[1]).read_text())
actual = classify_source(selection['base'], selection['source'],
                         pr=selection.get('pr_number') is not None or selection.get('event') == 'pull_request')
if (actual['kind'] != 'docs' or selection['kind'] != 'docs' or
        any(actual[key] != selection[key] for key in ('paths', 'diff_hash'))):
    raise SystemExit('Documentation exemption denied')
subprocess.run(['git', 'diff', '--check', selection['base'], selection['source'], '--'], check=True)
for name in selection['paths']:
    path = Path(name)
    if not path.exists():  # Deletions are reviewed by the same complete diff.
        continue
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
        raise SystemExit('Invalid document: ' + name)
    text = path.read_text(encoding='utf-8')
    if '\0' in text or re.search(r'^(?:<<<<<<<|=======|>>>>>>>)\s', text, re.M):
        raise SystemExit('Invalid document text: ' + name)
check([name for name in selection['paths'] if name in DOCS and Path(name).exists()])
print('Reviewed documentation allowlist, UTF-8, diff and local links pass')
