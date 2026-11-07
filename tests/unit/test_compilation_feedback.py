# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""External episode handoff: answer delivery, closed inputs and bounded failures."""
import asyncio
from copy import deepcopy
from uuid import UUID

import pytest

from czero_core.compilation_client import FEEDBACK_TOOLS, feedback_after_answer
from czero_core.compilation_schema import defaults

ID=lambda n:str(UUID(int=n))
SPACE=ID(1)
BINDING={'logical_document_id':ID(2),'revision_id':ID(3),'content_hash':'a'*64,
    'text_hash':'b'*64,'metadata_hash':'c'*64,'parts_hash':'d'*64,'chunks':[
        {'chunk_id':ID(4),'source_id':ID(2),'version_id':ID(3),'document_id':ID(5),
         'content_hash':'e'*64,'source_hash':'a'*64,'start_offset':0,'end_offset':40}]}
OBSERVATION={'reason':'missing_concept','topic_key':'fixture/listener','source_label':'Orion listener',
    'selections':[{'logical_document_id':ID(2),'revision_id':ID(3),'chunk_ids':[ID(4)]}]}
TARGET={'kind':'page','id':ID(6),'revision':1,'content_id':ID(7),'content_hash':'f'*64}


class Connection:
    def __init__(self):
        self.calls=[];self.events=[]
        self.policy={'revision':1,'data':{**defaults(),'enabled':True,'retrieval_feedback':True}}
        self.tasks=[];self.hits=[];self.cursor=None;self.space_role='admin'
        self.failure=None;self.delay=None
        self.page={'id':TARGET['id'],'revision':1,'content':{'id':TARGET['content_id'],'content_hash':TARGET['content_hash'],'body':'Current authored text'}}
    async def __call__(self,name,arguments):
        self.events.append(name);self.calls.append((name,deepcopy(arguments)))
        if name==self.failure: raise RuntimeError('PRIVATE_EPISODE_MUST_NOT_ECHO')
        if name==self.delay: await asyncio.sleep(1)
        if name=='knowledge_search':
            assert arguments['options']['space_id']==SPACE
            assert arguments['options']['query']==OBSERVATION['source_label']
            assert arguments['options']['mode']=='text' and arguments['options']['rerank']=='off'
            return {'hits':self.hits}
        assert arguments['space_id']==SPACE
        if name=='spaces_get':return {'id':SPACE,'role':self.space_role}
        if name=='compilation_policy_get':return deepcopy(self.policy)
        if name=='compilation_source_bindings_get':return {'source_bindings':[deepcopy(BINDING)]}
        if name=='compilation_tasks_list':return {'tasks':deepcopy(self.tasks),'next_cursor':self.cursor}
        if name=='wiki_pages_get':return deepcopy(self.page)
        if name=='compilation_propose':
            proposal=arguments['data']['data']
            self.tasks=[{'id':ID(8),'purpose':'knowledge','revision':1,'state':
                'needs_review' if proposal['reason'] in ('contradiction','applicability_gap') else 'queued',
                'profile_id':self.policy['data']['profile_id'],'profile_version':1,
                'source_bindings':proposal['source_bindings'],'reason':proposal['reason'],
                'target':proposal['target'] or {},'origin':proposal['origin']}]
            return {'outcome':self.tasks[0]['state'],'task':deepcopy(self.tasks[0])}
        if name=='compilation_tasks_get':return deepcopy(self.tasks[0])
        raise AssertionError(name)


def run(connection,observation=OBSERVATION,**options):
    return asyncio.run(feedback_after_answer(connection,SPACE,deepcopy(observation),
        **{'answer_delivered':True,'operation_names':FEEDBACK_TOOLS,'idempotency_key':'opaque-fixture-key',**options}))


def test_no_signal_majority_and_explicit_read_only_have_zero_learning_io():
    connection=Connection()
    for _ in range(95):assert run(connection,None)['outcome']=='no_change'
    for options in ({'answer_delivered':False},{'answer_delivered':'yes'},{'read_only':True},
                    {'read_only':'false'},{'operation_names':FEEDBACK_TOOLS-{'compilation_propose'}}):
        assert run(connection,**options)['outcome']=='skipped'
    assert connection.calls==[]


@pytest.mark.parametrize('field',['enabled','retrieval_feedback'])
def test_disabled_policy_stops_before_source_context_or_any_write(field):
    connection=Connection();connection.policy['data'][field]=False
    assert run(connection)['reason']=='feedback_disabled'
    assert [n for n,_ in connection.calls]==['spaces_get','compilation_policy_get']


@pytest.mark.parametrize('mode',['queue_only','automatic_supported'])
def test_delivered_answer_precedes_bounded_proposal_and_actual_readback(mode):
    connection=Connection();connection.policy['data']['publication_mode']=mode
    connection.policy['data']['retrieval_model_requests']=0
    connection.events.append('answer-delivered')
    result=run(connection)
    assert result['outcome']=='proposed' and result['task_id']==ID(8) and result['compiled'] is False
    assert connection.events[0]=='answer-delivered' and len(connection.calls)==7
    assert [n for n,_ in connection.calls].count('compilation_propose')==1
    assert all(n in FEEDBACK_TOOLS for n,_ in connection.calls)
    assert connection.calls[-1][0]=='compilation_tasks_get'
    assert connection.tasks[0]['origin']=='retrieval'
    before=len(connection.calls)
    assert run(connection)['outcome']=='existing'
    assert len(connection.calls)-before==6
    assert [n for n,_ in connection.calls].count('compilation_propose')==1


def test_current_wiki_candidates_and_incomplete_task_comparison_defer():
    connection=Connection();connection.hits=[{'id':ID(6)}]
    assert run(connection)['reason']=='wiki_resolution_required'
    assert not connection.tasks
    connection=Connection();connection.cursor=ID(9)
    assert run(connection)['reason']=='task_comparison_incomplete'
    assert [n for n,_ in connection.calls]==['spaces_get','compilation_policy_get','compilation_source_bindings_get','compilation_tasks_list']


def test_target_identity_is_reread_and_authored_revision_drift_defers():
    connection=Connection();observation={**OBSERVATION,'target':TARGET,'reason':'incomplete_page'}
    assert run(connection,observation)['outcome']=='proposed'
    assert any(n=='wiki_pages_get' for n,_ in connection.calls)
    connection=Connection();connection.page['revision']=2
    assert run(connection,observation)['reason']=='target_changed'
    assert not connection.tasks


@pytest.mark.parametrize('extra',['query','answer','conversation','benchmark_label','prompt','operations'])
def test_private_episode_and_arbitrary_operations_are_rejected_before_io(extra):
    connection=Connection()
    result=run(connection,{**OBSERVATION,extra:'PRIVATE_EPISODE_MUST_NOT_ECHO'})
    assert result['outcome']=='deferred' and 'PRIVATE_EPISODE' not in str(result)
    assert connection.calls==[]


@pytest.mark.parametrize('name',['spaces_get','compilation_policy_get','compilation_source_bindings_get',
    'compilation_tasks_list','knowledge_search','compilation_propose','compilation_tasks_get'])
def test_failure_never_throws_or_leaks_private_text_and_does_not_retry(name):
    connection=Connection();connection.failure=name
    connection.events.append('answer-delivered')
    result=run(connection)
    assert result['outcome']==('uncertain' if name in ('compilation_propose','compilation_tasks_get') else 'deferred')
    assert 'PRIVATE_EPISODE' not in str(result) and result['compiled'] is False
    assert connection.events[0]=='answer-delivered'
    assert [n for n,_ in connection.calls].count('compilation_propose')<=1


def test_deadline_is_bounded_and_unknown_write_stays_uncertain():
    connection=Connection();connection.delay='compilation_policy_get'
    assert run(connection,timeout_seconds=.01)['outcome']=='deferred'
    connection=Connection();connection.delay='compilation_propose'
    assert run(connection,timeout_seconds=.01)['outcome']=='uncertain'
    assert [n for n,_ in connection.calls].count('compilation_propose')==1
    connection=Connection()
    assert run(connection,timeout_seconds=6)['outcome']=='deferred'
    assert connection.calls==[]


def test_unknown_success_response_is_uncertain_rather_than_a_capacity_receipt():
    connection=Connection()
    async def malformed(name,args):
        if name=='compilation_propose':return {'outcome':'unrecognized_response'}
        return await connection(name,args)
    result=run(malformed)
    assert result['outcome']=='uncertain' and result['compiled'] is False


def test_selected_space_reader_skips_even_with_global_editor_capabilities():
    connection=Connection();connection.space_role='reader'
    result=run(connection)
    assert result['outcome']=='skipped' and result['reason']=='space_not_writable'
    assert [n for n,_ in connection.calls]==['spaces_get']
