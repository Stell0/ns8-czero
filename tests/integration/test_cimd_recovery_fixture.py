# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute the exact native Core-seeded recovery helper through signed HTTP."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from uuid import UUID

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from test_cimd_http import cimd_http
from test_auth_http import application, ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def recovery(cimd_http, monkeypatch, tmp_path):
    app, owner, registry = cimd_http
    tests = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(tests))
    spec = importlib.util.spec_from_file_location('native_cimd_recovery', tests/'cimd_recovery_fixture.py')
    fixture = importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    from czero_app.auth import AppAuth
    monkeypatch.setattr(AppAuth, 'from_env', lambda *_: app.state.auth)
    client = TestClient(app, base_url=ORIGIN)  # Keep the already configured fixture policy.
    identity = app.state.auth.oidc.verify_access_token(owner)
    class Browser:
        origin = ORIGIN
        @property
        def cookies(self): return client.cookies.jar
        def login(self):
            value = app.state.auth.sessions.create(identity)
            client.cookies.set('c0_session', value, domain='c0.example.test', path='/')
            response = client.get('/api/v1/me');assert response.status_code == 200
            return response.json()
        def request(self, path, data=None, method=None, headers=None):
            response = client.request(method or 'GET', path, content=data, headers=headers)
            for _ in range(8):
                if response.status_code != 302:
                    return response.status_code, response.content, str(response.url)
                response = client.get(response.headers['location'])
            raise AssertionError('Native CIMD fixture redirect loop')
        def api(self, path, data=None, method=None, csrf=None):
            headers = {'Origin': ORIGIN}
            if csrf: headers['X-C0-CSRF'] = csrf
            response = client.request(method or 'GET', path, json=data, headers=headers)
            return response.status_code, response.content, str(response.url)
    browser = Browser();profile = browser.login()
    async def forbidden_fetch(url):
        raise AssertionError('Core-seeded fixture must not claim a real network fetch')
    monkeypatch.setattr(app.state.cimd.fetcher, '_fetch', forbidden_fetch)
    def control(module, operation, browser, profile, document):
        payload = {'operation': operation, 'cookie': next(c.value for c in browser.cookies if c.name == 'c0_session'),
                   'profile_id': profile['id'], 'metadata_url': document['client_id'], 'document': document}
        monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):exec(fixture.CONTROL_CODE, {})
        return json.loads(output.getvalue())
    yield fixture, app, registry, browser, profile, control, tmp_path
    client.close()


def test_native_cimd_helper_retains_approval_and_requires_new_authority_after_restore(recovery):
    fixture, app, registry, browser, profile, control, directory = recovery
    proof = fixture.seed('czero900', browser, profile, directory=directory, control_fn=control)
    assert proof['stage'] == 'seed' and proof['network_fetch_tested'] is False
    saved = directory/'expected-cimd-recovery.json'
    assert saved.stat().st_mode & 0o777 == 0o600
    # A new adapter process must reload the approved descriptor from PostgreSQL.
    app.state.cimd.fetcher.cache.clear()
    assert fixture.verify('czero900', browser, profile, directory=directory, control_fn=control)['existing_authority_retained']
    app.state.delegated_grants.native_client = 'czero901'
    app.state.auth.sessions.client_id = 'czero901'
    app.state.cimd.fetcher.cache.clear()
    profile = browser.login()
    proof = fixture.verify('czero901', browser, profile, directory=directory, control_fn=control)
    assert proof['old_authority_rejected'] and proof['fresh_consent'] and proof['client_disabled']


def test_native_cimd_helper_rejects_approval_loss(recovery):
    fixture, _, registry, browser, profile, control, directory = recovery
    fixture.seed('czero900', browser, profile, directory=directory, control_fn=control)
    saved = json.loads((directory/'expected-cimd-recovery.json').read_text())
    with registry.access.database.engine.begin() as c:
        c.execute(text('UPDATE c0_cimd_clients SET review_required=true WHERE client_id=:id'),
                  {'id': UUID(saved['approval']['client_id'])})
    with pytest.raises(AssertionError, match='Approved CIMD state changed'):
        fixture.verify('czero900', browser, profile, directory=directory, control_fn=control)


def test_native_cimd_helper_fails_if_restore_keeps_old_access(recovery):
    fixture, _, _, browser, profile, control, directory = recovery
    fixture.seed('czero900', browser, profile, directory=directory, control_fn=control)
    with pytest.raises(AssertionError, match='Clean restore retained old CIMD access'):
        fixture.verify('czero901', browser, profile, directory=directory, control_fn=control)


@pytest.mark.parametrize('host,operation', [('production.example.org', 'seed'), ('czero7.test', 'verify')])
def test_native_cimd_cli_rejects_live_hosts_or_missing_restored_switch(recovery, monkeypatch, host, operation):
    fixture, _, _, _, _, _, directory = recovery
    monkeypatch.setattr(fixture, 'STATE', directory)
    (directory/'personas.json').write_text(json.dumps({'host': host, 'password': 'synthetic-only'}))
    monkeypatch.setattr(fixture.os, 'geteuid', lambda: 0)
    calls = []
    monkeypatch.setattr(fixture, 'task', lambda *args: calls.append(args) or {'cimd_enabled': False})
    monkeypatch.setattr(fixture, 'Browser', lambda *_: pytest.fail('A rejected fixture must not sign in'))
    with pytest.raises(AssertionError, match='disposable hosts|switch did not survive'):
        fixture.main('czero7', operation)
    assert len(calls) == (0 if operation == 'seed' else 1)


def test_native_cimd_helper_rejects_an_expired_grant_as_restore_evidence(recovery):
    import time
    fixture, _, _, browser, profile, control, directory = recovery
    fixture.seed('czero900', browser, profile, directory=directory, control_fn=control)
    path = directory/'expected-cimd-recovery.json'
    saved = json.loads(path.read_text());saved['grant_expires_at'] = time.time() - 1
    path.write_text(json.dumps(saved))
    with pytest.raises(AssertionError, match='grant expired before native binding assertion'):
        fixture.verify('czero901', browser, profile, directory=directory, control_fn=control)
