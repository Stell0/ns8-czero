# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real authorization-code flow in disposable QEMU; no secrets in output."""
from html.parser import HTMLParser
import hashlib
from http.cookiejar import CookieJar
import json
from pathlib import Path
import ssl
import sys
import time
from uuid import uuid4
from profile_fixture import verify_profile
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import build_opener, HTTPCookieProcessor, HTTPSHandler, Request

STATE = Path("/tmp/czero-oidc-fixture")


class LoginForm(HTMLParser):
    def __init__(self, *, logout=False):
        super().__init__()
        self.action = None
        self.fields = {}
        self.logout = logout

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and (self.logout or values.get("id") == "kc-form-login"):
            self.action = values.get("action")
        if tag == "input" and values.get("type") == "hidden" and values.get("name"):
            self.fields[values["name"]] = values.get("value", "")


class Browser:
    def __init__(self, origin):
        self.origin = origin
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies),
            HTTPSHandler(context=ssl.create_default_context(cafile=str(STATE / "ca.pem"))))

    def request(self, path, data=None, method=None, headers=None):
        request = Request(urljoin(self.origin, path), data=data, method=method, headers=headers or {})
        try:
            response = self.opener.open(request, timeout=15)
        except HTTPError as response:
            return response.code, response.read(), response.geturl()
        with response:
            return response.status, response.read(), response.geturl()

    def login(self, username, password, expected=200):
        status, body, url = self.request("/auth/login")
        assert status == 200, f"Provider login page unavailable (HTTP {status})"
        form = LoginForm()
        form.feed(body.decode())
        assert form.action, "Provider login form missing"
        form.fields.update(username=username, password=password)
        status, _, _ = self.request(urljoin(url, form.action), urlencode(form.fields).encode(), headers={
            "Content-Type": "application/x-www-form-urlencoded"})
        assert status == expected, "Provider callback rejected"
        status, body, _ = self.request("/api/v1/me")
        assert status == expected if expected == 200 else status == 401, "Session admission mismatch"
        return json.loads(body) if status == 200 else None

    def api(self, path, data=None, method=None, csrf=None):
        headers = {"Origin": self.origin}
        if csrf:
            headers["X-C0-CSRF"] = csrf
        if data is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data).encode()
        return self.request(path, data, method, headers)

    def upload(self, profile, content, *, filename, title, media_type, retain_original=False, source_id=None, expected_revision=None, metadata=None, space_id=None):
        boundary = 'czero-' + uuid4().hex
        fields = {'title': title, 'media_type': media_type, 'retain_original': 'true' if retain_original else 'false',
                  'metadata': json.dumps(metadata or {})}
        if source_id:
            fields.update(source_id=source_id, expected_revision=str(expected_revision))
        parts = []
        for key, value in fields.items():
            parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode())
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + content + b'\r\n')
        parts.append((f'--{boundary}--\r\n').encode())
        path='/api/v1/sources/upload'+('?space_id='+space_id if space_id else '')
        return self.request(path, b''.join(parts), 'POST', {
            'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Origin': self.origin, 'X-C0-CSRF': profile['csrf_token']})

    def logout(self, profile):
        status, body, _ = self.api("/auth/logout", {}, "POST", profile["csrf_token"])
        assert status == 200, "Local logout failed"
        logout = json.loads(body)
        assert logout["provider_logout"], "Provider logout unavailable"
        status, body, url = self.request(logout["logout_url"])
        assert status == 200, "Provider logout confirmation unavailable"
        form = LoginForm(logout=True)
        form.feed(body.decode())
        assert form.action, "Provider logout form missing"
        form.fields["confirmLogout"] = "Logout"
        status, _, _ = self.request(urljoin(url, form.action), urlencode(form.fields).encode(), headers={
            "Content-Type": "application/x-www-form-urlencoded"})
        assert status == 200, "Provider logout confirmation failed"
        status, _, _ = self.api("/api/v1/me")
        assert status == 401, "Logged-out session remains usable"
        status, body, _ = self.request("/auth/login")
        form = LoginForm()
        form.feed(body.decode())
        assert status == 200 and form.action, "Provider SSO session survived logout"


OBJECT_SCHEMA = {"type":"object","properties":{"name":{"type":"string","maxLength":64},"count":{"type":"integer","minimum":0}},"required":["name","count"]}


def object_fixtures(owner,profile):
    """Use authenticated public services, never fixture SQL, for app records."""
    for name,label in (("fixture-inventory","Inventory"),("fixture-projects","Projects")):
        status,_,_=owner.api("/api/v1/object-types/"+name)
        if status==404:
            status,_,_=owner.api("/api/v1/object-types",{"name":name,"label":label,"schema":OBJECT_SCHEMA,"unique_fields":["name"]},"POST",profile["csrf_token"])
            assert status==201,"Cannot register fixture object type"
        else:
            assert status==200,"Cannot inspect fixture object type"


def source_state(browser, version, expected, *, seconds=95):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status, body, _ = browser.api('/api/v1/sources/' + version['source_id'] + '/versions?limit=100')
        assert status == 200, 'Cannot inspect source history'
        current = next(v for v in json.loads(body)['versions'] if v['id'] == version['id'])
        if current['state'] == expected and (expected != 'ready' or current['original_present'] == current['retain_original']):
            return current
        assert current['state'] != 'failed' or expected == 'failed', 'Source extraction failed unexpectedly'
        time.sleep(2)
    raise AssertionError('Source extraction or post-persistence cleanup did not complete')


def seed_text_sources(owner, profile, *, title='Disposable text evidence'):
    request = {'idempotency_key':'native-text-'+uuid4().hex, 'title':title,
        'body':'Selected native memory evidence café 東京', 'media_type':'text/plain',
        'metadata':{'origin':'disposable investigation'}}
    records = []
    for index in range(2):
        status, body, _ = owner.api('/api/v1/sources/ingest-text', request, 'POST', profile['csrf_token'])
        assert status == 202, 'Native text ingestion failed'
        receipt = json.loads(body)
        assert receipt['state'] == 'queued', 'Native text receipt claimed extraction completion'
        assert receipt['content_hash'] == hashlib.sha256(request['body'].encode()).hexdigest(), 'Native text hash mismatch'
        records.append({'version':receipt, 'text':request['body'], 'text_request':request})
        request = {**request, 'idempotency_key':'native-text-'+uuid4().hex,
            'source_id':receipt['source_id'], 'expected_revision':1,
            'body':request['body']+'\nAdditional observation retained as a new version.'}
    return records


def verify_text_receipts(browser, profile, records):
    for record in records:
        if 'text_request' not in record:
            continue
        request = record['text_request']
        status, body, _ = browser.api('/api/v1/sources/ingest-text', request, 'POST', profile['csrf_token'])
        assert status == 202 and json.loads(body) == record['version'], 'Recovered text receipt/revision changed'
        status, _, _ = browser.api('/api/v1/sources/ingest-text', {**request,'body':'Conflicting retry'}, 'POST', profile['csrf_token'])
        assert status == 409, 'Recovered text receipt accepted changed content'


def seed_sources(owner, profile):
    manifest = json.loads(Path('/tmp/czero-evidence-manifest.json').read_text())
    uploaded = []
    for sample in manifest:
        content = Path('/tmp/czero-evidence-' + sample['filename']).read_bytes()
        status, body, _ = owner.upload(profile, content, filename=sample['filename'], title='Disposable ' + sample['filename'],
            media_type=sample['media_type'], metadata={'fixture': sample['filename']})
        assert status == 202, 'Cannot upload a format fixture'
        row = json.loads(body)
        assert row['content_hash'] == hashlib.sha256(content).hexdigest(), 'Uploaded source hash changed'
        uploaded.append({'version': row, 'text': sample['text']})
        status, body, _ = owner.upload(profile, content, filename=sample['filename'], title='Disposable ' + sample['filename'],
            media_type=sample['media_type'], metadata={'fixture': sample['filename']})
        assert status == 202 and json.loads(body)['id'] == row['id'], 'Identical upload duplicated evidence'
    first = uploaded[0]['version']
    revised = manifest[0]['text'] + '\nRevised source evidence'
    status, body, _ = owner.upload(profile, revised.encode(), filename='revised.txt', title='Disposable sample.txt',
        media_type='text/plain', source_id=first['source_id'], expected_revision=1)
    assert status == 202 and json.loads(body)['number'] == 2, 'Changed source did not create a version'
    uploaded.append({'version': json.loads(body), 'text': revised})
    for title, content, retained, expected in [('Retained evidence', b'Retained inventory evidence', True, 'ready'),
                                               ('Quarantined evidence', b'\xff', False, 'failed')]:
        status, body, _ = owner.upload(profile, content, filename='original.txt', title=title, media_type='text/plain', retain_original=retained)
        assert status == 202, 'Cannot upload original-retention fixture'
        row = json.loads(body)
        uploaded.append({'version': row, 'text': content.decode() if expected == 'ready' else None,
            'original_hash': hashlib.sha256(content).hexdigest(), 'expected_state': expected})
    uploaded.extend(seed_text_sources(owner, profile))
    for record in uploaded:
        row = record['version']; expected = record.get('expected_state', 'ready')
        source_state(owner, row, expected)
        status, body, _ = owner.api('/api/v1/sources/' + row['source_id'])
        assert status == 200, 'Cannot inspect persisted source'
        record['source_revision'] = json.loads(body)['revision']
        if expected == 'ready':
            status, body, _ = owner.api('/api/v1/source-versions/' + row['id'] + '/document')
            assert status == 200, 'Extracted document unavailable'
            document = json.loads(body)
            assert document['body'] == record['text'], 'Full extracted text changed'
            record['document'] = document
            status, body, _ = owner.api('/api/v1/documents/' + document['id'] + '/chunks')
            assert status == 200 and json.loads(body)['chunks'], 'Extracted chunks unavailable'
            record['chunks'] = json.loads(body)['chunks']
    return uploaded


def verify_sources(browser, records):
    for record in records:
        row = record['version']; expected = record.get('expected_state', 'ready')
        actual = source_state(browser, row, expected, seconds=15)
        assert all(actual[key] == row[key] for key in ('id','source_id','number','content_hash','media_type','retain_original')), 'Recovered source version changed'
        status, body, _ = browser.api('/api/v1/sources/' + row['source_id'])
        assert status == 200 and json.loads(body)['revision'] == record['source_revision'], 'Recovered source revision changed'
        if expected == 'ready':
            status, body, _ = browser.api('/api/v1/source-versions/' + row['id'] + '/document')
            actual = json.loads(body)
            assert status == 200 and all(actual[k] == record['document'][k] for k in ('id','version_id','body','text_hash','locations')), 'Recovered extracted document changed'
            status, body, _ = browser.api('/api/v1/documents/' + actual['id'] + '/chunks')
            assert status == 200 and json.loads(body)['chunks'] == record['chunks'], 'Recovered chunk IDs/text/offsets changed'
            status, body, _ = browser.api('/api/v1/chunks/' + record['chunks'][0]['id'] + '/citation')
            assert status == 200 and json.loads(body)['source_hash'] == row['content_hash'], 'Recovered citation unavailable'
        else:
            assert actual['error_code'] == 'invalid_text', 'Quarantine reason changed'
        status, body, _ = browser.api('/api/v1/source-versions/' + row['id'] + '/original')
        if 'original_hash' in record:
            assert status == 200 and hashlib.sha256(body).hexdigest() == record['original_hash'], 'Retained or quarantined original changed'
        else:
            assert status == 404, 'Default original was not removed after persistence'
    status, body, _ = browser.api('/api/v1/sources/search?query=inventory&limit=100')
    assert status == 200 and len(json.loads(body)['citations']) >= 5, 'Recovered full-text search missing evidence'


def verify_capabilities(browser, role):
    status, body, _ = browser.api('/agents/capabilities.json')
    assert status == 200, 'Caller capability discovery unavailable'
    capabilities = json.loads(body)
    assert capabilities['authenticated'] and capabilities['role'] == role, 'Capability role is stale'
    assert capabilities['interfaces']['mcp'] and capabilities['mcp_url'] == browser.origin+'/mcp', 'Installed MCP discovery unavailable'
    assert capabilities['oauth']['authorization_server'] == browser.origin+'/oauth', 'Installed OAuth discovery mismatch'
    status, body, _ = browser.api('/openapi.json')
    assert status == 200 and json.loads(body)['x-c0-interfaces']['mcp_url'] == capabilities['mcp_url'], 'Installed OpenAPI MCP metadata mismatch'
    definitions = {operation['name']: operation for operation in capabilities['operations']}
    assert {'objects_get', 'wiki_pages_get', 'documents_get', 'knowledge_search'} <= definitions.keys(), 'Reader operations missing'
    assert ('wiki_pages_create' in definitions) == (role != 'reader'), 'Editor discovery mismatch'
    assert ('schedules_list' in definitions) == (role == 'admin'), 'Admin discovery mismatch'
    if role == 'reader':
        assert all(operation['minimum_role'] == 'reader' and operation['read_only']
                   for operation in definitions.values()), 'Reader discovery exposes writes'


def seed_oauth_clients(browser, profile):
    clients = []
    for name, path, scopes in [('Disposable knowledge client', 'knowledge', ['c0:read','c0:write']),
                              ('Disposable disabled client', 'disabled', ['c0:read'])]:
        status, body, _ = browser.api('/api/v1/oauth/clients', {'client_name': name,
            'redirect_uris': ['https://client.example.test/' + path], 'allowed_scopes': scopes},
            'POST', profile['csrf_token'])
        assert status == 201, 'Cannot approve disposable OAuth client'
        client = json.loads(body)
        if path == 'disabled' and client['enabled']:
            status, body, _ = browser.api('/api/v1/oauth/clients/' + client['client_id'],
                {'enabled': False, 'expected_revision': client['revision']}, 'PUT', profile['csrf_token'])
            assert status == 200, 'Cannot disable disposable OAuth client'
            client = json.loads(body)
        assert client['token_endpoint_auth_method'] == 'none' and 'client_secret' not in client, 'Client approval exposes a secret'
        clients.append(client)
    return clients


def verify_oauth_clients(browser, expected):
    status, body, _ = browser.api('/api/v1/oauth/clients')
    assert status == 200, 'Recovered approved clients unavailable'
    actual = {client['client_id']: client for client in json.loads(body)['clients']}
    assert all(actual.get(client['client_id']) == client for client in expected), 'Recovered client approval metadata changed'


def probe():
    payload = json.loads((STATE / "personas.json").read_text())
    origin = "https://" + payload["host"]
    owner = Browser(origin)
    profile = owner.login("c0owner", payload["password"])
    assert profile["role"] == "admin" and profile["is_owner"], "Owner identity mismatch"
    verify_profile(owner, profile)
    verify_capabilities(owner, 'admin')
    status, body, _ = owner.api("/api/v1/schedules")
    assert status == 200 and len(json.loads(body)["schedules"]) >= 2, "Admin schedules unavailable"
    object_fixtures(owner,profile)
    identity_file = STATE / "owner-id.txt"
    if identity_file.exists():
        assert identity_file.read_text() == profile["id"], "Owner identity changed after restart"
    else:
        identity_file.write_text(profile["id"])
    session = next(cookie for cookie in owner.cookies if cookie.name == "c0_session")
    assert session.secure and session.has_nonstandard_attr("HttpOnly"), "Session cookie is not protected"
    denied = Browser(origin)
    denied.login("c0member", payload["password"], expected=403)
    status, body, _ = owner.api("/api/v1/access/accounts")
    assert status == 200, "Owner cannot list members"
    accounts = json.loads(body)["accounts"]
    member = next(account for account in accounts if account["username"] == "c0member")
    path = "/api/v1/access/accounts/" + member["id"]
    status, _, _ = owner.api(path, {"role": "reader"}, "PUT", profile["csrf_token"])
    assert status == 204, "Owner cannot admit reader"
    reader = Browser(origin)
    current = reader.login("c0member", payload["password"])
    assert current["role"] == "reader", "Reader grant not persisted"
    verify_profile(reader, current)
    verify_capabilities(reader, 'reader')
    status, _, _ = reader.api("/api/v1/access/accounts")
    assert status == 403, "Reader can administer"
    status, _, _ = reader.api('/api/v1/oauth/clients')
    assert status == 403, 'Reader can inspect approved external clients'
    status,_,_=reader.api("/api/v1/objects?type_name=fixture-inventory")
    assert status==200,"Reader cannot browse objects"
    status,_,_=reader.api("/api/v1/objects",{"type_name":"fixture-inventory","data":{"name":"denied","count":0}},"POST",current["csrf_token"])
    assert status==403,"Reader can mutate objects"
    status, _, _ = reader.api('/api/v1/sources')
    assert status == 200, 'Reader cannot browse sources'
    status, _, _ = reader.upload(current, b'denied', filename='reader.txt', title='Denied', media_type='text/plain')
    assert status == 403, 'Reader can upload evidence'
    status, _, _ = reader.api('/api/v1/wiki/pages')
    assert status == 200, 'Reader cannot browse Wiki'
    status, _, _ = reader.api('/api/v1/wiki/pages', {'slug':'denied','title':'Denied','body':'Denied','idempotency_key':'reader-denied'}, 'POST', current['csrf_token'])
    assert status == 403, 'Reader can author Wiki'
    from uuid import uuid4
    record_name="probe-"+uuid4().hex
    for role in ("editor", "admin"):
        status, _, _ = owner.api(path, {"role": role}, "PUT", profile["csrf_token"])
        assert status == 204, "Role update failed"
        status, body, _ = reader.api("/api/v1/me")
        assert status == 401, "Changed membership retained renewable authority"
        previous_reader = reader
        reader = Browser(origin)
        current = reader.login("c0member", payload["password"])
        assert current["role"] == role, "Fresh session role is stale"
        assert previous_reader.api('/api/v1/me')[0] == 401, 'Fresh sign-in revived prior membership authority'
        verify_capabilities(reader, role)
        status, _, _ = reader.api("/api/v1/access/accounts")
        assert status == (200 if role == "admin" else 403), "Role authorization mismatch"
        status, _, _ = reader.api("/api/v1/schedules")
        assert status == (200 if role == "admin" else 403), "Schedule authorization mismatch"
        status,body,_=reader.api("/api/v1/objects",{"type_name":"fixture-inventory","data":{"name":record_name+role,"count":1}},"POST",current["csrf_token"])
        assert status==201,"Editor/Admin object write failed"
        created=json.loads(body)
        status,_,_=reader.api("/api/v1/objects/"+created["id"]+"?expected_revision=1",None,"DELETE",current["csrf_token"])
        assert status==200,"Editor/Admin object delete failed"
        status, body, _ = reader.upload(current, b'Role-gated source evidence', filename='role.txt', title=record_name + role, media_type='text/plain')
        assert status == 202, 'Editor/Admin source upload failed'
        knowledge_request(reader, current, 'wiki/pages', {'slug':record_name+role,'title':'Role fixture','body':'Authored role fixture'}, 'POST', 201)
        status,_,_=reader.api("/api/v1/object-types",{"name":"fixture-inventory","label":"Inventory","schema":OBJECT_SCHEMA},"POST",current["csrf_token"])
        assert status==(409 if role=="admin" else 403),"Object type role mismatch"
    status, _, _ = owner.api(path, {"role": None}, "PUT", profile["csrf_token"])
    assert status == 204, "Role revocation failed"
    status, _, _ = reader.api("/api/v1/me")
    assert status == 401, "Revoked renewable session remains admitted"
    status, _, _ = reader.api('/agents/capabilities.json')
    assert status == 401, 'Revoked renewable session can discover private capabilities'
    owner.logout(profile)
    missing = Browser(origin)
    status, _, _ = missing.api("/api/v1/me")
    assert status == 401, "Anonymous REST access accepted"
    status, _, _ = missing.request("/api/v1/me", headers={"Authorization": "Bearer invalid"})
    assert status == 401, "Invalid bearer accepted"


def knowledge_request(browser, profile, path, data=None, method=None, expected=200):
    if data is not None:
        data = {**data, 'idempotency_key': 'fixture-' + uuid4().hex}
    status, body, _ = browser.api('/api/v1/' + path, data, method, profile['csrf_token'])
    assert status == expected, 'Knowledge operation failed (HTTP %s)' % status
    return json.loads(body)


def seed_wiki_memory(browser, profile):
    create = {'slug':'persistent-memory', 'title':'Persistent procedure',
        'body':'Original selected observation café 東京', 'metadata':{'status':'unverified'},
        'idempotency_key':'persistent-memory-create'}
    update = {**create, 'body':create['body']+'\nLater observation retained.',
        'expected_revision':1, 'idempotency_key':'persistent-memory-update'}
    receipts=[]
    for data in (create,update):
        status,body,_=browser.api('/api/v1/wiki/pages/upsert',data,'POST',profile['csrf_token'])
        assert status==200, 'Cannot seed revision-safe Wiki memory'
        receipts.append(json.loads(body))
    return {'requests':[create,update],'receipts':receipts}


def verify_wiki_memory_receipts(browser, profile, expected):
    for data,receipt in zip(expected['requests'],expected['receipts']):
        status,body,_=browser.api('/api/v1/wiki/pages/upsert',data,'POST',profile['csrf_token'])
        assert status==200 and json.loads(body)==receipt, 'Recovered Wiki retry receipt changed'
    status,_,_=browser.api('/api/v1/wiki/pages/upsert',{**expected['requests'][1],
        'idempotency_key':'persistent-stale-'+uuid4().hex},'POST',profile['csrf_token'])
    assert status==409, 'Recovered Wiki accepted stale overwrite'
    status,body,_=browser.api('/api/v1/wiki/pages/resolve?slug=persistent-memory')
    assert status==200 and json.loads(body)==expected['receipts'][1], 'Recovered Wiki slug/revision changed'
    for receipt in expected['receipts']:
        status,body,_=browser.api('/api/v1/wiki/pages/'+receipt['id']+'?revision='+str(receipt['revision']))
        assert status==200 and json.loads(body)['content']==receipt['content'], 'Recovered immutable memory revision changed'


def seed_knowledge(browser, profile, sources, objects):
    page = knowledge_request(browser, profile, 'wiki/pages', {
        'slug': 'persistent-wiki', 'title': 'Persistent Wiki', 'body': '# Inventory\n\nOriginal authored café 東京',
        'metadata': {'author': 'external fixture'}}, 'POST', 201)
    original = page['content']
    page = knowledge_request(browser, profile, 'wiki/pages/' + page['id'], {
        'title': 'Revised Wiki', 'body': '# Revised inventory\n\nIndependent authored claims',
        'metadata': {'author': 'external fixture'}, 'expected_revision': 1}, 'PUT')
    entities = [knowledge_request(browser, profile, 'entities', {
        'kind': 'system', 'label': 'Persistent entity ' + str(i), 'aliases': ['Persistent alias ' + str(i)]}, 'POST', 201)
        for i in range(4)]
    relations = [knowledge_request(browser, profile, 'knowledge/relations', {
        'source_id': entities[i]['id'], 'target_id': entities[i+1]['id'], 'kind': 'depends-on'}, 'POST', 201)
        for i in range(3)]
    chunk = sources[0]['chunks'][0]['id']
    claims = [knowledge_request(browser, profile, 'claims', {
        'entity_id': entities[0]['id'], 'page_id': page['id'], 'predicate': 'operating-system',
        'value': {'name': name}, 'evidence_chunk_ids': [chunk], 'valid_from': '2026-10-14T00:00:00Z'}, 'POST', 201)
        for name in ('Linux', 'BSD')]
    references = [knowledge_request(browser, profile, 'entities/' + entities[0]['id'] + '/references', {
        'target_kind': kind, 'target_id': key}, 'POST', 201) for kind, key in (
            ('page', page['id']), ('object', objects[0]['id']), ('source', sources[0]['version']['source_id']),
            ('document', sources[0]['document']['id']), ('chunk', chunk))]
    entities = [knowledge_request(browser, profile, 'entities/' + entity['id']) for entity in entities]
    claims = [knowledge_request(browser, profile, 'claims/' + claim['id']) for claim in claims]
    references = knowledge_request(browser, profile, 'entities/' + entities[0]['id'] + '/references')['references']
    memory = seed_wiki_memory(browser, profile)
    changes = knowledge_request(browser, profile, 'knowledge/changes?limit=100')['changes']
    return {'page': page, 'original': original, 'entities': entities, 'relations': relations,
            'claims': claims, 'references': references, 'changes': changes, 'memory': memory}


def verify_knowledge(browser, profile, expected):
    get = lambda path: knowledge_request(browser, profile, path)
    page = expected['page']; key = page['id']
    assert get('wiki/pages/' + key) == page, 'Recovered Wiki page changed'
    assert get('wiki/pages/' + key + '?revision=1')['content'] == expected['original'], 'Immutable Wiki revision changed'
    assert len(get('wiki/pages/' + key + '/revisions')['revisions']) == 2, 'Wiki revision history missing'
    status, body, _ = browser.api('/api/v1/wiki/pages/' + key + '/export?format=markdown&revision=1')
    assert status == 200 and body.decode() == expected['original']['body'], 'Markdown export changed'
    assert get('wiki/pages/' + key + '/export') == page, 'JSON export changed'
    searched = get('knowledge/search?query=independent+authored&kind=wiki&mode=text&rerank=off')
    assert searched['retrieval_method'] == 'text' and searched['fallback_reason'] is None, 'Provider-free text changed'
    assert any(h['id'] == page['content']['id'] and h['resource_id'] == key and h['wiki']['revision'] == 2 for h in searched['hits']), 'Recovered Wiki FTS/revision citation missing'
    for entity in expected['entities']:
        assert get('entities/' + entity['id']) == entity, 'Entity or aliases changed'
        assert get('entities/resolve?' + urlencode({'alias': entity['aliases'][0]['label']}))['id'] == entity['id'], 'Alias no longer resolves'
    for claim in expected['claims']:
        assert get('claims/' + claim['id']) == claim, 'Claim/provenance changed'
    root = expected['entities'][0]['id']
    claims = get('claims?entity_id=' + root)['claims']
    assert {c['id'] for c in claims} == {c['id'] for c in expected['claims']}, 'Conflicting claims lost'
    for depth in (1, 2, 3):
        graph = get('knowledge/graph/' + root + '?direction=out&depth=' + str(depth))
        assert len(graph['nodes']) == depth + 1 and not graph['truncated'], 'Recovered graph depth changed'
        assert {r['id'] for r in graph['relations']} == {r['id'] for r in expected['relations'][:depth]}, 'Graph relations changed'
    assert get('entities/' + root + '/references')['references'] == expected['references'], 'Typed knowledge references changed'
    assert get('knowledge/changes?limit=100')['changes'] == expected['changes'], 'Knowledge change cursor history changed'



class ScopedBrowser:
    """Public HTTP selector, shared by native recovery and signed local tests."""
    def __init__(self, browser, space_id):
        self.browser, self.space_id = browser, space_id

    def api(self, path, data=None, method=None, csrf=None):
        return self.browser.api(path + ('&' if '?' in path else '?') +
                                'space_id=' + self.space_id, data, method, csrf)


def seed_protected_space(browser, profile, member_id):
    def request(path, data=None, method=None, expected=200):
        status, body, _ = browser.api('/api/v1/' + path, data, method, profile['csrf_token'])
        assert status == expected, 'Cannot seed protected recovery fixture'
        return json.loads(body)
    space = request('spaces', {'name':'Retained protected recovery',
        'idempotency_key':'native-protected-space'}, 'POST', 201)
    scoped = ScopedBrowser(browser, space['id'])
    grant = request('spaces/' + space['id'] + '/grants/' + member_id,
        {'role':'reader','expected_revision':0,'idempotency_key':'native-retained-reader'}, 'PUT')
    memory = seed_wiki_memory(scoped, profile)
    records = seed_text_sources(scoped, profile, title='Retained protected evidence')
    original=b'Retained protected original evidence cafe'
    status, body, _ = browser.upload(profile, original, filename='protected.txt',
        title='Retained protected original', media_type='text/plain', retain_original=True, space_id=space['id'])
    assert status == 202, 'Cannot seed protected retained original'
    records.append({'version':json.loads(body),'original_hash':hashlib.sha256(original).hexdigest()})
    for record in records:
        ready = source_state(scoped, record['version'], 'ready')
        status, body, _ = scoped.api('/api/v1/source-versions/' + ready['id'] + '/document')
        assert status == 200, 'Protected document is unavailable'
        record['document'] = json.loads(body)
        status, body, _ = scoped.api('/api/v1/documents/' + record['document']['id'] + '/chunks')
        assert status == 200, 'Protected chunks are unavailable'
        record['chunks'] = json.loads(body)['chunks']
        assert record['chunks'], 'Protected extraction produced no evidence'
        status, body, _ = scoped.api('/api/v1/chunks/' + record['chunks'][0]['id'] + '/citation')
        assert status == 200, 'Protected citation is unavailable'
        record['citation'] = json.loads(body)
    status, body, _ = scoped.api('/api/v1/objects', {'type_name':'fixture-inventory',
        'data':{'name':'persistent-record','count':17}}, 'POST', profile['csrf_token'])
    assert status == 201, 'Protected uniqueness was not isolated from Shared'
    record = json.loads(body)
    annotations = seed_content_annotations(scoped,profile,memory,records,record)
    consolidation = seed_atomic_consolidation(scoped,profile,space['id'],memory,records,record)
    return {'space':space,'grant':grant,'memory':memory,'sources':records,'object':record,
            'annotations':annotations,'consolidation':consolidation}


def seed_atomic_consolidation(browser,profile,space_id,memory,records,record):
    """Owned current-runtime data must survive configured update/clean restore."""
    root=browser.browser if isinstance(browser,ScopedBrowser) else browser
    def step(operation,**arguments):return {'operation':operation,'arguments':arguments}
    def ref(index,path='id'):return {'$result':index,'path':path}
    prior=memory['receipts'][-1]
    citation=records[-1]['citation']
    applicability={'knowledge_type':'procedure','status':'applicable','products':['C0'],
        'components':['native-atomic'],'version_tags':['0.29'],'confidence':None,
        'source_references':[{'kind':'chunk','id':citation['chunk_id']}]}
    request={'space_id':space_id,'idempotency_key':'native-atomic-consolidation','operations':[
        step('entity.create',kind='procedure',label='Native atomic procedure'),
        step('wiki.upsert',slug='native-atomic-memory',title='Native atomic procedure',body='Retained native atomic procedure'),
        step('object.create',type_name='fixture-inventory',data={'name':'native-atomic-record','count':29}),
        step('claim.create',entity_id=ref(0),page_id=ref(1),predicate='observed',value={'state':'unknown'},evidence_chunk_ids=[citation['chunk_id']]),
        step('entity.link',entity_id=ref(0),target_kind='object',target_id=ref(2)),
        step('annotation.update',target={'kind':'wiki_revision','id':ref(1,'content.id'),'revision':1},namespace='applicability',
            value={**applicability,'supersedes':[
                {'kind':'wiki_revision','id':prior['content']['id'],'revision':prior['revision']},
                {'kind':'object','id':record['id'],'revision':record['revision']}]},expected_revision=0),
        step('annotation.update',target={'kind':'wiki_revision','id':ref(1,'content.id'),'revision':1},namespace='verification',
            value={'status':'unverified','verified_at':None,'source_references':[{'kind':'chunk','id':citation['chunk_id']}]},expected_revision=0),
        step('annotation.update',target={'kind':'object','id':ref(2),'revision':1},namespace='applicability',value=applicability,expected_revision=0),
        step('annotation.update',target={'kind':'claim','id':ref(3),'revision':1},namespace='applicability',value=applicability,expected_revision=0)]}
    status,body,_=root.api('/api/v1/knowledge/bundles/apply',request,'POST',profile['csrf_token'])
    assert status==200,'Cannot seed atomic consolidation receipt'
    receipt=json.loads(body);assert len(receipt['results'])==9,'Atomic recovery step coverage missing'
    current=knowledge_request(browser,profile,'wiki/pages/upsert',{
        'slug':'native-atomic-memory','title':'Native atomic procedure','body':'Later native atomic observation','expected_revision':1},'POST')
    return {'request':request,'receipt':receipt,'current':current,'prior':prior,'citation':citation}


def verify_atomic_consolidation(browser,profile,expected,space_id,*,admin=False):
    scoped=ScopedBrowser(browser,space_id)
    rows=expected['receipt']['results']
    status,body,_=browser.api('/api/v1/knowledge/bundles/apply',expected['request'],'POST',profile['csrf_token'])
    if admin:
        assert status==200 and json.loads(body)==expected['receipt'],'Whole atomic retry receipt changed during recovery'
    else:
        assert status==403,'Reader space grant admitted atomic publication'
    status,body,_=scoped.api('/api/v1/wiki/pages/resolve?slug=native-atomic-memory')
    assert status==200 and json.loads(body)==expected['current'],'Atomic current Wiki revision changed during recovery'
    status,body,_=scoped.api('/api/v1/wiki/pages/'+rows[1]['id']+'?revision=1')
    assert status==200 and json.loads(body)['content']==rows[1]['content'],'Atomic original authored content changed'
    assert browser.api('/api/v1/wiki/pages/'+rows[1]['id'])[0]==404,'Atomic private UUID leaked into Shared'
    status,body,_=scoped.api('/api/v1/wiki/pages/'+expected['prior']['id']+'?revision='+str(expected['prior']['revision']))
    assert status==200 and json.loads(body)['content']==expected['prior']['content'],'Superseded prior content changed'
    status,body,_=scoped.api('/api/v1/claims/'+rows[3]['id'])
    claim=json.loads(body) if status==200 else {}
    assert status==200 and claim['value']=={'state':'unknown'},'Atomic assertion changed during recovery'
    assert claim['evidence'][0]['chunk_id']==expected['citation']['chunk_id'],'Atomic claim evidence changed during recovery'
    status,body,_=scoped.api('/api/v1/chunks/'+expected['citation']['chunk_id']+'/citation')
    assert status==200 and json.loads(body)==expected['citation'],'Atomic immutable citation changed during recovery'
    status,body,_=scoped.api('/api/v1/objects/'+rows[2]['id'])
    assert status==200 and json.loads(body)==rows[2],'Atomic structured record changed during recovery'
    for row in rows[5:]:
        target=row['target'];path='/api/v1/knowledge/annotations/'+target['kind']+'/'+target['id']+'/'+str(target['revision'])+'/'+row['namespace']
        status,body,_=scoped.api(path);actual=json.loads(body) if status==200 else {}
        assert status==200 and actual['revision']==row['revision'] and actual['value']==row['value'],'Atomic annotation value/history changed'
        status,body,_=scoped.api(path+'/history')
        assert status==200 and [revision['number'] for revision in json.loads(body)['revisions']]==[1],'Atomic annotation history changed'
        assert browser.api(path)[0]==404,'Atomic annotation UUID leaked into Shared'
    current=expected['current']
    path='/api/v1/knowledge/annotations/wiki_revision/'+current['content']['id']+'/'+str(current['revision'])+'/verification'
    status,body,_=scoped.api(path);unknown=json.loads(body) if status==200 else {}
    assert status==200 and unknown['revision']==0 and unknown['status']=='unknown' and unknown['value'] is None,'Recovered atomic verification transferred to changed content'
    print('Retained atomic bundle receipt, supersession, source references and unknown new revision passed')



def seed_content_annotations(browser, profile, memory, records, record):
    """Persist every target through native update, encrypted backup and restore."""
    entity=knowledge_request(browser,profile,'entities',{
        'kind':'procedure','label':'Native annotation resolver'},'POST',201)
    assertion=knowledge_request(browser,profile,'claims',{
        'entity_id':entity['id'],'predicate':'observed-error','value':{'message':'Native EPIPE observation'},
        'evidence_chunk_ids':[records[-1]['chunks'][0]['id']]},'POST',201)
    current=memory['receipts'][-1]; version=records[-1]['version']
    targets=[('wiki_revision',current['content']['id'],current['revision'],'wiki','observation'),
        ('source_version',version['id'],version['number'],'source','Retained'),
        ('entity',entity['id'],entity['revision'],'entity','resolver'),
        ('object',record['id'],record['revision'],'object','persistent'),
        ('claim',assertion['id'],assertion['revision'],'claim','EPIPE')]
    saved=[]
    for kind,identifier,revision,category,query in targets:
        path='/api/v1/knowledge/annotations/'+kind+'/'+identifier+'/'+str(revision)
        entries={}
        for namespace,value in (
                ('applicability',{'products':['C0'],'components':['native-recovery'],'version_tags':['0.28'],
                    'status':'applicable','observed_at':'2026-10-18T00:00:00Z'}),
                ('verification',{'status':'verified','confidence':.9,'verified_at':'2026-10-18T00:00:00Z'})):
            request={'value':value,'expected_revision':0,'idempotency_key':'native-'+uuid4().hex}
            status,body,_=browser.api(path+'/'+namespace,request,'PUT',profile['csrf_token'])
            assert status==200,'Cannot seed revisioned annotation'
            entries[namespace]={'request':request,'receipt':json.loads(body)}
            if namespace=='verification':
                original=entries[namespace]
                request={'value':{**value,'extensions':{'retained-observation':'second'}},
                    'expected_revision':1,'idempotency_key':'native-'+uuid4().hex}
                status,body,_=browser.api(path+'/'+namespace,request,'PUT',profile['csrf_token'])
                assert status==200,'Cannot seed a second annotation revision'
                entries[namespace]={'request':request,'receipt':json.loads(body),
                    'original_request':original['request'],'original_receipt':original['receipt']}
        saved.append({'path':path,'category':category,'query':query,'id':identifier,'entries':entries})
    return saved


def verify_content_annotations(browser, profile, expected, space_id, *, admin=False):
    assert len(expected)==5,'Retained annotation target coverage is incomplete'
    scoped=ScopedBrowser(browser,space_id)
    for item in expected:
        for namespace,entry in item['entries'].items():
            path=item['path']+'/'+namespace
            status,body,_=scoped.api(path)
            assert status==200 and json.loads(body)==entry['receipt'],'Annotation identity/revision changed during recovery'
            status,body,_=scoped.api(path+'/history')
            history=json.loads(body) if status==200 else {}
            assert status==200 and [row['number'] for row in history['revisions']]==list(range(entry['receipt']['revision'],0,-1)),'Annotation history changed during recovery'
            if 'original_receipt' in entry:
                assert history['revisions'][-1]['value']==entry['original_receipt']['value'],'Old annotation observation changed during recovery'
            assert browser.api(path)[0]==404,'Protected annotation UUID leaked into Shared'
            status,body,_=scoped.api(path,entry['request'],'PUT',profile['csrf_token'])
            if admin:
                assert status==200 and json.loads(body)==entry['receipt'],'Annotation retry changed its original snapshot'
                if 'original_request' in entry:
                    status,body,_=scoped.api(path,entry['original_request'],'PUT',profile['csrf_token'])
                    assert status==200 and json.loads(body)==entry['original_receipt'],'Old annotation retry was replaced by current state'
            else:
                assert status==403,'Reader grant admitted an annotation write'
        request={'query':item['query'],'space_id':space_id,'mode':'text','rerank':'off','filters':{
            'categories':[item['category']],'products':['C0'],'components':['native-recovery'],
            'version_tags':['0.28'],'verification_statuses':['verified']}}
        status,body,_=browser.api('/api/v1/knowledge/search/structured',request,'POST')
        result=json.loads(body) if status==200 else {}
        assert status==200 and result['candidate_count']==1,'Recovered exact filtered retrieval changed'
        assert result['hits'][0]['reference']['id']==item['id'],'Recovered typed reference changed'
        assert result['hits'][0]['verification']['revision']==item['entries']['verification']['receipt']['revision'],'Recovered verification revision changed'
        request['filters']['version_tags']=['0.2']
        status,body,_=browser.api('/api/v1/knowledge/search/structured',request,'POST')
        assert status==200 and json.loads(body)['hits']==[],'Recovered version filter matched a prefix'
    print('Retained applicability/verification histories and all five structured categories passed')

def verify_protected_space(browser, profile, expected, *, admin=False):
    identifier = expected['space']['id']
    scoped = ScopedBrowser(browser, identifier)
    verify_content_annotations(browser,profile,expected['annotations'],identifier,admin=admin)
    verify_atomic_consolidation(browser,profile,expected['consolidation'],identifier,admin=admin)
    status, body, _ = scoped.api('/api/v1/me')
    assert status == 200 and json.loads(body)['role'] == ('admin' if admin else 'reader'), 'Recovered space role changed'
    status, body, _ = browser.api('/api/v1/spaces')
    assert status == 200 and any(s['id'] == identifier for s in json.loads(body)['spaces']), 'Recovered space discovery missing'
    if admin:
        status, body, _ = browser.api('/api/v1/spaces/' + identifier + '/grants')
        assert status == 200 and json.loads(body)['grants'] == [expected['grant']], 'Recovered space grant/revision changed'
        verify_wiki_memory_receipts(scoped, profile, expected['memory'])
        verify_text_receipts(scoped, profile, expected['sources'])
    else:
        status, _, _ = scoped.api('/api/v1/wiki/pages/upsert', {**expected['memory']['requests'][0],
            'slug':'reader-must-not-create','idempotency_key':'reader-must-not-create'}, 'POST', profile['csrf_token'])
        assert status == 403, 'Application Editor bypassed its Reader space grant'
    for page in expected['memory']['receipts']:
        path = '/api/v1/wiki/pages/' + page['id'] + '?revision=' + str(page['revision'])
        status, body, _ = scoped.api(path)
        assert status == 200 and json.loads(body)['content'] == page['content'], 'Protected authored history changed'
        assert browser.api(path)[0] == 404, 'Private UUID leaked into Shared'
    for record in expected['sources']:
        source_state(scoped, record['version'], 'ready', seconds=15)
        for path, value in [('/api/v1/source-versions/' + record['version']['id'] + '/document', record['document']),
                            ('/api/v1/chunks/' + record['chunks'][0]['id'] + '/citation', record['citation'])]:
            status, body, _ = scoped.api(path)
            assert status == 200 and json.loads(body) == value, 'Protected evidence identity or provenance changed'
            assert browser.api(path)[0] == 404, 'Protected evidence UUID leaked into Shared'
        status, body, _ = scoped.api('/api/v1/documents/' + record['document']['id'] + '/chunks')
        assert status == 200 and json.loads(body)['chunks'] == record['chunks'], 'Protected immutable chunks changed'
        original_path='/api/v1/source-versions/' + record['version']['id'] + '/original'
        status, body, _ = scoped.api(original_path)
        if 'original_hash' in record:
            assert status == 200 and hashlib.sha256(body).hexdigest() == record['original_hash'], 'Retained protected original changed'
        else:
            assert status == 404, 'Unretained protected original became available'
        assert browser.api(original_path)[0] == 404, 'Protected original leaked into Shared'
    row = expected['object']
    status, body, _ = scoped.api('/api/v1/objects/' + row['id'])
    assert status == 200 and json.loads(body) == row, 'Protected structured record changed'
    assert browser.api('/api/v1/objects/' + row['id'])[0] == 404, 'Private object leaked into Shared'
    status, body, _ = scoped.api('/api/v1/knowledge/search?query=native&mode=text&rerank=off')
    assert status == 200 and json.loads(body)['hits'], 'Recovered protected evidence is not searchable'


def persistence(operation):
    payload = json.loads((STATE / "personas.json").read_text())
    origin = "https://" + payload["host"]
    owner = Browser(origin)
    profile = owner.login("c0owner", payload["password"])
    assert profile["role"] == "admin" and profile["is_owner"], "Recovered owner is not admitted"
    verify_profile(owner, profile)
    verify_capabilities(owner, 'admin')
    expected_file = STATE / "expected-identities.json"
    if operation == "seed":
        status, body, _ = owner.api("/api/v1/access/accounts")
        assert status == 200, "Cannot seed persisted membership"
        member = next(account for account in json.loads(body)["accounts"] if account["username"] == "c0member")
        status, _, _ = owner.api("/api/v1/access/accounts/" + member["id"],
                                {"role": "editor"}, "PUT", profile["csrf_token"])
        assert status == 204, "Cannot persist Editor grant"
        object_fixtures(owner,profile)
        records=[]
        for type_name in ("fixture-inventory","fixture-projects"):
            status,body,_=owner.api("/api/v1/objects",{"type_name":type_name,"data":{"name":"persistent-record","count":7},"tags":["persistent"]},"POST",profile["csrf_token"])
            assert status==201,"Cannot seed persisted object"
            records.append(json.loads(body))
        status,body,_=owner.api("/api/v1/object-relations",{"source_id":records[0]["id"],"target_id":records[1]["id"],"source_type":"fixture-inventory","target_type":"fixture-projects","kind":"used-by"},"POST",profile["csrf_token"])
        assert status==201,"Cannot seed persisted relation"
        relation_id = json.loads(body)['id']
        source_records = seed_sources(owner, profile)
        knowledge = seed_knowledge(owner, profile, source_records, records)
        clients = seed_oauth_clients(owner, profile)
        protected = seed_protected_space(owner, profile, member["id"])
        expected_file.write_text(json.dumps({"owner":profile["id"],"member":member["id"],"objects":records,"relation":relation_id,"sources":source_records,"knowledge":knowledge,"oauth_clients":clients,"protected":protected}))
        expected_file.chmod(0o600)
    expected = json.loads(expected_file.read_text())
    assert profile["id"] == expected["owner"], "Recovered owner identity changed"
    verify_oauth_clients(owner, expected['oauth_clients'])
    verify_text_receipts(owner, profile, expected['sources'])
    verify_wiki_memory_receipts(owner, profile, expected['knowledge']['memory'])
    verify_protected_space(owner, profile, expected['protected'], admin=True)
    editor = Browser(origin)
    member_profile = editor.login("c0member", payload["password"])
    assert member_profile["id"] == expected["member"] and member_profile["role"] == "editor", "Recovered membership changed"
    verify_profile(editor, member_profile)
    verify_capabilities(editor, 'editor')
    verify_protected_space(editor, member_profile, expected['protected'])
    for record in expected["objects"]:
        status,body,_=editor.api("/api/v1/objects/"+record["id"])
        assert status==200,"Recovered object missing"
        actual=json.loads(body)
        assert all(actual[key]==record[key] for key in ("id","type_name","data","tags","revision")),"Recovered object changed"
    status,body,_=editor.api("/api/v1/objects/"+expected["objects"][0]["id"]+"/relations")
    assert status==200 and any(r["id"]==expected["relation"] for r in json.loads(body)["relations"]),"Recovered relation missing"
    status,body,_=editor.api("/api/v1/object-events?limit=100")
    assert status==200 and all(any(e["object_id"]==record["id"] and e["operation"]=="create" for e in json.loads(body)["events"]) for record in expected["objects"]),"Recovered event history missing"
    verify_sources(editor, expected['sources'])
    verify_knowledge(editor, member_profile, expected['knowledge'])
    status, _, _ = editor.api("/api/v1/access/accounts")
    assert status == 403, "Recovered Editor can administer"
    owner.logout(profile)
    editor.logout(member_profile)


def browser_reader():
    payload=json.loads((STATE/"personas.json").read_text())
    owner=Browser("https://"+payload["host"]); profile=owner.login("c0owner",payload["password"])
    status,body,_=owner.api("/api/v1/access/accounts")
    assert status==200,"Cannot prepare browser membership"
    member=next(a for a in json.loads(body)["accounts"] if a["username"]=="c0member")
    status,_,_=owner.api("/api/v1/access/accounts/"+member["id"],{"role":"reader"},"PUT",profile["csrf_token"])
    assert status==204,"Cannot grant browser Reader"
    owner.logout(profile)


def performance():
    import os
    from performance_probe import measure
    payload = json.loads((STATE / 'personas.json').read_text())
    expected = json.loads((STATE / 'expected-identities.json').read_text())
    owner = Browser('https://' + payload['host'])
    profile = owner.login('c0owner', payload['password'])
    try:
        result = measure(owner, expected['knowledge']['page'])
        result['seed_source_versions'] = len(expected['sources'])
        result['runner'] = {'logical_cpus': os.cpu_count(),
                            'memory_bytes': os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')}
        print(json.dumps(result, sort_keys=True))
    finally:
        owner.logout(profile)


if __name__ == "__main__":
    try:
        if len(sys.argv)>1 and sys.argv[1]=="browser-reader":
            browser_reader()
        elif len(sys.argv)>1 and sys.argv[1]=='performance':
            performance()
        elif len(sys.argv) > 1:
            persistence(sys.argv[1])
        else:
            probe()
        print("Real SSO owner, membership, revocation and logout assertions passed")
    except Exception as error:
        # Assertions contain only fixed labels; never emit URL/body/cookies.
        print(str(error) if isinstance(error, AssertionError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
