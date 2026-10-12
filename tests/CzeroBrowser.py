# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable-QEMU browser login without storing credentials in Robot logs."""
import hashlib
import json
import secrets

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
        # Hex/hash and JSON contain no single quotes. Only disposable QEMU uses
        # this helper; it never resets any existing administrator password.
        _, rc = ssh.execute_command(
            "api-cli run add-user --data '" + request + "'", return_rc=True
        )
        if rc != 0:
            raise AssertionError("Cannot create disposable browser administrator")
        previous_level = builtin.set_log_level("NONE")
        try:
            # Robot converts typed Browser arguments (states and timeouts).
            # Calling the Python keyword method directly skips that conversion.
            builtin.run_keyword("Browser.New Page", f"https://{node_addr}/cluster-admin/")
            builtin.run_keyword("Browser.Fill Text", 'text="Username"', username)
            builtin.run_keyword("Browser.Click", 'button >> text="Continue"')
            builtin.run_keyword("Browser.Fill Text", 'text="Password"', password)
            builtin.run_keyword("Browser.Click", 'button >> text="Log in"')
            builtin.run_keyword("Browser.Wait For Elements State", 'h2 >> text="Cluster status"', "visible", "timeout=30s")
        finally:
            builtin.set_log_level(previous_level)
