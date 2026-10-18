#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Run one serial, database-isolated feedback selection without shell expansion."""
import json
from pathlib import Path
import subprocess
import sys

selection = json.loads(Path(sys.argv[1]).read_text())
broad = selection['feedback'] == 'broad'
tests = ['app/tests', 'packages/czero-core/tests', 'tests/unit', 'tests/integration', 'tests/packaging'] if broad else selection['pytest']
if not broad and (not tests or any(not Path(p.split('::', 1)[0]).is_file() or
        not p.startswith(('tests/', 'app/tests/')) for p in tests)):
    raise SystemExit('Invalid or missing selected test; broad validation is required')
subprocess.run([sys.executable, '-m', 'pytest', '-q', *tests], check=True)
if broad or selection['node']:
    subprocess.run(['node', '--test', *map(str, sorted(Path('tests/ui').glob('*.cjs')))], check=True)
if selection['vue']:
    subprocess.run(['corepack', 'enable'], check=True)
    subprocess.run(['yarn', 'install', '--immutable'], cwd='ui', check=True)
    subprocess.run(['yarn', 'build'], cwd='ui', check=True)
if broad:
    subprocess.run(['go', 'run', 'tests/check_schemas.go'], check=True)
    subprocess.run(['bash', '-n', 'build-images.sh',
        'imageroot/actions/configure-module/80start_services', 'imageroot/actions/create-module/40scheduler',
        'imageroot/update-module.d/60scheduler', 'imageroot/update-module.d/80restart'], check=True)
    subprocess.run(['robot', '--dryrun', '--exclude', 'ui', '-v', 'NODE_ADDR:disposable.invalid',
        '-v', 'IMAGE_URL:ghcr.io/stell0/czero:main', '-d', '/tmp/robot-dryrun', 'tests'], check=True)
