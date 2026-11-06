# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult,TextContent

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
from agentic_retrieval.protocol import (Budget,body_hash,digest,episode_input,grade,partition,
                                       summary,validate_corpus,validate_questions)
from agentic_retrieval.layer import maintain,validate_plan,verify
from agentic_retrieval.runner import ReadBoundary,accepted
from evaluation.codex_driver import RunnerFailure,evaluate
from test_tool_evaluation import fake_codex


def fixture():
    body='Orion 2 uses port 7443.'
    c={'source_id':'s','version_id':'v','document_id':'d','chunk_id':'c',
        'content_hash':body_hash(body),'source_hash':'sh','start_offset':0,'end_offset':len(body),'body':body}
    d={'id':'s','url':'https://docs.example.test/2','generation':'v','content_hash':body_hash(body),
        'body':body,'product':'Orion','version':'2','language':'en','chunks':[c]}
    e={'document_id':'s','url':d['url'],'generation':'v','content_hash':d['content_hash'],'quote':'port 7443'}
    q={'id':'question-a','text':'Which port is used?','language':'en','type':'configuration',
        'answerability':'answerable','products':['Orion'],'versions':['2'],'evidence_sets':[[[e]]],
        'provenance':'provisional analyst fixture','confidence':'high','uncertainty':''}
    r={'key':'connection','title':'Orion connection','synthesis':'See original connection settings.',
       'classification':'extracted','evidence':[{k:v for k,v in e.items() if k!='url'}|{'chunk_id':'c'}]}
    return [d],q,{'namespace':'test-layer','records':[r]}


def test_quotes_hashes_generation_and_alternative_complete_sets():
    corpus,q,_=fixture();validate_corpus(corpus);validate_questions([q],corpus)
    q['evidence_sets'].append(q['evidence_sets'][0]);validate_questions([q],corpus)
    for k,v in [('generation','old'),('content_hash','wrong'),('quote','not in body')]:
        bad=deepcopy(q);bad['evidence_sets'][0][0][0][k]=v
        with pytest.raises(ValueError):validate_questions([bad],corpus)
    bad=deepcopy(corpus);bad[0]['body']='changed'
    with pytest.raises(ValueError):validate_corpus(bad)


def test_sealed_partition_projection_has_no_gold_or_other_questions():
    corpus,q,_=fixture()
    qs=[dict(q,id='question-'+str(i),text='Question '+str(i)) for i in range(12)]
    first=partition(qs,'fixed');assert first==partition(qs,'fixed')
    assert {v['split'] for v in first}=={'development','validation','sealed'}
    prompt=episode_input(first[-1],'space')
    assert first[-1]['text'] in prompt and 'evidence_sets' not in prompt
    assert first[-1]['id'] not in prompt and first[0]['text'] not in prompt


def call(citation):
    return {'name':'sources_search','arguments':{'space_id':'space','query':'Orion'},
            'result':{'structuredContent':{'citations':[citation]}}}


def test_hand_computable_multi_document_metrics_duplicates_and_missing_results():
    corpus,q,_=fixture();c=corpus[0]['chunks'][0]
    other=deepcopy(corpus[0]);other['id']='s2';other['url']+='other'
    other['generation']='v2'
    other['chunks'][0]|={'source_id':'s2','chunk_id':'c2','version_id':'v2','document_id':'d2'};corpus.append(other)
    e=deepcopy(q['evidence_sets'][0][0][0]);e|={'document_id':'s2','url':other['url'],'generation':'v2'}
    q['evidence_sets'][0].append([e])
    final={'outcome':'completed','citations':[{k:v for k,v in c.items() if k!='body'}]}
    result=grade(q,final,[call(c),call(c)],corpus)
    assert result['complete_evidence'] is False and result['passage_coverage']==.5
    assert result['rankings']['hit_at_1']==1 and result['rankings']['recall_at_5']==.5
    assert result['rankings']['mrr_at_10']==1
    assert grade(q,final,[],corpus)['invalid_citations']==1
    c2=other['chunks'][0];final['citations'].append({k:v for k,v in c2.items() if k!='body'})
    assert grade(q,final,[call(c),call(c2)],corpus)['complete_evidence'] is True
    q['evidence_sets'].append([[e]])
    final['citations']=final['citations'][1:]
    assert grade(q,final,[call(c2)],corpus)['complete_evidence'] is True


def test_unanswerable_recall_and_disposition_separate():
    corpus,q,_=fixture();q|={'answerability':'unanswerable','evidence_sets':[]}
    result=grade(q,{'outcome':'completed','citations':[]},[],corpus)
    assert result['complete_evidence'] is None and not result['disposition_correct']
    assert result['rankings']['recall_at_10'] is None


def test_boundary_enforces_actual_readonly_annotation_and_space():
    seen=[]
    class Client:
        async def call_tool(self,n,a):
            seen.append(n);return CallToolResult(content=[TextContent(type='text',text='permission_denied')],is_error=True)
    tool=SimpleNamespace(name='read',annotations=SimpleNamespace(read_only_hint=True))
    boundary=ReadBoundary(Client(),[tool],'space')
    for name,args in [('write',{'space_id':'space'}),('read',{}),('read',{'space_id':'other'})]:
        with pytest.raises(RunnerFailure):asyncio.run(boundary.call(name,args))
    asyncio.run(boundary.call('read',{'space_id':'space'}))
    with pytest.raises(RunnerFailure):asyncio.run(boundary.call('read',{'space_id':'space'}))
    assert seen==['read']


def test_budget_exhaustion_resume_and_uncertain_attempt(tmp_path):
    limits={'sessions':2,'tokens':100,'seconds':5,'episode_tokens':60}
    p=tmp_path/'ledger.json';b=Budget(p,limits);assert b.reserve('a')
    with pytest.raises(RuntimeError,match='uncertain'):Budget(p,limits).reserve('a')
    b.finish('a',{},'runner_failure');assert not Budget(p,limits).reserve('a')
    assert b.reserve('b');b.finish('b',{},'runner_failure')
    with pytest.raises(RuntimeError,match='budget'):b.reserve('c')
    assert b.state['tokens']==120


def test_benchmark_material_and_unknown_profile_fields_rejected():
    corpus,q,plan=fixture();validate_plan(plan,corpus,[q['id'],q['text']])
    for key,value in [('synthesis',q['text']),('question_id','question-a')]:
        bad=deepcopy(plan);bad['records'][0][key]=value
        with pytest.raises(ValueError):validate_plan(bad,corpus,[q['id'],q['text']])
    bad=deepcopy(plan);bad['records'][0]['evidence'][0]['generation']='old'
    with pytest.raises(ValueError,match='stale'):validate_plan(bad,corpus)


class LayerAPI:
    def __init__(self):self.pages={};self.annotations={};self.writes=0;self.lose=False;self.receipts={}
    async def __call__(self,name,args):
        if name=='wiki_pages_upsert':
            self.writes+=1;data=args['data'];key=data['idempotency_key']
            if key in self.receipts:return self.receipts[key]
            page={'id':'page','revision':len(self.pages)+1,'content':{'id':'revision',**data}}
            self.pages['page']=page;self.receipts[key]=deepcopy(page)
            if self.lose:self.lose=False;raise ConnectionError('committed reply lost')
            return page
        if name=='wiki_pages_get':return self.pages[args['page_id']]
        if name=='knowledge_annotations_get':return {'revision':int(bool(self.annotations)),'value':self.annotations or None}
        if name=='knowledge_annotations_update':self.writes+=1;self.annotations=args['data']['value'];return {}
        if name=='citations_get':return fixture()[0][0]['chunks'][0]
        raise AssertionError(name)


def test_managed_identity_idempotency_uncertain_replay_and_authored_conflict(tmp_path):
    corpus,q,plan=fixture();api=LayerAPI();state=tmp_path/'state.json'
    async def check():
        dry=await maintain(api,'space',corpus,plan,state)
        assert not state.exists() and api.writes==0 and dry['records'][0]['action']=='create'
        api.lose=True
        with pytest.raises(ConnectionError):await maintain(api,'space',corpus,plan,state,apply=True)
        assert json.loads(state.read_text())['pending']
        await maintain(api,'space',corpus,plan,state,apply=True)
        writes=api.writes
        await maintain(api,'space',corpus,plan,state,apply=True)
        assert api.writes==writes and len(api.pages)==1
        await verify(api,'space',corpus,plan,state)
        api.pages['page']['content']['body']='authored change'
        with pytest.raises(RuntimeError,match='authored'):await maintain(api,'space',corpus,plan,state,apply=True)
    asyncio.run(check())


def test_managed_rerun_preserves_authored_verification(tmp_path):
    corpus,q,plan=fixture();api=LayerAPI();state=tmp_path/'state.json'
    async def check():
        await maintain(api,'space',corpus,plan,state,apply=True)
        authored={'status':'verified','source_references':[], 'extensions':{'reviewer':'Alice'}}
        api.annotations=deepcopy(authored);writes=api.writes
        with pytest.raises(RuntimeError,match='annotation_edit'):
            await maintain(api,'space',corpus,plan,state,apply=True)
        assert api.annotations==authored and api.writes==writes
    asyncio.run(check())


def test_managed_rerun_with_multiple_quotes_from_one_chunk(tmp_path):
    from czero_core.annotations import annotation_value
    corpus,_,plan=fixture();state=tmp_path/'state.json'
    chunk_id='00000000-0000-4000-8000-000000000001'
    corpus[0]['chunks'][0]['chunk_id']=chunk_id
    evidence=plan['records'][0]['evidence'];evidence[0]['chunk_id']=chunk_id
    evidence.append({**evidence[0],'quote':'Orion 2'})

    class CanonicalAPI(LayerAPI):
        async def __call__(self,name,args):
            if name=='knowledge_annotations_update':
                args=deepcopy(args)
                args['data']['value']=annotation_value('verification',args['data']['value'])
            return await super().__call__(name,args)

    api=CanonicalAPI()
    async def check():
        await maintain(api,'space',corpus,plan,state,apply=True)
        before=deepcopy(api.pages);writes=api.writes
        assert len(api.pages['page']['content']['metadata']['source_bindings'])==2
        assert api.annotations['source_references']==[{'kind':'chunk','id':chunk_id}]
        result=await maintain(api,'space',corpus,plan,state,apply=True)
        assert result['records'][0]['action']=='unchanged'
        assert api.writes==writes and api.pages==before
    asyncio.run(check())


@pytest.mark.parametrize('limit,kwargs,match',[
    ('model',{'require_model':True},'model'),('context',{'max_context_bytes':1},'context'),
    ('calls',{'max_calls':0},'call budget')])
def test_driver_missing_model_and_hard_budgets_fail_closed(tmp_path,monkeypatch,limit,kwargs,match):
    monkeypatch.setenv('CODEX_HOME',str(tmp_path/'no-config'))
    tool=SimpleNamespace(name='actual_probe',description='Synthetic',input_schema={'type':'object'})
    async def actual(n,a):return CallToolResult(content=[])
    with pytest.raises(RunnerFailure,match=match):
        asyncio.run(evaluate(tools=[tool],instructions='Test',prompt='Probe',call_tool=actual,
            output=tmp_path/'episode',codex=str(fake_codex(tmp_path,'success')),timeout=10,**kwargs))


def test_builder_schema_constrains_logical_identity_counts_and_label_groups():
    from agentic_retrieval.builders import output_schema
    from jsonschema import validate,ValidationError
    corpus,q,plan=fixture()
    validate(plan,output_schema('layer',corpus,3,'test-layer'))
    invalid=deepcopy(plan);invalid['records'][0]['evidence'][0]['document_id']='physical-id'
    with pytest.raises(ValidationError):validate(invalid,output_schema('layer',corpus,3,'test-layer'))
    schema=output_schema('questions',corpus,12,'test-layer')
    assert schema['properties']['answerable']['maxItems']==6
    assert schema['properties']['ambiguous']['minItems']==3
    with pytest.raises(ValidationError):validate({'answerable':[],'ambiguous':[],'unanswerable':[]},schema)


def test_comparison_targets_reject_missing_controls():
    base={'runner_failures':0,'complete_evidence':{'mean':.5},'calls':{'p50':3,'n':1,'mean':3},
          'invalid_citations':0,'product_version_errors':0,'ambiguous':{'n':1,'mean':1},
          'unanswerable':{'n':0,'mean':None},'elapsed_seconds':{'p95':20}}
    candidate=deepcopy(base);candidate['complete_evidence']['mean']=1
    assert 'unanswerable' in accepted(base,candidate,{'complete':.8,'improvement':.1,'disposition':.8,'p95_seconds':180})


def test_derived_metadata_cannot_impersonate_an_original_evidence_read():
    corpus,q,_=fixture();c=corpus[0]['chunks'][0]
    forged={'name':'wiki_pages_get','arguments':{'space_id':'space','page_id':'page'},
        'result':{'structuredContent':{'content':{'metadata':{'citation':c}}}}}
    final={'outcome':'completed','citations':[{k:v for k,v in c.items() if k!='body'}]}
    assert grade(q,final,[forged],corpus)['invalid_citations']==1


def test_labels_freeze_only_after_hash_bound_audit_and_exposed_questions_stay_development():
    from agentic_retrieval.protocol import freeze_labels
    corpus,q,plan=fixture();proposal={'corpus_hash':digest(corpus),'questions_hash':digest([q]),'plan_hash':digest(plan)}
    with pytest.raises(ValueError,match='audit'):freeze_labels(corpus,[q],[q],{},'protocol',digest(plan))
    audit={'proposal_hash':digest(proposal),'reviewed_questions_hash':digest([q]),'approved_for_pilot':True,
           'audit':[{'id':q['id'],'provenance':'provisional analyst read original'}]}
    questions,frozen=freeze_labels(corpus,[q],[q],audit,'protocol',digest(plan))
    assert frozen['questions']==digest(questions)
    revised=[{**q,'previously_exposed':True}];audit['reviewed_questions_hash']=digest(revised)
    questions,_=freeze_labels(corpus,[q],revised,audit,'protocol',digest(plan))
    assert questions[0]['split']=='development'
    audit['reviewed_questions_hash']='tampered'
    with pytest.raises(ValueError):freeze_labels(corpus,[q],revised,audit,'protocol',digest(plan))


def test_wiki_hits_without_original_citations_do_not_break_or_earn_evidence_credit():
    corpus,q,_=fixture();c=corpus[0]['chunks'][0]
    calls=[{'name':'knowledge_search','arguments':{'options':{'space_id':'space','query':'Orion'}},
        'result':{'structuredContent':{'hits':[{'kind':'wiki','citation':None},{'kind':'chunk','citation':c}]}}}]
    final={'outcome':'completed','citations':[{k:v for k,v in c.items() if k!='body'}]}
    result=grade(q,final,calls,corpus)
    assert result['complete_evidence'] and result['citation_validity']==1
    calls[0]['result']['structuredContent']['hits']=calls[0]['result']['structuredContent']['hits'][:1]
    assert grade(q,final,calls,corpus)['invalid_citations']==1


def test_prepared_import_rebinds_only_exact_sources_and_preserves_sealed_partitions(tmp_path):
    from agentic_retrieval.prepared import load_prepared
    corpus,q,plan=fixture();q['split']='sealed'
    (tmp_path/'initial-layer-builder').mkdir()
    for name,value in [('corpus.json',corpus),('questions.json',[q]),('initial-layer-builder/validated.json',plan),
        ('freeze.json',{'corpus':digest(corpus),'questions':digest([q]),'plan':digest(plan)})]:
        (tmp_path/name).write_text(json.dumps(value))
    changed=deepcopy(corpus);changed[0]|={'id':'new-source','generation':'new-version'}
    changed[0]['chunks'][0]|={'source_id':'new-source','version_id':'new-version','document_id':'new-doc','chunk_id':'new-chunk'}
    questions,layer,proof=load_prepared(tmp_path,changed)
    assert questions[0]['text']==q['text'] and questions[0]['split']=='sealed'
    assert layer['records'][0]['evidence'][0]['chunk_id']=='new-chunk'
    assert proof['only_identity_bindings_changed']
    changed[0]['version']='other'
    with pytest.raises(ValueError,match='metadata'):load_prepared(tmp_path,changed)
    exposed=tmp_path/'sealed-0-raw-question-a-0';exposed.mkdir();(exposed/'runner.json').write_text('{}')
    questions,_,proof=load_prepared(tmp_path,corpus)
    assert questions[0]['split']=='development' and proof['previous_test_exposure']


def test_standalone_audited_label_freeze_and_maintenance_status_need_no_model_or_credentials(tmp_path):
    import subprocess
    corpus,q,plan=fixture();proposal={'corpus_hash':digest(corpus),'questions_hash':digest([q]),'plan_hash':digest(plan)}
    audit={'proposal_hash':digest(proposal),'reviewed_questions_hash':digest([q]),'approved_for_pilot':True,'audit':[{'id':q['id'],'review':'source audit'}]}
    for name,value in [('corpus',corpus),('proposed',[q]),('reviewed',[q]),('plan',plan),('audit',audit)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    script=ROOT/'scripts/evaluate-agentic-retrieval.py'
    command=[sys.executable,str(script),'freeze-labels']
    for name in ('corpus','proposed','reviewed','plan','audit'):command+=['--'+name,str(tmp_path/(name+'.json'))]
    subprocess.run([*command,'--output',str(tmp_path/'frozen')],check=True,capture_output=True)
    assert json.loads((tmp_path/'frozen/questions.json').read_text())[0]['id']==q['id']
    result=subprocess.run([sys.executable,str(script),'maintain','status','--job',str(tmp_path/'not-a-job'),
        '--corpus',str(tmp_path/'corpus.json'),'--plan',str(tmp_path/'plan.json'),'--state',str(tmp_path/'state.json')],check=True,capture_output=True,text=True)
    assert json.loads(result.stdout)=={'state_present':False,'pending':False}


def test_authorization_loss_is_not_recorded_as_a_quality_failure(tmp_path,monkeypatch):
    from contextlib import asynccontextmanager
    from agentic_retrieval import runner
    corpus,q,_=fixture()
    tool=SimpleNamespace(name='read',annotations=SimpleNamespace(read_only_hint=True,model_dump=lambda **kw:{'readOnlyHint':True}))
    class Client:
        async def list_tools(self):return SimpleNamespace(tools=[tool])
        async def call_tool(self,name,args):return CallToolResult(is_error=True,content=[TextContent(type='text',text='permission_denied')])
    class Fixture:
        space='space'
        async def corpus(self):return corpus
        def snapshot(self):return {'unchanged':[]}
        @asynccontextmanager
        async def mcp(self,case):yield Client()
    async def completed_denial(**kwargs):
        kwargs['output'].mkdir()
        result=await kwargs['call_tool']('read',{'space_id':'space'})
        return {'valid':True,'calls':1,'elapsed_seconds':1,'final':{'outcome':'denied','citations':[]},
                'token_usage':{'total':{'totalTokens':10}}},[{'name':'read','arguments':{'space_id':'space'},'result':result.model_dump(mode='json',by_alias=True)}]
    monkeypatch.setattr(runner,'evaluate',completed_denial)
    config={'sessions':1,'tokens':100000,'seconds':100,'episode_tokens':10000,'episode_seconds':10,
            'model':'test-only','effort':'low','cli_version':'codex-cli 0.166.0','calls':2,'context_bytes':100000}
    budget=Budget(tmp_path/'ledger.json',config)
    result=asyncio.run(runner.episode(Fixture(),corpus,q,config,tmp_path/'episode',budget,'case'))
    assert result['status']=='runner_failure' and 'authorization_unavailable' in result['failure']
    assert 'grade' not in result and budget.state['episodes']['case']['status']=='runner_failure'


def test_actual_model_child_cannot_inherit_c0_or_database_credentials(tmp_path,monkeypatch):
    monkeypatch.setenv('CODEX_HOME',str(tmp_path/'empty-config'))
    for key in ('CZERO_EVAL_DATABASE_URL','CZERO_TEST_DATABASE_URL','C0_TOKEN','PGPASSWORD','DATABASE_URL'):
        monkeypatch.setenv(key,'synthetic-private-binding')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-approved-model-auth')
    path=fake_codex(tmp_path,'success');text=path.read_text()
    text=text.replace('import json,sys', '''import json,sys,os
assert not any(k.startswith(("CZERO_","C0_")) or k in ("PGPASSWORD","DATABASE_URL") for k in os.environ)
assert os.environ["OPENAI_API_KEY"]=="synthetic-approved-model-auth"''')
    path.write_text(text)
    tool=SimpleNamespace(name='actual_probe',description='Synthetic boundary control',input_schema={'type':'object'})
    async def actual(name,args):return CallToolResult(content=[TextContent(type='text',text='{}')])
    proof,_=asyncio.run(evaluate(tools=[tool],instructions='Boundary control',prompt='Probe',call_tool=actual,
        output=tmp_path/'episode',codex=str(path),timeout=10))
    assert proof['valid']


def test_multipart_corpus_reader_pages_documents_and_chunks_and_binds_physical_generations():
    from agentic_retrieval.job import read_corpus
    corpus,q,_=fixture();base=corpus[0];calls=[]
    summaries=[{'id':str(i)} for i in range(101)]
    async def api(name,**args):
        calls.append((name,args))
        if name=='source_documents_list':return {'documents':summaries[args['offset']:args['offset']+args['limit']]}
        if name=='source_documents_get':
            identifier=args['logical_document_id']
            return {'id':identifier,'revision_id':'logical-'+identifier,'state':'ready','multipart':True,
                'body':base['body'],'text_hash':base['content_hash'],'title':'Original',
                'metadata':{'canonical_url':'https://docs.example.test/'+identifier},
                'parts':[{'version_id':'part-'+identifier,'document_id':'physical-'+identifier,'text_hash':base['content_hash']}]}
        if name=='documents_get':return {'id':args['version_id'].replace('part-','physical-'),'text_hash':base['content_hash']}
        if name=='document_chunks_list':
            identifier=args['document_id'].removeprefix('physical-')
            chunks=[{'id':identifier+'-'+str(i)} for i in range(101 if identifier=='0' else 1)]
            return {'chunks':chunks[args['offset']:args['offset']+args['limit']]}
        if name=='citations_get':
            identifier=args['chunk_id'].split('-')[0]
            return {**base['chunks'][0],'chunk_id':args['chunk_id'],'version_id':'part-'+identifier,
                    'source_id':'source-'+identifier,'document_id':'physical-'+identifier}
        raise AssertionError(name)
    result=asyncio.run(read_corpus(api))
    assert len(result)==101
    first=next(d for d in result if d['id']=='0')
    assert first['generation']=='logical-0' and len(first['chunks'])==101
    assert first['chunks'][0]['version_id']=='part-0'
    assert any(name=='source_documents_list' and args['offset']==100 for name,args in calls)
    assert any(name=='document_chunks_list' and args['offset']==100 for name,args in calls)
    with pytest.raises(ValueError,match='selection_budget'):asyncio.run(read_corpus(api,max_sources=100))
    async def stale(name,**args):
        result=await api(name,**args)
        if name=='citations_get':result['version_id']='superseded'
        return result
    with pytest.raises(ValueError,match='citation_identity'):asyncio.run(read_corpus(stale))


def test_source_selection_budget_is_explicit_and_multipart_offsets_cannot_be_flattened():
    from agentic_retrieval.fixture import validate_sources
    source={'key':'one','body':'café first\nsecond\n'}
    body=source['body'].encode();cut=len('café first\n'.encode())
    source['parts']=[{'start_byte':0,'end_byte':cut},{'start_byte':cut,'end_byte':len(body)}]
    sources=[{**source,'key':str(i)} for i in range(451)]
    validate_sources(sources,1000,134217728)
    with pytest.raises(ValueError,match='selection_budget'):validate_sources(sources,100,134217728)
    with pytest.raises(ValueError,match='total_bytes'):validate_sources(sources,1000,10)
    bad=deepcopy(source);bad['parts'][1]['start_byte']-=1
    with pytest.raises(ValueError,match='part_layout'):validate_sources([bad],1000,134217728)


def test_batched_builders_preserve_counts_bound_packets_and_charge_each_session(tmp_path,monkeypatch):
    from agentic_retrieval import builders
    corpus,q,_=fixture();prompts=[]
    async def model(**kwargs):
        packet=json.loads(kwargs['prompt']);prompts.append(packet)
        props=kwargs['final_schema']['properties'];value={}
        for group in ('answerable','ambiguous','unanswerable'):
            value[group]=[{**deepcopy(q),'id':str(i),'answerability':group,
                'evidence_sets':[] if group=='unanswerable' else q['evidence_sets']}
                for i in range(props[group]['minItems'])]
        kwargs['output'].mkdir()
        proof={'valid':True,'final':value,'elapsed_seconds':1,'token_usage':{'total':{'totalTokens':100}}}
        (kwargs['output']/'runner.json').write_text(json.dumps(proof))
        return proof,[]
    monkeypatch.setattr(builders,'evaluate',model)
    config={'model':'test-only','effort':'medium','episode_seconds':180,'episode_tokens':10000,
        'context_bytes':524288,'cli_version':'codex-cli 0.166.0','sessions':10,'tokens':100000,'seconds':100,
        'batch_size':4,'source_packet_bytes':49152,'question_counts':{'answerable':6,'ambiguous':3,'unanswerable':3}}
    value,proof=asyncio.run(builders.build('questions',corpus,config,tmp_path/'builder',count=12))
    assert len(value)==len({q['id'] for q in value})==12
    assert [sum(q['answerability']==group for q in value) for group in ('answerable','ambiguous','unanswerable')]==[6,3,3]
    assert len(prompts)==4 and max(p['count'] for p in prompts)<=4
    assert proof['token_usage']['total']['totalTokens']==400
    ledger=json.loads((tmp_path/'builder/ledger.json').read_text())
    assert len(ledger['episodes'])==4 and ledger['tokens']==400
    assert all('body' not in p['originals'][0] and 'chunks' in p['originals'][0] for p in prompts)


@pytest.mark.parametrize('mode,exploratory,expected_splits,expected_status',[
    ('benchmark',False,['development','validation','sealed'],'completed_targets_unmet'),
    ('optimize',False,['development'],'development_target_unmet'),
    ('benchmark',True,['development'],'exploratory_completed')])
def test_quality_targets_do_not_block_benchmark_and_exploration_needs_no_audit(
        tmp_path,monkeypatch,mode,exploratory,expected_splits,expected_status):
    from contextlib import asynccontextmanager
    spec=importlib.util.spec_from_file_location('evaluation_cli',ROOT/'scripts/evaluate-agentic-retrieval.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    corpus,q,plan=fixture();questions=[];splits=[]
    for group in ('answerable','ambiguous','unanswerable'):
        questions.extend({**deepcopy(q),'id':group+str(i),'answerability':group,
            'evidence_sets':[] if group=='unanswerable' else q['evidence_sets']} for i in range(3))
    config=tmp_path/'config.json';config.write_text(json.dumps({'mode':mode,'rounds':1,'questions':9}))
    sources=tmp_path/'sources.json';sources.write_text('[]')
    output=tmp_path/'run'
    class Fixture:
        space='space'
        async def api_call(self,*args):raise AssertionError('no runtime calls in control-flow test')
    @asynccontextmanager
    async def paired(*args,**kwargs):yield Fixture(),Fixture(),corpus
    async def builder(kind,corpus,config,destination,budget):
        destination.mkdir();value=plan if kind=='layer' else questions
        (destination/'validated.json').write_text(json.dumps(value))
        if kind=='questions' and not exploratory:
            proposal={'corpus_hash':digest(corpus),'questions_hash':digest(questions),'plan_hash':digest(plan)}
            (output/'label-audit.json').write_text(json.dumps({'proposal_hash':digest(proposal),
                'reviewed_questions_hash':digest(questions),'approved_for_pilot':True,'audit':[{'provenance':'test control'}]}))
        return value
    async def measure(*args,**kwargs):return []
    async def compare(*args,**kwargs):
        splits.append(args[7])
        return {'summary':{'raw':{},'enriched':{}},'unmet':['absolute_quality','improvement','ambiguous'],
            'results':{'raw':[],'enriched':[]}}
    async def maintain(*args,**kwargs):return {}
    monkeypatch.setenv('CZERO_EVAL_DATABASE_URL','synthetic-loopback-binding')
    monkeypatch.setattr(cli,'paired_fixture',paired);monkeypatch.setattr(cli,'builder',builder)
    monkeypatch.setattr(cli,'measure',measure);monkeypatch.setattr(cli,'compare',compare)
    monkeypatch.setattr(cli,'maintain',maintain);monkeypatch.setattr(cli,'verify',maintain)
    args=SimpleNamespace(config=config,output=output,sources=sources,prepared=None,resume=False,
                         prepare_only=False,exploratory=exploratory)
    code=asyncio.run(cli.loop(args))
    result=json.loads((output/'result.json').read_text())
    assert splits==expected_splits and result['status']==expected_status
    assert code==(2 if mode=='optimize' else 0)
    if exploratory:assert 'unaudited' in json.loads((output/'freeze.json').read_text())['label_provenance']


def test_question_only_label_freeze_does_not_require_a_semantic_layer(tmp_path):
    import subprocess
    corpus,q,_=fixture()
    proposal={'corpus_hash':digest(corpus),'questions_hash':digest([q]),'plan_hash':digest(None)}
    audit={'proposal_hash':digest(proposal),'reviewed_questions_hash':digest([q]),
        'approved_for_pilot':True,'audit':[{'provenance':'source-based analyst check'}]}
    for name,value in [('corpus',corpus),('proposed',[q]),('reviewed',[q]),('audit',audit)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    command=[sys.executable,str(ROOT/'scripts/evaluate-agentic-retrieval.py'),'freeze-labels']
    for name in ('corpus','proposed','reviewed','audit'):command+=['--'+name,str(tmp_path/(name+'.json'))]
    subprocess.run([*command,'--output',str(tmp_path/'frozen')],check=True,capture_output=True)
    assert json.loads((tmp_path/'frozen/freeze.json').read_text())['plan']==digest(None)
