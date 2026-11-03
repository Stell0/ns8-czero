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
        expect(browser.locator('#sign-out')).to_be_visible()
    browser.goto(live.origin+'/agents?'+urlencode({'space_id':live.space}))
    browser.locator('#reader-root > summary').click()
    expect(browser.locator('#guide-status')).to_have_text('Your current access: '+effective+'.')
    expect(browser.locator('#guide-workflows > details')).to_have_count(3 if effective=='reader' else 7)
    selective=browser.locator('#guide-workflows > details[data-workflow="selective-context"]')
    selective.locator('summary').click()
    expect(selective).to_contain_text('retain its exact revision_id and full-body hash')
    expect(selective).to_contain_text('max_tokens is a bytes/3 estimate')
    expect(browser.locator('#guide-tasks > details')).to_have_count(1 if effective=='reader' else 7)
    consolidate=browser.locator('#guide-workflows > details[data-workflow="consolidate"]')
    if effective=='reader':expect(consolidate).to_have_count(0)
    else:
        consolidate.locator('summary').click()
        expect(consolidate).to_contain_text('superseded result returns content_superseded (410)')
