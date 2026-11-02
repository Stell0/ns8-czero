# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Nebula presentation on the real, signed-in website with disposable data."""
import os
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from playwright.sync_api import expect

ACCESSIBILITY = (Path(__file__).resolve().parents[1] / 'accessibility_probe.js').read_text()


def assert_accessibility(page):
    result = page.evaluate(ACCESSIBILITY)
    assert result['controls_checked'] > 0 and result['links_checked'] > 0
    assert not any(count for key, count in result.items() if key.startswith(('missing_', 'unnamed_'))), result


def test_nebula_reader_themes_responsive_layout_and_keyboard(live, browser):
    version = live.upload('# Nebula reader\n\nCurrent source evidence.\n\n## A section\n\n'
                          '| Setting | Value |\n| --- | --- |\n| Mode | Automatic |\n')
    # Discover the complete document through the real, selected-space library.
    browser.goto(live.origin + '/sources?' + urlencode({'space_id': live.space, 'source': version['source_id']}))
    expect(browser.locator('#reader-status')).to_have_text('Complete document loaded.', timeout=20000)
    document_url = browser.url
    external = []
    browser.on('request', lambda request: external.append(request.url)
               if urlsplit(request.url).netloc != urlsplit(live.origin).netloc else None)
    for theme, background, foreground in [('light', 'rgb(249, 250, 251)', 'rgb(17, 24, 39)'),
                                         ('dark', 'rgb(17, 24, 39)', 'rgb(249, 250, 251)')]:
        browser.emulate_media(color_scheme=theme)
        for width in (1440, 390):
            browser.set_viewport_size({'width': width, 'height': 1000})
            for route in ('/', '/wiki', '/search', '/agents', '/projects', document_url):
                target = route if route.startswith('https:') else live.origin + route + '?' + urlencode({'space_id': live.space})
                browser.goto(target)
                expect(browser.locator('.topbar')).to_be_visible()
                browser.evaluate('document.fonts.ready')
                styles = browser.evaluate('''() => ({
                    background: getComputedStyle(document.documentElement).backgroundColor,
                    foreground: getComputedStyle(document.documentElement).color,
                    font: getComputedStyle(document.body).fontFamily,
                    loaded: [...document.fonts].filter(font => font.family === 'Poppins' && font.status === 'loaded').length === 2,
                    overflow: document.documentElement.scrollWidth > innerWidth,
                    sidebar: getComputedStyle(document.querySelector('.topbar')).position
                })''')
                assert styles['background'] == background and styles['foreground'] == foreground
                assert styles['font'].startswith('Poppins') and styles['loaded']
                assert not styles['overflow'], (route, width, theme)
                assert styles['sidebar'] == ('fixed' if width == 1440 else 'relative')
                assert_accessibility(browser)
                if route == '/':
                    summary = browser.locator('.menu > summary')
                    summary.press('Enter')
                    expect(browser.locator('.menu[open] .menu-items')).to_be_visible()
                    assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    summary.press('Enter')
                    expect(browser.locator('.menu .menu-items')).not_to_be_visible()
                for notice in browser.locator('.notice').all():
                    assert notice.evaluate('element => getComputedStyle(element).color') == (
                        'rgb(30, 64, 175)' if theme == 'light' else 'rgb(219, 234, 254)')
                # Start keyboard traversal at the page's first control.
                browser.locator('.skip-link').focus()
                browser.keyboard.press('Tab')
                expect(browser.locator('.topbar .brand')).to_be_focused()
                assert browser.locator('.topbar .brand').evaluate("element => getComputedStyle(element).outlineStyle") != 'none'
                if os.getenv('CZERO_NEBULA_SCREENSHOTS') and route in ('/', document_url):
                    directory = Path(os.environ['CZERO_NEBULA_SCREENSHOTS'])
                    directory.mkdir(parents=True, exist_ok=True)
                    browser.locator('.topbar .brand').evaluate('element => element.blur()')
                    browser.screenshot(path=str(directory / f'{theme}-{width}-{"home" if route == "/" else "reader"}.png'))
    assert external == [], 'Fonts and presentation must stay local'
    expect(browser.locator('#reader-document')).to_contain_text('Current source evidence.')


def test_nebula_admin_keyboard_and_nested_skip_links(live, browser):
    browser.context.clear_cookies()
    browser.goto(live.origin + '/auth/login')
    for theme in ('light', 'dark'):
        browser.emulate_media(color_scheme=theme)
        for width in (1440, 390):
            browser.set_viewport_size({'width': width, 'height': 1000})
            for route in ('/admin', '/admin/advanced', '/admin/work', '/admin/spaces'):
                url = live.origin + route + '?' + urlencode({'space_id': live.space})
                browser.goto(url)
                expect(browser.locator('h1')).to_be_visible()
                assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth'), (route, width, theme)
                assert_accessibility(browser)
                browser.locator('.skip-link').focus()
                browser.keyboard.press('Enter')
                expect(browser.locator('#main-content')).to_be_focused()
                assert browser.url == url + '#main-content'
                browser.locator('.topbar .brand').focus()
                assert browser.locator('.topbar .brand').evaluate("element => getComputedStyle(element).outlineStyle") != 'none'
