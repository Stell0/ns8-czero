# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
import shutil
from types import SimpleNamespace
import pytest

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


def test_disposable_ca_is_owned_by_rootless_module_before_mount(monkeypatch, tmp_path):
    module = runpy.run_path(str(ROOT / 'tests/oidc_fixture.py'))
    network = module['apply_czero_network']
    state, install = tmp_path / 'state', tmp_path / 'install'
    state.mkdir()
    install.mkdir()
    (state / 'ca.pem').write_text('public-test-certificate')
    network.__globals__['STATE'] = state
    calls = []
    monkeypatch.setattr(shutil, 'chown', lambda path, **kw: calls.append((Path(path), kw)))
    def command(args):
        if 'AGENT_INSTALL_DIR' in args[-1]: return str(install)
        if 'ip_address' in args[-1]: return '10.5.4.1'
        if 'cat' in args: return (ROOT / 'imageroot/systemd/user' / args[-1]).read_text()
        return ''
    network.__globals__['command'] = command
    network('czero7')
    assert calls[0] == (install / 'czero-test-ca.pem', {'user': 'czero7', 'group': 'czero7'})
    assert (install / 'czero-test-ca.pem').stat().st_mode & 0o777 == 0o644
    assert not (install/'systemd/user/czero-pod.service.d').exists()
    assert '--add-host' not in (install/'systemd/user/czero.service.d/90-test-oidc.conf').read_text()


@pytest.mark.parametrize('output,rejected', [('GET /api/v1/me HTTP/1.1', False),
                                          ('GET /auth/callback?code=fixture&state=fixture HTTP/1.1', True)])
def test_disposable_log_assertion_checks_both_streams(output, rejected):
    check = runpy.run_path(str(ROOT / 'tests/oidc_fixture.py'))['check_private_logs']
    def command(args, *, merge_stderr):
        assert merge_stderr
        return output
    check.__globals__['command'] = command
    if rejected:
        with pytest.raises(RuntimeError, match='OAuth query values'):
            check('czero7')
    else:
        check('czero7')


@pytest.mark.parametrize('ready', [False, True])
def test_identity_probe_waits_for_health_after_native_restart(monkeypatch, ready):
    library = runpy.run_path(str(ROOT / 'tests/CzeroSso.py'))['CzeroSso']()
    calls=[]
    monkeypatch.setattr(BuiltIn, 'get_library_instance', lambda self, name: SimpleNamespace(
        execute_command=lambda *a, **kw: ('',0)))
    monkeypatch.setattr(BuiltIn, 'set_log_level', lambda self, level: 'INFO')
    library._network=lambda *args: calls.append('network')
    library._persistence=lambda *args: calls.append('probe')
    library._retrieval=lambda *args: calls.append('retrieval')
    library._oauth_persistence=lambda *args: calls.append('oauth')
    def wait(self, name, *args):
        assert name == 'Wait Until Keyword Succeeds'
        assert args == ('30s','2s','Check application route')
        calls.append('health')
        if not ready: raise AssertionError('application not ready')
    monkeypatch.setattr(BuiltIn, 'run_keyword', wait)
    if ready:
        library.verify_disposable_identity_persistence('czero7')
        assert calls == ['network','health','probe','retrieval','oauth']
    else:
        with pytest.raises(AssertionError, match='application not ready'):
            library.verify_disposable_identity_persistence('czero7')
        assert calls == ['network','health']


def test_identity_backup_reuses_existing_encryption_repository(monkeypatch):
    library = runpy.run_path(str(ROOT / 'tests/CzeroBackup.py'))['CzeroBackup']()
    commands=[]
    def execute(command, **kwargs):
        commands.append(command)
        assert 'add-backup-repository' not in command
        if 'api-cli run add-backup ' in command:
            import shlex
            request=json.loads(shlex.split(command)[-1])
            assert request['repository']=='existing-repository'
            assert request['instances']==['czero7']
            return '2',0
        return 'czero/stable-logical-uuid',0
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    result=library.create_disposable_backup('czero7','existing-repository')
    assert result=={'repository':'existing-repository','backup_id':2,'path':'czero/stable-logical-uuid'}
    assert len(commands)==2


def test_objects_browser_fills_credentials_without_robot_keyword_arguments(monkeypatch):
    invocations=[]; filled=[]; commands=[]; secret='private-browser-fixture-value'
    def execute(command,**kwargs):
        commands.append(command)
        if command.startswith('cat '): return json.dumps({'password':secret})
        return '', '', 0
    ssh=SimpleNamespace(execute_command=execute)
    browser=SimpleNamespace(fill_text=lambda selector,value:filled.append((selector,value)),
        get_text=lambda selector:'00000000-0000-4000-8000-000000000001 · revision 1')
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:ssh if name=='SSHLibrary' else browser)
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    monkeypatch.setattr(BuiltIn,'run_keyword',lambda self,name,*args:invocations.append((name,args)))
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    library.verify_disposable_objects_browser('czero7.test')
    assert filled.count(('input[name="password"]',secret))==2
    assert all(secret not in str(item) for item in invocations+commands)


def test_search_browser_keeps_credentials_out_of_robot_arguments(monkeypatch):
    invocations=[]; filled=[]; commands=[]; secret='private-search-fixture-value'
    def execute(command, **kwargs):
        commands.append(command)
        return json.dumps({'password':secret}) if command.startswith('cat ') else ('', '', 0)
    ssh=SimpleNamespace(execute_command=execute)
    browser=SimpleNamespace(fill_text=lambda selector,value:filled.append((selector,value)))
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:ssh if name=='SSHLibrary' else browser)
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    monkeypatch.setattr(BuiltIn,'run_keyword',lambda self,name,*args:invocations.append((name,args)))
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    library.verify_disposable_search_browser('czero7.test')
    assert filled.count(('input[name="password"]',secret))==2
    assert all(secret not in str(item) for item in invocations+commands)


def test_sso_dependency_installation_can_use_a_longer_bounded_deadline(monkeypatch):
    namespace=runpy.run_path(str(ROOT/'tests/oidc_fixture.py')); durations=[]
    def run(args,**kwargs):
        durations.append(kwargs['timeout'])
        return SimpleNamespace(returncode=0,stdout=b'installed')
    monkeypatch.setattr(namespace['subprocess'],'run',run)
    assert namespace['command'](['safe-fixture-command'])=='installed'
    assert namespace['command'](['add-module','fixture-image','1'],timeout=480)=='installed'
    assert durations==[180,480]


def test_account_switch_uses_provider_restart_and_keeps_password_private(monkeypatch):
    calls=[];filled=[];private='private-switch-fixture-value'
    def execute(command,**kwargs):
        if command.startswith('cat '): return json.dumps({'password':private})
        return '',0
    ssh=SimpleNamespace(execute_command=execute)
    browser=SimpleNamespace(fill_text=lambda selector,value:filled.append((selector,value)),
        get_element_count=lambda selector:1 if selector=='#reset-login' else 0)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:ssh if name=='SSHLibrary' else browser)
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    monkeypatch.setattr(BuiltIn,'run_keyword',lambda self,name,*args:calls.append((name,args)))
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    library.verify_disposable_account_switch_browser('czero7','czero7.test')
    assert ('Browser.Click',('#reset-login',)) in calls
    assert filled.count(('input[name="password"]',private))==2
    assert all(private not in str(call) for call in calls)
