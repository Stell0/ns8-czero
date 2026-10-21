# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare the real default image's installed Core to its committed Git lock."""
import importlib.metadata
import importlib.util
import json
import re
import sys
from czero_core import core_version

version, commit = sys.argv[1:]
assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version)
assert re.fullmatch(r'[0-9a-f]{40}', commit)
package = importlib.metadata.distribution('czero-core')
assert package.version == core_version == version
source = json.loads(package.read_text('direct_url.json'))
assert source['url'] == 'https://github.com/Stell0/ns8-czero.git'
assert source['vcs_info']['vcs'] == 'git'
assert source['vcs_info']['commit_id'] == commit
assert source['subdirectory'] == 'packages/czero-core'
assert importlib.util.find_spec('agent') is None
print('Released image Core matches committed version and immutable Git source; no NS8 SDK')
