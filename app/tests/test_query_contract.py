# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import runpy
import sys

from pydantic import TypeAdapter,ValidationError
import pytest
import czero_app.retrieval


def test_producer_query_schema_and_runtime_enforce_normalized_bounds():
    query=TypeAdapter(czero_app.retrieval.SearchQuery)
    assert query.json_schema()['maxLength']==8192
    assert query.validate_python(' '*600+'alpha\nrecovery')=='alpha recovery'
    with pytest.raises(ValidationError):query.validate_python('a'*513)


def test_released_core_without_normalizer_keeps_its_existing_query_contract(monkeypatch):
    monkeypatch.setitem(sys.modules,'czero_core.search_query',None)
    namespace=runpy.run_path(str(Path(czero_app.retrieval.__file__)))
    query=TypeAdapter(namespace['SearchQuery'])
    assert query.json_schema()['maxLength']==512
    assert query.validate_python('alpha recovery')=='alpha recovery'
    with pytest.raises(ValidationError):query.validate_python('a'*513)
