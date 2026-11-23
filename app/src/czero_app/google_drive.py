# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Google's server-side OAuth client and bounded, read-only My Drive collector."""
import base64
import hashlib
import http.client
import json
import os
import re
import stat
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit

from cryptography.fernet import Fernet, InvalidToken
from czero_core import extraction
from czero_core.extraction import ExtractionError
from czero_core.source_http import CollectionError, FetchError, retry_time

SCOPE = 'https://www.googleapis.com/auth/drive.readonly'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_HOST = 'oauth2.googleapis.com'
DRIVE_HOST = 'www.googleapis.com'
DOCS_HOST = 'docs.googleapis.com'
FILE_ID = re.compile(r'[A-Za-z0-9_-]{1,256}')
DOC = 'application/vnd.google-apps.document'
FOLDER = 'application/vnd.google-apps.folder'
SHORTCUT = 'application/vnd.google-apps.shortcut'
FIELDS = 'id,name,mimeType,parents,trashed,driveId,ownedByMe,size,version,capabilities(canDownload,canListChildren)'
PDF = 'application/pdf'
PDF_LIMIT = getattr(extraction, 'MAX_PDF_BYTES', extraction.MAX_UPLOAD)
FILE_LIMIT = 2 * 1024 * 1024
PAGE_SIZE = 2


def folder_id_from_link(link):
    """Only extract an ID. A submitted URL never becomes a network destination."""
    try:
        if not isinstance(link, str) or len(link) > 2048 or any(ord(c) < 33 for c in link):
            raise ValueError()
        url = urlsplit(link)
        match = re.fullmatch(r'/drive/(?:u/[0-9]+/)?folders/([A-Za-z0-9_-]{1,256})/?', url.path)
        if url.scheme != 'https' or url.netloc != 'drive.google.com' or url.fragment or not match:
            raise ValueError()
        pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True, max_num_fields=3)
        if any(k not in ('usp', 'pli') for k, _ in pairs):
            raise ValueError()
        return match[1]
    except ValueError:
        raise CollectionError('invalid_drive_folder') from None


class GoogleHTTP:
    """Exact provider origins only, no redirects, proxy credentials or URL logging."""
    def __init__(self):
        self.deadline = time.monotonic() + 58
        self.remaining = PAGE_SIZE * PDF_LIMIT + 2 * 1024 * 1024
        self.requests = 0

    def fetch(self, host, path, *, token=None, form=None, limit=128 * 1024):
        if host not in (TOKEN_HOST, DRIVE_HOST, DOCS_HOST) or not path.startswith('/'):
            raise ValueError('invalid_google_endpoint')
        if self.requests >= 18 or limit > self.remaining:
            raise CollectionError('source_run_item_limit')
        self.requests += 1
        def timeout():
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise CollectionError('source_transport_failed')
            return min(remaining, 5)
        connection = http.client.HTTPSConnection(host, timeout=timeout())
        headers = {'Accept-Encoding': 'identity'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        body = None
        if form is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            body = urlencode(form)
        try:
            connection.request('POST' if form is not None else 'GET', path, body=body, headers=headers)
            response = connection.getresponse()
            chunks = bytearray()
            while len(chunks) <= limit:
                if connection.sock:
                    connection.sock.settimeout(timeout())
                else:
                    timeout()
                chunk = response.read1(min(65536, limit + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            self.remaining -= len(chunks)
            if len(chunks) > limit:
                raise CollectionError('drive_size_limit')
            if response.status == 200:
                if response.length not in (0, None):
                    raise CollectionError('source_transport_failed')
                if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
                    raise CollectionError('source_transport_failed')
                return bytes(chunks)
            if response.status == 401:
                raise CollectionError('drive_reconnect_required')
            if (response.status == 400 and host == DRIVE_HOST and path.startswith('/drive/v3/files?')
                    and 'pageToken=' in path):
                raise CollectionError('drive_page_rejected')
            if host == TOKEN_HOST and response.status == 400:
                try:
                    invalid = json.loads(chunks).get('error') == 'invalid_grant'
                except (ValueError, AttributeError):
                    invalid = False
                if invalid:
                    raise CollectionError('drive_reconnect_required')
            if response.status in (408, 429, 500, 502, 503, 504):
                raise FetchError('source_http_' + str(response.status),
                                 retry_time(response.getheader('Retry-After', '')))
            if response.status in (403, 404, 410):
                # Distinguish service configuration failures from file permissions.
                if response.status == 403:
                    try:
                        reasons = json.loads(chunks)['error']['errors']
                        if any(e.get('reason') == 'exportSizeLimitExceeded' for e in reasons):
                            raise CollectionError('drive_size_limit')
                        if any(e.get('reason') in ('accessNotConfigured', 'insufficientPermissions', 'serviceDisabled') for e in reasons):
                            raise CollectionError('drive_provider_error')
                        if any(e.get('reason') in ('rateLimitExceeded', 'userRateLimitExceeded', 'dailyLimitExceeded')
                               for e in reasons):
                            raise FetchError('source_http_429')
                    except (ValueError, TypeError, KeyError, AttributeError):
                        pass
                raise CollectionError('drive_item_unavailable')
            raise CollectionError('drive_provider_error')
        except (OSError, http.client.HTTPException, UnicodeError, ValueError):
            raise CollectionError('source_transport_failed') from None
        finally:
            connection.close()

    def document(self, host, path, **kwargs):
        try:
            value = json.loads(self.fetch(host, path, **kwargs))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, RecursionError):
            raise CollectionError('drive_provider_error') from None


def secret(value):
    return isinstance(value, str) and 1 <= len(value) <= 8192 and all(33 <= ord(c) <= 126 for c in value)


@dataclass(frozen=True, repr=False)
class GoogleDrive:
    client_id: str
    client_secret: str
    cipher: Fernet
    transport: object = field(default=GoogleHTTP)
    instance_uri: str | None = None

    @classmethod
    def configured(cls, instance_uri=None):
        path = os.getenv('CZERO_GOOGLE_DRIVE_FILE')
        if not path:
            # NS8 delivers this one value through a module-owned mode-0600 env file.
            raw = os.getenv('CZERO_GOOGLE_DRIVE_CONFIG')
            return cls._from_json(raw, instance_uri) if raw else None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
                raise ValueError('invalid_drive_configuration')
            return cls._from_json(stream.read(16385), instance_uri)

    @classmethod
    def _from_json(cls, raw, instance_uri):
        try:
            value = json.loads(raw) if len(raw) <= 16384 else {}
            if not secret(value['client_id']) or not secret(value['client_secret']):
                raise ValueError()
            return cls(value['client_id'], value['client_secret'], Fernet(value['encryption_key']),
                       instance_uri=instance_uri)
        except (KeyError, TypeError, ValueError):
            raise ValueError('invalid_drive_configuration') from None

    def authorization_url(self, state, verifier, redirect_uri, offline):
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode()
        return AUTH_URL + '?' + urlencode({
            'client_id': self.client_id, 'redirect_uri': redirect_uri, 'response_type': 'code',
            'state': state, 'scope': SCOPE, 'access_type': 'offline' if offline else 'online',
            'prompt': 'consent select_account', 'include_granted_scopes': 'false',
            'code_challenge_method': 'S256', 'code_challenge': challenge,
        })

    def _token(self, http, form, *, initial):
        data = http.document(TOKEN_HOST, '/token', form={**form, 'client_id': self.client_id,
                                                       'client_secret': self.client_secret})
        scope = data.get('scope')
        if ((initial or scope is not None) and (not isinstance(scope, str) or set(scope.split()) != {SCOPE})):
            raise CollectionError('drive_scope_mismatch')
        if str(data.get('token_type', '')).lower() != 'bearer' or not secret(data.get('access_token')):
            raise CollectionError('drive_provider_error')
        return data

    def exchange(self, code, verifier, redirect_uri, offline):
        http = self.transport()
        tokens = self._token(http, {'grant_type': 'authorization_code', 'code': code,
                                    'redirect_uri': redirect_uri, 'code_verifier': verifier}, initial=True)
        access = tokens['access_token']
        user = http.document(DRIVE_HOST, '/drive/v3/about?fields=user(permissionId)', token=access).get('user', {})
        subject = user.get('permissionId') if isinstance(user, dict) else None
        if not isinstance(subject, str) or not FILE_ID.fullmatch(subject):
            raise CollectionError('drive_provider_error')
        if offline and not secret(tokens.get('refresh_token')):
            raise CollectionError('drive_offline_required')
        payload = {'client': self.client_id, 'callback': redirect_uri, 'access': access, 'refresh': tokens['refresh_token'] if offline else None}
        return subject, self.cipher.encrypt(json.dumps(payload).encode()).decode()

    def _access(self, credential, http):
        try:
            payload = json.loads(self.cipher.decrypt(credential.encode()))
        except (InvalidToken, ValueError, AttributeError):
            raise CollectionError('drive_reconnect_required') from None
        if payload.get('client') != self.client_id or (self.instance_uri and payload.get('callback') != self.instance_uri):
            raise CollectionError('drive_reconnect_required')
        if payload['refresh']:
            return self._token(http, {'grant_type': 'refresh_token', 'refresh_token': payload['refresh']},
                               initial=False)['access_token']
        return payload['access']

    def preview(self, credential, folder_id):
        result, _, complete, folder = self._page(credential, folder_id, {}, preview=True)
        return {'items': result, 'complete': complete, 'folder_name': folder}

    def collect(self, credential, folder_id, cursor):
        items, next_cursor, complete, _ = self._page(credential, folder_id, cursor, preview=False)
        return items, next_cursor, complete

    def recheck(self, credential, folder_id, items):
        """Verify the exact fetched versions after parsing, just before Core publishes."""
        if not isinstance(folder_id, str) or not FILE_ID.fullmatch(folder_id) or len(items) > PAGE_SIZE:
            raise CollectionError('invalid_drive_folder')
        http = self.transport()
        token = self._access(credential, http)
        _root(_metadata(http, token, folder_id), folder_id)
        for item in items:
            identifier = item['key']
            current = _metadata(http, token, identifier)
            if not _inside(current, identifier, folder_id) or _skip(current):
                raise CollectionError('drive_item_unavailable')
            if (current.get('version') != item['version'] or current.get('mimeType') != item['google_mime']
                    or _title(current.get('name')) != item['title']):
                raise CollectionError('source_transport_failed')

    def _page(self, credential, folder_id, cursor, *, preview):
        if not isinstance(folder_id, str) or not FILE_ID.fullmatch(folder_id):
            raise CollectionError('invalid_drive_folder')
        http = self.transport()
        token = self._access(credential, http)
        _root(_metadata(http, token, folder_id), folder_id)
        query = {'q': f"'{folder_id}' in parents and trashed = false", 'spaces': 'drive', 'corpora': 'user',
                 'pageSize': PAGE_SIZE, 'fields': f'nextPageToken,incompleteSearch,files({FIELDS})'}
        pages = cursor.get('pages', 0)
        if type(pages) is not int or not 0 <= pages < 5000:
            raise CollectionError('drive_folder_limit')
        page_token = None
        if cursor.get('page'):
            try:
                page_token = self.cipher.decrypt(cursor['page'].encode()).decode()
            except (ValueError, InvalidToken, AttributeError):
                raise CollectionError('drive_invalid_checkpoint') from None
            query['pageToken'] = page_token
        resets = cursor.get('restarts', 0)
        if type(resets) is not int or resets not in (0, 1):
            raise CollectionError('drive_invalid_checkpoint')
        try:
            page = http.document(DRIVE_HOST, '/drive/v3/files?' + urlencode(query), token=token)
        except CollectionError as error:
            if error.args == ('drive_page_rejected',) and page_token and not resets:
                # Drive explicitly requires a fresh traversal when a token expires.
                # Skip duplicates using Core's stable keys. Keep the run budget.
                return [], {'pages': pages + 1, 'restarts': 1}, False, ''
            if error.args == ('drive_page_rejected',) and page_token:
                raise CollectionError('drive_invalid_checkpoint') from None
            raise
        if page.get('incompleteSearch') or not isinstance(page.get('files'), list) or len(page['files']) > PAGE_SIZE:
            raise CollectionError('source_transport_failed')
        next_page = page.get('nextPageToken')
        if next_page is not None and (not secret(next_page) or next_page == page_token):
            raise CollectionError('drive_provider_error')
        output = []
        for entry in page['files']:
            item_id = entry.get('id')
            if not isinstance(item_id, str) or not FILE_ID.fullmatch(item_id):
                raise CollectionError('drive_provider_error')
            try:
                current = _metadata(http, token, item_id)
                if not _inside(current, item_id, folder_id):
                    raise CollectionError('drive_item_unavailable')
                reason = _skip(current)
                body = None
                note = None
                if not reason:
                    reason, body = _read(http, token, current)
                    if preview and not reason and current['mimeType'] == PDF:
                        from czero_core.source_updates import prepare_drive_document
                        try:
                            document, _ = prepare_drive_document(body, PDF)
                            if getattr(document, 'textless_pages', ()):
                                note = 'pdf_text_layer_only'
                        except ExtractionError as error:
                            reason = _pdf_skip(error.code)
                # A move, edit or download restriction during export invalidates the bytes.
                final = _metadata(http, token, item_id)
                if not _inside(final, item_id, folder_id):
                    raise CollectionError('drive_item_unavailable')
                if not isinstance(final.get('version'), str) or not re.fullmatch(r'[0-9]{1,20}', final['version']):
                    raise CollectionError('drive_provider_error')
                if current.get('version') != final.get('version') or current.get('mimeType') != final.get('mimeType'):
                    raise CollectionError('source_transport_failed')
                reason = _skip(final) or reason
                title = _title(final.get('name'))
                if preview:
                    output.append({'title': title, 'outcome': 'skip' if reason else 'include', 'reason': reason or note or 'supported'})
                elif not reason:
                    media = _media(final, title)
                    output.append({'key': item_id, 'title': title, 'media_type': media, 'body': body,
                                   'version': final['version'], 'google_mime': final['mimeType']})
            except CollectionError as error:
                # A vanished or denied file cannot disclose its cached listing title.
                if error.args != ('drive_item_unavailable',):
                    raise
                if preview:
                    output.append({'title': '', 'outcome': 'skip', 'reason': 'no_longer_available'})
        # Revalidate the selected root too before handing this page to Core.
        final_folder = _metadata(http, token, folder_id)
        _root(final_folder, folder_id)
        next_cursor = {'page': self.cipher.encrypt(next_page.encode()).decode(), 'pages': pages + 1, 'restarts': resets} if next_page else {}
        return output, next_cursor, not next_page, _title(final_folder.get('name'))


def _metadata(http, token, identifier):
    if not isinstance(identifier, str) or not FILE_ID.fullmatch(identifier):
        raise CollectionError('drive_provider_error')
    return http.document(DRIVE_HOST, '/drive/v3/files/' + identifier + '?' + urlencode({'fields': FIELDS}), token=token)


def _root(folder, folder_id):
    if (folder.get('id') != folder_id or folder.get('mimeType') != FOLDER or folder.get('driveId')
            or folder.get('trashed') is not False or folder.get('ownedByMe') is not True
            or folder.get('capabilities', {}).get('canListChildren') is not True):
        raise CollectionError('invalid_drive_folder')


def _title(value):
    if not isinstance(value, str) or not value.strip():
        raise CollectionError('drive_provider_error')
    return ''.join(c if c.isprintable() else ' ' for c in value).strip()[:256] or 'Untitled'


def _inside(record, identifier, folder_id):
    return (record.get('id') == identifier and record.get('trashed') is False
            and record.get('parents') == [folder_id] and not record.get('driveId'))


def _media(record, title):
    if record['mimeType'] == PDF:
        return PDF
    if (record['mimeType'] in ('text/markdown', 'text/x-markdown')
            or (record['mimeType'] == 'text/plain' and title.lower().endswith(('.md', '.markdown')))):
        return 'text/markdown'
    return 'text/plain'


def _pdf_skip(code):
    if code in ('encrypted_pdf', 'too_large', 'pdf_too_many_pages'):
        return code
    if code in ('no_text', 'unsupported_scan'):
        return 'pdf_needs_ocr'
    if code in ('parser_timeout', 'resource_limit'):
        return 'pdf_parser_limit'
    return 'invalid_pdf'


def _skip(record):
    media = record.get('mimeType')
    if media == FOLDER:
        return 'subfolder'
    if media == SHORTCUT:
        return 'shortcut'
    if media not in (DOC, PDF, 'text/plain', 'text/markdown', 'text/x-markdown'):
        return 'unsupported_format'
    if record.get('capabilities', {}).get('canDownload') is not True:
        return 'download_restricted'
    if media != DOC and int(record.get('size', 0)) > (PDF_LIMIT if media == PDF else FILE_LIMIT):
        return 'too_large'
    return None


def _read(http, token, record):
    fid = record['id']
    if record['mimeType'] == DOC:
        tabs = http.document(DOCS_HOST, '/v1/documents/' + fid + '?' + urlencode({
            'includeTabsContent': 'true', 'fields': 'tabs(tabProperties(tabId),childTabs(tabProperties(tabId)))'
        }), token=token).get('tabs', [])
        if len(tabs) != 1 or tabs[0].get('childTabs') or not tabs[0].get('tabProperties', {}).get('tabId'):
            return 'multiple_tabs', None
        path = '/drive/v3/files/' + fid + '/export?mimeType=text%2Fplain'
    else:
        path = '/drive/v3/files/' + fid + '?alt=media'
    try:
        body = http.fetch(DRIVE_HOST, path, token=token, limit=PDF_LIMIT if record['mimeType'] == PDF else FILE_LIMIT)
    except CollectionError as error:
        if error.args == ('drive_size_limit',):
            return 'too_large', None
        raise
    if record['mimeType'] != DOC and 'size' in record and len(body) != int(record['size']):
        raise CollectionError('source_transport_failed')
    if record['mimeType'] == PDF:
        return (None, body) if body.startswith(b'%PDF-') else ('invalid_pdf', None)
    try:
        if not body.decode('utf-8').strip():
            return 'empty_file', None
        if b'\0' in body:
            return 'not_utf8', None
    except UnicodeError:
        return 'not_utf8', None
    return None, body
