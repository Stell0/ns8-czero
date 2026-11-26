# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from czero_app.google_drive import DOC, FOLDER, SHORTCUT, SCOPE, FILE_LIMIT, GoogleDrive, folder_id_from_link
from czero_core.source_http import CollectionError

FOLDER_ID = 'test-folder'


def record(identifier, media='text/plain', **extra):
    return {'id': identifier, 'mimeType': media, 'name': identifier, 'version': '1', 'size': '19',
            'parents': [FOLDER_ID], 'trashed': False, 'capabilities': {'canDownload': True}, **extra}


class GoogleFixture:
    def __init__(self):
        self.folder = record(FOLDER_ID, FOLDER, ownedByMe=True, capabilities={'canListChildren': True})
        self.records = [record('first'), record('second', 'video/mp4')]
        self.content = b'Full UTF-8 original'
        self.tabs = [{'tabProperties': {'tabId': 'one'}}]
        self.scope = SCOPE
        self.calls = []
        self.on_read = lambda: None

    def document(self, host, path, **kwargs):
        self.calls.append((host, path, kwargs))
        location = urlsplit(path)
        if path == '/token':
            return {'access_token': 'fixture-access', 'token_type': 'Bearer', 'scope': self.scope,
                    'refresh_token': 'fixture-refresh'}
        if location.path == '/drive/v3/about':
            return {'user': {'permissionId': 'fixture-principal'}}
        if location.path.startswith('/v1/documents/'):
            return {'tabs': self.tabs}
        if location.path.endswith('/files'):
            return {'files': self.records}
        if location.path.endswith('/' + FOLDER_ID):
            return self.folder
        identifier = location.path.split('/')[-1]
        return next(r.copy() for r in self.records if r['id'] == identifier)

    def fetch(self, host, path, **kwargs):
        self.calls.append((host, path, kwargs))
        self.on_read()
        if sink := kwargs.get('sink'):
            return sink.write(self.content)
        return self.content


@pytest.fixture
def drive():
    api = GoogleFixture()
    service = GoogleDrive('fixture.apps.googleusercontent.com', 'private', Fernet(Fernet.generate_key()),
                          transport=lambda: api)
    subject, credential = service.exchange('code', 'verifier', 'https://c0.example/callback', True)
    assert subject == 'fixture-principal'
    assert 'fixture-access' not in credential and 'fixture-refresh' not in credential
    return service, api, credential


def test_exact_scope_offline_opt_in_and_pkce(drive):
    service, api, _ = drive
    for offline in (False, True):
        url = service.authorization_url('state', 'x' * 60, 'https://c0.example/callback', offline)
        parsed = urlsplit(url)
        params = parse_qs(parsed.query)
        assert parsed.netloc == 'accounts.google.com'
        assert params['scope'] == [SCOPE] and params['include_granted_scopes'] == ['false']
        assert params['access_type'] == ['offline' if offline else 'online']
        assert params['code_challenge_method'] == ['S256'] and 'client_secret' not in params
    for wrong in ('https://www.googleapis.com/auth/drive.file', SCOPE + ' https://www.googleapis.com/auth/drive'):
        api.scope = wrong
        with pytest.raises(CollectionError, match='drive_scope_mismatch'):
            service.exchange('c', 'v', 'https://c0.example/callback', True)


@pytest.mark.parametrize('link', ['https://drive.google.com/drive/folders/test-folder?usp=drive_link',
                                  'https://drive.google.com/drive/u/0/folders/test-folder'])
def test_folder_link(link):
    assert folder_id_from_link(link) == FOLDER_ID


@pytest.mark.parametrize('link', ['http://drive.google.com/drive/folders/x', 'https://example.org/drive/folders/x',
    'https://evil.example@drive.google.com/drive/folders/x', 'https://drive.google.com/file/d/x/view',
    'https://drive.google.com/drive/folders/../../x', 'https://drive.google.com/drive/folders/x?resourcekey=private'])
def test_rejects_unsupported_links(link):
    with pytest.raises(CollectionError, match='invalid_drive_folder'):
        folder_id_from_link(link)


def test_preview_collection_and_refresh_have_the_same_selection(drive):
    service, api, credential = drive
    preview = service.preview(credential, FOLDER_ID)
    assert preview == {'folder_name': FOLDER_ID, 'complete': True,
        'items': [{'title': 'first', 'outcome': 'include', 'reason': 'supported'},
                  {'title': 'second', 'outcome': 'skip', 'reason': 'unsupported_format'}]}
    items, cursor, complete = service.collect(credential, FOLDER_ID, {})
    assert complete and cursor == {}
    assert items == [{'key': 'first', 'title': 'first', 'media_type': 'text/plain', 'body': api.content,
                      'version': '1', 'google_mime': 'text/plain'}]
    assert any(kwargs.get('form', {}).get('grant_type') == 'refresh_token' for _, _, kwargs in api.calls)
    assert all('fixture-access' not in path for _, path, _ in api.calls)


@pytest.mark.parametrize('entry,reason', [
    (record('child', FOLDER), 'subfolder'), (record('child', SHORTCUT), 'shortcut'),
    (record('child', capabilities={'canDownload': False}), 'download_restricted'),
    (record('child', size=str(FILE_LIMIT + 1)), 'too_large'),
])
def test_explains_skips_without_fetching_contents(drive, entry, reason):
    service, api, credential = drive
    api.records = [entry]
    assert service.preview(credential, FOLDER_ID)['items'][0]['reason'] == reason
    assert not any('alt=media' in path for _, path, _ in api.calls)


def test_single_tab_export_and_multitab_skip(drive):
    service, api, credential = drive
    api.records = [record('notes', DOC)]
    items, _, _ = service.collect(credential, FOLDER_ID, {})
    assert items[0]['body'] == api.content
    assert any('/export?' in path for _, path, _ in api.calls)
    api.tabs[0]['childTabs'] = [{'tabProperties': {'tabId': 'two'}}]
    assert service.preview(credential, FOLDER_ID)['items'][0]['reason'] == 'multiple_tabs'


def test_move_during_download_does_not_publish(drive):
    service, api, credential = drive
    api.records = [record('private')]
    api.on_read = lambda: api.records[0].update(parents=['elsewhere'])
    assert service.preview(credential, FOLDER_ID)['items'] == [{'title': '', 'outcome': 'skip', 'reason': 'no_longer_available'}]
    assert service.collect(credential, FOLDER_ID, {})[0] == []


def test_unowned_and_shared_drive_roots_are_rejected(drive):
    service, api, credential = drive
    for changes in ({'ownedByMe': False}, {'ownedByMe': True, 'driveId': 'shared-drive'}):
        api.folder.update(changes)
        with pytest.raises(CollectionError, match='invalid_drive_folder'):
            service.preview(credential, FOLDER_ID)


def test_partial_download_and_changed_generation_cannot_be_imported(drive):
    service, api, credential = drive
    api.records = [record('notes')]
    api.content = b'short'
    with pytest.raises(CollectionError, match='source_transport_failed'):
        service.collect(credential, FOLDER_ID, {})
    api.content = b'Full UTF-8 original'
    api.on_read = lambda: api.records[0].update(version='2')
    with pytest.raises(CollectionError, match='source_transport_failed'):
        service.collect(credential, FOLDER_ID, {})


def test_page_checkpoint_is_private_and_reusable(drive):
    service, api, credential = drive
    document = api.document
    def pages(host, path, **kwargs):
        data = document(host, path, **kwargs)
        if urlsplit(path).path == '/drive/v3/files' and 'pageToken' not in parse_qs(urlsplit(path).query):
            data['nextPageToken'] = 'private-provider-cursor'
        return data
    api.document = pages
    assert service.preview(credential, FOLDER_ID)['complete'] is False
    _, cursor, complete = service.collect(credential, FOLDER_ID, {})
    assert not complete and 'private-provider-cursor' not in repr(cursor)
    assert service.collect(credential, FOLDER_ID, cursor)[2] is True


def test_native_private_config_preserved_and_old_restore_starts_disabled(tmp_path, monkeypatch):
    import runpy
    from pathlib import Path
    helper = Path(__file__).resolve().parents[2] / 'imageroot/bin/czero-create-drive-state'
    monkeypatch.setenv('AGENT_STATE_DIR', str(tmp_path))
    runpy.run_path(str(helper))
    state = tmp_path / 'google-drive.env'
    assert state.read_bytes() == b'' and state.stat().st_mode & 0o777 == 0o600
    private = json.dumps({'client_id': 'example', 'client_secret': 'secret',
                          'encryption_key': Fernet.generate_key().decode()})
    state.write_text('CZERO_GOOGLE_DRIVE_CONFIG=' + private + '\n')
    runpy.run_path(str(helper))
    assert state.read_text().split('=', 1)[1].strip() == private
    monkeypatch.delenv('CZERO_GOOGLE_DRIVE_FILE', raising=False)
    monkeypatch.setenv('CZERO_GOOGLE_DRIVE_CONFIG', private)
    assert GoogleDrive.configured().client_id == 'example'
    state.write_text('UNRELATED_SETTING=unexpected\n')
    with pytest.raises(SystemExit):
        runpy.run_path(str(helper))


def test_recheck_after_parsing_fences_move_change_and_access_loss(drive):
    service, api, credential = drive
    items = service.collect(credential, FOLDER_ID, {})[0]
    service.recheck(credential, FOLDER_ID, items)
    for changes, reason in [({'version': '2'}, 'source_transport_failed'),
                            ({'parents': ['elsewhere']}, 'drive_item_unavailable'),
                            ({'capabilities': {'canDownload': False}}, 'drive_item_unavailable')]:
        api.records[0] = record('first', **changes)
        with pytest.raises(CollectionError, match=reason):
            service.recheck(credential, FOLDER_ID, items)
    api.folder['ownedByMe'] = False
    with pytest.raises(CollectionError, match='invalid_drive_folder'):
        service.recheck(credential, FOLDER_ID, items)


def test_rejected_continuation_restarts_once(drive):
    service, api, credential = drive
    document = api.document
    def expired(host, path, **kwargs):
        data = document(host, path, **kwargs)
        if urlsplit(path).path == '/drive/v3/files':
            if 'pageToken' in parse_qs(urlsplit(path).query):
                raise CollectionError('drive_page_rejected')
            data['nextPageToken'] = 'rejected-google-token'
        return data
    api.document = expired
    _, next_page, _ = service.collect(credential, FOLDER_ID, {})
    items, restarted, complete = service.collect(credential, FOLDER_ID, next_page)
    assert items == [] and not complete and restarted['restarts'] == 1 and 'page' not in restarted
    _, next_page, _ = service.collect(credential, FOLDER_ID, restarted)
    with pytest.raises(CollectionError, match='drive_invalid_checkpoint'):
        service.collect(credential, FOLDER_ID, next_page)


def test_pdf_download_exceeds_text_limit_without_dropping_data(drive):
    service, api, credential = drive
    from czero_app.google_drive import PDF
    api.content = b'%PDF-' + bytes(3 * 1024 * 1024)
    api.records = [record('handbook', PDF, size=str(len(api.content)))]
    items = service.collect(credential, FOLDER_ID, {})[0]
    assert len(items) == 1 and items[0]['media_type'] == PDF and items[0]['body'] == api.content
    service.recheck(credential, FOLDER_ID, items)


def test_pdf_preview_explains_unreadable_file(drive):
    service, api, credential = drive
    from czero_app.google_drive import PDF
    api.content = b'This is not a PDF'
    api.records = [record('sample', PDF, size=str(len(api.content)))]
    assert service.preview(credential, FOLDER_ID)['items'] == [
        {'title': 'sample', 'outcome': 'skip', 'reason': 'invalid_pdf'}]


def test_preview_includes_mixed_pdf_and_explains_missing_text(drive, monkeypatch):
    from types import SimpleNamespace
    from czero_app.google_drive import PDF
    from czero_core import drive_pdf
    service, api, credential = drive
    api.content = b'%PDF-synthetic'
    api.records = [record('mixed', PDF, size=str(len(api.content)))]
    monkeypatch.setattr(drive_pdf, 'prepare_pdf_file',
                        lambda path: (SimpleNamespace(textless_pages=(1,)), []))
    assert service.preview(credential, FOLDER_ID)['items'] == [
        {'title': 'mixed', 'outcome': 'include', 'reason': 'pdf_text_layer_only', 'textless_page_count': 1, 'textless_pages': [1]}]


def test_preview_skips_pdf_over_page_limit(drive, monkeypatch):
    from czero_app.google_drive import PDF
    from czero_core import drive_pdf
    from czero_core.extraction import ExtractionError
    service, api, credential = drive
    api.content = b'%PDF-synthetic'
    api.records = [record('long', PDF, size=str(len(api.content)))]
    def over_limit(*_):
        raise ExtractionError('pdf_too_many_pages')
    monkeypatch.setattr(drive_pdf, 'prepare_pdf_file', over_limit)
    assert service.preview(credential, FOLDER_ID)['items'] == [
        {'title': 'long', 'outcome': 'skip', 'reason': 'pdf_too_many_pages'}]


def test_preview_skips_text_exceeding_extracted_document_bounds(drive):
    service, api, credential = drive
    api.content = b'x' * 1_000_001
    api.records = [record('long', size=str(len(api.content)))]
    assert service.preview(credential, FOLDER_ID)['items'] == [
        {'title': 'long', 'outcome': 'skip', 'reason': 'too_large'}]


def test_concurrent_large_previews_limit_memory_and_clean_up(drive, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from czero_app.google_drive import GoogleHTTP, PDF, PDF_LIMIT
    from czero_core import drive_pdf

    service, api, credential = drive
    api.records = [record('large', PDF, size=str(PDF_LIMIT))]
    entered, resume = threading.Event(), threading.Event()
    files = []

    class Response:
        status = 200
        length = PDF_LIMIT
        def read1(self, limit):
            assert limit <= 65536
            n = min(self.length, limit)
            block = b'%PDF-' + bytes(n - 5) if self.length == PDF_LIMIT else bytes(n)
            self.length -= n
            return block
        def getheader(self, key, default=None):
            return default

    class Connection:
        sock = None
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): pass

    def parse(path):
        assert path.stat().st_size == PDF_LIMIT
        assert path.stat().st_mode & 0o077 == 0
        files.append(path)
        entered.set()
        assert resume.wait(10)
        raise drive_pdf.ExtractionError('invalid_pdf')

    monkeypatch.setattr('http.client.HTTPSConnection', Connection)
    monkeypatch.setattr(api, 'fetch', GoogleHTTP().fetch)
    monkeypatch.setattr(drive_pdf, 'prepare_pdf_file', parse)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.preview, credential, FOLDER_ID)
        try:
            assert entered.wait(10)
            with pytest.raises(CollectionError, match='drive_preview_busy'):
                service.preview(credential, FOLDER_ID)
        finally:
            resume.set()
        assert first.result()['items'][0]['reason'] == 'invalid_pdf'
    assert files and all(not path.exists() for path in files)


def test_google_network_budget_excludes_parser_time(monkeypatch):
    """Two 25s parses still leave network time to verify membership after extraction."""
    import czero_app.google_drive as module
    from types import SimpleNamespace
    clock = [0.0]
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda: clock[0]))

    class Connection:
        sock = None
        def __init__(self, host, timeout):
            assert 0 < timeout <= 5
        def request(self, *args, **kwargs):
            clock[0] += 2
        def getresponse(self):
            return SimpleNamespace(read1=lambda _: b'', status=200, length=0,
                                   getheader=lambda key, default=None: default)
        def close(self): pass

    monkeypatch.setattr(module.http.client, 'HTTPSConnection', Connection)
    http = module.GoogleHTTP()
    for _ in range(2):
        http.fetch(module.DRIVE_HOST, '/drive/v3/files/example')
        clock[0] += 25
    http.fetch(module.DRIVE_HOST, '/drive/v3/files/folder')
    assert clock[0] == 56
    assert http.network_seconds == 34
