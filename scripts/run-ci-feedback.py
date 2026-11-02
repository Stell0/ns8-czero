#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Run bounded fast checks without database or browser fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
from ci_policy import FAST_TESTS

selection = json.loads(Path(sys.argv[1]).read_text())
selected = selection['pytest']
if selected != FAST_TESTS or any(not Path(path).exists() for path in selected):
    raise SystemExit('Invalid or missing fast test selection')
subprocess.run([sys.executable, '-m', 'pytest', '-q', *selected], check=True)
subprocess.run(['node', '--test', *map(str, sorted(Path('tests/ui').glob('*.cjs')))], check=True)
if selection['vue']:
    subprocess.run(['corepack', 'enable'], check=True)
    subprocess.run(['yarn', 'install', '--immutable'], cwd='ui', check=True)
    subprocess.run(['yarn', 'build'], cwd='ui', check=True,
                   env={**os.environ, 'NODE_OPTIONS': '--openssl-legacy-provider'})
subprocess.run(['go', 'run', 'tests/check_schemas.go'], check=True)
for script in ('build-images.sh', 'imageroot/actions/configure-module/80start_services',
               'imageroot/actions/create-module/40scheduler',
               'imageroot/update-module.d/60scheduler', 'imageroot/update-module.d/80restart'):
    subprocess.run(['bash', '-n', script], check=True)
subprocess.run(['robot', '--dryrun', '--exclude', 'ui', '-v', 'NODE_ADDR:disposable.invalid',
    '-v', 'IMAGE_URL:ghcr.io/stell0/czero:main', '-d', '/tmp/robot-dryrun', 'tests'], check=True)
