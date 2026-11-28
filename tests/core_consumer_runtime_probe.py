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
from czero_core.extraction import MAX_PDF_BYTES, MAX_PDF_PAGES
from czero_core.api_keys import ApiKeyService, ApiKeyBinding
from czero_core.oauth_clients import OAuthClientService

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
assert SCHEMA_REVISION == '0048_consent_flows'
from czero_core.oauth_consent import OAuthConsentService
from czero_core.sessions import SessionService
assert OAuthConsentService.supports_session_only is True
assert callable(OAuthConsentService.review)
assert callable(SessionService.claim_browser_login)
from czero_core.pdf_access import PdfAccess
from czero_core.protected_pdf import inspect_pdf
from czero_core.sources import SourceService
assert callable(PdfAccess.check) and callable(inspect_pdf)
assert callable(SourceService.ingest_manual) and callable(SourceService.retry_pdf)
assert (MAX_PDF_BYTES, MAX_PDF_PAGES) == (104857600, 2000)
assert str(ContentSuperseded()) == 'content_superseded'
assert callable(ApiKeyService.verify) and callable(ApiKeyBinding.validate)
assert callable(preflight) and callable(DocumentService.read_document)
assert OAuthClientService.redirect_uri_matches(
    'http://localhost:53123/callback', ('http://localhost/callback',))
assert not OAuthClientService.redirect_uri_matches(
    'http://127.0.0.1:53123/callback', ('http://localhost/callback',))
assert not OAuthClientService.redirect_uri_matches(
    'http://localhost:53124/callback', ('http://localhost:53123/callback',))
assert importlib.util.find_spec('czero_core.compilation') is not None
assert importlib.util.find_spec('czero_core.bm25') is not None
from fastapi import FastAPI
from czero_core.compilation import CompilationService
from czero_app.operations import OperationCatalog
from czero_app.compilation import install as install_compilation
from czero_core.cross_space_references import CrossSpaceReferenceService
from czero_app.cross_space_references import install as install_references
application = FastAPI()
application.state.operation_catalog = OperationCatalog(None)
# Binding the released API must require neither a database nor model execution.
install_compilation(application, None, None, lambda: None, lambda: None)
assert isinstance(application.state.compilation, CompilationService)
assert len([route for route in application.routes
            if route.path.startswith('/api/v1/compilation/')]) == 19
install_references(application, None, None, lambda: None, lambda: None)
assert isinstance(application.state.cross_space_references, CrossSpaceReferenceService)
assert len([route for route in application.routes
            if route.path == '/api/v1/cross-space-references']) == 3
from czero_core.spaces import SpaceService
from czero_core.client_onboarding import ClientOnboardingService
from czero_app.spaces import install_space_routes
install_space_routes(application, None, None, lambda: None, lambda: None)
assert isinstance(application.state.spaces, SpaceService)
assert callable(SpaceService.set_access) and callable(ClientOnboardingService.register_reader)
assert len([route for route in application.routes
            if route.path == '/api/v1/spaces/{space_id}/access']) == 1
from czero_core.automatic_sources import AutomaticSourceService
from czero_app.automatic_sources import install as install_automatic_sources
install_automatic_sources(application, None, None, lambda: None, lambda: None)
assert isinstance(application.state.automatic_sources, AutomaticSourceService)
assert callable(AutomaticSourceService.preview_drive) and callable(AutomaticSourceService.save_drive)
public_routes=[route for route in application.routes if route.path.startswith('/api/v1/automatic-sources')
               and not route.path.startswith('/api/v1/automatic-sources/google-drive/')]
assert len(public_routes) == 6
assert application.state.google_drive is None
print('Released image Core matches immutable Git lock, schema, OAuth flow and native loopback contracts; no NS8 SDK')
