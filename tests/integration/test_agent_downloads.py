# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import runpy
import zipfile

from httpx import ASGITransport, AsyncClient
import pytest

from czero_app.agent_packages import package_name
from test_auth_http import application, ORIGIN
from test_onboarding_http import signin, headers

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')
ROOT = Path(__file__).parents[2]


def unpack(response, suffix):
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/zip'
    assert response.headers['content-disposition'].endswith(suffix + '"')
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    assert hashlib.sha256(response.content).hexdigest() == response.headers['x-c0-package-sha256']
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert all(i.date_time == (1980, 1, 1, 0, 0, 0) and i.external_attr >> 16 == 0o100644 for i in archive.infolist())
        return {path: archive.read(path) for path in archive.namelist()}


def test_stale_cookie_keeps_simple_guide_and_canonical_skill_download_available(application, monkeypatch):
    async def check():
        app = application[0]
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
            http.cookies.set('c0_session', 'x' * 43, domain='c0.example.test', path='/')
            page = await http.get('/agents')
            assert page.status_code == 200 and 'Plugins → personal' in page.text and 'Download .skill' in page.text
            assert 'data-copy-name="Description"' in page.text and 'aria-label="Copy description"' in page.text
            assert '<h2>Available operations</h2>' not in page.text
            connection = await http.get('/agents/connection.json', headers={'Host': 'untrusted.example.test'})
            assert connection.status_code == 200
            value = connection.json()
            assert value['name'] == 'C0' and value['description'] == 'C0 Knowledge Storage on c0.example.test'
            assert value['mcp_url'] == ORIGIN + '/mcp' and value['hostname'] == 'c0.example.test'
            one = await http.get('/agents/c0-memory.skill', headers={'Host': 'untrusted.example.test'})
            two = await http.get('/agents/c0-memory.skill')
            assert one.content == two.content
            payload = unpack(one, '.skill')
            assert set(payload) == {'SKILL.md', 'agents/openai.yaml', 'LICENSE'}
            assert ORIGIN.encode() in payload['SKILL.md'] and (ORIGIN + '/mcp').encode() in payload['agents/openai.yaml']
            assert b'{{' not in payload['SKILL.md'] and b'untrusted.example.test' not in one.content
            assert b'PRIVATE_DOWNLOAD_CANARY' not in one.content
            assert payload['LICENSE'] == (ROOT / 'LICENSE').read_bytes()
    monkeypatch.setenv('CZERO_PRIVATE_DOWNLOAD_CANARY', 'PRIVATE_DOWNLOAD_CANARY')
    asyncio.run(check())


def test_browser_plugin_is_instance_bound_and_identical_to_offline_archive(application, tmp_path):
    async def check():
        app = application[0]
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
            profile = await signin(http)
            response = await http.post('/agents/plugin.zip', json={'chatgpt_app_id': 'https://chatgpt.com/plugins/plugin_asdk_app_fixture'}, headers=headers(profile))
            payload = unpack(response, '.zip')
            assert set(payload) == {'plugin.json', '.app.json', 'LICENSE', 'references/instance.md',
                'references/connection.md', 'references/maintenance.md', 'skills/c0-setup/SKILL.md',
                'skills/c0-research/SKILL.md', 'skills/c0-maintain-knowledge/SKILL.md'}
            assert json.loads(payload['.app.json']) == {'apps': {'c0': {'id': 'asdk_app_fixture', 'required': True}}}
            assert b'c0.example.test' in payload['references/instance.md']
            assert profile['csrf_token'].encode() not in response.content and profile['id'].encode() not in response.content
            assert not any(p in payload for p in ('mcp.json', '.mcp.json', 'AGENTS.md', 'PLAN.md'))
            offline = runpy.run_path(str(ROOT / 'scripts/package-chatgpt-plugin.py'))
            offline['build'](ORIGIN + '/mcp', 'asdk_app_fixture', package_name(ORIGIN + '/mcp'), tmp_path / 'package')
            assert (tmp_path / 'package/plugin.zip').read_bytes() == response.content
    asyncio.run(check())


@pytest.mark.parametrize('reference', ['asdk_app_', 'asdk_app_-invalid', '../connector_x',
    'https://evil.example.test/plugins/asdk_app_fixture',
    'https://chatgpt.com/oauth/authorize?state=PRIVATE_BAD_REFERENCE'])
def test_bad_plugin_reference_is_static_error_and_does_not_leak_input(application, reference):
    async def check():
        async with AsyncClient(transport=ASGITransport(app=application[0]), base_url=ORIGIN) as http:
            profile = await signin(http)
            result = await http.post('/agents/plugin.zip', json={'chatgpt_app_id': reference}, headers=headers(profile))
            assert result.status_code == 422 and result.json() == {'detail': 'invalid_chatgpt_connection'}
            assert reference not in result.text
    asyncio.run(check())


def test_plugin_download_requires_current_browser_and_origin_csrf(application):
    async def check():
        app, owner, *_ = application
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
            data = {'chatgpt_app_id': 'asdk_app_fixture'}
            assert (await http.post('/agents/plugin.zip', json=data)).status_code == 401
            profile = await signin(http)
            assert (await http.post('/agents/plugin.zip', json=data)).status_code == 403
            assert (await http.post('/agents/plugin.zip', json=data, headers={**headers(profile), 'Origin': 'https://evil.example.test'})).status_code == 403
            assert (await http.post('/agents/plugin.zip', json=data, headers={**headers(profile), 'Authorization': 'Bearer ' + owner})).status_code == 403
    asyncio.run(check())


@pytest.mark.parametrize('chunked', [False, True])
def test_plugin_request_body_is_bounded_before_json_parsing(application, chunked):
    async def check():
        async with AsyncClient(transport=ASGITransport(app=application[0]), base_url=ORIGIN) as http:
            profile = await signin(http)
            data = json.dumps({'chatgpt_app_id': 'asdk_app_' + 'x' * 8192}).encode()
            async def stream():
                for n in range(0, len(data), 512): yield data[n:n + 512]
            result = await http.post('/agents/plugin.zip', content=stream() if chunked else data,
                headers={**headers(profile), 'Content-Type': 'application/json'})
            assert result.status_code == 413
    asyncio.run(check())


@pytest.mark.parametrize('value', [
    {'chatgpt_app_id': 'https://chatgpt.com/oauth/authorize?state=PRIVATE_REJECTED_REFERENCE' + 'x' * 2500},
    {'chatgpt_app_id': {'token': 'PRIVATE_REJECTED_REFERENCE'}},
    {'chatgpt_app_id': 'asdk_app_fixture', 'unexpected': 'PRIVATE_REJECTED_REFERENCE'},
])
def test_download_schema_errors_do_not_echo_pasted_private_details(application, value):
    async def check():
        async with AsyncClient(transport=ASGITransport(app=application[0]), base_url=ORIGIN) as http:
            profile = await signin(http)
            response = await http.post('/agents/plugin.zip', json=value, headers=headers(profile))
            assert response.status_code == 422
            assert 'PRIVATE_REJECTED_REFERENCE' not in response.text
            assert response.json() == {'detail': 'invalid_chatgpt_connection'}
            assert response.headers['cache-control'] == 'no-store'
    asyncio.run(check())
