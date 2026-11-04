# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Native pool/configuration/backup proof, restricted to disposable modules."""
import json
from pathlib import Path
import re
import shlex

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from extraction_pool_evidence import validate_measurement,validate_reindex,operation_error


class CzeroExtraction:
    @keyword
    def verify_disposable_explicit_reindex(self,module_id):
        assert re.fullmatch(r'czero[0-9]+',module_id)
        builtin=BuiltIn();previous=builtin.set_log_level('NONE')
        try:
            ssh=builtin.get_library_instance('SSHLibrary')
            output,error,code=ssh.execute_command('api-cli run module/'+module_id+'/get-configuration',return_rc=True,return_stderr=True)
            assert code==0
            config=json.loads(output)
            assert config['host'].endswith('.test') and config['extraction']['enabled'] is True
            timer='runagent -m '+module_id+' systemctl --user '
            output,error,code=ssh.execute_command(timer+'is-active czero-extraction.timer',return_rc=True,return_stderr=True)
            assert code==0 and output.strip()=='active','Active disposable extraction timer required'
            try:
                # This fixed manual pool must not race the native timer's pool.
                output,error,code=ssh.execute_command(timer+'stop czero-extraction.timer czero-extraction.service',return_rc=True,return_stderr=True,timeout='180 seconds')
                assert code==0,operation_error('configure',None,error)
                for workers in (2,4):
                    command='runagent -m '+module_id+' podman exec -i --env=CZERO_DISPOSABLE_TEST=1 czero python - reindex '+str(workers)+' < /tmp/c0-combined-extraction-pool.py'
                    output,error,code=ssh.execute_command(command,return_rc=True,return_stderr=True,timeout='180 seconds')
                    assert code==0,operation_error('reindex',workers,error)
                    proof=json.loads(output)
                    validate_reindex(proof)
                    assert proof['workers']==workers
                    level=builtin.set_log_level('INFO')
                    try:
                        marker='C0 explicit reindex: '+json.dumps(proof,sort_keys=True)
                        builtin.log(marker);builtin.log_to_console(marker)
                    finally:builtin.set_log_level(level)
            finally:
                output,error,code=ssh.execute_command(timer+'start czero-extraction.timer',return_rc=True,return_stderr=True,timeout='180 seconds')
                assert code==0,operation_error('configure',None,error)
        finally:builtin.set_log_level(previous)

    @keyword
    def verify_disposable_extraction_pool(self,module_id,stage):
        assert re.fullmatch(r'czero[0-9]+',module_id) and stage in ('seed','verify')
        builtin=BuiltIn(); previous=builtin.set_log_level('NONE')
        try:
            ssh=builtin.get_library_instance('SSHLibrary')
            def run(command,phase,workers=None,timeout='180 seconds'):
                output,error,code=ssh.execute_command(command,return_rc=True,return_stderr=True,timeout=timeout)
                assert code==0,operation_error(phase,workers,error)
                return output
            config=json.loads(run('api-cli run module/'+module_id+'/get-configuration','configuration'))
            assert config['host'].endswith('.test'),'Disposable native hostname required'
            ssh.put_file(str(Path(__file__).with_name('extraction_pool_fixture.py')),'/tmp/c0-extraction-pool.py',mode='0644')
            ssh.put_file(str(Path(__file__).parent/'integration/ocr_original.py'),'/tmp/c0-ocr-original.py',mode='0644')
            run('cat /tmp/c0-ocr-original.py /tmp/c0-extraction-pool.py > /tmp/c0-combined-extraction-pool.py','prepare')
            command='runagent -m '+module_id+' podman exec -i --env=CZERO_DISPOSABLE_TEST=1 czero python - '
            for workers in (2,4):
                measurements={key:None for key in ('memory_peak_bytes','parser_peak_rss_bytes','memory_limit_bytes','swap_limit_bytes','pids_limit','duration_seconds')}
                if stage=='seed':
                    data={key:config[key] for key in ('host','lets_encrypt','user_domain','idp','owner')}
                    data['extraction']={'enabled':True,'workers':workers,'document_workers':workers,'space_workers':workers,'ocr_enabled':True,'ocr_language':'eng'}
                    run('api-cli run module/'+module_id+'/configure-module --data '+shlex.quote(json.dumps(data)),'configure',workers)
                    assert json.loads(run(command+'seed '+str(workers)+' < /tmp/c0-combined-extraction-pool.py','seed',workers))['units']==9
                    run('runagent -m '+module_id+' systemctl --user start czero-extraction.service','drain',workers)
                    log=run('runagent -m '+module_id+' journalctl --user -u czero-extraction.service -n 100 --no-pager -o cat','journal',workers)
                    assert not any(word in log for word in ('Synthetic pool page','SCANNED SAFETY','lease_token','CZERO_DATABASE_URL','password='))
                    reports=[]
                    for line in log.splitlines():
                        if line.startswith('{'):
                            try: reports.append(json.loads(line))
                            except ValueError: pass
                    accepted=[value for value in reports if value.get('processed')==9 and value.get('workers')==workers]
                    assert accepted,'Actual native parallel worker report required'
                    report=accepted[-1]; memory=workers*1073741824
                    assert report['cgroup_limit_bytes']==memory and report['cgroup_swap_limit_bytes']==memory
                    assert report['cgroup_pids_limit']==256 and 0<report['parser_peak_rss_bytes']<=536870912
                    assert report['cgroup_peak_bytes'] is None or 0<report['cgroup_peak_bytes']<=memory
                    measurements={'memory_peak_bytes':report['cgroup_peak_bytes'],'memory_limit_bytes':report['cgroup_limit_bytes'],
                        'parser_peak_rss_bytes':report['parser_peak_rss_bytes'],
                        'swap_limit_bytes':report['cgroup_swap_limit_bytes'],'pids_limit':report['cgroup_pids_limit'],
                        'duration_seconds':report['seconds']}
                else:
                    assert config['extraction']['enabled'] and config['extraction']['workers']==4
                    assert config['extraction']['ocr_enabled'] and config['extraction']['ocr_language']=='eng'
                assert json.loads(run(command+'verify '+str(workers)+' < /tmp/c0-combined-extraction-pool.py','verify',workers))=={'stage':'verify','workers':workers,'units':9,'verified':True}
                proof={'stage':stage,'workers':workers,'units':9,'body_hash_verified':True,'staging_cleared':True,
                    'ocr_pages':1,'ocr_text_verified':True,'native_limits_verified':stage=='seed','backup_readback':stage=='verify',**measurements}
                validate_measurement(proof)
                hidden=builtin.set_log_level('INFO')
                try:
                    marker='C0 extraction pool: '+json.dumps(proof,sort_keys=True)
                    builtin.log(marker); builtin.log_to_console(marker)
                finally: builtin.set_log_level(hidden)
        finally: builtin.set_log_level(previous)
