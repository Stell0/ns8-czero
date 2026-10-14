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

    def upload(self, profile, content, *, filename, title, media_type, retain_original=False, source_id=None, expected_revision=None, metadata=None):
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
        return self.request('/api/v1/sources/upload', b''.join(parts), 'POST', {
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


def probe():
    payload = json.loads((STATE / "personas.json").read_text())
    origin = "https://" + payload["host"]
    owner = Browser(origin)
    profile = owner.login("c0owner", payload["password"])
    assert profile["role"] == "admin" and profile["is_owner"], "Owner identity mismatch"
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
    status, _, _ = reader.api("/api/v1/access/accounts")
    assert status == 403, "Reader can administer"
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
        assert status == 200 and json.loads(body)["role"] == role, "Session role is stale"
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
    assert status == 403, "Revoked session remains admitted"
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
    changes = knowledge_request(browser, profile, 'knowledge/changes?limit=100')['changes']
    return {'page': page, 'original': original, 'entities': entities, 'relations': relations,
            'claims': claims, 'references': references, 'changes': changes}


def verify_knowledge(browser, profile, expected):
    get = lambda path: knowledge_request(browser, profile, path)
    page = expected['page']; key = page['id']
    assert get('wiki/pages/' + key) == page, 'Recovered Wiki page changed'
    assert get('wiki/pages/' + key + '?revision=1')['content'] == expected['original'], 'Immutable Wiki revision changed'
    assert len(get('wiki/pages/' + key + '/revisions')['revisions']) == 2, 'Wiki revision history missing'
    status, body, _ = browser.api('/api/v1/wiki/pages/' + key + '/export?format=markdown&revision=1')
    assert status == 200 and body.decode() == expected['original']['body'], 'Markdown export changed'
    assert get('wiki/pages/' + key + '/export') == page, 'JSON export changed'
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


def persistence(operation):
    payload = json.loads((STATE / "personas.json").read_text())
    origin = "https://" + payload["host"]
    owner = Browser(origin)
    profile = owner.login("c0owner", payload["password"])
    assert profile["role"] == "admin" and profile["is_owner"], "Recovered owner is not admitted"
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
        expected_file.write_text(json.dumps({"owner":profile["id"],"member":member["id"],"objects":records,"relation":relation_id,"sources":source_records,"knowledge":knowledge}))
    expected = json.loads(expected_file.read_text())
    assert profile["id"] == expected["owner"], "Recovered owner identity changed"
    editor = Browser(origin)
    member_profile = editor.login("c0member", payload["password"])
    assert member_profile["id"] == expected["member"] and member_profile["role"] == "editor", "Recovered membership changed"
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


if __name__ == "__main__":
    try:
        if len(sys.argv)>1 and sys.argv[1]=="browser-reader":
            browser_reader()
        elif len(sys.argv) > 1:
            persistence(sys.argv[1])
        else:
            probe()
        print("Real SSO owner, membership, revocation and logout assertions passed")
    except Exception as error:
        # Assertions contain only fixed labels; never emit URL/body/cookies.
        print(str(error) if isinstance(error, AssertionError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
