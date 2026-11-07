# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual installed external CLI against disposable HTTPS, API keys and archives."""
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4
import zipfile

ROOT=Path(__file__).resolve().parents[2]


def test_installed_cli_checks_space_key_disabled_policy_and_revocation(live,browser,tmp_path):
    browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
    me=browser.request.get(live.origin+'/api/v1/me').json()
    headers={'Origin':live.origin,'X-C0-CSRF':me['csrf_token']}
    space=live.rest.post('/api/v1/spaces',json={'name':'Disposable external compiler',
        'idempotency_key':uuid4().hex}).json()
    created=browser.request.post(live.origin+'/api/v1/api-keys',headers=headers,data={
        'name':'External compiler fixture','scopes':['c0:read','c0:write'],'space_ids':[space['id']],'lifetime_days':1})
    assert created.status==201
    key=created.json()
    job=tmp_path/'private';job.mkdir(mode=0o700)
    (job/'c0.key').write_text(key['key']);(job/'c0.key').chmod(0o600)
    # Install the generated standalone archive and use its actual common protocol.
    # The loopback HTTPS fixture is not a deployable public package hostname.
    from czero_app.agent_packages import skill_payload,zip_bytes
    generated=zip_bytes(skill_payload('https://knowledge.example.org/mcp'))
    with zipfile.ZipFile(BytesIO(generated)) as archive:
        assert 'references/scheduling.md' in archive.namelist()
        protocol=archive.read('references/compiler.md')
    (job/'compiler.md').write_bytes(protocol);(job/'compiler.md').chmod(0o600)
    config=json.loads((ROOT/'samples/ingestion/examples/compiler/config.json').read_text())
    profile=live.rest.get('/api/v1/profile').json()
    assert profile['id']==me['id']
    config.update(url=live.origin+'/mcp',account_id=profile['id'],identity=profile['nickname'],
        space_id=space['id'],space_name=space['name'],c0_key_file=str(job/'c0.key'),
        state_dir=str(job/'state'),protocol_file=str(job/'compiler.md'))
    path=job/'config.json';path.write_text(json.dumps(config));path.chmod(0o600)
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','C0_API_KEY')}
    env['UV_CACHE_DIR']=str(tmp_path/'cache')
    # Trust the fixture alongside public package/provider roots in this client.
    import certifi
    bundle=job/'public-ca.pem'
    bundle.write_bytes((live.tmp/'tls.pem').read_bytes()+Path(certifi.where()).read_bytes())
    env['SSL_CERT_FILE']=str(bundle)
    def command(args,expected=0):
        result=subprocess.run([str(x) for x in args],cwd=job,env=env,capture_output=True,text=True,timeout=240)
        assert key['key'] not in result.stdout+result.stderr
        assert result.returncode==expected,(result.returncode,result.stdout,result.stderr)
        return result.stdout
    dist=tmp_path/'dist'
    for name,source in [('core',ROOT/'packages/czero-core'),('samples',ROOT/'samples/ingestion')]:
        copied=tmp_path/name
        shutil.copytree(source,copied,ignore=shutil.ignore_patterns('*.egg-info','__pycache__','build','.venv'))
        command(['uv','build','--wheel',str(copied),'--out-dir',dist])
    venv=job/'venv'
    command(['uv','venv',venv])
    command(['uv','pip','install','--python',venv/'bin/python',*sorted(dist.glob('*.whl'))])
    command([venv/'bin/python','-I','-c',
        'import c0_compiler,czero_core,sys;from pathlib import Path;'
        'assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (c0_compiler,czero_core))'])
    binary=venv/'bin/c0-compile'
    assert 'daily' in command([binary,'--help'])
    dry=json.loads(command([binary,'dry-run','--config',path]))
    assert dry['space_id']==space['id'] and dry['writes_c0']==0 and dry['model_calls']==0
    assert not dry['enabled'] and not dry['project_configured']
    disabled=json.loads(command([binary,'daily','--config',path,'--apply'],2))
    assert disabled=={'outcome':'disabled','compiled':False,'writes_c0':0}
    status=json.loads(command([binary,'status','--config',path]))
    assert status['outcome']=='inspected' and status['tasks']=={} and status['writes_c0']==0
    if os.getenv('C0_M5_LIVE_HOST_ACCEPTANCE'):
        # Explicit manual acceptance only: owned transient user timers, disposable
        # space/API key/model inputs. Normal CI never needs a provider login.
        from datetime import datetime, timedelta, timezone
        import time
        from czero_core.compilation_schema import defaults
        version=live.rest.post('/api/v1/sources/ingest-text',params={'space_id':space['id']},json={
            'title':'Synthetic listener procedure','body':'Orion 2 listens on TCP port 7443. Clients must validate the server certificate. This procedure applies to Orion version 2.',
            'idempotency_key':'host-original'}).json()
        limit=time.monotonic()+40
        while time.monotonic()<limit:
            document=live.rest.get('/api/v1/source-documents/'+version['source_id'],params={'space_id':space['id']}).json()
            if document.get('state')=='ready': break
            time.sleep(.2)
        assert document.get('state')=='ready'
        enabled=live.rest.put('/api/v1/compilation/policy',params={'space_id':space['id']},json={
            'data':{**defaults(),'enabled':True,'publication_mode':'automatic_supported',
                'daily_model_tokens':10000000,'weekly_model_tokens':10000000},'expected_revision':0,
            'authorization_ref':'synthetic:disposable-host-acceptance','idempotency_key':'host-policy'})
        assert enabled.status_code==200
        now=datetime.now(timezone.utc);past=now-timedelta(minutes=1)
        config.update(daily_local_time=past.strftime('%H:%M'),weekly_local_time=past.strftime('%H:%M'),
            weekly_day=now.strftime('%A').lower(),timeout_seconds=60,c0_key_file='credential:c0-key')
        path.write_text(json.dumps(config));path.chmod(0o600)
        def due_run(kind):
            unit='c0-m5-disposable-'+uuid4().hex
            try:
                command(['systemd-run','--user','--collect','--unit',unit,'--on-active=2s',
                    '--timer-property=AccuracySec=100ms','--property=LoadCredential=c0-key:'+str(job/'c0.key'),
                    '--setenv=SSL_CERT_FILE='+str(bundle),
                    '--setenv=PYTHONPATH=','--setenv=PATH='+os.environ['PATH'],
                    binary,kind,'--config',path,'--apply','--tick'])
                stop=time.monotonic()+210
                while time.monotonic()<stop:
                    result=subprocess.run(['journalctl','--user','-u',unit+'.service','-o','cat','--no-pager'],
                        env=env,capture_output=True,text=True,timeout=10)
                    for line in result.stdout.splitlines():
                        try: value=json.loads(line)
                        except ValueError: continue
                        if type(value) is dict and 'outcome' in value:
                            assert key['key'] not in line
                            return {'unit':unit,'result':value}
                    time.sleep(.5)
                raise AssertionError('Transient due runner did not produce a verifiable result')
            finally:
                subprocess.run(['systemctl','--user','stop',unit+'.timer',unit+'.service'],capture_output=True,timeout=15)
                subprocess.run(['systemctl','--user','reset-failed',unit+'.service'],capture_output=True,timeout=15)
        observations=[due_run('daily'),due_run('daily'),due_run('weekly')]
        (job/'host-observed.json').write_text(json.dumps(observations));(job/'host-observed.json').chmod(0o600)
        assert observations[0]['result']['state']=='partial'
        assert observations[1]['result']['compiled'] is True
        assert observations[2]['result']['state']=='complete'
        response=live.rest.get('/api/v1/compilation/status',params={'space_id':space['id']},
            headers={'Authorization':'Bearer '+key['key']})
        assert response.status_code==200
        saved=response.json()
        assert saved['tasks']['succeeded']>=1 and not saved['complete_corpus_coverage']
        (job/'verified-status.json').write_text(json.dumps(saved));(job/'verified-status.json').chmod(0o600)
    # The disposable provider's native token expires after five minutes; renew
    # the browser through its real login before the long host test's revocation.
    if os.getenv('C0_M5_LIVE_HOST_ACCEPTANCE'):
        browser.context.clear_cookies();browser.goto(live.origin+'/auth/login')
        me=browser.request.get(live.origin+'/api/v1/me').json()
        headers={'Origin':live.origin,'X-C0-CSRF':me['csrf_token']}
    revoked=browser.request.delete(live.origin+'/api/v1/api-keys/'+key['id'],headers=headers)
    assert revoked.status==204
    denied=json.loads(command([binary,'dry-run','--config',path],1))
    assert denied['outcome']=='blocked_or_uncertain'
