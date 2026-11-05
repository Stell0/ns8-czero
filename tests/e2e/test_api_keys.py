# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from playwright.sync_api import expect
from test_nebula_theme import assert_accessibility

SECRET='Copy this key now. It will not be shown again.'


def test_account_key_creation_disclosure_and_revocation(live,browser):
    browser.goto(live.origin+'/account')
    browser.get_by_role('button',name='Create API key',exact=True).click()
    dialog=browser.get_by_role('dialog')
    for theme in ('light','dark'):
        browser.emulate_media(color_scheme=theme)
        for width in (1440,390):
            browser.set_viewport_size({'width':width,'height':1000})
            assert_accessibility(browser)
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
    dialog.get_by_role('textbox',name='Name',exact=True).fill('Workflow fixture')
    dialog.get_by_role('checkbox',name='Shared',exact=True).check()
    dialog.get_by_role('button',name='Create API key',exact=True).press('Enter')
    expect(browser.get_by_role('textbox',name=SECRET,exact=True)).to_be_visible()
    secret=browser.get_by_role('textbox',name=SECRET,exact=True).input_value()
    assert secret.startswith('c0k_')
    browser.get_by_role('button',name='I saved the key',exact=True).press('Enter')
    expect(browser.get_by_role('textbox',name=SECRET,exact=True)).to_have_count(0)
    browser.reload()
    expect(browser.get_by_text('Workflow fixture',exact=False)).to_be_visible()
    assert secret not in browser.content()
    browser.get_by_role('button',name='Revoke API key',exact=True).click()
    dialog.get_by_role('button',name='Revoke API key',exact=True).click()
    expect(browser.get_by_text('Revoked',exact=False)).to_be_visible()
    assert live.rest.get('/api/v1/me',headers={'Authorization':'Bearer '+secret}).status_code==401


@pytest.mark.parametrize('role',['reader','editor'])
def test_reader_and_editor_key_creation_respects_current_permissions(live,browser,role):
    account=next(row for row in live.rest.get('/api/v1/access/accounts').json()['accounts'] if row['username']=='member')
    if role=='editor':
        assert live.rest.put('/api/v1/access/accounts/'+account['id'],json={'role':'editor'}).status_code==204
    shared=next(row['id'] for row in live.rest.get('/api/v1/spaces').json()['spaces'] if row['shared'])
    browser.context.clear_cookies()
    browser.context.add_cookies([{'name':'fixture_persona','value':'reader','url':live.origin,'secure':True,'sameSite':'Lax'}])
    browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/account')
    browser.get_by_role('button',name='Create API key',exact=True).click()
    dialog=browser.get_by_role('dialog')
    dialog.get_by_role('textbox',name='Name',exact=True).fill(role+' workflow')
    choice=dialog.get_by_role('checkbox',name='Shared',exact=True)
    choice.check()
    dialog.get_by_role('checkbox',name='Write',exact=True).check()
    if role=='reader':
        expect(choice).to_be_disabled()
        dialog.get_by_role('button',name='Create API key',exact=True).click()
        expect(dialog).to_contain_text('Write permission is required in every selected space. Review the key permissions.')
        expect(browser.get_by_role('textbox',name=SECRET,exact=True)).to_have_count(0)
        # Tampering with the browser cannot turn a Reader into a writer.
        denied=browser.evaluate("""async space=>{
          const me=await (await fetch('/api/v1/me')).json();
          return (await fetch('/api/v1/api-keys',{method:'POST',headers:{'Content-Type':'application/json','X-C0-CSRF':me.csrf_token},body:JSON.stringify({name:'Denied',lifetime_days:1,space_ids:[space],scopes:['c0:read','c0:write']})})).status;
        }""",shared)
        assert denied==403
        dialog.get_by_role('checkbox',name='Write',exact=True).uncheck()
    dialog.get_by_role('button',name='Create API key',exact=True).click()
    expect(browser.get_by_role('textbox',name=SECRET,exact=True)).to_be_visible()
    browser.get_by_role('button',name='I saved the key',exact=True).click()
    browser.reload()
    expect(browser.get_by_text(role+' workflow',exact=False)).to_be_visible()
    if role=='editor':expect(browser.get_by_text(role+' workflow',exact=False)).to_contain_text('c0:write')
