#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded source/semantic-layer comparison using real disposable C0 MCP calls."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from c0_ingest.state import atomic
from c0_ingest.auth import locked
from agentic_retrieval.builders import build
from agentic_retrieval.fixture import paired_fixture,cleanup_pair
from agentic_retrieval.layer import maintain,verify,validate_plan
from agentic_retrieval.protocol import Budget,digest,partition,summary,validate_corpus,validate_questions,freeze_labels
from agentic_retrieval.runner import episode,accepted,INSTRUCTIONS
from agentic_retrieval.job import job_client,corpus_snapshot
from agentic_retrieval.prepared import load_prepared

DEFAULTS={'model':'gpt-6-luna','effort':'medium','cli_version':'codex-cli 0.166.0',
    'calls':12,'context_bytes':524288,'episode_tokens':200000,'episode_seconds':180,
    'sessions':80,'tokens':4000000,'seconds':7200,'rounds':3,'repetitions':1,
    'questions':12,'layer_records':4,'namespace':'semantic-pilot',
    'targets':{'complete':.80,'improvement':.10,'disposition':.80,'p95_seconds':180}}


def configuration(path):
    supplied=json.loads(Path(path).read_text()) if path else {}
    if supplied.keys()-DEFAULTS.keys():raise ValueError('unknown_configuration')
    c=DEFAULTS|supplied
    from jsonschema import validate
    validate(c,json.loads((ROOT/'docs/agentic-retrieval.schema.json').read_text()))
    bounds={'calls':(1,16),'context_bytes':(16384,1048576),'episode_tokens':(10000,500000),
            'episode_seconds':(10,180),'sessions':(1,100),'tokens':(10000,10000000),
            'seconds':(10,14400),'rounds':(1,3),'repetitions':(1,2),'questions':(9,100),'layer_records':(1,20)}
    for k,(lo,hi) in bounds.items():
        if type(c[k]) is not int or not lo<=c[k]<=hi:raise ValueError('configuration_bound_'+k)
    if not isinstance(c['model'],str) or not c['model']:raise ValueError('explicit_model_required')
    if c['cli_version'] not in ('codex-cli 0.163.0','codex-cli 0.166.0'):raise ValueError('unsupported_driver')
    if set(c['targets'])!=set(DEFAULTS['targets']):raise ValueError('target_schema')
    for k in ('complete','improvement','disposition'):
        if not 0<=c['targets'][k]<=1:raise ValueError('invalid_quality_target')
    return c


async def builder(kind,corpus,config,output,budget,feedback=None):
    key='builder-'+Path(output).name
    if not budget.reserve(key):return json.loads((Path(output)/'validated.json').read_text())
    proof={}
    try:
        value,proof=await build(kind,corpus,budget.remaining(config),output,count=config['questions'] if kind=='questions' else config['layer_records'],
            namespace=config['namespace'],feedback=feedback)
        return value
    finally:
        if (Path(output)/'runner.json').exists():proof=json.loads((Path(output)/'runner.json').read_text())
        budget.finish(key,proof,'completed' if (Path(output)/'validated.json').exists() else 'builder_failure')


async def measure(arm,fixture,corpus,questions,config,output,budget,split,round_number):
    rows=[]
    for q in questions:
        if q['split']!=split:continue
        for repetition in range(config['repetitions']):
            key=f'{split}-{round_number}-{arm}-{q["id"]}-{repetition}'
            row=await episode(fixture,corpus,q,config,output/key,budget,key)
            row.update(repetition=repetition,split=split,arm=arm,round=round_number)
            rows.append(row);atomic(output/f'{split}-{round_number}-{arm}-progress.json',rows)
            if row['status']=='runner_failure':raise RuntimeError('episode_failure_checkpoint_'+key)
    return rows


async def compare(a,b,corpus,questions,config,output,budget,split,round_number,raw=None):
    if raw is None:raw=await measure('raw',a,corpus,questions,config,output,budget,split,round_number)
    enriched=await measure('enriched',b,corpus,questions,config,output,budget,split,round_number)
    results={'raw':raw,'enriched':enriched}
    summaries={arm:summary(rows) for arm,rows in results.items()}
    value={'results':results,'summary':summaries,'unmet':accepted(summaries['raw'],summaries['enriched'],config['targets'])}
    atomic(output/f'{split}-{round_number}.json',value)
    return value


async def loop(args):
    config=configuration(args.config)
    if not os.getenv('CZERO_EVAL_DATABASE_URL'):raise ValueError('explicit_loopback_administrator_required')
    output=Path(args.output).resolve();output.mkdir(parents=True,mode=0o700,exist_ok=args.resume)
    files=[Path(__file__),*sorted((ROOT/'scripts/agentic_retrieval').glob('*.py')),
           ROOT/'tests/evaluation/codex_driver.py',ROOT/'tests/evaluation/fixture.py']
    protocol={'version':1,'config':config,'instructions_hash':digest(INSTRUCTIONS),
        'code_hashes':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
        'packages':{n:importlib.metadata.version(n) for n in ('czero-core','czero-app','mcp','c0-ingestion-samples')},
        'boundary':'Disposable authenticated C0; experimental eager MCP adapter, no native discovery claim.',
        'prepared_input':str(args.prepared.resolve()) if args.prepared else None}
    if args.resume:
        if json.loads((output/'protocol.json').read_text())!=protocol:raise ValueError('resume_protocol_or_code_changed')
        if json.loads((output/'result.json').read_text())['status'] not in ('stopped_checkpoint','prepared_requires_audit'):raise ValueError('terminal_experiment_cannot_resume')
    else:atomic(output/'protocol.json',protocol)
    budget=Budget(output/'ledger.json',config)
    sources=json.loads(Path(args.sources).read_text())
    if args.resume and json.loads((output/'input-hash.json').read_text())!={'sha256':digest(sources)}:raise ValueError('resume_sources_changed')
    atomic(output/'input-hash.json',{'sha256':digest(sources)})
    result={'status':'started','rounds':[],'validation':'not_run','sealed':'not_run'}
    try:
        async with asyncio.timeout(max(1,config['seconds']-budget.state['elapsed'])), paired_fixture(os.environ['CZERO_EVAL_DATABASE_URL'],output/'fixture',sources,checkpoint=output/'database-binding.json') as (a,b,corpus):
            if args.resume and json.loads((output/'corpus.json').read_text())!=corpus:raise ValueError('resumed_corpus_drift')
            atomic(output/'corpus.json',corpus)
            partitions=None
            if args.prepared:
                questions,plan,import_proof=load_prepared(args.prepared,corpus)
                partitions=import_proof['partitions'];atomic(output/'prepared-import.json',import_proof)
                (output/'initial-layer-builder').mkdir(mode=0o700,exist_ok=True)
                atomic(output/'initial-layer-builder/validated.json',plan)
            else:
                # Crucially the initial builder never receives questions or failures.
                plan=await builder('layer',corpus,config,output/'initial-layer-builder',budget)
                questions=await builder('questions',corpus,config,output/'question-builder',budget)
            validate_questions(questions,corpus)
            proposal={'corpus_hash':digest(corpus),'questions_hash':digest(questions),'plan_hash':digest(plan)}
            atomic(output/'questions-proposed.json',questions);atomic(output/'proposal.json',proposal)
            if args.prepare_only or not (output/'label-audit.json').exists():
                result['status']='prepared_requires_audit'
                atomic(output/'result.json',result)
                print(json.dumps({'status':result['status'],'questions':len(questions)}));return 2
            audit=json.loads((output/'label-audit.json').read_text())
            reviewed_path=output/'questions-reviewed.json'
            reviewed=json.loads(reviewed_path.read_text()) if reviewed_path.exists() else questions
            questions,freeze=freeze_labels(corpus,questions,reviewed,audit,digest(protocol),digest(plan),partitions=partitions)
            if (output/'freeze.json').exists() and json.loads((output/'freeze.json').read_text())!=freeze:
                raise ValueError('frozen_labels_or_protocol_changed')
            atomic(output/'questions.json',questions);atomic(output/'freeze.json',freeze)
            forbidden=[x for q in questions for x in (q['id'],q['text'])]
            for round_number in range(config['rounds']):
                validate_plan(plan,corpus,forbidden)
                atomic(output/f'layer-{round_number}.json',plan)
                raw=await measure('raw',a,corpus,questions,config,output,budget,'development',round_number)
                state=output/'layer-state.json'
                dry=await maintain(b.api_call,b.space,corpus,plan,state,forbidden=forbidden)
                atomic(output/f'layer-{round_number}-dry-run.json',dry)
                applied=await maintain(b.api_call,b.space,corpus,plan,state,apply=True,max_operations=120,forbidden=forbidden)
                atomic(output/f'layer-{round_number}-receipt.json',applied)
                atomic(output/f'layer-{round_number}-verification.json',await verify(b.api_call,b.space,corpus,plan,state))
                measured=await compare(a,b,corpus,questions,config,output,budget,'development',round_number,raw=raw)
                result['rounds'].append({'round':round_number,'plan_hash':digest(plan),'summary':measured['summary'],'unmet':measured['unmet']})
                atomic(output/'result.json',result)
                if any(r['grade']['invalid_citations'] for arm in measured['results'].values() for r in arm):
                    result['status']='stopped_citation_regression';break
                if not measured['unmet']:
                    result['selected_round']=round_number
                    validation=await compare(a,b,corpus,questions,config,output,budget,'validation',round_number)
                    result['validation']=validation['summary']
                    if validation['unmet']:
                        result['status']='validation_target_unmet';break
                    sealed=await compare(a,b,corpus,questions,config,output,budget,'sealed',round_number)
                    result['sealed']=sealed['summary'];result['status']='accepted' if not sealed['unmet'] else 'sealed_target_unmet'
                    break
                if round_number and measured['summary']['enriched']['complete_evidence']['mean']<=result['rounds'][-2]['summary']['enriched']['complete_evidence']['mean']:
                    result['status']='stopped_no_improvement';break
                if round_number+1==config['rounds']:result['status']='development_target_unmet';break
                # Only coarse development failure categories cross the builder boundary.
                plan=await builder('layer',corpus,config,output/f'layer-builder-{round_number+1}',budget,feedback={'failure_categories':measured['unmet'],'current_managed_plan':plan})
    except Exception as exc:
        result.update(status='stopped_checkpoint',failure_type=type(exc).__name__,failure=str(exc))
        import traceback
        (output/'failure.txt').write_text(traceback.format_exc())
    atomic(output/'result.json',result)
    if result['status']!='stopped_checkpoint' and (output/'database-binding.json').exists():
        cleanup_pair(os.environ['CZERO_EVAL_DATABASE_URL'],output/'database-binding.json')
    print(json.dumps({'status':result['status'],'rounds':len(result['rounds']),'validation':result['validation']!='not_run','sealed':result['sealed']!='not_run'}))
    return 0 if result['status']=='accepted' else 2


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    run=sub.add_parser('loop',help='Disposable paired-source comparison with a bounded improvement loop')
    run.add_argument('--prepared',type=Path,help='Reuse frozen questions/partitions and the source-only plan; require identical bodies/metadata and audit new bindings')
    run.add_argument('--prepare-only',action='store_true',help='Freeze model proposals and partitions for private source-based analyst audit')
    run.add_argument('--resume',action='store_true',help='Resume only an unchanged nonterminal checkpoint; never replay uncertain episodes')
    run.add_argument('--sources',required=True,type=Path);run.add_argument('--config',type=Path);run.add_argument('--output',required=True,type=Path)
    for command in ('questions','layer'):
        c=sub.add_parser(command,help='Generate and validate a private proposal from originals only')
        c.add_argument('--corpus',required=True,type=Path);c.add_argument('--config',type=Path);c.add_argument('--output',required=True,type=Path)
    freeze=sub.add_parser('freeze',help='Read a selected private job corpus through existing authenticated APIs')
    freeze.add_argument('--job',required=True,type=Path);freeze.add_argument('--output',required=True,type=Path)
    manage=sub.add_parser('maintain',help='dry-run/apply/status/verify the approved managed Wiki profile')
    manage.add_argument('action',choices=('dry-run','apply','status','verify'))
    manage.add_argument('--job',required=True,type=Path);manage.add_argument('--corpus',required=True,type=Path)
    manage.add_argument('--plan',required=True,type=Path);manage.add_argument('--state',required=True,type=Path)
    manage.add_argument('--questions',required=True,type=Path,help='Private leakage denylist; never passed to builder')
    manage.add_argument('--max-operations',type=int,default=30)
    check=sub.add_parser('validate');check.add_argument('--corpus',required=True,type=Path);check.add_argument('--questions',type=Path);check.add_argument('--plan',type=Path)
    status=sub.add_parser('status');status.add_argument('output',type=Path)
    cleanup=sub.add_parser('cleanup',help='Remove only ownership-proven retained disposable databases')
    cleanup.add_argument('output',type=Path)
    args=p.parse_args()
    if args.command=='loop':
        args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with locked(args.output.parent/('.'+args.output.name+'.lock')):return asyncio.run(loop(args))
    if args.command=='cleanup':
        cleanup_pair(os.environ['CZERO_EVAL_DATABASE_URL'],args.output/'database-binding.json');print('Removed owned disposable databases');return 0
    if args.command=='status':
        print((args.output/'result.json').read_text());return 0
    if args.command=='freeze':
        args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
        with job_client(args.job) as client:atomic(args.output/'corpus.json',corpus_snapshot(client))
        print('Frozen verified current corpus privately');return 0
    corpus=json.loads(args.corpus.read_text());validate_corpus(corpus)
    if args.command=='maintain':
        plan=json.loads(args.plan.read_text());questions=json.loads(args.questions.read_text())
        validate_questions(questions,corpus)
        forbidden=[x for q in questions for x in (q['id'],q['text'])]
        validate_plan(plan,corpus,forbidden)
        if args.action=='status':
            print(json.dumps({'state_present':args.state.exists(),'pending':bool(json.loads(args.state.read_text()).get('pending')) if args.state.exists() else False}));return 0
        with job_client(args.job,writable=args.action=='apply') as client:
            if corpus_snapshot(client)!=corpus:raise ValueError('corpus_drift')
            async def call(name,arguments):return client.call(name,**arguments)
            if args.action=='verify':result=asyncio.run(verify(call,client.space_id,corpus,plan,args.state))
            else:result=asyncio.run(maintain(call,client.space_id,corpus,plan,args.state,apply=args.action=='apply',max_operations=args.max_operations,forbidden=forbidden))
            if corpus_snapshot(client)!=corpus:raise ValueError('corpus_drift')
            print(json.dumps(result));return 0
    if args.command=='validate':
        if args.questions:validate_questions(json.loads(args.questions.read_text()),corpus)
        if args.plan:validate_plan(json.loads(args.plan.read_text()),corpus)
        print('Validated current hashes, generations and literal evidence');return 0
    config=configuration(args.config)
    asyncio.run(build('questions' if args.command=='questions' else 'layer',corpus,config,args.output,
        count=config['questions'] if args.command=='questions' else config['layer_records'],namespace=config['namespace']))
    print('Validated private proposal; application requires the selected supported workflow')
    return 0


if __name__=='__main__':raise SystemExit(main())
