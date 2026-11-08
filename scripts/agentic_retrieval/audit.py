# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bind independent analyst answer judgments to frozen, actually observed evidence."""
import json
from pathlib import Path
from .protocol import digest


def answer_audit(output, reviews):
    output = Path(output)
    corpus = json.loads((output/'corpus.json').read_text())
    questions = json.loads((output/'questions.json').read_text())
    freeze = json.loads((output/'freeze.json').read_text())
    if freeze['corpus'] != digest(corpus) or freeze['questions'] != digest(questions):
        raise ValueError('audit_frozen_inputs_changed')
    if (set(reviews) != {'freeze_hash','provenance','independent_of_producer','episodes'}
            or reviews['freeze_hash'] != digest(freeze) or reviews['independent_of_producer'] is not True
            or not isinstance(reviews['provenance'],str) or not reviews['provenance'].strip()
            or not isinstance(reviews['episodes'],list)):
        raise ValueError('independent_answer_audit_required')
    rows = {}
    for path in sorted(output.glob('*/episode.json')):
        row = json.loads(path.read_text())
        if path.parent.name in rows:raise ValueError('duplicate_audit_episode')
        rows[path.parent.name] = row
    seen = set(); audited = []
    truth = {c['chunk_id'] for d in corpus for c in d['chunks']}
    for review in reviews['episodes']:
        required = {'episode','episode_hash','all_assertions_reviewed','correct','assertions','rationale'}
        if set(review)-{'content_correct'} != required or review['episode'] in seen:
            raise ValueError('duplicate_or_invalid_answer_review')
        seen.add(review['episode']);row = rows.get(review['episode'])
        if row is None or row['status'] != 'measured' or review['episode_hash'] != digest(row):
            raise ValueError('answer_review_missing_or_changed_episode')
        for judgment in (review['correct'],review.get('content_correct')):
            if type(judgment) is not bool and judgment is not None:
                raise ValueError('invalid_correctness_judgment')
        if (review['all_assertions_reviewed'] is not True or not isinstance(review['rationale'],str)
                or not review['rationale'].strip() or not isinstance(review['assertions'],list)):
            raise ValueError('incomplete_answer_review')
        final = row['runner']['final'];texts = [final['answer'],*[p['statement'] for p in final['parts']]]
        observed = set(row['grade']['observed_original_chunks']) & truth
        assertions = review['assertions'];unique = set()
        if final['outcome'] == 'completed' and not assertions:
            raise ValueError('completed_answer_without_assertion_review')
        for assertion in assertions:
            if (set(assertion) != {'text','verdict','chunk_ids'} or not isinstance(assertion['text'],str)
                    or not assertion['text'] or assertion['text'] in unique
                    or not any(assertion['text'] in t for t in texts)
                    or assertion['verdict'] not in ('supported','unsupported','uncertain')
                    or not isinstance(assertion['chunk_ids'],list)
                    or any(not isinstance(c,str) for c in assertion['chunk_ids'])
                    or not set(assertion['chunk_ids']) <= observed):
                raise ValueError('invalid_or_unobserved_assertion_review')
            unique.add(assertion['text'])
            if assertion['verdict'] == 'supported' and not assertion['chunk_ids']:
                raise ValueError('supported_review_requires_observed_original')
        unsupported = sum(a['verdict'] == 'unsupported' for a in assertions)
        uncertain = sum(a['verdict'] == 'uncertain' for a in assertions)
        if review.get('content_correct') is True and (unsupported or uncertain):
            raise ValueError('content_review_conflicts_with_failed_support')
        if review['correct'] is True and (unsupported or uncertain or row['grade']['invalid_citations']
                or row['grade']['product_errors'] or row['grade']['version_errors']):
            raise ValueError('correct_review_conflicts_with_failed_support')
        audited.append({'episode':review['episode'],'answerability':row['answerability'],
            'correct':review['correct'],'content_correct':review.get('content_correct'),'assertions':len(assertions),'unsupported':unsupported,'uncertain':uncertain})
    def aggregate(ids):
        measured = [name for name in ids if rows[name]['status'] == 'measured']
        selected = [r for r in audited if r['episode'] in ids]
        known = [r for r in selected if r['correct'] is not None]
        answerable = [r for r in known if r['answerability'] == 'answerable']
        content = [r for r in selected if r['content_correct'] is not None]
        return {'episodes':len(ids),'measured':len(measured),'runner_failures':len(ids)-len(measured),
            'reviewed':len(selected),'unreviewed':len(measured)-len(selected),'unknown':len(selected)-len(known),
            'accuracy':sum(r['correct'] for r in known)/len(known) if known else None,
            'accuracy_n':len(known),'content_accuracy':sum(r['content_correct'] for r in content)/len(content) if content else None,
            'content_accuracy_n':len(content),'content_unreviewed':len(selected)-len(content),'answerable_accuracy':sum(r['correct'] for r in answerable)/len(answerable) if answerable else None,
            'answerable_accuracy_n':len(answerable),'reviewed_assertions':sum(r['assertions'] for r in selected),
            'unsupported_assertions':sum(r['unsupported'] for r in selected),'uncertain_assertions':sum(r['uncertain'] for r in selected)}
    return {'freeze_hash':digest(freeze),'reviews_hash':digest(reviews),'provenance':reviews['provenance'],
        'judgment':'source-based analyst attestation, not independent human adjudication or automated entailment',
        'summary':aggregate(set(rows)),
        'arms':{arm:aggregate({name for name in rows if len(name.split('-',3))==4 and name.split('-',3)[2]==arm}) for arm in ('raw','enriched')},
        'monetary_cost':None,'monetary_cost_status':'unknown unless provider separately reports it'}
