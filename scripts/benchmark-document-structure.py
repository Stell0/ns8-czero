#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen synthetic coverage comparison, without models or remote providers."""
import hashlib
import json
from czero_core.extraction import Extracted
from czero_core.structure import derive,section_chunks


def benchmark():
    # Evidence labels are independent source phrases, not inferred answers.
    body=('# Preparation\n\nSafety key K17 is required before energizing.\n\n'+
        'The housing is blue.\n\n'*60+'## Procedure\n\nInsert K17 and turn the switch clockwise.\n\n'+
        'Check the indicator.\n\n'*60+'## Verification\n\nA green light confirms the switch state.\n')
    labels=['Safety key K17 is required before energizing.','Insert K17 and turn the switch clockwise.',
        'A green light confirms the switch state.']
    evidence=Extracted(body,[]); structure=derive(evidence,'text/markdown'); reports={}
    for profile in ('fixed-v1','sections-v1'):
        values=section_chunks(evidence,structure,profile=profile)
        covered=sum(any(label in chunk['text'] for chunk in values) for label in labels)
        assert covered==len(labels)
        assert all(chunk['text']==body[chunk['start']:chunk['end']] for chunk in values)
        reports[profile]={'chunks':len(values),'indexed_bytes':sum(len(chunk['text'].encode()) for chunk in values),
            'required_evidence':len(labels),'covered_evidence':covered,'exact_spans':True}
    return {'schema':1,'corpus_sha256':hashlib.sha256(body.encode()).hexdigest(),
        'measurement':'synthetic extraction spans and evidence containment; no model answer or ranking claim','profiles':reports}


if __name__=='__main__': print(json.dumps(benchmark(),sort_keys=True))
