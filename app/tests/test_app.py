# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from czero_app.main import create_app

STATIC = Path(__file__).resolve().parents[1] / "static"
DATABASE_READY = {"status": "ok", "schema_revision": "0013_oauth_consent", "vector_version": "0.8.7"}


def ready_database():
    return SimpleNamespace(health=lambda: DATABASE_READY, close=lambda: None)



@pytest.fixture
def client():
    async def get(path):
        async with AsyncClient(
            transport=ASGITransport(app=create_app("czero17", STATIC, database=ready_database())),
            base_url="http://testserver",
        ) as session:
            return await session.get(path)

    return lambda path: asyncio.run(get(path))


def test_instance_landing_page_and_links(client):
    response = client("/czero/czero17/")
    assert response.status_code == 200
    assert "A place to find what we know." in response.text
    assert "./api/v1/health" in response.text


def test_health_contract_is_mounted_under_only_this_instance(client):
    response = client("/czero/czero17/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "czero",
        "core_version": "0.25.0",
        "app_version": "0.40.0",
        "database": DATABASE_READY,
    }
    assert client("/czero/czero18/api/v1/health").status_code == 404


def test_agents_page_describes_only_available_capabilities(client):
    response = client("/czero/czero17/agents")
    assert response.status_code == 200
    assert "search source text" in response.text
    assert "sourced claims and bounded graph queries are available" in response.text
    assert "MCP is unavailable until NS8 sign-in and hostname-root routing are configured" in response.text
    assert "text fallback" in response.text
    assert '/api/v1/wiki/pages' in client('/czero/czero17/openapi.json').json()['paths']
    assert '/api/v1/sources/search' in client('/czero/czero17/openapi.json').json()['paths']
    assert "./docs" in response.text
    assert "A native timer wakes" in response.text
    assert "pending milestone slice" not in response.text
    capabilities = client('/czero/czero17/agents/capabilities.json')
    assert capabilities.status_code == 200 and capabilities.headers['cache-control'] == 'no-store'
    assert capabilities.json()['operations'] == [] and capabilities.json()['interfaces']['mcp'] is False
    assert capabilities.json()['rest_base'] == '/czero/czero17/api/v1'
    assert capabilities.json()['mcp_url'] is None and capabilities.json()['oauth'] is None
    assert client('/czero/czero17/openapi.json').json()['x-c0-interfaces']['interfaces']['mcp'] is False


def test_search_page_uses_local_assets_and_no_privileged_mutation(client):
    page = client('/czero/czero17/search')
    assert page.status_code == 200 and 'Knowledge search' in page.text
    assert 'src="./search.js"' in page.text
    script = client('/czero/czero17/search.js')
    assert script.status_code == 200 and 'knowledge/search?' in script.text
    assert 'innerHTML' not in script.text and 'method:' not in script.text


def test_openapi_documents_the_health_endpoint(client):
    response = client("/czero/czero17/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert "/api/v1/health" in document["paths"]
    assert document["info"]["version"] == "0.40.0"
    assert document["servers"][0]["url"] == "/czero/czero17"


def test_invalid_module_id_is_rejected():
    with pytest.raises(ValueError, match="assigned Czero module id"):
        create_app("other1", STATIC)


def test_hostname_root_endpoints_and_openapi():
    async def check():
        async with AsyncClient(transport=ASGITransport(app=create_app("czero17", STATIC, "", database=ready_database())),
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
        create_app("czero17", STATIC, path)


def test_database_unavailable_is_a_safe_503():
    unavailable = {"status": "unavailable", "reason": "database_unavailable"}
    async def check():
        app = create_app("czero17", STATIC, "", database=SimpleNamespace(
            health=lambda: unavailable, close=lambda: None))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as session:
            response = await session.get("/api/v1/health")
            assert response.status_code == 503
            assert response.json()["status"] == "degraded"
            assert response.json()["database"] == unavailable
            assert "password" not in response.text
            assert (await session.get("/")).status_code == 200
    asyncio.run(check())


def test_objects_page_uses_local_assets_and_accessible_editor(client):
    response=client('/czero/czero17/objects')
    assert response.status_code==200
    assert 'for="record-data"' in response.text and 'aria-live="polite"' in response.text
    assert './objects.js' in response.text
    script=client('/czero/czero17/objects.js')
    assert script.status_code==200 and 'expected_revision' in script.text
    assert 'innerHTML' not in script.text


@pytest.mark.parametrize('page', ['', 'objects', 'sources', 'wiki', 'search', 'agents', 'admin'])
def test_user_pages_share_local_navigation_and_keyboard_focus(client, page):
    response=client('/czero/czero17/'+page)
    assert response.status_code==200
    assert 'href="./app.css"' in response.text and './navigation.js' in response.text
    assert 'aria-label="C0 navigation"' in response.text and 'Skip to content' in response.text
    assert 'id="main-content"' in response.text
    css=client('/czero/czero17/app.css')
    assert css.status_code==200 and css.headers['content-type'].startswith('text/css')
    assert ':focus-visible' in css.text and '[hidden]' in css.text
    script=client('/czero/czero17/navigation.js')
    assert script.status_code==200 and 'innerHTML' not in script.text



def test_records_offer_schema_fields_and_explicit_json_editor(client):
    page=client('/czero/czero17/objects')
    assert 'id="record-fields"' in page.text and 'Advanced JSON editor' in page.text
    assert 'src="./record-fields.js"' in page.text
    script=client('/czero/czero17/record-fields.js')
    assert script.status_code==200 and 'Object.defineProperty' in script.text
    assert 'innerHTML' not in script.text and 'fetch(' not in script.text


def test_admin_page_uses_existing_role_guarded_apis_and_local_assets(client):
    page=client('/czero/czero17/admin')
    assert page.status_code==200 and 'id="admin-workspace" hidden' in page.text
    assert './admin.js' in page.text and 'UTC interval schedules' in page.text
    script=client('/czero/czero17/admin.js')
    assert script.status_code==200 and 'innerHTML' not in script.text
    assert 'expected_revision' in script.text and 'idempotency_key' in script.text
    assert 'X-C0-CSRF' in script.text


def test_wiki_graph_offers_readable_nodes_edges_and_references(client):
    page=client('/czero/czero17/wiki')
    assert page.status_code==200
    for element in ('graph-nodes','graph-edges','graph-references'):
        assert 'id="'+element+'"' in page.text
    assert '<summary>Graph JSON</summary>' in page.text


@pytest.mark.parametrize('asset', ['site.js', 'reader.js', 'vendor/markdown-it-15.0.2.min.js'])
def test_reader_assets_are_local_and_work_under_the_instance_prefix(client, asset):
    response = client('/czero/czero17/' + asset)
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/javascript')
    assert client('/czero/czero18/' + asset).status_code == 404


def test_reader_assets_do_not_expand_the_domain_api(client):
    paths = client('/czero/czero17/openapi.json').json()['paths']
    assert not any(path.endswith(('.js', '.html')) for path in paths)
    for script in ('site.js', 'reader.js'):
        source = client('/czero/czero17/' + script).text
        assert 'innerHTML' not in source
        assert "method:'POST'" not in source and "method:'PUT'" not in source


@pytest.mark.parametrize('page', ['', 'wiki', 'sources', 'search', 'agents', 'objects', 'admin'])
def test_reader_templates_have_unique_ids_and_one_page_heading(client, page):
    from html.parser import HTMLParser

    class Structure(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = []
            self.headings = 0

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if 'id' in attributes:
                self.ids.append(attributes['id'])
            if tag == 'h1':
                self.headings += 1

    structure = Structure()
    structure.feed(client('/czero/czero17/' + page).text)
    assert len(structure.ids) == len(set(structure.ids))
    assert structure.headings == 1


@pytest.mark.parametrize('page,form', [('wiki', 'wiki-form'), ('sources', 'upload-form')])
def test_manual_contribution_forms_belong_to_the_tools_view(client, page, form):
    from html.parser import HTMLParser

    class Ancestors(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.tools = False

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if attributes.get('id') == form:
                self.tools = any('data-tools-only' in ancestor for ancestor in self.stack)
            if tag not in {'input', 'br', 'hr', 'meta', 'link', 'img'}:
                self.stack.append(attributes)

        def handle_endtag(self, tag):
            if self.stack:
                self.stack.pop()

    structure = Ancestors()
    structure.feed(client('/czero/czero17/' + page).text)
    assert structure.tools


@pytest.mark.parametrize('page', ['', 'wiki', 'sources', 'search', 'agents', 'objects', 'admin'])
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

        def handle_endtag(self, tag):
            if not self.stack or self.stack[-1] != tag:
                self.errors.append(('unbalanced element', tag))
            elif self.stack:
                self.stack.pop()

    markup = Markup()
    markup.feed(client('/czero/czero17/' + page).text)
    assert not markup.errors
    assert not markup.stack
