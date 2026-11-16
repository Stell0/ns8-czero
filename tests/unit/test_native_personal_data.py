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
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(redis_connect=lambda **k:None,set_status=lambda s:None,run_helper=lambda *a,**k:SimpleNamespace(check_returncode=lambda:None)))
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


@pytest.mark.parametrize('kind',['webtop','nethvoice'])
def test_clear_disconnected_credentials_needs_no_live_source_or_directory(monkeypatch,tmp_path,capsys,kind):
    import io,runpy,sys
    from types import SimpleNamespace
    old,new=map(str,(uuid4(),uuid4()))
    native.private_write(tmp_path/'personal-data.json',{'enabled':False,kind:new})
    first={'api_key':'synthetic-old-dedicated-key'} if kind=='webtop' else {'users':{str(uuid4()):'synthetic-old-user-session'}}
    other={'api_key':'synthetic-other-dedicated-key'} if kind=='webtop' else {'users':{str(uuid4()):'synthetic-other-user-session'}}
    native.private_write(tmp_path/'personal-data-secrets.json',{kind:{old:first,new:other}})
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path));monkeypatch.setenv('AGENT_INSTALL_DIR',str(ROOT/'imageroot'))
    def unavailable(*args,**kwargs):raise AssertionError('Clearing must not contact the disconnected source')
    monkeypatch.setitem(sys.modules,'czero_personal_data',native)
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(redis_connect=unavailable,set_status=lambda _:None,run_helper=lambda *a,**k:SimpleNamespace(check_returncode=lambda:None)))
    monkeypatch.setitem(sys.modules,'agent.ldapproxy',SimpleNamespace(Ldapproxy=unavailable))
    monkeypatch.setitem(sys.modules,'agent.ldapclient',SimpleNamespace(Ldapclient=object))
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps({'connector':kind,'instance_id':old,'clear':True})))
    runpy.run_path(str(ROOT/'imageroot/actions/set-personal-data-credential/20save'))
    result=json.loads(capsys.readouterr().out)
    assert result=={'saved':True,'verified':False,'revocation_pending':True}
    state=native.private_read(tmp_path/'personal-data-secrets.json')[kind]
    assert state[new]==other and state[old]['revocation_pending'] is True
    assert 'api_key' not in state[old] if kind=='webtop' else state[old]['users']=={}


def test_internal_directory_replica_endpoint_outage_preserves_registered_binding():
    identities={name:str(uuid4()) for name in ('directory1','directory2')}
    class Redis:
        def hget(self,key,field):return identities.get(field)
    configured={'location':'internal','schema':'rfc2307','base_dn':'dc=example,dc=test',
        'providers':[{'id':'directory1','host':'directory-one.example.test','port':636},
                     {'id':'directory2','host':'directory-two.example.test','port':636}]}
    unavailable={**configured,'providers':[configured['providers'][0],{'id':'directory2','host':None,'port':None}]}
    assert native.registered_binding(Redis(),{'directory':configured},'directory')==native.registered_binding(Redis(),{'directory':unavailable},'directory')
    identities.pop('directory2')
    with pytest.raises(ValueError):native.registered_binding(Redis(),{'directory':unavailable},'directory')


def test_concurrent_private_snapshots_are_complete_and_leave_no_staging_files(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path=tmp_path/'personal-data-status.json'
    def write(writer):
        for revision in range(10):native.private_write(path,{'writer':writer,'revision':revision,'body':'synthetic-value'*1000})
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(write,range(4)))
    value=native.private_read(path)
    assert value['writer'] in range(4) and value['revision']==9 and value['body']=='synthetic-value'*1000
    assert list(tmp_path.iterdir())==[path]


def test_failed_later_configuration_cannot_reenable_the_disconnected_source(monkeypatch,tmp_path):
    import io,runpy,sys,subprocess
    from types import SimpleNamespace
    old,new,kept=map(str,(uuid4(),uuid4(),uuid4()))
    previous={'enabled':True,'nethvoice':old,'webtop':kept}
    pending={**previous,'nethvoice':new}
    native.private_write(tmp_path/'personal-data.json',previous)
    native.private_write(tmp_path/'personal-data-pending.json',pending)
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path));monkeypatch.setenv('AGENT_INSTALL_DIR',str(ROOT/'imageroot'))
    monkeypatch.setitem(sys.modules,'czero_personal_data',native)
    calls=[]
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(run_helper=lambda *a,**k:(calls.append(a) or SimpleNamespace(check_returncode=lambda:None))))
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:None)
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps({'personal_data':pending})))
    runpy.run_path(str(ROOT/'imageroot/actions/configure-module/17fence-personal-data'))
    assert native.read(tmp_path)=={'enabled':True,'nethvoice':None,'webtop':kept}
    assert json.loads((tmp_path/'personal-data-pending.json').read_text())==pending
    assert calls==[('czero-personal-data-run','--fence-only')]


def test_post_read_owner_rechecks_immutable_id_and_disable_flags():
    identifier=uuid4()
    class Directory:
        attributes={'entryUUID':[str(identifier)]}
        def get_user_entry(self,name,**kwargs):return {'attributes':self.attributes}
    client=Directory()
    expected=native.directory_user(client,'rfc2307','person')
    message={'binding_check':True,'directory_id':str(identifier),'username':'person'}
    assert native.current_directory_owner(client,'rfc2307',[expected],message)
    client.attributes={'entryUUID':[str(uuid4())]}
    assert not native.current_directory_owner(client,'rfc2307',[expected],message)
    client.attributes={'entryUUID':[str(identifier)],'nsAccountLock':['true']}
    assert not native.current_directory_owner(client,'rfc2307',[expected],message)
    client.attributes={'entryUUID':[str(identifier)]}
    assert not native.current_directory_owner(client,'rfc2307',[],message)
    assert not native.current_directory_owner(client,'rfc2307',[expected],{**message,'username':'another'})
    assert not native.current_directory_owner(client,'rfc2307',[expected],{**message,'extra':'rejected'})


def test_native_directory_ad_uses_guid_byte_order():
    identifier=uuid4()
    class Directory:
        def get_user_entry(self,name,**kwargs):return {'attributes':{'objectGUID':[identifier.bytes_le],'userAccountControl':[514]}}
    assert native.directory_user(Directory(),'ad','person')=={'directory_id':str(identifier),'username':'person','active':False}


def test_inflight_credential_copy_cannot_follow_rotation_or_disconnect(tmp_path):
    path=tmp_path/'personal-data-secrets.json'
    assert native.credentials_unchanged(path,{})
    instance=str(uuid4())
    old={'webtop':{instance:{'api_key':'synthetic-dedicated-old'}}}
    native.private_write(path,old)
    assert native.credentials_unchanged(path,old)
    native.private_write(path,{'webtop':{instance:{'api_key':'synthetic-dedicated-new'}}})
    assert not native.credentials_unchanged(path,old)
    native.private_write(path,{'webtop':{instance:{'revocation_pending':True}}})
    assert not native.credentials_unchanged(path,old)
    path.unlink()
    assert not native.credentials_unchanged(path,old)


def test_disconnect_intent_precedes_fence_even_when_the_helper_fails(monkeypatch,tmp_path):
    import io,runpy,sys,subprocess
    from types import SimpleNamespace
    selected=str(uuid4())
    previous={'enabled':True,'nethvoice':selected,'webtop':None}
    pending={'enabled':False,'nethvoice':None,'webtop':None}
    native.private_write(tmp_path/'personal-data.json',previous)
    native.private_write(tmp_path/'personal-data-pending.json',pending)
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path));monkeypatch.setenv('AGENT_INSTALL_DIR',str(ROOT/'imageroot'))
    monkeypatch.setitem(sys.modules,'czero_personal_data',native)
    def helper(*args,**kwargs):
        assert native.read(tmp_path)==pending
        raise RuntimeError('synthetic fence failure')
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(run_helper=helper))
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:None)
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps({'personal_data':pending})))
    with pytest.raises(RuntimeError,match='synthetic fence failure'):
        runpy.run_path(str(ROOT/'imageroot/actions/configure-module/17fence-personal-data'))
    assert native.read(tmp_path)==pending


@pytest.mark.parametrize('action',['get-personal-data-status','get-personal-data-options'])
def test_read_actions_accept_the_native_clients_default_null_input(action):
    import jsonschema
    schema=json.loads((ROOT/'imageroot/actions'/action/'validate-input.json').read_text())
    # Both api-cli without arguments and the settings UI omit task data.
    jsonschema.validate(None,schema)
    jsonschema.validate({},schema)
    for value in ({'secret':'unexpected'},[],True,'invalid'):
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,schema)


def test_private_runner_protocol_bypasses_the_container_log_driver():
    runner=(ROOT/'imageroot/bin/czero-personal-data-run').read_text()
    # Podman's logger sees container stdout even when the client uses a private pipe.
    assert "command=['podman','run','--rm','--log-driver=none'" in runner
    assert "process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)" in runner
