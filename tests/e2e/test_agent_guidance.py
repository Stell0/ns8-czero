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
    expect(browser.locator('details[data-task]')).to_have_count(2 if effective=='reader' else 15)
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


def test_compiler_prompts_follow_selected_space_languages_and_clipboard_fallback(live,browser):
    import re
    browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
    requests=[]
    browser.on('request',lambda request: requests.append((request.method,request.url)))
    browser.goto(live.origin+'/agents?'+urlencode({'space_id':live.space}))
    prompts=browser.locator('details[data-task]')
    expect(prompts).to_have_count(15)
    for language in ('en','it'):
        browser.goto(live.origin+'/account')
        browser.locator('main').get_by_role('button',name=re.compile(r'^(Language|Lingua) ')).click()
        browser.get_by_role('option',name='Italiano' if language=='it' else 'English',exact=True).click()
        browser.goto(live.origin+'/agents?'+urlencode({'space_id':live.space}))
        for theme in ('light','dark'):
            browser.emulate_media(color_scheme=theme)
            for width in (1280,390):
                browser.set_viewport_size({'width':width,'height':900})
                for task in ('compile','bootstrap','feedback','daily','weekly','chatgpt','external','status'):
                    entry=browser.locator(f'details[data-task="{task}"]')
                    entry.locator('summary').click()
                    field=entry.get_by_role('textbox')
                    expect(field).to_be_visible()
                    value=field.input_value()
                    assert live.space in value and live.origin+'/mcp' in value
                    assert 'c0-knowledge-compiler' in value and 'UTC' in value
                    if task=='chatgpt':
                        assert 'BLOCKED' in value and ('daily' in value or 'giornalier' in value)
                        assert 'weekly' in value or 'settimanale' in value
                    assert not browser.evaluate('document.documentElement.scrollWidth > innerWidth')
                    entry.locator('summary').click()
    # Clipboard may be denied by host policy; text stays selectable and keyboard reachable.
    browser.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>Promise.reject(new Error('denied'))}})")
    entry=browser.locator('details[data-task="status"]');entry.locator('summary').click()
    entry.get_by_role('button').focus();browser.keyboard.press('Enter')
    expect(entry.get_by_role('textbox')).to_be_visible()
    assert not [(method,url) for method,url in requests if method not in ('GET','HEAD','OPTIONS') and '/api/v1/compilation' in url]


def test_compiler_prompts_bind_project_manifest_timezone_and_schedule(live,browser):
    import json
    browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
    # Existing disposable fixture credentials authorize only this test namespace.
    stored=live.rest.get('/api/v1/project',params={'space_id':live.space}).json()
    manifest=stored['data']['manifest']
    manifest.update(name='Bound schedule fixture',timezone='Europe/Rome')
    manifest['schedule'].update(enabled=False,daily_local_time='06:17',weekly_day='sunday',weekly_local_time='08:29')
    response=live.rest.put('/api/v1/project',params={'space_id':live.space},json={
        'manifest':manifest,'expected_revision':stored['revision'],
        'authorization_ref':'synthetic:operator','idempotency_key':'prompt-project'})
    assert response.status_code==200,response.text
    browser.goto(live.origin+'/agents?'+urlencode({'space_id':live.space}))
    entry=browser.locator('details[data-task="chatgpt"]');entry.locator('summary').click()
    value=entry.get_by_role('textbox').input_value()
    assert all(s in value for s in ('Europe/Rome','06:17','08:29','sunday','"enabled": false','manifest_version',live.space))
