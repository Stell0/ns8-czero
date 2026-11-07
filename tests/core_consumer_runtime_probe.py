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
from czero_core.api_keys import ApiKeyService, ApiKeyBinding

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
assert SCHEMA_REVISION == '0034_compilation_maintenance'
assert str(ContentSuperseded()) == 'content_superseded'
assert callable(ApiKeyService.verify) and callable(ApiKeyBinding.validate)
assert callable(preflight) and callable(DocumentService.read_document)
assert importlib.util.find_spec('czero_core.compilation') is not None
from fastapi import FastAPI
from czero_core.compilation import CompilationService
from czero_app.operations import OperationCatalog
from czero_app.compilation import install as install_compilation
application = FastAPI()
application.state.operation_catalog = OperationCatalog(None)
# Binding the released API must require neither a database nor model execution.
install_compilation(application, None, None, lambda: None, lambda: None)
assert isinstance(application.state.compilation, CompilationService)
assert len([route for route in application.routes
            if route.path.startswith('/api/v1/compilation/')]) == 19
print('Released image Core matches immutable Git lock and latest-only schema/contracts; no NS8 SDK')
