# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json

from httpx import ASGITransport, AsyncClient
import pytest

from czero_app.website import Website


@pytest.fixture
def website(tmp_path):
    (tmp_path/'index.html').write_text('<html><head><base href="/" /></head><body><!--C0_BOOT--></body></html>')
    (tmp_path/'assets').mkdir()
    (tmp_path/'assets/site-test.js').write_text('const safe = true')
    return Website(tmp_path, '/czero/czero17')


def test_boot_data_is_inert_and_cannot_escape_the_script_element(website):
    hostile='</script><script src="https://example.org/x">&\u2028'
    response=website.render({'intent':hostile})
    body=response.body.decode()
    assert body.count('<script')==1 and hostile not in body
    assert 'type="application/json"' in body
    assert json.loads(body.split('type="application/json">')[1].split('</script>')[0])=={'intent':hostile}
    assert '<base href="/czero/czero17/" />' in body
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert 'unsafe-inline' not in response.headers['content-security-policy']
    assert response.headers['cache-control']=='no-store'


def test_spa_fallback_is_limited_to_website_routes(website):
    from fastapi import FastAPI
    app=FastAPI();website.install(app)
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app),base_url='https://example.org') as client:
            for path in ('/wiki/id','/sources/id','/account','/admin/spaces','/explore/entities/id'):
                assert (await client.get(path)).status_code==200
            for path in ('/api/v1/missing','/oauth/missing','/assets/missing.js','/markdown-worker.js','/vendor/poppins-LICENSE','/vendor/missing.js','/unknown'):
                assert (await client.get(path)).status_code==404
            response=await client.get('/assets/site-test.js')
            assert response.status_code==200 and 'immutable' in response.headers['cache-control']
            assert response.headers['content-type'].startswith('text/javascript')
    asyncio.run(check())


def test_missing_build_fails_without_returning_a_legacy_page(tmp_path):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as failure:
        Website(tmp_path,'').render()
    assert failure.value.status_code==503


@pytest.mark.parametrize('prefix', ['', '/czero/czero17'])
def test_table_links_and_reload_serve_the_compiled_website(website, prefix):
    from fastapi import FastAPI
    child=FastAPI();website.install(child)
    app=FastAPI()
    app.mount(prefix or '/', child)
    async def check():
        async with AsyncClient(transport=ASGITransport(app=app),base_url='https://example.org') as client:
            for path in ('/tables', '/tables/inventory-records'):
                response=await client.get(prefix+path+'?space_id=selected')
                assert response.status_code==200
                assert '<base href="/czero/czero17/" />' in response.text
                assert response.headers['cache-control']=='no-store'
            assert (await client.get(prefix+'/tables/inventory/extra')).status_code==404
    asyncio.run(check())
