# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare the real default image's installed Core to its committed Git lock."""
import importlib.metadata
import importlib.util
import json
import re
import sys
from czero_core import core_version
from czero_core.database import SCHEMA_REVISION
from czero_core.current_content import ContentSuperseded
from czero_core.retention import preflight
from czero_core.documents import DocumentService

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
assert SCHEMA_REVISION == '0023_current_content'
assert str(ContentSuperseded()) == 'content_superseded'
assert callable(preflight) and callable(DocumentService.read_document)
print('Released image Core matches immutable Git lock and latest-only schema/contracts; no NS8 SDK')
