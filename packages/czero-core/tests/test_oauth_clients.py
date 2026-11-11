# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from czero_core.oauth_clients import OAuthClientService, redirect_uri


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


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1', '[::1]'])
@pytest.mark.parametrize('port', [1, 53123, 65535])
def test_portless_http_loopback_registration_accepts_requested_port(host, port):
    registered = ['http://' + host + '/callback']
    callback = 'http://' + host + ':' + str(port) + '/callback'
    assert OAuthClientService.redirect_uri_matches(callback, registered)
    assert registered == ['http://' + host + '/callback']


@pytest.mark.parametrize('registered,callback', [
    ('http://localhost/callback', 'http://127.0.0.1:53123/callback'),
    ('http://127.0.0.1/callback', 'http://[::1]:53123/callback'),
    ('http://localhost/callback', 'http://localhost.evil.test:53123/callback'),
    ('http://localhost/callback', 'http://localhost:53123/other'),
    ('http://localhost/callback', 'http://localhost:53123/callback/'),
    ('http://localhost/callback', 'http://localhost:53123/%63allback'),
    ('http://localhost/callback', 'http://localhost:53123/callback?'),
    ('http://localhost/callback', 'http://localhost:53123/callback#'),
    ('http://localhost/callback', 'http://user@localhost:53123/callback'),
    ('http://localhost/callback', 'https://localhost:53123/callback'),
    ('http://localhost/callback', 'http://localhost:0/callback'),
    ('http://localhost/callback', 'http://localhost:65536/callback'),
    ('http://localhost/callback', 'http://localhost:invalid/callback'),
    ('http://localhost/callback', 'http://localhost:53123/call\\back'),
    ('http://localhost/callback', 'http://localhost:53123/call\nback'),
    ('http://localhost/callback', None),
    ('http://localhost/callback', 42),
    ('http://localhost:53123/callback', 'http://localhost:53124/callback'),
    ('http://localhost:53123/callback', 'http://localhost/callback'),
    ('https://client.example.test/callback', 'https://client.example.test:53123/callback'),
    ('https://localhost/callback', 'https://localhost:53123/callback'),
    ('https://127.0.0.1/callback', 'https://127.0.0.1:53123/callback'),
])
def test_loopback_port_exception_preserves_other_exact_callback_guards(registered, callback):
    assert not OAuthClientService.redirect_uri_matches(callback, [registered])


@pytest.mark.parametrize('callback', [
    'https://client.example.test/callback', 'http://localhost:53123/callback',
    'http://127.0.0.1/callback', 'http://[::1]/callback',
])
def test_exact_registered_callbacks_still_match(callback):
    assert OAuthClientService.redirect_uri_matches(callback, [callback])
