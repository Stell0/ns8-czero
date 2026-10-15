# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable-only checks of effective container security and cgroup limits."""
import json
import subprocess


# Read only numeric process/cgroup data, never container configuration or env.
COMMAND = """set -eu
printf 'uid '; id -u
awk '/^(NoNewPrivs|CapEff):/ {print $1, $2}' /proc/self/status
printf 'memory '; cat /sys/fs/cgroup/memory.max
printf 'swap '; cat /sys/fs/cgroup/memory.swap.max
printf 'cpu '; cat /sys/fs/cgroup/cpu.max
printf 'pids '; cat /sys/fs/cgroup/pids.max
rss=0
for status in /proc/[0-9]*/status; do
    value=$(awk '/^VmRSS:/ {print $2}' "$status" 2>/dev/null) || continue
    rss=$((rss + ${value:-0}))
done
printf 'rss_kib %s\n' "$rss"
"""


def validate(output, rss_limit_kib):
    if not isinstance(output, str) or len(output) > 4096:
        raise AssertionError('Invalid bounded runtime measurement')
    fields = {}
    try:
        for line in output.splitlines():
            key, value = line.split(maxsplit=1)
            if key in fields:
                raise ValueError()
            fields[key] = value
        if set(fields) != {'uid', 'NoNewPrivs:', 'CapEff:', 'memory', 'swap', 'cpu', 'pids', 'rss_kib'}:
            raise ValueError()
        uid = int(fields['uid'])
        privileges = int(fields['NoNewPrivs:'])
        capabilities = int(fields['CapEff:'], 16)
        memory = int(fields['memory'])
        swap = int(fields['swap'])
        quota, period = (int(value) for value in fields['cpu'].split())
        pids = int(fields['pids'])
        rss = int(fields['rss_kib'])
    except (ValueError, TypeError):
        raise AssertionError('Invalid bounded runtime measurement') from None
    if not (uid > 0 and privileges == 1 and capabilities == 0):
        raise AssertionError('Container privilege protection is missing')
    if not (memory == 1024**3 and swap == 1024**3 and period > 0
            and quota == 2 * period and pids == 256):
        raise AssertionError('Effective container resource bounds differ')
    if not 0 < rss <= rss_limit_kib:
        raise AssertionError('Container resident-memory target exceeded')
    return {'memory_bytes': memory, 'swap_bytes': swap, 'cpus': 2,
            'tasks': pids, 'rss_kib': rss, 'nonroot': True,
            'no_new_privileges': True, 'effective_capabilities': 0}


def probe(run=subprocess.run):
    measurements = {}
    for container, limit in [('czero', 256 * 1024), ('czero-postgres', 384 * 1024)]:
        try:
            result = run(['podman', 'exec', container, 'sh', '-ec', COMMAND],
                         capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise AssertionError('Runtime measurement unavailable') from None
        if result.returncode:
            raise AssertionError('Runtime measurement unavailable')
        measurements[container] = validate(result.stdout, limit)
    return measurements


if __name__ == '__main__':
    print(json.dumps(probe(), sort_keys=True))
