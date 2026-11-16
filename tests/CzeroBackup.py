# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable backup setup; never return/log the generated encryption password."""
import json
import shlex
from pathlib import Path
from uuid import uuid4

from personal_backup_evidence import validate as validate_personal_backup
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn


class CzeroBackup:
    @keyword
    def verify_disposable_personal_state(self,output):
        value=validate_personal_backup(json.loads(output))
        message='C0 personal backup: '+json.dumps(value,sort_keys=True)
        builtin=BuiltIn();builtin.log(message);builtin.log_to_console(message)

    def _personal_credentials(self, module_id, *, seed=False):
        # Generate in the disposable module; neither Robot nor argv gets a secret.
        code="""import hashlib,os,stat,sys,uuid,secrets
from pathlib import Path
sys.path.insert(0,str(Path(os.environ['AGENT_INSTALL_DIR'])/'bin'))
from czero_personal_data import private_read,private_write,read
p=Path(os.environ['AGENT_STATE_DIR'])/'personal-data-secrets.json'
"""
        if seed:
            code+="""assert not read()['enabled'], 'Only seed a disabled disposable collector'
assert not p.exists() or private_read(p)=={}, 'Preserve existing credentials'
private_write(p,{'webtop':{str(uuid.uuid4()):{'api_key':'synthetic-backup-'+secrets.token_urlsafe(32)}}})
"""
        code+="""value=private_read(p)
assert value.get('webtop') and stat.S_IMODE(p.stat().st_mode)==0o600
print(hashlib.sha256(p.read_bytes()).hexdigest())
"""
        builtin=BuiltIn();ssh=builtin.get_library_instance('SSHLibrary')
        previous=builtin.set_log_level('NONE')
        try:
            output,rc=ssh.execute_command('runagent -m '+shlex.quote(module_id)+' python3 -c '+shlex.quote(code),return_rc=True,timeout='30 seconds')
            if rc or len(output.strip())!=64 or any(c not in '0123456789abcdef' for c in output.strip()):
                raise AssertionError('Disposable personal credential file was not verified')
            return output.strip()
        finally:builtin.set_log_level(previous)

    @keyword
    def seed_disposable_personal_credentials(self,module_id):
        return self._personal_credentials(module_id,seed=True)

    @keyword
    def verify_disposable_personal_credentials(self,module_id,expected_hash):
        if self._personal_credentials(module_id)!=expected_hash:
            raise AssertionError('Native restore changed the private personal credential file')

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
