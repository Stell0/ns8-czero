# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generated SSO credentials stay outside Robot variables and reports."""
import json
from pathlib import Path
import secrets
import shlex
import tempfile

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from browser_privacy import configure_browser_diagnostics, assert_no_oauth_queries
from renewal_evidence import validate_measurement
from offline_provider_probe import validate as validate_offline_provider
from persistent_fixture import validate as validate_persistent_connection
from persistent_fixture import validate_recovery as validate_persistent_recovery
from remembered_fixture import validate as validate_remembered_browser
from cimd_recovery_evidence import validate_measurement as validate_cimd_recovery
from workspace_access_evidence import validate_measurement as validate_workspace_access
from workspace_access_evidence import require_stages as require_workspace_access


def assert_accessibility(browser, page, role):
    fields = {'controls_checked', 'links_checked', 'unnamed_controls', 'unnamed_links',
              'missing_language', 'missing_main', 'missing_h1', 'missing_navigation', 'missing_skip_target'}
    result = browser.evaluate_javascript(None, Path(__file__).with_name('accessibility_probe.js').read_text())
    if (page not in {'home', 'account', 'records', 'sources', 'wiki', 'search', 'agents', 'admin', 'projects'}
            or role not in {'admin', 'reader', 'editor'} or not isinstance(result, dict)
            or set(result) != fields or any(type(v) is not int or not 0 <= v <= 10000 for v in result.values())):
        raise AssertionError('Accessibility smoke measurement invalid')
    # This remains safe with Robot's private-login log level NONE.
    BuiltIn().log_to_console('C0 accessibility: ' + json.dumps({'page': page, 'role': role, **result}, sort_keys=True))
    if result['links_checked'] == 0 or any(result[key] for key in fields if not key.endswith('_checked')):
        raise AssertionError('Accessibility names or landmarks failed')


class CzeroSso:
    @keyword
    def provision_disposable_sso(self, module_id, host):
        configure_browser_diagnostics()
        builtin = BuiltIn()
        ssh = builtin.get_library_instance("SSHLibrary")
        previous = builtin.set_log_level("NONE")
        try:
            for name in ("oidc_fixture.py", "oidc_probe.py", "retrieval_fixture.py", "oauth_fixture.py", "mcp_tls_probe.py", "performance_probe.py", "renewal_fixture.py", "profile_fixture.py", "current_content_fixture.py", "cimd_recovery_fixture.py", "offline_provider_probe.py", "persistent_fixture.py", "remembered_fixture.py", "access_fixture.py"):
                ssh.put_file(str(Path(__file__).with_name(name)), "/tmp/" + name)
            fixture_root = Path(__file__).parent / 'fixtures/evidence'
            for name in ('manifest.json', 'sample.txt', 'sample.md', 'sample.pdf', 'sample.docx'):
                ssh.put_file(str(fixture_root / name), '/tmp/czero-evidence-' + name, mode='0644')
            _, present = ssh.execute_command('test -f /tmp/czero-oidc-fixture/resources.json', return_rc=True)
            if present == 0:
                output, errors, rc = ssh.execute_command('python3 /tmp/oidc_fixture.py reuse ' + shlex.quote(host),
                    return_stderr=True, return_rc=True, timeout='180 seconds')
            elif present == 1:
                with tempfile.TemporaryDirectory(prefix="czero-sso-") as directory:
                    payload = Path(directory) / "payload.json"
                    payload.write_text(json.dumps({"password": "Test-Sso-" + secrets.token_urlsafe(32) + "9!", "host": host}))
                    payload.chmod(0o600)
                    ssh.put_file(str(payload), "/tmp/czero-sso-payload.json", mode="0600")
                output, errors, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py setup /tmp/czero-sso-payload.json",
                                                 return_stderr=True, return_rc=True, timeout="900 seconds")
            else:
                raise AssertionError('Cannot inspect disposable SSO fixture')
            if rc:
                safe = next((line for line in errors.splitlines() if line.startswith("Disposable SSO fixture failed:")), "")
                raise AssertionError(safe or "Disposable SSO provisioning failed")
            config = json.loads(output)
            request = {"host": host, "lets_encrypt": False, "user_domain": config["domain"],
                       "idp": config["idp"], "owner": config["owner"]}
            _, rc = ssh.execute_command("api-cli run module/" + shlex.quote(module_id) +
                "/configure-module --data " + shlex.quote(json.dumps(request)), return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Native Czero SSO configuration failed")
            output, rc = ssh.execute_command("api-cli run module/" + shlex.quote(module_id) +
                "/get-configuration", return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Cannot verify native SSO settings")
            persisted = json.loads(output)
            if any(persisted.get(key) != value for key, value in request.items()):
                raise AssertionError("Native SSO settings did not persist")
            code = ("import agent,os,pathlib; p=pathlib.Path(os.environ['AGENT_STATE_DIR']); "
                    "assert (p/'auth.env').stat().st_mode & 0o777 == 0o600; "
                    "assert 'CZERO_OIDC_CLIENT_SECRET' not in agent.read_envfile(str(p/'environment'))")
            _, rc = ssh.execute_command("runagent -m " + shlex.quote(module_id) +
                " python3 -c " + shlex.quote(code), return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Native SSO credentials are not private")
            self._network(ssh, module_id)
        finally:
            ssh.execute_command("rm -f /tmp/czero-sso-payload.json", return_stdout=False)
            builtin.set_log_level(previous)

    @keyword
    def predecessor_profile(self, module_id, host, stage, expected_app, expected_core):
        builtin = BuiltIn()
        previous = builtin.set_log_level('NONE')
        try:
            ssh = builtin.get_library_instance('SSHLibrary')
            if stage == 'verify':
                self._network(ssh, module_id)
            builtin.run_keyword('Wait Until Keyword Succeeds', '30s', '2s',
                'Check application route', expected_app, host, expected_core)
            predecessor = json.loads((Path(__file__).parent / 'fixtures/upgrade_predecessor.json').read_text())
            admission = ' --reader-admission' if stage == 'seed' and predecessor.get('reader_admission') is True else ''
            background = ' --background-module ' + shlex.quote(module_id) if predecessor.get('background_grant') is True else ''
            output, _, rc = ssh.execute_command('python3 /tmp/profile_fixture.py ' + shlex.quote(stage) + admission + background,
                return_stderr=True, return_rc=True, timeout='180 seconds')
            if rc:
                raise AssertionError('Genuine predecessor profile identity check failed')
            if background:
                lines = [line.removeprefix('C0 predecessor background: ') for line in output.splitlines() if line.startswith('C0 predecessor background: ')]
                expected = {'stage':stage, 'verified':True}
                if len(lines) != 1 or json.loads(lines[0]) != expected or type(json.loads(lines[0]).get('verified')) is not bool:
                    raise AssertionError('Genuine predecessor background evidence missing')
                hidden = builtin.set_log_level('INFO')
                try:
                    builtin.log('C0 predecessor background: ' + json.dumps(expected, sort_keys=True))
                    builtin.log_to_console('C0 predecessor background: ' + json.dumps(expected, sort_keys=True))
                finally:
                    builtin.set_log_level(hidden)
            _, rc = ssh.execute_command('python3 /tmp/oidc_fixture.py check-logs ' + shlex.quote(module_id),
                return_rc=True, timeout='180 seconds')
            if rc:
                raise AssertionError('Predecessor profile privacy check failed')
        finally:
            builtin.set_log_level(previous)

    @staticmethod
    def _network(ssh, module_id):
        _, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py network " + shlex.quote(module_id),
                                    return_rc=True, timeout="180 seconds")
        if rc:
            raise AssertionError("Disposable Czero SSO network fixture failed")

    @keyword
    def predecessor_content(self,stage):
        assert stage in ('seed','verify'),'Invalid disposable content stage'
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            ssh=builtin.get_library_instance('SSHLibrary')
            _,_,rc=ssh.execute_command('python3 /tmp/current_content_fixture.py '+stage,
                return_stderr=True,return_rc=True,timeout='360 seconds')
            assert rc==0,'Disposable predecessor content '+stage+' failed'
            proof='C0 predecessor content: '+json.dumps({'stage':stage,'verified':True},sort_keys=True)
            hidden=builtin.set_log_level('INFO')
            try:builtin.log(proof);builtin.log_to_console(proof)
            finally:builtin.set_log_level(hidden)
        finally:builtin.set_log_level(previous)

    @keyword
    def verify_disposable_sso(self, module_id):
        builtin = BuiltIn()
        previous = builtin.set_log_level("NONE")
        try:
            ssh = builtin.get_library_instance("SSHLibrary")
            output, errors, rc = ssh.execute_command("python3 /tmp/oidc_probe.py", return_stderr=True, return_rc=True, timeout="180 seconds")
            if rc:
                # Probe emits only fixed assertions or an exception class.
                raise AssertionError("Real IdP probe: " + errors.strip())
            lines = [line.removeprefix('C0 admission: ') for line in output.splitlines() if line.startswith('C0 admission: ')]
            try:
                proof = json.loads(lines[0]) if len(lines) == 1 else None
            except ValueError:
                raise AssertionError('Native default-admission evidence missing or invalid') from None
            if (not isinstance(proof, dict) or set(proof) != {'fresh_readers', 'blocked_signins', 'shared_only'}
                    or type(proof['fresh_readers']) is not int or not 0 <= proof['fresh_readers'] <= 3
                    or proof['blocked_signins'] != 3 or proof['shared_only'] is not True):
                raise AssertionError('Native default-admission evidence missing or invalid')
            hidden = builtin.set_log_level('INFO')
            try:
                builtin.log('C0 admission: ' + json.dumps(proof, sort_keys=True))
                builtin.log_to_console('C0 admission: ' + json.dumps(proof, sort_keys=True))
            finally:
                builtin.set_log_level(hidden)
            _, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py check-logs " + shlex.quote(module_id),
                                       return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Disposable access logs contain OAuth query values")
            _, errors, rc = ssh.execute_command("python3 /tmp/oauth_fixture.py " + shlex.quote(module_id),
                return_stderr=True, return_rc=True, timeout="300 seconds")
            if rc:
                raise AssertionError("Installed OAuth probe: " + errors.strip())
            if not getattr(self, '_renewal_probe_done', False):
                output, _, rc = ssh.execute_command('python3 /tmp/renewal_fixture.py ' + shlex.quote(module_id),
                    return_stderr=True, return_rc=True, timeout='660 seconds')
                if rc:
                    raise AssertionError('Installed renewable-session probe failed')
                try:
                    measurement = validate_measurement(json.loads(output))
                except (ValueError, TypeError):
                    raise AssertionError('Renewal acceptance measurement invalid') from None
                # Only this strictly validated public measurement is recorded.
                builtin.set_log_level('INFO')
                try:
                    builtin.log('C0 renewable session: ' + json.dumps(measurement, sort_keys=True), console=True)
                finally:
                    builtin.set_log_level('NONE')
                self._renewal_probe_done = True
            if not getattr(self, '_offline_provider_done', False):
                output, _, rc = ssh.execute_command('python3 /tmp/offline_provider_probe.py ' + shlex.quote(module_id),
                    return_stderr=True, return_rc=True, timeout='180 seconds')
                if rc:
                    raise AssertionError('Installed offline-provider probe failed')
                lines = output.splitlines()
                try:
                    proof = (validate_offline_provider(json.loads(lines[0].removeprefix('C0 offline provider: ')))
                             if len(lines) == 1 and lines[0].startswith('C0 offline provider: ') else None)
                except (ValueError, TypeError):
                    raise AssertionError('Offline provider evidence invalid') from None
                if proof is None:
                    raise AssertionError('Offline provider evidence missing')
                builtin.set_log_level('INFO')
                try:
                    builtin.log('C0 offline provider: ' + json.dumps(proof, sort_keys=True), console=True)
                finally:
                    builtin.set_log_level('NONE')
                self._offline_provider_done = True
            if not getattr(self, '_persistent_connection_done', False):
                output, _, rc = ssh.execute_command('python3 /tmp/persistent_fixture.py ' + shlex.quote(module_id),
                    return_stderr=True, return_rc=True, timeout='600 seconds')
                if rc:
                    raise AssertionError('Installed persistent-connection probe failed')
                lines = output.splitlines()
                try:
                    proof = (validate_persistent_connection(json.loads(lines[0].removeprefix('C0 persistent connection: ')))
                             if len(lines) == 1 and lines[0].startswith('C0 persistent connection: ') else None)
                except (ValueError, TypeError):
                    raise AssertionError('Persistent connection evidence invalid') from None
                if proof is None:
                    raise AssertionError('Persistent connection evidence missing')
                builtin.set_log_level('INFO')
                try:
                    builtin.log('C0 persistent connection: ' + json.dumps(proof, sort_keys=True), console=True)
                finally:
                    builtin.set_log_level('NONE')
                self._persistent_connection_done = True
            _, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py check-logs " + shlex.quote(module_id),
                return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Installed OAuth access logs contain private query values")
        finally:
            builtin.set_log_level(previous)

    @keyword
    def prepare_disposable_identity_persistence(self):
        self._persistence("seed")

    @keyword
    def verify_disposable_identity_persistence(self, module_id):
        builtin = BuiltIn()
        previous = builtin.set_log_level("NONE")
        try:
            self._network(builtin.get_library_instance("SSHLibrary"), module_id)
            # Native update/systemd completion precedes ASGI readiness.
            builtin.run_keyword("Wait Until Keyword Succeeds", "30s", "2s", "Check application route")
            self._cimd_persistence(module_id, "verify")
            self._persistence("verify")
            self._retrieval(module_id, "verify")
            self._oauth_persistence(module_id, "verify")
            self._remembered_persistence(module_id, "verify")
            ssh = builtin.get_library_instance("SSHLibrary")
            _, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py check-logs " + shlex.quote(module_id),
                                       return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Persisted identity access logs contain OAuth query values")
        finally:
            builtin.set_log_level(previous)

    @staticmethod
    def _persistence(operation):
        builtin = BuiltIn()
        previous = builtin.set_log_level("NONE")
        try:
            ssh = builtin.get_library_instance("SSHLibrary")
            _, errors, rc = ssh.execute_command("python3 /tmp/oidc_probe.py " + operation,
                                               return_stderr=True, return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Real IdP persistence probe: " + errors.strip())
        finally:
            builtin.set_log_level(previous)

    @keyword
    def prepare_disposable_retrieval_persistence(self, module_id):
        self._retrieval(module_id, "prepare")
        BuiltIn().run_keyword("Wait Until Keyword Succeeds", "30s", "2s", "Check application route")
        self._retrieval(module_id, "seed")
        self._cimd_persistence(module_id, "seed")
        self._oauth_persistence(module_id, "seed")
        self._remembered_persistence(module_id, "seed")

    @staticmethod
    def _cimd_persistence(module_id, operation):
        builtin = BuiltIn(); previous = builtin.set_log_level('NONE')
        try:
            ssh = builtin.get_library_instance('SSHLibrary')
            output, _, rc = ssh.execute_command('python3 /tmp/cimd_recovery_fixture.py ' + shlex.quote(module_id) +
                ' ' + shlex.quote(operation), return_stderr=True, return_rc=True, timeout='300 seconds')
            if rc:
                raise AssertionError('Disposable Core-seeded CIMD recovery failed')
            prefix = 'C0 CIMD recovery: '
            lines = [line for line in output.splitlines() if line.startswith(prefix)]
            if len(lines) != 1:
                raise AssertionError('Disposable CIMD recovery proof missing')
            proof = validate_cimd_recovery(json.loads(lines[0][len(prefix):]))
            if operation == 'seed':
                prefix_onboarding = 'C0 onboarding: '
                lines_onboarding = [line for line in output.splitlines() if line.startswith(prefix_onboarding)]
                expected = {'core_seeded_approval': True, 'network_fetch_tested': False,
                    'unknown_client_handoff': True, 'explicit_consent': True, 'replay_rejected': True}
                if len(lines_onboarding) != 1 or json.loads(lines_onboarding[0][len(prefix_onboarding):]) != expected:
                    raise AssertionError('Native first-connection evidence missing or invalid')
                hidden = builtin.set_log_level('INFO')
                try:
                    builtin.log(prefix_onboarding + json.dumps(expected, sort_keys=True))
                    builtin.log_to_console(prefix_onboarding + json.dumps(expected, sort_keys=True))
                finally:
                    builtin.set_log_level(hidden)
            sanitized = prefix + json.dumps(proof, sort_keys=True)
            # Parent recovery methods intentionally hide private command output.
            # Raise logging only around the validated public measurement.
            hidden = builtin.set_log_level('INFO')
            try:
                builtin.log(sanitized)
                builtin.log_to_console(sanitized)
            finally:
                builtin.set_log_level(hidden)
        finally:
            builtin.set_log_level(previous)

    @staticmethod
    def _oauth_persistence(module_id, operation):
        builtin = BuiltIn(); previous = builtin.set_log_level('NONE')
        try:
            ssh = builtin.get_library_instance('SSHLibrary')
            _, errors, rc = ssh.execute_command('python3 /tmp/oauth_fixture.py ' + shlex.quote(module_id) +
                ' ' + operation, return_stderr=True, return_rc=True, timeout='300 seconds')
            if rc:
                raise AssertionError('Disposable OAuth recovery: ' + errors.strip())
            output, _, rc = ssh.execute_command('python3 /tmp/persistent_fixture.py ' + shlex.quote(module_id) +
                ' ' + shlex.quote(operation), return_stderr=True, return_rc=True, timeout='300 seconds')
            if rc:
                raise AssertionError('Disposable persistent recovery failed')
            lines=output.splitlines();prefix='C0 persistent recovery: '
            try:
                proof=(validate_persistent_recovery(json.loads(lines[0][len(prefix):]))
                       if len(lines)==1 and lines[0].startswith(prefix) else None)
            except (ValueError,TypeError):
                raise AssertionError('Persistent recovery evidence invalid') from None
            if proof is None:raise AssertionError('Persistent recovery evidence missing')
            builtin.set_log_level('INFO')
            try:
                sanitized=prefix+json.dumps(proof,sort_keys=True)
                builtin.log(sanitized);builtin.log_to_console(sanitized)
            finally:builtin.set_log_level('NONE')
        finally:
            builtin.set_log_level(previous)

    @staticmethod
    def _remembered_persistence(module_id, operation):
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            ssh=builtin.get_library_instance('SSHLibrary')
            output,_,rc=ssh.execute_command('python3 /tmp/remembered_fixture.py '+shlex.quote(module_id)+' '+shlex.quote(operation),
                return_stderr=True,return_rc=True,timeout='180 seconds')
            if rc:raise AssertionError('Disposable remembered browser recovery failed')
            prefix='C0 remembered browser: ';lines=output.splitlines()
            if len(lines)!=1 or not lines[0].startswith(prefix):raise AssertionError('Remembered browser evidence missing')
            proof=validate_remembered_browser(json.loads(lines[0][len(prefix):]))
            builtin.set_log_level('INFO')
            try:
                sanitized=prefix+json.dumps(proof,sort_keys=True)
                builtin.log(sanitized);builtin.log_to_console(sanitized)
            finally:builtin.set_log_level('NONE')
        finally:builtin.set_log_level(previous)

    @staticmethod
    def _retrieval(module_id, operation):
        builtin = BuiltIn()
        previous = builtin.set_log_level("NONE")
        try:
            ssh = builtin.get_library_instance("SSHLibrary")
            _, errors, rc = ssh.execute_command("python3 /tmp/retrieval_fixture.py " + operation + " " + shlex.quote(module_id),
                                               return_stderr=True, return_rc=True, timeout="300 seconds" if operation == 'seed' else "180 seconds")
            if rc:
                raise AssertionError("Disposable retrieval: " + errors.strip())
        finally:
            builtin.set_log_level(previous)

    @keyword
    def cleanup_disposable_sso(self):
        builtin = BuiltIn()
        previous = builtin.set_log_level("NONE")
        try:
            ssh = builtin.get_library_instance("SSHLibrary")
            _, rc = ssh.execute_command("test ! -f /tmp/oidc_fixture.py || python3 /tmp/oidc_fixture.py cleanup",
                                       return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Disposable SSO cleanup failed")
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_account_switch_browser(self, module_id, host):
        builtin=BuiltIn(); previous=builtin.set_log_level('NONE')
        try:
            ssh=builtin.get_library_instance('SSHLibrary'); browser=builtin.get_library_instance('Browser')
            payload=json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/personas.json'))
            self._browser_password=payload['password']
            def run(name,*args): return builtin.run_keyword('Browser.'+name,*args)
            run('Go To','https://'+host+'/auth/login')
            run('Wait For Elements State','input[name="username"]','visible','timeout=30s')
            browser.fill_text('input[name="username"]','c0denied')
            browser.fill_text('input[name="password"]',self._browser_password)
            run('Click','#kc-login')
            run('Get Text','h1','==','Access denied')
            run('Get Attribute','a','href','==','/auth/login?switch_account=true')
            run('Click','a')
            # Keycloak reauthentication can retain the selected username.
            # Its own restart control permits choosing another account.
            run('Wait For Elements State','input[name="password"]','visible','timeout=30s')
            if browser.get_element_count('#reset-login'):
                run('Click','#reset-login')
            run('Wait For Elements State','input[name="username"]','visible','timeout=30s')
            browser.fill_text('input[name="username"]','c0owner')
            browser.fill_text('input[name="password"]',self._browser_password)
            run('Click','#kc-login')
            run('Wait For Elements State','#sign-out','visible','timeout=30s')
            run('Get Text','#account-status','contains','Owner (Admin)')
            _, rc=ssh.execute_command('python3 /tmp/oidc_fixture.py check-logs '+shlex.quote(module_id),
                return_rc=True,timeout='180 seconds')
            if rc: raise AssertionError('Account-switch logs contain OAuth query values')
        except Exception as error:
            raise AssertionError('Disposable account-switch browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_objects_browser(self, host):
        """Generated password is never a Robot variable or nested keyword arg."""
        builtin=BuiltIn(); previous=builtin.set_log_level('NONE')
        try:
            ssh=builtin.get_library_instance('SSHLibrary')
            raw=ssh.execute_command('cat /tmp/czero-oidc-fixture/personas.json')
            payload=json.loads(raw); self._browser_password=payload['password']
            browser=builtin.get_library_instance('Browser')
            def run(name,*args): return builtin.run_keyword('Browser.'+name,*args)
            def login(username):
                run('Go To','https://'+host+'/objects')
                run('Wait For Elements State','#records-signin','visible','timeout=30s')
                run('Click','#records-signin')
                run('Get Property','input[name="remember"]','checked','==',False)
                if username == 'c0owner':run('Check Checkbox','input[name="remember"]')
                run('Click','#website-sign-in button[type="submit"]')
                browser.fill_text('input[name="username"]',username)
                browser.fill_text('input[name="password"]',self._browser_password)
                run('Click','#kc-login')
                run('Wait For Elements State','#sign-out, [name="accept"]','visible','timeout=30s')
                if browser.get_element_count('[name="accept"]'):run('Click','[name="accept"]')
                # OIDC callback returns to the home page.
                run('Wait For Elements State','#sign-out','visible','timeout=30s')
                if username == 'c0owner':run('Get Text','#account-status','contains','Remembered on this device')
                run('Go To','https://'+host+'/objects')
                run('Wait For Elements State','#records-workspace','visible','timeout=30s')
                assert_accessibility(browser, 'records', 'admin' if username == 'c0owner' else 'reader')
            login('c0owner')
            type_name='browser-inventory-'+secrets.token_hex(4)
            run('Click','#type-registration summary')
            run('Fill Text','#type-name',type_name)
            run('Fill Text','#type-label','Browser inventory')
            run('Fill Text','#type-schema',json.dumps({'type':'object','properties':{
                'name':{'type':'string','maxLength':64},'count':{'type':'integer','minimum':0}},'required':['name','count']}))
            run('Fill Text','#type-unique','name')
            run('Click','#type-form button')
            run('Get Text','#type-status','==','Type registered.')
            run('Click','#new-record')
            run('Get Element Count','#record-fields fieldset','==',2)
            run('Get Property','label:text-is("name (required)") + input','required','==',True)
            run('Fill Text','label:text-is("name (required)") + input','Field control draft')
            run('Fill Text','label:text-is("count (required)") + input','2')
            run('Get Property','#record-data','value','contains','Field control draft')
            run('Click','#record-json summary')
            run('Fill Text','#record-data','{"name":3,"count":2}')
            run('Click','#save-record')
            run('Get Text','#record-status','contains','Validation failed')
            run('Fill Text','#record-data','{"name":"Browser rack","count":2}')
            run('Fill Text','#record-tags','inventory, priority')
            run('Click','#save-record')
            run('Get Text','#record-status','==','Record saved.')
            run('Reload')
            run('Select Options By','#record-type','value',type_name)
            run('Click','#record-list button')
            run('Get Property','#record-data','value','contains','"count": 2')
            run('Click','#record-json summary')
            run('Fill Text','#record-data','{"name":"Browser rack revised","count":3}')
            run('Click','#save-record')
            run('Get Text','#record-status','==','Record saved.')
            run('Get Text','#record-identity','contains','revision 2')
            run('Reload')
            run('Select Options By','#record-type','value',type_name)
            run('Click','#record-list button')
            run('Get Property','#record-data','value','contains','"count": 3')
            hostile='<img src=x onerror=alert(1)>'
            run('Click','#record-json summary')
            run('Fill Text','#record-data',json.dumps({'name':hostile,'count':3}))
            run('Click','#save-record')
            run('Get Text','#record-status','==','Record saved.')
            run('Get Text','#record-list button','==',hostile)
            run('Get Element Count','#record-list img','==',0)
            source_identity=browser.get_text('#record-identity')
            run('Click','#new-record')
            run('Fill Text','label:text-is("name (required)") + input','Browser linked target')
            run('Fill Text','label:text-is("count (required)") + input','4')
            run('Click','#save-record');run('Get Text','#record-status','==','Record saved.')
            target_id=browser.get_text('#record-identity').split(' · ')[0]
            assert target_id != source_identity.split(' · ')[0], 'Linked fixture records must differ'
            run('Click','#record-list button:text-is('+json.dumps(hostile)+')')
            # A click starts an asynchronous detail read; its completion clears
            # target browsing. Wait for the selected identity before browsing.
            run('Get Text','#record-identity','==',source_identity)
            run('Select Options By','#relation-type','value',type_name)
            run('Click','#browse-relation-targets')
            run('Get Text','#relation-targets-status','contains','target records shown')
            run('Select Options By','#relation-picker','value',target_id)
            run('Get Property','#relation-target','value','==',target_id)
            run('Click','#relation-form button[type=submit]')
            run('Get Text','#record-status','==','Relation saved.')
            run('Get Text','#record-relations','contains','related-to')
            assert_accessibility(browser, 'records', 'admin')
            # Change membership through real owner-authenticated HTTP on the VM.
            _,errors,rc=ssh.execute_command('python3 /tmp/oidc_probe.py browser-reader',return_stderr=True,return_rc=True,timeout='180 seconds')
            if rc: raise AssertionError('Cannot prepare disposable Reader browser')
            run('New Context','ignoreHTTPSErrors=True')
            run('New Page')
            login('c0member')
            run('Select Options By','#record-type','value',type_name)
            run('Wait For Elements State','#new-record','hidden')
            run('Wait For Elements State','#type-registration','hidden')
            run('Click','#record-list button:text-is('+json.dumps(hostile)+')')
            run('Get Property','#record-data','readOnly','==',True)
            run('Get Element Count','#record-fields input:not(:disabled), #record-fields select:not(:disabled), #record-fields textarea:not(:disabled)','==',0)
            run('Wait For Elements State','#save-record','hidden')
            run('Get Property','#record-data','value','contains','"count": 3')
        except Exception as error:
            raise AssertionError('Disposable object browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_sources_browser(self, host):
        """Real owner/Reader workflows; only synthetic files enter the reports."""
        builtin = BuiltIn(); previous = builtin.set_log_level('NONE')
        try:
            ssh = builtin.get_library_instance('SSHLibrary')
            payload = json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/personas.json'))
            self._browser_password = payload['password']
            browser = builtin.get_library_instance('Browser')
            def run(name, *args): return builtin.run_keyword('Browser.' + name, *args)
            def login(username):
                run('Go To', 'https://' + host + '/sources?view=tools')
                run('Wait For Elements State', '#sources-signin', 'visible', 'timeout=30s')
                run('Click', '#sources-signin')
                run('Click', '#website-sign-in button[type="submit"]')
                browser.fill_text('input[name="username"]', username)
                browser.fill_text('input[name="password"]', self._browser_password)
                run('Click', '#kc-login')
                run('Wait For Elements State', '#sign-out', 'visible', 'timeout=30s')
                run('Go To', 'https://' + host + '/sources?view=tools')
                run('Wait For Elements State', '#sources-workspace', 'visible', 'timeout=30s')
                assert_accessibility(browser, 'sources', 'admin' if username == 'c0owner' else 'reader')
            def view(number, expected):
                selector = '#source-versions button:text-is("View version ' + str(number) + '")'
                run('Wait For Elements State', selector, 'visible', 'timeout=100s')
                run('Click', selector)
                run('Get Text', '#document-text', 'contains', expected)
            login('c0owner')
            title = '<img src=x onerror=alert(1)> browser-source-' + secrets.token_hex(4)
            sample = Path(__file__).parent / 'fixtures/evidence/sample.txt'
            expected_text = sample.read_text()
            run('Click', '#source-upload > summary')
            run('Fill Text', '#upload-title', title)
            run('Upload File By Selector', '#upload-file', str(sample))
            run('Click', '#upload-form details summary')
            run('Fill Text', '#upload-metadata', '{')
            run('Click', '#upload-submit')
            run('Get Text', '#upload-status', '==', 'Metadata must be valid JSON.')
            run('Fill Text', '#upload-metadata', '{"fixture":"browser"}')
            run('Check Checkbox', '#upload-retain')
            run('Click', '#upload-submit')
            run('Get Text', '#upload-status', 'contains', 'Upload accepted.')
            view(1, expected_text)
            run('Get Text', '#source-heading', '==', title)
            run('Get Element Count', '#source-detail img', '==', 0)
            run('Get Text', '#source-versions', 'contains', 'original retained')
            source_id = browser.get_text('#source-identity').split(' · ')[0]
            run('Click', '#source-chunks button')
            run('Get Text', '#source-citation', 'contains', '"source_hash"')
            run('Reload')
            run('Click', '#source-list button:text-is(' + json.dumps(title) + ')')
            view(1, expected_text)
            run('Click', '#source-upload > summary')
            run('Select Options By', '#upload-source', 'value', source_id)
            run('Check Checkbox', '#upload-retain')
            run('Upload File By Selector', '#upload-file', str(sample))
            run('Click', '#upload-submit')
            run('Get Text', '#upload-status', 'contains', 'Upload accepted.')
            run('Get Element Count', '#source-versions li', '==', 1)
            with tempfile.TemporaryDirectory(prefix='czero-source-browser-') as directory:
                revised = Path(directory) / 'revised.txt'
                revised.write_text(expected_text + '\nBrowser revised evidence')
                run('Upload File By Selector', '#upload-file', str(revised))
                run('Click', '#upload-submit')
                run('Get Text', '#upload-status', 'contains', 'Upload accepted.')
                view(2, 'Browser revised evidence')
                run('Get Text', '#source-identity', 'contains', 'revision 2')
                run('Get Element Count', '#source-versions li', '==', 2)
                view(1, expected_text)
                run('Fill Text', '#source-query', 'inventory')
                run('Click', '#source-search-form button')
                run('Wait For Elements State', '#source-results button:text-is(' + json.dumps(title + ' · version 2') + ')', 'visible')
                run('Click', '#source-results button:text-is(' + json.dumps(title + ' · version 2') + ')')
                run('Get Text', '#document-text', 'contains', 'Browser revised evidence')
                invalid = Path(directory) / 'invalid.txt'; invalid.write_bytes(b'\xff')
                run('Select Options By', '#upload-source', 'value', '')
                run('Fill Text', '#upload-title', 'Browser quarantined evidence')
                run('Upload File By Selector', '#upload-file', str(invalid))
                run('Uncheck Checkbox', '#upload-retain')
                run('Click', '#upload-submit')
                run('Get Text', '#upload-status', 'contains', 'Upload accepted.')
                retry = '#source-versions button:text-is("Retry version 1")'
                run('Wait For Elements State', retry, 'visible', 'timeout=100s')
                run('Get Text', '#source-versions', 'contains', 'Invalid UTF-8 text.')
                run('Get Element Count', '#source-versions a', '==', 1)
                run('Click', retry)
                run('Get Text', '#source-status', 'contains', 'Extraction queued.')
                run('Wait For Elements State', retry, 'visible', 'timeout=100s')
            _, errors, rc = ssh.execute_command('python3 /tmp/oidc_probe.py browser-reader', return_stderr=True, return_rc=True, timeout='180 seconds')
            if rc: raise AssertionError('Cannot prepare source Reader browser')
            run('New Context', 'ignoreHTTPSErrors=True'); run('New Page'); login('c0member')
            run('Wait For Elements State', '#source-upload', 'hidden')
            run('Click', '#source-list button:text-is(' + json.dumps(title) + ')')
            run('Wait For Elements State', '#archive-source', 'hidden')
            view(2, 'Browser revised evidence')
            run('Click', '#source-chunks button')
            run('Get Text', '#source-citation', 'contains', '"chunk_id"')
            citation = json.loads(browser.get_text('#source-citation'))
            run('Go To', 'https://' + host + '/sources?source=' + citation['source_id'] + '&version=' + citation['version_id'] + '&chunk=' + citation['chunk_id'])
            run('Get Text', '#reader-document', 'contains', 'Browser revised evidence')
            run('Get Text', '#reader-excerpt', 'contains', citation['body'])
            run('Wait For Elements State', '#sources-workspace', 'hidden')
            assert_accessibility(browser, 'sources', 'reader')
            run('Go To', 'https://' + host + '/sources?view=tools')
            run('Click', '#source-list button:text-is("Browser quarantined evidence")')
            run('Wait For Elements State', '#source-detail', 'visible')
            run('Get Element Count', '#source-versions button', '==', 0)
            run('Get Element Count', '#source-versions a', '==', 1)
            run('New Context', 'ignoreHTTPSErrors=True'); run('New Page'); login('c0owner')
            run('Click', '#source-list button:text-is(' + json.dumps(title) + ')')
            view(2, 'Browser revised evidence')
            run('Click', '#archive-source')
            run('Get Text', '#source-identity', 'contains', 'archived')
            run('Get Element Count', '#source-list button:text-is(' + json.dumps(title) + ')', '==', 0)
            view(2, 'Browser revised evidence')
            run('Click', '#source-chunks button')
            run('Get Text', '#source-citation', 'contains', '"deleted": true')
            run('Fill Text', '#source-query', '"Browser revised evidence"')
            run('Click', '#source-search-form button')
            run('Get Text', '#search-status', '==', '0 sourced text matches (up to 20).')
        except Exception as error:
            raise AssertionError('Disposable source browser failed (' + type(error).__name__ + ')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_wiki_browser(self, host):
        """Exercise actual authored pages and restored provenance through SSO."""
        builtin = BuiltIn(); previous = builtin.set_log_level('NONE')
        try:
            ssh = builtin.get_library_instance('SSHLibrary')
            payload = json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/personas.json'))
            expected = json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/expected-identities.json'))['knowledge']
            self._browser_password = payload['password']
            browser = builtin.get_library_instance('Browser')
            def run(name, *args): return builtin.run_keyword('Browser.' + name, *args)
            def login(username):
                run('Go To', 'https://' + host + '/wiki?view=tools')
                run('Wait For Elements State', '#wiki-signin', 'visible', 'timeout=30s')
                run('Click', '#wiki-signin')
                run('Click', '#website-sign-in button[type="submit"]')
                browser.fill_text('input[name="username"]', username)
                browser.fill_text('input[name="password"]', self._browser_password)
                run('Click', '#kc-login')
                run('Wait For Elements State', '#sign-out', 'visible', 'timeout=30s')
                run('Go To', 'https://' + host + '/wiki?view=tools')
                run('Wait For Elements State', '#wiki-workspace', 'visible', 'timeout=30s')
                assert_accessibility(browser, 'wiki', 'admin' if username == 'c0owner' else 'reader')
            login('c0owner')
            run('Click', '#new-page')
            slug = 'browser-wiki/article-' + secrets.token_hex(4)
            title = '<img src=x onerror=alert(1)> ' + slug
            run('Fill Text', '#wiki-slug', slug)
            run('Fill Text', '#wiki-title', title)
            run('Fill Text', '#wiki-body', '# Authored browser content')
            run('Click', '#wiki-form details summary')
            run('Fill Text', '#wiki-metadata', '{')
            run('Click', '#save-page')
            run('Get Text', '#page-status', '==', 'Metadata must be valid JSON.')
            run('Fill Text', '#wiki-metadata', '{"fixture":"browser"}')
            run('Click', '#save-page')
            run('Get Text', '#page-status', '==', 'Page saved.')
            run('Get Text', '#wiki-heading', '==', title)
            run('Get Element Count', '#wiki-detail img', '==', 0)
            run('Fill Text', '#wiki-body', '# Revised browser content')
            run('Click', '#save-page')
            run('Get Text', '#wiki-identity', 'contains', 'revision 2')
            run('Get Element Count', '#wiki-history', '==', 0)
            run('Get Property', '#wiki-body', 'value', '==', '# Revised browser content')
            run('Reload')
            run('Click', '#wiki-pages button:text-is(' + json.dumps(title) + ')')
            run('Get Property', '#wiki-body', 'value', '==', '# Revised browser content')
            root = expected['entities'][0]['id']
            run('Select Options By', '#knowledge-entity', 'value', root)
            run('Get Element Count', '#knowledge-claims li', '==', 2)
            run('Click', '#knowledge-claims button:text-is(' + json.dumps('Evidence for claim ' + expected['claims'][0]['id']) + ')')
            run('Get Text', '#claim-citations', 'contains', '"source_hash"')
            run('Select Options By', '#graph-depth', 'value', '3')
            run('Click', '#graph-form button')
            run('Get Text', '#graph-status', '==', '4 entities · 3 relationships')
            run('Get Element Count', '#graph-nodes li', '==', 4)
            run('Get Element Count', '#graph-edges li', '==', 3)
            run('Get Element Count', '#graph-references li', '==', 5)
            run('Get Element Count', '#graph-nodes img, #graph-edges img, #graph-references img', '==', 0)
            _, _, rc = ssh.execute_command('python3 /tmp/oidc_probe.py browser-reader', return_stderr=True, return_rc=True, timeout='180 seconds')
            assert rc == 0, 'Cannot prepare Wiki Reader'
            run('New Context', 'ignoreHTTPSErrors=True'); run('New Page'); login('c0member')
            run('Wait For Elements State', '#new-page', 'hidden')
            run('Click', '#wiki-pages button:text-is(' + json.dumps(title) + ')')
            run('Get Property', '#wiki-body', 'readOnly', '==', True)
            run('Wait For Elements State', '#save-page', 'hidden')
            run('Wait For Elements State', '#claim-form', 'hidden')
            run('Get Element Count', '#wiki-history', '==', 0)
            page_id = browser.get_text('#wiki-identity').split(' · ')[0]
            run('Go To', 'https://' + host + '/wiki?page=' + page_id)
            run('Get Text', '#page-title', '==', title)
            run('Get Text', '#reader-content h2', '==', 'Revised browser content')
            run('Get Element Count', '#reader-content img', '==', 0)
            run('Wait For Elements State', '#wiki-workspace', 'hidden')
            run('Get Element Count', '#reader-tree a[aria-current="location"]', '==', 1)
            run('Click', '#article-ai > summary')
            run('Wait For Elements State', '#article-update-task', 'hidden')
            run('Click', '#article-read-task')
            run('Get Property', '#article-task textarea', 'value', 'contains', page_id)
            run('Get Element Count', '#reader-history-panel', '==', 0)
            assert browser.evaluate_javascript(None, 'async () => (await fetch("/api/v1/wiki/pages/"+'+json.dumps(page_id)+'+"?revision=1")).status') == 410, 'Retired Wiki body remained readable'
            run('Get Text', '#reader-content h2', '==', 'Revised browser content')
            assert_accessibility(browser, 'wiki', 'reader')
        except Exception as error:
            raise AssertionError('Disposable Wiki browser failed (' + type(error).__name__ + ')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_spaces_browser(self, module_id, host):
        """Independent normal SSO sessions exercise actual protected-space UI."""
        from urllib.parse import parse_qs, urlsplit
        builtin=BuiltIn(); previous=builtin.set_log_level('NONE'); stage='sign-in'
        try:
            ssh=builtin.get_library_instance('SSHLibrary'); browser=builtin.get_library_instance('Browser')
            payload=json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/personas.json'))
            retained=json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/expected-identities.json'))['protected']
            self._browser_password=payload['password']
            def run(name,*args): return builtin.run_keyword('Browser.'+name,*args)
            def login(username):
                run('Go To','https://'+host+'/auth/login')
                run('Wait For Elements State','input[name="username"]','visible','timeout=30s')
                browser.fill_text('input[name="username"]',username)
                browser.fill_text('input[name="password"]',self._browser_password)
                run('Click','#kc-login');run('Wait For Elements State','#sign-out','visible','timeout=30s')
            def admin_role(role):
                run('Go To','https://'+host+'/admin')
                row='#access-people tr.access-person:has(th:text-is("c0member"))'
                run('Click',row+' button:text-is("Change permissions")')
                run('Select Options By','#access-role','value',role)
                run('Click','#access-role-save')
                run('Get Text','#access-message','matches','Permissions (saved|are unchanged).*')
            owner_context=run('New Context','ignoreHTTPSErrors=True');run('New Page');login('c0owner')
            stage='space-creation';admin_role('editor')
            run('Go To','https://'+host+'/admin/spaces')
            name='<img src=x onerror=alert(1)> protected-'+secrets.token_hex(4)
            run('Fill Text','#space-name',name);run('Click','#create-space')
            run('Wait For Elements State','#managed-space:has-text('+json.dumps(name)+')','visible','timeout=30s')
            run('Get Text','#managed-space','==','Protected space: '+name)
            identifier=parse_qs(urlsplit(browser.get_url()).query)['space_id'][0]
            run('Get Element Count','#managed-space img, #space-selector img','==',0)
            row='#space-grant-list tr:has(select[aria-label="Space access for c0member"])'
            def grant(role):
                run('Select Options By',row+' select','value',role)
                run('Click',row+' button')
                run('Get Text',row+' [role="status"]','contains','Grant saved.')
            grant('reader')
            stage='space-navigation'
            run('Reload')
            run('Wait For Elements State','#managed-space:has-text('+json.dumps(name)+')','visible','timeout=30s')
            run('Get Text','#managed-space','==','Protected space: '+name)
            CzeroSso._verify_skip_link(browser,run)
            assert_accessibility(browser,'admin','admin')
            stage='private-wiki-creation'
            tools='https://'+host+'/wiki?view=tools&space_id='+identifier
            run('Go To',tools);run('Wait For Elements State','#wiki-workspace','visible','timeout=30s')
            run('Click','#new-page');run('Fill Text','#wiki-slug','private/'+secrets.token_hex(4))
            title='Private browser article '+secrets.token_hex(4)
            run('Fill Text','#wiki-title',title);run('Fill Text','#wiki-body','# Private original')
            run('Click','#save-page');run('Get Text','#page-status','==','Page saved.')
            run('Fill Text','#wiki-body','# Private revised');run('Click','#save-page')
            run('Get Text','#wiki-identity','contains','revision 2')
            page=browser.get_text('#wiki-identity').split(' · ')[0]
            stage='project-configuration'
            probe=Path(__file__).with_name('project_browser_probe.js').read_text()
            assert browser.evaluate_javascript(None,'('+probe+')') == {'initialized':True,'replay':True,'revision':2,'workflows':True,'monitoring':True,'reports':True}
            project_url='https://'+host+'/projects?space_id='+identifier
            run('Go To',project_url)
            run('Get Text','#project-title','==','<img src=x> Synthetic research')
            run('Get Text','#project-topics','contains','<script> synthetic topic')
            run('Get Text','#project-sources','contains','browser-source · partial · 0/1 items verified')
            run('Get Text','#project-work','contains','<script> synthetic queued investigation')
            run('Get Text','#project-work','contains','phase_incomplete')
            run('Get Text','#project-monitoring','contains','no_material_update')
            run('Get Text','#project-monitoring','contains','queries 1/5')
            run('Get Text','#project-work','contains','No successful weekly run recorded.')
            run('Get Text','#project-reports a','contains','Daily report')
            report_href=browser.get_attribute('#project-reports a','href')
            assert 'space_id='+identifier in report_href and 'revision=1' in report_href and 'page_id=' in report_href
            run('Get Text','#project-report-status','contains','external notification are separate')
            run('Get Element Count','#project-content img, #project-content script','==',0)
            assert_accessibility(browser,'projects','admin')
            stage='reader-role-cap'
            member_context=run('New Context','ignoreHTTPSErrors=True');run('New Page');login('c0member')
            run('Go To',tools);run('Wait For Elements State','#wiki-workspace','visible','timeout=30s')
            run('Click','#wiki-pages button:text-is('+json.dumps(title)+')')
            run('Get Property','#wiki-body','readOnly','==',True)
            run('Wait For Elements State','#save-page','hidden')
            run('Get Property','#wiki-body','value','contains','Private revised')
            run('Get Element Count','#wiki-history','==',0)
            assert_accessibility(browser,'wiki','reader')
            run('Go To',project_url)
            run('Get Text','#project-title','==','<img src=x> Synthetic research')
            run('Get Text','#project-config','contains','Configuration 2')
            run('Get Text','#project-sources','contains','coverage_incomplete')
            run('Get Text','#project-work','contains','<script> synthetic queued investigation')
            assert_accessibility(browser,'projects','reader')
            run('Go To',tools)
            # Same user, same UUID, explicit Shared choice: no private fallback.
            stage='shared-selection'
            shared=browser.get_property('#space-selector option:text-matches("shared")','value')
            run('Select Options By','#space-selector','value',shared)
            run('Wait For Elements State','#wiki-workspace','visible','timeout=30s')
            assert 'space_id=' not in browser.get_url(), 'Shared choice retained a private selector'
            run('Get Element Count','#wiki-pages button:text-is('+json.dumps(title)+')','==',0)
            # Read the evidence created BEFORE native backup/clean restore.
            stage='restored-evidence'
            citation=retained['sources'][0]['citation'];source=retained['sources'][0]['version']
            run('Go To','https://'+host+'/sources?space_id='+retained['space']['id']+
                '&source='+source['source_id']+'&version='+source['id']+'&chunk='+citation['chunk_id'])
            run('Get Text','#reader-document','contains','Selected native memory evidence')
            run('Get Text','#reader-excerpt','contains','Selected native memory evidence')
            assert_accessibility(browser,'sources','reader')
            run('Switch Context',owner_context);run('Go To','https://'+host+'/admin/spaces?space_id='+identifier)
            stage='editor-grant';grant('editor')
            run('Switch Context',member_context);run('Go To',tools)
            run('Click','#wiki-pages button:text-is('+json.dumps(title)+')')
            run('Get Property','#wiki-body','readOnly','==',False)
            run('Fill Text','#wiki-body','# Independent private update');run('Click','#save-page')
            run('Get Text','#wiki-identity','contains','revision 3')
            assert_accessibility(browser,'wiki','editor')
            stage='manager-restart'
            _,rc=ssh.execute_command('runagent -m '+shlex.quote(module_id)+' systemctl --user restart czero-pod.service',return_rc=True,timeout='180 seconds')
            assert rc==0, 'Protected browser manager restart failed'
            builtin.run_keyword('Wait Until Keyword Succeeds','30s','2s','Check application route')
            article='https://'+host+'/wiki?space_id='+identifier+'&page='+page
            run('Go To',project_url)
            run('Get Text','#project-config','contains','Configuration 2')
            run('Get Text','#project-work','contains','phase_incomplete')
            run('Get Text','#project-monitoring','contains','no_material_update')
            run('Go To',article);run('Get Text','#reader-content h2','==','Independent private update')
            run('Get Element Count','#reader-history-panel','==',0)
            expired='/api/v1/wiki/pages/'+page+'?space_id='+identifier+'&revision=1'
            assert browser.evaluate_javascript(None,'async () => (await fetch('+json.dumps(expired)+')).status')==410, 'Protected retired body remained readable'
            stage='revoked-view-clearing'
            run('Switch Context',owner_context);run('Reload');grant('')
            run('Switch Context',member_context);run('Click','#refresh-space')
            run('Get Text','#space-status','contains','unavailable')
            run('Get Element Count','#reader-content h2','==',0)
            run('Get Text','#page-title','==','Knowledge')
            run('Get Element Count','#reader-export[href]','==',0)
            run('Get Element Count','#reader-history a','==',0)
            assert 'space_id='+identifier in browser.get_url(), 'Revoked space silently fell back'
            run('Reload');run('Get Element Count','#reader-content h2','==',0)
            run('Go To',project_url)
            run('Wait For Elements State','#project-content','hidden')
            run('Get Text','#project-description','==','')
            run('Get Element Count','#project-sources li','==',0)
            assert 'space_id='+identifier in browser.get_url(), 'Revoked project silently fell back'
        except Exception as error:
            raise AssertionError('Disposable spaces browser failed at '+stage+' ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_search_browser(self, host):
        builtin = BuiltIn(); previous = builtin.set_log_level('NONE')
        try:
            ssh = builtin.get_library_instance('SSHLibrary')
            payload = json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/personas.json'))
            self._browser_password = payload['password']
            browser = builtin.get_library_instance('Browser')
            def run(name, *args): return builtin.run_keyword('Browser.' + name, *args)
            for username in ('c0owner', 'c0member'):
                if username == 'c0member':
                    run('New Context', 'ignoreHTTPSErrors=True'); run('New Page')
                run('Go To', 'https://' + host + '/search')
                run('Wait For Elements State', '#search-signin', 'visible', 'timeout=30s')
                run('Click', '#search-signin')
                run('Click', '#website-sign-in button[type="submit"]')
                browser.fill_text('input[name="username"]', username)
                browser.fill_text('input[name="password"]', self._browser_password)
                run('Click', '#kc-login')
                run('Wait For Elements State', '#sign-out', 'visible', 'timeout=30s')
                run('Go To', 'https://' + host + '/search')
                run('Wait For Elements State', '#search-workspace', 'visible', 'timeout=30s')
                assert_accessibility(browser, 'search', 'admin' if username == 'c0owner' else 'reader')
                run('Fill Text', '#knowledge-query', 'independent authored')
                run('Click', '#knowledge-search-form > details > summary')
                run('Select Options By', '#knowledge-mode', 'value', 'hybrid')
                run('Select Options By', '#knowledge-rerank', 'value', 'filter')
                run('Click', '#knowledge-search-form button')
                run('Click', '#knowledge-search-details >> xpath=.. >> summary')
                run('Get Text', '#knowledge-search-details', 'contains', 'hybrid+filter')
                run('Get Element Count', '#knowledge-results article', '==', 1)
                run('Get Text', '#knowledge-results', 'contains', 'Independent authored claims')
                run('Click', '#knowledge-results details summary')
                run('Get Text', '#knowledge-results', 'contains', '"revision_id"')
                run('Select Options By', '#knowledge-mode', 'value', 'text')
                run('Select Options By', '#knowledge-rerank', 'value', 'off')
                run('Click', '#knowledge-search-form button')
                run('Get Text', '#knowledge-search-details', 'contains', 'text ·')
                run('Reload')
                run('Wait For Elements State', '#search-workspace', 'visible', 'timeout=30s')
                run('Click', '#knowledge-index-status >> xpath=.. >> summary')
                run('Get Text', '#knowledge-index-status', 'contains', 'derivative chunks indexed')
                run('Get Element Count', '#knowledge-results article', '==', 0)
                run('Get Element Count', '#knowledge-results img', '==', 0)
        except Exception as error:
            raise AssertionError('Disposable search browser failed (' + type(error).__name__ + ')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_oauth_browser(self, module_id, host):
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            ssh=builtin.get_library_instance('SSHLibrary');browser=builtin.get_library_instance('Browser')
            payload=json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/personas.json'))
            self._browser_password=payload['password']
            def run(name,*args): return builtin.run_keyword('Browser.'+name,*args)
            for role in ('admin','reader','editor'):
                _, _, rc=ssh.execute_command('python3 /tmp/oauth_fixture.py '+shlex.quote(module_id)+
                    ' browser-prepare '+role,return_stderr=True,return_rc=True,timeout='180 seconds')
                if rc: raise AssertionError('Cannot prepare OAuth browser request')
                value=json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/browser-oauth.json'))
                run('New Context','ignoreHTTPSErrors=True','acceptDownloads=True');run('New Page')
                # Admin begins with a remembered website session, then consents
                # separately to background access. Other roles stay ordinary.
                if role == 'admin':
                    run('Go To','https://'+host+'/auth/sign-in')
                    run('Get Property','input[name="remember"]','checked','==',False)
                    run('Check Checkbox','input[name="remember"]')
                    run('Click','#website-sign-in button[type="submit"]')
                    run('Wait For Elements State','input[name="username"]','visible','timeout=30s')
                    browser.fill_text('input[name="username"]','c0owner')
                    browser.fill_text('input[name="password"]',self._browser_password)
                    run('Click','#kc-login')
                    run('Wait For Elements State','#sign-out, [name="accept"]','visible','timeout=30s')
                    if browser.get_element_count('[name="accept"]'):run('Click','[name="accept"]')
                    run('Wait For Elements State','#sign-out','visible','timeout=30s')
                # Private URLs/passwords never enter Robot keyword arguments.
                browser.go_to(value['authorization_url'])
                if role != 'admin':
                    run('Wait For Elements State','input[name="username"]','visible','timeout=30s')
                    browser.fill_text('input[name="username"]','c0member')
                    browser.fill_text('input[name="password"]',self._browser_password)
                    run('Click','#kc-login')
                run('Wait For Elements State','#approve','enabled','timeout=30s')
                run('Get Text','#client','==',value['client']['client_name'])
                run('Get Element Count','#client img','==',0)
                disabled={'admin':0,'editor':1,'reader':2}[role]
                run('Get Element Count','#scopes input:disabled','==',disabled)
                run('Get Element Count','#scopes input:checked','==',3-disabled)
                run('Wait For Elements State','#background','visible','timeout=30s')
                assert browser.get_property('#background','checked') is False, 'Background consent was preselected'
                run('Get Text','#background-help','contains','30 days')
                if role == 'admin':
                    run('Check Checkbox','#background')
                    run('Get Text','#approve','==','Continue to background sign-in')
                    run('Click','#approve')
                    run('Wait For Elements State','input[name="password"]','visible','timeout=30s')
                    if browser.get_element_count('input[name="username"]:visible'):
                        browser.fill_text('input[name="username"]','c0owner')
                    browser.fill_text('input[name="password"]',self._browser_password)
                    run('Click','#kc-login')
                    run('Wait For Elements State','#approve, [name="accept"]','visible','timeout=30s')
                    if browser.get_element_count('[name="accept"]'):
                        run('Click','[name="accept"]')
                    run('Wait For Elements State','#approve','enabled','timeout=30s')
                    assert browser.get_property('#background','checked') is True, 'Background choice was lost'
                    run('Get Text','#approve','==','Authorize')
                    value['persistent'] = True
                run('Click','#approve')
                run('Get Text','h1','==','Use C0 with ChatGPT')
                run('Get Element Count','nav a[aria-current="page"]','==',1)
                run('Wait For Elements State', '#guide-mcp', 'visible', 'timeout=30s')
                run('Get Property','#agent-mcp-url','value','==','https://'+host+'/mcp')
                run('Get Property', '#agent-name', 'value', '==', 'C0')
                run('Get Property', '#agent-description', 'value', '==', 'C0 Knowledge Storage on ' + host)
                run('Get Attribute', '#download-skill', 'href', '==', './agents/c0-memory.skill')
                run('Get Attribute', 'button[data-copy-target="agent-name"]', 'aria-label', '==', 'Copy name')
                run('Get Attribute', 'button[data-copy-target="agent-description"]', 'aria-label', '==', 'Copy description')
                with tempfile.TemporaryDirectory(prefix='czero-agent-download-') as directory:
                    path = Path(directory) / 'memory.skill'
                    promise = browser.promise_to_wait_for_download(saveAs=str(path))
                    run('Click', '#download-skill')
                    browser.wait_for(promise)
                    self._verify_agent_archive(path, host)
                    run('Wait For Elements State', '#download-plugin', 'enabled', 'timeout=30s')
                    browser.fill_text('#chatgpt-connection', 'asdk_app_disposable')
                    path = Path(directory) / 'plugin.zip'
                    promise = browser.promise_to_wait_for_download(saveAs=str(path))
                    run('Click', '#download-plugin')
                    browser.wait_for(promise)
                    self._verify_agent_archive(path, host, plugin=True)
                run('Click','button[data-copy-target="agent-mcp-url"]')
                run('Get Text','#copy-status','matches',r'^(Connection copied\.|Select and copy the connection above\.)$')
                # The callback query is private and validated by the host probe.
                value['returned_callback']=browser.get_url()
                with tempfile.TemporaryDirectory(prefix='czero-oauth-browser-') as directory:
                    path=Path(directory)/'request.json';path.write_text(json.dumps(value));path.chmod(0o600)
                    ssh.put_file(str(path),'/tmp/czero-oidc-fixture/browser-oauth.json',mode='0600')
                _, _, rc=ssh.execute_command('python3 /tmp/oauth_fixture.py '+shlex.quote(module_id)+
                    ' browser-complete',return_stderr=True,return_rc=True,timeout='300 seconds')
                if rc: raise AssertionError('Real OAuth browser/token assertions failed')
                run('Go To','https://'+host+'/?view=account')
                if role == 'admin':run('Get Text','#account-status','contains','Remembered on this device')
                target = 'button[aria-label=' + json.dumps('Disconnect ' + value['client']['client_name']) + ']'
                run('Wait For Elements State',target,'visible','timeout=30s')
                run('Get Element Count','#connections-list img','==',0)
                assert_accessibility(browser,'account',role)
                run('Click',target)
                run('Wait For Elements State',target,'hidden','timeout=30s')
                _, _, rc=ssh.execute_command('python3 /tmp/oauth_fixture.py '+shlex.quote(module_id)+
                    ' browser-disconnected',return_stderr=True,return_rc=True,timeout='60 seconds')
                if rc: raise AssertionError('Account disconnect did not revoke the browser client')
                run('Go To', 'https://' + host + '/')
                run('Wait For Elements State', '#sign-out', 'visible', 'timeout=30s')
                assert_accessibility(browser, 'home', role)
                run('Go To', 'https://' + host + '/agents')
                run('Get Text', 'h1', '==', 'Use C0 with ChatGPT')
                run('Click', '#reader-root > summary')
                run('Wait For Elements State', '#guide-tasks > details >> nth=0', 'visible', 'timeout=30s')
                run('Get Element Count', '#guide-tasks > details', '==', 1 if role == 'reader' else 7)
                run('Get Element Count', '#guide-workflows > details', '==', 2 if role == 'reader' else 6)
                run('Get Text', '#guide-rules', 'contains', 'untrusted evidence')
                if role != 'reader':
                    run('Click', '#guide-workflows > details:nth-child(6) > summary')
                    run('Get Text', '#guide-workflows', 'contains', 'whole receipt')
                assert_accessibility(browser, 'agents', role)
                self._verify_admin_controls(browser, run, role, host, module_id)
                _, _, rc=ssh.execute_command('python3 /tmp/oauth_fixture.py '+shlex.quote(module_id)+
                    ' browser-cleanup',return_stderr=True,return_rc=True,timeout='180 seconds')
                if rc: raise AssertionError('OAuth browser cleanup failed')
                run('Close Context')
            _, rc=ssh.execute_command('python3 /tmp/oidc_fixture.py check-logs '+shlex.quote(module_id),
                                     return_rc=True,timeout='180 seconds')
            if rc: raise AssertionError('OAuth browser logs contain private query values')
        except Exception as error:
            raise AssertionError('Disposable OAuth browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @staticmethod
    def _verify_agent_archive(path, host, plugin=False):
        from zipfile import ZipFile
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            expected = {'SKILL.md', 'agents/openai.yaml', 'LICENSE'}
            if plugin:
                expected = {'plugin.json', '.app.json', 'LICENSE', 'references/instance.md',
                    'references/connection.md', 'references/maintenance.md', 'references/projects.md',
                    'skills/c0-setup/SKILL.md', 'skills/c0-research/SKILL.md',
                    'skills/c0-maintain-knowledge/SKILL.md', 'skills/c0-projects/SKILL.md'}
            assert names == expected and len(archive.namelist()) == len(names), 'Unexpected generated archive contents'
            assert 'LICENSE' in names and not names.intersection({'AGENTS.md', 'PLAN.md', 'mcp.json', '.mcp.json'})
            binding = archive.read('references/instance.md' if plugin else 'SKILL.md').decode()
            assert host in binding and 'https://' + host + '/mcp' in binding, 'Archive is not bound to this instance'
            if plugin:
                assert json.loads(archive.read('.app.json')) == {'apps': {'c0': {'id': 'asdk_app_disposable', 'required': True}}}

    @staticmethod
    def _verify_skip_link(browser, run):
        from urllib.parse import urlsplit
        before=urlsplit(browser.get_url())
        run('Press Keys','body','Tab')
        run('Wait For Elements State','.skip-link','focused')
        run('Press Keys','.skip-link','Enter')
        run('Wait For Elements State','#main-content','focused')
        after=urlsplit(browser.get_url())
        assert before._replace(fragment='')==after._replace(fragment=''), 'Skip link changed page or selected space'

    @staticmethod
    def _verify_admin_controls(browser, run, role, host, module_id=None):
        run('Go To', 'https://' + host + '/admin')
        if role != 'admin':
            run('Get Text', '#admin-account', 'contains', 'Only C0 administrators')
            run('Wait For Elements State', '#access-workspace', 'hidden')
            run('Wait For Elements State', 'nav a[data-admin-link]', 'hidden')
            assert_accessibility(browser, 'admin', role)
            return
        run('Wait For Elements State', '#access-workspace', 'visible', 'timeout=30s')
        run('Wait For Elements State', 'nav a[data-admin-link]', 'visible', 'timeout=30s')
        run('Get Element Count', 'nav a[aria-current="page"]', '==', 1)
        run('Get Element Count', '#job-form, #schedule-form, #client-form', '==', 0)
        run('Get Text', '#people-table caption', '==', 'People, application requests and connections')
        assert_accessibility(browser, 'admin', role)
        if module_id is not None:
            CzeroSso._verify_people_access(browser, run, host, module_id)
        run('Go To', 'https://' + host + '/admin/advanced')
        run('Wait For Elements State', '#admin-workspace', 'visible', 'timeout=30s')
        run('Wait For Elements State', '#cimd-administration', 'visible', 'timeout=30s')
        CzeroSso._verify_skip_link(browser,run)
        run('Wait For Elements State', '#cimd-preview', 'disabled', 'timeout=30s')
        if module_id is not None:
            ssh = BuiltIn().get_library_instance('SSHLibrary')
            def switch(enabled):
                request = json.dumps({'host': host, 'lets_encrypt': False, 'cimd_enabled': enabled})
                _, rc = ssh.execute_command('api-cli run module/' + shlex.quote(module_id) +
                    '/configure-module --data ' + shlex.quote(request), return_rc=True, timeout='180 seconds')
                if rc:
                    raise AssertionError('Disposable CIMD switch failed')
            try:
                switch(True)
                run('Reload')
                run('Wait For Elements State', '#cimd-preview', 'enabled', 'timeout=30s')
                run('Fill Text', '#cimd-url', 'https://127.0.0.1/client.json')
                run('Click', '#cimd-preview')
                run('Get Text', '#cimd-form-status', 'contains', 'Check the exact HTTPS URL')
                run('Fill Text', '#cimd-url', 'https://localhost/client.json')
                run('Click', '#cimd-preview')
                run('Get Text', '#cimd-form-status', 'contains', 'Metadata is unavailable')
                run('Wait For Elements State', '#cimd-approve', 'disabled')
            finally:
                switch(False)
            run('Click', '#cimd-refresh')
            run('Wait For Elements State', '#cimd-preview', 'disabled', 'timeout=30s')
        name = 'browser-client-' + secrets.token_hex(4)
        run('Fill Text', '#client-name', name)
        run('Fill Text', '#client-callbacks', 'https://client.example.test/callback')
        run('Click', '#approve-client')
        row = '#client-list li:has-text("' + name + '")'
        run('Wait For Elements State', row, 'visible', 'timeout=30s')
        run('Click', row + ' button:text-is("Disable application for everyone")')
        run('Wait For Elements State', row + ' button:text-is("Enable application for everyone")', 'visible', 'timeout=30s')
        run('Go To', 'https://' + host + '/admin/work')
        run('Wait For Elements State', '#admin-workspace', 'visible', 'timeout=30s')
        CzeroSso._verify_skip_link(browser,run)
        run('Select Options By', '#job-handler', 'value', 'health')
        run('Fill Text', '#job-payload', '{}')
        run('Click', '#enqueue-job')
        run('Wait For Elements State', '#job-detail', 'visible', 'timeout=30s')
        # Capture only a public job UUID, never credentials or authorization URLs.
        job_id = json.loads(browser.get_text('#job-data'))['id']
        for _ in range(45):
            if json.loads(browser.get_text('#job-data'))['state'] == 'succeeded':
                break
            run('Click', '#refresh-jobs')
            run('Wait For Elements State', '#job-status:text-matches("latest jobs shown")', 'visible', 'timeout=30s')
            run('Click', '#job-list li:has-text("' + job_id + '") button')
            run('Wait For Elements State', '#job-data:has-text("' + job_id + '")', 'visible', 'timeout=30s')
            BuiltIn().run_keyword('Sleep', '2s')
        run('Get Text', '#job-data', 'contains', '"state": "succeeded"')
        name = 'browser-schedule-' + secrets.token_hex(4)
        run('Fill Text', '#schedule-name', name)
        run('Select Options By', '#schedule-handler', 'value', 'health')
        run('Fill Text', '#schedule-payload', '{}')
        run('Fill Text', '#schedule-interval', '3600')
        run('Click', '#create-schedule')
        run('Wait For Elements State', '#schedule-identity:has-text("' + name + '")', 'visible', 'timeout=30s')
        run('Uncheck Checkbox', '#schedule-enabled')
        run('Fill Text', '#schedule-edit-interval', '7200')
        run('Click', '#save-schedule')
        row = '#schedule-list li:has-text("' + name + '")'
        run('Get Text', row, 'contains', 'paused · every 7200 seconds')
        run('Reload')
        run('Wait For Elements State', row, 'visible', 'timeout=30s')
        run('Click', row + ' button')
        run('Get Property', '#schedule-enabled', 'checked', '==', False)
        run('Get Property', '#schedule-edit-interval', 'value', '==', '7200')
        assert_accessibility(browser, 'admin', role)

    @staticmethod
    def _verify_people_access(browser, run, host, module_id):
        """Actual native SSO/HTTPS; browser mutates, independent HTTP grades."""
        ssh=BuiltIn().get_library_instance('SSHLibrary');measurements=[]
        def phase(name):
            output,_,rc=ssh.execute_command('python3 /tmp/access_fixture.py '+shlex.quote(module_id)+' '+name,
                return_stderr=True,return_rc=True,timeout='180 seconds')
            assert rc==0,'Native access fixture failed at '+name
            marker='C0 workspace access: '
            lines=[line for line in output.splitlines() if line.startswith(marker)]
            assert len(lines)==1,'Native access measurement missing'
            measured=validate_workspace_access(json.loads(lines[0][len(marker):]))
            assert measured['phase']==name,'Native access phase differs'
            measurements.append(measured)
            BuiltIn().log_to_console(marker+json.dumps(measured,sort_keys=True))
        output,rc=ssh.execute_command('api-cli run module/'+shlex.quote(module_id)+'/get-configuration',
                                      return_rc=True,timeout='180 seconds')
        assert rc==0,'Native access discovery baseline unavailable'
        original=json.loads(output)['cimd_enabled'];assert type(original) is bool
        def discovery(enabled):
            request=json.dumps({'host':host,'lets_encrypt':False,'cimd_enabled':enabled})
            _,rc=ssh.execute_command('api-cli run module/'+shlex.quote(module_id)+'/configure-module --data '+shlex.quote(request),
                                    return_rc=True,timeout='180 seconds')
            assert rc==0,'Native access discovery change failed'
        try:
            discovery(True)
            phase('prepare')
            run('Reload');run('Get Text','#pending-summary','contains','pending application request')
            row='#access-people tr.access-application:has-text("Application awaiting review")'
            run('Click',row+' button:text-is("Approve")')
            run('Wait For Elements State','#access-approve-save','enabled','timeout=30s')
            run('Get Text','#access-review-info','contains','C0 disposable access browser')
            run('Get Property','#access-approve-write','checked','==',False)
            run('Get Property','#access-approve-manage','checked','==',False)
            run('Click','#access-approve-save')
            run('Wait For Elements State','#access-message:has-text("Application approved.")','visible','timeout=30s')
            run('Get Text','#access-message','contains','Application approved.')
            phase('approved')
            value=json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/workspace-access.json'))
            # Cancel the new sibling, retaining the first request to prove exact targeting.
            run('Click','#access-refresh')
            row='#access-people tr.access-application:not([data-application-id="'+value['request_id']+'"]):has(button:text-is("Decline"))'
            run('Click',row+' button:text-is("Decline")');run('Click','#access-confirm-save')
            run('Wait For Elements State','#access-message:has-text("Access updated.")','visible','timeout=30s')
            run('Get Text','#access-message','contains','Access updated.')
            phase('declined')
            value=json.loads(ssh.execute_command('cat /tmp/czero-oidc-fixture/workspace-access.json'))
            run('Click','#access-refresh')
            row='#access-people tr[data-application-id="'+value['connection_ids'][0]+'"]'
            run('Click',row+' button:text-is("Disconnect application connection")');run('Click','#access-confirm-save')
            run('Wait For Elements State','#access-message:has-text("Access updated.")','visible','timeout=30s')
            run('Get Text','#access-message','contains','Access updated.')
            phase('disconnected')
            person='#access-people tr.access-person[data-account-id="'+value['member_id']+'"]'
            run('Click',person+' button:text-is("Block user")');run('Click','#access-confirm-save')
            run('Wait For Elements State','#access-message:has-text("Access updated.")','visible','timeout=30s')
            run('Get Text','#access-message','contains','Access updated.')
            phase('blocked')
            # Restart while blocked; normal admission must not revive the account.
            _,rc=ssh.execute_command('api-cli run node/1/restart-module --data '+shlex.quote(json.dumps({'module_id':module_id})),
                                    return_rc=True,timeout='180 seconds')
            assert rc==0,'Native access restart failed'
            BuiltIn().run_keyword('Wait Until Keyword Succeeds','30s','2s','Check application route')
            phase('blocked_after_restart')
            run('Reload');run('Click',person+' button:text-is("Unblock user")')
            run('Select Options By','#access-role','value','reader');run('Click','#access-role-save')
            run('Wait For Elements State','#access-message:has-text("Permissions saved.")','visible','timeout=30s')
            run('Get Text','#access-message','contains','Permissions saved.')
            phase('unblocked')
            for selected,stage in [('editor','editor_permissions'),('admin','manage_permissions'),('reader','reader_permissions')]:
                run('Click',person+' button:text-is("Change permissions")')
                run('Select Options By','#access-role','value',selected);run('Click','#access-role-save')
                run('Wait For Elements State','#access-message:has-text("Permissions saved.")','visible','timeout=30s')
                run('Get Text','#access-message','contains','Permissions saved.')
                phase(stage)
            require_workspace_access(measurements)
            run('Click','#access-refresh');assert_accessibility(browser,'admin','admin')
        finally:
            discovery(original)


    @keyword
    def assert_disposable_sso_browser_password_is_private(self):
        builtin=BuiltIn(); output=Path(builtin.get_variable_value('${OUTPUT FILE}'))
        previous = builtin.set_log_level('NONE')
        try:
            key = builtin.get_library_instance('SSHLibrary').execute_command('cat /tmp/czero-oidc-fixture/retrieval-key')
            assert isinstance(key,str) and len(key)>20, 'Fixture provider credential missing'
            assert_no_oauth_queries((output, output.parent/'playwright-log.txt'))
            for path in (output,output.parent/'playwright-log.txt'):
                if path.exists():
                    content=path.read_text(errors='replace')
                    if self._browser_password in content or key.strip() in content:
                        raise AssertionError('Temporary fixture credential entered test output')
        finally:
            builtin.set_log_level(previous)
