# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from playwright.sync_api import expect
from test_nebula_theme import assert_accessibility


def test_account_key_creation_disclosure_and_revocation(live,browser):
    browser.goto(live.origin+'/?view=account')
    expect(browser.locator('#api-keys-panel')).to_be_visible()
    for theme in ('light','dark'):
        browser.emulate_media(color_scheme=theme)
        for width in (1440,390):
            browser.set_viewport_size({'width':width,'height':1000})
            assert_accessibility(browser)
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
    browser.locator('#api-key-name').fill('Workflow fixture')
    browser.locator('#api-key-spaces input').first.check()
    browser.locator('#api-key-create button').press('Enter')
    expect(browser.locator('#api-key-secret-panel')).to_be_visible()
    assert browser.locator('#api-key-secret').input_value().startswith('c0k_')
    browser.locator('#api-key-dismiss').press('Enter')
    expect(browser.locator('#api-key-secret')).to_have_value('')
    browser.locator('#api-key-refresh').click()
    expect(browser.locator('#api-key-list')).to_contain_text('Workflow fixture')
    browser.get_by_role('button',name='Revoke key Workflow fixture',exact=True).click()
    expect(browser.locator('#api-key-list')).to_contain_text('Revoked')


@pytest.mark.parametrize('role',['reader','editor'])
def test_reader_and_editor_key_creation_respects_current_permissions(live,browser,role):
    account=next(row for row in live.rest.get('/api/v1/access/accounts').json()['accounts'] if row['username']=='member')
    if role=='editor':
        assert live.rest.put('/api/v1/access/accounts/'+account['id'],json={'role':'editor'}).status_code==204
    shared=next(row['id'] for row in live.rest.get('/api/v1/spaces').json()['spaces'] if row['shared'])
    browser.context.clear_cookies()
    browser.context.add_cookies([{'name':'fixture_persona','value':'reader','url':live.origin,'secure':True,'sameSite':'Lax'}])
    browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/?view=account')
    expect(browser.locator('#api-keys-panel')).to_be_visible()
    browser.locator('#api-key-name').fill(role+' workflow')
    browser.locator('#api-key-permissions').select_option('write')
    choice=browser.locator('#api-key-spaces input[value="'+shared+'"]')
    choice.check()
    if role=='reader':
        browser.locator('#api-key-create button').click()
        expect(browser.locator('#api-key-status')).to_have_text('Write access is required in every selected space.')
        expect(browser.locator('#api-keys-panel')).to_be_visible()
        expect(browser.locator('#api-key-secret-panel')).to_be_hidden()
        # Stale or tampered client metadata cannot grant server-side Write access.
        choice.evaluate("node => node.dataset.role='editor'")
        browser.locator('#api-key-create button').click()
        expect(browser.locator('#api-key-status')).to_have_text('Key creation was denied. Review your access and key settings.')
        expect(browser.locator('#api-keys-panel')).to_be_visible()
        expect(browser.locator('#api-key-name')).to_have_value(role+' workflow')
        browser.locator('#api-key-permissions').select_option('read')
        choice.check()
    browser.locator('#api-key-create button').click()
    expect(browser.locator('#api-key-secret-panel')).to_be_visible()
    browser.locator('#api-key-dismiss').click()
    browser.locator('#api-key-refresh').click()
    expect(browser.locator('#api-key-list')).to_contain_text(role+' workflow')
    if role=='editor':expect(browser.locator('#api-key-list')).to_contain_text('Read, Write')
