# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from unittest.mock import patch
import pytest
from c0_ingest.auth import credentials
from c0_ingest.errors import C0Error


def test_api_key_never_refreshes_or_creates_credential_files(monkeypatch):
    monkeypatch.setenv('C0_API_KEY', 'c0k_'+'a'*43)
    with patch('c0_ingest.auth.open_url') as network:
        assert credentials({'auth_mode':'api_key'})=='c0k_'+'a'*43
        network.assert_not_called()
    monkeypatch.delenv('C0_API_KEY')
    with pytest.raises(C0Error): credentials({'auth_mode':'api_key'})
