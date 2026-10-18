# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parse the native add-module command's output without evaluating code."""
import ast
import json
import re
import shlex

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn


class CzeroActions:
    @keyword
    def verify_installed_candidate_images(self, module_id, source):
        if not re.fullmatch(r'czero[0-9]+', module_id):
            raise AssertionError('Invalid module identity')
        if not re.fullmatch(r'[0-9a-f]{40}', source):
            raise AssertionError('Invalid expected source')
        ssh = BuiltIn().get_library_instance('SSHLibrary')
        images = []
        for container in ('czero', 'czero-postgres'):
            code = ('import json,subprocess; '
                'c=json.loads(subprocess.check_output(["podman","container","inspect",'+repr(container)+']))[0]; '
                'i=json.loads(subprocess.check_output(["podman","image","inspect",c["Image"]]))[0]; '
                'print(json.dumps({"digest":i["Digest"],"revision":i["Labels"]["org.opencontainers.image.revision"]}))')
            output, rc = ssh.execute_command('runagent -m '+shlex.quote(module_id)+' python3 -c '+shlex.quote(code), return_rc=True)
            if rc:
                raise AssertionError('Installed candidate inspection failed')
            image = json.loads(output)
            if image['revision'] != source or not re.fullmatch(r'sha256:[0-9a-f]{64}', image['digest']):
                raise AssertionError('Installed candidate source mismatch')
            images.append(image)
        # Public image identities only; the artifact auditor compares actual
        # installed app/database digests against the verified registry records.
        BuiltIn().log_to_console('C0 installed candidates: '+json.dumps({'source': source, 'images': images}, sort_keys=True))

    @keyword
    def installed_module_id(self, output):
        # Core add-module prints result['output'] as a Python dict. api-cli
        # emits JSON; accept either representation for runner compatibility.
        try:
            result = json.loads(output)
        except json.JSONDecodeError:
            result = ast.literal_eval(output)
        if not isinstance(result, dict):
            raise AssertionError("Installation result must be a dictionary")
        module_id = result.get("module_id")
        if not isinstance(module_id, str) or not module_id.startswith("czero"):
            raise AssertionError("Installation did not return a Czero module id")
        return module_id
