# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

from czero_core.cimd_metadata import MetadataRejected, metadata_url, parse_metadata

URL = 'https://client.example.test/oauth/client.json'
CALLBACK = 'https://client.example.test/callback'


def document(**changes):
    return json.dumps({'client_id': URL, 'client_name': 'Public client',
        'redirect_uris': [CALLBACK], 'token_endpoint_auth_method': 'none', **changes}).encode()


def test_approval_descriptor_is_exact_and_ignores_unused_display_and_jwks_urls():
    value = parse_metadata(URL, document())
    assert value.client_id == URL and value.grant_types == ('authorization_code',)
    assert value.scope_ceiling is None
    assert value.digest == parse_metadata(URL, document(logo_uri='http://127.0.0.1/secret',
        jwks_uri='http://169.254.169.254/secret', client_uri='javascript:ignored')).digest
    assert 'jwks_uri' not in value.descriptor()
    assert value.digest != parse_metadata(URL, document(client_name='Changed')).digest


def test_chatgpt_plural_negotiation_selects_none_over_legacy_jwt_preference():
    value = parse_metadata(URL, document(token_endpoint_auth_method='private_key_jwt',
        token_endpoint_auth_methods_supported=['none', 'private_key_jwt'],
        jwks_uri='https://client.example.test/jwks.json',
        grant_types=['refresh_token', 'authorization_code'], scope='c0:write c0:read'))
    assert value.descriptor()['token_endpoint_auth_method'] == 'none'
    assert value.grant_types == ('authorization_code', 'refresh_token')
    assert value.scope_ceiling == ('c0:read', 'c0:write')
    other = parse_metadata(URL, document(token_endpoint_auth_methods_supported=['private_key_jwt', 'none'],
        grant_types=['authorization_code', 'refresh_token'], scope='c0:read c0:write'))
    assert value.digest == other.digest


@pytest.mark.parametrize('url', [
    'http://client.example.test/x', 'https://client.example.test',
    'https://client.example.test/x?', 'https://client.example.test/x#',
    'https://client.example.test:444/x', 'https://u:p@client.example.test/x',
    'https://127.0.0.1/x', 'https://[::1]/x', 'https://2130706433/x',
    'https://client.example.test/./x', 'https://client.example.test/%2e%2e/x',
    'https://client.example.test/x%2f..%2fy', 'https://client.example.test/\\x',
    'https://client.example.test/x\n', 'https://client.example.test./x',
    'https://-client.example.test/x', 'https://café.example.test/x',
    'https://client.example.test/' + 'a' * 2048, None, 1,
])
def test_metadata_identity_rejects_ambiguous_or_unsafe_urls(url):
    with pytest.raises(MetadataRejected):
        metadata_url(url)


@pytest.mark.parametrize('changes', [
    {'client_id': URL + '/'}, {'client_name': ''}, {'client_name': ' '},
    {'client_name': 'a\nb'}, {'client_name': 'a' * 129},
    {'redirect_uris': []}, {'redirect_uris': [CALLBACK, CALLBACK]},
    {'redirect_uris': [CALLBACK + '?secret=x']}, {'redirect_uris': [None]},
    {'token_endpoint_auth_method': 'private_key_jwt'},
    {'token_endpoint_auth_method': None}, {'token_endpoint_auth_methods_supported': ['client_secret_post']},
    {'token_endpoint_auth_methods_supported': 'none'},
    {'token_endpoint_auth_methods_supported': ['none', 'none']},
    {'grant_types': ['refresh_token']}, {'grant_types': ['authorization_code', 'implicit']},
    {'grant_types': []}, {'response_types': ['token']}, {'response_types': []},
    {'scope': ''}, {'scope': 'c0:read  c0:write'}, {'scope': 'c0:read\tc0:write'},
    {'scope': 'other'}, {'scope': 'c0:read c0:read'},
    {'client_secret': 'do-not-accept'}, {'jwks': {'keys': [{'kty': 'RSA', 'd': 'private'}]}},
])
def test_invalid_or_unsupported_metadata_is_rejected(changes):
    with pytest.raises(MetadataRejected, match='^invalid_client_metadata$'):
        parse_metadata(URL, document(**changes))


@pytest.mark.parametrize('body', [b'\xff', b'{}', b'[]', b'{"client_id":1,"client_id":2}',
    b'{"unused":NaN}', b' ' * 32769, b'{"unused":' + b'[' * 17 + b'0' + b']' * 17 + b'}'])
def test_bounded_strict_json_rejects_duplicate_keys_encoding_constants_and_depth(body):
    with pytest.raises(MetadataRejected):
        parse_metadata(URL, body)
