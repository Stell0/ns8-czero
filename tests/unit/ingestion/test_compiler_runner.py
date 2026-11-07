# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""External host bounds, calendar identity, recovery and credential isolation."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest

from c0_compiler import cli
from c0_compiler.config import load, private_file
from c0_compiler.runner import REQUIRED, Runner, due
from c0_ingest.errors import C0Error
from c0_ingest.state import read

ROOT = Path(__file__).resolve().parents[3]


def private(path, text):
    path.write_text(text)
    path.chmod(0o600)
    return str(path)


@pytest.fixture
def settings(tmp_path):
    tmp_path.chmod(0o700)
    value = json.loads((ROOT/'samples/ingestion/examples/compiler/config.json').read_text())
    value.update(c0_key_file=private(tmp_path/'c0.key', 'c0k_'+'x'*43),
                 model_key_file=private(tmp_path/'model.key', 'synthetic-provider-key'),
                 protocol_file=private(tmp_path/'compiler.md', 'Trusted compiler protocol.'),
                 state_dir=str(tmp_path/'state'))
    path=tmp_path/'config.json'
    private(path, json.dumps(value))
    return path, value


class Client:
    """Only host orchestration is faked here; actual Core/MCP is integration coverage."""
    def __init__(self, config, *, tasks=(), claim_outcome='claimed'):
        self.space_id=config['space_id']
        self.config=config
        self.operations={name:{'input_schema':{'type':'object','properties':{}}} for name in REQUIRED}
        self.calls=[]
        self.tasks={task['id']:deepcopy(task) for task in tasks}
        self.claim_outcome=claim_outcome
        self.run={'id':str(uuid4()),'revision':1,'policy_revision':1,'kind':'daily',
                  'cycle_key':'2026-11-07','state':'running','lease_owner':'fixture',
                  'data':{'task_ids':list(self.tasks),'calls':{}}}
        self.lease={'run_id':self.run['id'],'lease_owner':'fixture','fencing_generation':1}

    def call(self, name, **args):
        self.calls.append((name,deepcopy(args)))
        if name=='spaces_get':
            return {'id':self.space_id,'name':self.config['space_name'],'role':'editor','shared':False}
        if name=='compilation_policy_get':
            return {'space_id':self.space_id,'revision':1,'data':{'enabled':True,'timezone':self.config['timezone'],'request_seconds':60}}
        if name=='compilation_status_get':
            return {'tasks':{},'sources':{},'runs':[deepcopy(self.run)]}
        if name=='compilation_tasks_get':
            return deepcopy(self.tasks[args['task_id']])
        if name=='compilation_run_claim':
            self.run['revision']+=1
            data=args['data']['data']
            self.run.update(kind=data['kind'],cycle_key=data['cycle_key'],lease_owner=data['lease_owner'])
            return {'outcome':self.claim_outcome,'run':deepcopy(self.run),'lease':self.lease,
                    'tasks':[deepcopy(t) for t in self.tasks.values() if t['state'] in ('leased','planned','applied_pending_verify')]}
        if name=='compilation_discover':
            self.run['revision']+=1
            return {'outcome':'discovered','run':deepcopy(self.run),'tasks':[]}
        if name=='compilation_run_checkpoint':
            data=args['data']['data']; action=data['action']
            assert data['expected_revision']==self.run['revision']
            self.run['revision']+=1
            if action=='reserve_model':
                self.run['data']['calls'][data['request_id']]={'state':'reserved','task_id':data['task_id']}
            elif action=='start_model':
                self.run['data']['calls'][data['request_id']]['state']='started'
            elif action in ('return_model','reconcile_returned'):
                self.run['data']['calls'][data['request_id']].update(state='returned',
                    external_reference_hash=data['external_reference_hash'],observed_tokens=data['observed_tokens'])
            elif action=='uncertain_model':
                self.run['data']['calls'][data['request_id']]['state']='uncertain'
            elif action in ('partial','finish'):
                self.run['state']='complete' if action=='finish' else 'partial'
            elif action=='no_change':
                self.tasks[data['task_id']]['state']='no_change'
            return {'outcome':'completed_bounded' if action=='finish' else action,'run':deepcopy(self.run)}
        if name=='source_documents_get':
            return {'state':'ready','title':'Synthetic source','body':'SOURCE-BODY-MUST-STAY-TRANSIENT'}
        if name=='knowledge_search':
            return {'hits':[]}
        raise AssertionError('Unexpected operation '+name)

    @property
    def writes(self):
        return [call for call in self.calls if call[0] in ('compilation_run_claim','compilation_discover','compilation_run_checkpoint')]


def task(state='leased', **extra):
    return {'id':str(uuid4()),'revision':1,'state':state,'purpose':'knowledge','target':{},
            'source_bindings':[{'logical_document_id':str(uuid4()),'revision_id':str(uuid4()),'chunks':[]}],**extra}


def decision(**extra):
    return {'title':'Source-backed concept','synthesis':'SYNTHESIS-MUST-STAY-TRANSIENT',
            'classification':'supported_synthesis','citations':[],'topics':[],'no_change':True,**extra}


class Model:
    def __init__(self, response=None, callback=None):
        self.response=response or {'id':'resp_fixture','usage':{'total_tokens':30},'output':[
            {'type':'message','content':[{'type':'output_text','text':json.dumps(decision())}]}]}
        self.callback=callback
        self.calls=0

    def request(self, messages, schemas):
        self.calls+=1
        if self.callback: self.callback()
        return deepcopy(self.response)


@pytest.mark.parametrize('field', ['max_model_calls','max_output_tokens','max_input_bytes','timeout_seconds'])
def test_configuration_rejects_boolean_limits(settings,field):
    path,value=settings;value[field]=True;private(path,json.dumps(value))
    with pytest.raises(C0Error):load(path)


def test_private_configuration_and_protocol_are_required(settings):
    path,value=settings
    config=load(path)
    assert config['space_id']==value['space_id'] and config['binding_hash']
    path.chmod(0o644)
    with pytest.raises(C0Error,match='private_file_required'):load(path)
    path.chmod(0o600)
    Path(value['protocol_file']).chmod(0o644)
    with pytest.raises(C0Error,match='private_file_required'):load(path)


def test_private_file_rejects_symlinks_and_public_directory(tmp_path):
    tmp_path.chmod(0o700)
    path=Path(private(tmp_path/'secret','synthetic'))
    link=tmp_path/'linked';link.symlink_to(path)
    with pytest.raises(C0Error,match='private_file_required'):private_file(link)
    tmp_path.chmod(0o755)
    with pytest.raises(C0Error,match='private_file_required'):private_file(path)


def test_configuration_changes_preserve_and_block_existing_journal(settings):
    path,_=settings;config=load(path);client=Client(config)
    runner=Runner(client,config);runner.save()
    preserved=runner.path.read_bytes()
    with pytest.raises(C0Error,match='configuration_changed'):
        Runner(client,{**config,'binding_hash':'changed'})
    assert runner.path.read_bytes()==preserved


@pytest.mark.parametrize(('now','expected'),[
    ('2026-03-29T01:29:00+00:00','2026-03-28T01:30:00+00:00'),
    ('2026-03-29T01:31:00+00:00','2026-03-29T01:30:00+00:00'),
    ('2026-10-25T00:45:00+00:00','2026-10-25T00:30:00+00:00'),
    ('2026-10-25T01:45:00+00:00','2026-10-25T00:30:00+00:00'),
])
def test_calendar_reuses_gap_shift_and_first_fold(now,expected):
    config={'timezone':'Europe/Rome','daily_local_time':'02:30','weekly_local_time':'02:30','weekly_day':'sunday'}
    assert due(config,'daily',datetime.fromisoformat(now))==expected


def test_missed_weekly_ticks_coalesce_to_latest_local_occurrence():
    config={'timezone':'Europe/Rome','daily_local_time':'06:00','weekly_local_time':'07:00','weekly_day':'sunday'}
    assert due(config,'weekly',datetime(2026,11,18,10,tzinfo=timezone.utc))=='2026-11-15T06:00:00+00:00'


def test_complete_assessment_with_settled_children_can_finish(settings):
    path,_=settings;config=load(path)
    child=task('succeeded')
    parent=task('assessed',purpose='source_assessment',assessment={'child_task_ids':[child['id']]})
    client=Client(config,tasks=[parent,child]);runner=Runner(client,config)
    result=runner.execute('daily',apply=True)
    assert result['outcome']=='completed_bounded'
    assert client.writes[-1][1]['data']['data']['action']=='finish'


def test_completed_server_occurrence_is_recorded_and_second_tick_is_read_only(settings):
    path,_=settings;config=load(path);client=Client(config,claim_outcome='completed_bounded')
    now=datetime(2026,11,7,10,tzinfo=timezone.utc)
    first=Runner(client,config).execute('daily',apply=True,tick=True,now=now)
    assert first['outcome']=='completed_bounded'
    previous=len(client.writes)
    second=Runner(client,config).execute('daily',apply=True,tick=True,now=now)
    assert second['outcome']=='not_due' and len(client.writes)==previous


def test_model_invocation_is_reserved_started_and_journaled_before_call(settings):
    path,_=settings;config=load(path);selected=task();client=Client(config,tasks=[selected])
    runner=Runner(client,config)
    def check():
        saved=read(runner.path)
        assert saved['model']['state']=='started'
        actions=[a['data']['data']['action'] for name,a in client.calls if name=='compilation_run_checkpoint']
        assert actions[-2:]==['reserve_model','start_model']
    model=Model(callback=check);runner.model=model
    result=runner.execute('daily',apply=True)
    assert result['outcome']=='completed_bounded' and model.calls==1
    assert runner.path.stat().st_mode & 0o777 ==0o600
    contents=runner.path.read_text()
    assert 'SOURCE-BODY-MUST-STAY-TRANSIENT' not in contents
    assert 'SYNTHESIS-MUST-STAY-TRANSIENT' not in contents
    assert 'synthetic-provider-key' not in contents


def test_unknown_model_outcome_blocks_new_inference_and_all_writes(settings):
    path,_=settings;config=load(path);selected=task();client=Client(config,tasks=[selected])
    class Unknown:
        def request(self,*args):raise C0Error('model_outcome_uncertain')
    runner=Runner(client,config,Unknown())
    with pytest.raises(C0Error,match='model_outcome_uncertain'):runner.execute('daily',apply=True)
    previous=len(client.writes)
    model=Model()
    result=Runner(client,config,model).execute('daily',apply=True)
    assert result['outcome']=='reconcile_required'
    assert model.calls==0 and len(client.writes)==previous


@pytest.mark.parametrize('operation', ['compilation_policy_set','wiki_pages_upsert','knowledge_bundle_apply','run_shell'])
def test_model_cannot_dispatch_mutation_or_shell_tool(settings,operation):
    path,_=settings;config=load(path);selected=task();client=Client(config,tasks=[selected])
    response={'id':'resp_tool','usage':{'total_tokens':20},'output':[{'type':'function_call','name':'c0_read',
        'call_id':'call_fixture','arguments':json.dumps({'operation':operation,'arguments':'{}'})}]}
    runner=Runner(client,config,Model(response))
    with pytest.raises(C0Error,match='invalid_model_tool'):runner.execute('daily',apply=True)
    assert operation not in [name for name,_ in client.calls]


@pytest.mark.parametrize('operation,arguments',[
    ('source_documents_get',{'space_id':'00000000-0000-4000-8000-000000000099'}),
    ('knowledge_search',{'options':{'space_id':'00000000-0000-4000-8000-000000000099','query':'source'}}),
])
def test_model_read_rejects_wrong_explicit_space_without_fallback(settings,operation,arguments):
    path,_=settings;config=load(path);client=Client(config);runner=Runner(client,config)
    with pytest.raises(C0Error,match='wrong_space_selector'):runner.call(operation,arguments)
    assert client.calls==[]


def test_cli_never_echoes_configuration_or_credential_exception(monkeypatch,capsys,tmp_path):
    def fail(*args):raise RuntimeError('PRIVATE-CREDENTIAL-MUST-NOT-APPEAR')
    monkeypatch.setattr(cli,'load',fail)
    assert cli.main(['dry-run','--config',str(tmp_path/'private.json')])==1
    captured=capsys.readouterr()
    assert 'PRIVATE-CREDENTIAL-MUST-NOT-APPEAR' not in captured.out+captured.err
    assert json.loads(captured.out)['outcome']=='blocked_or_uncertain'


def test_missing_write_capabilities_stop_before_coordination_or_model(settings):
    path,_=settings;config=load(path);client=Client(config);model=Model()
    del client.operations['compilation_apply']
    with pytest.raises(C0Error,match='compiler_capabilities_unavailable'):
        Runner(client,config,model).execute('daily',apply=True)
    assert client.calls==[] and model.calls==0


def test_cli_overlap_stops_before_authentication_or_network(settings,monkeypatch,capsys):
    import fcntl
    import os
    path,_=settings;config=load(path)
    lock=Path(config['state_dir'])/'runner.lock'
    fd=os.open(lock,os.O_CREAT|os.O_RDWR,0o600)
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    calls=[]
    monkeypatch.setattr(cli,'C0',lambda *a,**k:calls.append(True))
    try:
        assert cli.main(['dry-run','--config',str(path)])==1
    finally:
        os.close(fd)
    assert calls==[]
    assert json.loads(capsys.readouterr().out)['outcome']=='blocked_or_uncertain'


def test_cli_cleanup_failure_never_exposes_credential_exception(settings,monkeypatch,capsys):
    from types import SimpleNamespace
    path,_=settings
    class BrokenClose:
        space_id='fixture'
        def __init__(self,*args):pass
        def close(self):raise RuntimeError('PRIVATE-CREDENTIAL-IN-CLOSE-MUST-NOT-APPEAR')
    monkeypatch.setattr(cli,'C0',BrokenClose)
    monkeypatch.setattr(cli,'Runner',lambda *args:SimpleNamespace(
        state={},inspect=lambda:{'status':{'tasks':{},'sources':{}}}))
    result=cli.main(['status','--config',str(path)])
    assert result in (0,1)
    captured=capsys.readouterr()
    assert 'PRIVATE-CREDENTIAL-IN-CLOSE-MUST-NOT-APPEAR' not in captured.out+captured.err


def test_configuration_schema_version_is_integer_not_boolean(settings):
    path,value=settings
    value['schema_version']=True
    private(path,json.dumps(value))
    with pytest.raises(C0Error,match='invalid_compiler_configuration'):load(path)


def test_private_file_rejects_symlink_parent_directory(tmp_path):
    tmp_path.chmod(0o700)
    real=tmp_path/'actual';real.mkdir(mode=0o700)
    private(real/'key','synthetic')
    link=tmp_path/'linked';link.symlink_to(real,target_is_directory=True)
    with pytest.raises(C0Error,match='private_file_required'):private_file(link/'key')


def test_missed_tick_before_desired_time_stays_partial_then_resumes_same_cycle(settings):
    path,value=settings
    value['daily_local_time']='08:00'
    private(path,json.dumps(value))
    config=load(path);client=Client(config)
    early=datetime(2026,11,7,6,tzinfo=timezone.utc)
    first=Runner(client,config).execute('daily',apply=True,tick=True,now=early)
    assert first['state']=='partial'
    assert client.writes[-1][1]['data']['data']['action']=='partial'
    previous=len(client.writes)
    second=Runner(client,config).execute('daily',apply=True,tick=True,
        now=datetime(2026,11,7,6,5,tzinfo=timezone.utc))
    assert second['outcome']=='not_due' and len(client.writes)==previous
    saved_id=client.run['id'];saved_calls=deepcopy(client.run['data']['calls'])
    actual_due=Runner(client,config).execute('daily',apply=True,tick=True,
        now=datetime(2026,11,7,8,1,tzinfo=timezone.utc))
    assert actual_due['state']=='complete' and actual_due['run_id']==saved_id
    assert client.run['data']['calls']==saved_calls
    claims=[args['data']['data'] for name,args in client.calls if name=='compilation_run_claim']
    assert len(claims)==2 and {claim['cycle_key'] for claim in claims}=={'2026-11-07'}


def test_imported_task_lost_apply_recovers_by_verifying_without_new_inference(settings,monkeypatch):
    from czero_core import compilation_client
    path,_=settings;config=load(path);selected=task();client=Client(config,tasks=[selected])
    first_model=Model();runner=Runner(client,config,first_model)
    # This task came from claim, before discovery. Its recovery identity must be
    # durable before the publication engine can commit and lose its reply.
    def lost_apply(task,decision,usage_id,apply):
        assert runner.state.get('task_id')==task['id']
        client.tasks[task['id']].update(state='applied_pending_verify',revision=2,
            publication={'plan_hash':'a'*64,'records':[{'kind':'page','id':str(uuid4())}]})
        runner.state['pending']={'operation':'compile_plan','key':'original-apply-key','fingerprint':'b'*64}
        runner.save()
        raise C0Error('lost_apply_response')
    monkeypatch.setattr(runner,'knowledge',lost_apply)
    with pytest.raises(C0Error,match='lost_apply_response'):
        runner.execute('manual',apply=True)
    assert first_model.calls==1
    observed=[]
    async def verify_saved(call,space,task_id,lease,expected_revision,*,idempotency_key):
        observed.append((space,task_id,lease,expected_revision,idempotency_key))
        assert client.tasks[task_id]['state']=='applied_pending_verify'
        client.tasks[task_id]['state']='succeeded'
        return {'outcome':'succeeded'}
    monkeypatch.setattr(compilation_client,'verify_pending',verify_saved)
    fresh_model=Model();recovering=Runner(client,config,fresh_model)
    result=recovering.recover()
    assert result=={'outcome':'succeeded','compiled':True}
    assert len(observed)==1 and observed[0][1]==selected['id']
    assert fresh_model.calls==0 and client.tasks[selected['id']]['state']=='succeeded'
    assert not any(name in ('compilation_apply','compilation_propose','compilation_discover') for name,_ in client.calls)
    assert 'pending' not in read(recovering.path) and 'recovery_of' not in read(recovering.path)


@pytest.mark.parametrize('operation,action',[
    ('compilation_propose',None),('compilation_assessment_complete',None),
    ('compilation_run_checkpoint','start_model'),('compilation_run_checkpoint','reserve_model'),
    ('compilation_run_checkpoint','finish'),
])
def test_old_model_receipt_cannot_clear_a_different_uncertain_write(settings,operation,action):
    path,_=settings;config=load(path);client=Client(config)
    old=str(uuid4())
    client.run['data']['calls'][old]={'state':'returned','task_id':None,'external_reference_hash':'a'*64}
    runner=Runner(client,config)
    pending={'operation':operation,'key':'preserve-this-uncertain-key','fingerprint':'b'*64}
    if action:pending.update(action=action,request_id=str(uuid4()))
    runner.state.update(run_id=client.run['id'],pending=pending,
        model={'state':'returned','request_id':old,'response_id':'resp_old',
               'external_reference_hash':'a'*64,'observed_tokens':73})
    runner.save()
    result=runner.recover()
    assert result['outcome']=='reconcile_required' and not result['compiled']
    assert client.writes==[] and read(runner.path)['pending']==pending


@pytest.mark.parametrize('matches',[True,False])
def test_return_model_recovery_requires_matching_pending_request_identity(settings,matches):
    path,_=settings;config=load(path);client=Client(config)
    request_id=str(uuid4())
    client.run['data']['calls'][request_id]={'state':'started','task_id':None}
    runner=Runner(client,config)
    pending={'operation':'compilation_run_checkpoint','action':'return_model',
        'request_id':request_id if matches else str(uuid4()),'key':'returned-checkpoint-key','fingerprint':'b'*64}
    runner.state.update(run_id=client.run['id'],pending=pending,
        model={'state':'returned','request_id':request_id,'response_id':'resp_actual',
               'external_reference_hash':'a'*64,'observed_tokens':73})
    runner.save()
    result=runner.recover()
    if matches:
        assert result['outcome']=='reconciled_pending_analysis'
        assert client.run['data']['calls'][request_id]['state']=='returned'
        assert 'pending' not in read(runner.path)
    else:
        assert result['outcome']=='reconcile_required'
        assert client.writes==[] and read(runner.path)['pending']==pending


def test_second_recovery_interruption_preserves_original_publication_intent(settings,monkeypatch):
    from czero_core import compilation_client
    path,_=settings;config=load(path)
    selected=task('applied_pending_verify',publication={'plan_hash':'a'*64,'records':[]})
    client=Client(config,tasks=[selected]);runner=Runner(client,config)
    original={'operation':'compile_plan','key':'original-apply-identity','fingerprint':'b'*64}
    runner.state.update(run_id=client.run['id'],task_id=selected['id'],pending=original)
    runner.save();calls=[]
    async def readback(call,space,task_id,lease,expected_revision,*,idempotency_key):
        saved=read(runner.path)
        assert saved['recovery_of']['key']==original['key']
        assert saved['pending']['operation']=='verify_pending'
        assert saved['pending']['key']==idempotency_key
        calls.append(task_id)
        if len(calls)==1:raise C0Error('interrupted_readback')
        client.tasks[task_id]['state']='succeeded'
        return {'outcome':'succeeded'}
    monkeypatch.setattr(compilation_client,'verify_pending',readback)
    with pytest.raises(C0Error,match='interrupted_readback'):runner.recover()
    assert read(runner.path)['recovery_of']==original
    recovered=Runner(client,config,Model()).recover()
    assert recovered=={'outcome':'succeeded','compiled':True}
    assert calls==[selected['id'],selected['id']]
    assert 'pending' not in read(runner.path) and 'recovery_of' not in read(runner.path)


def test_imported_pending_verification_saves_intent_before_core_readback(settings,monkeypatch):
    from czero_core import compilation_client
    path,_=settings;config=load(path)
    selected=task('applied_pending_verify',publication={'plan_hash':'a'*64,'records':[]})
    client=Client(config,tasks=[selected]);provider=Model();runner=Runner(client,config,provider)
    async def interrupted(call,space,task_id,lease,expected_revision,*,idempotency_key):
        saved=read(runner.path)
        assert saved['task_id']==selected['id']
        assert saved['pending']['operation']=='verify_pending'
        assert saved['pending']['key']==idempotency_key
        raise C0Error('readback_reply_lost')
    monkeypatch.setattr(compilation_client,'verify_pending',interrupted)
    with pytest.raises(C0Error,match='readback_reply_lost'):runner.execute('manual',apply=True)
    assert provider.calls==0
    assert read(runner.path)['pending']['operation']=='verify_pending'


def test_lost_initial_claim_replays_exact_key_and_cycle_without_model(settings,monkeypatch):
    path,_=settings;config=load(path);client=Client(config);provider=Model()
    runner=Runner(client,config,provider)
    original_call=client.call;committed={}
    def uncertain_claim(name,**args):
        if name=='compilation_run_claim':
            if not committed:
                result=original_call(name,**args)
                committed.update(arguments=deepcopy(args),result=deepcopy(result))
                saved=read(runner.path)
                assert saved['cycle']==args['data']['data']['cycle_key']
                assert saved['pending']['key']==args['data']['idempotency_key']
                raise C0Error('initial_claim_reply_lost')
            assert args==committed['arguments']
            client.calls.append((name,deepcopy(args)))
            return deepcopy(committed['result'])
        return original_call(name,**args)
    monkeypatch.setattr(client,'call',uncertain_claim)
    with pytest.raises(C0Error,match='initial_claim_reply_lost'):runner.execute('manual',apply=True)
    assert not runner.state.get('run_id')
    result=Runner(client,config,provider).recover()
    assert not result['compiled'] and provider.calls==0
    saved=read(runner.path)
    assert saved['run_id']==client.run['id'] and 'pending' not in saved
    assert len([name for name,_ in client.calls if name=='compilation_run_claim'])==2


@pytest.mark.parametrize('gate',['reader','disabled'])
def test_recovery_checks_current_editor_role_and_enabled_policy_before_write(settings,monkeypatch,gate):
    path,_=settings;config=load(path);client=Client(config)
    request_id=str(uuid4());client.run['data']['calls'][request_id]={'state':'started','task_id':None}
    runner=Runner(client,config)
    pending={'operation':'compilation_run_checkpoint','action':'return_model','request_id':request_id,
             'key':'authority-bound-key','fingerprint':'b'*64}
    runner.state.update(run_id=client.run['id'],pending=pending,
        model={'state':'returned','request_id':request_id,'response_id':'resp_known',
               'external_reference_hash':'a'*64,'observed_tokens':73})
    runner.save();original_call=client.call
    def restricted(name,**args):
        result=original_call(name,**args)
        if gate=='reader' and name=='spaces_get':result['role']='reader'
        if gate=='disabled' and name=='compilation_policy_get':result['data']['enabled']=False
        return result
    monkeypatch.setattr(client,'call',restricted)
    try:result=runner.recover()
    except C0Error:result={'compiled':False}
    assert not result['compiled'] and client.writes==[]
    assert read(runner.path)['pending']==pending


def test_bootstrap_three_children_use_successor_cycles_without_resetting_attempts_or_usage(settings):
    """Four successful stages must not exhaust one run's three-attempt ceiling."""
    path,_=settings;config=load(path)
    initial=task('queued',purpose='source_assessment',assessment={})
    initial['source_bindings'][0]['chunks']=[{'chunk_id':str(uuid4())}]
    chunk=initial['source_bindings'][0]['chunks'][0]['chunk_id']
    original='SOURCE-BODY-MUST-STAY-TRANSIENT'

    class BoundedServer(Client):
        # Model real coordinator semantics needed by this regression: terminal
        # tasks stay terminal, run attempts are capped, usage is space-wide.
        def __init__(self):
            super().__init__(config,tasks=[initial])
            self.runs={};self.requests=0
            self.operations['compilation_tasks_list']={'input_schema':{'type':'object','properties':{}}}
        def call(self,name,**args):
            if name=='compilation_run_claim':
                self.calls.append((name,deepcopy(args)))
                data=args['data']['data'];cycle=data['cycle_key']
                run=self.runs.get(cycle)
                if run and run['state']=='complete':
                    self.run=run
                    return {'outcome':'completed_bounded','run':deepcopy(run)}
                if run and run['attempts']>=3:
                    return {'outcome':'retry_exhausted','run':deepcopy(run)}
                if run is None:
                    run={'id':str(uuid4()),'revision':1,'attempts':0,'policy_revision':1,
                        'kind':data['kind'],'cycle_key':cycle,'state':'running','lease_owner':data['lease_owner'],
                        'data':{'task_ids':[],'calls':{}}}
                    self.runs[cycle]=run
                run['attempts']+=1;run['revision']+=1;run['state']='running'
                self.run=run
                self.lease={'run_id':run['id'],'lease_owner':data['lease_owner'],'fencing_generation':run['attempts']}
                pending=next((t for t in self.tasks.values() if t['state']=='queued'),None)
                if pending:
                    pending.update(state='leased',revision=pending['revision']+1,attempts=pending.get('attempts',0)+1)
                    run['data']['task_ids'].append(pending['id'])
                return {'outcome':'claimed','run':deepcopy(run),'lease':self.lease,
                    'tasks':[deepcopy(pending)] if pending else []}
            if name=='compilation_tasks_list':
                self.calls.append((name,deepcopy(args)))
                return {'tasks':[deepcopy(t) for t in self.tasks.values() if t['state']==args['state']],
                        'next_cursor':None}
            if name=='citations_get':
                self.calls.append((name,deepcopy(args)))
                return {'chunk_id':chunk,'body':original}
            if name=='compilation_source_bindings_get':
                self.calls.append((name,deepcopy(args)))
                return {'source_bindings':deepcopy(initial['source_bindings'])}
            if name=='compilation_propose':
                self.calls.append((name,deepcopy(args)))
                data=args['data']['data']
                child=task('queued',purpose='knowledge',topic_key=data['topic_key'],
                    source_bindings=deepcopy(data['source_bindings']),attempts=0)
                self.tasks[child['id']]=child
                return {'outcome':'queued','task':deepcopy(child)}
            if name=='compilation_assessment_complete':
                self.calls.append((name,deepcopy(args)))
                data=args['data']['data'];parent=self.tasks[data['task_id']]
                parent.update(state='assessed',revision=parent['revision']+1,
                    assessment={'child_task_ids':data['child_task_ids'],'review_complete':True,'findings':[]})
                self.run['revision']+=1
                return {'outcome':'assessment_partial','run':deepcopy(self.run),'task':deepcopy(parent)}
            if name=='compilation_run_checkpoint' and args['data']['data']['action']=='reserve_model':
                self.requests+=1
            return super().call(name,**args)

    class ThreeTopics(Model):
        def request(self,messages,schemas):
            packet=json.loads(messages[0]['content'])
            self.calls+=1
            value=decision()
            if packet['task']['purpose']=='source_assessment':
                value['no_change']=False
                value['topics']=[{'topic_key':'concept/'+str(index),'title':'Concept '+str(index),
                    'synthesis':'A supported navigation opportunity.','classification':'supported_synthesis',
                    'citations':[{'chunk_id':chunk,'quote':original}]} for index in range(3)]
            return {'id':'response-'+str(self.calls),'usage':{'total_tokens':50},'output':[
                {'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}

    server=BoundedServer();provider=ThreeTopics();results=[]
    for _ in range(4):
        results.append(Runner(server,config,provider).execute('bootstrap',apply=True))
    assert all(r['outcome']!='retry_exhausted' for r in results)
    children=[t for t in server.tasks.values() if t['purpose']=='knowledge']
    assert len(children)==3 and all(t['state']=='no_change' for t in children)
    assert all(t['attempts']==1 for t in children)
    assert server.tasks[initial['id']]['attempts']==1
    assert len({r['run_id'] for r in results})==4
    assert len(server.runs)==4 and all(run['attempts']==1 for run in server.runs.values())
    assert provider.calls==4 and server.requests==4
    calls=[call for run in server.runs.values() for call in run['data']['calls'].values()]
    assert len(calls)==4 and all(call['state']=='returned' for call in calls)
    assert all(not r['complete_corpus_coverage'] for r in results)


@pytest.mark.parametrize('configured,policy_seconds,expected',[(45,2,2),(1,60,1)])
def test_lazy_model_construction_uses_stricter_current_policy_deadline(settings,monkeypatch,configured,policy_seconds,expected):
    from c0_compiler import model
    path,value=settings;value['timeout_seconds']=configured;private(path,json.dumps(value))
    config=load(path);selected=task();client=Client(config,tasks=[selected])
    original_call=client.call
    def current_policy(name,**args):
        result=original_call(name,**args)
        if name=='compilation_policy_get':result['data']['request_seconds']=policy_seconds
        return result
    monkeypatch.setattr(client,'call',current_policy)
    received=[];provider=Model()
    def construct(bounded):
        received.append(bounded['timeout_seconds'])
        return provider
    monkeypatch.setattr(model,'Responses',construct)
    monkeypatch.setattr(model,'Codex',construct)
    result=Runner(client,config).execute('daily',apply=True)
    assert result['outcome']=='completed_bounded' and provider.calls==1
    assert received==[expected] and config['timeout_seconds']==configured


def test_private_state_symlink_ancestor_is_rejected_before_directory_or_journal_write(settings):
    path,value=settings
    actual=path.parent/'actual-state-parent';actual.mkdir(mode=0o700)
    linked=path.parent/'linked-state-parent';linked.symlink_to(actual,target_is_directory=True)
    value['state_dir']=str(linked/'new-private-state'/'job')
    private(path,json.dumps(value))
    with pytest.raises(C0Error,match='^private_state_directory_required$'):load(path)
    assert not (actual/'new-private-state').exists()
    assert list(actual.iterdir())==[]


@pytest.mark.parametrize('exception,expected_code',[
    (C0Error('model_outcome_uncertain_spawn'),'model_outcome_uncertain_spawn'),
    (C0Error('PRIVATE-UNKNOWN-ADAPTER-CREDENTIAL'),None),
    (RuntimeError('PRIVATE-UNKNOWN-TRANSPORT-CREDENTIAL'),None),
])
def test_model_error_journal_retains_only_closed_codes_and_never_exception_text(settings,exception,expected_code):
    path,_=settings;config=load(path);selected=task();client=Client(config,tasks=[selected])
    class Failed:
        def request(self,*args):raise exception
    runner=Runner(client,config,Failed())
    with pytest.raises(type(exception)):runner.execute('daily',apply=True)
    saved=read(runner.path)
    assert saved['model']['state']=='started'
    assert saved['model'].get('error_code')==expected_code
    assert 'PRIVATE-UNKNOWN-' not in runner.path.read_text()
    assert 'SOURCE-BODY-MUST-STAY-TRANSIENT' not in runner.path.read_text()
    before=len(client.writes);model=Model()
    repeated=Runner(client,config,model).execute('daily',apply=True)
    assert repeated['outcome']=='reconcile_required' and model.calls==0
    assert len(client.writes)==before
