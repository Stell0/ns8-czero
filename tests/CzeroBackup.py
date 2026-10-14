# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable backup setup; never return/log the generated encryption password."""
import json
import shlex
from pathlib import Path
from uuid import uuid4

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn


class CzeroBackup:
    @keyword
    def begin_disposable_backup_observer(self, module_id):
        ssh = BuiltIn().get_library_instance('SSHLibrary')
        ssh.put_file(str(Path(__file__).with_name('backup_observer.py')), '/tmp/czero-backup-observer.py', mode='0644')
        token = uuid4().hex
        background = 'python3 /tmp/czero-backup-observer.py observe ' + token + ' </dev/null >/dev/null 2>&1 &'
        _, rc = ssh.execute_command('runagent -m ' + shlex.quote(module_id) + ' sh -c ' + shlex.quote(background), return_rc=True, timeout='15 seconds')
        if rc: raise AssertionError('Cannot start disposable native backup observer')
        return token

    @keyword
    def verify_disposable_backup_observer(self, token):
        ssh = BuiltIn().get_library_instance('SSHLibrary')
        _, errors, rc = ssh.execute_command('python3 /tmp/czero-backup-observer.py verify ' + shlex.quote(token),
            return_stderr=True, return_rc=True, timeout='20 seconds')
        if rc:
            raise AssertionError('Disposable backup observation: ' + errors.strip())

    @keyword
    def create_disposable_backup(self, module_id, repository=None):
        builtin=BuiltIn()
        ssh=builtin.get_library_instance('SSHLibrary')
        previous=builtin.set_log_level('NONE')
        try:
            if repository is None:
                # Read only the public VPN address required by Core's cluster provider.
                address,rc=ssh.execute_command("runagent -m node python3 -c \"import agent,os; print(agent.redis_connect().hget('node/'+os.environ['NODE_ID']+'/vpn','ip_address'))\"",return_rc=True,timeout='180 seconds')
                if rc != 0: raise AssertionError('Cannot resolve disposable backup node')
                request={'provider':'cluster','name':'Czero disposable backup','url':'webdav:http://'+address.strip()+':4694','password':'','parameters':{}}
                output,rc=ssh.execute_command('api-cli run add-backup-repository --data '+shlex.quote(json.dumps(request)),return_rc=True,timeout='180 seconds')
                if rc != 0: raise AssertionError('Cannot create disposable backup destination')
                repository=json.loads(output)['id']
            request={'name':'Czero disposable backup','repository':repository,'schedule':'2099-01-01 00:00:00','retention':2,'instances':[module_id],'enabled':True}
            output,rc=ssh.execute_command('api-cli run add-backup --data '+shlex.quote(json.dumps(request)),return_rc=True,timeout='180 seconds')
            if rc != 0: raise AssertionError('Cannot create disposable backup schedule')
            backup_id=int(json.loads(output))
            output,rc=ssh.execute_command("runagent -m "+shlex.quote(module_id)+" python3 -c \"import os; print('czero/'+os.environ['MODULE_UUID'])\"",return_rc=True,timeout='180 seconds')
            if rc != 0: raise AssertionError('Cannot resolve disposable backup path')
            return {'repository':repository,'backup_id':backup_id,'path':output.strip()}
        finally:
            builtin.set_log_level(previous)

    @keyword
    def verify_disposable_snapshot(self, module_id, repository, path):
        builtin=BuiltIn()
        ssh=builtin.get_library_instance('SSHLibrary')
        code=("import agent,json,subprocess; r=agent.redis_connect(privileged=True,use_replica=True); "
              "p=agent.run_restic(r,"+repr(repository)+","+repr(path)+",[],['snapshots','--json'],text=True,stdout=subprocess.PIPE,check=True); "
              "assert json.loads(p.stdout), 'Native backup did not create a snapshot'")
        previous=builtin.set_log_level('NONE')
        try:
            _,rc=ssh.execute_command('runagent -m '+shlex.quote(module_id)+' python3 -c '+shlex.quote(code),return_rc=True,timeout='180 seconds')
            if rc != 0: raise AssertionError('Native backup snapshot was not verified')
        finally:
            builtin.set_log_level(previous)
