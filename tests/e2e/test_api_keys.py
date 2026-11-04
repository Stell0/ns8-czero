# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
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
