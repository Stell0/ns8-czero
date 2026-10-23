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
                  'preferred_username': 'owner', 'iat': clock[0] - 1, 'exp': clock[0] + options.get('access_seconds',300), 'typ': kind, **overrides}
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
        if 'scope' in options:
            result['scope'] = options['scope']
        if 'refresh_lifetime' in options:
            result['refresh_expires_in'] = options['refresh_lifetime']
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
        'nonce': 'original', 'id_context': {'iss': ISSUER, 'sub': 'owner', 'aud': 'native1'},
        'refresh_after': time.time() + 270})
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


@pytest.mark.parametrize('access_seconds,lifetime,expected', [
    (3600,'missing',300),(3600,0,300),(3600,120,90),(3600,1800,300),
    (300,1800,270),(3600,30,0),(3600,10,-20),(3600,10**1000,300),
])
def test_new_credential_refresh_deadline_honors_both_provider_windows(provider,access_seconds,lifetime,expected):
    client,options,_,credential=provider
    options['access_seconds']=access_seconds
    if lifetime!='missing':options['refresh_lifetime']=lifetime
    started=time.time()
    result=client.check_renewal(credential(exp=int(time.time())+10))
    deadline=json.loads(result.credential)['refresh_after']
    assert deadline-started==pytest.approx(expected,abs=1.1)


@pytest.mark.parametrize('lifetime',[None,True,False,-1,float('inf'),float('nan'),'120',{},[]])
def test_malformed_provider_refresh_lifetime_is_rejected_without_private_data(provider,lifetime):
    client,options,_,credential=provider
    options['refresh_lifetime']=lifetime
    with pytest.raises(RenewalRejected,match='^invalid_session$') as caught:
        client.check_renewal(credential(exp=int(time.time())+10))
    assert 'private' not in str(caught.value).lower()


@pytest.mark.parametrize('deadline',[None,True,'123',{},[],float('inf'),float('nan'),10**1000])
def test_malformed_saved_refresh_deadline_cannot_select_a_schedule(provider,deadline):
    client,_,calls,credential=provider
    saved=json.loads(credential());saved['refresh_after']=deadline
    with pytest.raises(RenewalRejected):client.check_renewal(json.dumps(saved))
    assert calls==[]


def test_introspection_never_slides_an_existing_refresh_deadline(provider,monkeypatch):
    from types import SimpleNamespace
    import czero_core.oidc as oidc_module
    client,options,calls,credential=provider
    options['access_seconds']=3600
    saved=json.loads(credential());original=saved['refresh_after']
    current=time.time()
    monkeypatch.setattr(oidc_module,'time',SimpleNamespace(time=lambda:current,monotonic=time.monotonic))
    for offset in (0,60,120):
        current+=offset
        saved=json.loads(client.check_renewal(json.dumps(saved)).credential)
        assert saved['refresh_after']==original
    assert len(calls)==3 and all(path.endswith('/check') for path,_ in calls)


def test_old_encrypted_credential_performs_one_real_refresh_then_acquires_deadline(provider):
    client,options,calls,credential=provider
    options['access_seconds']=3600
    saved=json.loads(credential());saved.pop('refresh_after')
    first=client.check_renewal(json.dumps(saved))
    assert calls==[('/realm/token',['grant_type','refresh_token'])]
    assert json.loads(first.credential)['refresh_after']>time.time()
    second=client.check_renewal(first.credential)
    assert json.loads(second.credential)['refresh_after']==json.loads(first.credential)['refresh_after']
    assert calls[-1][0].endswith('/check')


def test_offline_renewal_retains_attestation_across_rotation_and_checks(provider):
    client, options, calls, credential = provider
    options['scope'] = 'openid profile offline_access'
    saved = json.loads(credential(exp=int(time.time()) + 10))
    saved['offline'] = True
    result = client.check_renewal(json.dumps(saved))
    assert result.offline and json.loads(result.credential)['offline'] is True
    assert calls == [('/realm/token', ['grant_type', 'refresh_token'])]
    checked = client.check_renewal(result.credential)
    assert checked.offline and json.loads(checked.credential)['offline'] is True
    assert calls[-1][0] == '/realm/check'


@pytest.mark.parametrize('scope', [None, '', 'openid profile'])
def test_offline_refresh_cannot_drop_provider_attestation(provider, scope):
    client, options, _, credential = provider
    if scope is not None:
        options['scope'] = scope
    saved = json.loads(credential(exp=int(time.time()) + 10))
    saved['offline'] = True
    with pytest.raises(RenewalRejected):
        client.check_renewal(json.dumps(saved))


@pytest.mark.parametrize('offline', ['true', 1, None, {}])
def test_malformed_saved_offline_attestation_never_contacts_provider(provider, offline):
    client, _, calls, credential = provider
    saved = json.loads(credential())
    saved['offline'] = offline
    with pytest.raises(RenewalRejected):
        client.check_renewal(json.dumps(saved))
    assert calls == []
