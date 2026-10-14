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


class CzeroSso:
    @keyword
    def provision_disposable_sso(self, module_id, host):
        configure_browser_diagnostics()
        builtin = BuiltIn()
        ssh = builtin.get_library_instance("SSHLibrary")
        previous = builtin.set_log_level("NONE")
        try:
            for name in ("oidc_fixture.py", "oidc_probe.py", "retrieval_fixture.py", "oauth_fixture.py", "mcp_tls_probe.py"):
                ssh.put_file(str(Path(__file__).with_name(name)), "/tmp/" + name)
            fixture_root = Path(__file__).parent / 'fixtures/evidence'
            for name in ('manifest.json', 'sample.txt', 'sample.md', 'sample.pdf', 'sample.docx'):
                ssh.put_file(str(fixture_root / name), '/tmp/czero-evidence-' + name, mode='0644')
            with tempfile.TemporaryDirectory(prefix="czero-sso-") as directory:
                payload = Path(directory) / "payload.json"
                payload.write_text(json.dumps({"password": "Sso-" + secrets.token_urlsafe(32) + "9!", "host": host}))
                payload.chmod(0o600)
                ssh.put_file(str(payload), "/tmp/czero-sso-payload.json", mode="0600")
            output, errors, rc = ssh.execute_command("python3 /tmp/oidc_fixture.py setup /tmp/czero-sso-payload.json",
                                             return_stderr=True, return_rc=True, timeout="900 seconds")
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
            _, errors, rc = ssh.execute_command("python3 /tmp/oauth_fixture.py " + shlex.quote(module_id),
                return_stderr=True, return_rc=True, timeout="300 seconds")
            if rc:
                raise AssertionError("Installed OAuth probe: " + errors.strip())
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
            self._persistence("verify")
            self._retrieval(module_id, "verify")
            self._oauth_persistence(module_id, "verify")
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
        self._oauth_persistence(module_id, "seed")

    @staticmethod
    def _oauth_persistence(module_id, operation):
        builtin = BuiltIn(); previous = builtin.set_log_level('NONE')
        try:
            ssh = builtin.get_library_instance('SSHLibrary')
            _, errors, rc = ssh.execute_command('python3 /tmp/oauth_fixture.py ' + shlex.quote(module_id) +
                ' ' + operation, return_stderr=True, return_rc=True, timeout='300 seconds')
            if rc:
                raise AssertionError('Disposable OAuth recovery: ' + errors.strip())
        finally:
            builtin.set_log_level(previous)

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
                run('Go To', 'https://' + host + '/sources')
                run('Wait For Elements State', '#sources-signin', 'visible', 'timeout=30s')
                run('Click', '#sources-signin')
                browser.fill_text('input[name="username"]', username)
                browser.fill_text('input[name="password"]', self._browser_password)
                run('Click', '#kc-login')
                run('Wait For Elements State', '#sign-out', 'visible', 'timeout=30s')
                run('Go To', 'https://' + host + '/sources')
                run('Wait For Elements State', '#sources-workspace', 'visible', 'timeout=30s')
            def view(number, expected):
                selector = '#source-versions button:text-is("View version ' + str(number) + '")'
                run('Wait For Elements State', selector, 'visible', 'timeout=100s')
                run('Click', selector)
                run('Get Text', '#document-text', 'contains', expected)
            login('c0owner')
            title = '<img src=x onerror=alert(1)> browser-source-' + secrets.token_hex(4)
            sample = Path(__file__).parent / 'fixtures/evidence/sample.txt'
            expected_text = sample.read_text()
            run('Click', '#source-upload summary')
            run('Fill Text', '#upload-title', title)
            run('Upload File By Selector', '#upload-file', str(sample))
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
            run('Click', '#source-upload summary')
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
                run('Go To', 'https://' + host + '/wiki')
                run('Wait For Elements State', '#wiki-signin', 'visible', 'timeout=30s')
                run('Click', '#wiki-signin')
                browser.fill_text('input[name="username"]', username)
                browser.fill_text('input[name="password"]', self._browser_password)
                run('Click', '#kc-login')
                run('Wait For Elements State', '#sign-out', 'visible', 'timeout=30s')
                run('Go To', 'https://' + host + '/wiki')
                run('Wait For Elements State', '#wiki-workspace', 'visible', 'timeout=30s')
            login('c0owner')
            run('Click', '#new-page')
            slug = 'browser-wiki-' + secrets.token_hex(4)
            title = '<img src=x onerror=alert(1)> ' + slug
            run('Fill Text', '#wiki-slug', slug)
            run('Fill Text', '#wiki-title', title)
            run('Fill Text', '#wiki-body', '# Authored browser content')
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
            run('Click', '#wiki-history button:text-is("View revision 1")')
            run('Get Text', '#wiki-revision', 'contains', '# Authored browser content')
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
            _, _, rc = ssh.execute_command('python3 /tmp/oidc_probe.py browser-reader', return_stderr=True, return_rc=True, timeout='180 seconds')
            assert rc == 0, 'Cannot prepare Wiki Reader'
            run('New Context', 'ignoreHTTPSErrors=True'); run('New Page'); login('c0member')
            run('Wait For Elements State', '#new-page', 'hidden')
            run('Click', '#wiki-pages button:text-is(' + json.dumps(title) + ')')
            run('Get Property', '#wiki-body', 'readOnly', '==', True)
            run('Wait For Elements State', '#save-page', 'hidden')
            run('Wait For Elements State', '#claim-form', 'hidden')
            run('Click', '#wiki-history button:text-is("View revision 1")')
            run('Get Text', '#wiki-revision', 'contains', '# Authored browser content')
        except Exception as error:
            raise AssertionError('Disposable Wiki browser failed (' + type(error).__name__ + ')') from None
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
                browser.fill_text('input[name="username"]', username)
                browser.fill_text('input[name="password"]', self._browser_password)
                run('Click', '#kc-login')
                run('Wait For Elements State', '#sign-out', 'visible', 'timeout=30s')
                run('Go To', 'https://' + host + '/search')
                run('Wait For Elements State', '#search-workspace', 'visible', 'timeout=30s')
                run('Fill Text', '#knowledge-query', 'independent authored')
                run('Select Options By', '#knowledge-mode', 'value', 'hybrid')
                run('Select Options By', '#knowledge-rerank', 'value', 'filter')
                run('Click', '#knowledge-search-form button')
                run('Get Text', '#knowledge-search-status', 'contains', 'hybrid+filter')
                run('Get Element Count', '#knowledge-results article', '==', 1)
                run('Get Text', '#knowledge-results', 'contains', 'Independent authored claims')
                run('Get Text', '#knowledge-results', 'contains', '"revision_id"')
                run('Select Options By', '#knowledge-mode', 'value', 'text')
                run('Select Options By', '#knowledge-rerank', 'value', 'off')
                run('Click', '#knowledge-search-form button')
                run('Get Text', '#knowledge-search-status', 'contains', '· text ·')
                run('Reload')
                run('Wait For Elements State', '#search-workspace', 'visible', 'timeout=30s')
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
                run('New Context','ignoreHTTPSErrors=True');run('New Page')
                # Private URLs/passwords never enter Robot keyword arguments.
                browser.go_to(value['authorization_url'])
                run('Wait For Elements State','input[name="username"]','visible','timeout=30s')
                browser.fill_text('input[name="username"]','c0owner' if role=='admin' else 'c0member')
                browser.fill_text('input[name="password"]',self._browser_password)
                run('Click','#kc-login')
                run('Wait For Elements State','#approve','enabled','timeout=30s')
                run('Get Text','#client','==',value['client']['client_name'])
                run('Get Element Count','#client img','==',0)
                disabled={'admin':0,'editor':1,'reader':2}[role]
                run('Get Element Count','#scopes input:disabled','==',disabled)
                run('Get Element Count','#scopes input:checked','==',3-disabled)
                run('Click','#approve')
                run('Get Text','h1','==','C0 agent capabilities')
                # The callback query is private and validated by the host probe.
                value['returned_callback']=browser.get_url()
                with tempfile.TemporaryDirectory(prefix='czero-oauth-browser-') as directory:
                    path=Path(directory)/'request.json';path.write_text(json.dumps(value));path.chmod(0o600)
                    ssh.put_file(str(path),'/tmp/czero-oidc-fixture/browser-oauth.json',mode='0600')
                _, _, rc=ssh.execute_command('python3 /tmp/oauth_fixture.py '+shlex.quote(module_id)+
                    ' browser-complete',return_stderr=True,return_rc=True,timeout='300 seconds')
                if rc: raise AssertionError('Real OAuth browser/token assertions failed')
                run('Close Context')
            _, rc=ssh.execute_command('python3 /tmp/oidc_fixture.py check-logs '+shlex.quote(module_id),
                                     return_rc=True,timeout='180 seconds')
            if rc: raise AssertionError('OAuth browser logs contain private query values')
        except Exception as error:
            raise AssertionError('Disposable OAuth browser failed ('+type(error).__name__+')') from None
        finally:
            builtin.set_log_level(previous)

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
