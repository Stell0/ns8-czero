# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real authorization-code flow in disposable QEMU; no secrets in output."""
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
from pathlib import Path
import ssl
import sys
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
        expected_file.write_text(json.dumps({"owner":profile["id"],"member":member["id"],"objects":records,"relation":json.loads(body)["id"]}))
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
