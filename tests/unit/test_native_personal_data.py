# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_personal_data',ROOT/'imageroot/bin/czero_personal_data.py')
native=importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def test_disabled_default_and_dedicated_private_files(tmp_path):
    assert native.read(tmp_path)=={'enabled':False,'nethvoice':None,'webtop':None}
    native.private_write(tmp_path/'personal-data.json',{'enabled':True,'webtop':str(uuid4())})
    assert native.read(tmp_path)['enabled']
    assert (tmp_path/'personal-data.json').stat().st_mode & 0o077==0
    for value in ({'enabled':True},{'enabled':'true'},{'enabled':False,'token':'forbidden'}, {'enabled':True,'webtop':'mailbox'}):
        with pytest.raises(ValueError):native.validate(value)


def test_provider_identity_does_not_follow_a_domain_or_credential_string():
    first={'provider_ids':['directory-one.example.test:389'],'location':'external','schema':'rfc2307','base_dn':'dc=example,dc=test','bind_password':'synthetic-binding-one'}
    assert native.provider_binding(first)==native.provider_binding({**first,'bind_password':'synthetic-binding-two'})
    assert native.provider_binding(first)!=native.provider_binding({**first,'provider_ids':['directory-two.example.test:389']})
    with pytest.raises(ValueError):native.provider_binding(None)


def test_selection_checks_webtop_through_mail_and_distinguishes_mismatch():
    voice,webtop=map(str,(uuid4(),uuid4()))
    class Redis:
        values={
            'module/nethvoice1/environment':{'MODULE_UUID':voice,'USER_DOMAIN':'same','NETHCTI_UI_HOST':'voice.example.test'},
            'module/webtop1/environment':{'MODULE_UUID':webtop,'WEBTOP_HOSTNAME':'webtop.example.test','MAIL_MODULE':'mail1'},
            'module/mail1/environment':{'POSTFIX_ORIGIN':'other'}}
        def scan_iter(self,**kwargs):return iter(self.values)
        def hmget(self,key,fields):return [self.values[key].get(field) for field in fields]
        def hget(self,key,field):
            if key=='cluster/module_uuid':return {'nethvoice1':voice,'webtop1':webtop}.get(field)
            return self.values[key].get(field)
    class Proxy:
        def get_domain(self,name):return {'host':'one' if name=='same' else 'two','port':389,'schema':'rfc2307','base_dn':'dc=example'}
    domains={name:{'schema':'rfc2307','location':'external','base_dn':'dc=example','providers':[{'host':host,'port':389}]} for name,host in [('same','one'),('other','two')]}
    _,options=native.discover(Redis(),Proxy(),'same',domains=domains)
    assert [r['id'] for r in options['nethvoice']]==[voice]
    assert options['webtop']==[] and options['_mismatches']['webtop']==[webtop]


def test_native_credential_store_accepts_only_selected_dedicated_key(monkeypatch,tmp_path,capsys):
    import io,runpy,sys
    from types import SimpleNamespace
    instance=str(uuid4())
    native.private_write(tmp_path/'personal-data.json',{'enabled':True,'webtop':instance,'nethvoice':None})
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path))
    monkeypatch.setenv('AGENT_INSTALL_DIR',str(ROOT/'imageroot'))
    monkeypatch.setenv('CZERO_USER_DOMAIN','example.test')
    monkeypatch.setitem(sys.modules,'czero_personal_data',native)
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(redis_connect=lambda **k:None,set_status=lambda s:None))
    monkeypatch.setitem(sys.modules,'agent.ldapproxy',SimpleNamespace(Ldapproxy=lambda:None))
    monkeypatch.setitem(sys.modules,'agent.ldapclient',SimpleNamespace(Ldapclient=object))
    monkeypatch.setattr(native,'discover',lambda *args:('provider',{'webtop':[{'id':instance}],'nethvoice':[]}))
    key='abcdefgh_abcdefghijklmnopqrstuv'
    request={'connector':'webtop','instance_id':instance,'secret':key}
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps(request)))
    runpy.run_path(str(ROOT/'imageroot/actions/set-personal-data-credential/20save'))
    result=capsys.readouterr().out
    assert key not in result and json.loads(result)=={'saved':True,'verified':False,'revocation_pending':False}
    assert json.loads((tmp_path/'personal-data-secrets.json').read_text())['webtop'][instance]['api_key']==key
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps({**request,'secret':'a'*32})))
    with pytest.raises(SystemExit):runpy.run_path(str(ROOT/'imageroot/actions/set-personal-data-credential/20save'))
    assert 'a'*32 not in capsys.readouterr().out
    assert json.loads((tmp_path/'personal-data-secrets.json').read_text())['webtop'][instance]['api_key']==key


@pytest.mark.parametrize('mismatched_copy',[False,True])
def test_duplicate_restored_source_uuid_is_unavailable_not_first_match(mismatched_copy):
    identifier=str(uuid4())
    class Redis:
        def scan_iter(self,**kwargs):return iter(['module/voice1/environment','module/voice2/environment'])
        def hmget(self,key,fields):return [{'USER_DOMAIN':'other' if mismatched_copy and 'voice2' in key else 'same','NETHCTI_UI_HOST':'voice.example.test'}.get(x) for x in fields]
        def hget(self,key,field):return identifier
    domains={'same':{'schema':'rfc2307','location':'external','base_dn':'dc=example',
        'providers':[{'host':'directory.example.test','port':389}]}}
    domains['other']={**domains['same'],'base_dn':'dc=other'}
    _,options=native.discover(Redis(),None,'same',domains=domains)
    assert options['nethvoice']==[] and options['_mismatches']['nethvoice']==[]


def test_changed_login_issuer_cannot_adopt_previous_personal_registry():
    prior={'issuer':'https://old.example.test/realm','provider_id':str(uuid4())}
    assert native.identity_binding({'CZERO_OIDC_ISSUER':'https://new.example.test/realm'},prior)==(prior['issuer'],True)
    assert native.identity_binding({'CZERO_OIDC_ISSUER':prior['issuer']},prior)==(prior['issuer'],False)
    assert native.identity_binding({},prior)==(prior['issuer'],False)
    assert native.identity_binding({'CZERO_OIDC_ISSUER':prior['issuer']},{})==(prior['issuer'],False)


@pytest.mark.parametrize('was_enabled',[False,True])
def test_native_reconfiguration_fences_existing_imports_before_service_changes(monkeypatch,tmp_path,was_enabled):
    import io,runpy,sys,subprocess
    from types import SimpleNamespace
    instance=str(uuid4())
    previous={'enabled':was_enabled,'webtop':instance,'nethvoice':None}
    pending={**previous,'enabled':not was_enabled}
    native.private_write(tmp_path/'personal-data.json',previous)
    native.private_write(tmp_path/'personal-data-pending.json',pending)
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path));monkeypatch.setenv('AGENT_INSTALL_DIR',str(ROOT/'imageroot'))
    calls=[]
    monkeypatch.setitem(sys.modules,'czero_personal_data',native)
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(run_helper=lambda *a,**k:(calls.append(a) or SimpleNamespace(check_returncode=lambda:None))))
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:calls.append(a))
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps({'personal_data':pending})))
    runpy.run_path(str(ROOT/'imageroot/actions/configure-module/17fence-personal-data'))
    if was_enabled:
        assert calls==[(['systemctl','--user','start','czero-postgres.service'],),('czero-personal-data-run','--fence-only')]
    else:assert calls==[]  # First enable does not require a running predecessor DB.


def test_private_native_credentials_reject_symlinks_and_public_modes(tmp_path):
    path=tmp_path/'credentials.json';native.private_write(path,{'webtop':{}})
    assert native.private_read(path)=={'webtop':{}}
    link=tmp_path/'link.json';link.symlink_to(path)
    with pytest.raises(OSError):native.private_read(link)
    path.chmod(0o644)
    with pytest.raises(ValueError):native.private_read(path)
