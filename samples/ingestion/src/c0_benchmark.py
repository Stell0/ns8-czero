# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only retrieval measurements against a frozen current-document corpus."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

from c0_ingest.auth import locked
from c0_ingest.client import C0
from c0_ingest.config import connection_settings
from c0_ingest.errors import C0Error
from c0_ingest.jobs import check_job
from c0_ingest.state import atomic
from c0_projects.model import sha


def snapshot(client):
    """Read full current documents through authorized APIs; retain no old bodies."""
    documents=[];bodies={};sources={}
    for summary in client.listing('source_documents_list','documents'):
        doc=client.call('source_documents_get',logical_document_id=summary['id'])
        if doc['state']!='ready' or doc.get('body') is None:raise C0Error('benchmark_incomplete_document')
        digest=hashlib.sha256(doc['body'].encode()).hexdigest()
        if digest!=doc['text_hash']:raise C0Error('benchmark_document_hash_mismatch')
        metadata=doc.get('metadata',{});provenance=metadata.get('provenance',{})
        url=metadata.get('canonical_url') or provenance.get('canonical_url') or doc.get('canonical_url')
        if not url:raise C0Error('benchmark_canonical_url_missing')
        row={'id':doc['id'],'url':url,'revision_id':doc['revision_id'],'content_hash':digest,
             'product':provenance.get('product',''),'version':provenance.get('product_version',''),
             'language':provenance.get('language','')}
        if url in bodies:raise C0Error('benchmark_duplicate_canonical_url')
        bodies[url]=doc['body'];documents.append(row)
        parts=doc['parts'] if doc['multipart'] else [{'source_id':doc['id'],'version_id':doc['revision_id']}]
        for part in parts:
            key=part['source_id']
            if key in sources:raise C0Error('benchmark_ambiguous_source_parent')
            sources[key]={**row,'version_id':part['version_id']}
    documents.sort(key=lambda d:d['id'])
    return {'documents':documents,'hash':sha(documents)},bodies,sources


def check_corpus(expected,observed):
    if expected!=observed:raise C0Error('benchmark_corpus_drift')


def validate_questions(questions,manifest,bodies):
    if not isinstance(questions,list) or not 1<=len(questions)<=500:raise ValueError('question_count')
    urls={d['url']:d for d in manifest['documents']};seen=set()
    for q in questions:
        if (not isinstance(q.get('id'),str) or not q['id'] or q['id'] in seen
                or not isinstance(q.get('text'),str) or not 1<=len(q['text'])<=512
                or q.get('answerability') not in ('answerable','ambiguous','unanswerable')
                or q.get('split') not in ('development','held_out') or not q.get('language')
                or not q.get('label_provenance') or not q.get('confidence')):
            raise ValueError('question_schema')
        seen.add(q['id']);relevant=q.get('relevant',[])
        if q['answerability']=='answerable' and not relevant:raise ValueError('answerable_without_evidence')
        if q['answerability']=='unanswerable' and relevant:raise ValueError('unanswerable_with_evidence')
        if len({r['url'] for r in relevant})!=len(relevant):raise ValueError('duplicate_gold_document')
        for label in relevant:
            url=label['url']
            if url not in urls or label['content_hash']!=urls[url]['content_hash']:raise ValueError('gold_corpus_mismatch')
            if not label.get('passages'):raise ValueError('gold_passages_missing')
            for alternatives in label['passages']:
                if not alternatives or any(not isinstance(p,str) or not p or p not in bodies[url] for p in alternatives):
                    raise ValueError('gold_passage_not_in_document')


def normalize(result,sources):
    chunks=[];documents=[];seen=set()
    for rank,hit in enumerate(result['hits'],1):
        citation=hit.get('citation')
        if hit.get('kind')!='chunk' or not citation:raise C0Error('benchmark_unexpected_hit_kind')
        parent=sources.get(citation['source_id'])
        if parent is None or parent['version_id']!=citation['version_id']:raise C0Error('benchmark_hit_outside_corpus')
        row={**parent,'rank':rank,'chunk_id':hit['id'],'body':citation['body']}
        chunks.append(row)
        if parent['id'] not in seen:
            seen.add(parent['id']);documents.append({**parent,'rank':len(documents)+1})
    return chunks,documents


def metrics(question,chunks,documents):
    gold={r['url'] for r in question.get('relevant',[])};ranking=[d['url'] for d in documents]
    output={}
    for k in (1,5,10):output['hit_at_'+str(k)]=int(bool(gold.intersection(ranking[:k]))) if gold else None
    for k in (5,10):output['recall_at_'+str(k)]=len(gold.intersection(ranking[:k]))/len(gold) if gold else None
    output['mrr_at_10']=next((1/rank for rank,url in enumerate(ranking[:10],1) if url in gold),0.) if gold else None
    evidence=[]
    for label in question.get('relevant',[]):
        passages=[c['body'] for c in chunks if c['url']==label['url']]
        evidence.extend(any(alternative in chunk for alternative in alternatives for chunk in passages) for alternatives in label['passages'])
    output['evidence_coverage']=sum(evidence)/len(evidence) if evidence else None
    output['complete_evidence']=int(all(evidence)) if evidence else None
    output['duplicate_document_rate']=(len(chunks)-len(documents))/len(chunks) if chunks else 0.
    output['wrong_product_hits']=sum(bool(question.get('products')) and d['product'] not in question['products'] for d in documents)
    output['wrong_version_hits']=sum(bool(question.get('versions')) and bool(d['version']) and d['version'] not in question['versions'] for d in documents)
    output['unknown_version_hits']=sum(not d['version'] for d in documents)
    output['returned_documents']=len(documents)
    return output


def percentile(values,fraction):
    if not values:return None
    return sorted(values)[max(0,math.ceil(len(values)*fraction)-1)]


def summarize(rows):
    output={}
    # First repetitions measure quality; repeat timings never inflate question N.
    for split in ('all','development','held_out'):
        selected=[r for r in rows if r['status']=='measured' and (split=='all' or r['split']==split)]
        for answerability in ('answerable','ambiguous','unanswerable'):
            timed=[r for r in selected if r['answerability']==answerability]
            first=[r for r in timed if r['repetition']==0]
            means={}
            for key in first[0]['metrics'] if first else []:
                values=[r['metrics'][key] for r in first if r['metrics'][key] is not None]
                means[key]=sum(values)/len(values) if values else None
            output[split+'/'+answerability]={'questions':len(first),'quality_means':means,
                'latency_samples':len(timed),'p50_ms':percentile([r['latency_ms'] for r in timed],.5),
                'p95_ms':percentile([r['latency_ms'] for r in timed],.95),
                'first_requests_ms':[r['latency_ms'] for r in first],
                'repeat_requests_ms':[r['latency_ms'] for r in timed if r['repetition']>0]}
    return output


def effective(result,mode,rerank):
    method=result['retrieval_method']
    return not result.get('fallback_reason') and method==mode+('+'+rerank if rerank!='off' else '')


def comparator_result(response,manifest,question_id):
    """Contract for an approved read-only adapter or disposable comparator index."""
    if response['corpus_hash']!=manifest['hash'] or response['question_id']!=question_id:
        raise C0Error('benchmark_comparator_binding_mismatch')
    docs={d['url']:d for d in manifest['documents']};chunks=[];ranking=[];seen=set()
    for hit in response['hits']:
        doc=docs.get(hit['url'])
        if doc is None or doc['content_hash']!=hit['content_hash']:raise C0Error('benchmark_comparator_corpus_mismatch')
        chunks.append({**doc,'body':hit['body'],'chunk_id':hit['chunk_id']})
        if doc['id'] not in seen:seen.add(doc['id']);ranking.append(doc)
    return chunks,ranking


def experiment(client,config,questions,expected,output):
    manifest,bodies,sources=snapshot(client);check_corpus(expected,manifest)
    validate_questions(questions,manifest,bodies)
    index=client.call('knowledge_index_status');rows=[];summaries={}
    if not 1<=config['repetitions']<=5 or not 10<=config['limit']<=50:raise ValueError('benchmark_budget')
    if len(questions)*len(config['modes'])*config['repetitions']>config['max_queries']:raise ValueError('benchmark_query_budget')
    atomic(output/'before.json',manifest);atomic(output/'index.json',index)
    try:
        for selection in config['modes']:
            mode=selection['mode'];rerank=selection['rerank'];name=mode+'+'+rerank
            if mode not in ('text','semantic','hybrid') or rerank not in ('off','rerank','filter'):raise ValueError('benchmark_mode')
            check_corpus(expected,snapshot(client)[0])
            if mode in ('semantic','hybrid') and not index['configured']:
                summaries[name]={'status':'unavailable','reason':'embeddings_not_configured'};continue
            measured=[]
            for q in questions:
                for repetition in range(config['repetitions']):
                    started=time.perf_counter()
                    # API failures stop the experiment. Denial is never a zero-hit result.
                    result=client.call('knowledge_search',options={'query':q['text'],'mode':mode,'rerank':rerank,'limit':config['limit'],'kind':'source','graph_depth':0})
                    elapsed=(time.perf_counter()-started)*1000
                    chunks,documents=normalize(result,sources)
                    row={'question_id':q['id'],'split':q['split'],'answerability':q['answerability'],
                        'repetition':repetition,'requested':selection,'effective_method':result['retrieval_method'],
                        'status':'measured' if effective(result,mode,rerank) else 'fallback',
                        'fallback_reason':result.get('fallback_reason'),'latency_ms':elapsed,
                        'chunks':chunks,'documents':documents,'metrics':metrics(q,chunks,documents),'raw':result}
                    rows.append(row);measured.append(row);atomic(output/'rankings.json',rows)
            check_corpus(expected,snapshot(client)[0])
            summaries[name]={'status':'measured' if any(r['status']=='measured' for r in measured) else 'fallback_only',
                'results':summarize(measured),'fallback_samples':sum(r['status']=='fallback' for r in measured)}
        check_corpus(expected,snapshot(client)[0])
    except Exception:
        atomic(output/'status.json',{'status':'invalid_or_blocked','comparison_valid':False});raise
    atomic(output/'after.json',manifest)
    result={'comparison_valid':True,'corpus_hash':manifest['hash'],'config_hash':sha(config),'questions_hash':sha(questions),
            'query_calls':len(rows),'modes':summaries,'cache_note':'First/repeat observed requests; backend cold cache is not established.'}
    atomic(output/'summary.json',result);return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('snapshot','run'))
    parser.add_argument('--job',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--config',type=Path);parser.add_argument('--questions',type=Path);parser.add_argument('--corpus',type=Path)
    args=parser.parse_args(argv);os.umask(0o077);check_job(args.job)
    args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    with locked(args.job/'job.lock'):
        client=C0(connection_settings(args.job))
        try:
            space=client.select_space(client.config['space_id'],writable=False)
            if space['name']!=client.config['space_name']:raise C0Error('benchmark_space_name_changed')
            atomic(args.output/'capabilities.json',client.capabilities)
            if args.operation=='snapshot':
                manifest,_,_=snapshot(client);atomic(args.output/'corpus.json',manifest)
                print(json.dumps({'documents':len(manifest['documents']),'corpus_hash':manifest['hash']}))
            else:
                result=experiment(client,json.loads(args.config.read_text()),json.loads(args.questions.read_text()),json.loads(args.corpus.read_text()),args.output)
                print(json.dumps({'comparison_valid':result['comparison_valid'],'query_calls':result['query_calls']}))
        finally:client.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
