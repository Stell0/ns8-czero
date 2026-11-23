# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real C0 HTTPS/session/PostgreSQL flow with synthetic responses at Google's boundary."""
import hashlib
import base64
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from cryptography.fernet import Fernet
from playwright.sync_api import expect


def test_drive_consent_preview_save_and_disconnect(request, monkeypatch, tmp_path):
    from czero_app.google_drive import DRIVE_HOST, FOLDER, SCOPE, TOKEN_HOST, GoogleHTTP

    configuration = tmp_path / 'drive.json'
    configuration.write_text(json.dumps({
        'client_id': 'browser-example', 'client_secret': 'example-secret',
        'encryption_key': Fernet.generate_key().decode(),
    }))
    configuration.chmod(0o600)
    monkeypatch.setenv('CZERO_GOOGLE_DRIVE_FILE', str(configuration))
    pdf = (Path(__file__).resolve().parents[1] / 'fixtures/evidence/sample.pdf').read_bytes()
    children = ['Notes', 'Archive']
    challenge = {}
    seen = set()

    def fetch(_http, host, path, *, token=None, form=None, **_):
        endpoint = urlsplit(path)
        if host == TOKEN_HOST and endpoint.path == '/token':
            grant = form['grant_type']
            seen.add(grant)
            if grant == 'authorization_code':
                digest = hashlib.sha256(form['code_verifier'].encode()).digest()
                assert base64.urlsafe_b64encode(digest).decode().rstrip('=') == challenge['value']
                assert form['code'] == 'fixture-code'
            else:
                assert grant == 'refresh_token' and form['refresh_token'] == 'fixture-refresh'
            result = {'access_token': 'fixture-access', 'refresh_token': 'fixture-refresh', 'scope': SCOPE, 'token_type': 'Bearer'}
        else:
            assert host == DRIVE_HOST and token == 'fixture-access'
            if endpoint.path == '/drive/v3/about':
                result = {'user': {'permissionId': 'fixture-user'}}
            elif endpoint.path == '/drive/v3/files':
                assert parse_qs(endpoint.query)['q'] == ["'MyFolder' in parents and trashed = false"]
                offset = int(parse_qs(endpoint.query).get('pageToken', ['0'])[0])
                result = {'files': [{'id': child} for child in children[offset:offset + 2]]}
                if offset + 2 < len(children):
                    result['nextPageToken'] = str(offset + 2)
            elif endpoint.path == '/drive/v3/files/MyFolder':
                result = {'id': 'MyFolder', 'name': 'Fixture folder', 'mimeType': FOLDER,
                          'ownedByMe': True, 'trashed': False, 'capabilities': {'canListChildren': True}}
            elif endpoint.path.rsplit('/', 1)[-1] in children:
                identifier = endpoint.path.rsplit('/', 1)[1]
                if parse_qs(endpoint.query).get('alt') == ['media']:
                    assert identifier in ('Notes','Later')
                    seen.add('file')
                    return pdf if identifier == 'Later' else f'Complete {identifier} document'.encode()
                result = {'id': identifier, 'name': identifier, 'version': '1', 'parents': ['MyFolder'],
                          'trashed': False, 'capabilities': {'canDownload': True},
                          'mimeType': FOLDER if identifier == 'Archive' else ('application/pdf' if identifier == 'Later' else 'text/plain')}
            else:
                raise AssertionError('Unexpected Drive endpoint')
        return json.dumps(result).encode()

    monkeypatch.setattr(GoogleHTTP, 'fetch', fetch)
    live = request.getfixturevalue('live')
    page = request.getfixturevalue('browser')
    page.context.clear_cookies()
    page.goto(live.origin + '/auth/login')
    page.goto(live.origin + '/automatic-sources?' + urlencode({'space_id': live.space}))

    def consent(route):
        query = parse_qs(urlsplit(route.request.url).query)
        assert query['scope'] == [SCOPE] and query['access_type'] == ['offline']
        assert query['code_challenge_method'] == ['S256']
        assert query['include_granted_scopes'] == ['false']
        uri = query['redirect_uri'][0]
        assert uri == live.origin + '/auth/google-drive/callback'
        challenge['value'] = query['code_challenge'][0]
        route.fulfill(status=302, headers={'location': uri + '?' + urlencode({'state': query['state'][0], 'code': 'fixture-code'})})

    page.route('https://accounts.google.com/o/oauth2/v2/auth?*', consent)
    page.get_by_role('button', name='Add automatic source', exact=True).press('Enter')
    drawer = page.get_by_role('dialog')
    drawer.get_by_role('button', name='Source type Website').click()
    page.get_by_role('option', name='Google Drive folder', exact=True).click()
    drawer.get_by_role('checkbox', name='Allow background updates while I’m signed out').check()
    drawer.get_by_role('button', name='Connect Google account', exact=True).click()
    expect(drawer.get_by_role('status')).to_contain_text('Google account connected')
    drawer.get_by_role('textbox', name='Folder link').fill('https://drive.google.com/drive/folders/MyFolder')
    drawer.get_by_role('button', name='Preview', exact=True).press('Enter')
    expect(drawer.get_by_role('heading', name='Folder preview · Fixture folder')).to_be_focused()
    expect(drawer.get_by_text('Skip · Subfolder', exact=True)).to_be_visible()
    expect(drawer.get_by_text('Include', exact=True)).to_be_visible()
    expect(drawer.get_by_role('textbox', name='Title', exact=True)).to_have_value('Fixture folder')
    if screenshots := os.getenv('CZERO_NEBULA_SCREENSHOTS'):
        directory = Path(screenshots)
        directory.mkdir(parents=True, exist_ok=True)
        for theme, width in (('light', 1440), ('dark', 390)):
            page.set_viewport_size({'width':width, 'height':960})
            page.emulate_media(color_scheme=theme)
            drawer.get_by_role('region', name='Folder preview · Fixture folder').scroll_into_view_if_needed()
            page.screenshot(path=str(directory / f'drive-preview-{theme}-{width}.png'))
    drawer.get_by_role('button', name='Save configuration').press('Enter')
    expect(drawer).to_have_count(0)
    page.reload()
    row = page.get_by_role('row').filter(has_text='Fixture folder')
    expect(row).to_contain_text('Paused')
    row.get_by_role('button', name='Edit source').click()
    # The saved folder can be previewed without sending its private link to
    # the browser. Enable manual collection, then run the shipped worker.
    live.pause_worker()
    drawer.get_by_role('button', name='Preview', exact=True).click()
    expect(drawer.get_by_role('heading', name='Folder preview · Fixture folder')).to_be_visible()
    drawer.get_by_role('checkbox', name='Enable source updates').check()
    drawer.get_by_role('button', name='Manual updates').click()
    drawer.get_by_role('button', name='Save configuration').click()
    expect(drawer).to_have_count(0)

    from czero_app.job_handlers import build_registry
    from czero_app.worker import update_sources
    from czero_core.worker import Worker
    from sqlalchemy import text
    app, _, _, _, database, issuer = request.getfixturevalue('application')
    owner_id = live.rest.get('/api/v1/me').json()['id']
    with database.engine.connect() as connection:
        owner_key = connection.execute(text('SELECT account_key FROM c0_accounts WHERE id=:id'), {'id':owner_id}).scalar_one()
    monkeypatch.setenv('CZERO_OIDC_ISSUER', issuer)
    monkeypatch.setenv('CZERO_OWNER_LDAP_UUID', str(owner_key))
    monkeypatch.setenv('CZERO_AUTH_PUBLIC_ORIGIN', live.origin)
    monkeypatch.setenv('CZERO_BASE_PATH', '')
    monkeypatch.setenv('CZERO_DATABASE_URL', os.environ['CZERO_TEST_DATABASE_URL'])
    monkeypatch.setenv('CZERO_SOURCE_DIR', str(live.originals.root))
    registry = build_registry(database, live.originals, access=app.state.auth.access)

    def read(path):
        response = live.rest.get('/api/v1/' + path, params={'space_id': live.space})
        response.raise_for_status()
        return response.json()

    definition = read('automatic-sources')['definitions'][0]
    assert definition['enabled'] and definition['interval_seconds'] is None
    path = 'automatic-sources/' + definition['id']

    def complete_run():
        for _ in range(6):
            update_sources()
            Worker(database, registry).tick()
            runs = read(path + '/runs')['runs']
            if runs and runs[0]['state'] == 'complete':
                return read(path + '/documents')['documents']
        raise AssertionError('Source update failed to complete: ' + str(runs[0]['error_code'] if runs else 'no run'))

    docs = complete_run()
    assert [doc['title'] for doc in docs] == ['Notes']
    first = docs[0]['id']
    body = read('source-documents/' + first)
    assert body['state'] == 'ready' and body['body'] == 'Complete Notes document'
    assert 'MyFolder' not in json.dumps(body['metadata'])
    # A new child arrives after the previous scan. The next run refreshes
    # Google credentials and imports it after genuine C0 browser logout.
    children.append('Later')
    with page.expect_response(lambda response: response.url.split('?')[0].endswith('/' + definition['id'] + '/run')) as started:
        row.get_by_role('button', name='Update now').click()
    assert started.value.ok
    csrf = page.request.get(live.origin + '/api/v1/me').json()['csrf_token']
    logout = page.request.post(live.origin + '/auth/logout', headers={'Origin': live.origin, 'X-C0-CSRF': csrf})
    assert logout.ok
    page.goto(logout.json()['logout_url'])
    assert page.request.get(live.origin + '/api/v1/me').status == 401
    docs = complete_run()
    indexed = {doc['title']: doc['id'] for doc in docs}
    assert set(indexed) == {'Notes','Later'} and indexed['Notes'] == first
    later = read('source-documents/' + indexed['Later'])
    assert later['state'] == 'ready' and later['media_type'] == 'application/pdf' and later['body'].strip()

    page.goto(live.origin + '/auth/login')
    page.goto(live.origin + '/sources/' + indexed['Later'] + '?' + urlencode({'space_id':live.space}))
    expect(page.get_by_role('article')).to_contain_text(later['body'].strip()[:20])
    page.goto(live.origin + '/automatic-sources?' + urlencode({'space_id':live.space}))
    row.get_by_role('button', name='Edit source').click()
    drawer.get_by_role('button', name='Disconnect Google account').click()
    page.get_by_role('dialog').filter(has_text='Disconnecting stops updates').get_by_role('button', name='Disconnect Google account').click()
    expect(drawer.get_by_role('button', name='Connect Google account', exact=True)).to_be_visible()
    drawer.get_by_role('button', name='Close', exact=True).click()
    row.get_by_role('button', name='Remove configuration').click()
    page.get_by_role('dialog').get_by_role('button', name='Remove configuration').click()
    expect(row).to_have_count(0)
    assert read('source-documents/' + indexed['Later'])['state'] == 'ready'
    assert seen == {'authorization_code', 'refresh_token', 'file'}
