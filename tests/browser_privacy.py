# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep disposable browser internals out of published test diagnostics."""
import os
from html import unescape
from pathlib import Path
import re


def configure_browser_diagnostics():
    # Browser 19.14.2's supported Pino setting is inherited by its lazy
    # Node subprocess. INFO dumps complete browser/response objects, including
    # OAuth Location headers. Robot assertions and bounded Python errors remain.
    os.environ['ROBOT_FRAMEWORK_BROWSER_PINO_LOG_LEVEL'] = 'silent'


configure_browser_diagnostics()


def assert_no_oauth_queries(paths):
    for path in paths:
        path = Path(path)
        if path.exists() and re.search(r'[?&](?:state|nonce|code_challenge|code|access_token|id_token)=',
                unescape(path.read_text(errors='replace'))):
            raise AssertionError('OAuth query values entered browser test output')
