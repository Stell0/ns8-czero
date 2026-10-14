# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only native backup-window observer, for disposable QEMU only."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def paths(token):
    if not re.fullmatch('[0-9a-f]{32}', token):
        raise ValueError('invalid_observer_id')
    return Path('/tmp/czero-backup-observer-' + token + '.json'), Path('/tmp/czero-backup-observer-' + token + '.stop')


def copying():
    names = subprocess.run(['podman','ps','--format','{{.Names}}'], capture_output=True, text=True, timeout=3, check=True).stdout.splitlines()
    return any(name.startswith('restic-') for name in names)


def observe(token):
    output, stop = paths(token)
    state = Path(os.environ['AGENT_STATE_DIR'])
    samples = violations = 0
    deadline = time.monotonic() + 180
    while not stop.exists() and time.monotonic() < deadline:
        if (state / 'backup-metadata.json').exists() and (state / 'backup-worker-state.json').exists() and copying():
            active = any(subprocess.run(['systemctl','--user','is-active','--quiet', unit], timeout=3).returncode == 0
                for unit in ('czero.service','czero-worker.service','czero-worker.timer'))
            # Confirm the copy is still in progress after state queries; cleanup
            # may legitimately resume the app once Restic has exited.
            if copying():
                samples += 1
                violations += int(active)
        time.sleep(0.05)
    os.umask(0o077)
    output.write_text(json.dumps({'samples': samples, 'violations': violations}))


def verify(token):
    output, stop = paths(token)
    stop.touch()
    deadline = time.monotonic() + 15
    while not output.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    result = json.loads(output.read_text())
    assert result['samples'] > 0, 'Native backup copy window was not observed'
    assert result['violations'] == 0, 'Native backup allowed an active file writer during copy'
    output.unlink(); stop.unlink()
    print('Observed quiescent native backup copy samples:', result['samples'])


if __name__ == '__main__':
    try:
        if sys.argv[1] == 'observe': observe(sys.argv[2])
        elif sys.argv[1] == 'verify': verify(sys.argv[2])
        else: raise ValueError('invalid_observer_operation')
    except Exception as error:
        print(str(error) if isinstance(error, AssertionError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
