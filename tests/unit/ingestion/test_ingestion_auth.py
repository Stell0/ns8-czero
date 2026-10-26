# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import concurrent.futures
import io
import json
import time
from unittest.mock import patch
import pytest
from c0_ingest import auth
from c0_ingest.errors import C0Error
from c0_ingest.state import atomic, read
from c0_ingest.client import C0


def configured(tmp_path, *, expired=True):
    config = {'url': 'https://c0.example.org/mcp', 'client_id': 'synthetic-client',
              'credentials_file': str(tmp_path / 'oauth.json'), 'scopes': 'c0:read c0:write'}
    value = {'format': 1, 'server_url': config['url'], 'issuer': 'https://c0.example.org/oauth',
             'client_id': config['client_id'], 'access_token': 'old-synthetic-access',
             'refresh_token': 'old-synthetic-refresh', 'scope': config['scopes'],
             'expires_at': 0 if expired else time.time() + 3600}
    atomic(config['credentials_file'], value)
    return config, value


def response(value):
    return io.BytesIO(json.dumps(value).encode())


def renewal_responses():
    return [response({'issuer': 'https://c0.example.org/oauth',
                      'authorization_endpoint': 'https://c0.example.org/oauth/authorize',
                      'token_endpoint': 'https://c0.example.org/oauth/token'}),
            response({'access_token': 'new-synthetic-access', 'refresh_token': 'new-synthetic-refresh',
                      'expires_in': 300, 'token_type': 'Bearer'})]


def test_valid_token_does_not_refresh(tmp_path):
    config, _ = configured(tmp_path, expired=False)
    with patch('c0_ingest.auth.open_url') as network:
        assert auth.credentials(config) == 'old-synthetic-access'
        network.assert_not_called()


def test_rotation_persists_before_reuse_and_does_not_log_secrets(tmp_path, capsys):
    config, _ = configured(tmp_path)
    with patch('c0_ingest.auth.open_url', side_effect=renewal_responses()) as network:
        assert auth.credentials(config) == 'new-synthetic-access'
        assert auth.credentials(config) == 'new-synthetic-access'
        assert network.call_count == 2
    value = read(config['credentials_file'])
    assert value['refresh_token'] == 'new-synthetic-refresh'
    assert (tmp_path / 'oauth.json').stat().st_mode & 0o777 == 0o600
    assert 'synthetic-access' not in capsys.readouterr().err
    assert not (tmp_path / 'oauth.json.pending').exists()


def test_concurrent_renewal_has_one_sender(tmp_path):
    config, _ = configured(tmp_path)
    with patch('c0_ingest.auth.open_url', side_effect=renewal_responses()) as network:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            values = list(pool.map(lambda _: auth.credentials(config), range(2)))
        assert values == ['new-synthetic-access'] * 2
        assert network.call_count == 2


@pytest.mark.parametrize('change', [
    {'issuer': 'https://wrong.example/oauth'}, {'server_url': 'https://other.example/mcp'},
    {'client_id': 'another-client'}, {'format': 2},
])
def test_mismatched_binding_never_transmits_credentials(tmp_path, change):
    config, value = configured(tmp_path)
    atomic(config['credentials_file'], {**value, **change})
    with patch('c0_ingest.auth.open_url') as network:
        with pytest.raises(C0Error, match='binding'):
            auth.credentials(config)
        network.assert_not_called()


def test_missing_background_refresh_stops_before_network(tmp_path):
    config, value = configured(tmp_path)
    value.pop('refresh_token')
    atomic(config['credentials_file'], value)
    with patch('c0_ingest.auth.open_url') as network:
        with pytest.raises(C0Error, match='background'):
            auth.credentials(config)
        network.assert_not_called()


def test_changed_metadata_never_receives_refresh(tmp_path):
    config, _ = configured(tmp_path)
    malicious = response({'issuer': 'https://c0.example.org/oauth',
                          'authorization_endpoint': 'https://c0.example.org/oauth/authorize',
                          'token_endpoint': 'https://attacker.example/token'})
    with patch('c0_ingest.auth.open_url', return_value=malicious) as network:
        with pytest.raises(C0Error, match='metadata'):
            auth.credentials(config)
        assert network.call_count == 1


@pytest.mark.parametrize('failure', ['network', 'persist'])
def test_uncertain_rotation_is_not_replayed_after_restart(tmp_path, failure):
    config, _ = configured(tmp_path)
    if failure == 'network':
        context = patch('c0_ingest.auth.exchange', side_effect=TimeoutError)
    else:
        context = patch('c0_ingest.auth.save_tokens', side_effect=OSError)
    with context, patch('c0_ingest.auth.open_url', side_effect=renewal_responses()):
        with pytest.raises((C0Error, OSError)):
            auth.credentials(config)
    assert (tmp_path / 'oauth.json.pending').exists()
    with patch('c0_ingest.auth.open_url') as network:
        with pytest.raises(C0Error, match='uncertain'):
            auth.credentials(config)
        network.assert_not_called()


def test_codex_store_and_readable_credentials_are_rejected(tmp_path):
    config, _ = configured(tmp_path)
    atomic(config['credentials_file'], {'some-other-app': {'access_token': 'synthetic'}})
    with pytest.raises(C0Error, match='dedicated'):
        auth.credentials(config)
    configured(tmp_path)
    (tmp_path / 'oauth.json').chmod(0o644)
    with pytest.raises(C0Error, match='0600'):
        auth.credentials(config)


def test_login_cannot_overwrite_another_applications_store(tmp_path):
    config, _ = configured(tmp_path)
    config['redirect_uri'] = 'http://127.0.0.1:1/callback'
    atomic(config['credentials_file'], {'another-app': {'access_token': 'synthetic-access'}})
    before = (tmp_path / 'oauth.json').read_bytes()
    with patch('c0_ingest.auth.open_url') as network:
        with pytest.raises(C0Error, match='binding'):
            auth.login(config, launch=lambda _: pytest.fail('must not start login'))
        network.assert_not_called()
    assert (tmp_path / 'oauth.json').read_bytes() == before


def test_batch_never_mutates_or_crosses_space():
    client = object.__new__(C0)
    client.space_id = 'correct'
    client.operations = {'objects_create': {'read_only': False},
                         'objects_get': {'read_only': True, 'input_schema': {'properties': {'space_id': {}}}}}
    with pytest.raises(C0Error, match='read-only'):
        client.read_many([('objects_create', {})])
    with pytest.raises(C0Error, match='wrong target'):
        client.read_many([('objects_get', {'space_id': 'wrong'})])
