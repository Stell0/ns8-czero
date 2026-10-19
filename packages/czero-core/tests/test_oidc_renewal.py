# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real signed provider responses, bounded requests and private diagnostics."""
import json
import time
from urllib.parse import parse_qs
from uuid import uuid4

import httpx2
import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey

from czero_core.identity import TokenVerifier
from czero_core.oidc import OidcClient, OidcConfig
from czero_core.renewal import RenewalRejected, RenewalUnavailable

ISSUER = 'https://idp.example.test/realm'


@pytest.fixture
def provider():
    key = RSAKey.generate_key(2048, {'kid': 'trusted', 'use': 'sig'})
    account, clock = str(uuid4()), [int(time.time())]
    options = {'active': True, 'http': 200, 'subject': 'owner', 'nonce': None}
    calls = []
    def token(kind='Bearer', **overrides):
        claims = {'iss': ISSUER, 'aud': 'native1', 'sub': options['subject'], 'ldap_uuid': account,
                  'preferred_username': 'owner', 'iat': clock[0] - 1, 'exp': clock[0] + 300, 'typ': kind, **overrides}
        return jwt.encode({'alg': 'RS256', 'kid': 'trusted'}, claims, key)
    def handle(request):
        if request.url.path.endswith('openid-configuration'):
            return httpx2.Response(200, json={'issuer': ISSUER, 'authorization_endpoint': ISSUER+'/auth',
                'token_endpoint': ISSUER+'/token', 'jwks_uri': ISSUER+'/keys',
                'end_session_endpoint': ISSUER+'/logout', 'introspection_endpoint': options.get('endpoint', ISSUER+'/check')})
        assert request.headers['authorization'].startswith('Basic ')
        body = parse_qs(request.content.decode())
        calls.append((request.url.path, sorted(body)))
        if options.get('transport_error'):
            raise httpx2.ReadTimeout('PRIVATE response lost')
        if options['http'] != 200:
            return httpx2.Response(options['http'], json={'error': 'invalid_grant', 'error_description': 'PRIVATE'})
        if request.url.path.endswith('/check'):
            return httpx2.Response(200, json={'active': options['active']})
        assert body['grant_type'] == ['refresh_token']
        assert body['refresh_token'] == ['private-refresh']
        result = {'access_token': token(), 'refresh_token': 'rotated-private-refresh', 'token_type': 'Bearer'}
        if options['nonce'] is not None:
            result['id_token'] = token('ID', **({} if options['nonce'] is False else {'nonce': options['nonce']}), **options.get('id_overrides', {}))
        if options.get('oversized'):
            result['private_padding'] = 'x'*65536
        return httpx2.Response(200, json=result)
    client = OidcClient(OidcConfig(ISSUER, 'native1', 's'*32, 'https://c0.example.test'),
                        transport=httpx2.MockTransport(handle))
    client._verifier = TokenVerifier(ISSUER, 'native1', {'keys': [key.as_dict(private=False)]})
    client._keys_until = time.monotonic() + 300
    credential = lambda **overrides: json.dumps({'access': token(**overrides), 'refresh': 'private-refresh',
        'nonce': 'original', 'id_context': {'iss': ISSUER, 'sub': 'owner', 'aud': 'native1'}})
    yield client, options, calls, credential
    client.close()


def test_current_token_is_checked_with_provider_before_use(provider):
    client, options, calls, credential = provider
    result = client.check_renewal(credential())
    assert result.identity.subject == 'owner'
    assert calls == [('/realm/check', ['token', 'token_type_hint'])]
    assert 'private-refresh' not in repr(result)
    options['active'] = False
    with pytest.raises(RenewalRejected, match='^invalid_session$'):
        client.check_renewal(credential())


@pytest.mark.parametrize('nonce', [False, 'original'])
def test_near_expiry_refreshes_and_validates_optional_id_token(provider, nonce):
    client, options, calls, credential = provider
    options['nonce'] = nonce
    result = client.check_renewal(credential(exp=int(time.time()) + 10))
    assert result.identity.subject == 'owner'
    assert json.loads(result.credential)['refresh'] == 'rotated-private-refresh'
    # Successful refresh is the provider control; do not lose the rotated
    # credential to an unnecessary second network call that could fail.
    assert calls == [('/realm/token', ['grant_type', 'refresh_token'])]


def test_refresh_wrong_nonce_is_denied(provider):
    client, options, _, credential = provider
    options['nonce'] = 'wrong'
    with pytest.raises(RenewalRejected):
        client.check_renewal(credential(exp=int(time.time()) + 10))


@pytest.mark.parametrize('status,error', [(400, RenewalRejected), (401, RenewalRejected), (503, RenewalUnavailable)])
def test_provider_errors_are_static_and_outage_is_retryable(provider, status, error):
    client, options, _, credential = provider
    options['http'] = status
    with pytest.raises(error) as caught:
        client.check_renewal(credential())
    assert 'PRIVATE' not in str(caught.value)
    assert 'private-refresh' not in str(caught.value)


def test_refresh_response_is_bounded(provider):
    client, options, _, credential = provider
    options['oversized'] = True
    with pytest.raises(RenewalRejected):
        client.check_renewal(credential(exp=int(time.time()) + 10))


def test_discovery_cannot_exfiltrate_introspection_token(provider):
    client, options, calls, credential = provider
    options['endpoint'] = 'https://untrusted.example.test/check'
    with pytest.raises(RenewalRejected):
        client.check_renewal(credential())
    assert calls == []


@pytest.mark.parametrize('claims', [{'auth_time': 123}, {'azp': 'native1'}, {'aud': ['native1','other']}])
def test_refresh_id_token_cannot_change_original_authentication_context(provider, claims):
    client, options, _, credential = provider
    options.update(nonce=False, id_overrides=claims)
    with pytest.raises(RenewalRejected):
        client.check_renewal(credential(exp=int(time.time()) + 10))


def test_ambiguous_native_refresh_is_rejected_but_introspection_can_retry(provider):
    client, options, _, credential = provider
    options['transport_error'] = True
    with pytest.raises(RenewalUnavailable):
        client.check_renewal(credential())
    with pytest.raises(RenewalRejected):
        client.check_renewal(credential(exp=int(time.time()) + 10))


@pytest.mark.parametrize('context',[{'auth_time':123},{'azp':'native1','auth_time':123}])
def test_refresh_retains_verified_original_authentication_context(provider,context):
    client,options,_,credential=provider
    options.update(nonce=False,id_overrides=context)
    saved=json.loads(credential(exp=int(time.time())+10))
    saved['id_context'].update(context)
    result=client.check_renewal(json.dumps(saved))
    assert result.identity.subject=='owner'
    assert json.loads(result.credential)['id_context']==saved['id_context']
