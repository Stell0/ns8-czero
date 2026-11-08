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
    'mode':'benchmark','max_sources':1000,'max_source_bytes':134217728,
    'batch_size':4,'source_packet_bytes':49152,'question_counts':None,
    'targets':{'complete':.80,'improvement':.10,'disposition':.80,'p95_seconds':180}}


def configuration(path):
    supplied=json.loads(Path(path).read_text()) if path else {}
    if supplied.keys()-DEFAULTS.keys():raise ValueError('unknown_configuration')
    c=DEFAULTS|supplied
    from jsonschema import validate
    validate(c,json.loads((ROOT/'docs/agentic-retrieval.schema.json').read_text()))
    bounds={'calls':(1,16),'context_bytes':(16384,1048576),'episode_tokens':(10000,500000),
            'episode_seconds':(10,180),'sessions':(1,1000),'tokens':(10000,30000000),
            'seconds':(10,21600),'rounds':(1,3),'repetitions':(1,2),'questions':(1,500),'layer_records':(1,20),
            'max_sources':(1,10000),'max_source_bytes':(1,536870912),
            'batch_size':(1,20),'source_packet_bytes':(16384,524288)}
    for k,(lo,hi) in bounds.items():
        if type(c[k]) is not int or not lo<=c[k]<=hi:raise ValueError('configuration_bound_'+k)
    if not isinstance(c['model'],str) or not c['model']:raise ValueError('explicit_model_required')
    if c['cli_version'] not in ('codex-cli 0.163.0','codex-cli 0.166.0'):raise ValueError('unsupported_driver')
    if set(c['targets'])!=set(DEFAULTS['targets']):raise ValueError('target_schema')
    for k in ('complete','improvement','disposition'):
        if not 0<=c['targets'][k]<=1:raise ValueError('invalid_quality_target')
    from agentic_retrieval.builders import question_counts
    question_counts(c['questions'],c['question_counts'])
    return c


async def builder(kind,corpus,config,output,budget,feedback=None):
    completed=Path(output)/'validated.json'
    if completed.exists():
        value=json.loads(completed.read_text())
        if kind=='questions':validate_questions(value,corpus)
        else:validate_plan(value,corpus)
        return value
    value,proof=await build(kind,corpus,config,output,count=config['questions'] if kind=='questions' else config['layer_records'],
        namespace=config['namespace'],feedback=feedback,budget=budget)
    return value


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
        'prepared_input':str(args.prepared.resolve()) if args.prepared else None,
        'exploratory':args.exploratory,'publisher':getattr(args,'publisher','semantic-layer')}
    if args.resume:
        if json.loads((output/'protocol.json').read_text())!=protocol:raise ValueError('resume_protocol_or_code_changed')
        if json.loads((output/'result.json').read_text())['status'] not in ('stopped_checkpoint','prepared_requires_audit'):raise ValueError('terminal_experiment_cannot_resume')
    else:atomic(output/'protocol.json',protocol)
    if protocol['publisher']=='compiler' and (config['mode']!='benchmark' or args.exploratory):
        raise ValueError('compiler_requires_frozen_reviewed_benchmark')
    budget=Budget(output/'ledger.json',config)
    sources=json.loads(Path(args.sources).read_text())
    if args.resume and json.loads((output/'input-hash.json').read_text())!={'sha256':digest(sources)}:raise ValueError('resume_sources_changed')
    atomic(output/'input-hash.json',{'sha256':digest(sources)})
    result={'status':'started','rounds':[],'validation':'not_run','sealed':'not_run'}
    try:
        async with asyncio.timeout(max(1,config['seconds']-budget.state['elapsed'])), paired_fixture(os.environ['CZERO_EVAL_DATABASE_URL'],output/'fixture',sources,checkpoint=output/'database-binding.json',max_sources=config['max_sources'],max_source_bytes=config['max_source_bytes']) as (a,b,corpus):
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
            if args.prepare_only or (not args.exploratory and not (output/'label-audit.json').exists()):
                result['status']='prepared_requires_audit'
                atomic(output/'result.json',result)
                print(json.dumps({'status':result['status'],'questions':len(questions)}));return 2
            audit=json.loads((output/'label-audit.json').read_text()) if not args.exploratory else None
            reviewed_path=output/'questions-reviewed.json'
            reviewed=json.loads(reviewed_path.read_text()) if reviewed_path.exists() else questions
            if args.exploratory:
                questions=partition(reviewed,seed=digest(corpus))
                questions=[{**q,'previously_exposed':True} if q['split']=='development' else q for q in questions]
                freeze={'corpus':digest(corpus),'questions':digest(questions),'protocol':digest(protocol),
                    'plan':digest(plan),'label_provenance':'unaudited exploratory labels; no held-out acceptance'}
            else:
                questions,freeze=freeze_labels(corpus,questions,reviewed,audit,digest(protocol),digest(plan),partitions=partitions)
            if (output/'freeze.json').exists() and json.loads((output/'freeze.json').read_text())!=freeze:
                raise ValueError('frozen_labels_or_protocol_changed')
            atomic(output/'questions.json',questions);atomic(output/'freeze.json',freeze)
            compiler_review=None
            if protocol['publisher']=='compiler':
                from agentic_retrieval.compiler import review_plan
                compiler_review=json.loads((output/'compilation-review.json').read_text())
                review_plan(compiler_review,corpus,plan)
            forbidden=[x for q in questions for x in (q['id'],q['text'])]
            for round_number in range(config['rounds'] if config['mode']=='optimize' and not args.exploratory else 1):
                validate_plan(plan,corpus,forbidden)
                atomic(output/f'layer-{round_number}.json',plan)
                raw=await measure('raw',a,corpus,questions,config,output,budget,'development',round_number)
                state=output/'layer-state.json'
                if protocol['publisher']=='compiler':
                    from agentic_retrieval.compiler import publish
                    dry=await publish(b,corpus,plan,state,compiler_review,forbidden=forbidden)
                    atomic(output/f'layer-{round_number}-dry-run.json',dry)
                    applied=await publish(b,corpus,plan,state,compiler_review,apply=True,forbidden=forbidden)
                    verified=await publish(b,corpus,plan,state,compiler_review,apply=True,forbidden=forbidden)
                else:
                    dry=await maintain(b.api_call,b.space,corpus,plan,state,forbidden=forbidden)
                    atomic(output/f'layer-{round_number}-dry-run.json',dry)
                    applied=await maintain(b.api_call,b.space,corpus,plan,state,apply=True,max_operations=120,forbidden=forbidden)
                    verified=await verify(b.api_call,b.space,corpus,plan,state)
                atomic(output/f'layer-{round_number}-receipt.json',applied)
                atomic(output/f'layer-{round_number}-verification.json',verified)
                measured=await compare(a,b,corpus,questions,config,output,budget,'development',round_number,raw=raw)
                result['rounds'].append({'round':round_number,'plan_hash':digest(plan),'summary':measured['summary'],'unmet':measured['unmet']})
                atomic(output/'result.json',result)
                if args.exploratory:
                    result['status']='exploratory_completed';break
                if config['mode']=='optimize' and any(r['grade']['invalid_citations'] for arm in measured['results'].values() for r in arm):
                    result['status']='stopped_citation_regression';break
                if config['mode']=='benchmark' or not measured['unmet']:
                    result['selected_round']=round_number
                    validation=await compare(a,b,corpus,questions,config,output,budget,'validation',round_number)
                    result['validation']=validation['summary']
                    if config['mode']=='optimize' and validation['unmet']:
                        result['status']='validation_target_unmet';break
                    sealed=await compare(a,b,corpus,questions,config,output,budget,'sealed',round_number)
                    result['sealed']=sealed['summary']
                    result['unmet']={'development':measured['unmet'],'validation':validation['unmet'],'sealed':sealed['unmet']}
                    passed=not any(result['unmet'].values())
                    result['status']=('accepted' if passed else 'completed_targets_unmet') if config['mode']=='benchmark' else ('accepted' if not sealed['unmet'] else 'sealed_target_unmet')
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
    return 0 if result['status'] in ('accepted','completed_targets_unmet','exploratory_completed') else 2


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    run=sub.add_parser('loop',help='Disposable paired-source comparison with a bounded improvement loop')
    run.add_argument('--publisher',choices=('semantic-layer','compiler'),default='semantic-layer',
        help='Publish reviewed construction through the existing semantic profile or production compiler in the disposable fixture')
    run.add_argument('--prepared',type=Path,help='Reuse frozen questions/partitions and the source-only plan; require identical bodies/metadata and audit new bindings')
    run.add_argument('--exploratory',action='store_true',help='Run development with provisional labels, without an audit; never run held-out partitions or claim acceptance')
    run.add_argument('--prepare-only',action='store_true',help='Freeze model proposals and partitions for private source-based analyst audit')
    run.add_argument('--resume',action='store_true',help='Resume only an unchanged nonterminal checkpoint; never replay uncertain episodes')
    run.add_argument('--sources',required=True,type=Path);run.add_argument('--config',type=Path);run.add_argument('--output',required=True,type=Path)
    for command in ('questions','layer'):
        c=sub.add_parser(command,help='Generate and validate a private proposal from originals only')
        c.add_argument('--corpus',required=True,type=Path);c.add_argument('--config',type=Path);c.add_argument('--output',required=True,type=Path)
    freeze=sub.add_parser('freeze',help='Read a selected private job corpus through existing authenticated APIs')
    freeze.add_argument('--job',required=True,type=Path);freeze.add_argument('--output',required=True,type=Path)
    freeze.add_argument('--max-sources',type=int,default=1000)
    freeze.add_argument('--max-source-bytes',type=int,default=134217728)
    manage=sub.add_parser('maintain',help='dry-run/apply/status/verify the approved managed Wiki profile')
    manage.add_argument('action',choices=('dry-run','apply','status','verify'))
    manage.add_argument('--job',required=True,type=Path);manage.add_argument('--corpus',required=True,type=Path)
    manage.add_argument('--plan',required=True,type=Path);manage.add_argument('--state',required=True,type=Path)
    manage.add_argument('--questions',type=Path,help='Optional private evaluation leakage denylist; never passed to builder')
    manage.add_argument('--max-operations',type=int,default=30)
    labels=sub.add_parser('freeze-labels',help='Freeze source-audited questions and partitions without a model or database')
    for field in ('corpus','proposed','reviewed','audit','output'):labels.add_argument('--'+field,required=True,type=Path)
    labels.add_argument('--plan',type=Path,help='Optional semantic plan; question-only freezes bind JSON null instead')
    check=sub.add_parser('validate');check.add_argument('--corpus',required=True,type=Path);check.add_argument('--questions',type=Path);check.add_argument('--plan',type=Path)
    audit=sub.add_parser('answer-audit',help='Bind source-based analyst judgments to exact frozen episodes; no model or publication')
    audit.add_argument('output',type=Path);audit.add_argument('--reviews',required=True,type=Path)
    status=sub.add_parser('status');status.add_argument('output',type=Path)
    cleanup=sub.add_parser('cleanup',help='Remove only ownership-proven retained disposable databases')
    cleanup.add_argument('output',type=Path)
    args=p.parse_args()
    if args.command=='loop':
        args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with locked(args.output.parent/('.'+args.output.name+'.lock')):return asyncio.run(loop(args))
    if args.command=='answer-audit':
        from agentic_retrieval.audit import answer_audit
        report=answer_audit(args.output,json.loads(args.reviews.read_text()))
        atomic(args.output/'answer-audit.json',report)
        print(json.dumps(report['summary']));return 0
    if args.command=='cleanup':
        cleanup_pair(os.environ['CZERO_EVAL_DATABASE_URL'],args.output/'database-binding.json');print('Removed owned disposable databases');return 0
    if args.command=='status':
        print((args.output/'result.json').read_text());return 0
    if args.command=='freeze':
        args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
        with job_client(args.job) as client:
            corpus=corpus_snapshot(client,max_sources=args.max_sources,max_source_bytes=args.max_source_bytes)
            if corpus_snapshot(client,max_sources=args.max_sources,max_source_bytes=args.max_source_bytes)!=corpus:raise ValueError('corpus_drift')
            atomic(args.output/'corpus.json',corpus)
        print('Frozen verified current corpus privately');return 0
    corpus=json.loads(args.corpus.read_text());validate_corpus(corpus)
    if args.command=='freeze-labels':
        proposed=json.loads(args.proposed.read_text());reviewed=json.loads(args.reviewed.read_text());audit=json.loads(args.audit.read_text());plan=json.loads(args.plan.read_text()) if args.plan else None
        if plan is not None:validate_plan(plan,corpus)
        questions,frozen=freeze_labels(corpus,proposed,reviewed,audit,digest({'command':'freeze-labels','source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}),digest(plan))
        args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
        atomic(args.output/'questions.json',questions);atomic(args.output/'freeze.json',frozen)
        print('Frozen audited labels and partitions privately');return 0
    if args.command=='maintain':
        plan=json.loads(args.plan.read_text());questions=json.loads(args.questions.read_text()) if args.questions else []
        if questions:validate_questions(questions,corpus)
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
