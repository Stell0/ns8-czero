# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private protocol validation, partitioning, evidence grading and budget ledger."""
import hashlib
import json
import math
from pathlib import Path
import random
import time

from c0_ingest.state import atomic
from c0_benchmark import metrics


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def body_hash(body):
    return hashlib.sha256(body.encode()).hexdigest()


def validate_corpus(corpus):
    ids=set(); urls=set()
    for d in corpus:
        required={'id','url','generation','content_hash','body','product','version','language','chunks'}
        if not required <= d.keys() or d['id'] in ids or d['url'] in urls:
            raise ValueError('invalid_corpus_identity')
        ids.add(d['id']);urls.add(d['url'])
        if body_hash(d['body'])!=d['content_hash'] or not d['generation']:
            raise ValueError('corpus_hash_or_generation')
        for c in d['chunks']:
            if c['body'] not in d['body'] or body_hash(c['body'])!=c['content_hash']:
                raise ValueError('chunk_hash_or_body')
    if not corpus:raise ValueError('empty_corpus')
    return digest(corpus)


def validate_questions(questions,corpus):
    validate_corpus(corpus)
    docs={d['id']:d for d in corpus};seen=set()
    for q in questions:
        required={'id','text','language','type','answerability','products','versions',
                  'evidence_sets','provenance','confidence','uncertainty'}
        if not required<=q.keys() or q['id'] in seen or not q['id'] or not q['text']:
            raise ValueError('invalid_question')
        seen.add(q['id'])
        if 'previously_exposed' in q and type(q['previously_exposed']) is not bool:raise ValueError('invalid_exposure_marker')
        if q['answerability'] not in ('answerable','ambiguous','unanswerable'):
            raise ValueError('invalid_answerability')
        if not q['provenance'] or q['confidence'] not in ('low','medium','high'):
            raise ValueError('missing_analyst_provenance')
        sets=q['evidence_sets']
        if q['answerability']=='answerable' and not sets:raise ValueError('missing_complete_set')
        if q['answerability']=='unanswerable' and sets:raise ValueError('unanswerable_gold')
        for units in sets:
            if not units:raise ValueError('empty_complete_set')
            for alternatives in units:
                if not alternatives:raise ValueError('empty_evidence_unit')
                for e in alternatives:
                    d=docs.get(e['document_id'])
                    if d is None:raise ValueError('gold_unknown_logical_document')
                    if (e['generation']!=d['generation'] or e['content_hash']!=d['content_hash']
                        or e['url']!=d['url'] or not e['quote'] or e['quote'] not in d['body']):
                        raise ValueError('invalid_gold_evidence')
    if not seen:raise ValueError('empty_questions')
    return digest(questions)


def partition(questions,seed):
    """Deterministic stratification; input labels never modified after freezing."""
    groups={};result=[];rng=random.Random(seed)
    for q in questions:groups.setdefault(q['answerability'],[]).append(q)
    for key in sorted(groups):
        group=sorted(groups[key],key=lambda q:(q['type'],q['language'],q['id']));rng.shuffle(group)
        for index,q in enumerate(group):
            split=(('development','validation','sealed')[index] if len(group)==3 else
                   ('development','development','validation','sealed')[index%4])
            result.append({**q,'split':'development' if q.get('previously_exposed') else split})
    return sorted(result,key=lambda q:q['id'])


def freeze_labels(corpus,proposed,reviewed,audit,protocol_hash,plan_hash,partitions=None):
    validate_questions(proposed,corpus);validate_questions(reviewed,corpus)
    proposal={'corpus_hash':digest(corpus),'questions_hash':digest(proposed),'plan_hash':plan_hash}
    if (audit.get('proposal_hash')!=digest(proposal) or audit.get('reviewed_questions_hash')!=digest(reviewed)
        or audit.get('approved_for_pilot') is not True or not audit.get('audit')):
        raise ValueError('label_audit_missing_or_changed')
    questions=partition(reviewed,seed=digest(corpus))
    if partitions is not None:
        if set(partitions)!={q['id'] for q in questions} or set(partitions.values())-{'development','validation','sealed'}:
            raise ValueError('prepared_partition_changed')
        questions=[{**q,'split':'development' if q.get('previously_exposed') else partitions[q['id']]} for q in questions]
    frozen={'corpus':digest(corpus),'questions':digest(questions),'protocol':protocol_hash,
        'plan':plan_hash,'audit':digest(audit),'label_provenance':'provisional analyst labels; independent human adjudication unavailable'}
    return questions,frozen


def episode_input(question,space):
    """Deliberate projection: no IDs, labels, partitions or applicability hints."""
    return 'Selected space: '+space+'\nQuestion: '+question['text']


def objects(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from objects(v)
    elif isinstance(value,list):
        for v in value:yield from objects(v)


def payload(call):
    result=call.get('result',{})
    if result.get('isError'):return {}
    if result.get('structuredContent') is not None:return result['structuredContent']
    values=[]
    for c in result.get('content',[]):
        if c.get('type')=='text':
            try:values.append(json.loads(c['text']))
            except (ValueError,TypeError):pass
    return values


def original_citations(calls,corpus):
    # Reuse the established typed-response grader; arbitrary retrieved metadata
    # cannot impersonate an original citation. Truth comes from frozen API reads.
    from evaluation.grader import observed_citations
    truth={c['chunk_id']:{**c,'parent':d} for d in corpus for c in d['chunks']}
    tables={'c0_sources':{},'c0_source_versions':{},'c0_documents':{},'c0_chunks':{}}
    for c in truth.values():
        tables['c0_sources'][c['source_id']]={'id':c['source_id']}
        tables['c0_source_versions'][c['version_id']]={'id':c['version_id'],'source_id':c['source_id'],'state':'ready','content_hash':c['source_hash']}
        tables['c0_documents'][c['document_id']]={'id':c['document_id'],'version_id':c['version_id']}
        tables['c0_chunks'][c['chunk_id']]={'id':c['chunk_id'],**{k:c[k] for k in ('document_id','content_hash','start_offset','end_offset','body')}}
    snapshot={t:[json.dumps(v) for v in rows.values()] for t,rows in tables.items()}
    seen={c['chunk_id']:truth[c['chunk_id']] for c in observed_citations(calls,snapshot)}
    ranked=[];ranked_ids=set()
    for call in calls:
        value=payload(call)
        if not isinstance(value,dict):continue
        if call['name']=='sources_search':citations=value.get('citations',[])
        elif call['name'] in ('knowledge_search','knowledge_search_structured'):
            citations=[h.get('citation',{}) for h in value.get('hits',[])]
        else:continue
        for citation in citations:
            if not isinstance(citation,dict):continue
            key=citation.get('chunk_id')
            if key in seen and key not in ranked_ids:ranked.append(seen[key]);ranked_ids.add(key)
    return seen,ranked


def grade(question,final,calls,corpus):
    observed,ranked=original_citations(calls,corpus)
    selected=[];valid=[]
    for citation in final.get('citations',[]):
        c=observed.get(citation['chunk_id'])
        ok=c is not None and all(citation.get(k)==c.get(k) for k in citation)
        valid.append(ok)
        if ok:selected.append(c)
    units=[]
    for evidence_set in question['evidence_sets']:
        units.append([any(e['document_id']==c['parent']['id'] and e['quote'] in c['body']
                          for e in alternatives for c in selected) for alternatives in evidence_set])
    coverage=max((sum(s)/len(s) for s in units),default=None)
    complete=any(all(s) for s in units) if units else None
    disposition=final.get('outcome')
    disposition_ok=disposition=={'answerable':'completed','ambiguous':'clarification','unanswerable':'unavailable'}[question['answerability']]
    documents=[];chunks=[];seen=set()
    for c in ranked:
        d=c['parent'];chunks.append({'url':d['url'],'body':c['body']})
        if d['id'] not in seen:documents.append({'url':d['url'],'product':d['product'],'version':d['version']});seen.add(d['id'])
    # Ranking metrics use the union of acceptable complete sets; evidence success
    # above preserves alternatives rather than requiring that union in full.
    relevant={e['document_id']:e for s in question['evidence_sets'] for unit in s for e in unit}
    proxy={'relevant':[{'url':e['url'],'passages':[[e['quote']]]} for e in relevant.values()],
           'products':question['products'],'versions':question['versions']}
    retrieval=metrics(proxy,chunks,documents)
    product_errors=sum(bool(question['products'] and c['parent']['product'] and c['parent']['product'] not in question['products']) for c in selected)
    version_errors=sum(bool(question['versions'] and c['parent']['version'] and c['parent']['version'] not in question['versions']) for c in selected)
    return {'complete_evidence':complete,'passage_coverage':coverage,'disposition_correct':disposition_ok,
            'citation_validity':sum(valid)/len(valid) if valid else None,
            'invalid_citations':len(valid)-sum(valid),'product_errors':product_errors,'version_errors':version_errors,
            'unknown_product':sum(not c['parent']['product'] for c in selected),
            'unknown_version':sum(not c['parent']['version'] for c in selected),
            'rankings':retrieval,'original_chunks':[c['chunk_id'] for c in ranked],'observed_original_chunks':sorted(observed),
            'documents':[d['url'] for d in documents],
            'semantic_answer_review':'pending; deterministic evidence matching does not grade entailment'}


class Budget:
    def __init__(self,path,limits):
        self.path=Path(path);self.limits=limits;self.started=time.monotonic()
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {'episodes':{},'tokens':0,'elapsed':0}
    def reserve(self,key):
        if key in self.state['episodes']:
            if self.state['episodes'][key]['status']=='started':raise RuntimeError('uncertain_episode_requires_reconciliation')
            return False
        if (len(self.state['episodes'])>=self.limits['sessions'] or self.state['tokens']>=self.limits['tokens']
            or self.state['elapsed']>=self.limits['seconds']):raise RuntimeError('experiment_budget_exhausted')
        self.state['episodes'][key]={'status':'started','reserved_at':time.time()};atomic(self.path,self.state);return True
    def remaining(self,config):
        c=dict(config)
        c['episode_tokens']=min(c['episode_tokens'],self.limits['tokens']-self.state['tokens'])
        c['episode_seconds']=min(c['episode_seconds'],int(self.limits['seconds']-self.state['elapsed']))
        if c['episode_tokens']<1000 or c['episode_seconds']<10:raise RuntimeError('experiment_budget_exhausted')
        return c
    def finish(self,key,proof,status):
        usage=(proof.get('token_usage') or {}).get('total',{})
        tokens=usage.get('totalTokens')
        # Unknown usage charges the entire reserved episode allowance.
        charged=tokens if tokens is not None else self.limits['episode_tokens']
        elapsed=proof.get('elapsed_seconds',max(0,time.time()-self.state['episodes'][key]['reserved_at']))
        self.state['tokens']+=charged;self.state['elapsed']+=elapsed
        self.state['episodes'][key]={'status':status,'tokens':tokens,'charged_tokens':charged,
                                      'elapsed':elapsed}
        atomic(self.path,self.state)


def summary(rows):
    out={'episodes':len(rows),'runner_failures':sum(r['status']=='runner_failure' for r in rows)}
    timed=[r for r in rows if r['status']=='measured']
    valid=[r for r in timed if r.get('repetition',0)==0];answerable=[r for r in valid if r['answerability']=='answerable']
    for name in ('complete_evidence','passage_coverage'):
        vals=[r['grade'][name] for r in answerable]
        out[name]={'mean':sum(vals)/len(vals) if vals else None,'n':len(vals)}
    for kind in ('ambiguous','unanswerable'):
        vals=[r['grade']['disposition_correct'] for r in valid if r['answerability']==kind]
        out[kind]={'mean':sum(vals)/len(vals) if vals else None,'n':len(vals)}
    out['invalid_citations']=sum(r['grade']['invalid_citations'] for r in valid)
    out['submitted_citations']=sum(len(r['runner'].get('final',{}).get('citations',[])) for r in valid)
    out['citation_validity']=(1-out['invalid_citations']/out['submitted_citations']) if out['submitted_citations'] else None
    out['model_usage_events']=sum(r['runner'].get('usage_events',0) for r in timed)
    out['product_version_errors']=sum(r['grade']['product_errors']+r['grade']['version_errors'] for r in valid)
    for name in ('calls','context_bytes','elapsed_seconds'):
        vals=sorted(r['runner'][name] for r in timed)
        out[name]={'n':len(vals),'mean':sum(vals)/len(vals) if vals else None,
            'p50':vals[math.ceil(len(vals)*.5)-1] if vals else None,'p95':vals[math.ceil(len(vals)*.95)-1] if vals else None}
    out['first_requests']=sum(r.get('repetition',0)==0 for r in timed)
    out['repeat_requests']=len(timed)-out['first_requests']
    out['usage_reported']=sum(bool(r['runner'].get('token_usage')) for r in timed)
    tokens=[r['runner']['token_usage']['total']['totalTokens'] for r in timed if r['runner'].get('token_usage')]
    out['observed_tokens']={'n':len(tokens),'mean':sum(tokens)/len(tokens) if tokens else None,'total':sum(tokens)}
    out['ranking_means']={k:sum(r['grade']['rankings'][k] for r in answerable)/len(answerable) if answerable else None for k in ('hit_at_1','hit_at_5','hit_at_10','recall_at_5','recall_at_10','mrr_at_10','duplicate_document_rate')}
    return out
