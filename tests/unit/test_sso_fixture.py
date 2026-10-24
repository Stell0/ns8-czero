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


@pytest.fixture
def accessibility_measurement(monkeypatch):
    monkeypatch.setattr(BuiltIn, 'log_to_console', lambda self, *args: None)
    return lambda *args: {'controls_checked': 4, 'links_checked': 7,
        'unnamed_controls': 0, 'unnamed_links': 0, 'missing_language': 0,
        'missing_main': 0, 'missing_h1': 0, 'missing_navigation': 0, 'missing_skip_target': 0}


@pytest.mark.parametrize('existing', [False, True])
def test_sso_password_uploaded_privately_never_in_argv(monkeypatch, existing):
    commands, uploads, levels = [], [], []
    def upload(source, destination, **kwargs):
        if destination.endswith('payload.json'):
            uploads.append((Path(source).read_text(), kwargs, Path(source).stat().st_mode & 0o777))
    def execute(command, **kwargs):
        commands.append(command)
        if command == 'test -f /tmp/czero-oidc-fixture/resources.json':
            return '', 0 if existing else 1
        if ' setup ' in command or ' reuse ' in command:
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
    assert len(uploads) == (0 if existing else 1)
    assert sum(' setup ' in command for command in commands) == (0 if existing else 1)
    assert sum(' reuse ' in command for command in commands) == (1 if existing else 0)
    if not existing:
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
    library._cimd_persistence=lambda *args: calls.append('cimd')
    def wait(self, name, *args):
        assert name == 'Wait Until Keyword Succeeds'
        assert args == ('30s','2s','Check application route')
        calls.append('health')
        if not ready: raise AssertionError('application not ready')
    monkeypatch.setattr(BuiltIn, 'run_keyword', wait)
    if ready:
        library.verify_disposable_identity_persistence('czero7')
        assert calls == ['network','health','cimd','probe','retrieval','oauth']
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


def test_objects_browser_fills_credentials_without_robot_keyword_arguments(monkeypatch, accessibility_measurement):
    invocations=[]; filled=[]; commands=[]; secret='private-browser-fixture-value'
    selection_pending=[False]
    identities=iter(['00000000-0000-4000-8000-000000000001 · revision 3',
        '00000000-0000-4000-8000-000000000002 · revision 1'])
    def execute(command,**kwargs):
        commands.append(command)
        if command.startswith('cat '): return json.dumps({'password':secret})
        return '', '', 0
    ssh=SimpleNamespace(execute_command=execute)
    browser=SimpleNamespace(fill_text=lambda selector,value:filled.append((selector,value)),
        get_text=lambda selector:next(identities),
        evaluate_javascript=accessibility_measurement)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:ssh if name=='SSHLibrary' else browser)
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level:'INFO')
    def keyword(self,name,*args):
        invocations.append((name,args))
        if name=='Browser.Click' and args[0].startswith('#record-list button:text-is('):
            selection_pending[0]=True
        if name=='Browser.Get Text' and args==('#record-identity','==',
                '00000000-0000-4000-8000-000000000001 · revision 3'):
            selection_pending[0]=False
        if name=='Browser.Click' and args[0]=='#browse-relation-targets':
            assert not selection_pending[0], 'Relation browsing raced the selected detail reply'
    monkeypatch.setattr(BuiltIn,'run_keyword',keyword)
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    library.verify_disposable_objects_browser('czero7.test')
    assert filled.count(('input[name="password"]',secret))==2
    assert all(secret not in str(item) for item in invocations+commands)


def test_search_browser_keeps_credentials_out_of_robot_arguments(monkeypatch, accessibility_measurement):
    invocations=[]; filled=[]; commands=[]; secret='private-search-fixture-value'
    def execute(command, **kwargs):
        commands.append(command)
        return json.dumps({'password':secret}) if command.startswith('cat ') else ('', '', 0)
    ssh=SimpleNamespace(execute_command=execute)
    browser=SimpleNamespace(fill_text=lambda selector,value:filled.append((selector,value)),
        evaluate_javascript=accessibility_measurement)
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


def test_admin_browser_checks_real_controls_without_private_arguments(monkeypatch, accessibility_measurement):
    calls=[]
    browser=SimpleNamespace(get_text=lambda selector:json.dumps({'id':'00000000-0000-4000-8000-000000000001','state':'succeeded'}),
        evaluate_javascript=accessibility_measurement,get_url=lambda:'https://czero7.test/admin/work')
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    library._verify_admin_controls(browser,lambda name,*args:calls.append((name,args)),'admin','czero7.test')
    assert ('Select Options By',('#job-handler','value','health')) in calls
    assert ('Uncheck Checkbox',('#schedule-enabled',)) in calls
    assert ('Reload',()) in calls
    for role in ('reader','editor'):
        denied=[]
        library._verify_admin_controls(browser,lambda name,*args:denied.append((name,args)),role,'czero7.test')
        assert ('Wait For Elements State',('#access-workspace','hidden')) in denied
        assert all(name not in ('Click','Fill Text') for name,_ in denied)


def test_accessibility_diagnostics_contain_only_counts_and_fixed_context(monkeypatch, accessibility_measurement):
    messages = []
    monkeypatch.setattr(BuiltIn, 'log_to_console', lambda self, value: messages.append(value))
    check = runpy.run_path(str(ROOT / 'tests/CzeroSso.py'))['assert_accessibility']
    check(SimpleNamespace(evaluate_javascript=accessibility_measurement), 'home', 'admin')
    assert len(messages) == 1 and '"page": "home"' in messages[0]
    assert '"controls_checked": 4' in messages[0]


@pytest.mark.parametrize('changes', [
    {'controls_checked': 'private fixture value'}, {'private fixture key': 1}, {'unnamed_controls': 1},
])
def test_accessibility_rejects_private_or_failing_results(monkeypatch, accessibility_measurement, changes):
    messages = []
    monkeypatch.setattr(BuiltIn, 'log_to_console', lambda self, value: messages.append(value))
    check = runpy.run_path(str(ROOT / 'tests/CzeroSso.py'))['assert_accessibility']
    browser = SimpleNamespace(evaluate_javascript=lambda *args: {**accessibility_measurement(), **changes})
    with pytest.raises(AssertionError) as error:
        check(browser, 'sources', 'reader')
    assert 'private fixture' not in str(error.value) + ''.join(messages)


@pytest.mark.parametrize('fault', [None, 'host', 'provider', 'certificate'])
def test_existing_sso_fixture_requires_exact_host_provider_and_valid_tls(tmp_path, fault):
    reuse=runpy.run_path(str(ROOT/'tests/oidc_fixture.py'))['reuse']
    (tmp_path/'personas.json').write_text(json.dumps({'host':'changed-czero7.test','password':'private-fixture'}))
    (tmp_path/'resources.json').write_text(json.dumps({'idp':'idp7','provider':'stable-fixture-id'}))
    reuse.__globals__['STATE']=tmp_path
    before=(tmp_path/'personas.json').read_bytes();calls=[]
    def command(args):
        calls.append(args)
        if args[0]=='openssl':
            if fault=='certificate':raise RuntimeError('Expired certificate')
            return ''
        return 'another-provider' if fault=='provider' else 'stable-fixture-id'
    reuse.__globals__['command']=command
    if fault:
        with pytest.raises(RuntimeError):reuse('other.test' if fault=='host' else 'changed-czero7.test')
    else:
        assert reuse('changed-czero7.test')=={'domain':'users.czero.test','idp':'stable-fixture-id','owner':'c0owner'}
    assert (tmp_path/'personas.json').read_bytes()==before
    assert not any('add-module' in arg or 'setup' in arg for args in calls for arg in args)


@pytest.mark.parametrize('stage,expected_app,expected_core',[
    ('seed','0.51.0','0.32.0'),('verify','0.52.0','0.33.0')])
def test_predecessor_profile_wrapper_uses_supplied_health_version(monkeypatch,stage,expected_app,expected_core):
    calls,levels,network = [],[],[]
    def execute(command,**options):
        calls.append(command)
        return ('C0 predecessor background: '+json.dumps({'stage':stage,'verified':True}),'',0) if options.get('return_stderr') else ('',0)
    ssh = SimpleNamespace(execute_command=execute)
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda self,name:ssh)
    monkeypatch.setattr(BuiltIn,'set_log_level',lambda self,level: levels.append(level) or ('NONE' if level=='INFO' else 'INFO'))
    monkeypatch.setattr(BuiltIn,'log',lambda *args:None)
    monkeypatch.setattr(BuiltIn,'log_to_console',lambda *args:None)
    waits=[]
    monkeypatch.setattr(BuiltIn,'run_keyword',lambda self,*args: waits.append(args))
    library = runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    monkeypatch.setattr(library,'_network',lambda *args: network.append(args))
    library.predecessor_profile('czero7','czero7.test',stage,expected_app,expected_core)
    assert waits == [('Wait Until Keyword Succeeds','30s','2s','Check application route',expected_app,'czero7.test',expected_core)]
    assert network == ([(ssh,'czero7')] if stage=='verify' else [])
    admission = ' --reader-admission' if stage=='seed' else ''
    assert calls == ['python3 /tmp/profile_fixture.py '+stage+admission+' --background-module czero7','python3 /tmp/oidc_fixture.py check-logs czero7']
    assert levels == ['NONE','INFO','NONE','INFO']


@pytest.mark.parametrize('original', [False, True])
def test_people_browser_restores_discovery_after_browser_failure(monkeypatch, original):
    import shlex
    changed=[]
    def execute(command, **options):
        if '/get-configuration' in command:
            return json.dumps({'cimd_enabled':original}),0
        if '/configure-module' in command:
            args=shlex.split(command)
            changed.append(json.loads(args[args.index('--data')+1])['cimd_enabled'])
            return '',0
        assert command == 'python3 /tmp/access_fixture.py czero7 prepare'
        return 'C0 workspace access: '+json.dumps({'phase':'prepare','fresh_reader':True,'pending_request':True}),'',0
    monkeypatch.setattr(BuiltIn,'get_library_instance',lambda *args:SimpleNamespace(execute_command=execute))
    monkeypatch.setattr(BuiltIn,'log_to_console',lambda *args:None)
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    def fail_browser(*args):raise AssertionError('Forced browser stop')
    with pytest.raises(AssertionError,match='Forced browser stop'):
        library._verify_people_access(None,fail_browser,'czero7.test','czero7')
    assert changed == [True,original]


@pytest.mark.parametrize('after', ['https://c0.test/?space_id=selected#main-content',
    'https://c0.test/admin/spaces?space_id=other#main-content'])
def test_native_skip_guard_rejects_page_or_space_changes(after):
    urls=iter(['https://c0.test/admin/spaces?space_id=selected',after])
    library=runpy.run_path(str(ROOT/'tests/CzeroSso.py'))['CzeroSso']()
    with pytest.raises(AssertionError,match='Skip link changed page or selected space'):
        library._verify_skip_link(SimpleNamespace(get_url=lambda:next(urls)),lambda *args:None)
