# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
from uuid import UUID, uuid4
import importlib.util
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from czero_core.identity import PermissionDenied, Role
from test_auth_http import application, ORIGIN

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_signed_client_approval_retry_revision_disable_and_scoped_operation_parity(application):
    async def check():
        app, owner_token, member_token, _, db, _ = application
        access = app.state.auth.access
        owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
        service = app.state.oauth_clients
        ids = []
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get('/api/v1/oauth/clients')).status_code == 401
            client.headers['Authorization'] = 'Bearer ' + owner_token
            payload = {'client_name':'OAuth fixture ' + uuid4().hex,
                'redirect_uris':['http://127.0.0.1:3456/callback'],
                'allowed_scopes':['c0:read','c0:write']}
            try:
                first = await client.post('/api/v1/oauth/clients', json=payload)
                assert first.status_code == 201
                saved = first.json(); identifier = UUID(saved['client_id']); ids.append(identifier)
                assert saved['token_endpoint_auth_method'] == 'none' and 'client_secret' not in saved
                assert (await client.post('/api/v1/oauth/clients', json=payload)).json() == saved
                direct = app.state.operations.execute('oauth_clients_list', owner, {}, scopes={'c0:admin'})
                assert direct == (await client.get('/api/v1/oauth/clients')).json()
                disabled = await client.put('/api/v1/oauth/clients/' + str(identifier),
                    json={'enabled':False,'expected_revision':1})
                assert disabled.status_code == 200 and disabled.json()['revision'] == 2
                assert not disabled.json()['enabled']
                assert (await client.post('/api/v1/oauth/clients', json=payload)).json() == disabled.json()
                assert (await client.put('/api/v1/oauth/clients/' + str(identifier),
                    json={'enabled':True,'expected_revision':1})).status_code == 409
                assert (await client.put('/api/v1/oauth/clients/' + str(identifier),
                    json={'enabled':True,'expected_revision':2})).json()['revision'] == 3
                with db.engine.connect() as connection:
                    assert service._registered(connection, str(identifier))['revision'] == 3
                    assert service._registered(connection, 'unregistered-client') is None
                for bad in [dict(payload,allowed_scopes=['arbitrary:scope']),
                            dict(payload,redirect_uris=['https://client.example.test/*']),
                            dict(payload,client_secret='not accepted')]:
                    assert (await client.post('/api/v1/oauth/clients', json=bad)).status_code == 422
                oversized = b'{' + b' ' * 16384 + b'}'
                response = await client.post('/api/v1/oauth/clients', content=oversized,
                    headers={'Content-Type':'application/json'})
                assert response.status_code == 413 and response.json()['detail'] == 'upload_too_large'
                async def chunked():
                    yield oversized[:8192]
                    yield oversized[8192:]
                assert (await client.post('/api/v1/oauth/clients', content=chunked(),
                    headers={'Content-Type':'application/json'})).status_code == 413
                for role in (Role.READER, Role.EDITOR):
                    with pytest.raises(PermissionDenied):
                        access.resolve(app.state.auth.oidc.verify_access_token(member_token))
                    member_id = next(a['id'] for a in access.list_accounts(owner) if a['username']=='member')
                    access.set_role(owner, member_id, role)
                    member = access.resolve(app.state.auth.oidc.verify_access_token(member_token))
                    client.headers['Authorization'] = 'Bearer ' + member_token
                    assert (await client.get('/api/v1/oauth/clients')).status_code == 403
                    assert (await client.post('/api/v1/oauth/clients', json=payload)).status_code == 403
                    with pytest.raises(PermissionDenied):
                        service.set_enabled(member, identifier, enabled=False, expected_revision=3)
                    access.set_role(owner, member_id, None)
                client.headers['Authorization'] = 'Bearer ' + owner_token
            finally:
                with db.engine.begin() as connection:
                    for identifier in ids:
                        connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id':identifier})
    asyncio.run(check())


def test_client_limit_and_stale_actor_revocation_use_actual_database(application):
    app, owner_token, member_token, _, db, _ = application
    access = app.state.auth.access
    owner = access.resolve(app.state.auth.oidc.verify_access_token(owner_token))
    service = app.state.oauth_clients
    # Preserve any preexisting fixture rows; fill only the remaining capacity.
    ids = []
    try:
        with db.engine.connect() as connection:
            count = connection.execute(text('SELECT count(*) FROM c0_oauth_clients')).scalar_one()
        for _ in range(64-count):
            value = service.register(owner, 'Limit ' + uuid4().hex, ['https://client.example.test/callback'])
            ids.append(UUID(value['client_id']))
        with pytest.raises(ValueError, match='^oauth_client_limit$'):
            service.register(owner, 'Over limit ' + uuid4().hex, ['https://client.example.test/callback'])
        with pytest.raises(PermissionDenied):
            access.resolve(app.state.auth.oidc.verify_access_token(member_token))
        member_id = next(a['id'] for a in access.list_accounts(owner) if a['username']=='member')
        access.set_role(owner, member_id, Role.ADMIN)
        stale = access.resolve(app.state.auth.oidc.verify_access_token(member_token))
        assert len(service.list(stale)) == 64
        access.set_role(owner, member_id, None)
        with pytest.raises(PermissionDenied):
            service.list(stale)
        with pytest.raises(PermissionDenied):
            service.register(stale, 'Revoked', ['https://client.example.test/callback'])
    finally:
        with db.engine.begin() as connection:
            for identifier in ids:
                connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id':identifier})


def test_exact_disposable_client_seed_and_recovery_verifier_use_signed_rest(application):
    app, owner, _, _, db, _ = application
    path = Path(__file__).resolve().parents[1] / 'oidc_probe.py'
    specification = importlib.util.spec_from_file_location('oauth_fixture_probe', path)
    probe = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(probe)
    saved = []
    with TestClient(app, base_url=ORIGIN, headers={'Authorization':'Bearer ' + owner}) as client:
        class Browser:
            def api(self, path, data=None, method=None, csrf=None):
                response = client.request(method or 'GET', path, json=data)
                return response.status_code, response.content, str(response.url)
        try:
            saved = probe.seed_oauth_clients(Browser(), {'csrf_token':'unit-fixture-only'})
            assert len(saved) == 2 and saved[0]['enabled'] and not saved[1]['enabled']
            assert saved[1]['revision'] == 2
            probe.verify_oauth_clients(Browser(), saved)
            assert probe.seed_oauth_clients(Browser(), {'csrf_token':'unit-fixture-only'}) == saved
        finally:
            with db.engine.begin() as connection:
                for value in saved:
                    connection.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'), {'id':UUID(value['client_id'])})
