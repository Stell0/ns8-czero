# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Nebula presentation on the real, signed-in website with disposable data."""
import os
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from playwright.sync_api import expect

ACCESSIBILITY = (Path(__file__).resolve().parents[1] / 'accessibility_probe.js').read_text()


def assert_accessibility(page):
    result = page.evaluate(ACCESSIBILITY)
    assert result['controls_checked'] > 0
    if page.get_by_role('dialog').count()==0:assert result['links_checked'] > 0
    assert not any(count for key, count in result.items() if key.startswith(('missing_', 'unnamed_'))), result


def check_layout(browser, language, theme, width):
    expect(browser.locator('html')).to_have_attribute('lang',language)
    expect(browser.locator('header')).to_be_visible()
    browser.evaluate('document.fonts.ready')
    styles=browser.evaluate("""() => ({
        font:getComputedStyle(document.body).fontFamily,
        loaded:[...document.fonts].filter(f=>f.family==='Poppins' && f.status==='loaded').length,
        overflow:document.documentElement.scrollWidth>innerWidth,
        sticky:getComputedStyle(document.querySelector('header')).position,
        dark:document.documentElement.classList.contains('dark'),
        background:getComputedStyle(document.body).backgroundColor,
        foreground:getComputedStyle(document.body).color,
        contrast:(()=>{
          const canvas=document.createElement('canvas'),c=canvas.getContext('2d');
          const light=color=>{c.fillStyle=color;c.fillRect(0,0,1,1);const a=[...c.getImageData(0,0,1,1).data].slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return .2126*a[0]+.7152*a[1]+.0722*a[2]};
          const s=getComputedStyle(document.body),a=light(s.color),b=light(s.backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        })()
    })""")
    assert styles['font'].startswith('Poppins') and styles['loaded']==2
    assert not styles['overflow'] and styles['sticky']=='sticky', (width,styles)
    assert styles['dark']==(theme=='dark') and styles['contrast']>=4.5, styles
    assert_accessibility(browser)
    browser.locator('.skip-link').focus()
    browser.keyboard.press('Enter')
    expect(browser.locator('main')).to_be_focused()
    if width==390:
        menu=browser.locator('header').get_by_role('button',name='Navigation' if language=='en' else 'Navigazione',exact=True)
        menu.click()
        expect(browser.get_by_role('dialog').get_by_role('link',name='Home',exact=True)).to_be_visible()
        assert_accessibility(browser)
        browser.keyboard.press('Escape')
        expect(browser.get_by_role('dialog')).to_have_count(0)
        expect(menu).to_be_focused()
    else:
        brand=browser.locator('aside').get_by_role('link',name='C0',exact=True)
        brand.focus()
        assert brand.evaluate("e=>getComputedStyle(e).outlineStyle")!='none'
    return styles


def test_nebula_reader_themes_responsive_layout_and_keyboard(live,browser):
    version=live.upload('# Nebula reader\n\nCurrent source evidence.\n\n## A section\n\n| Setting | Value |\n| --- | --- |\n| Mode | Automatic |\n')
    document_url='/sources/'+version['source_id']
    external=[]
    browser.on('request',lambda request:external.append(request.url) if urlsplit(request.url).netloc!=urlsplit(live.origin).netloc else None)
    backgrounds={}
    for language in ('en','it'):
        browser.goto(live.origin+'/account')
        browser.locator('main').get_by_role('button',name=re.compile(r'^(Language|Lingua) ')).click()
        browser.get_by_role('option',name='Italiano' if language=='it' else 'English',exact=True).click()
        expect(browser.locator('html')).to_have_attribute('lang',language)
        for theme in ('light','dark'):
            browser.emulate_media(color_scheme=theme)
            for width in (1440,390):
                browser.set_viewport_size({'width':width,'height':1000})
                for route in ('/','/wiki','/search','/agents','/projects',document_url):
                    browser.goto(live.origin+route+'?'+urlencode({'space_id':live.space}))
                    expect(browser.locator('header button:visible').first).to_be_visible()
                    backgrounds[theme]=check_layout(browser,language,theme,width)['background']
                    if route==document_url:expect(browser.get_by_role('article')).to_contain_text('Current source evidence.')
                    if os.getenv('CZERO_NEBULA_SCREENSHOTS') and route in ('/',document_url):
                        directory=Path(os.environ['CZERO_NEBULA_SCREENSHOTS']);directory.mkdir(parents=True,exist_ok=True)
                        browser.screenshot(path=str(directory/f'{language}-{theme}-{width}-{"home" if route=="/" else "reader"}.png'))
    assert backgrounds['light']!=backgrounds['dark'] and not external


def test_nebula_admin_keyboard_and_nested_skip_links(live,browser):
    browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
    for theme in ('light','dark'):
        browser.emulate_media(color_scheme=theme)
        for width in (1440,390):
            browser.set_viewport_size({'width':width,'height':1000})
            for route in ('/admin','/admin/advanced','/admin/work','/admin/spaces'):
                url=live.origin+route+'?'+urlencode({'space_id':live.space})
                browser.goto(url)
                expect(browser.locator('header').get_by_role('button',name=re.compile(r'^Knowledge space '))).to_be_visible()
                expect(browser.locator('h1')).to_be_visible()
                browser.locator('body').press('Tab')
                expect(browser.locator('.skip-link')).to_be_focused()
                browser.keyboard.press('Enter')
                expect(browser.locator('main')).to_be_focused()
                assert browser.url==url+'#main'
                check_layout(browser,'en',theme,width)
