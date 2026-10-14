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


class CzeroSso:
    @keyword
    def provision_disposable_sso(self, module_id, host):
        builtin = BuiltIn()
        ssh = builtin.get_library_instance("SSHLibrary")
        previous = builtin.set_log_level("NONE")
        try:
            for name in ("oidc_fixture.py", "oidc_probe.py"):
                ssh.put_file(str(Path(__file__).with_name(name)), "/tmp/" + name)
            with tempfile.TemporaryDirectory(prefix="czero-sso-") as directory:
                payload = Path(directory) / "payload.json"
                payload.write_text(json.dumps({"password": "Sso-" + secrets.token_urlsafe(32) + "9!", "host": host}))
                payload.chmod(0o600)
                ssh.put_file(str(payload), "/tmp/czero-sso-payload.json", mode="0600")
            output, errors, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py setup /tmp/czero-sso-payload.json",
                                             return_stderr=True, return_rc=True, timeout="600 seconds")
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

    @staticmethod
    def _network(ssh, module_id):
        _, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py network " + shlex.quote(module_id),
                                    return_rc=True, timeout="180 seconds")
        if rc:
            raise AssertionError("Disposable Czero SSO network fixture failed")

    @keyword
    def verify_disposable_sso(self, module_id):
        builtin = BuiltIn()
        previous = builtin.set_log_level("NONE")
        try:
            ssh = builtin.get_library_instance("SSHLibrary")
            _, errors, rc = ssh.execute_command("python3 /tmp/oidc_probe.py", return_stderr=True, return_rc=True, timeout="180 seconds")
            if rc:
                # Probe emits only fixed assertions or an exception class.
                raise AssertionError("Real IdP probe: " + errors.strip())
            _, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py check-logs " + shlex.quote(module_id),
                                       return_rc=True, timeout="180 seconds")
            if rc:
                raise AssertionError("Disposable access logs contain OAuth query values")
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
            self._persistence("verify")
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
                browser.fill_text('input[name="username"]',username)
                browser.fill_text('input[name="password"]',self._browser_password)
                run('Click','#kc-login')
                # OIDC callback returns to the home page.
                run('Wait For Elements State','#sign-out','visible','timeout=30s')
                run('Go To','https://'+host+'/objects')
                run('Wait For Elements State','#records-workspace','visible','timeout=30s')
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
            run('Fill Text','#record-data','{"name":"Browser rack revised","count":3}')
            run('Click','#save-record')
            run('Get Text','#record-status','==','Record saved.')
            run('Get Text','#record-identity','contains','revision 2')
            run('Reload')
            run('Select Options By','#record-type','value',type_name)
            run('Click','#record-list button')
            run('Get Property','#record-data','value','contains','"count": 3')
            hostile='<img src=x onerror=alert(1)>'
            run('Fill Text','#record-data',json.dumps({'name':hostile,'count':3}))
            run('Click','#save-record')
            run('Get Text','#record-status','==','Record saved.')
            run('Get Text','#record-list button','==',hostile)
            run('Get Element Count','#record-list img','==',0)
            # Change membership through real owner-authenticated HTTP on the VM.
            _,errors,rc=ssh.execute_command('python3 /tmp/oidc_probe.py browser-reader',return_stderr=True,return_rc=True,timeout='180 seconds')
            if rc: raise AssertionError('Cannot prepare disposable Reader browser')
            run('New Context','ignoreHTTPSErrors=True')
            run('New Page')
            login('c0member')
            run('Select Options By','#record-type','value',type_name)
            run('Wait For Elements State','#new-record','hidden')
            run('Wait For Elements State','#type-registration','hidden')
            run('Click','#record-list button')
            run('Get Property','#record-data','readOnly','==',True)
            run('Wait For Elements State','#save-record','hidden')
            run('Get Property','#record-data','value','contains','"count": 3')
        except Exception as error:
            raise AssertionError('Disposable object browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

    @keyword
    def assert_disposable_sso_browser_password_is_private(self):
        builtin=BuiltIn(); output=Path(builtin.get_variable_value('${OUTPUT FILE}'))
        for path in (output,output.parent/'playwright-log.txt'):
            if path.exists() and self._browser_password in path.read_text(errors='replace'):
                raise AssertionError('Temporary SSO browser password entered test output')
