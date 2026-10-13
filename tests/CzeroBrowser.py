# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable-QEMU browser login without storing credentials in Robot logs."""
import hashlib
import json
from pathlib import Path
import secrets
import tempfile

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn


class CzeroBrowser:
    @keyword
    def login_to_disposable_cluster(self, node_addr):
        builtin = BuiltIn()
        ssh = builtin.get_library_instance("SSHLibrary")
        username = "czero-ci-" + secrets.token_hex(4)
        password = secrets.token_urlsafe(32)
        request = json.dumps({
            "user": username,
            "password_hash": hashlib.sha256(password.encode()).hexdigest(),
            "set": {},
            "grant": [{"role": "owner", "on": "*"}],
        })
        previous_level = builtin.set_log_level("NONE")
        try:
            with tempfile.TemporaryDirectory(prefix="czero-browser-") as directory:
                payload = Path(directory) / "user.json"
                payload.write_text(request)
                payload.chmod(0o600)
                ssh.put_file(str(payload), "/tmp/czero-browser-user.json", mode="0600")
            _, rc = ssh.execute_command(
                "api-cli run add-user --data=- < /tmp/czero-browser-user.json", return_rc=True
            )
            if rc != 0:
                raise AssertionError("Cannot create disposable browser administrator")
            self._password = password
            browser = builtin.get_library_instance("Browser")
            builtin.run_keyword("Browser.New Page", f"https://{node_addr}/cluster-admin/")
            # NONE suppresses messages but retains nested Robot keyword args.
            # Fill's arguments are plain strings; call the public library method
            # directly. Keep Robot conversion for typed states/timeouts below.
            browser.fill_text('text="Username"', username)
            builtin.run_keyword("Browser.Click", 'button >> text="Continue"')
            browser.fill_text('text="Password"', password)
            builtin.run_keyword("Browser.Click", 'button >> text="Log in"')
            builtin.run_keyword("Browser.Wait For Elements State", 'h2 >> text="Cluster status"', "visible", "timeout=30s")
        except Exception as error:
            # Underlying fill failures can include the typed value in call logs.
            raise AssertionError("Disposable browser login failed (" + type(error).__name__ + ")") from None
        finally:
            ssh.execute_command("rm -f /tmp/czero-browser-user.json", return_stdout=False)
            builtin.set_log_level(previous_level)

    @keyword
    def assert_disposable_browser_password_is_private(self):
        builtin = BuiltIn()
        output = Path(builtin.get_variable_value("${OUTPUT FILE}"))
        logs = [output, output.parent / "playwright-log.txt"]
        for path in logs:
            if path.exists() and self._password in path.read_text(errors="replace"):
                raise AssertionError("Temporary browser password entered test output")
