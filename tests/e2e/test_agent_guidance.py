# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Advertised read-only context remains visible under real browser roles."""
from urllib.parse import urlencode

from playwright.sync_api import expect
import pytest


@pytest.mark.parametrize('role',['reader','protected-reader','editor','admin'])
def test_selective_context_guidance_and_stable_workflow_identity(live,browser,role):
    effective='reader' if role=='protected-reader' else role
    if role in ('editor','protected-reader'):
        accounts=live.rest.get('/api/v1/access/accounts').json()['accounts']
        account=next(value for value in accounts if value['username']=='member')
        assert live.rest.put('/api/v1/access/accounts/'+account['id'],json={'role':'editor'}).status_code==204
        if role=='editor':
            assert live.rest.put(live.grant_path,json={'role':'editor','expected_revision':1,'idempotency_key':'guide-editor'}).status_code==200
    if role!='reader':
        browser.context.clear_cookies()
        if role!='admin':browser.context.add_cookies([{'name':'fixture_persona','value':'reader','url':live.origin}])
        browser.goto(live.origin+'/auth/login')
        expect(browser.get_by_role('button',name='Knowledge space Shared',exact=True)).to_be_visible()
    browser.goto(live.origin+'/agents?'+urlencode({'space_id':live.space}))
    expect(browser.get_by_text('Your current access: '+effective+'.',exact=True)).to_have_text('Your current access: '+effective+'.')
    expect(browser.locator('details[data-workflow]')).to_have_count(3 if effective=='reader' else 8)
    selective=browser.locator('details[data-workflow][data-workflow="selective-context"]')
    selective.locator('summary').click()
    expect(selective).to_contain_text('retain its exact revision_id and full-body hash')
    expect(selective).to_contain_text('max_tokens is a bytes/3 estimate')
    expect(browser.locator('details[data-task]')).to_have_count(1 if effective=='reader' else 7)
    compiler=browser.locator('details[data-workflow][data-workflow="knowledge-compiler"]')
    if effective=='reader':expect(compiler).to_have_count(0)
    else:
        compiler.locator('summary').click()
        expect(compiler).to_contain_text('enabled policy')
        expect(compiler).to_contain_text('compilation_verify')
    consolidate=browser.locator('details[data-workflow][data-workflow="consolidate"]')
    if effective=='reader':expect(consolidate).to_have_count(0)
    else:
        consolidate.locator('summary').click()
        expect(consolidate).to_contain_text('superseded result returns content_superseded (410)')


def test_stale_session_keeps_public_connection_and_skill_available(live,browser):
    browser.context.clear_cookies()
    browser.context.add_cookies([{'name':'c0_session','value':'x'*43,'url':live.origin,'secure':True}])
    browser.goto(live.origin+'/agents')
    expect(browser.get_by_role('heading',name='Use with AI',exact=True)).to_be_visible()
    expect(browser.get_by_role('textbox',name='MCP server URL',exact=True)).to_have_value(live.origin+'/mcp')
    expect(browser.get_by_role('link',name='Download skill',exact=True)).to_be_visible()
    expect(browser.get_by_role('button',name='Download ChatGPT plugin',exact=True)).to_have_count(0)
    expect(browser.locator('details[data-workflow]')).to_have_count(0)
