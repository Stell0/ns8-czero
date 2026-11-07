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
from vue_native_browser import NativeWebsite
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
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            NativeWebsite(self,host,builtin).account_switch(module_id)
        except Exception as error:
            raise AssertionError('Disposable account_switch browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_objects_browser(self, host):
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            NativeWebsite(self,host,builtin).objects()
        except Exception as error:
            raise AssertionError('Disposable objects browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_sources_browser(self, host):
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            NativeWebsite(self,host,builtin).sources()
        except Exception as error:
            raise AssertionError('Disposable sources browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_wiki_browser(self, host):
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            NativeWebsite(self,host,builtin).wiki()
        except Exception as error:
            raise AssertionError('Disposable wiki browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_spaces_browser(self, module_id, host):
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            NativeWebsite(self,host,builtin).spaces(module_id)
        except Exception as error:
            raise AssertionError('Disposable spaces browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_search_browser(self, host):
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            NativeWebsite(self,host,builtin).search()
        except Exception as error:
            raise AssertionError('Disposable search browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_oauth_browser(self, module_id, host):
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            NativeWebsite(self,host,builtin).oauth(module_id)
        except Exception as error:
            raise AssertionError('Disposable oauth browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @staticmethod
    def _verify_agent_archive(path, host, plugin=False):
        from zipfile import ZipFile
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            expected = {'SKILL.md', 'agents/openai.yaml', 'LICENSE', 'references/compiler.md', 'references/scheduling.md'}
            if plugin:
                expected = {'plugin.json', '.app.json', 'LICENSE', 'references/instance.md',
                    'references/connection.md', 'references/maintenance.md', 'references/projects.md',
                    'skills/c0-setup/SKILL.md', 'skills/c0-research/SKILL.md',
                    'skills/c0-maintain-knowledge/SKILL.md', 'skills/c0-projects/SKILL.md',
        'skills/c0-knowledge-compiler/SKILL.md', 'references/compiler.md', 'references/scheduling.md'}
            assert names == expected and len(archive.namelist()) == len(names), 'Unexpected generated archive contents'
            assert 'LICENSE' in names and not names.intersection({'AGENTS.md', 'PLAN.md', 'mcp.json', '.mcp.json'})
            binding = archive.read('references/instance.md' if plugin else 'SKILL.md').decode()
            assert host in binding and 'https://' + host + '/mcp' in binding, 'Archive is not bound to this instance'
            if plugin:
                assert json.loads(archive.read('.app.json')) == {'apps': {'c0': {'id': 'asdk_app_disposable', 'required': True}}}





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
