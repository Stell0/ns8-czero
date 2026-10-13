# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

from robot.libraries.BuiltIn import BuiltIn

ROOT = Path(__file__).resolve().parents[2]


def test_sso_password_uploaded_privately_never_in_argv(monkeypatch):
    commands, uploads, levels = [], [], []
    def upload(source, destination, **kwargs):
        if destination.endswith('payload.json'):
            uploads.append((Path(source).read_text(), kwargs, Path(source).stat().st_mode & 0o777))
    def execute(command, **kwargs):
        commands.append(command)
        if ' setup ' in command:
            return json.dumps({'domain': 'users.czero.test', 'idp': 'fixture-id', 'owner': 'c0owner'}), '', 0
        if '/get-configuration' in command:
            return json.dumps({'host': 'czero7.test', 'lets_encrypt': False, 'user_domain': 'users.czero.test',
                               'idp': 'fixture-id', 'owner': 'c0owner'}), 0
        return '', 0
    ssh = SimpleNamespace(put_file=upload, execute_command=execute)
    monkeypatch.setattr(BuiltIn, 'get_library_instance', lambda self, name: ssh)
    def log_level(self, level):
        levels.append(level)
        return 'INFO'
    monkeypatch.setattr(BuiltIn, 'set_log_level', log_level)
    library = runpy.run_path(str(ROOT / 'tests/CzeroSso.py'))['CzeroSso']()
    library.provision_disposable_sso('czero7', 'czero7.test')
    assert len(uploads) == 1
    payload, options, mode = uploads[0]
    assert mode == 0o600 and options['mode'] == '0600'
    assert json.loads(payload)['password'] not in '\n'.join(commands)
    assert commands[-1] == 'rm -f /tmp/czero-sso-payload.json'
    assert levels == ['NONE', 'INFO']


def test_real_provider_form_decodes_html_action_and_preserves_hidden_fields():
    parser = runpy.run_path(str(ROOT / 'tests/oidc_probe.py'))['LoginForm']()
    parser.feed('<form id="kc-form-login" action="https://idp.czero.test/login?a=1&amp;b=2">'
                '<input type="hidden" name="credentialId" value=""></form>')
    assert parser.action == 'https://idp.czero.test/login?a=1&b=2'
    assert parser.fields == {'credentialId': ''}


def test_provider_logout_relative_action_uses_provider_origin():
    Browser = runpy.run_path(str(ROOT / 'tests/oidc_probe.py'))['Browser']
    browser = Browser.__new__(Browser)
    calls = []
    def api(path, *args):
        if path == '/auth/logout':
            return 200, json.dumps({'provider_logout': True,
                'logout_url': 'https://idp.czero.test/realms/test/logout'}).encode(), ''
        return 401, b'{}', ''
    def request(path, data=None, headers=None):
        calls.append(path)
        if len(calls) == 1:
            return 200, b'<form action="/realms/test/logout-confirm"><input type="hidden" name="session_code" value="fixture"></form>', path
        if len(calls) == 2:
            assert path == 'https://idp.czero.test/realms/test/logout-confirm'
            assert b'session_code=fixture' in data
            return 200, b'<html>Application</html>', 'https://czero7.test/'
        return 200, b'<form id="kc-form-login" action="/login"></form>', 'https://idp.czero.test/login'
    browser.api, browser.request = api, request
    browser.logout({'csrf_token': 'fixture'})
