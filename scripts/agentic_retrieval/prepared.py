# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reuse frozen analyst labels across identical disposable source snapshots."""
from copy import deepcopy
import json
from pathlib import Path

from .protocol import digest,validate_corpus,validate_questions
from .layer import validate_plan


def load_prepared(directory,corpus):
    directory=Path(directory)
    old=json.loads((directory/'corpus.json').read_text())
    questions=json.loads((directory/'questions.json').read_text())
    plan=json.loads((directory/'initial-layer-builder/validated.json').read_text())
    validate_corpus(old);validate_corpus(corpus);validate_questions(questions,old);validate_plan(plan,old)
    frozen=json.loads((directory/'freeze.json').read_text())
    if frozen['questions']!=digest(questions) or frozen['corpus']!=digest(old) or frozen['plan']!=digest(plan):raise ValueError('prepared_freeze_changed')
    by_url={d['url']:d for d in corpus}
    if set(by_url)!={d['url'] for d in old}:raise ValueError('prepared_selection_changed')
    mapping={};chunks={}
    for d in old:
        target=by_url[d['url']]
        if any(d[k]!=target[k] for k in ('body','content_hash','product','version','language')):
            raise ValueError('prepared_body_or_metadata_drift')
        mapping[d['id']]=target
        for c in d['chunks']:
            matches=[n for n in target['chunks'] if all(c[k]==n[k] for k in ('content_hash','body','source_hash','start_offset','end_offset'))]
            if len(matches)!=1:raise ValueError('prepared_chunk_layout_changed')
            chunks[c['chunk_id']]=matches[0]['chunk_id']
    rebound=deepcopy(questions);layer=deepcopy(plan)
    def bind(e):
        target=mapping[e['document_id']]
        e['document_id']=target['id'];e['generation']=target['generation']
        if 'chunk_id' in e:e['chunk_id']=chunks[e['chunk_id']]
    for q in rebound:
        for complete in q['evidence_sets']:
            for alternatives in complete:
                for e in alternatives:bind(e)
    for r in layer['records']:
        for e in r['evidence']:bind(e)
    exposed=any(directory.glob('validation-*/runner.json')) or any(directory.glob('sealed-*/runner.json'))
    for q in rebound:
        if exposed:q['previously_exposed']=True;q['split']='development'
    validate_questions(rebound,corpus);validate_plan(layer,corpus)
    builder_protocol=json.loads((directory/'protocol.json').read_text()) if (directory/'protocol.json').exists() else {}
    proof={'builder_source':builder_protocol.get('source'),'source_freeze_hash':digest(frozen),'original_questions_hash':digest(questions),
           'rebound_questions_hash':digest(rebound),'source_builder_hash':digest(plan),
           'only_identity_bindings_changed':True,'previous_test_exposure':exposed,
           'partitions':{q['id']:q['split'] for q in rebound},
           'boundary':'New measured episodes must execute real tools; no saved calls or grades are replayed.'}
    return rebound,layer,proof
