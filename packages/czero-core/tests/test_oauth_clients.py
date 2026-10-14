# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from czero_core.oauth_clients import redirect_uri


@pytest.mark.parametrize('value', [
    'https://client.example.test/callback', 'http://127.0.0.1:3456/callback',
    'http://localhost:3456/callback', 'http://[::1]:3456/callback'])
def test_registered_callbacks_preserve_exact_https_and_loopback_uris(value):
    assert redirect_uri(value) == value


@pytest.mark.parametrize('value', [
    'http://client.example.test/callback', 'http://localhost.evil.test/callback',
    'https://user:password@client.example.test/callback', 'https://client.example.test/*',
    'https://client.example.test/callback?token=private', 'https://client.example.test/callback#fragment',
    'https://client.example.test/callback?', 'https://client.example.test/callback#',
    'https://client.example.test:invalid/callback', 'https://client.example.test:0/callback',
    'https://client.example.test/ callback', 'https://client.example.test/\\callback', None, 42])
def test_callbacks_reject_nonloopback_http_wildcards_credentials_and_ambiguous_values(value):
    with pytest.raises(ValueError, match='^invalid_redirect_uri$'):
        redirect_uri(value)
