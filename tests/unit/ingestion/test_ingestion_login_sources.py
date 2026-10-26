# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import base64
import hashlib
from pathlib import Path
import runpy
import socket
import threading
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit
import urllib.error
import urllib.request
from unittest.mock import patch
import pytest
from c0_ingest import auth
from c0_ingest.sources import submit_text, verify_document
from c0_ingest.errors import C0Error
from c0_ingest.state import atomic, read


def test_login_uses_pkce_state_issuer_and_duplicate_callback_guards(tmp_path):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    config = {'url': 'https://c0.example.org/mcp', 'client_id': 'synthetic-client',
              'credentials_file': str(tmp_path / 'oauth.json'),
              'redirect_uri': f'http://127.0.0.1:{port}/callback', 'scopes': 'c0:read c0:write'}
    atomic(tmp_path / 'oauth.json.pending', {'uncertain': True})
    callbacks, errors, exchanges, workers = [], [], [], []

    def launch(url):
        values = parse_qs(urlsplit(url).query)
        assert values['resource'] == [config['url']] and values['code_challenge_method'] == ['S256']
        callbacks.append(values)
        def browse():
            try:
                for fields in [dict(state='wrong', code='synthetic-code'),
                               dict(state=values['state'][0], code='synthetic-code', iss='https://wrong.example/oauth')]:
                    with pytest.raises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(config['redirect_uri'] + '?' + urlencode(fields), timeout=3)
                    assert error.value.code == 400
                duplicate = urlencode({'state': values['state'][0], 'code': ['one', 'two']}, doseq=True)
                with pytest.raises(urllib.error.HTTPError):
                    urllib.request.urlopen(config['redirect_uri'] + '?' + duplicate, timeout=3)
                with urllib.request.urlopen(config['redirect_uri'] + '?' + urlencode({
                        'state': values['state'][0], 'code': 'synthetic-code', 'iss': 'https://c0.example.org/oauth'}), timeout=3) as response:
                    assert response.status == 200 and response.headers['Cache-Control'] == 'no-store'
            except BaseException as exc:
                errors.append(exc)
        worker = threading.Thread(target=browse, daemon=True)
        workers.append(worker); worker.start()
        return True

    def exchange(selected, fields):
        exchanges.append(fields)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(fields['code_verifier'].encode()).digest()).rstrip(b'=').decode()
        assert challenge == callbacks[0]['code_challenge'][0]
        assert fields['code'] == 'synthetic-code' and fields['redirect_uri'] == config['redirect_uri']
        return {'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh', 'expires_in': 300}
    with patch('c0_ingest.auth.metadata', return_value={'authorization_endpoint': 'https://c0.example.org/oauth/authorize'}), \
            patch('c0_ingest.auth.exchange', side_effect=exchange):
        assert auth.login(config, launch=launch, timeout=5)['status'] == 'connected'
    for worker in workers:
        worker.join(5)
    assert not errors and len(exchanges) == 1
    assert read(config['credentials_file'])['refresh_token'] == 'synthetic-refresh'
    assert not (tmp_path / 'oauth.json.pending').exists()


def test_oversized_utf8_source_stops_before_write():
    class Client:
        space_id = 'selected'
        def call(self, *args, **kwargs):
            pytest.fail('oversized input must not reach C0')
    with pytest.raises(C0Error, match='UTF-8'):
        submit_text(Client(), body='é' * 70000, title='Fixture', metadata={}, external_key='doc')


def test_indexing_has_bounded_wait_and_no_false_readback():
    version = {'id': 'version', 'source_id': 'source', 'state': 'queued', 'content_hash': 'hash'}
    calls = []
    client = SimpleNamespace(listing=lambda *a, **k: calls.append(a) or [version],
                             call=lambda *a, **k: pytest.fail('queued content must not be claimed verified'))
    with pytest.raises(C0Error, match='bounded'):
        verify_document(client, version, 'Body', attempts=2, seconds=0)
    assert len(calls) == 2


def test_privacy_checker_flags_artifacts_hosts_credentials_and_private_values():
    check = runpy.run_path(str(Path(__file__).resolve().parents[3] / 'scripts/check-ingestion-public.py'))['issues']
    assert check('.local/ingestion/job/.env', 'harmless') == ['private artifact']
    private_url = 'https://' + 'private.internal' + '/mcp'
    assert 'non-example instance URL' in check('adapter.py', private_url)
    secret = 'ghp_' + 'X' * 40
    assert 'credential-shaped material' in check('adapter.py', secret)
    assert 'private value from operator denylist' in check('notes.md', 'example private marker', ['private marker'])
    assert not check('example.py', 'https://c0.example.org/mcp')
