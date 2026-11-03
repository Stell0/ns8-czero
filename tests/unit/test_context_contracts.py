# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from czero_app.document_context import BundleRequest,install_context_routes
from czero_core.document_units import text_blocks
from czero_core.extraction import ExtractionError


def test_old_released_core_does_not_advertise_unavailable_context_operations():
    assert install_context_routes(None,object(),None,None) is False


def test_lazy_metadata_derivation_is_bounded_before_allocation():
    with pytest.raises(ExtractionError,match='too_large'):
        text_blocks('\n'*10000+'Visible',True,max_boundaries=4002)
    assert text_blocks('```\n'+'\n'*10000+'```\n',True,max_boundaries=4002)[1]==[]


def test_bundle_schema_does_not_accept_an_executable_plan_or_budget_boolean():
    from pydantic import ValidationError
    with pytest.raises(ValidationError): BundleRequest.model_validate({'plan':[],'command':'untrusted'})
    with pytest.raises(ValidationError): BundleRequest.model_validate({'plan':[],'max_tokens':True})


def test_context_errors_are_closed_and_never_echo_unexpected_details():
    from czero_app.context_errors import mcp_context_error
    assert mcp_context_error('source_document_outline_get',404,'source_not_found')==('source_not_found',404)
    assert mcp_context_error('source_document_sections_get',422,'PRIVATE_CONTEXT_CANARY')==('service_unavailable',503)
    assert mcp_context_error('unregistered',404,'source_not_found') is None
