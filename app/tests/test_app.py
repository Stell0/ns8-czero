# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from czero_core import core_version

from czero_app.main import create_app

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "dist"
APP_VERSION = version('czero-app')
DATABASE_READY = {"status": "ok", "schema_revision": "0017_session_renewal", "vector_version": "0.8.7"}


def ready_database():
    return SimpleNamespace(health=lambda: DATABASE_READY, close=lambda: None)

@pytest.fixture
def client():
    async def get(path):
        async with AsyncClient(
            transport=ASGITransport(app=create_app("czero17", FRONTEND, database=ready_database())),
            base_url="http://testserver",
        ) as session:
            return await session.get(path)

    return lambda path: asyncio.run(get(path))

def test_health_contract_is_mounted_under_only_this_instance(client):
    response = client("/czero/czero17/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "czero",
        # Producer Core and the released consumer pin advance independently.
        "core_version": core_version,
        "app_version": APP_VERSION,
        "database": DATABASE_READY,
    }
    assert client("/czero/czero18/api/v1/health").status_code == 404

def test_openapi_documents_the_health_endpoint(client):
    response = client("/czero/czero17/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert "/api/v1/health" in document["paths"]
    assert document["info"]["version"] == APP_VERSION
    assert document["servers"][0]["url"] == "/czero/czero17"

def test_invalid_module_id_is_rejected():
    with pytest.raises(ValueError, match="assigned Czero module id"):
        create_app("other1", FRONTEND)

def test_hostname_root_endpoints_and_openapi():
    async def check():
        async with AsyncClient(transport=ASGITransport(app=create_app("czero17", FRONTEND, "", database=ready_database())),
                               base_url="https://c0.example.test") as session:
            for path in ("/", "/agents", "/api/v1/health", "/openapi.json", "/docs"):
                assert (await session.get(path)).status_code == 200
            document = (await session.get("/openapi.json")).json()
            assert "/api/v1/health" in document["paths"]
            assert "servers" not in document
            assert (await session.get("/czero/czero17/api/v1/health")).status_code == 404
    asyncio.run(check())

@pytest.mark.parametrize("path", ["/arbitrary", "/czero/czero18", "/", "https://other.test"])
def test_invalid_base_path_is_rejected(path):
    with pytest.raises(ValueError, match="CZERO_BASE_PATH"):
        create_app("czero17", FRONTEND, path)

def test_database_unavailable_is_a_safe_503():
    unavailable = {"status": "unavailable", "reason": "database_unavailable"}
    async def check():
        app = create_app("czero17", FRONTEND, "", database=SimpleNamespace(
            health=lambda: unavailable, close=lambda: None))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as session:
            response = await session.get("/api/v1/health")
            assert response.status_code == 503
            assert response.json()["status"] == "degraded"
            assert response.json()["database"] == unavailable
            assert "password" not in response.text
            assert (await session.get("/")).status_code == 200
    asyncio.run(check())

@pytest.mark.parametrize('weight', [400, 500])
def test_nebula_fonts_are_local_and_bound_to_the_instance_prefix(client, weight):
    asset = f'vendor/poppins-latin-{weight}-normal.woff2'
    response = client('/czero/czero17/' + asset)
    assert response.status_code == 200
    assert response.headers['content-type'] == 'font/woff2'
    assert response.content == (FRONTEND / asset).read_bytes()
    assert response.content.startswith(b'wOF2')
    assert client('/czero/czero18/' + asset).status_code == 404
    assert client('/czero/czero17/vendor/poppins-latin-700-normal.woff2').status_code == 404
    assert not any('poppins' in path for path in client('/czero/czero17/openapi.json').json()['paths'])

@pytest.mark.parametrize('page', ['', 'wiki', 'sources', 'search', 'agents', 'explore', 'admin'])
def test_user_templates_have_balanced_elements_and_no_duplicate_attributes(client, page):
    from html.parser import HTMLParser

    class Markup(HTMLParser):
        void = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                'link', 'meta', 'param', 'source', 'track', 'wbr'}

        def __init__(self):
            super().__init__()
            self.stack = []
            self.errors = []

        def handle_starttag(self, tag, attrs):
            names = [key for key, value in attrs]
            if len(names) != len(set(names)):
                self.errors.append(('duplicate attributes', tag))
            if tag not in self.void:
                self.stack.append(tag)

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            if tag not in self.void:
                self.handle_endtag(tag)

        def handle_endtag(self, tag):
            if not self.stack or self.stack[-1] != tag:
                self.errors.append(('unbalanced element', tag))
            elif self.stack:
                self.stack.pop()

    markup = Markup()
    markup.feed(client('/czero/czero17/' + page).text)
    assert not markup.errors
    assert not markup.stack


@pytest.mark.parametrize('page', ['', 'search', 'wiki', 'wiki/id', 'sources', 'sources/id',
    'evidence/id', 'projects', 'explore', 'explore/entities/id', 'account', 'agents',
    'admin', 'admin/spaces', 'admin/work', 'admin/advanced'])
def test_compiled_website_routes_preserve_mount_and_local_csp(client, page):
    from html.parser import HTMLParser
    class Assets(HTMLParser):
        def __init__(self):super().__init__();self.urls=[];self.base=None
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='base':self.base=attrs['href']
            if tag=='script' and attrs.get('src'):self.urls.append(attrs['src'])
            if tag=='link' and attrs.get('rel') in ('stylesheet','modulepreload'):self.urls.append(attrs['href'])
    response=client('/czero/czero17/'+page)
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert 'unsafe-inline' not in response.headers['content-security-policy']
    markup=Assets();markup.feed(response.text)
    assert markup.base=='/czero/czero17/' and markup.urls
    for url in markup.urls:
        assert url.startswith('./assets/')
        assert client('/czero/czero17/'+url[2:]).status_code==200
    assert 'id="app"' in response.text and 'id="c0-boot"' in response.text


@pytest.mark.parametrize('asset', ['markdown-worker.js', 'vendor/markdown-it-15.0.2.min.js',
    'vendor/markdown-it-LICENSE', 'vendor/poppins-LICENSE', 'vendor/third-party-notices.txt'])
def test_local_runtime_assets_and_notices(client, asset):
    response=client('/czero/czero17/'+asset)
    assert response.status_code==200 and response.content
    assert client('/czero/czero18/'+asset).status_code==404
    assert not any(path.endswith(('.js','.html','.css','.woff2')) for path in client('/czero/czero17/openapi.json').json()['paths'])


@pytest.mark.parametrize('path', ['objects', 'wiki.js', 'sources.js', 'site.js', 'reader.js',
    'app.css', 'auth.js', 'oauth/consent.js', 'assets/missing.js', 'api/v1/missing'])
def test_missing_and_removed_routes_never_return_the_spa(client, path):
    assert client('/czero/czero17/'+path).status_code==404


def test_public_agents_uses_unchanged_caller_aware_capabilities(client):
    capabilities=client('/czero/czero17/agents/capabilities.json')
    assert capabilities.status_code==200 and capabilities.headers['cache-control']=='no-store'
    data=capabilities.json()
    assert data['operations']==[] and data['interfaces']['mcp'] is False
    assert data['rest_base']=='/czero/czero17/api/v1'
    assert data['mcp_url'] is None and data['oauth'] is None
    document=client('/czero/czero17/openapi.json').json()
    assert document['x-c0-interfaces']['interfaces']['mcp'] is False
    assert '/api/v1/wiki/pages' in document['paths'] and '/api/v1/sources/search' in document['paths']
