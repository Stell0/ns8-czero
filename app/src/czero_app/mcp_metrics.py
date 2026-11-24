# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Expose aggregate tool outcomes to the module collector through a container-local file."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

METRICS_FILE = Path('/tmp/czero-mcp-counts.json')


class ToolCounts:
    def __init__(self, path):
        self.path = path
        self.counts = {'success': 0, 'error': 0}
        self.publish()

    def record(self, *, is_error):
        self.counts['error' if is_error else 'success'] += 1
        self.publish()

    def publish(self):
        temporary = None
        try:
            with NamedTemporaryFile(dir=self.path.parent, delete=False, mode='w', encoding='ascii') as output:
                temporary = Path(output.name)
                json.dump(self.counts, output)
            temporary.replace(self.path)
        except OSError:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


def module_tool_counts():
    if os.getenv('CZERO_MODULE_ID'):
        return ToolCounts(METRICS_FILE)
    return None
